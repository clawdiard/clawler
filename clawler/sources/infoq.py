"""InfoQ source — enterprise software engineering articles via RSS (no key needed).

Enhanced features (v10.83.0):
- Quality scoring (0–1) based on topic prominence + keyword specificity + position
- 7 topic feeds covering AI, architecture, cloud, DevOps, Java, .NET, and general
- Two-tier keyword category detection
- Rich summaries with author/topic metadata
- Provenance tags: infoq:topic, infoq:category, infoq:author, infoq:tag
- Filters: min_quality, category_filter, global_limit
- Cross-feed URL deduplication
"""
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Set

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

# Topic prominence scores
TOPIC_PROMINENCE: Dict[str, float] = {
    "ai": 0.55,
    "architecture": 0.50,
    "cloud": 0.50,
    "devops": 0.48,
    "java": 0.45,
    "dotnet": 0.45,
    "all": 0.42,
}

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
    "ai": [
        "ai", "machine learning", "deep learning", "llm", "gpt", "neural",
        "ml ", "artificial intelligence", "generative ai", "transformer",
        "large language model", "chatgpt", "copilot",
    ],
    "security": [
        "security", "vulnerability", "cve", "breach", "authentication",
        "encryption", "zero-day", "ransomware", "cybersecurity", "owasp",
    ],
    "business": [
        "leadership", "management", "agile", "scrum", "team", "organization",
        "hiring", "culture", "strategy", "enterprise",
    ],
    "science": ["research", "quantum", "physics"],
    "devops": [
        "kubernetes", "docker", "ci/cd", "pipeline", "terraform", "ansible",
        "gitops", "observability", "monitoring", "sre",
    ],
    "cloud": [
        "aws", "azure", "gcp", "serverless", "lambda", "microservices",
        "cloud native", "containers",
    ],
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
    """Two-tier: keyword hits first, then topic map fallback."""
    text = f"{title} {summary}".lower()
    best_cat = None
    best_hits = 0
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits > best_hits:
            best_hits = hits
            best_cat = cat
    if best_cat and best_hits >= 1:
        return best_cat
    return TOPIC_MAP.get(topic, "tech")


def _compute_quality(topic: str, category: str, topic_default: str,
                     position: int, author: str) -> float:
    """Quality score (0–1) based on topic prominence + position + specificity."""
    base = TOPIC_PROMINENCE.get(topic, 0.42)
    position_factor = 1.0 / (1.0 + 0.05 * position)
    score = base * position_factor
    # Boost for specific keyword-detected category
    if category != topic_default:
        score = min(1.0, score + 0.08)
    # Bylined articles get a boost
    if author:
        score = min(1.0, score + 0.05)
    return round(min(1.0, score), 3)


class InfoQSource(BaseSource):
    """Fetch enterprise software engineering articles from InfoQ RSS feeds.

    Parameters
    ----------
    feeds : list of dict or None
        Custom feed list (overrides defaults).
    limit : int
        Max articles per feed. Default 20.
    topics : list of str or None
        Topic filter — only fetch these topics.
    min_quality : float
        Minimum quality score (0–1). Default 0.0.
    category_filter : list of str or None
        Only include articles in these categories.
    global_limit : int or None
        Max total articles (quality-sorted). None = no limit.
    """

    name = "infoq"

    def __init__(
        self,
        feeds: Optional[List[dict]] = None,
        limit: int = 20,
        topics: Optional[List[str]] = None,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        global_limit: Optional[int] = None,
    ):
        self.feeds = feeds or INFOQ_FEEDS
        self.limit = limit
        self.min_quality = min_quality
        self.category_filter = [c.lower() for c in category_filter] if category_filter else None
        self.global_limit = global_limit
        if topics:
            topic_set = set(t.lower() for t in topics)
            self.feeds = [f for f in self.feeds if f["topic"] in topic_set]

    def _parse_feed(self, feed_url: str, topic: str, seen_urls: Set[str]) -> List[Article]:
        xml = self.fetch_url(feed_url)
        if not xml:
            return []

        articles: List[Article] = []
        items = _ITEM_RE.findall(xml)
        topic_default = TOPIC_MAP.get(topic, "tech")

        for position, item_xml in enumerate(items[:self.limit]):
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

                rss_categories = _extract_all(_TAG_RE["category"], item_xml)
                author = _extract(_TAG_RE["author"], item_xml)

                category = _detect_category(title, summary, topic)

                # Quality scoring
                quality = _compute_quality(topic, category, topic_default, position, author)

                # Build rich summary
                parts = []
                if author:
                    parts.append(f"✍️ {author}")
                parts.append(f"📰 {topic.title()}")
                if summary:
                    parts.append(summary)
                rich_summary = " · ".join(parts[:2])
                if summary:
                    rich_summary += f" — {summary}"

                # Provenance tags
                tags = [f"infoq:topic:{topic}", f"infoq:category:{category}"]
                if author:
                    tags.append(f"infoq:author:{author.lower()}")
                for rc in rss_categories[:5]:
                    tags.append(f"infoq:tag:{rc.lower()}")

                source_label = f"InfoQ ({topic})" if topic != "all" else "InfoQ"

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=source_label,
                        summary=rich_summary,
                        timestamp=ts,
                        category=category,
                        tags=tags,
                        author=author if author else None,
                        quality_score=quality,
                    )
                )
            except Exception as e:
                logger.debug(f"[InfoQ] Skipping item: {e}")
                continue

        return articles

    def crawl(self) -> List[Article]:
        all_articles: List[Article] = []
        seen_urls: Set[str] = set()

        for feed in self.feeds:
            try:
                articles = self._parse_feed(feed["url"], feed["topic"], seen_urls)
                all_articles.extend(articles)
                logger.info(f"[InfoQ] {feed['topic']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[InfoQ] Failed to fetch {feed['topic']}: {e}")

        # Apply quality filter
        if self.min_quality > 0:
            all_articles = [a for a in all_articles if (a.quality_score or 0) >= self.min_quality]

        if self.category_filter:
            all_articles = [a for a in all_articles if a.category in self.category_filter]

        # Sort by quality descending
        all_articles.sort(key=lambda a: a.quality_score or 0, reverse=True)

        # Global limit
        if self.global_limit:
            all_articles = all_articles[:self.global_limit]

        logger.info(f"[InfoQ] Total: {len(all_articles)} articles from {len(self.feeds)} topic feeds")
        return all_articles
