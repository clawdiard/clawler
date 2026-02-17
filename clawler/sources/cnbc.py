"""CNBC source — fetches articles from CNBC RSS feeds.

CNBC provides high-quality business, financial markets, and technology news.
Free RSS feeds are available at cnbc.com.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# CNBC RSS feeds (free, no key required)
CNBC_FEEDS = [
    {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147", "section": "Top News", "category": "business"},
    {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", "section": "Finance", "category": "business"},
    {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910", "section": "Technology", "category": "tech"},
    {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069", "section": "Media", "category": "business"},
    {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258", "section": "Earnings", "category": "business"},
    {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "section": "World", "category": "world"},
]

# Keyword-based quality boosting
_QUALITY_KEYWORDS = {
    "high": ["earnings", "fed", "market", "ai", "billion", "ipo", "acquisition", "merger",
             "gdp", "inflation", "interest rate", "cryptocurrency", "startup"],
    "medium": ["stock", "investor", "wall street", "nasdaq", "s&p", "dow", "bond",
               "revenue", "profit", "growth", "economy"],
}


def _quality_boost(title: str, summary: str) -> float:
    """Return a quality boost (0.0-0.15) based on keyword presence."""
    text = f"{title} {summary}".lower()
    for kw in _QUALITY_KEYWORDS["high"]:
        if kw in text:
            return 0.15
    for kw in _QUALITY_KEYWORDS["medium"]:
        if kw in text:
            return 0.08
    return 0.0


class CNBCSource(BaseSource):
    """Crawl CNBC RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "cnbc"

    def __init__(self, sections: Optional[List[str]] = None, limit: int = 15):
        self.sections = [s.lower() for s in sections] if sections else None
        self.limit = limit

    def _parse_feed(self, feed_info: dict) -> List[Article]:
        """Parse a single CNBC RSS feed into articles."""
        url = feed_info["url"]
        section = feed_info["section"]
        category = feed_info["category"]

        content = self.fetch_url(url)
        if not content:
            return []

        parsed = feedparser.parse(content)
        articles = []

        for entry in parsed.entries[:self.limit]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            if not title or not link:
                continue

            summary = entry.get("summary", "").strip()
            if summary:
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                if len(summary) > 300:
                    summary = summary[:297] + "..."

            ts = None
            for date_field in ("published", "updated"):
                raw = entry.get(date_field)
                if raw:
                    try:
                        ts = dateparser.parse(raw)
                        break
                    except (ValueError, TypeError):
                        continue

            author = entry.get("author", "")
            boost = _quality_boost(title, summary)

            articles.append(Article(
                title=title,
                url=link,
                source=f"CNBC ({section})",
                summary=summary,
                timestamp=ts,
                category=category,
                quality_score=0.65 + boost,
                author=author,
                tags=[f"cnbc:{section.lower()}"],
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = CNBC_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]

        all_articles = []
        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info)
                all_articles.extend(articles)
                logger.info(f"[CNBC] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[CNBC] Failed to parse {feed_info['section']}: {e}")

        logger.info(f"[CNBC] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
