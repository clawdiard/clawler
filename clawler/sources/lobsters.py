"""Lobsters source — uses the free lobste.rs JSON API (no key needed).

Supports multiple feed pages (hottest, newest, active) with deduplication,
min_score filtering, tag-based filtering, quality scoring, domain extraction,
and rich category mapping from lobste.rs tags.
"""
import logging
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

LOBSTERS_FEEDS: Dict[str, str] = {
    "hottest": "https://lobste.rs/hottest.json",
    "newest": "https://lobste.rs/newest.json",
    "active": "https://lobste.rs/active.json",
}

# Tag → category mapping with specificity tiers.
# Specific categories are preferred over generic "tech".
_SPECIFIC_TAG_MAP: Dict[str, str] = {
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
    # AI / ML
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
    # Design
    "css": "design",
    "design": "design",
    # Gaming
    "games": "gaming",
    "graphics": "gaming",
    # Education
    "education": "education",
}

_GENERIC_TAG_MAP: Dict[str, str] = {
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
    "typescript": "tech",
    "ocaml": "tech",
    "clojure": "tech",
    "scala": "tech",
    "kotlin": "tech",
    "nim": "tech",
    "wasm": "tech",
    # Web & Infra
    "web": "tech",
    "browsers": "tech",
    "api": "tech",
    "compsci": "tech",
    "plt": "tech",
    "testing": "tech",
    "debugging": "tech",
    "performance": "tech",
    "compilers": "tech",
    "virtualization": "tech",
}


class LobstersSource(BaseSource):
    """Fetch stories from lobste.rs with multi-feed, filtering, quality scoring,
    tag filtering, and domain extraction support."""

    name = "lobsters"

    def __init__(
        self,
        limit: int = 25,
        page: str = "hottest",
        feeds: Optional[List[str]] = None,
        min_score: int = 0,
        min_comments: int = 0,
        include_comments_url: bool = True,
        filter_tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        include_domain: bool = True,
    ):
        """
        Args:
            limit: Max stories per feed page.
            page: Single feed page (legacy compat). Ignored if ``feeds`` is set.
            feeds: List of feed pages to fetch (hottest, newest, active).
                   Fetches all three by default when explicitly set to ``None``.
            min_score: Skip stories below this score.
            min_comments: Skip stories below this comment count.
            include_comments_url: Include lobste.rs discussion link in summary.
            filter_tags: Only include stories with at least one of these tags.
            exclude_tags: Exclude stories that have any of these tags.
            include_domain: Extract and display the link domain in summary.
        """
        self.limit = limit
        self.min_score = min_score
        self.min_comments = min_comments
        self.include_comments_url = include_comments_url
        self.filter_tags = set(t.lower() for t in filter_tags) if filter_tags else None
        self.exclude_tags = set(t.lower() for t in exclude_tags) if exclude_tags else None
        self.include_domain = include_domain

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
        if comment_count < self.min_comments:
            return None

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
        tags_lower = [t.lower() for t in tags_raw]

        # Tag filtering
        if self.filter_tags and not self.filter_tags.intersection(tags_lower):
            return None
        if self.exclude_tags and self.exclude_tags.intersection(tags_lower):
            return None

        category = _map_category(tags_raw)

        # Timestamp
        ts = _parse_timestamp(item.get("created_at"))

        # Domain extraction
        domain = _extract_domain(url)

        # Quality score: logarithmic scaling of score + comment engagement
        quality = _compute_quality(score, comment_count)

        # Build rich summary
        parts = [f"↑{score}"]
        if author_name:
            parts.append(f"by {author_name}")
        parts.append(f"💬{comment_count}")
        if self.include_domain and domain and "lobste.rs" not in domain:
            parts.append(f"🔗{domain}")
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
            quality_score=quality,
            tags=[f"lobsters:{t}" for t in tags_raw]
            + [f"lobsters-feed:{feed_name}"]
            + ([f"lobsters-domain:{domain}"] if domain else []),
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


def _extract_domain(url: str) -> str:
    """Extract a clean domain from a URL."""
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _compute_quality(score: int, comment_count: int) -> float:
    """Compute a 0-1 quality score from upvotes and comment engagement.

    Uses logarithmic scaling so a story with score=50, comments=20 ≈ 0.9,
    while score=1, comments=0 ≈ 0.3.
    """
    # Log-scaled score component (0-1 range, score 100 → ~1.0)
    score_component = min(1.0, math.log1p(max(0, score)) / math.log1p(100))
    # Comment engagement boost (0-0.2 range)
    comment_boost = min(0.2, math.log1p(comment_count) / math.log1p(50) * 0.2)
    # Base quality for appearing on lobste.rs at all
    base = 0.3
    return min(1.0, base + score_component * 0.5 + comment_boost)


def _map_category(tags: List[str]) -> str:
    """Map lobste.rs tags to Clawler categories, preferring specific over generic."""
    # First pass: look for specific categories
    for tag in tags:
        tag_lower = tag.lower()
        if tag_lower in _SPECIFIC_TAG_MAP:
            return _SPECIFIC_TAG_MAP[tag_lower]
    # Second pass: fall back to generic tech categories
    for tag in tags:
        tag_lower = tag.lower()
        if tag_lower in _GENERIC_TAG_MAP:
            return _GENERIC_TAG_MAP[tag_lower]
    return "tech"
