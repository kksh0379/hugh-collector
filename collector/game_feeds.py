"""Direct official game-news RSS ingestion. No forum/user-board crawling."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
import logging

from bs4 import BeautifulSoup
from . import fetcher, extractor

LOG = logging.getLogger(__name__)
# Official Ruliweb feed, published on the site's RSS guidance page.
FEEDS = (
    ("루리웹", "https://bbs.ruliweb.com/news/rss", "게임 뉴스"),
)
_ALLOWED = {"bbs.ruliweb.com", "m.ruliweb.com", "www.ruliweb.com"}
_LIMIT_PER_FEED = 120


def _date(value):
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (ValueError, TypeError, OverflowError):
            return None


def parse_rss(payload, *, days=30, now=None, source="루리웹", category="게임 뉴스"):
    """Use only well-formed current news items and safe article destinations."""
    soup = BeautifulSoup(payload, "xml")
    try:
        if not (soup.find("rss") or soup.find("feed")):
            raise ValueError("Not an RSS or Atom feed")
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=max(1, int(days)))
        result, seen = [], set()
        for item in soup.find_all(["item", "entry"])[:_LIMIT_PER_FEED]:
            title_tag = item.find("title")
            title = title_tag.get_text(" ", strip=True) if title_tag else ""
            link_tag = item.find("link")
            link = (link_tag.get("href") or link_tag.get_text(strip=True)) if link_tag else ""
            parsed = urlsplit(link)
            if parsed.scheme != "https" or parsed.hostname not in _ALLOWED or not parsed.path.startswith("/news/"):
                continue
            # RSS may publish the same article through desktop and mobile hosts.
            stable = parsed.path.rstrip("/")
            if stable in seen or not title:
                continue
            published_tag = item.find(["pubDate", "published", "updated"])
            published = _date(published_tag.get_text(strip=True) if published_tag else None)
            if published is None or published < cutoff or published > now + timedelta(days=1):
                continue
            description = item.find("description") or item.find("summary")
            if description:
                raw_summary = description.get_text(" ", strip=True)
                summary = extractor.clean_summary_text(BeautifulSoup(raw_summary, "html.parser").get_text(" ", strip=True))
            else:
                summary = ""
            seen.add(stable)
            result.append({
                "title": title, "url": "https://m.ruliweb.com" + stable,
                "source_url": "https://m.ruliweb.com" + stable,
                "published_at": published.replace(tzinfo=None).isoformat(timespec="minutes"),
                "author": source, "content": summary[:3000], "image_url": None,
                "category": category,
            })
        return result
    finally:
        soup.decompose()


def collect(*, days=30):
    results, warnings = [], []
    for name, url, category in FEEDS:
        try:
            response = fetcher.get(
                url, timeout=12, retries=0,
                headers={"User-Agent": "Mozilla/5.0 (compatible; HscopeNewsAggregator/1.0)",
                         "Accept": "application/rss+xml, application/xml, text/xml;q=0.9"},
            )
            if getattr(response, "status_code", 200) != 200:
                raise RuntimeError("HTTP " + str(response.status_code))
            items = parse_rss(response.content, days=min(int(days), 60), source=name, category=category)
            results.extend(items)
            LOG.info("Game RSS %s: %d recent articles", name, len(items))
        except Exception as exc:
            LOG.warning("Game RSS %s unavailable: %s", name, type(exc).__name__)
            warnings.append(f"{name} RSS를 수집하지 못했어요. 구글 뉴스 검색 자료는 유지됩니다.")
    return results, warnings
