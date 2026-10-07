"""Bounded, persistent repair queue for missing event posters."""
import hashlib
import json
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from . import db, extractor, fetcher, google_news

_lock = threading.Lock()
_status = {}


def extract(html, url):
    soup = BeautifulSoup(html, 'lxml')
    image = extractor.extract_image(soup, url)
    if image and not re.search(r'logo|noimage|no_image|default_image', image, re.I):
        return image
    # Venue detail pages often use a poster block rather than article markup.
    for node in soup.select('.poster img, .event-poster img, .event-image img, .event_view img, .event-view img, .view-cont img, .board-view img, .kboard-content img, img.poster'):
        for attr in ('data-original', 'data-src', 'data-lazy-src', 'src'):
            value = node.get(attr, '')
            if not value or re.search(r'logo|icon|noimage|no_image|default|data:', value, re.I):
                continue
            image = urljoin(url, value)
            if image.startswith(('http://', 'https://')):
                return image
    return ''


def fetch(row):
    try:
        url = row.get('source_url') or row['url']
        if 'news.google.' in url:
            url = google_news._decode_google_url(url)
        if not url:
            return row['url'], '', '원문 복원 실패'
        response = fetcher.get(url, retries=0, timeout=10)
        image = extract(response.text, response.url or url)
        return row['url'], image, '이미지 확보' if image else '원문 이미지 없음'
    except Exception as exc:
        return row['url'], '', type(exc).__name__


def status():
    return dict(_status)


def enrich(limit=12):
    if not _lock.acquire(blocking=False):
        return 0
    try:
        now = time.time()
        attempts = json.loads(db.get_meta('event_image_attempts_v2', '{}'))
        attempts = {key: ts for key, ts in attempts.items() if now - ts < 7 * 86400}
        with db.get_conn() as conn:
            rows = conn.execute(db._q("SELECT url, source_url FROM events WHERE "
                "(image_url IS NULL OR image_url='') AND (end_date IS NULL OR end_date='' OR end_date>=?) "
                "ORDER BY start_date ASC, id DESC LIMIT 1000"), (time.strftime('%Y-%m-%d'),)).fetchall()
        selected = []
        for row in rows:
            key = hashlib.sha256(row['url'].encode()).hexdigest()
            if key not in attempts:
                selected.append(dict(row))
                attempts[key] = now
            if len(selected) >= limit:
                break
        # Persist attempts before network work; a restart must not repeat the batch.
        db.set_meta('event_image_attempts_v2', json.dumps(attempts))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(fetch, selected))
        images = [(image, url) for url, image, _ in results if image]
        if images:
            with db.get_conn() as conn:
                conn.cursor().executemany(db._q("UPDATE events SET image_url=? WHERE url=? AND "
                    "(image_url IS NULL OR image_url='')"), images)
        _status.update(checked=True, checked_at=now, attempted=len(results), images=len(images),
                       reasons=dict(Counter(reason for _, _, reason in results)))
        if results:
            print('[event-images] ' + json.dumps(_status, ensure_ascii=False), flush=True)
        return len(images)
    finally:
        _lock.release()
