"""404 Media source — independent technology and internet journalism.

404 Media is a journalist-owned publication covering hacking, cybersecurity,
consumer tech, digital rights, surveillance, AI, and internet culture.
Founded by former Motherboard (VICE) reporters.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

FEED_URL = "https://www.404media.co/rss/"

# Keyword-based category mapping
CATEGORY_KEYWORDS = {
    "cybersecurity": ["hack", "breach", "malware", "ransomware", "exploit", "vulnerability", "phishing", "cyber"],
    "ai": ["ai", "artificial intelligence", "machine learning", "llm", "chatgpt", "openai", "deepfake", "generative"],
    "privacy": ["surveillance", "privacy", "tracking", "data broker", "spyware", "stalkerware", "nso", "pegasus"],
    "internet_culture": ["social media", "tiktok", "youtube", "reddit", "discord", "meme", "viral", "influencer"],
    "policy": ["regulation", "law", "fcc", "ftc", "congress", "legislation", "ban", "court"],
}


def _categorize(title: str, summary: str) -> str:
    """Assign a category based on keyword matching in title and summary."""
    text = f"{title} {summary}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "tech"


class FourZeroFourMediaSource(BaseSource):
    """Crawl 404 Media's RSS feed.

    Parameters
    ----------
    limit : int
        Maximum articles to return. Default 25.
    categories : list of str or None
        Filter to specific categories. None = all.
    """

    name = "404media"

    def __init__(self, limit: int = 25, categories: Optional[List[str]] = None):
        self.limit = limit
        self.categories = [c.lower() for c in categories] if categories else None

    def crawl(self) -> List[Article]:
        content = self.fetch_url(FEED_URL)
        if not content:
            logger.warning("[404Media] Failed to fetch RSS feed")
            return []

        parsed = feedparser.parse(content)
        articles = []

        for entry in parsed.entries[:self.limit]:
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

            author = entry.get("author", "")
            category = _categorize(title, summary)

            if self.categories and category not in self.categories:
                continue

            # Extract tags from entry if available
            tags = ["404media"]
            if hasattr(entry, "tags"):
                for tag in entry.get("tags", []):
                    term = tag.get("term", "").strip()
                    if term:
                        tags.append(term.lower())

            articles.append(Article(
                title=title,
                url=link,
                source="404 Media",
                summary=summary,
                timestamp=ts,
                category=category,
                author=author,
                tags=tags,
            ))

        logger.info(f"[404Media] Fetched {len(articles)} articles")
        return articles
