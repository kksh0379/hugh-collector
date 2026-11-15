"""Collapse equivalent public schedules without deleting source rows."""
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit


def _norm(value):
    value = unicodedata.normalize('NFKC', str(value or '')).casefold()
    return re.sub(r'[^0-9a-z가-힣]', '', value)


def _title(value):
    value = re.sub(r'\[(?:무료|사전등록|사전신청|참가신청|온라인|오프라인)[^\]]*\]', '', str(value or ''))
    return _norm(value)


def _url(value):
    parts = urlsplit(value or '')
    if not parts.hostname or parts.hostname == 'news.google.com':
        return ''
    # Preserve identity query arguments; remove tracking only.
    query = '&'.join(p for p in parts.query.split('&') if p and not p.startswith(('utm_', 'fbclid=', 'gclid=')))
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip('/'), query, ''))


def _same(left, right):
    a, b = _url(left.get('source_url') or left.get('url')), _url(right.get('source_url') or right.get('url'))
    if a and a == b:
        return True
    if not left.get('start_date') or left.get('start_date') != right.get('start_date'):
        return False
    if not _title(left.get('title')) or _title(left.get('title')) != _title(right.get('title')):
        return False
    a, b = _norm(left.get('venue')), _norm(right.get('venue'))
    return not a or not b or a in b or b in a


def merge_events(items):
    """Merge equivalent schedules without scanning all previous articles per row.

    A URL match takes priority; otherwise candidates share normalized title and
    start date. Candidate indices are kept in insertion order to preserve the
    previous first-match and source-preference behavior.
    """
    out = []
    by_url = {}
    by_title_date = {}

    def add(index, row):
        url = _url(row.get('source_url') or row.get('url'))
        if url:
            by_url.setdefault(url, set()).add(index)
        start = row.get('start_date')
        title = _title(row.get('title'))
        if start and title:
            by_title_date.setdefault((start, title), set()).add(index)

    for source in items:
        row = dict(source)
        url = _url(row.get('source_url') or row.get('url'))
        start = row.get('start_date')
        title = _title(row.get('title'))
        candidates = set(by_url.get(url, ())) if url else set()
        if start and title:
            candidates.update(by_title_date.get((start, title), ()))
        match = next((i for i in sorted(candidates) if _same(out[i], row)), None)
        if match is None:
            out.append(row)
            add(len(out) - 1, row)
            continue
        old = out[match]
        if old.get('source') in ('', '뉴스', None) and row.get('source') not in ('', '뉴스', None):
            preferred, other = row, old
        else:
            preferred, other = old, row
        merged = dict(preferred)
        for field in ('content', 'image_url', 'venue', 'region', 'end_date', 'author'):
            if not merged.get(field) and other.get(field):
                merged[field] = other[field]
        out[match] = merged
        add(match, merged)
    return out
