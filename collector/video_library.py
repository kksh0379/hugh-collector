"""Source metadata and short-lived playback URLs; media is never proxied."""
import re
import time
import math
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from flask import Blueprint, jsonify, request, send_file, session, redirect, Response, url_for
from . import video_hls, db

bp = Blueprint('video_library', __name__)
ORIGIN = 'https://linkani.tv'
TITLE_NAMES = {'19240': '강철의 연금술사', '3217': '원피스',
               '21707': '나루토', '2010': '보루토', '70867': '바람의 검심'}
WATCH = re.compile(r'^/watch/([1-9]\d{0,8})/a([1-9]\d{0,3})/k([1-9]\d{0,4})/?$')
_STATE_LOCK = threading.RLock()
_CHECK_SLOTS = threading.BoundedSemaphore(2)
_EPISODE_STATES = {}


def episode_states(title_id):
    with _STATE_LOCK:
        if title_id not in _EPISODE_STATES:
            try:
                import json
                saved = json.loads(db.get_meta('video_availability_' + title_id, '{}') or '{}')
            except Exception:
                saved = {}
            if len(_EPISODE_STATES) >= 128:
                _EPISODE_STATES.pop(next(iter(_EPISODE_STATES)))
            _EPISODE_STATES[title_id] = saved if isinstance(saved, dict) else {}
        return {key: value for key, value in _EPISODE_STATES[title_id].items()
                if isinstance(value, dict) and time.time() - value.get('checked_at', 0) < 21600}


def record_episode(title_id, series, episode, state):
    if state not in ('available', 'missing'):
        return
    with _STATE_LOCK:
        values = episode_states(title_id)
        values[f'{series}:{episode}'] = dict(status=state, checked_at=time.time())
        _EPISODE_STATES[title_id] = values
        try:
            import json
            db.set_meta('video_availability_' + title_id, json.dumps(values))
        except Exception:
            pass


def check_episode(title_id, series, episode):
    key = f'{series}:{episode}'
    known = episode_states(title_id).get(key)
    if known:
        return key, known['status']
    path = f'/watch/{title_id}/a{series}/k{episode}/'
    state = 'unknown'
    try:
        with _CHECK_SLOTS:
            response = requests.get(ORIGIN + path, timeout=(5, 10), allow_redirects=False)
        if response.status_code in (404, 410):
            state = 'missing'
        elif response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            player = parse_playback(response.text)
            if player:
                target = player['src']
                for _ in range(4):
                    with _CHECK_SLOTS:
                        with requests.get(target, timeout=(5, 10), stream=True, allow_redirects=False) as media:
                            if media.status_code in (301, 302, 303, 307, 308):
                                target = urljoin(target, media.headers.get('Location', ''))
                                if not video_hls.safe_media_url(target):
                                    break
                                continue
                            if media.status_code in (404, 410):
                                state = 'missing'
                            elif media.status_code in (200, 206):
                                state = 'available'
                    break
            else:
                canonical = soup.select_one('link[rel="canonical"][href], meta[property="og:url"][content]')
                page_path = urlparse(canonical.get('href') or canonical.get('content') or '').path if canonical else ''
                # A captcha/error page or unsupported embedded player is not a missing video.
                if (page_path.rstrip('/') == path.rstrip('/') or soup.select_one('#linktv-video')) and not soup.select_one('video[src], video source[src], iframe[src]'):
                    state = 'missing'
        if state == 'unknown':
            print(f'[video] 회차 사전 확인 보류: {title_id}/{series}/{episode} · HTTP {response.status_code}', flush=True)
    except requests.RequestException:
        print(f'[video] 회차 사전 확인 연결 지연: {title_id}/{series}/{episode}', flush=True)
    record_episode(title_id, series, episode, state)
    return key, state


