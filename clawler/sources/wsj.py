"""Wall Street Journal source — fetches articles from WSJ RSS feeds.

WSJ provides public RSS feeds for major sections. Full article content
may be paywalled, but headlines, summaries, and metadata are freely available.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

WSJ_FEEDS = [
    {"url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml", "section": "World", "category": "world"},
    {"url": "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml", "section": "Business", "category": "business"},
    {"url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "section": "Markets", "category": "business"},
    {"url": "https://feeds.a.dj.com/rss/RSSWSJD.xml", "section": "Tech", "category": "tech"},
    {"url": "https://feeds.a.dj.com/rss/RSSLifestyle.xml", "section": "Lifestyle", "category": "culture"},
    {"url": "https://feeds.a.dj.com/rss/RSSOpinion.xml", "section": "Opinion", "category": "opinion"},
]

SECTION_WEIGHTS = {
    "World": 0.85, "Business": 0.85, "Markets": 0.80,
    "Tech": 0.85, "Lifestyle": 0.65, "Opinion": 0.75,
}


class WSJSource(BaseSource):
    """Crawl Wall Street Journal RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "wsj"

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
                source=f"WSJ ({section})",
                summary=summary,
                timestamp=ts,
                category=category,
                quality_score=quality,
                author=author,
                tags=[f"wsj:{section.lower()}"],
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = WSJ_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]

        all_articles = []
        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info)
                all_articles.extend(articles)
                logger.info(f"[WSJ] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[WSJ] Failed to parse {feed_info['section']}: {e}")

        logger.info(f"[WSJ] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
