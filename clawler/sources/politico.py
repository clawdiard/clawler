"""Politico source — fetches articles from Politico RSS feeds.

Politico is a leading political journalism outlet covering US and global
politics, policy, and power dynamics. Free RSS feeds, no API key required.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

POLITICO_FEEDS = [
    {"url": "https://rss.politico.com/politics-news.xml", "section": "Politics", "category": "politics"},
    {"url": "https://rss.politico.com/congress.xml", "section": "Congress", "category": "politics"},
    {"url": "https://rss.politico.com/economy.xml", "section": "Economy", "category": "business"},
    {"url": "https://rss.politico.com/healthcare.xml", "section": "Healthcare", "category": "health"},
    {"url": "https://rss.politico.com/defense.xml", "section": "Defense", "category": "world"},
    {"url": "https://rss.politico.com/energy.xml", "section": "Energy", "category": "science"},
    {"url": "https://rss.politico.com/technology.xml", "section": "Technology", "category": "tech"},
    {"url": "https://rss.politico.com/education.xml", "section": "Education", "category": "education"},
]

# Keywords for category refinement
_CATEGORY_KEYWORDS = {
    "security": {"cybersecurity", "hack", "breach", "nsa", "surveillance", "encryption"},
    "tech": {"ai", "artificial intelligence", "tech", "software", "algorithm", "data"},
    "world": {"nato", "ukraine", "china", "europe", "foreign", "diplomacy", "sanctions"},
}


class PoliticoSource(BaseSource):
    """Crawl Politico RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "politico"

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

            tags = [f"politico:{section.lower()}"]

            articles.append(Article(
                title=title,
                url=link,
                source=f"Politico ({section})",
                summary=summary,
                timestamp=ts,
                category=refined_category,
                author=author,
                tags=tags,
                quality_score=0.78,
            ))

        return articles

    def crawl(self) -> List[Article]:
        articles = []
        for feed_info in POLITICO_FEEDS:
            if self.sections and feed_info["section"].lower() not in self.sections:
                continue
            try:
                articles.extend(self._parse_feed(feed_info))
            except Exception as exc:
                logger.warning("Politico %s failed: %s", feed_info["section"], exc)
        return articles
