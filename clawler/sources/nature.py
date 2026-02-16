"""Nature News source — high-impact science journalism from nature.com RSS (no key needed)."""
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Nature RSS feeds
NATURE_FEEDS = [
    {"url": "https://www.nature.com/nature.rss", "section": "nature"},
    {"url": "https://www.nature.com/nbt.rss", "section": "biotech"},
    {"url": "https://www.nature.com/natmachintell.rss", "section": "machine-intelligence"},
    {"url": "https://www.nature.com/nclimate.rss", "section": "climate"},
    {"url": "https://www.nature.com/nnano.rss", "section": "nanotech"},
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
    "creator": re.compile(r"<dc:creator><!\[CDATA\[(.*?)\]\]></dc:creator>|<dc:creator>(.*?)</dc:creator>", re.DOTALL),
}


def _extract(pattern, text):
    m = pattern.search(text)
    if not m:
        return ""
    return next((g for g in m.groups() if g is not None), "").strip()


class NatureSource(BaseSource):
    """Fetch latest research articles from Nature journals RSS feeds."""

    name = "nature"

    def __init__(self, feeds=None, limit: int = 15):
        self.feeds = feeds or NATURE_FEEDS
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

                author = _extract(_TAG_RE["creator"], item_xml)

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
                    "nature": "science",
                    "biotech": "science",
                    "machine-intelligence": "tech",
                    "climate": "science",
                    "nanotech": "science",
                }

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=f"Nature ({section})",
                        summary=summary,
                        timestamp=ts,
                        category=cat_map.get(section, "science"),
                        tags=[f"nature:{section}"],
                        author=author,
                    )
                )
            except Exception as e:
                logger.debug(f"[Nature] Skipping item: {e}")
                continue

        return articles

    def crawl(self) -> List[Article]:
        all_articles: List[Article] = []
        for feed in self.feeds:
            try:
                articles = self._parse_feed(feed["url"], feed["section"])
                all_articles.extend(articles)
            except Exception as e:
                logger.warning(f"[Nature] Failed to fetch {feed['section']}: {e}")

        logger.info(f"[Nature] Fetched {len(all_articles)} articles from {len(self.feeds)} journal feeds")
        return all_articles
