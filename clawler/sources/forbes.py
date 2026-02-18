"""Forbes source — fetches articles from Forbes RSS feeds.

Forbes provides business, tech, entrepreneurship, and leadership news.
Free RSS feeds available at forbes.com.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

FORBES_FEEDS = [
    {"url": "https://www.forbes.com/innovation/feed2", "section": "Innovation", "category": "tech"},
    {"url": "https://www.forbes.com/business/feed2", "section": "Business", "category": "business"},
    {"url": "https://www.forbes.com/leadership/feed2", "section": "Leadership", "category": "business"},
    {"url": "https://www.forbes.com/money/feed2", "section": "Money", "category": "business"},
    {"url": "https://www.forbes.com/ai/feed2", "section": "AI", "category": "tech"},
    {"url": "https://www.forbes.com/cybersecurity/feed2", "section": "Cybersecurity", "category": "security"},
    {"url": "https://www.forbes.com/healthcare/feed2", "section": "Healthcare", "category": "science"},
    {"url": "https://www.forbes.com/digital-assets/feed2", "section": "Digital Assets", "category": "business"},
    {"url": "https://www.forbes.com/lifestyle/feed2", "section": "Lifestyle", "category": "culture"},
    {"url": "https://www.forbes.com/world/feed2", "section": "World", "category": "world"},
]

_QUALITY_KEYWORDS = {
    "high": ["billionaire", "ai", "startup", "ipo", "acquisition", "billion", "funding",
             "ceo", "unicorn", "venture capital", "breakthrough", "cybersecurity", "ransomware"],
    "medium": ["entrepreneur", "innovation", "market", "growth", "investor", "valuation",
               "revenue", "leadership", "strategy", "digital", "cloud", "fintech"],
}


def _quality_boost(title: str, summary: str) -> float:
    text = f"{title} {summary}".lower()
    for kw in _QUALITY_KEYWORDS["high"]:
        if kw in text:
            return 0.15
    for kw in _QUALITY_KEYWORDS["medium"]:
        if kw in text:
            return 0.08
    return 0.0


class ForbesSource(BaseSource):
    """Crawl Forbes RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "forbes"

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
            boost = _quality_boost(title, summary)

            articles.append(Article(
                title=title,
                url=link,
                source=f"Forbes ({section})",
                summary=summary,
                timestamp=ts,
                category=category,
                quality_score=0.68 + boost,
                author=author,
                tags=[f"forbes:{section.lower()}"],
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = FORBES_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]

        all_articles = []
        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info)
                all_articles.extend(articles)
                logger.info(f"[Forbes] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[Forbes] Failed to parse {feed_info['section']}: {e}")

        logger.info(f"[Forbes] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
