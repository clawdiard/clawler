"""Washington Post source — fetches articles from WaPo RSS feeds.

The Washington Post provides public RSS feeds for all major sections.
No API key required.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

WAPO_FEEDS = [
    {"url": "https://feeds.washingtonpost.com/rss/national", "section": "National", "category": "world"},
    {"url": "https://feeds.washingtonpost.com/rss/world", "section": "World", "category": "world"},
    {"url": "https://feeds.washingtonpost.com/rss/politics", "section": "Politics", "category": "politics"},
    {"url": "https://feeds.washingtonpost.com/rss/business", "section": "Business", "category": "business"},
    {"url": "https://feeds.washingtonpost.com/rss/business/technology", "section": "Technology", "category": "tech"},
    {"url": "https://feeds.washingtonpost.com/rss/climate-environment", "section": "Climate", "category": "science"},
    {"url": "https://feeds.washingtonpost.com/rss/opinions", "section": "Opinions", "category": "opinion"},
]

SECTION_WEIGHTS = {
    "National": 0.80, "World": 0.80, "Politics": 0.80, "Business": 0.75,
    "Technology": 0.80, "Climate": 0.80, "Opinions": 0.70,
}


class WashingtonPostSource(BaseSource):
    """Crawl Washington Post RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "washingtonpost"

    def __init__(self, sections: Optional[List[str]] = None, limit: int = 15):
        self.sections = [s.lower() for s in sections] if sections else None
        self.limit = limit

    def _parse_feed(self, feed_info: dict) -> List[Article]:
        url = feed_info["url"]
        section = feed_info["section"]
        category = feed_info["category"]
        quality = SECTION_WEIGHTS.get(section, 0.70)

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

            articles.append(Article(
                title=title,
                url=link,
                source=f"WaPo ({section})",
                summary=summary,
                timestamp=ts,
                category=category,
                quality_score=quality,
                author=author,
                tags=[f"wapo:{section.lower()}"],
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = WAPO_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]

        all_articles = []
        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info)
                all_articles.extend(articles)
                logger.info(f"[WaPo] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[WaPo] Failed to parse {feed_info['section']}: {e}")

        logger.info(f"[WaPo] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
