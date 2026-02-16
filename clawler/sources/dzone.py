"""DZone source — developer articles and tutorials from dzone.com (no key needed)."""
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# DZone topic RSS feeds — curated selection of high-signal developer topics
DZONE_FEEDS = [
    {"url": "https://feeds.dzone.com/home", "topic": "general"},
    {"url": "https://feeds.dzone.com/ai", "topic": "ai"},
    {"url": "https://feeds.dzone.com/cloud", "topic": "cloud"},
    {"url": "https://feeds.dzone.com/devops", "topic": "devops"},
    {"url": "https://feeds.dzone.com/microservices", "topic": "microservices"},
    {"url": "https://feeds.dzone.com/security", "topic": "security"},
    {"url": "https://feeds.dzone.com/webdev", "topic": "webdev"},
    {"url": "https://feeds.dzone.com/java", "topic": "java"},
    {"url": "https://feeds.dzone.com/python", "topic": "python"},
    {"url": "https://feeds.dzone.com/database", "topic": "database"},
    {"url": "https://feeds.dzone.com/iot", "topic": "iot"},
    {"url": "https://feeds.dzone.com/performance", "topic": "performance"},
]

# Simple tag extraction from XML without requiring feedparser
_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.DOTALL)
_TAG_RE = {
    "title": re.compile(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", re.DOTALL),
    "link": re.compile(r"<link>(.*?)</link>"),
    "description": re.compile(
        r"<description><!\[CDATA\[(.*?)\]\]></description>|<description>(.*?)</description>",
        re.DOTALL,
    ),
    "pubDate": re.compile(r"<pubDate>(.*?)</pubDate>"),
    "creator": re.compile(r"<dc:creator><!\[CDATA\[(.*?)\]\]></dc:creator>|<dc:creator>(.*?)</dc:creator>"),
    "category": re.compile(
        r"<category><!\[CDATA\[(.*?)\]\]></category>|<category>(.*?)</category>"
    ),
}


def _extract(pattern, text):
    m = pattern.search(text)
    if not m:
        return ""
    return next((g for g in m.groups() if g is not None), "").strip()


def _extract_all(pattern, text):
    return [next(g for g in m.groups() if g is not None).strip() for m in pattern.finditer(text)]


class DZoneSource(BaseSource):
    """Fetch developer articles from DZone topic RSS feeds."""

    name = "dzone"

    def __init__(self, feeds=None, limit: int = 15):
        self.feeds = feeds or DZONE_FEEDS
        self.limit = limit

    def _parse_feed(self, feed_url: str, topic: str) -> List[Article]:
        xml = self.fetch_url(feed_url)
        if not xml:
            return []

        articles: List[Article] = []
        items = _ITEM_RE.findall(xml)

        for item_xml in items[: self.limit]:
            try:
                title = _extract(_TAG_RE["title"], item_xml)
                url = _extract(_TAG_RE["link"], item_xml)
                if not title or not url:
                    continue

                summary = _extract(_TAG_RE["description"], item_xml)
                # Strip HTML tags from summary
                summary = re.sub(r"<[^>]+>", "", summary).strip()[:300]

                author = _extract(_TAG_RE["creator"], item_xml)
                categories = _extract_all(_TAG_RE["category"], item_xml)

                ts = None
                pub_date = _extract(_TAG_RE["pubDate"], item_xml)
                if pub_date:
                    try:
                        ts = parsedate_to_datetime(pub_date)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

                tags = [f"dzone:{topic}"]
                for cat in categories[:5]:
                    tag = cat.lower().replace(" ", "-")
                    tags.append(f"dzone:{tag}")

                # Map topic to category
                cat_map = {
                    "ai": "tech",
                    "security": "security",
                    "cloud": "tech",
                    "devops": "tech",
                    "webdev": "tech",
                    "iot": "tech",
                }
                category = cat_map.get(topic, "tech")

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=f"DZone ({topic})",
                        summary=summary,
                        timestamp=ts,
                        category=category,
                        tags=tags,
                        author=author,
                    )
                )
            except Exception as e:
                logger.debug(f"[DZone] Skipping item: {e}")
                continue

        return articles

    def crawl(self) -> List[Article]:
        all_articles: List[Article] = []
        for feed in self.feeds:
            try:
                articles = self._parse_feed(feed["url"], feed["topic"])
                all_articles.extend(articles)
            except Exception as e:
                logger.warning(f"[DZone] Failed to fetch {feed['topic']}: {e}")

        logger.info(f"[DZone] Fetched {len(all_articles)} articles from {len(self.feeds)} topic feeds")
        return all_articles
