"""NPR source — fetches articles from NPR's free JSON API.

NPR provides a public RSS feed, but their API gives richer metadata.
We use their RSS feeds which are freely available and well-structured.
Covers: news, politics, science, technology, culture, health, business.
"""
import logging
from datetime import datetime
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource, HEADERS

logger = logging.getLogger(__name__)

# NPR section RSS feeds (all free, no key required)
NPR_FEEDS = [
    {"url": "https://feeds.npr.org/1001/rss.xml", "section": "News", "category": "world"},
    {"url": "https://feeds.npr.org/1014/rss.xml", "section": "Politics", "category": "politics"},
    {"url": "https://feeds.npr.org/1007/rss.xml", "section": "Science", "category": "science"},
    {"url": "https://feeds.npr.org/1019/rss.xml", "section": "Technology", "category": "tech"},
    {"url": "https://feeds.npr.org/1008/rss.xml", "section": "Culture", "category": "culture"},
    {"url": "https://feeds.npr.org/1128/rss.xml", "section": "Health", "category": "health"},
    {"url": "https://feeds.npr.org/1006/rss.xml", "section": "Business", "category": "business"},
    {"url": "https://feeds.npr.org/1057/rss.xml", "section": "Economy", "category": "business"},
    {"url": "https://feeds.npr.org/1032/rss.xml", "section": "Education", "category": "education"},
    {"url": "https://feeds.npr.org/1052/rss.xml", "section": "Books", "category": "culture"},
]


class NPRSource(BaseSource):
    """Crawl NPR section RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
        Options: News, Politics, Science, Technology, Culture, Health, Business, Economy, Education, Books.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "npr"

    def __init__(self, sections: Optional[List[str]] = None, limit: int = 15):
        self.sections = [s.lower() for s in sections] if sections else None
        self.limit = limit

    def _parse_feed(self, feed_info: dict) -> List[Article]:
        """Parse a single NPR RSS feed into articles."""
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
            # Clean HTML from summary
            if summary:
                import re
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                if len(summary) > 300:
                    summary = summary[:297] + "..."

            # Parse publication date
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
                source=f"NPR ({section})",
                summary=summary,
                timestamp=ts,
                category=category,
                author=author,
                tags=[f"npr:{section.lower()}"],
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = NPR_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]

        all_articles = []
        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info)
                all_articles.extend(articles)
                logger.info(f"[NPR] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[NPR] Failed to parse {feed_info['section']}: {e}")

        logger.info(f"[NPR] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
