"""Restaurant photo lookup via Kakao Daum Image Search API.

No Google scraping or arbitrary source downloads. Only source-linked search results
with matching restaurant identity are shown; ambiguous results are omitted.
"""
import hashlib
import json
import os
import re
import threading
import time
from urllib.parse import urlsplit, unquote

import requests
from . import db
from .background_budget import budget

_lock = threading.Lock()
_running = False
_last_search = 0.0
_API = "https://dapi.kakao.com/v2/search/image"
_HEADERS = {"Accept": "application/json"}
_RETRY_TTL = 24 * 3600
_SUCCESS_TTL = 30 * 86400


def identity(row):
    value = [str(row.get("name") or ""), str(row.get("road_address") or row.get("address") or "")]
    return "lunch_image_kakao_v2:" + hashlib.sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()


def normalize(value):
    return re.sub(r"[^가-힣a-z0-9]", "", str(value or "").casefold())


def _address_tokens(address):
    address = str(address or "").replace("서울특별시", "서울").replace("경기도", "경기")
    road = re.search(r"([가-힣0-9·.]+(?:로|길))\s*(\d+(?:-\d+)?)", address)
    district = re.search(r"([가-힣]+(?:구|군|시))", address)
    return road, district


def _safe_url(url):
    try:
        p = urlsplit(url)
        return bool(p.scheme in ("https", "http") and p.hostname and not p.username and not p.password and p.port in (None, 80, 443))
    except ValueError:
        return False


def discover(row):
    key = os.environ.get("KAKAO_REST_KEY", "").strip()
    if not key:
        return {"status": "unavailable"}
    name = str(row.get("name") or "").strip()
    address = str(row.get("road_address") or row.get("address") or "").strip()
    if not name or not address:
        return {"status": "unverified"}
    response = requests.get(_API, headers={**_HEADERS, "Authorization": "KakaoAK " + key},
                            params={"query": name + " " + address, "size": 30, "sort": "accuracy"},
                            timeout=(3, 7))
    if response.status_code in (401, 403, 429):
        return {"status": "unavailable"}
    response.raise_for_status()
    road, district = _address_tokens(address)
    images = []
    source = None
    for doc in response.json().get("documents", []):
        page = str(doc.get("doc_url") or "")
        image = str(doc.get("thumbnail_url") or doc.get("image_url") or "")
        if not _safe_url(page) or not _safe_url(image):
            continue
        # Image search is not a business photo API. Require a strong match in
        # the source URL; never attribute an ambiguous picture to a business.
        decoded = normalize(unquote(page))
        if len(normalize(name)) < 3 or normalize(name) not in decoded:
            continue
        if district and normalize(district.group(1)) not in decoded:
            continue
        if road and normalize(road.group(1)) not in decoded:
            continue
        if image not in images:
            images.append(image)
            if source is None:
                source = page
        if len(images) == 3:
            break
    if not images:
        return {"status": "unverified"}
    return {"status": "verified", "verification": "business_name_address",
            "image_url": images[0], "images": images, "source_url": source,
            "source_name": urlsplit(source).hostname or "Daum 이미지 검색"}


def _work(rows):
    global _running, _last_search
    try:
        for row in rows:
            with budget.hold(wait=False) as acquired:
                if not acquired:
                    break
                try:
                    result = discover(row)
                except (requests.RequestException, ValueError, TypeError):
                    result = {"status": "unavailable"}
                result["checked_at"] = time.time()
                db.set_meta(identity(row), json.dumps(result, ensure_ascii=False))
                _last_search = time.time()
    finally:
        with _lock:
            _running = False


def lookup(ids):
    global _running
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    with db.get_conn() as conn:
        rows = [dict(row) for row in conn.execute(
            db._q(f"SELECT id,name,road_address,address FROM lunch_restaurant WHERE id IN ({placeholders})"),
            tuple(ids)).fetchall()]
        keys = [identity(row) for row in rows]
        cached = {row["key"]: row["value"] for row in conn.execute(
            db._q("SELECT key,value FROM meta WHERE key IN (" + ",".join("?" for _ in keys) + ")"),
            tuple(keys)).fetchall()} if keys else {}
    results, pending = {}, []
    now = time.time()
    for row in rows:
        try:
            value = json.loads(cached.get(identity(row), "{}"))
        except (ValueError, TypeError):
            value = {}
        ttl = _SUCCESS_TTL if value.get("status") == "verified" else _RETRY_TTL
        if now - value.get("checked_at", 0) < ttl:
            results[str(row["id"])] = value
        else:
            results[str(row["id"])] = {"status": "pending"}
            if row.get("name") and (row.get("road_address") or row.get("address")):
                pending.append(row)
    with _lock:
        if pending and not _running and now - _last_search >= 1:
            _running = True
            threading.Thread(target=_work, args=(pending[:3],), daemon=True,
                             name="lunch-kakao-images").start()
    return results
