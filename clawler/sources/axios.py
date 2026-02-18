"""Axios source — smart brevity news across tech, politics, business, and more.

Axios is known for concise, high-signal reporting. Free RSS feeds,
no API key required.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

AXIOS_FEEDS = [
    {"url": "https://api.axios.com/feed/", "section": "Top Stories", "category": "world"},
    {"url": "https://api.axios.com/feed/technology/", "section": "Technology", "category": "tech"},
    {"url": "https://api.axios.com/feed/politics/", "section": "Politics", "category": "politics"},
    {"url": "https://api.axios.com/feed/business/", "section": "Business", "category": "business"},
    {"url": "https://api.axios.com/feed/science/", "section": "Science", "category": "science"},
    {"url": "https://api.axios.com/feed/health/", "section": "Health", "category": "health"},
    {"url": "https://api.axios.com/feed/energy-environment/", "section": "Energy & Environment", "category": "science"},
    {"url": "https://api.axios.com/feed/world/", "section": "World", "category": "world"},
    {"url": "https://api.axios.com/feed/media-trends/", "section": "Media", "category": "culture"},
]

_CATEGORY_KEYWORDS = {
    "security": {"cybersecurity", "hack", "breach", "surveillance", "ransomware", "zero-day"},
    "tech": {"ai", "artificial intelligence", "startup", "software", "silicon valley", "crypto", "blockchain"},
    "science": {"climate", "research", "nasa", "space", "carbon", "emissions", "genome"},
    "business": {"market", "economy", "trade", "gdp", "inflation", "ipo", "earnings"},
}


class AxiosSource(BaseSource):
    """Crawl Axios RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "axios"

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

            # Refine category based on keywords
            text_lower = f"{title} {summary}".lower()
            refined_category = category
            for cat, keywords in _CATEGORY_KEYWORDS.items():
                if any(kw in text_lower for kw in keywords):
                    refined_category = cat
                    break

            tags = [f"axios:{section.lower().replace(' ', '_').replace('&', 'and')}"]

            articles.append(Article(
                title=title,
                url=link,
                source=f"Axios ({section})",
                summary=summary,
                timestamp=ts,
                category=refined_category,
                author=author,
                tags=tags,
                quality_score=0.82,
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = AXIOS_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]

        all_articles = []
        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info)
                all_articles.extend(articles)
                logger.info("[Axios] %s: %d articles", feed_info["section"], len(articles))
            except Exception as exc:
                logger.warning("[Axios] Failed to parse %s: %s", feed_info["section"], exc)

        logger.info("[Axios] Total: %d articles from %d sections", len(all_articles), len(feeds))
        return all_articles
