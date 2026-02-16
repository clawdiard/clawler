"""Ars Technica source — fetches articles from arstechnica.com RSS feeds.

Supports multiple section feeds (main, tech policy, science, gaming, etc.)
with category mapping and rich metadata.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from xml.etree import ElementTree

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Section feeds — curated for quality and breadth
ARS_FEEDS: Dict[str, str] = {
    "main": "https://feeds.arstechnica.com/arstechnica/index",
    "tech-policy": "https://feeds.arstechnica.com/arstechnica/tech-policy",
    "science": "https://feeds.arstechnica.com/arstechnica/science",
    "gaming": "https://feeds.arstechnica.com/arstechnica/gaming",
    "gadgets": "https://feeds.arstechnica.com/arstechnica/gadgets",
    "ai": "https://feeds.arstechnica.com/arstechnica/ai",
    "security": "https://feeds.arstechnica.com/arstechnica/security",
    "cars": "https://feeds.arstechnica.com/arstechnica/cars",
    "apple": "https://feeds.arstechnica.com/arstechnica/apple",
    "staff-blogs": "https://feeds.arstechnica.com/arstechnica/staff-blogs",
}

# Section → Clawler category mapping
SECTION_CATEGORY_MAP: Dict[str, str] = {
    "main": "tech",
    "tech-policy": "tech",
    "science": "science",
    "gaming": "gaming",
    "gadgets": "tech",
    "ai": "ai",
    "security": "security",
    "cars": "automotive",
    "apple": "tech",
    "staff-blogs": "tech",
}


class ArsTechnicaSource(BaseSource):
    """Fetch articles from Ars Technica RSS feeds."""

    name = "arstechnica"

    def __init__(
        self,
        limit: int = 25,
        feeds: Optional[List[str]] = None,
    ):
        """
        Args:
            limit: Max articles per feed.
            feeds: List of section feeds to crawl. Defaults to ['main', 'science', 'ai', 'security'].
        """
        self.limit = limit
        if feeds is not None:
            self._feeds = [f for f in feeds if f in ARS_FEEDS]
        else:
            self._feeds = ["main", "science", "ai", "security"]

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()
        articles: List[Article] = []

        for section in self._feeds:
            feed_url = ARS_FEEDS[section]
            try:
                xml_text = self.fetch_url(feed_url)
                if not xml_text:
                    continue
                parsed = self._parse_feed(xml_text, section, seen_urls)
                articles.extend(parsed)
            except Exception as e:
                logger.warning(f"[ArsTechnica] Failed to fetch {section}: {e}")

        logger.info(f"[ArsTechnica] Fetched {len(articles)} articles from {len(self._feeds)} section(s)")
        return articles

    def _parse_feed(
        self, xml_text: str, section: str, seen: Set[str]
    ) -> List[Article]:
        articles: List[Article] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"[ArsTechnica] XML parse error for {section}: {e}")
            return articles

        # Handle both RSS 2.0 and Atom namespaces
        ns = {"atom": "http://www.w3.org/2005/Atom", "dc": "http://purl.org/dc/elements/1.1/"}

        # RSS 2.0 format
        items = root.findall(".//item")
        if not items:
            # Try Atom format
            items = root.findall("atom:entry", ns)

        for item in items[: self.limit]:
            try:
                article = self._parse_item(item, section, seen, ns)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"[ArsTechnica] Skipping item in {section}: {e}")

        return articles

    def _parse_item(
        self, item, section: str, seen: Set[str], ns: dict
    ) -> Optional[Article]:
        # RSS 2.0
        title_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description")
        pubdate_el = item.find("pubDate")
        author_el = item.find("dc:creator", ns)
        if author_el is None:
            author_el = item.find("author")

        # Atom fallback
        if title_el is None:
            title_el = item.find("atom:title", ns)
        if link_el is None:
            link_atom = item.find("atom:link[@rel='alternate']", ns)
            if link_atom is not None:
                link_text = link_atom.get("href", "")
            else:
                link_text = ""
        else:
            link_text = (link_el.text or "").strip()

        title = (title_el.text or "").strip() if title_el is not None else ""
        if not isinstance(link_text, str):
            link_text = ""
        url = link_text.strip()

        if not title or not url:
            return None

        if url in seen:
            return None
        seen.add(url)

        summary = ""
        if desc_el is not None and desc_el.text:
            # Strip HTML tags from description
            import re
            summary = re.sub(r"<[^>]+>", "", desc_el.text).strip()
            if len(summary) > 300:
                summary = summary[:297] + "..."

        author = ""
        if author_el is not None and author_el.text:
            author = author_el.text.strip()

        ts = _parse_rss_date(pubdate_el.text if pubdate_el is not None else None)

        category = SECTION_CATEGORY_MAP.get(section, "tech")

        # Collect RSS category tags
        tags = []
        for cat_el in item.findall("category"):
            if cat_el.text:
                tags.append(f"ars:{cat_el.text.strip().lower()}")
        tags.append(f"ars-section:{section}")

        return Article(
            title=title,
            url=url,
            source=f"Ars Technica ({section})",
            summary=summary,
            timestamp=ts,
            category=category,
            tags=tags,
            author=author,
        )


def _parse_rss_date(raw: Optional[str]) -> Optional[datetime]:
    """Parse RFC 2822 / RFC 822 dates commonly used in RSS feeds."""
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
    # Fallback: ISO format
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None
