"""TechRadar source — consumer tech, reviews, and buying guides.

TechRadar covers consumer technology, reviews, buying guides,
and tech news across computing, mobile, audio, gaming, and smart home.
"""
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Set
from xml.etree import ElementTree

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

TECHRADAR_FEEDS = [
    ("https://www.techradar.com/rss", "all"),
    ("https://www.techradar.com/rss/news/computing", "computing"),
    ("https://www.techradar.com/rss/news/phone-and-communications", "mobile"),
]

_AI_KEYWORDS = {"ai", "artificial intelligence", "machine learning", "chatgpt", "copilot",
                "gemini", "openai", "llm", "generative"}
_MOBILE_KEYWORDS = {"iphone", "android", "samsung", "pixel", "phone", "smartphone", "tablet",
                    "ipad", "wearable", "watch"}
_GAMING_KEYWORDS = {"game", "gaming", "ps5", "xbox", "nintendo", "gpu", "graphics card",
                    "steam", "rtx", "radeon"}
_SECURITY_KEYWORDS = {"security", "vpn", "antivirus", "malware", "hack", "breach",
                      "ransomware", "privacy", "password"}


class TechRadarSource(BaseSource):
    """Fetch articles from TechRadar's RSS feeds."""

    name = "techradar"

    def __init__(self, limit: int = 30, **kwargs):
        super().__init__(**kwargs)
        self.limit = limit

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        seen: Set[str] = set()

        for feed_url, feed_tag in TECHRADAR_FEEDS:
            try:
                xml_text = self.fetch_url(feed_url)
                if not xml_text:
                    continue
                parsed = self._parse_feed(xml_text, feed_tag, seen)
                articles.extend(parsed)
            except Exception as e:
                logger.warning(f"[TechRadar] Failed to fetch {feed_url}: {e}")

        articles = articles[:self.limit]
        logger.info(f"[TechRadar] Fetched {len(articles)} articles")
        return articles

    def _parse_feed(self, xml_text: str, feed_tag: str, seen: Set[str]) -> List[Article]:
        articles: List[Article] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"[TechRadar] XML parse error: {e}")
            return articles

        for item in root.findall(".//item"):
            try:
                article = self._parse_item(item, feed_tag, seen)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"[TechRadar] Skipping item: {e}")

        return articles

    def _parse_item(self, item, feed_tag: str, seen: Set[str]) -> Optional[Article]:
        title_el = item.find("title")
        link_el = item.find("link")

        title = (title_el.text or "").strip() if title_el is not None else ""
        url = (link_el.text or "").strip() if link_el is not None else ""

        if not title or not url:
            return None
        if url in seen:
            return None
        seen.add(url)

        # Description
        summary = ""
        desc_el = item.find("description")
        if desc_el is not None and desc_el.text:
            summary = re.sub(r"<[^>]+>", "", desc_el.text).strip()
        if len(summary) > 300:
            summary = summary[:297] + "..."

        # Author
        author = ""
        ns_dc = {"dc": "http://purl.org/dc/elements/1.1/"}
        creator_el = item.find("dc:creator", ns_dc)
        if creator_el is not None and creator_el.text:
            author = creator_el.text.strip()

        # Timestamp
        ts = None
        pub_el = item.find("pubDate")
        if pub_el is not None and pub_el.text:
            ts = _parse_date(pub_el.text)

        # Tags
        tags = [f"tr:{feed_tag}"]
        for cat_el in item.findall("category"):
            if cat_el.text:
                tags.append(f"tr:{cat_el.text.strip().lower()}")

        category = _detect_category(title, summary, tags)

        return Article(
            title=title,
            url=url,
            source="TechRadar",
            summary=summary,
            timestamp=ts,
            category=category,
            tags=tags,
            author=author,
        )


def _detect_category(title: str, summary: str, tags: List[str]) -> str:
    text = (title + " " + summary + " " + " ".join(tags)).lower()
    if any(kw in text for kw in _AI_KEYWORDS):
        return "ai"
    if any(kw in text for kw in _SECURITY_KEYWORDS):
        return "security"
    if any(kw in text for kw in _GAMING_KEYWORDS):
        return "gaming"
    if any(kw in text for kw in _MOBILE_KEYWORDS):
        return "mobile"
    return "tech"


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
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
