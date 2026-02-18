"""Al Jazeera source — fetches articles from Al Jazeera RSS feeds.

Al Jazeera is one of the world's largest news organizations, providing
comprehensive international news coverage with strong Middle East, Africa,
and Global South reporting. Free RSS feeds, no API key required.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

ALJAZEERA_FEEDS = [
    {"url": "https://www.aljazeera.com/xml/rss/all.xml", "section": "Top Stories", "category": "world"},
    {"url": "https://www.aljazeera.com/xml/rss/all.xml", "section": "Top Stories", "category": "world"},
]

# Al Jazeera uses a single main feed; we categorize via keywords
_CATEGORY_KEYWORDS = {
    "tech": {"ai", "artificial intelligence", "tech", "software", "cyber", "robot", "algorithm"},
    "science": {"climate", "space", "nasa", "research", "study", "scientist", "environment"},
    "business": {"economy", "trade", "market", "bank", "gdp", "inflation", "stock", "finance"},
    "health": {"health", "covid", "vaccine", "hospital", "disease", "who", "pandemic"},
    "politics": {"election", "vote", "parliament", "congress", "president", "policy"},
    "security": {"military", "army", "war", "missile", "nuclear", "sanctions", "conflict"},
    "culture": {"film", "art", "music", "sport", "olympic", "football", "culture"},
}


class AlJazeeraSource(BaseSource):
    """Crawl Al Jazeera RSS feeds.

    Parameters
    ----------
    limit : int
        Max articles to return. Default 25.
    """

    name = "aljazeera"

    def __init__(self, limit: int = 25):
        self.limit = limit

    def crawl(self) -> List[Article]:
        url = "https://www.aljazeera.com/xml/rss/all.xml"
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

            # Keyword-based category detection
            text_lower = f"{title} {summary}".lower()
            category = "world"  # default for Al Jazeera
            for cat, keywords in _CATEGORY_KEYWORDS.items():
                if any(kw in text_lower for kw in keywords):
                    category = cat
                    break

            tags = ["aljazeera"]

            articles.append(Article(
                title=title,
                url=link,
                source="Al Jazeera",
                summary=summary,
                timestamp=ts,
                category=category,
                author=author,
                tags=tags,
                quality_score=0.80,
            ))

        return articles
