"""MedPage Today source — fetches articles from RSS feed."""
import logging
import re
from typing import List

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)


class MedPageTodaySource(BaseSource):
    """Crawl MedPage Today RSS feed."""

    name = "medpagetoday"

    FEED_URL = "https://www.medpagetoday.com/rss/headlines.xml"
    DEFAULT_CATEGORY = "health"
    LIMIT = 20

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        try:
            content = self.fetch_url(self.FEED_URL)
            if not content:
                logger.warning("[medpagetoday] Empty response from feed")
                return articles
            parsed = feedparser.parse(content)
        except Exception as e:
            logger.error("[medpagetoday] Failed to fetch/parse feed: %s", e)
            return articles

        for i, entry in enumerate(parsed.entries[:self.LIMIT]):
            try:
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
                for field in ("published", "updated"):
                    raw = entry.get(field)
                    if raw:
                        try:
                            ts = dateparser.parse(raw)
                            break
                        except (ValueError, TypeError):
                            continue

                author = entry.get("author", "").strip()
                quality = round(max(0.4, 0.7 - i * 0.015), 3)

                tags = [
                    "medpagetoday:category:health",
                ]
                if author:
                    tags.append(f"medpagetoday:author:{author.lower()}")

                articles.append(Article(
                    title=title,
                    url=link,
                    source="MedPage Today",
                    summary=summary or "",
                    timestamp=ts,
                    category=self.DEFAULT_CATEGORY,
                    author=author,
                    tags=tags,
                    quality_score=quality,
                ))
            except Exception as e:
                logger.warning("[medpagetoday] Error parsing entry: %s", e)

        logger.info("[medpagetoday] Fetched %d articles", len(articles))
        return articles
