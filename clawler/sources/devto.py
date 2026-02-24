"""Dev.to source — uses public API (no API key needed).

Supports multiple feed endpoints (published, top, rising, latest, videos),
tag filtering, reading time metadata, comment counts, and rich category mapping.

Enhanced features:
- Quality scoring (0–1) based on reactions, comments, reading time, feed prominence
- Filters: min_quality, category_filter
- Quality-sorted output
"""
import logging
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Comprehensive tag → category mapping
TAG_CATEGORY_MAP: Dict[str, str] = {
    # AI & ML
    "ai": "ai",
    "machinelearning": "ai",
    "deeplearning": "ai",
    "nlp": "ai",
    "datascience": "ai",
    "openai": "ai",
    "llm": "ai",
    "gpt": "ai",
    "chatgpt": "ai",
    "copilot": "ai",
    # Security
    "security": "security",
    "cybersecurity": "security",
    "infosec": "security",
    "hacking": "security",
    "privacy": "security",
    "encryption": "security",
    # Science
    "science": "science",
    "math": "science",
    "physics": "science",
    "biology": "science",
    # Business & Career
    "career": "business",
    "productivity": "business",
    "management": "business",
    "startup": "business",
    "entrepreneur": "business",
    "business": "business",
    "hiring": "business",
    "leadership": "business",
    "remote": "business",
    # Design
    "design": "design",
    "ux": "design",
    "ui": "design",
    "css": "design",
    "accessibility": "design",
    "figma": "design",
    "tailwindcss": "design",
    # DevOps & Cloud
    "devops": "tech",
    "docker": "tech",
    "kubernetes": "tech",
    "aws": "tech",
    "azure": "tech",
    "gcp": "tech",
    "cloud": "tech",
    "linux": "tech",
    "serverless": "tech",
    "cicd": "tech",
    # Web
    "webdev": "tech",
    "javascript": "tech",
    "typescript": "tech",
    "react": "tech",
    "vue": "tech",
    "angular": "tech",
    "svelte": "tech",
    "nextjs": "tech",
    "node": "tech",
    "deno": "tech",
    # Programming
    "programming": "tech",
    "python": "tech",
    "rust": "tech",
    "go": "tech",
    "java": "tech",
    "csharp": "tech",
    "ruby": "tech",
    "swift": "tech",
    "kotlin": "tech",
    "elixir": "tech",
    "haskell": "tech",
    "php": "tech",
    # Mobile
    "android": "tech",
    "ios": "tech",
    "flutter": "tech",
    "reactnative": "tech",
    "mobile": "tech",
    # Blockchain
    "blockchain": "crypto",
    "crypto": "crypto",
    "web3": "crypto",
    "ethereum": "crypto",
    "solidity": "crypto",
    "nft": "crypto",
    # Culture & Community
    "discuss": "culture",
    "watercooler": "culture",
    "news": "world",
    "opensource": "tech",
    "beginners": "tech",
    "tutorial": "tech",
    "showdev": "tech",
    "codenewbie": "tech",
    "testing": "tech",
    "database": "tech",
    "api": "tech",
    "git": "tech",
    "algorithms": "tech",
    # Gaming
    "gamedev": "gaming",
    "gaming": "gaming",
    "unity": "gaming",
    "godot": "gaming",
}

# Feed prominence — editorial signal value
FEED_PROMINENCE: Dict[str, float] = {
    "published": 0.15,
    "rising": 0.25,
    "latest": 0.10,
    "videos": 0.12,
}

# Prominent Dev.to authors (well-known tech writers)
PROMINENT_AUTHORS: Dict[str, float] = {
    "ben": 0.10,          # Ben Halpern (founder)
    "jess": 0.08,         # Jess Lee (co-founder)
    "lydiahallie": 0.08,  # Lydia Hallie
    "aspittel": 0.08,     # Ali Spittel
    "cassidoo": 0.06,     # Cassidy Williams
    "swyx": 0.06,         # Shawn Wang
    "dabit3": 0.06,       # Nader Dabit
    "nickytonline": 0.06, # Nick Taylor
    "devteam": 0.05,      # Dev.to team
    "coffeecraftcode": 0.05,
    "therealdanvega": 0.05,
}


def _compute_quality(reactions: int, comments: int, reading_time: int,
                     feed_name: str, author: str) -> float:
    """Compute quality score (0–1) for a Dev.to article."""
    q = 0.0

    # Feed prominence (0–0.25)
    q += FEED_PROMINENCE.get(feed_name, 0.15)

    # Reaction score (0–0.35) — log-scaled
    if reactions > 0:
        q += min(0.35, 0.10 * math.log10(reactions + 1))

    # Comment engagement (0–0.15)
    if comments > 0:
        q += min(0.15, 0.05 * math.log10(comments + 1))

    # Reading time bonus — longer = more substantial (0–0.10)
    if reading_time >= 8:
        q += 0.10
    elif reading_time >= 4:
        q += 0.06
    elif reading_time >= 2:
        q += 0.03

    # Author prominence (0–0.10)
    author_lower = author.lower() if author else ""
    q += PROMINENT_AUTHORS.get(author_lower, 0.0)

    return min(1.0, round(q, 3))


# Dev.to API endpoints
DEVTO_FEEDS: Dict[str, str] = {
    "published": "https://dev.to/api/articles",
    "rising": "https://dev.to/api/articles?state=rising",
    "latest": "https://dev.to/api/articles/latest",
    "videos": "https://dev.to/api/videos",
}


