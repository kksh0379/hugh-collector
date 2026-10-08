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
    out = []
    for source in items:
        row = dict(source)
        for index, old in enumerate(out):
            if not _same(old, row):
                continue
            # Original schedule beats extracted news; retain richer missing fields.
            if old.get('source') in ('', '뉴스', None) and row.get('source') not in ('', '뉴스', None):
                preferred, other = row, old
            else:
                preferred, other = old, row
            out[index] = dict(preferred)
            for field in ('content', 'image_url', 'venue', 'region', 'end_date', 'author'):
                if not out[index].get(field) and other.get(field):
                    out[index][field] = other[field]
            break
        else:
            out.append(row)
    return out
