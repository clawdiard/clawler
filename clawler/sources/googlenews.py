"""Google News source — topic and geo-based news via public RSS feeds.

Google News exposes RSS feeds for topics, search queries, and geographic regions
at news.google.com/rss/. No API key required. This source covers major topic
categories with high-quality, editorially selected articles from thousands of
publishers worldwide.
"""
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional
from xml.etree import ElementTree as ET

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Google News topic IDs and their RSS endpoints
GOOGLE_NEWS_TOPICS = [
    # Major sections
    {"topic": "CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB", "name": "Top Stories", "category": "world"},
    {"topic": "CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB", "name": "Technology", "category": "tech"},
    {"topic": "CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB", "name": "Science", "category": "science"},
    {"topic": "CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB:science", "name": "Science", "category": "science"},
    {"topic": "CAAqJggKIiBDQkFTRWdvSUwyMHZNREpxYW5RU0FtVnVHZ0pWVXlnQVAB", "name": "Business", "category": "business"},
    {"topic": "CAAqJggKIiBDQkFTRWdvSUwyMHZNRE55YXpBU0FtVnVHZ0pWVXlnQVAB", "name": "Health", "category": "science"},
    {"topic": "CAAqJggKIiBDQkFTRWdvSUwyMHZNREpxYW5RU0FtVnVHZ0pWVXlnQVAB:business", "name": "Business", "category": "business"},
]

# Search-based feeds for niche topics not covered by main sections
GOOGLE_NEWS_SEARCHES = [
    {"query": "artificial intelligence", "name": "AI News", "category": "tech"},
    {"query": "cybersecurity", "name": "Cybersecurity", "category": "security"},
    {"query": "open source software", "name": "Open Source", "category": "tech"},
    {"query": "climate change environment", "name": "Climate & Environment", "category": "science"},
    {"query": "space exploration NASA", "name": "Space", "category": "science"},
    {"query": "cryptocurrency blockchain", "name": "Crypto & Blockchain", "category": "business"},
    {"query": "startup funding venture capital", "name": "Startups & VC", "category": "business"},
    {"query": "investigative journalism", "name": "Investigative", "category": "investigative"},
]

_HTML_TAG_RE = re.compile(r"<[^>]+>")


class GoogleNewsSource(BaseSource):
    """Fetches articles from Google News RSS feeds (topics + search queries)."""

    name = "Google News"
    timeout = 12

    def __init__(
        self,
        topics: Optional[List[dict]] = None,
        searches: Optional[List[dict]] = None,
        max_per_feed: int = 8,
        lang: str = "en",
        geo: str = "US",
    ):
        self.topics = topics if topics is not None else GOOGLE_NEWS_TOPICS
        self.searches = searches if searches is not None else GOOGLE_NEWS_SEARCHES
        self.max_per_feed = max_per_feed
        self.lang = lang
        self.geo = geo

    def _feed_url_for_topic(self, topic_id: str) -> str:
        return f"https://news.google.com/rss/topics/{topic_id}?hl={self.lang}&gl={self.geo}&ceid={self.geo}:{self.lang}"

    def _feed_url_for_search(self, query: str) -> str:
        from urllib.parse import quote_plus
        return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl={self.lang}&gl={self.geo}&ceid={self.geo}:{self.lang}"

    def _parse_feed(self, url: str, source_label: str, category: str) -> List[Article]:
        """Parse a Google News RSS feed and return articles."""
        text = self.fetch_url(url)
        if not text:
            return []

        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            logger.warning(f"[Google News] XML parse error for {source_label}: {e}")
            return []

        articles: List[Article] = []
        for item in root.findall(".//item")[: self.max_per_feed]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue

            # Google News titles often end with " - <Publisher>"
            publisher = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                if len(parts) == 2 and len(parts[1]) < 60:
                    publisher = parts[1].strip()

            description = (item.findtext("description") or "").strip()
            clean_desc = _HTML_TAG_RE.sub("", description)[:300].strip()

            pub_date = item.findtext("pubDate")
            timestamp = None
            if pub_date:
                try:
                    timestamp = parsedate_to_datetime(pub_date)
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            source_name = f"Google News ({source_label})"
            if publisher:
                source_name = f"Google News ({publisher})"

            articles.append(
                Article(
                    title=title,
                    url=link,
                    source=source_name,
                    summary=clean_desc[:300],
                    timestamp=timestamp,
                    category=category,
                    author=publisher,
                )
            )

        return articles

    def crawl(self) -> List[Article]:
        """Crawl all configured Google News topic and search feeds."""
        all_articles: List[Article] = []

        # Topic feeds
        seen_topics = set()
        for topic_info in self.topics:
            topic_id = topic_info["topic"].split(":")[0]  # strip dedup suffix
            if topic_id in seen_topics:
                continue
            seen_topics.add(topic_id)
            url = self._feed_url_for_topic(topic_info["topic"])
            try:
                articles = self._parse_feed(url, topic_info["name"], topic_info["category"])
                all_articles.extend(articles)
            except Exception as e:
                logger.warning(f"[Google News] Error crawling topic {topic_info['name']}: {e}")

        # Search feeds
        for search_info in self.searches:
            url = self._feed_url_for_search(search_info["query"])
            try:
                articles = self._parse_feed(url, search_info["name"], search_info["category"])
                all_articles.extend(articles)
            except Exception as e:
                logger.warning(f"[Google News] Error crawling search '{search_info['query']}': {e}")

        logger.info(
            f"[Google News] Fetched {len(all_articles)} articles from "
            f"{len(seen_topics)} topics + {len(self.searches)} searches"
        )
        return all_articles
