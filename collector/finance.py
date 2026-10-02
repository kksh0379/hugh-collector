"""Finance adapters. Secrets stay server-side; unavailable data is never a verdict."""
import os
import re
import math
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, quote, urlencode
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup
from flask import Blueprint, jsonify, request
from lxml import etree
from collector.read_cache import ReadCache
from collector import reader

bp = Blueprint('finance', __name__, url_prefix='/api/finance')
cache = ReadCache(max_entries=16, workers=2)
KST = timezone(timedelta(hours=9))


def _gnews(query):
    """공식 RSS를 확인하지 못한 출처는 구글 뉴스 RSS(공개·안정 엔드포인트)로 주제별 수집한다.
    운영자가 FINANCE_RSS_<코드>에 검증된 공식 RSS를 지정하면 그 값이 항상 우선한다."""
    return 'https://news.google.com/rss/search?' + urlencode(
        {'q': query, 'hl': 'ko', 'gl': 'KR', 'ceid': 'KR:ko'})


# 공식 RSS가 확인된 출처(MOEF)는 그대로, 나머지는 구글 뉴스 주제 RSS로 기본 연결.
# 임의의 비공개 엔드포인트를 추측하지 않으며, 운영자 환경변수로 공식 RSS를 지정하면 대체된다.
SOURCES = [
    ('MOEF', '재정경제부(구 기획재정부)', 'policy', 'https://mofe.go.kr/'),
    ('NTS', '국세청·국세 뉴스', 'policy', 'https://www.nts.go.kr/'),
    ('PWC', '삼일회계법인(PwC) 뉴스', 'guide', 'https://www.pwc.com/kr/ko.html'),
    ('KPMG', '삼정KPMG 뉴스', 'guide', 'https://kpmg.com/kr/ko/home.html'),
    ('JOSEILBO', '조세일보', 'guide', 'https://www.joseilbo.com/'),
    ('ASSEMBLY', '세법 입법 동향', 'legislation', 'https://pal.assembly.go.kr/'),
]
DEFAULT_FEEDS = {
    'MOEF': 'https://mofe.go.kr/com/detailRssTagService.do?bbsId=MOSFBBS_000000000028',
    'NTS': _gnews('국세청 세금 세정'),
    'PWC': _gnews('삼일회계법인 PwC 세무'),
    'KPMG': _gnews('삼정KPMG 세무'),
    'JOSEILBO': _gnews('조세일보'),
    'ASSEMBLY': _gnews('세법 개정 입법예고'),
}
CATEGORIES = {'policy': '세법·보도자료', 'guide': '회계·세무 가이드', 'legislation': '입법예고'}
INDICATORS = [('731Y001', '0000001', '원/달러 환율', '원', 1350.0),
              ('817Y002', '010502000', 'CD 91일', '%', 3.0),
              ('817Y002', '010200000', '국고채 3년', '%', 2.8)]
# 국세 법정 신고·납부 기한. 모두 세법에 명시된 고정 기한이며, 추측이 아닌 확정 규칙입니다.
# 기한이 주말이면 다음 영업일로 조정합니다(국세기본법 제5조). 공휴일이 겹치면 추가 연장되나,
# 공휴일(특히 음력 명절) 날짜는 검증 없이 하드코딩하지 않고 안내 문구로만 처리합니다.
TAX_MONTHLY = [(10, '원천세 신고·납부', '전월 원천징수분(반기납부 승인 사업자 제외)')]
TAX_ANNUAL = [
    (1, 25, '부가가치세 제2기 확정신고·납부', '직전 과세기간(7~12월) 분'),
    (1, 25, '간이과세자 부가가치세 신고·납부', '직전 1년(1~12월) 분'),
    (2, 10, '면세사업자 사업장현황신고', '개인 면세사업자 직전 연도 수입금액'),
    (3, 31, '법인세 신고·납부', '12월 말 결산 법인'),
    (4, 25, '부가가치세 제1기 예정신고·납부', '법인사업자(개인 일반과세자는 예정고지)'),
    (5, 31, '종합소득세·개인지방소득세 확정신고·납부', '직전 연도 귀속분'),
    (6, 30, '성실신고확인대상자 종합소득세 신고·납부', '성실신고확인서 제출 대상'),
    (7, 25, '부가가치세 제1기 확정신고·납부', '1~6월 분'),
    (8, 31, '법인세 중간예납 신고·납부', '12월 말 결산 법인'),
    (10, 25, '부가가치세 제2기 예정신고·납부', '법인사업자(개인 일반과세자는 예정고지)'),
    (11, 30, '종합소득세 중간예납 납부', '고지분(11월 중 고지서 수령)'),
]
NTS_CALENDAR_URL = 'https://www.nts.go.kr/'


def now():
    return datetime.now(KST)


def safe_url(url):
    try:
        p = urlsplit(url)
        return url if p.scheme in ('https', 'http') and p.hostname and not p.username and not p.password else ''
    except ValueError:
        return ''


def get_json(url, **kwargs):
    response = requests.get(url, timeout=(3, 7), allow_redirects=False, **kwargs)
    response.raise_for_status()
    return response.json()


