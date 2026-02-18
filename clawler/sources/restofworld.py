"""Rest of World source — global technology and internet coverage.

Rest of World is an international nonprofit journalism organization covering
technology's impact outside the Western bubble. Free RSS feeds, no API key.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

RESTOFWORLD_FEEDS = [
    {"url": "https://restofworld.org/feed/", "section": "Latest", "category": "tech"},
    {"url": "https://restofworld.org/section/big-tech/feed/", "section": "Big Tech", "category": "tech"},
    {"url": "https://restofworld.org/section/creators-and-culture/feed/", "section": "Creators & Culture", "category": "culture"},
    {"url": "https://restofworld.org/section/labor-and-commerce/feed/", "section": "Labor & Commerce", "category": "business"},
    {"url": "https://restofworld.org/section/policy-and-rights/feed/", "section": "Policy & Rights", "category": "politics"},
    {"url": "https://restofworld.org/section/gaming/feed/", "section": "Gaming", "category": "culture"},
]

_CATEGORY_KEYWORDS = {
    "security": {"cybersecurity", "hack", "breach", "surveillance", "privacy", "censorship"},
    "science": {"ai", "artificial intelligence", "machine learning", "quantum", "biotech"},
    "world": {"government", "regulation", "election", "war", "geopolitics"},
}


class RestOfWorldSource(BaseSource):
    """Crawl Rest of World RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "restofworld"

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

            # Keyword-based category refinement
            text_lower = f"{title} {summary}".lower()
            refined_category = category
            for cat, keywords in _CATEGORY_KEYWORDS.items():
                if any(kw in text_lower for kw in keywords):
                    refined_category = cat
                    break

            tags = [f"restofworld:{section.lower().replace(' & ', '_').replace(' ', '_')}"]

            articles.append(Article(
                title=title,
                url=link,
                source=f"Rest of World ({section})",
                summary=summary,
                timestamp=ts,
                category=refined_category,
                author=author,
                tags=tags,
                quality_score=0.82,
            ))

        return articles

    def crawl(self) -> List[Article]:
        articles = []
        for feed_info in RESTOFWORLD_FEEDS:
            if self.sections and feed_info["section"].lower() not in self.sections:
                continue
            try:
                articles.extend(self._parse_feed(feed_info))
            except Exception as exc:
                logger.warning("Rest of World %s failed: %s", feed_info["section"], exc)
        return articles
