"""탭: 재단YT(유튜브) 수집.

대상
- 재단: NC문화재단 유튜브 채널(@nccf) — 채널 업로드 전체(Data API) 또는 RSS 최신.
- 주요 재단: 업계동향과 동일한 주요 재단/공익법인명으로 유튜브 검색(Data API).
  (채널ID를 몰라도 되도록 검색 방식. YOUTUBE_API_KEY 필요 — 없으면 주요 재단은 건너뜀)
"""
import os
import json
import hashlib
import re
import time

from bs4 import BeautifulSoup

from . import extractor, fetcher, db
from .collection_result import CollectionItems, CollectionFailure, failure_reason, summarize_failures

YT_DATA_API = "https://www.googleapis.com/youtube/v3/playlistItems"
YT_SEARCH_API = "https://www.googleapis.com/youtube/v3/search"
SEARCH_CACHE_SECONDS = 6 * 3600

# 재단(NC문화재단) 채널
SOURCES = [
    {
        "channel": "유튜브", "account": "NC문화재단",
        "type": "youtube",
        "url": "https://www.youtube.com/@nccf",
    },
]

# 주요 재단(업계동향 B 목록과 동일) — 유튜브 검색어로 사용
MAJOR_FOUNDATIONS = [
    "아산나눔재단", "삼성문화재단", "CJ문화재단", "롯데문화재단", "현대차 정몽구 재단",
    "포스코청암재단", "두산연강재단", "LG연암문화재단", "카카오임팩트", "네이버문화재단",
]

YT_FEED = "https://www.youtube.com/feeds/videos.xml"


def _youtube_channel_id(url):
    """유튜브 채널 URL에서 channel_id(UC...)를 알아낸다."""
    if not url:
        return None
    m = re.search(r"/channel/(UC[\w-]+)", url) or re.search(r"channel_id=(UC[\w-]+)", url)
    if m:
        return m.group(1)
    try:
        resp = fetcher.get(url)
    except Exception as e:  # noqa: BLE001
        print(f"[social] 유튜브 채널 조회 실패: {url} ({e})", flush=True)
        return None
    html = resp.text
    for pat in (
        r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]+)"',
        r'"channelId":"(UC[\w-]+)"',
        r'"externalId":"(UC[\w-]+)"',
        r"youtube\.com/channel/(UC[\w-]+)",
        r"channel_id=(UC[\w-]+)",
    ):
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return None


