"""ScienceDaily source — latest science research news from sciencedaily.com (no key needed)."""
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# ScienceDaily RSS feeds by section
SCIENCEDAILY_FEEDS = [
    {"url": "https://www.sciencedaily.com/rss/top.xml", "section": "top"},
    {"url": "https://www.sciencedaily.com/rss/computers_math.xml", "section": "computers"},
    {"url": "https://www.sciencedaily.com/rss/matter_energy.xml", "section": "physics"},
    {"url": "https://www.sciencedaily.com/rss/space_time.xml", "section": "space"},
    {"url": "https://www.sciencedaily.com/rss/health_medicine.xml", "section": "health"},
    {"url": "https://www.sciencedaily.com/rss/mind_brain.xml", "section": "neuroscience"},
    {"url": "https://www.sciencedaily.com/rss/earth_climate.xml", "section": "climate"},
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


class ScienceDailySource(BaseSource):
    """Fetch latest research news from ScienceDaily RSS feeds."""

    name = "sciencedaily"

    def __init__(self, feeds=None, limit: int = 15):
        self.feeds = feeds or SCIENCEDAILY_FEEDS
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
                    "top": "science",
                    "computers": "tech",
                    "physics": "science",
                    "space": "science",
                    "health": "science",
                    "neuroscience": "science",
                    "climate": "science",
                }

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=f"ScienceDaily ({section})",
                        summary=summary,
                        timestamp=ts,
                        category=cat_map.get(section, "science"),
                        tags=[f"sciencedaily:{section}"],
                    )
                )
            except Exception as e:
                logger.debug(f"[ScienceDaily] Skipping item: {e}")
                continue

        return articles

    def crawl(self) -> List[Article]:
        all_articles: List[Article] = []
        for feed in self.feeds:
            try:
                articles = self._parse_feed(feed["url"], feed["section"])
                all_articles.extend(articles)
            except Exception as e:
                logger.warning(f"[ScienceDaily] Failed to fetch {feed['section']}: {e}")

        logger.info(f"[ScienceDaily] Fetched {len(all_articles)} articles from {len(self.feeds)} section feeds")
        return all_articles
