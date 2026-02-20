"""EchoJS source — JavaScript/web dev news from echojs.com (no key needed).

Enhanced with keyword-based category detection, quality scoring based on
community engagement, and content type classification.
"""
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

ECHOJS_API = "https://www.echojs.com/api/getnews/latest/0/30"
ECHOJS_TOP_API = "https://www.echojs.com/api/getnews/top/0/30"

# Keyword → category mapping for JS/web dev articles
KEYWORD_CATEGORIES = {
    "react": "tech",
    "vue": "tech",
    "angular": "tech",
    "svelte": "tech",
    "nextjs": "tech",
    "next.js": "tech",
    "nuxt": "tech",
    "node": "tech",
    "deno": "tech",
    "bun": "tech",
    "typescript": "tech",
    "javascript": "tech",
    "css": "tech",
    "html": "tech",
    "webpack": "tech",
    "vite": "tech",
    "tailwind": "tech",
    "wasm": "tech",
    "webassembly": "tech",
    "api": "tech",
    "graphql": "tech",
    "rest": "tech",
    "security": "security",
    "xss": "security",
    "csrf": "security",
    "vulnerability": "security",
    "cve": "security",
    "auth": "security",
    "oauth": "security",
    "startup": "business",
    "funding": "business",
    "acquisition": "business",
    "hiring": "business",
    "career": "business",
    "salary": "business",
    "ai": "tech",
    "machine learning": "tech",
    "llm": "tech",
    "gpt": "tech",
    "copilot": "tech",
    "tutorial": "tech",
    "guide": "tech",
    "benchmark": "tech",
    "performance": "tech",
    "testing": "tech",
    "rust": "tech",
    "go": "tech",
    "python": "tech",
    "open source": "tech",
    "release": "tech",
}

# Quality tiers based on vote score
QUALITY_TIERS = [
    (50, 1.0),   # 50+ votes → top quality
    (20, 0.85),
    (10, 0.7),
    (5, 0.55),
    (0, 0.4),
]


def _classify_category(title: str) -> str:
    """Determine article category from title keywords."""
    lower = title.lower()
    for keyword, category in KEYWORD_CATEGORIES.items():
        if keyword in lower:
            return category
    return "tech"  # default for EchoJS


def _quality_score(upvotes: int, downvotes: int) -> float:
    """Compute quality score from community votes."""
    score = upvotes - downvotes
    for threshold, quality in QUALITY_TIERS:
        if score >= threshold:
            return quality
    return 0.3


def _extract_tags(title: str) -> List[str]:
    """Extract relevant tags from the title."""
    tags = ["echojs:javascript", "echojs:webdev"]
    lower = title.lower()
    tag_keywords = [
        "react", "vue", "angular", "svelte", "node", "deno", "bun",
        "typescript", "css", "wasm", "graphql", "nextjs", "next.js",
        "tailwind", "vite", "webpack", "ai", "rust", "go", "python",
        "testing", "performance", "security", "tutorial",
    ]
    for kw in tag_keywords:
        if kw in lower:
            tags.append(f"echojs:{kw}")
    return tags[:8]


class EchoJSSource(BaseSource):
    """Fetch latest and top stories from EchoJS (JavaScript/web dev community).

    Features:
    - Dual-feed: latest + top stories
    - Keyword-based category classification
    - Quality scoring from community votes
    - Rich tag extraction
    """

    name = "echojs"

    def __init__(self, limit: int = 30, include_top: bool = True):
        self.limit = limit
        self.include_top = include_top

    def _parse_items(self, data: dict, feed_label: str) -> List[Article]:
        """Parse articles from an EchoJS API response."""
        if not data or "news" not in data:
            return []

        articles: List[Article] = []
        for item in data["news"][:self.limit]:
            try:
                title = item.get("title", "").strip()
                url = item.get("url", "").strip()
                if not title or not url:
                    continue

                # Timestamp from atime (unix)
                ts: Optional[datetime] = None
                atime = item.get("atime")
                if atime:
                    try:
                        ts = datetime.fromtimestamp(int(atime), tz=timezone.utc)
                    except (ValueError, TypeError, OSError):
                        pass

                up = int(item.get("up", 0))
                down = int(item.get("down", 0))
                score = up - down
                username = item.get("username", "")
                hn_id = item.get("id", "")
                discussion_url = f"https://www.echojs.com/news/{hn_id}" if hn_id else ""

                quality = _quality_score(up, down)
                category = _classify_category(title)
                tags = _extract_tags(title)

                summary_parts = [f"Score: {score} (quality: {quality:.0%})"]
                if username:
                    summary_parts.append(f"By: {username}")
                if discussion_url:
                    summary_parts.append(f"Discussion: {discussion_url}")

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=f"EchoJS {feed_label} (↑{score})",
                        summary=" | ".join(summary_parts),
                        timestamp=ts,
                        category=category,
                        tags=tags,
                        author=username,
                        discussion_url=discussion_url,
                    )
                )
            except Exception as e:
                logger.debug(f"[EchoJS] Skipping item: {e}")
                continue
        return articles

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        seen_urls: set = set()

        # Fetch latest
        try:
            data = self.fetch_json(ECHOJS_API)
            for a in self._parse_items(data, "Latest"):
                if a.url not in seen_urls:
                    seen_urls.add(a.url)
                    articles.append(a)
        except Exception as e:
            logger.warning(f"[EchoJS] Failed to fetch latest: {e}")

        # Fetch top
        if self.include_top:
            try:
                data = self.fetch_json(ECHOJS_TOP_API)
                for a in self._parse_items(data, "Top"):
                    if a.url not in seen_urls:
                        seen_urls.add(a.url)
                        articles.append(a)
            except Exception as e:
                logger.warning(f"[EchoJS] Failed to fetch top: {e}")

        logger.info(f"[EchoJS] Fetched {len(articles)} stories")
        return articles
