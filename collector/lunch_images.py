"""Conservative Google discovery: accept images attached to an exact business entity.

No search thumbnails, generic OG images, captcha bypass, paid API or AI guesses.
Network work runs outside requests; both hits and misses are persisted by identity.
"""
import hashlib
import ipaddress
import json
import re
import socket
import threading
import time
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from . import db
from .background_budget import budget

_lock = threading.Lock()
_running = False
_blocked_until = 0
_last_search = 0
_TYPES = {"Restaurant", "FoodEstablishment", "CafeOrCoffeeShop", "Bakery", "FastFoodRestaurant", "BarOrPub"}
_HEADERS = {"User-Agent": "HScopeImageBot/1.0 (+https://hscope.onrender.com)", "Accept-Language": "ko-KR,ko;q=0.9"}


class SearchBlocked(RuntimeError):
    pass


def identity(row):
    value = [str(row.get("name") or ""), str(row.get("road_address") or row.get("address") or "")]
    return "lunch_image_v1:" + hashlib.sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()


def public_url(url):
    """Reject local services, embedded credentials and nonstandard ports, including redirects."""
    try:
        p = urlsplit(url)
        if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
            return False
        if p.port not in (None, 80, 443):
            return False
        addresses = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
    except (ValueError, OSError):
        return False


def download(url, limit=2 * 1024 * 1024):
    for _ in range(4):
        if not public_url(url):
            raise ValueError("Unsafe URL")
        with requests.get(url, headers=_HEADERS, timeout=(3, 6), stream=True, allow_redirects=False) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers.get("Location", ""))
                continue
            if response.status_code in (403, 429) and urlsplit(url).hostname == "www.google.com":
                raise SearchBlocked("Google refused the request")
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(32768):
                size += len(chunk)
                if size > limit:
                    raise ValueError("Image source too large")
                chunks.append(chunk)
            return b"".join(chunks), url, response.headers.get("Content-Type", "")
    raise ValueError("Too many redirects")


def normalize(value):
    return re.sub(r"[^가-힣a-z0-9]", "", str(value or "").casefold())


def address_matches(expected, actual):
    """Require region, district/city, road and the complete building number."""
    def canonical(value):
        value = str(value or "")
        for old, new in (("서울특별시", "서울"), ("경기도", "경기"), ("부산광역시", "부산"), ("인천광역시", "인천")):
            value = value.replace(old, new)
        return value
    expected, actual = canonical(expected), canonical(actual)
    road = re.search(r"([가-힣0-9·.]+(?:로|길))\s*(\d+(?:-\d+)?)", expected)
    regions = re.findall(r"[가-힣]+(?:시|구|군)", expected[:road.start()] if road else "")
    province = expected.split()[0] if expected.split() else ""
    if not road or not regions or not province:
        return normalize(expected) == normalize(actual) and len(normalize(expected)) >= 10
    actual_roads = re.findall(r"([가-힣0-9·.]+(?:로|길))\s*(\d+(?:-\d+)?)", actual)
    return (road.groups() in actual_roads and normalize(province) in normalize(actual)
            and all(normalize(region) in normalize(actual) for region in regions))


def _entities(value):
    if isinstance(value, list):
        for child in value:
            yield from _entities(child)
    elif isinstance(value, dict):
        yield value
        for child in value.values():
            if isinstance(child, (dict, list)):
                yield from _entities(child)


def extract(html, source, row):
    soup = BeautifulSoup(html, "html.parser")
    expected_address = row.get("road_address") or row.get("address") or ""
    if not row.get("name") or not expected_address:
        return None
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            entities = json.loads(script.string or script.get_text())
        except (ValueError, TypeError):
            continue
        for entity in _entities(entities):
            types = entity.get("@type", [])
            if isinstance(types, str): types = [types]
            if not isinstance(types, list) or not _TYPES.intersection(str(t).rsplit("/", 1)[-1] for t in types):
                continue
            if normalize(entity.get("name")) != normalize(row["name"]):
                continue
            address = entity.get("address", "")
            if isinstance(address, dict):
                address = " ".join(str(address.get(key) or "") for key in ("addressRegion", "addressLocality", "streetAddress"))
            if not isinstance(address, str) or not address_matches(expected_address, address):
                continue
            images = entity.get("image", [])
            if not isinstance(images, list): images = [images]
            accepted = []
            for image in images:
                if isinstance(image, dict): image = image.get("contentUrl") or image.get("url")
                if not isinstance(image, str) or not image.strip(): continue
                url = urljoin(source, image)
                if urlsplit(url).scheme not in ("http", "https") or re.search(r"logo|no[-_]?image|placeholder|default|icon", url, re.I):
                    continue
                if url not in accepted: accepted.append(url)
                if len(accepted) == 3: break
            if accepted:
                return {"image_url": accepted[0], "images": accepted, "source_url": source, "source_name": urlsplit(source).hostname,
                        "verification": "business_name_address", "status": "verified"}
    return None


