"""Flipboard source — trending stories from Flipboard topic RSS feeds.

Flipboard curates stories from across the web into topic-based magazines.
Public RSS feeds are available at flipboard.com/topic/<topic>.rss with
no API key required.
"""
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource, HEADERS

logger = logging.getLogger(__name__)

# Flipboard topic feeds — curated by editors + community
FLIPBOARD_TOPICS: List[Dict[str, str]] = [
    {"slug": "technology", "label": "Technology", "category": "tech"},
    {"slug": "science", "label": "Science", "category": "science"},
    {"slug": "artificial-intelligence", "label": "AI", "category": "ai"},
    {"slug": "programming", "label": "Programming", "category": "tech"},
    {"slug": "cybersecurity", "label": "Cybersecurity", "category": "security"},
    {"slug": "startups", "label": "Startups", "category": "business"},
    {"slug": "business", "label": "Business", "category": "business"},
    {"slug": "world-news", "label": "World News", "category": "world"},
    {"slug": "politics", "label": "Politics", "category": "politics"},
    {"slug": "climate-change", "label": "Climate", "category": "science"},
    {"slug": "space", "label": "Space", "category": "science"},
    {"slug": "gaming", "label": "Gaming", "category": "gaming"},
    {"slug": "design", "label": "Design", "category": "design"},
    {"slug": "cryptocurrency", "label": "Crypto", "category": "crypto"},
]


def _quality_score(entry: dict) -> float:
    """Estimate quality from feed entry metadata.

    Flipboard curates editorially, so baseline is decent (0.45).
    Boost for entries with longer summaries (indicates richer source).
    """
    base = 0.45
    summary = entry.get("summary", "")
    clean = re.sub(r"<[^>]+>", "", summary).strip()
    if len(clean) > 200:
        base += 0.15
    elif len(clean) > 80:
        base += 0.08
    return round(min(1.0, base), 3)


class FlipboardSource(BaseSource):
    """Crawl Flipboard topic RSS feeds.

    Parameters
    ----------
    topics : list[str] | None
        Topic slugs to include. None = all defaults.
    limit : int
        Max articles per topic feed. Default 12.
    """

    name = "flipboard"

    def __init__(self, topics: Optional[List[str]] = None, limit: int = 12):
        self.topics = topics
        self.limit = limit

    def _parse_topic(self, topic: Dict[str, str]) -> List[Article]:
        """Fetch and parse a single Flipboard topic feed."""
        slug = topic["slug"]
        label = topic["label"]
        category = topic["category"]
        url = f"https://flipboard.com/topic/{slug}.rss"

        content = self.fetch_url(url)
        if not content:
            return []

        parsed = feedparser.parse(content)
        articles: List[Article] = []

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

            quality = _quality_score(entry)
            author = entry.get("author", "")

            articles.append(Article(
                title=title,
                url=link,
                source=f"Flipboard ({label})",
                summary=summary,
                timestamp=ts,
                category=category,
                author=author,
                quality_score=quality,
                tags=[f"flipboard:{slug}"],
            ))

        return articles

    def crawl(self) -> List[Article]:
        topics = FLIPBOARD_TOPICS
        if self.topics:
            topics = [t for t in topics if t["slug"] in self.topics]

        all_articles: List[Article] = []
        for topic in topics:
            try:
                articles = self._parse_topic(topic)
                all_articles.extend(articles)
                logger.info(f"[Flipboard] {topic['label']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[Flipboard] Failed {topic['label']}: {e}")

        logger.info(f"[Flipboard] Total: {len(all_articles)} articles from {len(topics)} topics")
        return all_articles
