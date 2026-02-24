"""Changelog source — fetches articles from changelog.com (developer news/podcasts, no key needed).

Enhanced features:
- Quality scoring (0–1) based on feed prominence, tag richness, title signals
- Keyword-based category detection
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

CHANGELOG_FEEDS = [
    ("https://changelog.com/feed", "Changelog", 0.20),
    ("https://changelog.com/news/feed", "Changelog News", 0.25),
]

TAG_CATEGORY_MAP = {
    "open-source": "tech",
    "go": "tech",
    "rust": "tech",
    "elixir": "tech",
    "python": "tech",
    "javascript": "tech",
    "ruby": "tech",
    "kubernetes": "tech",
    "docker": "tech",
    "devops": "tech",
    "infrastructure": "tech",
    "ai": "tech",
    "machine-learning": "tech",
    "security": "security",
    "privacy": "security",
    "career": "business",
    "hiring": "business",
    "startup": "business",
    "linux": "tech",
    "database": "tech",
    "web": "tech",
    "frontend": "tech",
    "backend": "tech",
    "cloud": "tech",
}


_QUALITY_TITLE_SIGNALS = [
    "open source", "release", "new in", "major", "announcement",
    "deep dive", "interview", "why", "how", "future of",
]


def _compute_quality(title: str, tags: list, author: str, feed_prominence: float) -> float:
    """Compute quality score (0–1) for a Changelog article."""
    q = feed_prominence
    title_lower = title.lower()

    signal_hits = sum(1 for s in _QUALITY_TITLE_SIGNALS if s in title_lower)
    q += min(0.25, signal_hits * 0.08)
    q += min(0.20, len(tags) * 0.04)
    if author:
        q += 0.05
    if len(title) > 50:
        q += 0.05

    return min(1.0, max(0.0, round(q, 3)))


class ChangelogSource(BaseSource):
    """Fetches recent articles from changelog.com via RSS feeds."""

    name = "changelog"
    timeout = 20

    def __init__(self, limit: int = 30):
        self.limit = limit

    def crawl(self) -> List[Article]:
        import feedparser

        articles: List[Article] = []
        seen_urls: set = set()

        for feed_url, feed_label, feed_prominence in CHANGELOG_FEEDS:
            text = self.fetch_url(feed_url)
            if not text:
                logger.warning(f"[Changelog] Failed to fetch {feed_label} feed")
                continue

            feed = feedparser.parse(text)
            if not feed.entries:
                logger.warning(f"[Changelog] No entries in {feed_label} feed")
                continue

            for entry in feed.entries[: self.limit]:
                title = (entry.get("title") or "").strip()
                url = entry.get("link", "")
                if not title or not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                # Parse timestamp
                timestamp = None
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    try:
                        timestamp = datetime(*published[:6], tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

                # Extract tags
                tags = []
                for tag_entry in entry.get("tags", []):
                    term = (tag_entry.get("term") or "").strip().lower()
                    if term:
                        tags.append(term)

                # Determine category from tags
                category = "tech"  # default for Changelog
                for tag in tags:
                    if tag in TAG_CATEGORY_MAP:
                        category = TAG_CATEGORY_MAP[tag]
                        break

                # Summary — strip HTML
                summary = entry.get("summary", "") or ""
                if "<" in summary:
                    from bs4 import BeautifulSoup
                    summary = BeautifulSoup(summary, "html.parser").get_text(separator=" ")
                summary = summary[:300].strip()

                # Author
                author = ""
                if entry.get("author"):
                    author = entry["author"]
                elif entry.get("authors"):
                    author = entry["authors"][0].get("name", "")

                if author:
                    summary = f"by {author} — {summary}"

                quality = _compute_quality(title, tags, author, feed_prominence)

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=f"Changelog ({feed_label})",
                        summary=summary,
                        timestamp=timestamp,
                        category=category,
                        tags=tags[:5],
                        author=author,
                        quality_score=quality,
                    )
                )

        logger.info(f"[Changelog] Fetched {len(articles)} articles")
        return articles
