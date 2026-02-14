"""ProductHunt source — trending products via RSS (no key needed)."""
import logging
from datetime import datetime
from typing import List, Optional
import feedparser
from dateutil import parser as dateparser
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

PRODUCTHUNT_FEED = "https://www.producthunt.com/feed"


class ProductHuntSource(BaseSource):
    """Fetch trending products from ProductHunt's RSS feed."""

    name = "producthunt"
    timeout = 15

    def crawl(self) -> List[Article]:
        text = self.fetch_url(PRODUCTHUNT_FEED)
        if not text:
            return []

        feed = feedparser.parse(text)
        articles: List[Article] = []

        for entry in feed.entries:
            title = getattr(entry, "title", "").strip()
            link = getattr(entry, "link", "").strip()
            if not title or not link:
                continue

            summary = ""
            if hasattr(entry, "summary"):
                import re
                summary = re.sub(r"<[^>]+>", "", entry.summary).strip()
                if len(summary) > 300:
                    summary = summary[:297] + "..."

            timestamp = self._parse_date(entry)

            articles.append(Article(
                title=title,
                url=link,
                source="ProductHunt",
                summary=summary,
                timestamp=timestamp,
                category="tech",
                discussion_url=link,  # PH links are the discussion page
            ))

        logger.info(f"[ProductHunt] Parsed {len(articles)} articles")
        return articles

    @staticmethod
    def _parse_date(entry) -> Optional[datetime]:
        for field in ("published", "updated"):
            raw = getattr(entry, field, None)
            if raw:
                try:
                    return dateparser.parse(raw)
                except (ValueError, OverflowError):
                    pass
        return None
