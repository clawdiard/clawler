"""Semafor source — modern news analysis and global journalism.

Semafor delivers news with transparent sourcing and structured analysis.
Free RSS feed, no API key required.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

SEMAFOR_FEEDS = [
    {"url": "https://www.semafor.com/feed", "section": "Latest", "category": "world"},
    {"url": "https://www.semafor.com/vertical/tech/feed", "section": "Tech", "category": "tech"},
    {"url": "https://www.semafor.com/vertical/business/feed", "section": "Business", "category": "business"},
    {"url": "https://www.semafor.com/vertical/media/feed", "section": "Media", "category": "culture"},
    {"url": "https://www.semafor.com/vertical/climate/feed", "section": "Climate", "category": "science"},
    {"url": "https://www.semafor.com/vertical/africa/feed", "section": "Africa", "category": "world"},
    {"url": "https://www.semafor.com/vertical/net-zero/feed", "section": "Net Zero", "category": "science"},
]

_CATEGORY_KEYWORDS = {
    "security": {"cybersecurity", "hack", "breach", "surveillance", "encryption", "nsa"},
    "tech": {"ai", "artificial intelligence", "startup", "software", "silicon valley", "crypto"},
    "science": {"climate", "energy", "research", "carbon", "emissions"},
    "business": {"market", "economy", "trade", "gdp", "inflation", "investment"},
}


class SemaforSource(BaseSource):
    """Crawl Semafor RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "semafor"

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

            text_lower = f"{title} {summary}".lower()
            refined_category = category
            for cat, keywords in _CATEGORY_KEYWORDS.items():
                if any(kw in text_lower for kw in keywords):
                    refined_category = cat
                    break

            tags = [f"semafor:{section.lower().replace(' ', '_')}"]

            articles.append(Article(
                title=title,
                url=link,
                source=f"Semafor ({section})",
                summary=summary,
                timestamp=ts,
                category=refined_category,
                author=author,
                tags=tags,
                quality_score=0.80,
            ))

        return articles

    def crawl(self) -> List[Article]:
        articles = []
        for feed_info in SEMAFOR_FEEDS:
            if self.sections and feed_info["section"].lower() not in self.sections:
                continue
            try:
                articles.extend(self._parse_feed(feed_info))
            except Exception as exc:
                logger.warning("Semafor %s failed: %s", feed_info["section"], exc)
        return articles
