"""Phys.org source — science and technology news from phys.org RSS feeds (no key needed)."""
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Phys.org RSS feeds by topic
PHYSORG_FEEDS = [
    {"url": "https://phys.org/rss-feed/breaking/", "section": "breaking"},
    {"url": "https://phys.org/rss-feed/physics-news/", "section": "physics"},
    {"url": "https://phys.org/rss-feed/nanotech-news/", "section": "nanotech"},
    {"url": "https://phys.org/rss-feed/technology-news/", "section": "technology"},
    {"url": "https://phys.org/rss-feed/space-news/", "section": "space"},
    {"url": "https://phys.org/rss-feed/earth-news/", "section": "earth"},
    {"url": "https://phys.org/rss-feed/biology-news/", "section": "biology"},
    {"url": "https://phys.org/rss-feed/chemistry-news/", "section": "chemistry"},
]

_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.DOTALL)
_TAG_RE = {
    "title": re.compile(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", re.DOTALL),
    "link": re.compile(r"<link>(.*?)</link>"),
    "description": re.compile(
        r"<description><!\[CDATA\[(.*?)\]\]></description>|<description>(.*?)</description>",
        re.DOTALL,
    ),
    "pubDate": re.compile(r"<pubDate>(.*?)</pubDate>"),
}


def _extract(pattern, text):
    m = pattern.search(text)
    if not m:
        return ""
    return next((g for g in m.groups() if g is not None), "").strip()


class PhysOrgSource(BaseSource):
    """Fetch latest science/tech news from Phys.org RSS feeds."""

    name = "physorg"

    def __init__(self, feeds=None, limit: int = 15):
        self.feeds = feeds or PHYSORG_FEEDS
        self.limit = limit

    def _parse_feed(self, feed_url: str, section: str) -> List[Article]:
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
                summary = re.sub(r"<[^>]+>", "", summary).strip()[:300]

                ts = None
                pub_date = _extract(_TAG_RE["pubDate"], item_xml)
                if pub_date:
                    try:
                        ts = parsedate_to_datetime(pub_date)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

                cat_map = {
                    "breaking": "science",
                    "physics": "science",
                    "nanotech": "tech",
                    "technology": "tech",
                    "space": "science",
                    "earth": "science",
                    "biology": "science",
                    "chemistry": "science",
                }

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=f"Phys.org ({section})",
                        summary=summary,
                        timestamp=ts,
                        category=cat_map.get(section, "science"),
                        tags=[f"physorg:{section}"],
                    )
                )
            except Exception as e:
                logger.debug(f"[PhysOrg] Skipping item: {e}")
                continue

        return articles

    def crawl(self) -> List[Article]:
        all_articles: List[Article] = []
        for feed in self.feeds:
            try:
                articles = self._parse_feed(feed["url"], feed["section"])
                all_articles.extend(articles)
            except Exception as e:
                logger.warning(f"[PhysOrg] Failed to fetch {feed['section']}: {e}")

        logger.info(f"[PhysOrg] Fetched {len(all_articles)} articles from {len(self.feeds)} section feeds")
        return all_articles
