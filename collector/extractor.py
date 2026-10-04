"""범용 본문/메타 추출기.

네이버 검색은 외부 언론사 기사로 직접 링크되고, 게시판 상세 페이지도 사이트마다
구조가 달라서, 사이트별 선택자 대신 "가장 본문다운 영역"을 추정해 텍스트를 뽑는
가벼운 readability 방식을 쓴다.
"""
import json
import re
from urllib.parse import urljoin, urlsplit
from datetime import datetime

# 본문이 아닌 영역(메뉴/광고/댓글 등)
_NOISE = "script, style, nav, header, footer, aside, form, button, .gnb, .lnb, " \
         ".footer, .header, .nav, .menu, .comment, .reply, .ad, .banner, .sns, .share"

_CONTENT_HINTS = [
    "article", ".view_content", ".board_view", ".board-view", ".post-content",
    ".post_content", ".content_view", ".view-content", "#content", ".content",
    "[class*=article]", "[class*=view]", "[itemprop=articleBody]", "#dic_area", "main",
]

_DATE_RE = re.compile(r"(20\d{2})[.\-/년 ]\s*(\d{1,2})[.\-/월 ]\s*(\d{1,2})")


def clean_text(s):
    """본문에 섞일 수 있는 HTML 태그/과도한 공백을 제거해 순수 텍스트로."""
    if not s:
        return s
    if "<" in s and ">" in s:
        from bs4 import BeautifulSoup

        s = BeautifulSoup(s, "lxml").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", s).strip()


def summarize(text, max_len=220):
    """본문을 카드에 보여줄 요약으로 자른다(공백 경계에서 자르고 말줄임 추가)."""
    text = clean_text(text)
    if not text or len(text) <= max_len:
        return text
    cut = text[:max_len]
    sp = cut.rfind(" ")
    if sp > max_len * 0.6:
        cut = cut[:sp]
    return cut.rstrip() + "…"


def parse_date(text):
    """문자열에서 YYYY.MM.DD 형태를 찾아 ISO 문자열로. 실패 시 None."""
    if not text:
        return None
    m = _DATE_RE.search(text)
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    try:
        return datetime(y, mo, d).isoformat(timespec="minutes")
    except ValueError:
        return None


def extract_main_text(soup):
    """페이지에서 가장 본문다운 텍스트 블록을 추출한다."""
    for junk in soup.select(_NOISE):
        junk.decompose()

    best, best_len = "", 0
    for sel in _CONTENT_HINTS:
        for c in soup.select(sel):
            txt = c.get_text("\n", strip=True)
            if len(txt) > best_len:
                best, best_len = txt, len(txt)
    if best_len >= 120:
        return best

    # 폴백1: <p> 텍스트를 모은다
    ps = [p.get_text(strip=True) for p in soup.select("p")]
    joined = "\n".join(p for p in ps if p)
    if len(joined) >= 80:
        return joined

    # 폴백2: 노이즈 제거 후 남은 블록 중 가장 텍스트가 많은 것 (사이트별 클래스를 몰라도 동작)
    for c in soup.select("article, section, td, div, li"):
        txt = c.get_text("\n", strip=True)
        if len(txt) > best_len:
            best, best_len = txt, len(txt)
    return best or joined


def _meta(soup, *names):
    for n in names:
        el = soup.select_one(f'meta[property="{n}"], meta[name="{n}"]')
        if el and el.get("content"):
            return el["content"].strip()
    return None


def extract_image(soup, url=None):
    """대표 메타 → 기사 구조화 데이터 → 본문 사진. 상대경로와 지연 로딩도 지원."""
    def normalize(value):
        if not isinstance(value, str) or not value.strip():
            return None
        value = value.strip()
        if value.startswith("//"):
            value = "https:" + value
        elif url:
            value = urljoin(url, value)
        try:
            parts = urlsplit(value)
        except ValueError:
            return None
        # HTTP 원본은 그대로 보관하고 화면의 이미지 프록시로 전달한다.
        if parts.scheme in ("http", "https") and parts.hostname:
            return value
        return None

    for name in ("og:image:secure_url", "og:image", "og:image:url",
                 "twitter:image", "twitter:image:src"):
        for node in soup.select(f'meta[property="{name}"], meta[name="{name}"]'):
            image = normalize(node.get("content"))
            if image:
                return image

    def structured_images(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for item in value:
                yield from structured_images(item)
        elif isinstance(value, dict):
            for key in ("contentUrl", "url", "thumbnailUrl"):
                if value.get(key):
                    yield from structured_images(value[key])

    def article_images(value):
        if isinstance(value, list):
            for item in value:
                yield from article_images(item)
        elif isinstance(value, dict):
            kinds = value.get("@type", [])
            kinds = [kinds] if isinstance(kinds, str) else kinds
            if any(kind in ("Article", "NewsArticle", "BlogPosting", "ReportageNewsArticle")
                   for kind in kinds or []):
                yield from structured_images(value.get("image"))
                yield from structured_images(value.get("thumbnailUrl"))
            for key in ("@graph", "mainEntity"):
                yield from article_images(value.get(key))

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            for candidate in article_images(json.loads(script.get_text())):
                image = normalize(candidate)
                if image:
                    return image
        except (ValueError, TypeError):
            continue

    selectors = ("[itemprop=articleBody]", "#article-view-content-div", "#newsct_article",
                 "#dic_area", "#articleBodyContents", ".article-body", ".article_body",
                 ".news-body", ".view_content", ".view-content", ".article-content", "article")
    for selector in selectors:
        for container in soup.select(selector):
            for node in container.select("img"):
                if node.find_parent(["nav", "header", "footer", "aside"]):
                    continue
                hint = " ".join(str(node.get(key) or "") for key in ("src", "id", "class", "alt"))
                if re.search(r"logo|icon|avatar|banner|advert|tracking|pixel|spacer", hint, re.I):
                    continue
                if any(str(node.get(key, "")).isdigit() and int(node[key]) <= 80
                       for key in ("width", "height")):
                    continue
                candidates = [node.get(key) for key in ("data-original", "data-src", "data-lazy-src")]
                srcset = node.get("data-srcset") or node.get("srcset") or ""
                candidates.extend(part.strip().split()[0] for part in reversed(srcset.split(",")) if part.strip())
                candidates.append(node.get("src"))
                for candidate in candidates:
                    image = normalize(candidate)
                    if image:
                        return image
    return None


def extract_summary(soup):
    """기사 요약(og:description/meta description)을 추출. 없으면 None."""
    d = _meta(soup, "og:description", "description", "twitter:description")
    if d:
        d = clean_text(d)
        if len(d) >= 20:
            return d
    return None


def extract_article(soup, url):
    """기사/글 1건에서 제목·작성일·작성자·본문을 추출."""
    title = _meta(soup, "og:title")
    if not title:
        h = soup.select_one("h1, h2, .title, #title_area")
        title = h.get_text(strip=True) if h else (soup.title.get_text(strip=True) if soup.title else None)

    published = _meta(soup, "article:published_time", "og:article:published_time")
    if published:
        published = published[:16].replace("T", " ")
    else:
        t = soup.select_one("time[datetime]")
        if t and t.get("datetime"):
            published = t["datetime"][:16].replace("T", " ")
        else:
            published = parse_date(soup.get_text(" ", strip=True)[:2000])

    author = _meta(soup, "og:site_name", "author")
    if not author:
        m = re.search(r"https?://(?:www\.|m\.)?([^/]+)", url or "")
        author = m.group(1) if m else None

    content = clean_text(extract_main_text(soup))
    return {"title": clean_text(title), "published_at": published, "author": author, "content": content}

