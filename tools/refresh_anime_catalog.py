"""Refresh the public anime index without downloading videos."""
import json
import gzip
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ORIGIN = 'https://linkani.tv'
CHECKPOINT = Path('/tmp/hscope-anime-index')


def parse_index(html):
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    for card in soup.select('.vod-item'):
        a = card.select_one('.vod-item-title a[href]')
        if not a:
            continue
        match = re.fullmatch(r'/ani/([1-9]\d{0,8})/?', a['href'])
        if not match:
            continue
        visual = card.select_one('[data-original]')
        desc = card.select_one('.vod-item-desc')
        items.append(dict(id=match[1], title=a.get_text(' ', strip=True),
                          image=urljoin(ORIGIN, visual.get('data-original', '')) if visual else '',
                          description=desc.get_text(' ', strip=True).rstrip(' .') if desc else '',
                          series=1, episode=1))
    pages = [int(m[1]) for a in soup.select('a[href]')
             if (m := re.fullmatch(r'/list/2/page/(\d+)/?', a['href']))]
    return items, max(pages, default=1)


def fetch_page(page):
    saved = CHECKPOINT / f'{page}.json'
    if saved.exists():
        return json.loads(saved.read_text())
    url = ORIGIN + ('/list/2/' if page == 1 else f'/list/2/page/{page}/')
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=(10, 25), allow_redirects=False)
            r.raise_for_status()
            rows, last = parse_index(r.text)
            if not rows:
                raise ValueError('empty index')
            data = dict(items=rows, last=last)
            saved.write_text(json.dumps(data, ensure_ascii=False))
            return data
        except (requests.RequestException, ValueError):
            if attempt == 2:
                raise
            time.sleep(attempt+1)


def main():
    CHECKPOINT.mkdir(exist_ok=True)
    first = fetch_page(1)
    last = first['last']
    completed, failed = {1: first['items']}, []
    print(f'Index pages: {last}', flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {pool.submit(fetch_page, p): p for p in range(2, last+1)}
        for job in as_completed(pending):
            page = pending[job]
            try:
                completed[page] = job.result()['items']
            except Exception:
                failed.append(page)
            if (len(completed)+len(failed)) % 10 == 0:
                print(f'Pages {len(completed)}/{last}, failures {len(failed)}', flush=True)
    if failed:
        print(f'Incomplete: {sorted(failed)}; keeping existing catalog', flush=True)
        sys.exit(1)
    seen, items = set(), []
    for page in sorted(completed):
        for item in completed[page]:
            if item['id'] not in seen:
                seen.add(item['id'])
                items.append(item)
    target = Path('static/data/anime_catalog.json.gz')
    target.parent.mkdir(exist_ok=True)
    data = dict(updated_at=datetime.now(timezone.utc).isoformat(), source=ORIGIN+'/list/2/',
                pages=last, complete=True, items=items)
    temp = target.with_suffix('.tmp')
    temp.write_bytes(gzip.compress(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode(), mtime=0))
    temp.replace(target)
    print(f'Complete: {len(items)} unique works, {last} pages', flush=True)


if __name__ == '__main__':
    main()
