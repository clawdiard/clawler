"""DZone source — developer articles and tutorials from dzone.com (no key needed).

Enhanced features:
- Quality scoring (0–1) based on topic prominence, keyword categories, title signals
- Keyword-based category detection from title/summary
- Filters: min_quality, category_filter
"""
import logging
import math
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Set

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# DZone topic RSS feeds — curated selection of high-signal developer topics
DZONE_FEEDS = [
    {"url": "https://feeds.dzone.com/home", "topic": "general"},
    {"url": "https://feeds.dzone.com/ai", "topic": "ai"},
    {"url": "https://feeds.dzone.com/cloud", "topic": "cloud"},
    {"url": "https://feeds.dzone.com/devops", "topic": "devops"},
    {"url": "https://feeds.dzone.com/microservices", "topic": "microservices"},
    {"url": "https://feeds.dzone.com/security", "topic": "security"},
    {"url": "https://feeds.dzone.com/webdev", "topic": "webdev"},
    {"url": "https://feeds.dzone.com/java", "topic": "java"},
    {"url": "https://feeds.dzone.com/python", "topic": "python"},
    {"url": "https://feeds.dzone.com/database", "topic": "database"},
    {"url": "https://feeds.dzone.com/iot", "topic": "iot"},
    {"url": "https://feeds.dzone.com/performance", "topic": "performance"},
    {"url": "https://feeds.dzone.com/agile", "topic": "agile"},
    {"url": "https://feeds.dzone.com/integration", "topic": "integration"},
    {"url": "https://feeds.dzone.com/big-data", "topic": "big-data"},
]

# Topic prominence — specialty feeds score higher than general
TOPIC_PROMINENCE: Dict[str, float] = {
    "ai": 0.25,
    "security": 0.22,
    "cloud": 0.20,
    "devops": 0.20,
    "performance": 0.18,
    "big-data": 0.18,
    "microservices": 0.15,
    "database": 0.15,
    "python": 0.15,
    "java": 0.15,
    "webdev": 0.15,
    "iot": 0.15,
    "agile": 0.12,
    "integration": 0.12,
    "general": 0.10,
}

# Keyword categories detected from title/summary text
KEYWORD_CATEGORIES: Dict[str, List[str]] = {
    "ai": ["machine learning", "deep learning", "neural", "llm", "gpt", "transformer",
           "artificial intelligence", "nlp", "generative ai", "chatbot"],
    "security": ["vulnerability", "exploit", "authentication", "encryption", "zero-day",
                 "malware", "ransomware", "firewall", "penetration", "oauth", "ssl", "tls"],
    "tech": ["kubernetes", "docker", "microservice", "api", "rest", "graphql", "grpc",
             "serverless", "terraform", "ci/cd", "pipeline", "container", "observability"],
    "science": ["quantum", "algorithm", "research", "computation"],
}

# Title signals that indicate high-quality content
_QUALITY_TITLE_SIGNALS = [
    "guide", "tutorial", "best practices", "deep dive", "architecture",
    "benchmark", "comparison", "how to", "step-by-step", "production",
    "scalable", "performance", "optimization", "patterns",
]


def _compute_quality(topic: str, title: str, summary: str, categories: List[str]) -> float:
    """Compute quality score (0–1) for a DZone article."""
    q = 0.0
    text_lower = f"{title} {summary}".lower()

    # Topic prominence (0–0.25)
    q += TOPIC_PROMINENCE.get(topic, 0.10)

    # Title quality signals (0–0.25)
    signal_hits = sum(1 for s in _QUALITY_TITLE_SIGNALS if s in text_lower)
    q += min(0.25, signal_hits * 0.08)

    # Category richness — more categories = more detailed (0–0.15)
    q += min(0.15, len(categories) * 0.03)

    # Keyword category match bonus (0–0.20)
    kw_hits = 0
    for cat_keywords in KEYWORD_CATEGORIES.values():
        kw_hits += sum(1 for kw in cat_keywords if kw in text_lower)
    q += min(0.20, kw_hits * 0.05)

    # Title length penalty — very short titles are often low quality
    if len(title) < 20:
        q -= 0.05
    elif len(title) > 50:
        q += 0.05

    return min(1.0, max(0.0, round(q, 3)))

