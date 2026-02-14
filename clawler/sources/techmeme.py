"""TechMeme source — curated tech news river via RSS (no key needed)."""
import logging
from datetime import datetime
from typing import List, Optional
import feedparser
from dateutil import parser as dateparser
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

TECHMEME_FEED = "https://www.techmeme.com/feed.xml"


class TechMemeSource(BaseSource):
    """Fetch top tech stories from TechMeme's RSS feed."""

    name = "techmeme"
    timeout = 15

    def crawl(self) -> List[Article]:
        text = self.fetch_url(TECHMEME_FEED)
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
                summary = entry.summary.strip()
                # Strip HTML tags from summary
                import re
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                if len(summary) > 300:
                    summary = summary[:297] + "..."

            timestamp = self._parse_date(entry)

            articles.append(Article(
                title=title,
                url=link,
                source="TechMeme",
                summary=summary,
                timestamp=timestamp,
                category="tech",
            ))

        logger.info(f"[TechMeme] Parsed {len(articles)} articles")
        return articles

    @staticmethod
    def _parse_date(entry) -> Optional[datetime]:
        """Extract and parse date from feed entry."""
        for field in ("published", "updated"):
            raw = getattr(entry, field, None)
            if raw:
                try:
                    return dateparser.parse(raw)
                except (ValueError, OverflowError):
                    pass
        return None
