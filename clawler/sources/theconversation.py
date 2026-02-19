"""The Conversation source — academic expertise for a general audience.

Free RSS feeds, no API key required. Articles are written by scholars
and fact-checked by professional editors.
"""
import logging
import re
from typing import List, Optional, Set

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

CONVERSATION_FEEDS = [
    {"url": "https://theconversation.com/us/articles.atom", "section": "US", "category": "world"},
    {"url": "https://theconversation.com/us/technology/articles.atom", "section": "Technology", "category": "tech"},
    {"url": "https://theconversation.com/us/science/articles.atom", "section": "Science", "category": "science"},
    {"url": "https://theconversation.com/us/health/articles.atom", "section": "Health", "category": "science"},
    {"url": "https://theconversation.com/us/business/articles.atom", "section": "Business", "category": "business"},
    {"url": "https://theconversation.com/us/environment/articles.atom", "section": "Environment", "category": "science"},
    {"url": "https://theconversation.com/us/politics/articles.atom", "section": "Politics", "category": "world"},
    {"url": "https://theconversation.com/us/arts/articles.atom", "section": "Arts", "category": "culture"},
]

_CATEGORY_KEYWORDS = {
    "security": {"cybersecurity", "hack", "breach", "surveillance", "encryption"},
    "tech": {"ai", "artificial intelligence", "machine learning", "algorithm", "software", "robot"},
    "science": {"climate", "research", "study", "experiment", "species", "quantum"},
    "business": {"economy", "market", "inflation", "trade", "gdp"},
}


class TheConversationSource(BaseSource):
    """Crawl The Conversation Atom feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "theconversation"

    def __init__(self, sections: Optional[List[str]] = None, limit: int = 15):
        self.sections = [s.lower() for s in sections] if sections else None
        self.limit = limit

    def _parse_feed(self, feed_info: dict, seen_urls: Set[str]) -> List[Article]:
        url = feed_info["url"]
        section = feed_info["section"]
        category = feed_info["category"]

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
            if link in seen_urls:
                continue
            seen_urls.add(link)

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

            tags = [f"conversation:{section.lower().replace(' ', '_')}"]

            articles.append(
                Article(
                    title=title,
                    url=link,
                    source=f"The Conversation ({section})",
                    summary=summary,
                    timestamp=ts,
                    category=refined_category,
                    author=author,
                    tags=tags,
                    quality_score=0.82,
                )
            )

        return articles

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        seen_urls: Set[str] = set()
        for feed_info in CONVERSATION_FEEDS:
            if self.sections and feed_info["section"].lower() not in self.sections:
                continue
            try:
                articles.extend(self._parse_feed(feed_info, seen_urls))
            except Exception as exc:
                logger.warning("The Conversation %s failed: %s", feed_info["section"], exc)
        return articles
