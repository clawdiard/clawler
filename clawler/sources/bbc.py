"""BBC News source — fetches articles from BBC RSS feeds.

BBC News is one of the world's most trusted and comprehensive news
services with free RSS feeds covering all major sections.
No API key required.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# BBC News RSS feeds (free, no key required)
BBC_FEEDS = [
    {"url": "https://feeds.bbci.co.uk/news/rss.xml", "section": "Top Stories", "category": "general"},
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml", "section": "World", "category": "world"},
    {"url": "https://feeds.bbci.co.uk/news/business/rss.xml", "section": "Business", "category": "business"},
    {"url": "https://feeds.bbci.co.uk/news/technology/rss.xml", "section": "Technology", "category": "tech"},
    {"url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "section": "Science", "category": "science"},
    {"url": "https://feeds.bbci.co.uk/news/health/rss.xml", "section": "Health", "category": "health"},
    {"url": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml", "section": "Entertainment", "category": "culture"},
    {"url": "https://feeds.bbci.co.uk/news/politics/rss.xml", "section": "Politics", "category": "politics"},
    {"url": "https://feeds.bbci.co.uk/news/education/rss.xml", "section": "Education", "category": "education"},
    {"url": "https://feeds.bbci.co.uk/sport/rss.xml", "section": "Sport", "category": "sports"},
]


class BBCNewsSource(BaseSource):
    """Crawl BBC News RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "bbc"

    def __init__(self, sections: Optional[List[str]] = None, limit: int = 15):
        self.sections = [s.lower() for s in sections] if sections else None
        self.limit = limit

    def _parse_feed(self, feed_info: dict) -> List[Article]:
        """Parse a single BBC RSS feed into articles."""
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

            summary = entry.get("summary", entry.get("description", "")).strip()
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
                source=f"BBC News ({section})",
                summary=summary,
                timestamp=ts,
                category=category,
                author=author,
                tags=[f"bbc:{section.lower()}"],
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = BBC_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]

        all_articles = []
        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info)
                all_articles.extend(articles)
                logger.info(f"[BBC] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[BBC] Failed to parse {feed_info['section']}: {e}")

        logger.info(f"[BBC] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
