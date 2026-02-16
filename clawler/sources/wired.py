"""Wired source — fetches articles from wired.com RSS feeds.

Covers technology, science, culture, business, and gear with
high-quality long-form journalism.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from xml.etree import ElementTree

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

WIRED_FEEDS: Dict[str, str] = {
    "main": "https://www.wired.com/feed/rss",
    "science": "https://www.wired.com/feed/category/science/latest/rss",
    "security": "https://www.wired.com/feed/category/security/latest/rss",
    "business": "https://www.wired.com/feed/category/business/latest/rss",
    "culture": "https://www.wired.com/feed/category/culture/latest/rss",
    "gear": "https://www.wired.com/feed/category/gear/latest/rss",
}

SECTION_CATEGORY_MAP: Dict[str, str] = {
    "main": "tech",
    "science": "science",
    "security": "security",
    "business": "business",
    "culture": "culture",
    "gear": "tech",
}


class WiredSource(BaseSource):
    """Fetch articles from Wired RSS feeds."""

    name = "wired"

    def __init__(self, limit: int = 20, feeds: Optional[List[str]] = None):
        self.limit = limit
        if feeds is not None:
            self._feeds = [f for f in feeds if f in WIRED_FEEDS]
        else:
            self._feeds = ["main", "science", "security"]

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()
        articles: List[Article] = []

        for section in self._feeds:
            feed_url = WIRED_FEEDS[section]
            try:
                xml_text = self.fetch_url(feed_url)
                if not xml_text:
                    continue
                parsed = self._parse_feed(xml_text, section, seen_urls)
                articles.extend(parsed)
            except Exception as e:
                logger.warning(f"[Wired] Failed to fetch {section}: {e}")

        logger.info(f"[Wired] Fetched {len(articles)} articles from {len(self._feeds)} section(s)")
        return articles

    def _parse_feed(self, xml_text: str, section: str, seen: Set[str]) -> List[Article]:
        articles: List[Article] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"[Wired] XML parse error for {section}: {e}")
            return articles

        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        items = root.findall(".//item")

        for item in items[:self.limit]:
            try:
                article = self._parse_item(item, section, seen, ns)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"[Wired] Skipping item in {section}: {e}")

        return articles

    def _parse_item(self, item, section: str, seen: Set[str], ns: dict) -> Optional[Article]:
        title_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description")
        pubdate_el = item.find("pubDate")
        author_el = item.find("dc:creator", ns)
        if author_el is None:
            author_el = item.find("author")

        title = (title_el.text or "").strip() if title_el is not None else ""
        url = (link_el.text or "").strip() if link_el is not None else ""

        if not title or not url:
            return None
        if url in seen:
            return None
        seen.add(url)

        summary = ""
        if desc_el is not None and desc_el.text:
            summary = re.sub(r"<[^>]+>", "", desc_el.text).strip()
            if len(summary) > 300:
                summary = summary[:297] + "..."

        author = ""
        if author_el is not None and author_el.text:
            author = author_el.text.strip()

        ts = _parse_rss_date(pubdate_el.text if pubdate_el is not None else None)
        category = SECTION_CATEGORY_MAP.get(section, "tech")

        tags = []
        for cat_el in item.findall("category"):
            if cat_el.text:
                tags.append(f"wired:{cat_el.text.strip().lower()}")
        tags.append(f"wired-section:{section}")

        return Article(
            title=title,
            url=url,
            source=f"Wired ({section})",
            summary=summary,
            timestamp=ts,
            category=category,
            tags=tags,
            author=author,
        )


def _parse_rss_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(raw.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None
