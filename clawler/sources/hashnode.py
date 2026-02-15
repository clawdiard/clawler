"""Hashnode source — developer blog posts from hashnode.com (no key needed)."""
import logging
from datetime import datetime, timezone
from typing import List

import feedparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

HASHNODE_FEEDS = [
    ("https://hashnode.com/feed", "Hashnode Featured"),
    ("https://hashnode.com/n/javascript/rss", "Hashnode JavaScript"),
    ("https://hashnode.com/n/python/rss", "Hashnode Python"),
    ("https://hashnode.com/n/web-development/rss", "Hashnode Web Dev"),
    ("https://hashnode.com/n/devops/rss", "Hashnode DevOps"),
    ("https://hashnode.com/n/ai/rss", "Hashnode AI"),
]

# Tag mappings from Hashnode topic slugs
_TOPIC_TAGS = {
    "javascript": ["hashnode:javascript", "hashnode:webdev"],
    "python": ["hashnode:python"],
    "web-development": ["hashnode:webdev"],
    "devops": ["hashnode:devops", "hashnode:infrastructure"],
    "ai": ["hashnode:ai", "hashnode:ml"],
}


class HashnodeSource(BaseSource):
    """Fetch latest developer blog posts from Hashnode RSS feeds."""

    name = "hashnode"

    def __init__(self, limit: int = 30):
        self.limit = limit

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        seen_urls: set = set()

        for feed_url, feed_name in HASHNODE_FEEDS:
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

                    articles.append(
                        Article(
                            title=title,
                            url=url,
                            source=feed_name,
                            summary=summary,
                            timestamp=ts,
                            category="tech",
                            tags=tags[:10],  # cap tags
                            author=author,
                        )
                    )
                except Exception as e:
                    logger.debug(f"[Hashnode] Skipping entry: {e}")
                    continue

        # Deduplicate and limit
        articles = articles[:self.limit]
        logger.info(f"[Hashnode] Fetched {len(articles)} posts from {len(HASHNODE_FEEDS)} feeds")
        return articles
