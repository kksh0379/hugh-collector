"""구조화된 국내 행사 소스 어댑터(공공 Open API 등).

구글 뉴스 기반 수집(events.crawl)은 '기사화된 행사'만 잡혀 누락이 많다. 이 모듈은
행사를 '목록으로 직접' 제공하는 구조화 소스에서 날짜·장소가 확정된 행사를 모은다.

원칙(gold 교훈):
  - 키/URL은 env로만 받는다. 미설정이면 해당 소스를 건너뛴다(추측·날조 없음).
  - 실패하면 빈 리스트로 degrade — 전체 수집을 막지 않는다.
  - 응답 구조는 운영에서 /api/admin/eventcheck(diagnose)로 먼저 확인한 뒤 매핑을 보정한다.

반환 항목 shape는 events.crawl과 동일:
  title, published_at, author, content, url, source_url, image_url, venue, region,
  start_date(YYYY-MM-DD), end_date(YYYY-MM-DD)
"""
import os
import datetime

import requests
from lxml import etree


def _fmt8(s):
    """YYYYMMDD → YYYY-MM-DD. 아니면 None."""
    s = str(s or "").strip()
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s.isdigit() else None


def _item(title, start, end, venue="", region="", url="", content="", image="", source="", author=""):
    return {
        "title": (title or "").strip(),
        "published_at": datetime.date.today().isoformat(),
        "author": author or source,
        "content": content or "",
        "url": url or "",
        "source_url": url or "",
        "image_url": image or "",
        "venue": venue or "",
        "region": region or "",
        "start_date": start,
        "end_date": end or start,
        "source": source or "",
    }


def _rows(data):
    """data.go.kr 공통 응답에서 items.item 리스트를 뽑는다(단건 dict도 리스트로)."""
    try:
        items = data["response"]["body"]["items"]
        if not items:
            return []
        it = items.get("item") if isinstance(items, dict) else items
        if it is None:
            return []
        return it if isinstance(it, list) else [it]
    except Exception:
        return []


# ---------------------------- 한국관광공사 TourAPI: 행사/축제 ----------------------------
def tour_festivals(progress=None):
    """TourAPI searchFestival(행사/축제). TOURAPI_KEY(디코딩된 서비스키) 필요.
    최근 2주 이후 시작 행사까지 포함(진행 중 포함). 종료 행사는 DB list_events가 걸러낸다."""
    key = os.getenv("TOURAPI_KEY")
    if not key:
        return []
    out = []
    try:
        base = os.getenv("TOURAPI_FESTIVAL_URL",
                         "https://apis.data.go.kr/B551011/KorService2/searchFestival2")
        start = (datetime.date.today() - datetime.timedelta(days=14)).strftime("%Y%m%d")
        params = {"serviceKey": key, "MobileOS": "ETC", "MobileApp": "hscope",
                  "_type": "json", "arrange": "A",
                  "eventStartDate": start, "numOfRows": 300, "pageNo": 1}
        data = requests.get(base, params=params, timeout=(3, 12)).json()
        for it in _rows(data):
            sd = _fmt8(it.get("eventstartdate"))
            if not sd or not (it.get("title") or "").strip():
                continue
            addr = (it.get("addr1") or "").strip()
            cid = it.get("contentid") or ""
            out.append(_item(
                it.get("title", ""), sd, _fmt8(it.get("eventenddate")) or sd,
                venue=addr, region=(addr.split()[0] if addr else ""),
                url=(f"https://korean.visitkorea.or.kr/detail/ms_detail.do?cotid={cid}" if cid else ""),
                image=it.get("firstimage") or "", source="관광공사"))
    except Exception:
        return out
    if progress:
        progress(f"관광공사 축제 {len(out)}건")
    return out


# ------------------------------ 문화포털/공공데이터: 문화행사 ------------------------------
CULTURE_URL = "http://www.culture.go.kr/openapi/rest/publicperformancedisplays/period"


def _culture_date(s):
    """'YYYY.MM.DD'·'YYYY-MM-DD'·'YYYYMMDD' → YYYY-MM-DD."""
    s = str(s or "").strip().replace(".", "").replace("-", "")
    return _fmt8(s)


