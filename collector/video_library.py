"""Source metadata and short-lived playback URLs; media is never proxied."""
import re
import time
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from flask import Blueprint, jsonify, request, send_file

bp = Blueprint('video_library', __name__)
ORIGIN = 'https://linkani.tv'
TITLE_NAMES = {'19240': '강철의 연금술사', '3217': '원피스',
               '21707': '나루토', '2010': '보루토', '70867': '바람의 검심'}
WATCH = re.compile(r'^/watch/([1-9]\d{0,8})/a([1-9]\d{0,3})/k([1-9]\d{0,4})/?$')


def parse_playback(html):
    soup = BeautifulSoup(html, 'html.parser')
    video = soup.select_one('video#linktv-video')
    if not video:
        return None
    source = video.find('source', src=True)
    url = video.get('src') or (source.get('src') if source else '')
    def safe(value):
        u = urlparse(value)
        return u.scheme == 'https' and bool(re.fullmatch(r'aniplayer\d+\.site', u.hostname or '')) and not u.username and not u.password and u.port in (None, 443)
    if not safe(url):
        return None
    tracks = [dict(src=t['src'], language=t.get('srclang', 'ko'), label=t.get('label', '한국어'))
              for t in video.select('track[src]') if safe(t['src'])]
    return dict(src=url, tracks=tracks)


@bp.get('/api/videos/playback')
def playback():
    parts = [request.args.get(key, '') for key in ('id', 'series', 'episode')]
    path = f'/watch/{parts[0]}/a{parts[1]}/k{parts[2]}/'
    if not WATCH.fullmatch(path):
        return jsonify(error='영상 주소를 확인해 주세요.'), 400
    try:
        response = requests.get(ORIGIN + path, timeout=(5, 10), allow_redirects=False)
        response.raise_for_status()
        data = parse_playback(response.text) if response.status_code == 200 else None
        result = jsonify(data or dict(error='별도 플레이어를 연결할 수 없어요.'))
        result.status_code = 200 if data else 409
    except requests.RequestException:
        result = jsonify(error='원본 재생 영역으로 연결할게요.')
        result.status_code = 502
    result.headers['Cache-Control'] = 'no-store'
    return result


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
def load_catalog(title_id, series, episode, bucket):
    url = f'{ORIGIN}/ani/{title_id}/'
    response = requests.get(url, timeout=(10, 15), allow_redirects=False)
    if response.status_code != 200:
        raise requests.RequestException('watch page unavailable')
    return parse_page(response.text, title_id, series, episode, include_requested=False)


@bp.get('/api/videos/catalog')
def catalog():
    parts = [request.args.get(key, default) for key, default in
             [('id', '19240'), ('series', '1'), ('episode', '8')]]
    if not WATCH.fullmatch(f'/watch/{parts[0]}/a{parts[1]}/k{parts[2]}/'):
        return jsonify(error='영상 주소를 확인해 주세요.'), 400
    try:
        data = load_catalog(*parts, int(time.time() // 3600))
        if not data.get('series'):
            return jsonify(error='이 작품은 아직 재생할 수 있는 회차가 등록되지 않았어요.'), 409
        return jsonify(data)
    except requests.RequestException:
        # Snapshot verified from the supplied page; never invent episode ranges.
        if parts[0] == '19240' and parts[1] == '1' and 1 <= int(parts[2]) <= 68:
            return jsonify(id='19240', title='강철의 연금술사',
                           image='https://linkani.tv/anime_uploads/anilist-5114.jpg',
                           series=[dict(id=1, episodes=list(range(1, 69)))], stale=True)
        return jsonify(error='작품 정보를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.'), 502