def plain(text):
    return BeautifulSoup(text or '', 'html.parser').get_text(' ', strip=True)


def parse_feed(content, source):
    root = etree.fromstring(content, parser=etree.XMLParser(resolve_entities=False, no_network=True, recover=False))
    if etree.QName(root).localname not in ('rss', 'feed', 'RDF'):
        raise ValueError('Not a feed')
    items = []
    for node in root.xpath('//*[local-name()="item" or local-name()="entry"]')[:30]:
        def field(*names):
            for name in names:
                found = node.xpath('./*[local-name()=$name]', name=name)
                if found:
                    return ''.join(found[0].itertext()).strip()
            return ''
        url = field('link')
        if not url:
            links = node.xpath('./*[local-name()="link"][@href]')
            url = next((x.get('href') for x in links if x.get('rel', 'alternate') == 'alternate'), '')
        url = safe_url(url)
        title = plain(field('title'))[:250]
        if title and url:
            items.append(dict(category=source[2], source=source[1], title=title,
                              description=plain(field('description', 'summary', 'content'))[:500],
                              url=url, pub_date=field('pubDate', 'published', 'updated', 'date')[:80], mode='live'))
    return items


def collect_source(source):
    env = 'FINANCE_RSS_' + source[0]
    url = os.getenv(env, DEFAULT_FEEDS.get(source[0], '')).strip()
    status = dict(name=source[1], category=source[2], url=source[3], mode='unconfigured')
    if not url:
        return [], status
    try:
        # Operator-controlled URL only; no arbitrary URL is accepted from a browser.
        if not safe_url(url) or urlsplit(url).scheme != 'https':
            raise ValueError('HTTPS required')
        with requests.get(url, timeout=(3, 6), stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(32768):
                size += len(chunk)
                if size > 2 * 1024 * 1024:
                    raise ValueError('Feed too large')
                chunks.append(chunk)
        items = parse_feed(b''.join(chunks), source)
        status.update(mode='live', count=len(items))
        return items, status
    except Exception:
        status['mode'] = 'unavailable'
        return [], status


def news():
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(collect_source, SOURCES))
    items, sources, seen = [], [], set()
    for rows, status in results:
        sources.append(status)
        for row in rows:
            if row['url'] not in seen:
                seen.add(row['url'])
                items.append(row)
    return dict(items=items, sources=sources, fetched_at=now().isoformat())


def sample_history(values, points=26):
    """최근 6개월 추이를 과밀하지 않게 균등 샘플링. 가장 최신 값은 항상 포함한다."""
    if len(values) <= points:
        sampled = values
    else:
        step = (len(values) - 1) / (points - 1)
        index = sorted({round(i * step) for i in range(points)} | {len(values) - 1})
        sampled = [values[i] for i in index]
    return [dict(date=d, value=v) for d, v in sampled]


def indicator(spec):
    table, code, name, unit, sample = spec
    result = dict(code=f'{table}/{code}', name=name, unit=unit, value=sample,
                  change=None, date=None, mode='demo', history=[])
    key = os.getenv('ECOS_API_KEY')
    if not key:
        return result
    try:
        end = now().date()
        start = end - timedelta(days=190)  # 최근 약 6개월
        url = (f'https://ecos.bok.or.kr/api/StatisticSearch/{quote(key, safe="")}/json/kr/1/700/'
               f'{table}/D/{start:%Y%m%d}/{end:%Y%m%d}/{code}')
        rows = get_json(url)['StatisticSearch']['row']
        rows = sorted(rows, key=lambda x: x['TIME'])
        values = [(r['TIME'], float(r['DATA_VALUE'])) for r in rows if r.get('DATA_VALUE') not in (None, '')]
        if not values or not all(math.isfinite(v) for _, v in values):
            raise ValueError('No observations')
        result.update(value=values[-1][1], date=values[-1][0], mode='live',
                      change=round(values[-1][1]-values[-2][1], 4) if len(values)>1 else None,
                      history=sample_history(values))
    except Exception:
        result.update(mode='unavailable', value=None)
    return result


def next_business_day(day):
    # 주말이면 다음 영업일(월요일)로 이동. 공휴일은 안내 문구로만 처리한다.
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def tax_calendar(today=None):
    today = (today or now().date())
    horizon = today + timedelta(days=120)
    raw = []
    # 매월 반복 기한(원천세 등)을 향후 5개월까지 생성.
    for offset in range(0, 5):
        year, month = divmod(today.year * 12 + today.month - 1 + offset, 12)
        month += 1
        for day, title, note in TAX_MONTHLY:
            raw.append((datetime(year, month, day).date(), title, note))
    # 연 1회 고정 기한은 올해와 내년 모두 생성해 연말·연초 경계를 포함.
    for year in (today.year, today.year + 1):
        for month, day, title, note in TAX_ANNUAL:
            raw.append((datetime(year, month, day).date(), title, note))
    events, seen = [], set()
    for statutory, title, note in sorted(raw):
        due = next_business_day(statutory)
        if not (today <= due <= horizon):
            continue
        key = (due.isoformat(), title)
        if key in seen:
            continue
        seen.add(key)
        events.append(dict(date=due.isoformat(), statutory_date=statutory.isoformat(),
                           shifted=due != statutory, days_left=(due - today).days,
                           title=title, note=note, url=NTS_CALENDAR_URL))
    events.sort(key=lambda e: (e['date'], e['title']))
    return dict(mode='reference', source_url=NTS_CALENDAR_URL, events=events[:8],
        message='세법에 명시된 국세 신고·납부 법정기한입니다. 주말은 다음 영업일로 조정했으며, '
                '공휴일이 겹치면 기한이 하루 이상 연장될 수 있으니 확정 일정은 국세청 홈택스에서 확인하세요.')