def _culture_rows(resp):
    """culture.go.kr는 XML(perforInfo), 일부 제공처는 JSON(items.item). 둘 다 처리."""
    try:
        rows = _rows(resp.json())
        if rows:
            return rows
    except Exception:
        pass
    try:
        root = etree.fromstring(resp.content, parser=etree.XMLParser(
            resolve_entities=False, no_network=True, recover=True))
        nodes = root.xpath("//perforInfo") or root.xpath("//item") or root.xpath("//perforList/*")
        out = []
        for node in nodes:
            d = {}
            for ch in node:
                d[etree.QName(ch).localname] = (ch.text or "").strip()
            if d:
                out.append(d)
        return out
    except Exception:
        return []


def culture_events(progress=None):
    """문화포털(culture.go.kr) 공연·전시정보 API — 국내 전시·공연·행사를 날짜·장소 구조화로.
    CULTURE_API_KEY(디코딩 서비스키) 필요. URL은 CULTURE_API_URL로 교체 가능(기본: culture.go.kr).
    응답이 XML이라 XML/JSON 모두 처리한다."""
    key = os.getenv("CULTURE_API_KEY")
    if not key:
        return []
    url = os.getenv("CULTURE_API_URL", CULTURE_URL)
    out = []
    try:
        today = datetime.date.today()
        params = {"serviceKey": key,
                  "from": (today - datetime.timedelta(days=14)).strftime("%Y%m%d"),
                  "to": (today + datetime.timedelta(days=180)).strftime("%Y%m%d"),
                  "rows": 300, "cPage": 1}
        resp = requests.get(url, params=params, timeout=(3, 12))
        for it in _culture_rows(resp):
            if not isinstance(it, dict):
                continue
            title = it.get("title") or it.get("fstvlNm") or ""
            sd = _culture_date(it.get("startDate") or it.get("eventstartdate"))
            ed = _culture_date(it.get("endDate") or it.get("eventenddate"))
            place = it.get("place") or it.get("addr1") or it.get("rdnmadr") or ""
            if title and sd:
                out.append(_item(title, sd, ed or sd, venue=place,
                                 region=(it.get("area") or (place.split()[0] if place else "")),
                                 url=it.get("url") or it.get("homepageUrl") or "",
                                 image=it.get("thumbnail") or it.get("imageObject") or "",
                                 content=it.get("realmName") or "", source="문화포털"))
    except Exception:
        return out
    if progress:
        progress(f"문화행사 {len(out)}건")
    return out


def collect(progress=None):
    """설정된 구조화 소스를 모두 모아 반환(미설정/실패는 자동 제외)."""
    items = []
    for fn in (tour_festivals, culture_events):
        try:
            items.extend(fn(progress) or [])
        except Exception:
            pass
    return items


# --------------------------------- 진단(운영 전용) ---------------------------------
def _probe(url, params):
    """원응답 상태·행수·첫 항목 키·본문 일부를 돌려준다(키는 노출하지 않음)."""
    try:
        r = requests.get(url, params=params, timeout=(3, 12))
        rows = _culture_rows(r)   # JSON(items.item)·XML(perforInfo) 모두 처리
        first = rows[0] if rows and isinstance(rows[0], dict) else None
        return {"status": r.status_code, "rows": len(rows),
                "first_keys": (list(first.keys())[:40] if first else None),
                "sample": (r.text or "")[:700]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}


def diagnose():
    """각 소스 설정/응답 진단. 운영에서 /api/admin/eventcheck로 호출(키 비노출)."""
    out = {}
    key = os.getenv("TOURAPI_KEY")
    row = {"configured": bool(key), "parsed": len(tour_festivals()) if key else 0}
    if key:
        start = (datetime.date.today() - datetime.timedelta(days=14)).strftime("%Y%m%d")
        row["raw"] = _probe(os.getenv("TOURAPI_FESTIVAL_URL",
                                      "https://apis.data.go.kr/B551011/KorService2/searchFestival2"),
                            {"serviceKey": key, "MobileOS": "ETC", "MobileApp": "hscope",
                             "_type": "json", "arrange": "A",
                             "eventStartDate": start, "numOfRows": 5, "pageNo": 1})
    out["tour_festivals"] = row
    ckey = os.getenv("CULTURE_API_KEY")
    crow = {"configured": bool(ckey), "parsed": len(culture_events()) if ckey else 0}
    if ckey:
        today = datetime.date.today()
        crow["raw"] = _probe(os.getenv("CULTURE_API_URL", CULTURE_URL),
                             {"serviceKey": ckey,
                              "from": (today - datetime.timedelta(days=14)).strftime("%Y%m%d"),
                              "to": (today + datetime.timedelta(days=180)).strftime("%Y%m%d"),
                              "rows": 5, "cPage": 1})
    out["culture_events"] = crow
    return out
