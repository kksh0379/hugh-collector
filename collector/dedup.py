"""중복 판단·기사 그룹화 로직.

무거운 TF-IDF 라이브러리 대신 NFKC 정규화, 원문 URL, 제목 유사도,
가벼운 문자 n-gram Dice 유사도를 사용한다.
"""
import hashlib
import re
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SIMILARITY_THRESHOLD = 0.55
NGRAM_SIZE = 3
_TRACKING_KEYS = {
    "oc", "ved", "usg", "gclid", "fbclid", "igshid", "ref", "referrer",
}


def normalize_text(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", str(text)).lower()
    text = re.sub(r"\s+", "", text)
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def content_hash(text):
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def canonical_source_url(value):
    if not isinstance(value, str) or not value.startswith(("http://", "https://")):
        return ""
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").lower()
        port_num = parts.port
    except ValueError:
        return ""
    if not host:
        return ""
    if host.startswith("www."):
        host = host[4:]
    port = f":{port_num}" if port_num and port_num not in (80, 443) else ""
    query = []
    for key, val in parse_qsl(parts.query, keep_blank_values=True):
        low = key.lower()
        if low.startswith("utm_") or low in _TRACKING_KEYS:
            continue
        query.append((key, val))
    path = re.sub(r"/+$", "", parts.path or "/") or "/"
    return urlunsplit((parts.scheme.lower(), host + port, path, urlencode(query), ""))


def _char_ngrams(text, size=NGRAM_SIZE, max_chars=1400):
    value = normalize_text(text)[:max_chars]
    if len(value) < size:
        return {value} if value else set()
    return {value[i:i + size] for i in range(len(value) - size + 1)}


def _content_similarity(a, b):
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ga, gb = _char_ngrams(na), _char_ngrams(nb)
    if not ga or not gb:
        return 0.0
    return (2.0 * len(ga & gb)) / (len(ga) + len(gb))


def _title_similarity(a, b):
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if min(len(na), len(nb)) >= 12:
        short, long = (na, nb) if len(na) <= len(nb) else (nb, na)
        if short in long and len(short) / len(long) >= 0.82:
            return 0.96
    return SequenceMatcher(None, na, nb, autojunk=False).ratio()


def is_duplicate_news(new_content, existing_items, threshold=SIMILARITY_THRESHOLD):
    if not new_content or not new_content.strip():
        return False
    new_hash = content_hash(new_content)
    for item in existing_items:
        if item.get("content_hash") == new_hash:
            return True
        if _content_similarity(new_content, item.get("content") or "") >= threshold:
            return True
    return False


def dedup_news_items(items, existing_contents, threshold=SIMILARITY_THRESHOLD):
    kept = []
    bases = [c or "" for c in existing_contents]
    dup = 0
    for item in items:
        content = item.get("content") or ""
        if content and any(_content_similarity(content, old) >= threshold for old in bases):
            dup += 1
            continue
        kept.append(item)
        if content:
            bases.append(content)
    return kept, dup


def normalize_title(title):
    return normalize_text(title)


def is_duplicate_title(title, existing_titles):
    norm = normalize_title(title)
    return norm in {normalize_title(t) for t in existing_titles}


def cluster_items(items, threshold=SIMILARITY_THRESHOLD, max_tfidf=600):
    """원문 URL·제목·본문 유사도로 같은 기사의 group_key를 만든다."""
    n = len(items)
    if not n:
        return []
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    def union_buckets(values):
        buckets = {}
        for i, value in enumerate(values):
            if value:
                buckets.setdefault(value, []).append(i)
        for idxs in buckets.values():
            for idx in idxs[1:]:
                union(idxs[0], idx)

    union_buckets([canonical_source_url(it.get("source_url") or "") for it in items])
    union_buckets([normalize_title(it.get("title") or "") for it in items])

    def daykey(it):
        value = (it.get("published_at") or "").strip()
        return value[:10] if len(value) >= 10 else ""

    day_blocks = {}
    for i, item in enumerate(items):
        key = daykey(item)
        if key:
            day_blocks.setdefault(key, []).append(i)

    for idxs in day_blocks.values():
        if not (2 <= len(idxs) <= max_tfidf):
            continue
        grams = {i: _char_ngrams(items[i].get("content") or "") for i in idxs}
        for pos, a in enumerate(idxs):
            for b in idxs[pos + 1:]:
                if find(a) == find(b):
                    continue
                if _title_similarity(items[a].get("title"), items[b].get("title")) >= 0.92:
                    union(a, b)
                    continue
                ga, gb = grams[a], grams[b]
                if ga and gb:
                    sim = (2.0 * len(ga & gb)) / (len(ga) + len(gb))
                    if sim >= threshold:
                        union(a, b)

    keys = []
    for i in range(n):
        root = find(i)
        keys.append(items[root].get("url") or f"grp-{root}")
    return keys
