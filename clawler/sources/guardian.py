"""The Guardian source — fetches articles from The Guardian's free RSS feeds.

The Guardian provides comprehensive free RSS feeds across all sections.
Covers: world, UK, US, tech, science, business, environment, culture, opinion, sport.
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

GUARDIAN_FEEDS = [
    {"url": "https://www.theguardian.com/world/rss", "section": "World", "category": "world"},
    {"url": "https://www.theguardian.com/uk-news/rss", "section": "UK News", "category": "world"},
    {"url": "https://www.theguardian.com/us-news/rss", "section": "US News", "category": "world"},
    {"url": "https://www.theguardian.com/technology/rss", "section": "Technology", "category": "tech"},
    {"url": "https://www.theguardian.com/science/rss", "section": "Science", "category": "science"},
    {"url": "https://www.theguardian.com/business/rss", "section": "Business", "category": "business"},
    {"url": "https://www.theguardian.com/environment/rss", "section": "Environment", "category": "science"},
    {"url": "https://www.theguardian.com/culture/rss", "section": "Culture", "category": "culture"},
    {"url": "https://www.theguardian.com/commentisfree/rss", "section": "Opinion", "category": "opinion"},
    {"url": "https://www.theguardian.com/sport/rss", "section": "Sport", "category": "sports"},
]


class GuardianSource(BaseSource):
    """Crawl The Guardian section RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "guardian"

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
                source=f"The Guardian ({section})",
                summary=summary,
                timestamp=ts,
                category=category,
                author=author,
                tags=[f"guardian:{section.lower()}"],
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = GUARDIAN_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]

        all_articles = []
        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info)
                all_articles.extend(articles)
                logger.info(f"[Guardian] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[Guardian] Failed to parse {feed_info['section']}: {e}")

        logger.info(f"[Guardian] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
