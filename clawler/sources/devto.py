"""Dev.to source — uses public API (no API key needed)."""
import logging
from datetime import datetime, timezone
from typing import List, Optional
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Map dev.to tags to clawler categories
TAG_CATEGORY_MAP = {
    "python": "tech",
    "javascript": "tech",
    "webdev": "tech",
    "programming": "tech",
    "devops": "tech",
    "rust": "tech",
    "go": "tech",
    "typescript": "tech",
    "react": "tech",
    "node": "tech",
    "ai": "tech",
    "machinelearning": "tech",
    "security": "security",
    "cybersecurity": "security",
    "opensource": "tech",
    "career": "business",
    "productivity": "business",
    "beginners": "tech",
    "tutorial": "tech",
    "discuss": "culture",
    "news": "world",
    "science": "science",
}


class DevToSource(BaseSource):
    """Fetches top articles from dev.to public API."""

    name = "dev.to"

    def __init__(self, per_page: int = 30, top: Optional[int] = None):
        self.per_page = per_page
        self.top = top  # top N by reaction count (published in last N days)

    def crawl(self) -> List[Article]:
        url = "https://dev.to/api/articles"
        params = {"per_page": str(self.per_page)}
        if self.top:
            params["top"] = str(self.top)

        try:
            data = self.fetch_json(f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}")
        except Exception as e:
            logger.warning(f"[Dev.to] Failed to fetch articles: {e}")
            return []

        if not data or not isinstance(data, list):
            logger.warning("[Dev.to] Unexpected response format")
            return []

        articles: List[Article] = []
        for item in data:
            title = (item.get("title") or "").strip()
            article_url = item.get("url", "")
            if not title or not article_url:
                continue

            description = item.get("description", "") or ""
            tags_str = item.get("tag_list") or []
            if isinstance(tags_str, str):
                tags_str = [t.strip() for t in tags_str.split(",") if t.strip()]

            # Determine category from tags
            category = "tech"  # default for dev.to
            for tag in tags_str:
                tag_lower = tag.lower()
                if tag_lower in TAG_CATEGORY_MAP:
                    category = TAG_CATEGORY_MAP[tag_lower]
                    break

            published = item.get("published_at")
            timestamp = None
            if published:
                try:
                    timestamp = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            user = item.get("user", {})
            author = user.get("name") or user.get("username") or ""
            reactions = item.get("positive_reactions_count", 0)

            summary = description[:300]
            if author:
                summary = f"by {author} — {summary}"
            if reactions:
                summary = f"♥{reactions} | {summary}"

            articles.append(Article(
                title=title,
                url=article_url,
                source="dev.to",
                summary=summary[:300],
                timestamp=timestamp,
                category=category,
                tags=tags_str[:5] if tags_str else [],
                author=author,
            ))

        logger.info(f"[Dev.to] Fetched {len(articles)} articles")
        return articles
