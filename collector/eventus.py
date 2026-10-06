"""Bounded public Eventus search adapter. Rejected listings never reach the DB."""
import datetime as dt
import html
import os
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

API = 'https://api.event-us.kr/api/v1/engine/search'
BASE = 'https://event-us.kr/'
KST = dt.timezone(dt.timedelta(hours=9))
_STATUS = {'checked': False, 'ok': False}
# Explicit event identity in the title beats a broad publisher category such as 강연/세미나.
_EVENT = re.compile(r'컨퍼런스|콘퍼런스|포럼|박람회|엑스포|페어|전시|밋업|네트워킹|해커톤|데모\s*데이|공모전|경진대회|축제|페스티벌|심포지엄|학술대회|서밋|발표회|공개행사|콘테스트|디캠프\s*디데이|conference|forum|expo\b|\bfair\b|meet\s*up|networking|hackathon|demo\s*day|summit|symposium|festival', re.I)
_PRODUCT = re.compile(r'체험교실|서포터즈\s*모집|전시사\s*모집|갤러리\s*모집|버스킹\s*모집|교육\s*체험|체험\s*프로그램|성장\s*프로그램|참여기업\s*모집|기업모집|지원사업|액셀러레이팅|\d+\s*기\s*모집|수강생|교육생|자격증|자격\s*과정|교육\s*과정|부트캠프|원데이\s*클래스|정기\s*클래스|상시\s*(?:모집|진행|강의)|온라인\s*강의|강의\s*(?:패키지|판매)|커리큘럼|\d+\s*(?:주차|주\s*과정)|매주\s*(?:월|화|수|목|금|토|일)|\bbootcamp\b', re.I)
_LESSON = re.compile(r'특강|강좌|강의|수업|클래스|수강|실습|교육|멘토링|컨설팅|취미\s*체험|\b(?:class|course|training|tutorial)\b', re.I)
_SEMINAR = re.compile(r'세미나|워크[숍샵]|웨비나|특별강연|seminar|workshop|webinar', re.I)
_PUBLIC = re.compile(r'산업|정책|학술|연구|거버넌스|윤리|공익|비영리|패널|토론|네트워킹|사례\s*(?:발표|공유)|공개\s*(?:행사|토론)|발표\s*세션', re.I)


def text(value):
    return re.sub(r'\s+', ' ', BeautifulSoup(html.unescape(str(value or '')), 'html.parser').get_text(' ', strip=True)).strip()


def is_event(title, description='', event_type=''):
    """Conservative contextual filter, no AI calls or review queue."""
    title, description, event_type = map(text, (title, description, event_type))
    # Selling a curriculum remains a course even when its title mentions a forum.
    if not title or _PRODUCT.search(title):
        return False
    if _EVENT.search(title):
        return True
    if _LESSON.search(title) or _PRODUCT.search(description):
        return False
    if _SEMINAR.search(title):
        return bool(_PUBLIC.search(title + ' ' + description)) and not _LESSON.search(description)
    # Clear conference/exhibition categories can identify otherwise named events.
    if event_type in {'기업회의', '학술회의', '정부회의', '컨벤션', '축제'}:
        return not _LESSON.search(description)
    return False


def _raw(row, key):
    value = row.get(key)
    return value.get('raw') if isinstance(value, dict) else value


def _date(value):
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return (parsed.astimezone(KST) if parsed.tzinfo else parsed).date()
    except (TypeError, ValueError):
        return None


