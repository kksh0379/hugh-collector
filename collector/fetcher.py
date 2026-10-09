"""HTTP 요청 헬퍼.

모바일 UA로 요청하고, 실패 시 가볍게 재시도한다. 일부 사이트는
정적 HTML이 아니라 JS로 렌더링되는 SPA일 수 있는데, 그 경우 requests로는
목록이 비어 보일 수 있다. 그때는 fetcher만 Playwright 기반으로 교체하면
나머지 크롤러 로직은 그대로 재사용할 수 있도록 분리해 두었다.
"""
import re
import time

import requests
import urllib3

# SSL 검증을 끄고 재시도할 때 나오는 InsecureRequestWarning을 로그에서 억제한다.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    # 구글 뉴스 등은 데이터센터 IP에 동의(consent) 페이지를 띄워 RSS 대신 HTML을 준다 →
    # 동의 쿠키로 바로 콘텐츠를 받게 한다(다른 사이트는 무시). 뉴스가 0건 수집되던 원인.
    "Cookie": "CONSENT=YES+",
}

# (연결+읽기) 타임아웃. 국내 기관 사이트는 응답이 느린 편이라 너무 짧으면
# 상태확인/수집이 ReadTimeout으로 실패한다. 무료 호스팅 gunicorn timeout(300s)
# 안에서 안전한 선에서 넉넉히 둔다.
TIMEOUT = 15
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class ResponseTooLarge(ValueError):
    pass


def _read_bounded(resp):
    """Reject oversized decoded bodies instead of constructing partial documents."""
    try:
        chunks, size = [], 0
        for chunk in resp.iter_content(chunk_size=65536):
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise ResponseTooLarge('Response exceeds 4 MiB collection limit')
            chunks.append(chunk)
        resp._content = b''.join(chunks)
        resp._content_consumed = True
        return resp
    finally:
        resp.close()

_META_CHARSET_RE = re.compile(
    rb'<meta[^>]+charset\s*=\s*["\']?\s*([A-Za-z0-9._-]+)', re.I
)
_META_CONTENT_CHARSET_RE = re.compile(
    rb'<meta[^>]+content\s*=\s*["\'][^"\']*charset\s*=\s*([A-Za-z0-9._-]+)', re.I
)


def _response_encoding(resp):
    """HTML 바이트를 실제 인코딩에 가깝게 해석한다."""
    raw = resp.content or b""
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"

    head = raw[:16384]
    meta = None
    for pattern in (_META_CHARSET_RE, _META_CONTENT_CHARSET_RE):
        match = pattern.search(head)
        if match:
            meta = match.group(1).decode("ascii", "ignore").strip()
            if meta:
                break

    header = requests.utils.get_encoding_from_headers(resp.headers)
    weak = {"iso-8859-1", "latin-1", "latin1"}
    candidates = []
    if meta:
        candidates.append(meta)
    if header and header.lower() not in weak:
        candidates.append(header)
    if raw:
        try:
            raw.decode("utf-8", "strict")
            candidates.append("utf-8")
        except UnicodeDecodeError:
            pass
    seen = set()
    for enc in candidates:
        key = (enc or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        try:
            raw.decode(enc, "strict")
            return enc
        except (LookupError, UnicodeDecodeError):
            continue
    # Known/valid UTF-8 never needs an expensive full-body detector. Legacy
    # encodings are inferred from a bounded sample after those checks fail.
    try:
        apparent = requests.models.chardet.detect(raw[:65536]).get('encoding')
    except Exception:
        apparent = None
    for enc in (apparent, 'cp949', 'euc-kr', header, 'utf-8'):
        if not enc or enc.lower() in seen: continue
        try:
            raw.decode(enc, 'strict')
            return enc
        except (LookupError, UnicodeDecodeError): pass
    return resp.encoding or 'utf-8'



def get(url, params=None, headers=None, retries=1, timeout=None, raise_status=True):
    last_err = None
    to = timeout or TIMEOUT
    merged = dict(DEFAULT_HEADERS)
    if headers:
        merged.update(headers)
    for attempt in range(retries + 1):
        # verify=True로 먼저 시도하고, 인증서 검증 실패(체인 누락 등 국내 사이트에
        # 흔함) 시에만 verify=False로 재시도한다. 정상 사이트의 검증은 유지된다.
        for verify in (True, False):
            try:
                resp = requests.get(
                    url, params=params, headers=merged, timeout=to, verify=verify, stream=True
                )
                try:
                    if raise_status: resp.raise_for_status()
                    _read_bounded(resp)
                except Exception:
                    resp.close()
                    raise
                content_type = (resp.headers.get('content-type') or '').lower()
                if not content_type.startswith(('image/', 'application/octet-stream', 'binary/octet-stream')):
                    resp.encoding = _response_encoding(resp)
                return resp
            except requests.exceptions.SSLError as e:
                last_err = e
                continue  # verify=False로 한 번 더
            except requests.RequestException as e:  # noqa: PERF203
                last_err = e
                break  # SSL 외 오류는 verify=False가 의미 없음 → 다음 재시도로
        if attempt < retries:
            time.sleep(0.8 * (attempt + 1))
    raise last_err


def get_json(url, params=None, headers=None, retries=2):
    return get(url, params=params, headers=headers, retries=retries).json()


def post(url, data=None, headers=None, retries=1, timeout=None, raise_status=True):
    """POST 요청 헬퍼. 구글 뉴스 batchexecute 같은 폼 전송에 쓴다."""
    last_err = None
    to = timeout or TIMEOUT
    merged = dict(DEFAULT_HEADERS)
    if headers:
        merged.update(headers)
    for attempt in range(retries + 1):
        try:
            resp = requests.post(url, data=data, headers=merged, timeout=to, stream=True)
            try:
                if raise_status: resp.raise_for_status()
                _read_bounded(resp)
            except Exception:
                resp.close()
                raise
            resp.encoding = _response_encoding(resp)
            return resp
        except requests.RequestException as e:  # noqa: PERF203
            last_err = e
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
    raise last_err
