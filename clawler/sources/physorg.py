"""Phys.org source — science and technology news from phys.org RSS feeds (no key needed).

Enhanced features:
- Quality scoring (0–1) based on section prominence, title signals, keyword categories
- Expanded section feeds (medicine, math, ecology)
- Keyword-based category refinement
"""
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List

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
    {"url": "https://phys.org/rss-feed/medicine-news/", "section": "medicine"},
    {"url": "https://phys.org/rss-feed/math-news/", "section": "math"},
    {"url": "https://phys.org/rss-feed/ecology-news/", "section": "ecology"},
]

# Section prominence
SECTION_PROMINENCE: Dict[str, float] = {
    "breaking": 0.25,
    "space": 0.22,
    "physics": 0.20,
    "technology": 0.18,
    "medicine": 0.18,
    "nanotech": 0.18,
    "biology": 0.15,
    "chemistry": 0.15,
    "earth": 0.15,
    "math": 0.15,
    "ecology": 0.15,
}

# Title signals for quality
_QUALITY_TITLE_SIGNALS = [
    "discovery", "breakthrough", "first", "new", "study finds",
    "researchers", "scientists", "evidence", "novel", "record",
    "observation", "theory", "experiment",
]


def _compute_quality(section: str, title: str, summary: str) -> float:
    """Compute quality score (0–1) for a Phys.org article."""
    q = SECTION_PROMINENCE.get(section, 0.12)
    text_lower = f"{title} {summary}".lower()

    signal_hits = sum(1 for s in _QUALITY_TITLE_SIGNALS if s in text_lower)
    q += min(0.30, signal_hits * 0.07)

    if len(title) > 60:
        q += 0.08
    elif len(title) > 40:
        q += 0.04

    if len(summary) > 150:
        q += 0.05

    return min(1.0, max(0.0, round(q, 3)))

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
                    "medicine": "science",
                    "math": "science",
                    "ecology": "science",
                }

                quality = _compute_quality(section, title, summary)

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=f"Phys.org ({section})",
                        summary=summary,
                        timestamp=ts,
                        category=cat_map.get(section, "science"),
                        tags=[f"physorg:{section}"],
                        quality_score=quality,
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