class DevToSource(BaseSource):
    """Fetches articles from dev.to public API with multi-feed and filtering."""

    name = "dev.to"

    def __init__(
        self,
        per_page: int = 30,
        top: Optional[int] = None,
        feeds: Optional[List[str]] = None,
        tag: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_reactions: int = 0,
        min_reading_time: int = 0,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        include_reading_time: bool = True,
        include_comments: bool = True,
    ):
        """
        Args:
            per_page: Articles per feed request (max 100).
            top: Fetch top articles from the last N days.
            feeds: Feed endpoints to crawl. Default: ["published"].
                   Options: published, rising, latest, videos.
            tag: Single tag filter (API-level filtering).
            tags: Multiple tags to fetch separately (one API call per tag).
            min_reactions: Skip articles below this reaction count.
            min_reading_time: Skip articles below this reading time (minutes).
            include_reading_time: Show reading time in summary.
            include_comments: Show comment count in summary.
        """
        self.per_page = min(per_page, 100)
        self.top = top
        self.tag = tag
        self.tags = tags
        self.min_reactions = min_reactions
        self.min_reading_time = min_reading_time
        self.min_quality = min_quality
        self.category_filter = category_filter
        self.include_reading_time = include_reading_time
        self.include_comments = include_comments

        if feeds is not None:
            self._feeds = [f for f in feeds if f in DEVTO_FEEDS]
        else:
            self._feeds = ["published"]

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()
        articles: List[Article] = []

        # If multiple tags requested, fetch each tag separately
        if self.tags:
            for tag in self.tags:
                self._fetch_feed("published", seen_urls, articles, tag_filter=tag)
        else:
            for feed_name in self._feeds:
                self._fetch_feed(feed_name, seen_urls, articles, tag_filter=self.tag)

        logger.info(f"[Dev.to] Fetched {len(articles)} articles")
        # Sort by quality descending
        articles.sort(key=lambda a: a.quality_score or 0, reverse=True)
        return articles

    def _fetch_feed(
        self,
        feed_name: str,
        seen: Set[str],
        articles: List[Article],
        tag_filter: Optional[str] = None,
    ) -> None:
        base_url = DEVTO_FEEDS.get(feed_name, DEVTO_FEEDS["published"])
        sep = "&" if "?" in base_url else "?"
        params = [f"per_page={self.per_page}"]

        if self.top and feed_name == "published":
            params.append(f"top={self.top}")
        if tag_filter:
            params.append(f"tag={tag_filter}")

        url = base_url + sep + "&".join(params) if params else base_url

        try:
            data = self.fetch_json(url)
            if not data or not isinstance(data, list):
                return
        except Exception as e:
            logger.warning(f"[Dev.to] Failed to fetch {feed_name}: {e}")
            return

        for item in data:
            try:
                article = self._parse_item(item, feed_name, seen)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"[Dev.to] Skipping item: {e}")

    def _parse_item(
        self, item: dict, feed_name: str, seen: Set[str]
    ) -> Optional[Article]:
        title = (item.get("title") or "").strip()
        article_url = item.get("url", "")
        if not title or not article_url:
            return None

        # Dedup across feeds/tags
        if article_url in seen:
            return None
        seen.add(article_url)

        # Reactions filter
        reactions = item.get("positive_reactions_count", 0) or 0
        if reactions < self.min_reactions:
            return None

        # Reading time filter
        reading_time = item.get("reading_time_minutes", 0) or 0
        if reading_time < self.min_reading_time:
            return None

        description = item.get("description", "") or ""
        comments_count = item.get("comments_count", 0) or 0

        # Tags
        tags_raw = item.get("tag_list") or []
        if isinstance(tags_raw, str):
            tags_raw = [t.strip() for t in tags_raw.split(",") if t.strip()]

        # Category — prefer specific categories over generic 'tech'
        category = _map_category(tags_raw)

        # Timestamp
        published = item.get("published_at") or item.get("published_timestamp")
        timestamp = _parse_timestamp(published)

        # Author
        user = item.get("user", {}) or {}
        author = user.get("name") or user.get("username") or ""

        # Build rich summary
        parts = []
        if reactions:
            parts.append(f"♥{reactions}")
        if self.include_comments and comments_count:
            parts.append(f"💬{comments_count}")
        if self.include_reading_time and reading_time:
            parts.append(f"📖{reading_time}min")
        if author:
            parts.append(f"by {author}")
        if description:
            parts.append(description)

        summary = " | ".join(parts)[:300]

        # Build tag list with feed info
        article_tags = [f"devto:{t}" for t in tags_raw[:5]]
        if feed_name != "published":
            article_tags.append(f"devto-feed:{feed_name}")

        # Quality scoring
        quality = _compute_quality(reactions, comments_count, reading_time,
                                   feed_name, author)
        if self.min_quality and quality < self.min_quality:
            return None
        if self.category_filter and category not in self.category_filter:
            return None
        article_tags.append(f"devto:quality:{quality:.2f}")

        return Article(
            title=title,
            url=article_url,
            source="dev.to" if feed_name == "published" else f"dev.to ({feed_name})",
            summary=summary,
            timestamp=timestamp,
            category=category,
            tags=article_tags,
            author=author,
            quality_score=quality,
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
    """Map dev.to tags to categories, preferring specific over generic."""
    best = "tech"  # default for dev.to
    for tag in tags:
        tag_lower = tag.lower()
        mapped = TAG_CATEGORY_MAP.get(tag_lower)
        if mapped and mapped != "tech":
            return mapped  # prefer non-tech specific category
        if mapped == "tech":
            best = "tech"
    return best
