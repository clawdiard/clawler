"""Reuters source — fetches articles from Reuters RSS feeds.

Reuters is one of the world's most trusted wire services, providing
high-quality breaking news across multiple sections. Free RSS feeds
are available at reuters.com.
"""
import logging
import re
from datetime import datetime
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource, HEADERS

logger = logging.getLogger(__name__)

# Reuters RSS feeds (free, no key required)
REUTERS_FEEDS = [
    {"url": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best", "section": "Business", "category": "business"},
    {"url": "https://www.reutersagency.com/feed/?best-topics=tech&post_type=best", "section": "Technology", "category": "tech"},
    {"url": "https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best", "section": "Politics", "category": "politics"},
    {"url": "https://www.reutersagency.com/feed/?best-topics=environment&post_type=best", "section": "Environment", "category": "science"},
    {"url": "https://www.reutersagency.com/feed/?best-topics=health&post_type=best", "section": "Health", "category": "health"},
    {"url": "https://www.reutersagency.com/feed/?best-topics=sports&post_type=best", "section": "Sports", "category": "sports"},
    {"url": "https://www.reutersagency.com/feed/?best-topics=lifestyle-entertainment&post_type=best", "section": "Lifestyle", "category": "culture"},
    {"url": "https://www.reutersagency.com/feed/?taxonomy=best-regions&post_type=best", "section": "World", "category": "world"},
]


class ReutersSource(BaseSource):
    """Crawl Reuters RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
        Options: Business, Technology, Politics, Environment, Health, Sports, Lifestyle, World.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "reuters"

    def __init__(self, sections: Optional[List[str]] = None, limit: int = 15):
        self.sections = [s.lower() for s in sections] if sections else None
        self.limit = limit

    def _parse_feed(self, feed_info: dict) -> List[Article]:
        """Parse a single Reuters RSS feed into articles."""
        url = feed_info["url"]
        section = feed_info["section"]
        category = feed_info["category"]

        content = self.fetch_url(url)
        if not content:
            return []

        parsed = feedparser.parse(content)
        articles = []

        for entry in parsed.entries[: self.limit]:
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
                source=f"Reuters ({section})",
                summary=summary,
                timestamp=ts,
                category=category,
                author=author,
                tags=[f"reuters:{section.lower()}"],
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = REUTERS_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]

        all_articles = []
        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info)
                all_articles.extend(articles)
                logger.info(f"[Reuters] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[Reuters] Failed to parse {feed_info['section']}: {e}")

        logger.info(f"[Reuters] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
