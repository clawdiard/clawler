"""AP News source — fetches articles from the Associated Press RSS feeds.

AP News is one of the most widely-trusted wire services globally.
Covers: top news, world, US, politics, business, technology, science, health, sports, entertainment.
All feeds are freely available RSS — no API key required.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

AP_FEEDS = [
    {"url": "https://rsshub.app/apnews/topics/apf-topnews", "section": "Top News", "category": "world"},
    {"url": "https://rsshub.app/apnews/topics/apf-WorldNews", "section": "World", "category": "world"},
    {"url": "https://rsshub.app/apnews/topics/apf-usnews", "section": "US News", "category": "world"},
    {"url": "https://rsshub.app/apnews/topics/apf-politics", "section": "Politics", "category": "politics"},
    {"url": "https://rsshub.app/apnews/topics/apf-business", "section": "Business", "category": "business"},
    {"url": "https://rsshub.app/apnews/topics/apf-technology", "section": "Technology", "category": "tech"},
    {"url": "https://rsshub.app/apnews/topics/apf-science", "section": "Science", "category": "science"},
    {"url": "https://rsshub.app/apnews/topics/apf-Health", "section": "Health", "category": "health"},
    {"url": "https://rsshub.app/apnews/topics/apf-sports", "section": "Sports", "category": "sports"},
    {"url": "https://rsshub.app/apnews/topics/apf-entertainment", "section": "Entertainment", "category": "culture"},
]


class APNewsSource(BaseSource):
    """Crawl AP News section RSS feeds via RSSHub mirror.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "apnews"

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

        for entry in parsed.entries[: self.limit]:
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
                source=f"AP News ({section})",
                summary=summary,
                timestamp=ts,
                category=category,
                author=author,
                tags=[f"apnews:{section.lower()}"],
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = AP_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]

        all_articles = []
        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info)
                all_articles.extend(articles)
                logger.info(f"[AP News] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[AP News] Failed to parse {feed_info['section']}: {e}")

        logger.info(f"[AP News] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
