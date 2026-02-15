"""Medium source — fetches articles via Medium's public RSS feeds (no API key needed)."""
import logging
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Default Medium feeds: mix of popular tags and notable publications
DEFAULT_TAG_FEEDS = [
    "artificial-intelligence",
    "machine-learning",
    "programming",
    "technology",
    "data-science",
    "startup",
    "product-management",
    "cybersecurity",
    "design",
    "science",
    "economics",
    "cryptocurrency",
    "javascript",
    "python",
    "devops",
    "ux",
    "business",
    "productivity",
    "software-engineering",
    "climate-change",
]

DEFAULT_PUBLICATION_FEEDS = [
    "towards-data-science",
    "better-programming",
    "the-startup",
    "hackernoon",  # legacy medium feed
    "netflix-techblog",
    "airbnb-engineering",
    "google-developers",
    "slack-eng",
    "flutter",
    "javascript-in-plain-english",
]

TAG_CATEGORY_MAP = {
    "artificial-intelligence": "tech",
    "machine-learning": "tech",
    "programming": "tech",
    "technology": "tech",
    "data-science": "tech",
    "startup": "business",
    "product-management": "business",
    "cybersecurity": "security",
    "design": "culture",
    "science": "science",
    "economics": "business",
    "cryptocurrency": "business",
    "javascript": "tech",
    "python": "tech",
    "devops": "tech",
    "ux": "culture",
    "business": "business",
    "productivity": "business",
    "software-engineering": "tech",
    "climate-change": "science",
}


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"&[a-zA-Z]+;", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse RSS date formats."""
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _extract_categories(item: ET.Element) -> List[str]:
    """Extract category tags from an RSS item."""
    tags = []
    for cat in item.findall("category"):
        text = (cat.text or "").strip()
        if text:
            tags.append(text.lower())
    return tags[:10]


class MediumSource(BaseSource):
    """Fetches articles from Medium via public RSS feeds."""

    name = "medium"

    def __init__(
        self,
        tag_feeds: Optional[List[str]] = None,
        publication_feeds: Optional[List[str]] = None,
        user_feeds: Optional[List[str]] = None,
        max_per_feed: int = 5,
    ):
        self.tag_feeds = tag_feeds if tag_feeds is not None else DEFAULT_TAG_FEEDS
        self.publication_feeds = publication_feeds if publication_feeds is not None else DEFAULT_PUBLICATION_FEEDS
        self.user_feeds = user_feeds or []
        self.max_per_feed = max_per_feed

    def _build_feed_urls(self) -> List[tuple]:
        """Build (url, label) pairs for all configured feeds."""
        urls = []
        for tag in self.tag_feeds:
            urls.append((f"https://medium.com/feed/tag/{tag}", tag))
        for pub in self.publication_feeds:
            urls.append((f"https://medium.com/feed/{pub}", pub))
        for user in self.user_feeds:
            handle = user.lstrip("@")
            urls.append((f"https://medium.com/feed/@{handle}", f"@{handle}"))
        return urls

    def _parse_feed(self, xml_text: str, label: str) -> List[Article]:
        """Parse RSS XML into Article objects."""
        if not xml_text:
            return []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.warning(f"[Medium] XML parse error for {label}: {e}")
            return []

        articles = []
        # Handle both RSS 2.0 (<channel><item>) structures
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall(".//item")

        for item in items[: self.max_per_feed]:
            title = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or "").strip()
            if not title or not url:
                continue

            # Clean tracking params from Medium URLs
            if "?" in url:
                url = url.split("?")[0]

            # Extract description/content
            description = ""
            content_encoded = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or ""
            raw_desc = item.findtext("description") or ""
            description = _strip_html(content_encoded or raw_desc)[:500]

            # Author — Medium uses dc:creator
            author = (
                item.findtext("{http://purl.org/dc/elements/1.1/}creator")
                or item.findtext("author")
                or ""
            ).strip()

            # Timestamp
            pub_date = item.findtext("pubDate") or ""
            timestamp = _parse_date(pub_date)

            # Tags
            tags = _extract_categories(item)

            # Category mapping
            category = TAG_CATEGORY_MAP.get(label, "tech")
            for tag in tags:
                if tag in TAG_CATEGORY_MAP:
                    category = TAG_CATEGORY_MAP[tag]
                    break

            summary = description[:300]
            if author:
                summary = f"by {author} — {summary}"

            articles.append(
                Article(
                    title=title,
                    url=url,
                    source="medium",
                    summary=summary[:300],
                    timestamp=timestamp,
                    category=category,
                    tags=tags[:5],
                    author=author,
                )
            )

        return articles

    def crawl(self) -> List[Article]:
        feed_urls = self._build_feed_urls()
        all_articles: List[Article] = []
        seen_urls = set()

        for url, label in feed_urls:
            xml_text = self.fetch_url(url)
            articles = self._parse_feed(xml_text, label)
            for a in articles:
                if a.url not in seen_urls:
                    seen_urls.add(a.url)
                    all_articles.append(a)

        logger.info(f"[Medium] Fetched {len(all_articles)} articles from {len(feed_urls)} feeds")
        return all_articles
