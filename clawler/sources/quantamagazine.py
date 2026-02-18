"""Quanta Magazine source — exceptional science/math/CS journalism.

Quanta Magazine publishes deep-dive articles on mathematics, physics,
computer science, and biology. Uses their RSS feed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

QUANTA_RSS = "https://api.quantamagazine.org/feed/"

# Category mapping based on Quanta's sections
_CATEGORY_MAP = {
    "mathematics": "science",
    "physics": "science",
    "biology": "science",
    "computer science": "tech",
    "computer-science": "tech",
    "quantized columns": "science",
    "abstractions blog": "science",
}


class QuantaMagazineSource(BaseSource):
    """Crawl Quanta Magazine via RSS."""

    name = "Quanta Magazine"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.limit = kwargs.get("limit", 30)

    def crawl(self) -> List[Article]:
        text = self.fetch_url(QUANTA_RSS)
        if not text:
            return []

        try:
            import feedparser
        except ImportError:
            logger.warning("[QuantaMagazine] feedparser not installed")
            return []

        feed = feedparser.parse(text)
        articles: List[Article] = []

        for entry in feed.entries[: self.limit]:
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()
            if not title or not url:
                continue

            summary = entry.get("summary", "").strip()
            # Strip HTML tags from summary
            if "<" in summary:
                import re
                summary = re.sub(r"<[^>]+>", "", summary).strip()
            # Truncate long summaries
            if len(summary) > 500:
                summary = summary[:497] + "..."

            # Parse timestamp
            ts = None
            for ts_field in ("published_parsed", "updated_parsed"):
                parsed = entry.get(ts_field)
                if parsed:
                    try:
                        ts = datetime(*parsed[:6], tzinfo=timezone.utc)
                    except Exception:
                        pass
                    break

            # Detect category from tags or content
            category = "science"
            tags = []
            for tag in entry.get("tags", []):
                term = tag.get("term", "").strip().lower()
                if term:
                    tags.append(term)
                    if term in _CATEGORY_MAP:
                        category = _CATEGORY_MAP[term]

            author = entry.get("author", "").strip()

            articles.append(Article(
                title=title,
                url=url,
                source=self.name,
                summary=summary,
                timestamp=ts,
                category=category,
                tags=tags,
                author=author,
                quality_score=0.85,  # High-quality journalism
            ))

        logger.info(f"[QuantaMagazine] Fetched {len(articles)} articles")
        return articles
