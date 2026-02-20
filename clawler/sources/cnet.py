"""CNET source — fetches articles from cnet.com RSS feeds.

Major tech media outlet covering consumer electronics, software, services,
and how technology intersects with daily life. Known for reviews,
buying guides, and consumer-focused tech news.
"""
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Set
from xml.etree import ElementTree

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

FEEDS = {
    "news": "https://www.cnet.com/rss/news/",
    "reviews": "https://www.cnet.com/rss/reviews/",
    "how-to": "https://www.cnet.com/rss/how-to/",
    "deals": "https://www.cnet.com/rss/deals/",
}

_CATEGORY_KEYWORDS = {
    "tech": ["\\bai\\b", "software", "app", "google", "apple", "microsoft", "samsung",
             "android", "iphone", "laptop", "chip", "processor"],
    "science": ["science", "space", "nasa", "climate", "health", "medical"],
    "security": ["security", "hack", "breach", "privacy", "malware", "vpn",
                 "password", "phishing", "ransomware"],
    "business": ["price", "deal", "sale", "buy", "cost", "subscription",
                 "market", "stock", "company"],
    "culture": ["streaming", "netflix", "disney", "movie", "show", "game",
                "gaming", "playstation", "xbox", "nintendo"],
}


class CNETSource(BaseSource):
    """Fetch articles from CNET's RSS feeds."""

    name = "cnet"

    def __init__(self, sections: Optional[List[str]] = None, limit: int = 30):
        self.sections = sections or ["news", "reviews"]
        self.limit = limit

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        seen: Set[str] = set()

        for section in self.sections:
            feed_url = FEEDS.get(section)
            if not feed_url:
                continue
            try:
                xml_text = self.fetch_url(feed_url)
                if xml_text:
                    section_articles = self._parse_feed(xml_text, section, seen)
                    articles.extend(section_articles)
            except Exception as e:
                logger.warning(f"[CNET] Failed to fetch {section}: {e}")

        articles.sort(key=lambda a: a.timestamp or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        logger.info(f"[CNET] Fetched {len(articles)} articles across {len(self.sections)} sections")
        return articles[:self.limit]

    def _parse_feed(self, xml_text: str, section: str, seen: Set[str]) -> List[Article]:
        articles: List[Article] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"[CNET] XML parse error for {section}: {e}")
            return articles

        channel = root.find("channel")
        if channel is None:
            return articles

        for item in channel.findall("item"):
            try:
                article = self._parse_item(item, section, seen)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"[CNET] Skipping item in {section}: {e}")

        return articles

    def _parse_item(self, item, section: str, seen: Set[str]) -> Optional[Article]:
        title_el = item.find("title")
        link_el = item.find("link")

        title = (title_el.text or "").strip() if title_el is not None else ""
        url = (link_el.text or "").strip() if link_el is not None else ""

        if not title or not url:
            return None
        if url in seen:
            return None
        seen.add(url)

        # Summary
        summary = ""
        desc_el = item.find("description")
        if desc_el is not None and desc_el.text:
            summary = re.sub(r"<[^>]+>", "", desc_el.text).strip()
        if len(summary) > 300:
            summary = summary[:297] + "..."

        # Author
        author = ""
        for ns_prefix in ["{http://purl.org/dc/elements/1.1/}", ""]:
            author_el = item.find(f"{ns_prefix}creator")
            if author_el is not None and author_el.text:
                author = author_el.text.strip()
                break
        if not author:
            author_el = item.find("author")
            if author_el is not None and author_el.text:
                author = author_el.text.strip()

        # Timestamp
        ts = None
        pub_el = item.find("pubDate")
        if pub_el is not None and pub_el.text:
            ts = _parse_date(pub_el.text)

        # Tags
        tags = [f"cnet:{section}"]
        for cat_el in item.findall("category"):
            if cat_el.text:
                tags.append(f"cnet:{cat_el.text.strip().lower()}")

        category = _detect_category(title, summary, section)

        return Article(
            title=title,
            url=url,
            source=f"CNET ({section.title()})",
            summary=summary,
            timestamp=ts,
            category=category,
            tags=tags,
            author=author,
        )


def _detect_category(title: str, summary: str, section: str) -> str:
    section_map = {"reviews": "tech", "how-to": "tech", "deals": "business"}
    default = section_map.get(section, "tech")

    text = (title + " " + summary).lower()
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.startswith("\\b"):
                if re.search(kw, text):
                    return cat
            elif kw in text:
                return cat
    return default


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
