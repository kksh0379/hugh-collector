"""점심 맛집 도메인: 카카오 로컬 API 수집 어댑터 + 카테고리 정규화 + 거리계산.

- 상세 정보(메뉴·영업시간·사진·평점)는 수집/저장하지 않고 카카오맵 링크로 랜딩한다.
- 우리가 확보하는 건 최소 신뢰 데이터: 상호·카테고리·주소·좌표·전화·place_url.
- 이용자 평점/후기는 우리 앱에 직접 누적(외부 평점 아님).
- 특정 서비스 종속 방지를 위해 수집은 어댑터로 분리(현재 kakao). 키는 KAKAO_REST_KEY.
"""
import math
import os

from . import fetcher

KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"

# 카카오 category_name(예: "음식점 > 한식 > 국밥") → 서비스 내부 카테고리
CATEGORY_RULES = [
    ("한식", ["한식", "백반", "국밥", "찌개", "탕", "해장", "곰탕", "설렁탕", "감자탕", "쌈밥", "한정식", "죽"]),
    ("고기", ["고기", "구이", "삼겹", "갈비", "곱창", "막창", "정육", "바베큐", "스테이크"]),
    ("면요리", ["국수", "칼국수", "냉면", "면", "우동", "라멘", "라면", "소바", "메밀"]),
    ("분식", ["분식", "떡볶이", "김밥", "튀김", "순대"]),
    ("중식", ["중식", "중국", "짜장", "짬뽕", "마라"]),
    ("일식", ["일식", "일본", "초밥", "스시", "회", "사시미", "덮밥", "돈부리", "우나기"]),
    ("돈까스", ["돈까스", "돈가스", "카츠"]),
    ("양식", ["양식", "이탈리", "파스타", "피자", "스파게티", "브런치", "스테이크하우스"]),
    ("아시아음식", ["아시아", "베트남", "쌀국수", "태국", "인도", "커리", "포"]),
    ("생선/해산물", ["해산물", "생선", "조개", "회", "물회", "생선구이", "해물"]),
    ("샐러드/건강식", ["샐러드", "샌드위치", "건강", "포케", "비건", "채식"]),
    ("패스트푸드", ["패스트푸드", "버거", "햄버거", "치킨", "핫도그"]),
    ("카페/디저트", ["카페", "디저트", "베이커리", "제과", "빵"]),
]


def normalize_category(kakao_category_name):
    """카카오 category_name에서 내부 카테고리 1개를 뽑는다. 못 찾으면 '기타'."""
    c = (kakao_category_name or "").replace(" ", "")
    for name, kws in CATEGORY_RULES:
        if any(kw.replace(" ", "") in c for kw in kws):
            return name
    return "기타"


def sub_category(kakao_category_name):
    """세부 카테고리(원본 마지막 토큰). 예: '음식점 > 한식 > 국밥' → '국밥'."""
    parts = [p.strip() for p in (kakao_category_name or "").split(">") if p.strip()]
    return parts[-1] if parts else ""


def haversine_m(lat1, lng1, lat2, lng2):
    """두 좌표(WGS84) 사이 거리(미터)."""
    try:
        r = 6371000.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lng2 - lng1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * r * math.asin(min(1.0, math.sqrt(a)))
    except Exception:  # noqa: BLE001
        return None


def walk_minutes(dist_m):
    """예상 도보시간(분). 보행 속도 ~67m/분(4km/h) 가정. 없으면 None."""
    if dist_m is None:
        return None
    return max(1, round(dist_m / 67.0))


def _key():
    return os.environ.get("KAKAO_REST_KEY", "").strip()


def has_key():
    return bool(_key())


def _headers():
    return {"Authorization": "KakaoAK " + _key()}


