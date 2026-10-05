"""HLS subtitle renditions for native playback/AirPlay; video bytes stay at source."""
import math
import re
from functools import lru_cache
from urllib.parse import urljoin, urlparse

import requests
from flask import current_app, url_for
from itsdangerous import URLSafeTimedSerializer


def safe_media_url(value):
    try:
        u = urlparse(value)
        return (u.scheme == 'https' and bool(re.fullmatch(r'aniplayer\d+\.site', u.hostname or ''))
                and not u.username and not u.password and u.port in (None, 443))
    except ValueError:
        return False


def serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt='video-subtitles-v1')


def encode_playback(data):
    return serializer().dumps(data)


def decode_playback(token):
    data = serializer().loads(token, max_age=21600)
    if not isinstance(data, dict) or not safe_media_url(data.get('src', '')):
        raise ValueError('invalid source')
    tracks = data.get('tracks', [])
    if not isinstance(tracks, list) or len(tracks) > 16 or any(not safe_media_url(t.get('src', '')) for t in tracks):
        raise ValueError('invalid subtitle')
    return data


@lru_cache(maxsize=32)
def load_text(url):
    if not safe_media_url(url):
        raise ValueError('invalid source')
    with requests.get(url, timeout=(5, 10), allow_redirects=False, stream=True) as response:
        if response.status_code != 200:
            raise ValueError('source unavailable')
        chunks, size = [], 0
        for chunk in response.iter_content(16384):
            size += len(chunk)
            if size > 2_000_000:
                raise ValueError('source too large')
            chunks.append(chunk)
    return b''.join(chunks).decode('utf-8-sig')


def attribute(value):
    return re.sub(r'["\r\n]', '', str(value))[:80]


def master_playlist(text, source, tracks, token):
    if not text.lstrip().startswith('#EXTM3U'):
        raise ValueError('invalid playlist')
    media = []
    for i, track in enumerate(tracks):
        uri = url_for('video_library.subtitle_playlist', token=token, track=i, _external=True, _scheme='https')
        media.append(f'#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="hscope-captions",NAME="{attribute(track.get("label", "한국어"))} {i+1}",LANGUAGE="{attribute(track.get("language", "ko"))}",DEFAULT={"YES" if i == 0 else "NO"},AUTOSELECT=YES,FORCED=NO,URI="{uri}"')
    if '#EXT-X-STREAM-INF:' not in text:
        return '\n'.join(['#EXTM3U', '#EXT-X-VERSION:6', *media,
                          '#EXT-X-STREAM-INF:BANDWIDTH=2500000,SUBTITLES="hscope-captions"', source, ''])
    lines = []
    for line in text.splitlines():
        if line.startswith('#EXT-X-MEDIA:') and re.search(r'(?:^|[:,])TYPE=SUBTITLES(?:,|$)', line):
            continue
        if line.startswith('#EXT-X-STREAM-INF:'):
            line = re.sub(r',?SUBTITLES="[^"]*"', '', line) + ',SUBTITLES="hscope-captions"'
        if line.startswith('#'):
            line = re.sub(r'URI="([^"]+)"', lambda m: 'URI="' + urljoin(source, m[1]) + '"', line)
        elif line.strip():
            line = urljoin(source, line.strip())
        lines.append(line)
    lines[1:1] = media
    return '\n'.join(lines) + '\n'


def timestamp(value):
    parts = value.split(':')
    return sum(float(p) * 60 ** i for i, p in enumerate(reversed(parts)))


def vtt_cues(text):
    if not text.lstrip('\ufeff').startswith('WEBVTT'):
        raise ValueError('invalid subtitles')
    cues = []
    seen = set()
    for block in re.split(r'\n\s*\n', text.replace('\r\n', '\n')):
        match = re.search(r'(\d{2}:)?\d{2}:\d{2}\.\d{3}\s+-->\s+((?:\d{2}:)?\d{2}:\d{2}\.\d{3})', block)
        if not match:
            continue
        start_value = match.group(0).split('-->')[0].strip()
        start, end = timestamp(start_value), timestamp(match[2])
        if end > start:
            key = (start, end, block[match.end():].strip())
            if key in seen:
                continue
            seen.add(key)
            cues.append((start, end, block))
    # A complete but empty WEBVTT file is a valid empty subtitle track.
    return cues


def subtitle_segments(text):
    cues = vtt_cues(text)
    duration = max((end for _, end, _ in cues), default=6)
    if duration > 86400:
        raise ValueError('subtitles too long')
    return cues, max(1, math.ceil(duration / 6))


def subtitle_segment(text, index):
    cues, count = subtitle_segments(text)
    if not 0 <= index < count:
        raise ValueError('invalid segment')
    def clock(seconds):
        milliseconds = round(seconds * 1000)
        return f'{milliseconds // 3600000:02}:{milliseconds // 60000 % 60:02}:{milliseconds // 1000 % 60:02}.{milliseconds % 1000:03}'
    blocks = []
    for cue_id, (start, end, block) in enumerate(cues):
        if start >= (index + 1) * 6 or end <= index * 6:
            continue
        # Adjacent segments must never render overlapping copies of one cue.
        lines = block.splitlines()
        timing_index = next(i for i, line in enumerate(lines) if '-->' in line)
        timing = re.sub(r'(?:(?:\d{2}:)?\d{2}:\d{2}\.\d{3})\s+-->\s+(?:(?:\d{2}:)?\d{2}:\d{2}\.\d{3})',
                        f'{clock(max(start, index * 6))} --> {clock(min(end, (index + 1) * 6))}', lines[timing_index])
        blocks.append('\n'.join([f'hscope-{cue_id}-{index}', timing, *lines[timing_index + 1:]]))
    mapping = re.search(r'^X-TIMESTAMP-MAP=[^\r\n]+', text, re.M)
    header = mapping[0] if mapping else 'X-TIMESTAMP-MAP=LOCAL:00:00:00.000,MPEGTS:0'
    return 'WEBVTT\n' + header + '\n\n' + '\n\n'.join(blocks) + '\n'