def dashboard():
    with ThreadPoolExecutor(max_workers=3) as executor:
        indicators = list(executor.map(indicator, INDICATORS))
    data = news()
    data.update(indicators=indicators, calendar=tax_calendar())
    return data


@bp.get('/dashboard')
def dashboard_route():
    data = cache.get('dashboard', dashboard, ttl=900, wait=0)
    if data is None:
        return jsonify(dict(pending=True, indicators=[dict(code=s[0]+'/'+s[1], name=s[2], unit=s[3],
            value=s[4], change=None, date=None, mode='demo', history=[]) for s in INDICATORS],
            items=[], sources=[], calendar=tax_calendar()))
    # 브리핑 기사를 리더(본문 읽기·AI 요약)로 열 수 있도록 메모리에 등록한다.
    reader.register_external([dict(url=r['url'], title=r['title'], author=r.get('source', ''),
        published_at=r.get('pub_date', ''), content=r.get('description', '')) for r in data.get('items', [])])
    return jsonify(dict(data, pending=False))


@bp.post('/business-status')
def business_status():
    body = request.get_json(silent=True)
    raw = body.get('number', '') if isinstance(body, dict) else ''
    if not isinstance(raw, str) or not re.fullmatch(r'(?:[0-9]{10}|[0-9]{3}-[0-9]{2}-[0-9]{5})', raw):
        return jsonify(error='사업자등록번호 10자리를 입력해 주세요.'), 400
    number = raw.replace('-', '')
    key = os.getenv('NTS_API_KEY')
    if not key:
        return jsonify(mode='unconfigured', status='조회 불가', message='조회 서비스 연결 전입니다. 실제 사업자 상태는 확인되지 않았습니다.')
    try:
        response = requests.post('https://api.odcloud.kr/api/nts-businessman/v1/status',
            params={'serviceKey': key, 'returnType': 'JSON'}, json={'b_no': [number]}, timeout=(3, 7), allow_redirects=False)
        response.raise_for_status()
        payload = response.json()
        if payload.get('status_code') != 'OK':
            raise ValueError('Provider failure')
        row = payload['data'][0]
        if row.get('b_no') != number:
            raise ValueError('Mismatched response')
        return jsonify(mode='live', status=row.get('b_stt') or '등록 상태 확인 불가',
            tax_type=row.get('tax_type', ''), end_date=row.get('end_dt', ''), checked_at=now().isoformat())
    except Exception:
        return jsonify(mode='unavailable', status='조회 실패', message='조회 기관 응답을 받지 못했습니다. 잠시 후 다시 시도해 주세요.')


@bp.after_request
def private_response(response):
    if request.path.endswith('/business-status'):
        response.headers['Cache-Control'] = 'no-store'
    return response


def disclosures(corp):
    key = os.getenv('DART_API_KEY')
    if not key:
        return dict(mode='unconfigured', items=[], message='공시 서비스 연결 전입니다. Open DART에서 확인할 수 있습니다.')
    end = now().date()
    try:
        params = dict(crtfc_key=key, bgn_de=(end-timedelta(days=90)).strftime('%Y%m%d'),
                      end_de=end.strftime('%Y%m%d'), page_count=30, sort='date', sort_mth='desc')
        if corp:
            params['corp_code'] = corp
        data = get_json('https://opendart.fss.or.kr/api/list.json', params=params)
        if data.get('status') == '013':
            return dict(mode='live', items=[], message='최근 90일 공시가 없습니다.')
        if data.get('status') != '000':
            raise ValueError('Provider failure')
        items = [dict(company=r['corp_name'], title=r['report_nm'], date=r['rcept_dt'],
                      url='https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+quote(r['rcept_no'], safe='')) for r in data.get('list', [])]
        return dict(mode='live', items=items, fetched_at=now().isoformat())
    except Exception:
        return dict(mode='unavailable', items=[], message='공시를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')


@bp.get('/disclosures')
def disclosures_route():
    corp = request.args.get('corp_code', '').strip()
    if corp and not re.fullmatch(r'[0-9]{8}', corp):
        return jsonify(error='DART 고유번호 8자리를 입력해 주세요.'), 400
    data = cache.get('dart:'+corp, lambda: disclosures(corp), ttl=300, wait=0)
    return jsonify(data or dict(mode='loading', pending=True, items=[], message='공시를 불러오고 있습니다.'))