def _crawl_youtube_api(cfg, cid, max_items):
    """YouTube Data API v3로 채널의 '업로드 재생목록'을 페이지네이션해 전 영상을 수집한다.
    (RSS는 최신 ~15개만 주므로 과거 영상까지 받으려면 이 방식이 필요) 키 없으면 호출 안 함."""
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        return None  # 키 없음 → 호출측이 RSS로 폴백
    uploads = "UU" + cid[2:]  # 업로드 재생목록 id = 채널id의 UC→UU
    label = f"{cfg['channel']}·{cfg['account']}"
    cap = max(max_items, 1000)
    items, token = [], None
    for _ in range(40):  # 최대 40페이지(50개씩=2000개) 안전장치
        params = {"part": "snippet", "maxResults": 50, "playlistId": uploads, "key": key}
        if token:
            params["pageToken"] = token
        try:
            j = fetcher.get(YT_DATA_API, params=params, retries=1, timeout=12).json()
            _raise_youtube_error(j)
            if not isinstance(j.get("items"), list):
                raise CollectionFailure("유튜브 재생목록 응답 형식이 바뀌었어요")
        except Exception as e:  # noqa: BLE001
            print(f"[social] 유튜브 Data API 실패({label}): {type(e).__name__}", flush=True)
            return None if not items else CollectionItems(items, complete=False, warnings=[failure_reason(e)])
        for it in j.get("items", []):
            sn = it.get("snippet", {})
            vid = (sn.get("resourceId") or {}).get("videoId")
            title = extractor.clean_text(sn.get("title") or "")
            if not vid or title in ("Private video", "Deleted video", ""):
                continue
            pub = (sn.get("publishedAt") or "")[:16].replace("T", " ")
            th = sn.get("thumbnails") or {}
            img = ((th.get("high") or th.get("medium") or th.get("default") or {}).get("url")
                   or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg")
            items.append({
                "channel": cfg["channel"], "account": cfg["account"],
                "title": title, "published_at": pub,
                "content": extractor.summarize(sn.get("description") or ""),
                "url": "https://www.youtube.com/watch?v=" + vid, "image_url": img,
            })
        token = j.get("nextPageToken")
        if not token or len(items) >= cap:
            break
    print(f"[social] 유튜브 Data API {label}: {len(items)}개", flush=True)
    return CollectionItems(items)


def _crawl_youtube(cfg, max_items=15):
    cid = _youtube_channel_id(cfg["url"])
    if not cid:
        print(f"[social] {cfg['channel']}·{cfg['account']}: channel_id 못 찾음 ({cfg['url']})", flush=True)
        raise CollectionFailure("유튜브 채널 주소에서 채널 ID를 찾지 못했어요")
    print(f"[social] 유튜브 channel_id={cid}", flush=True)
    api_items = _crawl_youtube_api(cfg, cid, max_items)  # 키 있으면 전 영상, 없으면 None
    if api_items is not None:
        return api_items
    try:
        resp = fetcher.get(YT_FEED, params={"channel_id": cid})
    except Exception as e:  # noqa: BLE001
        print(f"[social] 유튜브 RSS 실패: {type(e).__name__}", flush=True)
        raise

    soup = BeautifulSoup(resp.content, "xml")
    if soup.find("feed") is None:
        raise CollectionFailure("유튜브 RSS 응답 형식이 바뀌었어요")
    entries = soup.find_all("entry")
    print(f"[social] 유튜브 RSS 영상 {len(entries)}개", flush=True)
    items = []
    for entry in entries[:max_items]:
        title_el = entry.find("title")
        vid_el = entry.find("videoId")
        link_el = entry.find("link")
        pub_el = entry.find("published")
        desc_el = entry.find("description")  # media:description

        image = None
        if vid_el and vid_el.text:
            vid = vid_el.text.strip()
            link = "https://www.youtube.com/watch?v=" + vid
            image = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"  # 영상 썸네일
        else:
            link = link_el.get("href") if link_el else None
        # RSS media:thumbnail 이 있으면 우선 사용
        thumb_el = entry.find("thumbnail")
        if thumb_el and thumb_el.get("url"):
            image = thumb_el.get("url")

        # 날짜 제한은 두지 않는다(영상 수가 많지 않아 전체 수집).
        published = pub_el.text[:16].replace("T", " ") if (pub_el and pub_el.text) else None

        items.append({
            "channel": cfg["channel"],
            "account": cfg["account"],
            "title": extractor.clean_text(title_el.text) if title_el else None,
            "published_at": published,
            "content": extractor.summarize(desc_el.text if desc_el else ""),
            "url": link,
            "image_url": image,
        })
    return CollectionItems(items, complete=False, warnings=["RSS는 최근 영상만 제공하므로 기존 영상 목록을 보존했어요"])


SEARCH_BACKOFF_KEY = "youtube_search_backoff_v385"


def _search_backoff(reason, delay):
    try:
        db.set_meta(SEARCH_BACKOFF_KEY, json.dumps({"until": time.time() + delay, "reason": reason}))
    except Exception:
        pass
    return CollectionFailure(reason, stop_search=True)



def _raise_youtube_error(data, *, search=False):
    error = data.get("error") if isinstance(data, dict) else None
    if not error:
        return
    reasons = {e.get("reason") for e in error.get("errors", []) if isinstance(e, dict)}
    code = error.get("code")
    if reasons & {"quotaExceeded", "dailyLimitExceeded", "dailyLimitExceededUnreg"}:
        reason = "유튜브 API 일일 할당량 소진 · 자동 재시도 대기"
        if search:
            raise _search_backoff(reason, 86400)
        raise CollectionFailure(reason, stop_search=True)
    if code == 429 or reasons & {"rateLimitExceeded", "userRateLimitExceeded"}:
        reason = "유튜브 요청 제한(HTTP 429) · 자동 재시도 대기"
        if search:
            raise _search_backoff(reason, 3600)
        raise CollectionFailure(reason, stop_search=True)
    if reasons & {"keyInvalid", "accessNotConfigured", "forbidden", "ipRefererBlocked"} or code in (401, 403):
        raise CollectionFailure("유튜브 API 키·권한 설정 확인이 필요해요", stop_search=True)
    raise CollectionFailure(f"유튜브 API 응답 오류 (HTTP {code or 'unknown'})")


def _crawl_youtube_search(query, account, max_items=8):
    """YouTube Data API v3 search로 주요 재단명 관련 최신 영상을 수집한다.
    채널ID를 몰라도 되도록 검색 방식 사용. 키 설정·권한·할당량 오류는 명확히 보고한다."""
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        raise CollectionFailure("유튜브 검색 연결 설정이 없어요", stop_search=True)
    cache_key = "youtube_search_v384_" + hashlib.sha256(f"{query}|{account}|{max_items}".encode()).hexdigest()[:20]
    try:
        cached = json.loads(db.get_meta(cache_key, "{}") or "{}")
        age = time.time() - cached.get("at", 0)
        if 0 <= age < SEARCH_CACHE_SECONDS and isinstance(cached.get("items"), list):
            return cached["items"]
    except Exception:
        pass
    try:
        blocked = json.loads(db.get_meta(SEARCH_BACKOFF_KEY, "{}") or "{}")
        if blocked.get("until", 0) > time.time():
            raise CollectionFailure(blocked.get("reason") or "유튜브 요청 제한 · 자동 재시도 대기", stop_search=True)
    except CollectionFailure:
        raise
    except Exception:
        pass
    params = {
        "part": "snippet", "q": query, "type": "video", "order": "date",
        "maxResults": max_items, "regionCode": "KR", "relevanceLanguage": "ko", "key": key,
    }
    try:
        j = fetcher.get(YT_SEARCH_API, params=params, retries=0, timeout=12).json()
    except Exception as e:  # noqa: BLE001
        response = getattr(e, "response", None)
        if response is not None:
            try:
                _raise_youtube_error(response.json(), search=True)
            except ValueError:
                pass
        if response is not None and response.status_code == 429:
            try:
                delay = max(60, min(86400, int(response.headers.get("Retry-After", 3600))))
            except (AttributeError, TypeError, ValueError):
                delay = 3600
            raise _search_backoff("유튜브 요청 제한(HTTP 429) · 자동 재시도 대기", delay) from None
        raise CollectionFailure(failure_reason(e)) from None
    _raise_youtube_error(j, search=True)
    if not isinstance(j.get("items"), list):
        raise CollectionFailure("유튜브 검색 응답 형식이 바뀌었어요")
    items = []
    for it in j.get("items", []):
        vid = (it.get("id") or {}).get("videoId")
        if not vid:
            continue
        sn = it.get("snippet", {})
        title = extractor.clean_text(sn.get("title") or "")
        if not title:
            continue
        pub = (sn.get("publishedAt") or "")[:16].replace("T", " ")
        th = sn.get("thumbnails") or {}
        img = ((th.get("high") or th.get("medium") or th.get("default") or {}).get("url")
               or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg")
        items.append({
            "channel": "유튜브", "account": account,
            "title": title, "published_at": pub,
            "content": extractor.summarize(sn.get("description") or ""),
            "url": "https://www.youtube.com/watch?v=" + vid, "image_url": img,
        })
    print(f"[social] 유튜브 검색 {account}: {len(items)}개", flush=True)
    try:
        db.set_meta(cache_key, json.dumps({"at": time.time(), "items": items}, ensure_ascii=False))
    except Exception:
        pass
    return items


def crawl_source(cfg, max_items=10):
    label = f"{cfg['channel']} · {cfg['account']}"
    if not cfg.get("url"):
        print(f"[social] {label}: URL 없음, 건너뜀", flush=True)
        return []
    t0 = time.time()
    items = _crawl_youtube(cfg, max_items=max_items) if cfg["type"] == "youtube" else []
    print(f"[social] {label}: 수집 {len(items)}건 / {time.time() - t0:.1f}s", flush=True)
    return items


def crawl_all(max_items=10, progress=None):
    progress = progress or (lambda m: None)
    t0 = time.time()
    results, sources = [], []
    for cfg in SOURCES:
        try:
            items = crawl_source(cfg, max_items=max_items)
            complete = getattr(items, "complete", bool(items))
            reason = " · ".join(getattr(items, "warnings", [])) or ("" if complete else "유튜브 채널 목록을 찾지 못했어요")
        except Exception as error:
            items, complete, reason = [], False, failure_reason(error)
        sources.append({"name": cfg['account'], "status": "success" if complete else "failed",
                        "count": len(items), "reason": reason})
        results.extend(items)
        progress(f"{cfg['account']}: {len(items)}건" + (f" · {reason}" if reason else ""))
    # 동일한 키로 한도를 소진했으면 이후 검색은 같은 오류이므로 추가 호출하지 않는다.
    stopped = None
    if os.environ.get("YOUTUBE_API_KEY", "").strip():
        for i, name in enumerate(MAJOR_FOUNDATIONS, 1):
            status, reason = "success", ""
            try:
                if stopped:
                    items, status, reason = [], "deferred", stopped
                else:
                    items = _crawl_youtube_search(name, name, max_items=8)
            except Exception as error:
                items, status, reason = [], "failed", failure_reason(error)
                if getattr(error, "stop_search", False):
                    stopped = reason
            sources.append({"name": name, "status": status, "count": len(items), "reason": reason})
            results.extend(items)
            progress(f"주요 재단 {i}/{len(MAJOR_FOUNDATIONS)} · {name}: {len(items)}건" + (f" · {reason}" if reason else ""))
    else:
        sources.append({"name": "주요 재단 영상 검색", "status": "deferred", "count": 0,
                        "reason": "유튜브 검색 연결 설정이 없어요"})
        progress("주요 재단: 유튜브 검색 연결 설정 필요")
    print(f"[social] 전체 완료: 총 {len(results)}건 / {time.time() - t0:.1f}s", flush=True)
    warnings = summarize_failures(sources)
    return CollectionItems(results, complete=not warnings, warnings=warnings, sources=sources)
