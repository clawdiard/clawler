"""freeCodeCamp source — fetches articles from freeCodeCamp's public RSS/API (no key needed)."""
import logging
from datetime import datetime, timezone
from typing import List
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# freeCodeCamp publishes a JSON feed at their Ghost API endpoint
FCC_API = "https://www.freecodecamp.org/news/ghost/api/content/posts/"
FCC_RSS = "https://www.freecodecamp.org/news/rss/"

TAG_CATEGORY_MAP = {
    "python": "tech",
    "javascript": "tech",
    "web-development": "tech",
    "programming": "tech",
    "linux": "tech",
    "html": "tech",
    "css": "tech",
    "react": "tech",
    "nodejs": "tech",
    "typescript": "tech",
    "machine-learning": "tech",
    "artificial-intelligence": "tech",
    "data-science": "science",
    "career": "business",
    "tutorial": "tech",
    "security": "security",
    "devops": "tech",
    "cloud": "tech",
    "database": "tech",
}


class FreeCodeCampSource(BaseSource):
    """Fetches recent articles from freeCodeCamp via RSS feed."""

    name = "freecodecamp"
    timeout = 20

    def __init__(self, limit: int = 25):
        self.limit = limit

    def crawl(self) -> List[Article]:
        import feedparser

        text = self.fetch_url(FCC_RSS)
        if not text:
            logger.warning("[freeCodeCamp] Failed to fetch RSS feed")
            return []

        feed = feedparser.parse(text)
        if not feed.entries:
            logger.warning("[freeCodeCamp] No entries in RSS feed")
            return []

        articles: List[Article] = []
        for entry in feed.entries[: self.limit]:
            title = (entry.get("title") or "").strip()
            url = entry.get("link", "")
            if not title or not url:
                continue

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
            category = "tech"  # default for freeCodeCamp
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

            articles.append(
                Article(
                    title=title,
                    url=url,
                    source="freeCodeCamp",
                    summary=summary,
                    timestamp=timestamp,
                    category=category,
                    tags=tags[:5],
                    author=author,
                )
            )

        logger.info(f"[freeCodeCamp] Fetched {len(articles)} articles")
        return articles