def discover(row):
    query = f'"{row["name"]}" "{row.get("road_address") or row.get("address") or ""}"'
    raw, final, _ = download("https://www.google.com/search?" + urlencode({"q": query, "num": 5, "hl": "ko"}))
    html = raw.decode("utf-8", "replace")
    if (urlsplit(final).hostname != "www.google.com" or "/sorry" in final
            or re.search(r"unusual traffic|g-recaptcha|recaptcha/api|동의하기|비정상적인 트래픽", html, re.I)):
        raise SearchBlocked("Search consent/captcha required")
    soup = BeautifulSoup(html, "html.parser")
    sources = []
    for link in soup.select("a[href]"):
        url = urljoin(final, link["href"])
        if urlsplit(url).path == "/url" and urlsplit(url).hostname == "www.google.com":
            params = parse_qs(urlsplit(url).query)
            url = (params.get("q") or params.get("url") or [""])[0]
        host = urlsplit(url).hostname or ""
        if (urlsplit(url).scheme not in ("http", "https") or not host
                or host == "google.com" or host.endswith((".google.com", ".gstatic.com", ".googleusercontent.com"))):
            continue
        if url not in sources: sources.append(url)
        if len(sources) == 4: break
    for source in sources:
        try:
            raw, final, content_type = download(source)
            if "html" not in content_type: continue
            result = extract(raw.decode("utf-8", "replace"), final, row)
            if not result: continue
            # Verify a real, nontrivial raster image; do not accept an HTML error or SVG logo.
            from PIL import Image
            from io import BytesIO
            verified = []
            for candidate in result["images"]:
                try:
                    image_raw, image_url, content_type = download(candidate, 4 * 1024 * 1024)
                    if not content_type.startswith("image/"): continue
                    with Image.open(BytesIO(image_raw)) as image:
                        if image.width < 160 or image.height < 120: continue
                        image.verify()
                    verified.append(image_url)
                except (ValueError, OSError, requests.RequestException):
                    continue
            if verified:
                result.update(image_url=verified[0], images=verified)
                return result
        except (ValueError, OSError, requests.RequestException):
            continue
    return {"status": "unverified"}


def _work(rows):
    global _running, _blocked_until, _last_search
    try:
        for row in rows:
            if time.time() < _blocked_until: break
            # Never compete with collectors or full-service checks.
            with budget.hold(wait=False) as acquired:
                if not acquired: break
                if time.time() - _last_search < 15: break
                _last_search = time.time()
                try:
                    result = discover(row)
                except SearchBlocked:
                    _blocked_until = time.time() + 86400
                    db.set_meta("lunch_image_search_backoff", str(_blocked_until))
                    result = {"status": "search_blocked"}
                except Exception:
                    result = {"status": "unavailable"}
                result["checked_at"] = time.time()
                db.set_meta(identity(row), json.dumps(result, ensure_ascii=False))
    finally:
        with _lock: _running = False


def lookup(ids):
    """One short DB read; return cached results and queue at most one remote lookup."""
    global _running, _blocked_until
    placeholders = ",".join("?" for _ in ids)
    with db.get_conn() as conn:
        rows = [dict(row) for row in conn.execute(db._q(f"SELECT id,name,road_address,address FROM lunch_restaurant WHERE id IN ({placeholders})"), tuple(ids)).fetchall()]
        keys = [identity(row) for row in rows] + ["lunch_image_search_backoff"]
        cached = {row["key"]: row["value"] for row in conn.execute(db._q("SELECT key,value FROM meta WHERE key IN (" + ",".join("?" for _ in keys) + ")"), tuple(keys)).fetchall()}
    _blocked_until = max(_blocked_until, float(cached.get("lunch_image_search_backoff", "0")))
    results, pending = {}, []
    for row in rows:
        try: value = json.loads(cached.get(identity(row), "{}"))
        except (ValueError, TypeError): value = {}
        ttl = 30 * 86400 if value.get("status") == "verified" else 7 * 86400
        if time.time() - value.get("checked_at", 0) < ttl:
            results[str(row["id"])] = value
        elif time.time() < _blocked_until:
            results[str(row["id"])] = {"status": "search_blocked"}
        else:
            results[str(row["id"])] = {"status": "pending"}
            if row.get("name") and (row.get("road_address") or row.get("address")): pending.append(row)
    with _lock:
        if pending and not _running and time.time() - _last_search >= 15:
            _running = True
            threading.Thread(target=_work, args=(pending[:1],), daemon=True, name="lunch-images").start()
    return results
