"""Salon source — progressive news and commentary on politics, culture, and tech.

Long-form journalism and opinion. Free RSS feed, no API key required.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

SALON_FEEDS = [
    {"url": "https://www.salon.com/feed/", "section": "Latest", "category": "world"},
    {"url": "https://www.salon.com/topic/tech/feed/", "section": "Tech", "category": "tech"},
    {"url": "https://www.salon.com/topic/science/feed/", "section": "Science", "category": "science"},
    {"url": "https://www.salon.com/topic/politics/feed/", "section": "Politics", "category": "politics"},
    {"url": "https://www.salon.com/topic/culture/feed/", "section": "Culture", "category": "culture"},
]

_CATEGORY_KEYWORDS = {
    "tech": {"ai", "artificial intelligence", "startup", "software", "silicon valley", "social media", "algorithm"},
    "science": {"climate", "research", "study", "brain", "health", "pandemic", "evolution"},
    "politics": {"congress", "senate", "election", "trump", "democrat", "republican", "supreme court"},
    "business": {"economy", "market", "inflation", "corporate", "wall street"},
}


class SalonSource(BaseSource):
    """Crawl Salon RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section. Default 15.
    """

    name = "salon"

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

            quality = 0.70
            text_lower = f"{title} {summary}".lower()
            if any(kw in text_lower for kw in ("investigation", "exclusive", "analysis", "deep dive")):
                quality = 0.85

            refined_category = category
            for cat, keywords in _CATEGORY_KEYWORDS.items():
                if any(kw in text_lower for kw in keywords):
                    refined_category = cat
                    break

            tags = [f"salon:{section.lower().replace(' ', '_')}"]

            articles.append(Article(
                title=title,
                url=link,
                source=f"Salon ({section})",
                summary=summary,
                timestamp=ts,
                category=refined_category,
                author=author,
                tags=tags,
                quality_score=quality,
            ))

        return articles

    def crawl(self) -> List[Article]:
        articles = []
        for feed_info in SALON_FEEDS:
            if self.sections and feed_info["section"].lower() not in self.sections:
                continue
            try:
                articles.extend(self._parse_feed(feed_info))
            except Exception as exc:
                logger.warning("Salon %s failed: %s", feed_info["section"], exc)
        return articles
