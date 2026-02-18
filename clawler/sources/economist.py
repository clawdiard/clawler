"""The Economist source — fetches articles from The Economist RSS feeds.

The Economist provides high-quality analysis on world affairs, business,
finance, science, and technology. Free RSS feeds (headlines + summaries)
are available at economist.com.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

ECONOMIST_FEEDS = [
    {"url": "https://www.economist.com/the-world-this-week/rss.xml", "section": "The World This Week", "category": "world"},
    {"url": "https://www.economist.com/leaders/rss.xml", "section": "Leaders", "category": "world"},
    {"url": "https://www.economist.com/finance-and-economics/rss.xml", "section": "Finance & Economics", "category": "business"},
    {"url": "https://www.economist.com/science-and-technology/rss.xml", "section": "Science & Technology", "category": "science"},
    {"url": "https://www.economist.com/business/rss.xml", "section": "Business", "category": "business"},
    {"url": "https://www.economist.com/international/rss.xml", "section": "International", "category": "world"},
    {"url": "https://www.economist.com/briefing/rss.xml", "section": "Briefing", "category": "world"},
    {"url": "https://www.economist.com/united-states/rss.xml", "section": "United States", "category": "world"},
    {"url": "https://www.economist.com/asia/rss.xml", "section": "Asia", "category": "world"},
    {"url": "https://www.economist.com/europe/rss.xml", "section": "Europe", "category": "world"},
    {"url": "https://www.economist.com/culture/rss.xml", "section": "Culture", "category": "culture"},
]

_QUALITY_KEYWORDS = {
    "high": ["geopolitics", "central bank", "inflation", "ai", "climate", "trade war",
             "sanctions", "gdp", "recession", "election", "energy", "semiconductor"],
    "medium": ["policy", "regulation", "reform", "growth", "debt", "supply chain",
               "diplomacy", "democracy", "technology", "innovation", "investment"],
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


class EconomistSource(BaseSource):
    """Crawl The Economist RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "economist"

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
                source=f"The Economist ({section})",
                summary=summary,
                timestamp=ts,
                category=category,
                quality_score=0.82 + boost,
                author=author,
                tags=[f"economist:{section.lower().replace(' & ', '_').replace(' ', '_')}"],
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = ECONOMIST_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]

        all_articles = []
        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info)
                all_articles.extend(articles)
                logger.info(f"[Economist] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[Economist] Failed to parse {feed_info['section']}: {e}")

        logger.info(f"[Economist] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