# Simple tag extraction from XML without requiring feedparser
_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.DOTALL)
_TAG_RE = {
    "title": re.compile(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", re.DOTALL),
    "link": re.compile(r"<link>(.*?)</link>"),
    "description": re.compile(
        r"<description><!\[CDATA\[(.*?)\]\]></description>|<description>(.*?)</description>",
        re.DOTALL,
    ),
    "pubDate": re.compile(r"<pubDate>(.*?)</pubDate>"),
    "creator": re.compile(r"<dc:creator><!\[CDATA\[(.*?)\]\]></dc:creator>|<dc:creator>(.*?)</dc:creator>"),
    "category": re.compile(
        r"<category><!\[CDATA\[(.*?)\]\]></category>|<category>(.*?)</category>"
    ),
}


def _extract(pattern, text):
    m = pattern.search(text)
    if not m:
        return ""
    return next((g for g in m.groups() if g is not None), "").strip()


def _extract_all(pattern, text):
    return [next(g for g in m.groups() if g is not None).strip() for m in pattern.finditer(text)]


class DZoneSource(BaseSource):
    """Fetch developer articles from DZone topic RSS feeds."""

    name = "dzone"

    def __init__(self, feeds=None, limit: int = 15):
        self.feeds = feeds or DZONE_FEEDS
        self.limit = limit

    def _parse_feed(self, feed_url: str, topic: str) -> List[Article]:
        xml = self.fetch_url(feed_url)
        if not xml:
            return []

        articles: List[Article] = []
        items = _ITEM_RE.findall(xml)

        for item_xml in items[: self.limit]:
            try:
                title = _extract(_TAG_RE["title"], item_xml)
                url = _extract(_TAG_RE["link"], item_xml)
                if not title or not url:
                    continue

                summary = _extract(_TAG_RE["description"], item_xml)
                # Strip HTML tags from summary
                summary = re.sub(r"<[^>]+>", "", summary).strip()[:300]

                author = _extract(_TAG_RE["creator"], item_xml)
                categories = _extract_all(_TAG_RE["category"], item_xml)

                ts = None
                pub_date = _extract(_TAG_RE["pubDate"], item_xml)
                if pub_date:
                    try:
                        ts = parsedate_to_datetime(pub_date)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

                tags = [f"dzone:{topic}"]
                for cat in categories[:5]:
                    tag = cat.lower().replace(" ", "-")
                    tags.append(f"dzone:{tag}")

                # Map topic to category (enhanced)
                cat_map = {
                    "ai": "ai",
                    "security": "security",
                    "cloud": "tech",
                    "devops": "tech",
                    "webdev": "tech",
                    "iot": "tech",
                    "big-data": "tech",
                    "agile": "business",
                    "integration": "tech",
                    "performance": "tech",
                }
                category = cat_map.get(topic, "tech")

                # Override category from keyword detection only if topic mapped to generic "tech"
                if category == "tech":
                    text_lower = f"{title} {summary}".lower()
                    for kw_cat, keywords in KEYWORD_CATEGORIES.items():
                        if any(kw in text_lower for kw in keywords):
                            category = kw_cat
                            break

                quality = _compute_quality(topic, title, summary, categories)

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=f"DZone ({topic})",
                        summary=summary,
                        timestamp=ts,
                        category=category,
                        tags=tags,
                        author=author,
                        quality_score=quality,
                    )
                )
            except Exception as e:
                logger.debug(f"[DZone] Skipping item: {e}")
                continue

        return articles

    def crawl(self) -> List[Article]:
        all_articles: List[Article] = []
        for feed in self.feeds:
            try:
                articles = self._parse_feed(feed["url"], feed["topic"])
                all_articles.extend(articles)
            except Exception as e:
                logger.warning(f"[DZone] Failed to fetch {feed['topic']}: {e}")

        logger.info(f"[DZone] Fetched {len(all_articles)} articles from {len(self.feeds)} topic feeds")
        return all_articles
