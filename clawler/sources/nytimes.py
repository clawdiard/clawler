"""New York Times source — fetches articles from NYT RSS feeds.

The New York Times provides public RSS feeds across all major sections.
No API key required for RSS access.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

NYT_FEEDS = [
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "section": "Home", "category": "world"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "section": "World", "category": "world"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/US.xml", "section": "US", "category": "world"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", "section": "Business", "category": "business"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "section": "Technology", "category": "tech"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml", "section": "Science", "category": "science"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Health.xml", "section": "Health", "category": "health"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Sports.xml", "section": "Sports", "category": "sports"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml", "section": "Arts", "category": "culture"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Opinion.xml", "section": "Opinion", "category": "opinion"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Climate.xml", "section": "Climate", "category": "science"},
]

# Quality weights by section
SECTION_WEIGHTS = {
    "Home": 0.85, "World": 0.85, "US": 0.80, "Business": 0.80,
    "Technology": 0.85, "Science": 0.85, "Health": 0.80, "Sports": 0.65,
    "Arts": 0.70, "Opinion": 0.75, "Climate": 0.80,
}


class NYTimesSource(BaseSource):
    """Crawl New York Times RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "nytimes"

    def __init__(self, sections: Optional[List[str]] = None, limit: int = 15):
        self.sections = [s.lower() for s in sections] if sections else None
        self.limit = limit

    def _parse_feed(self, feed_info: dict) -> List[Article]:
        url = feed_info["url"]
        section = feed_info["section"]
        category = feed_info["category"]
        quality = SECTION_WEIGHTS.get(section, 0.70)

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

            articles.append(Article(
                title=title,
                url=link,
                source=f"NYT ({section})",
                summary=summary,
                timestamp=ts,
                category=category,
                quality_score=quality,
                author=author,
                tags=[f"nytimes:{section.lower()}"],
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = NYT_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]

        all_articles = []
        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info)
                all_articles.extend(articles)
                logger.info(f"[NYT] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[NYT] Failed to parse {feed_info['section']}: {e}")

        logger.info(f"[NYT] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