@bp.get('/api/videos/availability')
def availability():
    title_id, series = request.args.get('id', ''), request.args.get('series', '')
    raw = request.args.get('episodes', '').split(',')
    if not 1 <= len(raw) <= 12 or any(not WATCH.fullmatch(f'/watch/{title_id}/a{series}/k{ep}/') for ep in raw):
        return jsonify(error='회차 범위를 확인해 주세요.'), 400
    try:
        data = load_catalog(title_id, series, raw[0], int(time.time() // 300))
        allowed = next((s['episodes'] for s in data['series'] if s['id'] == int(series)), [])
        if any(int(ep) not in allowed for ep in raw):
            return jsonify(error='등록된 회차만 확인할 수 있어요.'), 400
        with ThreadPoolExecutor(max_workers=2) as pool:
            states = dict(pool.map(lambda ep: check_episode(title_id, series, ep), raw))
        return jsonify(states=states)
    except requests.RequestException:
        return jsonify(states={f'{series}:{ep}': 'unknown' for ep in raw})


def parse_playback(html):
    soup = BeautifulSoup(html, 'html.parser')
    video = soup.select_one('video#linktv-video')
    if not video:
        return None
    source = video.find('source', src=True)
    url = video.get('src') or (source.get('src') if source else '')
    safe = video_hls.safe_media_url
    if not safe(url):
        return None
    tracks = [dict(src=t['src'], language=t.get('srclang', 'ko'), label=t.get('label', '한국어'))
              for t in video.select('track[src]') if safe(t['src'])]
    return dict(src=url, tracks=tracks)


@lru_cache(maxsize=128)
def _watch_response(path, bucket):
    response = requests.get(ORIGIN + path, timeout=(5, 10), allow_redirects=False)
    if response.status_code not in (200, 404, 410):
        response.raise_for_status()
    return response


@bp.get('/api/videos/playback')
def playback():
    parts = [request.args.get(key, '') for key in ('id', 'series', 'episode')]
    path = f'/watch/{parts[0]}/a{parts[1]}/k{parts[2]}/'
    if not WATCH.fullmatch(path):
        return jsonify(error='영상 주소를 확인해 주세요.'), 400
    try:
        subtitle_delay = float(request.args.get('subtitle_delay', '0'))
        if not math.isfinite(subtitle_delay) or not -10 <= subtitle_delay <= 10:
            raise ValueError()
    except ValueError:
        return jsonify(error='자막 조정 범위를 확인해 주세요.'), 400
    try:
        response = requests.get(ORIGIN + path, timeout=(5, 10), allow_redirects=False) if request.args.get('refresh') == '1' else _watch_response(path, int(time.time() // 120))
        if response.status_code in (404, 410):
            record_episode(*parts, 'missing')
            result = jsonify(error='원출처에 이 회차의 영상이 없어요. 다른 회차를 선택해 주세요.', code='video_missing')
            result.status_code = 404
            result.headers['Cache-Control'] = 'no-store'
            return result
        response.raise_for_status()
        data = parse_playback(response.text) if response.status_code == 200 else None
        if data and data.get('tracks') and request.args.get('probe') != '1':
            data['subtitle_delay'] = subtitle_delay
            data['native_src'] = url_for('video_library.native_manifest', token=video_hls.encode_playback(data), _external=True, _scheme='https')
        absent = response.status_code == 200 and not BeautifulSoup(response.text, 'html.parser').select_one('video[src], video source[src], iframe[src]')
        result = jsonify(data or dict(error='원출처에서 재생 가능한 영상을 찾지 못했어요. 다른 회차를 선택해 주세요.' if absent else '영상 연결 형식을 확인하지 못했어요. 다시 시도해 주세요.', code='video_missing' if absent else 'unsupported_player'))
        result.status_code = 200 if data else 404 if absent else 409
    except requests.RequestException:
        result = jsonify(error='원본 재생 영역으로 연결할게요.')
        result.status_code = 502
    result.headers['Cache-Control'] = 'no-store'
    return result


@bp.get('/api/videos/original')
def original():
    if not session.get('admin'):
        return jsonify(error='관리자만 원문 링크를 열 수 있어요.'), 403
    parts = [request.args.get(key, '') for key in ('id', 'series', 'episode')]
    path = f'/watch/{parts[0]}/a{parts[1]}/k{parts[2]}/'
    if not WATCH.fullmatch(path):
        return jsonify(error='영상 주소를 확인해 주세요.'), 400
    return redirect(ORIGIN + path)


def hls_response(text, mime='application/vnd.apple.mpegurl'):
    response = Response(text, mimetype=mime)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@bp.get('/api/videos/native.m3u8')
def native_manifest():
    try:
        token = request.args.get('token', '')
        data = video_hls.decode_playback(token)
        text = video_hls.load_text(data['src'])
        return hls_response(video_hls.master_playlist(text, data['src'], data['tracks'], token))
    except Exception:
        return jsonify(error='자막 포함 재생 목록을 불러오지 못했어요.'), 502


def subtitle_source():
    token = request.args.get('token', '')
    data = video_hls.decode_playback(token)
    index = int(request.args.get('track', '0'))
    if not 0 <= index < len(data['tracks']):
        raise ValueError('invalid track')
    return token, index, video_hls.load_text(data['tracks'][index]['src']), float(data.get('subtitle_delay', 0))


@bp.get('/api/videos/subtitles.m3u8')
def subtitle_playlist():
    try:
        token, index, text, delay = subtitle_source()
        _, count = video_hls.subtitle_segments(text, delay)
        lines = ['#EXTM3U', '#EXT-X-VERSION:6', '#EXT-X-TARGETDURATION:6', '#EXT-X-MEDIA-SEQUENCE:0', '#EXT-X-PLAYLIST-TYPE:VOD']
        for segment in range(count):
            lines += ['#EXTINF:6.000,', url_for('video_library.subtitle_vtt', token=token, track=index, segment=segment, _external=True, _scheme='https')]
        return hls_response('\n'.join(lines + ['#EXT-X-ENDLIST', '']))
    except Exception:
        return jsonify(error='자막 재생 목록을 불러오지 못했어요.'), 502


@bp.get('/api/videos/subtitle.vtt')
def subtitle_vtt():
    try:
        _, _, text, delay = subtitle_source()
        return hls_response(video_hls.subtitle_segment(text, int(request.args.get('segment', '0')), delay), 'text/vtt')
    except Exception:
        return jsonify(error='자막을 불러오지 못했어요.'), 502


@bp.get('/api/videos/library')
def library():
    path = Path(__file__).resolve().parent.parent / 'static/data/anime_catalog.json.gz'
    if not path.exists():
        return jsonify(error='전체 작품 목록을 준비하고 있어요.'), 503
    response = send_file(path, mimetype='application/json', conditional=True, max_age=3600)
    response.headers['Content-Encoding'] = 'gzip'
    return response


def parse_page(html, title_id, series, episode, include_requested=True):
    soup = BeautifulSoup(html, 'html.parser')
    meta = soup.find('meta', property='og:title')
    title = meta.get('content', '') if meta else ''
    title = re.sub(r'\s+-\s+Anime\s+-\s+Linkkf.*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s+\d+화(?:\s.*)?$', '', title).strip() or f'작품 {title_id}'
    title = TITLE_NAMES.get(title_id, title)
    found = {}
    for a in soup.select('a[href]'):
        u = urlparse(urljoin(ORIGIN, a['href']))
        m = WATCH.fullmatch(u.path)
        if u.netloc != 'linkani.tv' or u.scheme != 'https' or not m or m[1] != title_id:
            continue
        sid, ep = int(m[2]), int(m[3])
        found.setdefault(sid, set()).add(ep)
    # The requested page itself is a valid selection even without navigation.
    if include_requested:
        found.setdefault(int(series), set()).add(int(episode))
    poster = soup.find('meta', property='og:image')
    image = poster.get('content', '') if poster else ''
    if urlparse(image).scheme != 'https':
        image = ''
    return dict(id=title_id, title=title[:160], image=image,
                series=[dict(id=sid, episodes=sorted(eps)) for sid, eps in sorted(found.items())])


@lru_cache(maxsize=128)
def _load_catalog_page(title_id, bucket):
    url = f'{ORIGIN}/ani/{title_id}/'
    response = requests.get(url, timeout=(10, 15), allow_redirects=False)
    if response.status_code != 200:
        raise requests.RequestException('watch page unavailable')
    return parse_page(response.text, title_id, '1', '1', include_requested=False)


def load_catalog(title_id, series, episode, bucket):
    # Every episode uses the same /ani page. Do not refetch it for each batch.
    return _load_catalog_page(title_id, bucket)


@bp.get('/api/videos/catalog')
def catalog():
    parts = [request.args.get(key, default) for key, default in
             [('id', '19240'), ('series', '1'), ('episode', '8')]]
    if not WATCH.fullmatch(f'/watch/{parts[0]}/a{parts[1]}/k{parts[2]}/'):
        return jsonify(error='영상 주소를 확인해 주세요.'), 400
    try:
        data = load_catalog(*parts, int(time.time() // 300))
        if not data.get('series'):
            return jsonify(error='이 작품은 아직 재생할 수 있는 회차가 등록되지 않았어요.'), 409
        return jsonify(dict(data, availability=episode_states(parts[0])))
    except requests.RequestException:
        # Snapshot verified from the supplied page; never invent episode ranges.
        if parts[0] == '19240' and parts[1] == '1' and 1 <= int(parts[2]) <= 68:
            return jsonify(id='19240', title='강철의 연금술사',
                           image='https://linkani.tv/anime_uploads/anilist-5114.jpg',
                           series=[dict(id=1, episodes=list(range(1, 69)))], stale=True)
        return jsonify(error='작품 정보를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.'), 502