def parse(row, today=None):
    today = today or dt.datetime.now(KST).date()
    if not isinstance(row, dict):
        return None
    title, description = text(_raw(row, 'title')), text(_raw(row, 'description'))
    start, end = _date(_raw(row, 'start_date')), _date(_raw(row, 'close_date'))
    if (not start or not end or end < start or end < today
            or start > today + dt.timedelta(days=180) or (end-start).days > 120):
        return None
    if not is_event(title, description, _raw(row, 'event_type')):
        return None
    event_id, channel = str(_raw(row, 'id') or ''), str(_raw(row, 'subdomain') or '')
    if not event_id.isdigit() or not re.fullmatch(r'[a-zA-Z0-9_-]+', channel):
        return None
    online = _raw(row, 'event_system_type') == 'online'
    region = text(_raw(row, 'area_detail') or _raw(row, 'area'))
    address = text(_raw(row, 'full_address') or _raw(row, 'address'))
    from .events import is_domestic
    if not is_domestic(title, address + ' ' + text(_raw(row, 'place'))):
        return None
    if not online:
        # Positive Korean venue evidence, do not infer a domestic venue from title.
        from .events import DOMESTIC_REGIONS
        if not any(place in region + ' ' + address for place in DOMESTIC_REGIONS):
            return None
    venue = '온라인' if online else text(_raw(row, 'place')) or address or region
    cost = _raw(row, 'min_money')
    try:
        price = '무료' if float(cost) == 0 else f'참가비 {int(float(cost)):,}원부터'
    except (TypeError, ValueError):
        price = ''
    deadline = _date(_raw(row, 'register_due_date'))
    summary = ' · '.join(x for x in [text(_raw(row, 'category')), description[:800], price,
                                   '신청마감 ' + deadline.isoformat() if deadline else ''] if x)
    image = str(_raw(row, 'cover_image_url') or '')
    image = urljoin(BASE, image) if image else ''
    if not image.startswith(('https://', 'http://')):
        image = ''
    url = f'{BASE}{channel}/event/{event_id}'
    return dict(title=title, published_at=today.isoformat(), author=text(_raw(row, 'app_title')) or '이벤터스',
                content=summary, url=url, source_url=url, image_url=image, venue=venue,
                region='온라인' if online else region, start_date=start.isoformat(), end_date=end.isoformat(), source='이벤터스')


def diagnose():
    return dict(_STATUS)


def collect(progress=None):
    global _STATUS
    if os.getenv('EVENTUS_OFF') == '1':
        _STATUS = {'checked': False, 'ok': True, 'disabled': True}
        return []
    today = dt.datetime.now(KST).date()
    try:
        max_pages = max(1, min(30, int(os.getenv('EVENTUS_MAX_PAGES', '30'))))
    except ValueError:
        max_pages = 30
    out, seen, scanned, excluded, pages = [], set(), 0, 0, 0
    began = time.monotonic()
    _STATUS = {'checked': True, 'ok': False}
    try:
        with requests.Session() as session:
            session.headers.update({'User-Agent': 'hscope-event-collector/1.0', 'Accept': 'application/json'})
            for page in range(1, max_pages+1):
                if time.monotonic() - began > 120:
                    raise TimeoutError('collection time budget')
                model = {'query': '', 'page': {'current': page, 'size': 100},
                         'filters': {'all': [{'state': 'Start'}, {'disclosure_status': 'open'}, {'is_ignore': 'false'},
                                           {'close_date': {'from': today.isoformat() + 'T00:00:00+09:00'}},
                                           {'start_date': {'from': (today-dt.timedelta(days=120)).isoformat() + 'T00:00:00+09:00',
                                                           'to': (today+dt.timedelta(days=181)).isoformat() + 'T00:00:00+09:00'}}]},
                         'sort': [{'start_date': 'asc'}, {'id': 'desc'}]}
                response = session.post(API, json=model, timeout=(15, 35))
                response.raise_for_status()  # Never hammer a blocked or rate-limited source.
                data = response.json()
                rows = data.get('results')
                if not isinstance(rows, list):
                    raise ValueError('unrecognized search response')
                pages += 1
                new_ids = 0
                for row in rows:
                    if not isinstance(row, dict):
                        excluded += 1
                        continue
                    key = str(_raw(row, 'id') or '')
                    if not key or key in seen:
                        continue
                    seen.add(key); new_ids += 1; scanned += 1
                    item = parse(row, today)
                    if item:
                        out.append(item)
                    else:
                        excluded += 1
                total_pages = int(data.get('meta', {}).get('page', {}).get('total_pages', page))
                if not rows or not new_ids or page >= total_pages:
                    _STATUS['ok'] = True
                    break
                if page == max_pages:
                    _STATUS['truncated'] = True
                time.sleep(0.15)
    except (requests.RequestException, ValueError, TypeError, TimeoutError) as exc:
        _STATUS['error'] = type(exc).__name__
    _STATUS.update(scanned=scanned, excluded=excluded, accepted=len(out), pages=pages)
    if progress:
        progress(f'이벤터스 행사 {len(out)}건 · 비행사/기간/지역 제외 {excluded}건'
                 + (' · 일부 수집' if not _STATUS.get('ok') else ''))
    return out
