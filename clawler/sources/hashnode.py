"""Hashnode source — developer blog posts from hashnode.com (no key needed).

Enhanced features:
- Quality scoring (0–1) based on feed prominence, tag richness, title signals
- Expanded feeds and keyword categories
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List

import feedparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

HASHNODE_FEEDS = [
    ("https://hashnode.com/feed", "Hashnode Featured", 0.25),
    ("https://hashnode.com/n/javascript/rss", "Hashnode JavaScript", 0.18),
    ("https://hashnode.com/n/python/rss", "Hashnode Python", 0.18),
    ("https://hashnode.com/n/web-development/rss", "Hashnode Web Dev", 0.18),
    ("https://hashnode.com/n/devops/rss", "Hashnode DevOps", 0.18),
    ("https://hashnode.com/n/ai/rss", "Hashnode AI", 0.22),
    ("https://hashnode.com/n/react/rss", "Hashnode React", 0.15),
    ("https://hashnode.com/n/cloud/rss", "Hashnode Cloud", 0.15),
]

# Tag mappings from Hashnode topic slugs
_TOPIC_TAGS = {
    "javascript": ["hashnode:javascript", "hashnode:webdev"],
    "python": ["hashnode:python"],
    "web-development": ["hashnode:webdev"],
    "devops": ["hashnode:devops", "hashnode:infrastructure"],
    "ai": ["hashnode:ai", "hashnode:ml"],
    "react": ["hashnode:react", "hashnode:frontend"],
    "cloud": ["hashnode:cloud", "hashnode:infrastructure"],
}

# Keyword categories for enhanced category detection
KEYWORD_CATEGORIES: Dict[str, List[str]] = {
    "ai": ["machine learning", "deep learning", "neural", "llm", "gpt", "transformer",
           "artificial intelligence", "nlp", "generative ai"],
    "security": ["vulnerability", "authentication", "encryption", "oauth", "xss", "csrf",
                 "security", "penetration testing"],
}

_QUALITY_TITLE_SIGNALS = [
    "guide", "tutorial", "how to", "step-by-step", "complete",
    "best practices", "deep dive", "explained", "from scratch",
    "architecture", "production", "scalable", "performance",
]


def _compute_quality(title: str, tags: list, author: str, feed_prominence: float) -> float:
    """Compute quality score (0–1) for a Hashnode article."""
    q = feed_prominence
    title_lower = title.lower()

    signal_hits = sum(1 for s in _QUALITY_TITLE_SIGNALS if s in title_lower)
    q += min(0.25, signal_hits * 0.08)
    q += min(0.20, len(tags) * 0.03)
    if author:
        q += 0.05
    if len(title) > 50:
        q += 0.05

    return min(1.0, max(0.0, round(q, 3)))


class HashnodeSource(BaseSource):
    """Fetch latest developer blog posts from Hashnode RSS feeds."""

    name = "hashnode"

    def __init__(self, limit: int = 30):
        self.limit = limit

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        seen_urls: set = set()

        for feed_url, feed_name, feed_prominence in HASHNODE_FEEDS:
            try:
                raw = self.fetch_url(feed_url)
                if not raw:
                    continue
                feed = feedparser.parse(raw)
            except Exception as e:
                logger.warning(f"[Hashnode] Failed to fetch {feed_name}: {e}")
                continue

            for entry in feed.entries[:self.limit]:
                try:
                    url = (entry.get("link") or "").strip()
                    title = (entry.get("title") or "").strip()
                    if not url or not title or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    # Parse timestamp
                    ts = None
                    for ts_field in ("published_parsed", "updated_parsed"):
                        parsed = entry.get(ts_field)
                        if parsed:
                            try:
                                ts = datetime(*parsed[:6], tzinfo=timezone.utc)
                            except (ValueError, TypeError):
                                pass
                            break

                    author = (entry.get("author") or "").strip()
                    summary = (entry.get("summary") or "").strip()
                    if len(summary) > 300:
                        summary = summary[:297] + "..."

                    # Determine tags from the feed topic
                    tags = ["hashnode:devblog"]
                    for topic_slug, topic_tags in _TOPIC_TAGS.items():
                        if topic_slug in feed_url:
                            tags.extend(topic_tags)
                            break

                    # Extract entry tags/categories if present
                    for tag_obj in entry.get("tags", []):
                        term = (tag_obj.get("term") or "").strip().lower()
                        if term:
                            tags.append(f"hashnode:{term}")

                    # Override category from keyword detection
                    text_lower = f"{title} {summary}".lower()
                    for kw_cat, keywords in KEYWORD_CATEGORIES.items():
                        if any(kw in text_lower for kw in keywords):
                            category = kw_cat
                            break
                    else:
                        category = "tech"

                    quality = _compute_quality(title, tags, author, feed_prominence)

                    articles.append(
                        Article(
                            title=title,
                            url=url,
                            source=feed_name,
                            summary=summary,
                            timestamp=ts,
                            category=category,
                            tags=tags[:10],  # cap tags
                            author=author,
                            quality_score=quality,
                        )
                    )
                except Exception as e:
                    logger.debug(f"[Hashnode] Skipping entry: {e}")
                    continue

        # Deduplicate and limit
        articles = articles[:self.limit]
        logger.info(f"[Hashnode] Fetched {len(articles)} posts from {len(HASHNODE_FEEDS)} feeds")
        return articles
