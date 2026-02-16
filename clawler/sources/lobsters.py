"""Lobsters source — uses the free lobste.rs JSON API (no key needed).

Supports multiple feed pages (hottest, newest, active) with deduplication,
min_score filtering, and rich category mapping from lobste.rs tags.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

LOBSTERS_FEEDS: Dict[str, str] = {
    "hottest": "https://lobste.rs/hottest.json",
    "newest": "https://lobste.rs/newest.json",
    "active": "https://lobste.rs/active.json",
}

# Comprehensive tag → category mapping for lobste.rs
TAG_CATEGORY_MAP: Dict[str, str] = {
    # Security & Privacy
    "security": "security",
    "privacy": "security",
    "netsec": "security",
    "crypto": "security",
    # Science & Research
    "science": "science",
    "math": "science",
    "formalmethods": "science",
    "cogsci": "science",
    "ai": "ai",
    "ml": "ai",
    # Culture & Society
    "culture": "culture",
    "law": "culture",
    "person": "culture",
    "interviews": "culture",
    "ask": "culture",
    "announce": "culture",
    "meta": "culture",
    # Business & Practices
    "practices": "business",
    "devops": "business",
    "scaling": "business",
    "job": "business",
    # Systems & Low-level
    "linux": "tech",
    "unix": "tech",
    "freebsd": "tech",
    "openbsd": "tech",
    "networking": "tech",
    "distributed": "tech",
    "databases": "tech",
    "osdev": "tech",
    "hardware": "tech",
    "reversing": "tech",
    "emulation": "tech",
    # Programming Languages
    "python": "tech",
    "rust": "tech",
    "go": "tech",
    "c": "tech",
    "c++": "tech",
    "java": "tech",
    "haskell": "tech",
    "lisp": "tech",
    "elixir": "tech",
    "erlang": "tech",
    "ruby": "tech",
    "javascript": "tech",
    "swift": "tech",
    "zig": "tech",
    # Web & Design
    "web": "tech",
    "browsers": "tech",
    "css": "design",
    "design": "design",
    # Gaming
    "games": "gaming",
    "graphics": "gaming",
}


class LobstersSource(BaseSource):
    """Fetch stories from lobste.rs with multi-feed and filtering support."""

    name = "lobsters"

    def __init__(
        self,
        limit: int = 25,
        page: str = "hottest",
        feeds: Optional[List[str]] = None,
        min_score: int = 0,
        include_comments_url: bool = True,
    ):
        """
        Args:
            limit: Max stories per feed page.
            page: Single feed page (legacy compat). Ignored if ``feeds`` is set.
            feeds: List of feed pages to fetch (hottest, newest, active).
                   Fetches all three by default when explicitly set to ``None``.
            min_score: Skip stories below this score.
            include_comments_url: Include lobste.rs discussion link in summary.
        """
        self.limit = limit
        self.min_score = min_score
        self.include_comments_url = include_comments_url

        # Determine which feeds to crawl
        if feeds is not None:
            self._feeds = [f for f in feeds if f in LOBSTERS_FEEDS]
        else:
            # Legacy: single page mode for backward compat
            self._feeds = [page if page in LOBSTERS_FEEDS else "hottest"]

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()
        articles: List[Article] = []

        for feed_name in self._feeds:
            url = LOBSTERS_FEEDS[feed_name]
            try:
                data = self.fetch_json(url)
                if not data or not isinstance(data, list):
                    continue
            except Exception as e:
                logger.warning(f"[Lobsters] Failed to fetch {feed_name}: {e}")
                continue

            for item in data[: self.limit]:
                try:
                    article = self._parse_item(item, feed_name, seen_urls)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.debug(f"[Lobsters] Skipping item: {e}")

        logger.info(f"[Lobsters] Fetched {len(articles)} stories from {len(self._feeds)} feed(s)")
        return articles

    def _parse_item(
        self, item: dict, feed_name: str, seen: Set[str]
    ) -> Optional[Article]:
        title = (item.get("title") or "").strip()
        url = item.get("url") or item.get("comments_url", "")
        if not title or not url:
            return None

        # Dedup across feeds
        if url in seen:
            return None
        seen.add(url)

        score = item.get("score", 0)
        if score < self.min_score:
            return None

        comment_count = item.get("comment_count", 0)
        comments_url = item.get("comments_url", "")
        short_id = item.get("short_id", "")

        # Author
        author_field = item.get("submitter_user", {})
        if isinstance(author_field, dict):
            author_name = author_field.get("username", "")
        else:
            author_name = str(author_field)

        # Tags
        tags_raw = [t for t in item.get("tags", []) if isinstance(t, str)]
        category = _map_category(tags_raw)

        # Timestamp
        ts = _parse_timestamp(item.get("created_at"))

        # Build rich summary
        parts = [f"↑{score}"]
        if author_name:
            parts.append(f"by {author_name}")
        parts.append(f"💬{comment_count}")
        if tags_raw:
            parts.append(f"[{', '.join(tags_raw)}]")
        if self.include_comments_url and comments_url:
            parts.append(f"Discussion: {comments_url}")

        return Article(
            title=title,
            url=url,
            source=f"Lobsters ({feed_name})",
            summary=" | ".join(parts),
            timestamp=ts,
            category=category,
            tags=[f"lobsters:{t}" for t in tags_raw] + [f"lobsters-feed:{feed_name}"],
            discussion_url=comments_url,
            author=author_name,
        )


def _parse_timestamp(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except (ValueError, AttributeError):
        return None


def _map_category(tags: List[str]) -> str:
    """Map lobste.rs tags to Clawler categories using comprehensive mapping."""
    for tag in tags:
        tag_lower = tag.lower()
        if tag_lower in TAG_CATEGORY_MAP:
            return TAG_CATEGORY_MAP[tag_lower]
    # Default: tech (lobste.rs is primarily a tech site)
    return "tech"
