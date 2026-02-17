"""MarketWatch source — fetches articles from MarketWatch RSS feeds.

MarketWatch (Dow Jones) provides stock market, financial, and business news.
Free RSS feeds are available at marketwatch.com.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

MARKETWATCH_FEEDS = [
    {"url": "http://feeds.marketwatch.com/marketwatch/topstories/", "section": "Top Stories", "category": "business"},
    {"url": "http://feeds.marketwatch.com/marketwatch/marketpulse/", "section": "Market Pulse", "category": "business"},
    {"url": "http://feeds.marketwatch.com/marketwatch/software/", "section": "Software", "category": "tech"},
    {"url": "http://feeds.marketwatch.com/marketwatch/pf/", "section": "Personal Finance", "category": "business"},
    {"url": "http://feeds.marketwatch.com/marketwatch/realtimeheadlines/", "section": "Breaking", "category": "business"},
]

_QUALITY_KEYWORDS = {
    "high": ["earnings", "fed", "market crash", "billion", "ipo", "acquisition",
             "gdp", "inflation", "interest rate", "recession"],
    "medium": ["stock", "investor", "wall street", "s&p 500", "dow jones",
               "revenue", "profit", "growth"],
}


def _quality_boost(title: str, summary: str) -> float:
    text = f"{title} {summary}".lower()
    for kw in _QUALITY_KEYWORDS["high"]:
        if kw in text:
            return 0.15
    for kw in _QUALITY_KEYWORDS["medium"]:
        if kw in text:
            return 0.08
    return 0.0


class MarketWatchSource(BaseSource):
    """Crawl MarketWatch RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "marketwatch"

    def __init__(self, sections: Optional[List[str]] = None, limit: int = 15):
        self.sections = [s.lower() for s in sections] if sections else None
        self.limit = limit

    def _parse_feed(self, feed_info: dict) -> List[Article]:
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
                source=f"MarketWatch ({section})",
                summary=summary,
                timestamp=ts,
                category=category,
                quality_score=0.60 + boost,
                author=author,
                tags=[f"marketwatch:{section.lower()}"],
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = MARKETWATCH_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]

        all_articles = []
        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info)
                all_articles.extend(articles)
                logger.info(f"[MarketWatch] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[MarketWatch] Failed to parse {feed_info['section']}: {e}")

        logger.info(f"[MarketWatch] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