def geocode(query):
    """주소/장소명 → (lat, lng). 주소검색 우선, 실패 시 키워드검색(장소명 대응). 실패 시 None."""
    if not has_key() or not query:
        return None
    # 1) 주소 검색
    try:
        r = fetcher.get(KAKAO_ADDRESS_URL, params={"query": query}, headers=_headers(),
                        retries=1, timeout=8, raise_status=False)
        docs = (r.json() or {}).get("documents") or []
        if docs:
            d = docs[0]
            return (float(d["y"]), float(d["x"]))  # y=lat, x=lng
    except Exception:  # noqa: BLE001
        pass
    # 2) 키워드(장소명) 검색 폴백
    try:
        r = fetcher.get(KAKAO_KEYWORD_URL, params={"query": query, "size": 1}, headers=_headers(),
                        retries=1, timeout=8, raise_status=False)
        docs = (r.json() or {}).get("documents") or []
        if docs:
            d = docs[0]
            return (float(d["y"]), float(d["x"]))
    except Exception:  # noqa: BLE001
        pass
    return None


# 점심 식당 수집용 검색어(카테고리 다양성 확보). 각 검색어를 좌표 반경으로 조회.
SEARCH_TERMS = ["맛집", "한식", "백반", "국밥", "김치찌개", "칼국수", "국수", "분식", "김밥",
                "중식", "짜장면", "일식", "초밥", "돈까스", "덮밥", "고기", "쌀국수",
                "파스타", "피자", "버거", "샐러드", "카페"]


def collect(lat, lng, radius_m, progress=None, max_terms=0):
    """좌표 기준 반경 내 음식점 수집(카카오 키워드검색). place_id로 중복 제거한 리스트 반환.
    각 원소: {place_id, name, category, cat_norm, sub_cat, address, road_address,
              lat, lng, phone, place_url, dist_m}. 키 없으면 빈 리스트."""
    progress = progress or (lambda m: None)
    if not has_key():
        progress("카카오 키가 없어요(KAKAO_REST_KEY 미설정) — 수동 등록만 가능")
        return []
    radius = max(1, min(int(radius_m or 500), 20000))  # 카카오 최대 20km
    terms = SEARCH_TERMS[:max_terms] if max_terms else SEARCH_TERMS
    seen, out = set(), []
    for i, term in enumerate(terms):
        page = 1
        while page <= 3:  # 페이지당 15개, 최대 45개/검색어
            try:
                r = fetcher.get(KAKAO_KEYWORD_URL, headers=_headers(), retries=1, timeout=8,
                                raise_status=False, params={
                                    "query": term, "x": lng, "y": lat, "radius": radius,
                                    "page": page, "size": 15, "sort": "distance",
                                    "category_group_code": "FD6",  # 음식점
                                })
                j = r.json() or {}
            except Exception as e:  # noqa: BLE001
                progress(f"수집 오류({term}): {e}")
                break
            docs = j.get("documents") or []
            for d in docs:
                pid = d.get("id")
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                try:
                    rlat, rlng = float(d["y"]), float(d["x"])
                except (KeyError, TypeError, ValueError):
                    continue
                dist = haversine_m(lat, lng, rlat, rlng)
                if dist is not None and dist > radius:
                    continue
                cat_name = d.get("category_name") or ""
                out.append({
                    "place_id": pid,
                    "name": d.get("place_name") or "",
                    "category": cat_name,
                    "cat_norm": normalize_category(cat_name),
                    "sub_cat": sub_category(cat_name),
                    "address": d.get("address_name") or "",
                    "road_address": d.get("road_address_name") or "",
                    "lat": rlat, "lng": rlng,
                    "phone": d.get("phone") or "",
                    "place_url": d.get("place_url") or "",
                    "dist_m": round(dist) if dist is not None else None,
                })
            if (j.get("meta") or {}).get("is_end", True):
                break
            page += 1
        if (i + 1) % 5 == 0 or i == len(terms) - 1:
            progress(f"카카오 수집 {i + 1}/{len(terms)} 검색어 · 누적 {len(out)}곳")
    progress(f"수집 완료 · {len(out)}곳")
    return out
