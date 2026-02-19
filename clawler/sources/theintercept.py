"""The Intercept source — adversarial investigative journalism.

Free RSS feeds, no API key required.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

INTERCEPT_FEEDS = [
    {"url": "https://theintercept.com/feed/?rss", "section": "Latest", "category": "investigative"},
    {"url": "https://theintercept.com/staff/ken-klippenstein/feed/", "section": "Ken Klippenstein", "category": "investigative"},
]

_CATEGORY_KEYWORDS = {
    "security": {"surveillance", "nsa", "fbi", "cia", "hack", "cybersecurity", "encryption", "spy"},
    "tech": {"ai", "artificial intelligence", "algorithm", "silicon valley", "big tech", "meta", "google"},
    "world": {"war", "military", "drone", "gaza", "ukraine", "foreign policy"},
    "business": {"corporate", "wall street", "billionaire", "lobbying"},
    "science": {"climate", "environment", "pollution", "fossil fuel"},
}


class TheInterceptSource(BaseSource):
    """Crawl The Intercept RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per feed. Default 15.
    """

    name = "theintercept"

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
        articles: List[Article] = []

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

            text_lower = f"{title} {summary}".lower()
            refined_category = category
            for cat, keywords in _CATEGORY_KEYWORDS.items():
                if any(kw in text_lower for kw in keywords):
                    refined_category = cat
                    break

            tags = [f"intercept:{section.lower().replace(' ', '_')}"]

            articles.append(
                Article(
                    title=title,
                    url=link,
                    source=f"The Intercept ({section})",
                    summary=summary,
                    timestamp=ts,
                    category=refined_category,
                    author=author,
                    tags=tags,
                    quality_score=0.85,
                )
            )

        return articles

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        for feed_info in INTERCEPT_FEEDS:
            if self.sections and feed_info["section"].lower() not in self.sections:
                continue
            try:
                articles.extend(self._parse_feed(feed_info))
            except Exception as exc:
                logger.warning("The Intercept %s failed: %s", feed_info["section"], exc)
        return articles
