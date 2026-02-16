"""InfoQ source — enterprise software engineering articles via RSS (no key needed)."""
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# InfoQ topic RSS feeds (all public)
INFOQ_FEEDS = [
    {"url": "https://feed.infoq.com/", "topic": "all"},
    {"url": "https://feed.infoq.com/ai-ml-data-eng", "topic": "ai"},
    {"url": "https://feed.infoq.com/architecture-design", "topic": "architecture"},
    {"url": "https://feed.infoq.com/cloud-computing", "topic": "cloud"},
    {"url": "https://feed.infoq.com/devops", "topic": "devops"},
    {"url": "https://feed.infoq.com/java", "topic": "java"},
    {"url": "https://feed.infoq.com/dotnet", "topic": "dotnet"},
]

_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.DOTALL)
_TAG_RE = {
    "title": re.compile(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", re.DOTALL),
    "link": re.compile(r"<link>(.*?)</link>"),
    "description": re.compile(
        r"<description><!\[CDATA\[(.*?)\]\]></description>|<description>(.*?)</description>",
        re.DOTALL,
    ),
    "pubDate": re.compile(r"<pubDate>(.*?)</pubDate>"),
    "category": re.compile(r"<category><!\[CDATA\[(.*?)\]\]></category>|<category>(.*?)</category>"),
    "author": re.compile(r"<author>(.*?)</author>|<dc:creator><!\[CDATA\[(.*?)\]\]></dc:creator>|<dc:creator>(.*?)</dc:creator>", re.DOTALL),
}

# Map InfoQ topics/categories to clawler categories
TOPIC_MAP = {
    "ai": "ai",
    "ai-ml-data-eng": "ai",
    "architecture": "tech",
    "architecture-design": "tech",
    "cloud": "tech",
    "cloud-computing": "tech",
    "devops": "tech",
    "java": "tech",
    "dotnet": "tech",
    "security": "security",
    "all": "tech",
}

# Keyword-based category detection for finer categorization
_CATEGORY_KEYWORDS = {
    "ai": ["ai", "machine learning", "deep learning", "llm", "gpt", "neural", "ml ", "artificial intelligence", "generative ai", "transformer"],
    "security": ["security", "vulnerability", "cve", "breach", "authentication", "encryption", "zero-day", "ransomware"],
    "business": ["leadership", "management", "agile", "scrum", "team", "organization", "hiring", "culture", "strategy"],
    "science": ["research", "quantum", "physics"],
}


def _extract(pattern, text) -> str:
    m = pattern.search(text)
    if not m:
        return ""
    return next((g for g in m.groups() if g is not None), "").strip()


def _extract_all(pattern, text) -> List[str]:
    results = []
    for m in pattern.finditer(text):
        val = next((g for g in m.groups() if g is not None), "").strip()
        if val:
            results.append(val)
    return results


def _detect_category(title: str, summary: str, topic: str) -> str:
    """Detect category from title/summary keywords, falling back to topic map."""
    text = f"{title} {summary}".lower()
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return cat
    return TOPIC_MAP.get(topic, "tech")


class InfoQSource(BaseSource):
    """Fetch enterprise software engineering articles from InfoQ RSS feeds."""

    name = "infoq"

    def __init__(self, feeds: Optional[List[dict]] = None, limit: int = 20,
                 topics: Optional[List[str]] = None):
        """
        Args:
            feeds: Custom feed list (overrides defaults).
            limit: Max articles per feed.
            topics: Topic filter — only fetch these topics (e.g. ["ai", "devops"]).
        """
        self.feeds = feeds or INFOQ_FEEDS
        self.limit = limit
        if topics:
            topic_set = set(t.lower() for t in topics)
            self.feeds = [f for f in self.feeds if f["topic"] in topic_set]

    def _parse_feed(self, feed_url: str, topic: str) -> List[Article]:
        xml = self.fetch_url(feed_url)
        if not xml:
            return []

        articles: List[Article] = []
        seen_urls: set = set()
        items = _ITEM_RE.findall(xml)

        for item_xml in items[:self.limit]:
            try:
                title = _extract(_TAG_RE["title"], item_xml)
                url = _extract(_TAG_RE["link"], item_xml)
                if not title or not url:
                    continue
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                summary = _extract(_TAG_RE["description"], item_xml)
                summary = re.sub(r"<[^>]+>", "", summary).strip()[:300]

                ts = None
                pub_date = _extract(_TAG_RE["pubDate"], item_xml)
                if pub_date:
                    try:
                        ts = parsedate_to_datetime(pub_date)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

                # Extract categories/tags from RSS
                rss_categories = _extract_all(_TAG_RE["category"], item_xml)

                # Extract author
                author = _extract(_TAG_RE["author"], item_xml)

                category = _detect_category(title, summary, topic)

                tags = [f"infoq:topic:{topic}"]
                if author:
                    tags.append(f"infoq:author:{author}")
                for rc in rss_categories[:5]:
                    tags.append(f"infoq:tag:{rc.lower()}")

                source_label = f"InfoQ ({topic})" if topic != "all" else "InfoQ"

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=source_label,
                        summary=summary,
                        timestamp=ts,
                        category=category,
                        tags=tags,
                    )
                )
            except Exception as e:
                logger.debug(f"[InfoQ] Skipping item: {e}")
                continue

        return articles

    def crawl(self) -> List[Article]:
        all_articles: List[Article] = []
        seen_urls: set = set()

        for feed in self.feeds:
            try:
                articles = self._parse_feed(feed["url"], feed["topic"])
                for a in articles:
                    if a.url not in seen_urls:
                        seen_urls.add(a.url)
                        all_articles.append(a)
            except Exception as e:
                logger.warning(f"[InfoQ] Failed to fetch {feed['topic']}: {e}")

        logger.info(f"[InfoQ] Fetched {len(all_articles)} articles from {len(self.feeds)} topic feeds")
        return all_articles
