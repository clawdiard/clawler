"""Bluesky trending source — uses public AT Protocol API (no key needed).

Fetches posts with external link embeds from multiple Bluesky feeds and search.
Supports quality scoring, engagement filtering, keyword categories, and trending topics.
"""
import logging
import math
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from urllib.parse import quote

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Public AppView endpoint (no auth required for public data)
BSKY_PUBLIC_API = "https://public.api.bsky.app"

# Bluesky curated feed generators (DIDs are stable)
BSKY_FEEDS = {
    "whats-hot": "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/whats-hot",
    "with-friends": "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/with-friends",
}

# ---------- Category keyword maps ----------
# Specific categories checked first (order matters: first match wins)
SPECIFIC_KEYWORDS: Dict[str, List[str]] = {
    "ai": [
        "artificial intelligence", " ai ", "machine learning", "deep learning",
        "neural net", "llm", "gpt", "chatgpt", "claude", "gemini", "openai",
        "transformer", "diffusion model", "generative ai", "langchain",
        "fine-tun", "rag ", "embedding", "prompt engineer",
    ],
    "security": [
        "vulnerability", "exploit", "breach", "ransomware", "malware",
        "cve-", "zero-day", "0day", "phishing", "ddos", "apt ", "pentest",
        "cybersecurity", "infosec", "threat actor", "patch tuesday",
    ],
    "crypto": [
        "bitcoin", "ethereum", "crypto ", "blockchain", "web3", "nft ",
        "defi ", "solana", "token", "dao ", "smart contract",
    ],
    "science": [
        "climate", "space", "nasa", "research", "study finds", "scientist",
        "physics", "biology", "nature ", "arxiv", "cern", "genome",
        "neuroscience", "astronomy", "quantum",
    ],
    "health": [
        "health", "medical", "vaccine", "fda ", "clinical trial", "cancer",
        "disease", "mental health", "therapy", "drug ", "pharma", "hospital",
    ],
    "business": [
        "market", "stock", "economy", "finance", "bank", "trade", "gdp",
        "inflation", "ipo ", "venture capital", "startup", "earnings",
        "revenue", "acquisition", "merger",
    ],
    "design": [
        "design", "ux ", "ui ", "figma", "typography", "branding",
        "illustration", "graphic design",
    ],
    "gaming": [
        "gaming", "video game", "playstation", "xbox", "nintendo", "steam ",
        "esports", "indie game",
    ],
    "culture": [
        "movie", "film ", "music", "album", "book ", "novel", "art ",
        "museum", "theater", "festival",
    ],
    "world": [
        "election", "government", "parliament", "senate", "congress",
        "president", "minister", "geopolit", "war ", "treaty", "united nations",
    ],
}

# Generic tech keywords (fallback)
GENERIC_TECH_KEYWORDS = [
    "software", "programming", "code", "github", "open source", "linux",
    "developer", "tech", "hack", "app ", "api ", "model", "database",
    "javascript", "python", "rust ", "kubernetes", "docker",
]

# Default search queries for discovering link-rich posts
DEFAULT_SEARCH_QUERIES = [
    "breaking news",
    "new research",
    "just launched",
    "thread worth reading",
]


def _format_count(n: int) -> str:
    """Human-readable count: 1500 → 1.5K, 2300000 → 2.3M."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _quality_score(likes: int, reposts: int, replies: int) -> float:
    """Engagement-based quality score 0–1 (logarithmic).

    Weights: likes×1 + reposts×3 + replies×2. Score of ~100 engagement ≈ 0.5.
    """
    total = likes + reposts * 3 + replies * 2
    if total <= 0:
        return 0.0
    # log10 scale: 10→0.25, 100→0.5, 1000→0.75, 10000→1.0
    return min(1.0, max(0.0, math.log10(max(1, total)) / 4.0))


def _guess_category(title: str, description: str) -> str:
    """Two-tier keyword category detection: specific first, generic tech second."""
    text = f" {title} {description} ".lower()
    # Check specific categories first
    for cat, keywords in SPECIFIC_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return cat
    # Generic tech fallback
    if any(kw in text for kw in GENERIC_TECH_KEYWORDS):
        return "tech"
    return "general"


class BlueskySource(BaseSource):
    """Crawl trending posts with links from Bluesky.

    Features:
    - Multiple curated feeds (whats-hot, with-friends)
    - Search-based discovery via custom queries
    - Trending topics discovery
    - Quality scoring (engagement-based, 0–1)
    - Engagement filtering (min_likes, min_engagement)
    - Keyword-based category detection (specific > generic > fallback)
    - Author handle + display name
    - Discussion URL linking back to Bluesky post
    - Provenance tags (bsky:feed, bsky:author, bsky:category)
    """

    name = "bluesky"

    def __init__(
        self,
        limit: int = 40,
        feeds: Optional[List[str]] = None,
        search_queries: Optional[List[str]] = None,
        include_trending: bool = True,
        min_likes: int = 0,
        min_engagement: int = 0,
        exclude_domains: Optional[List[str]] = None,
    ):
        """
        Args:
            limit: Max articles to return.
            feeds: Feed keys from BSKY_FEEDS to use (default: all).
            search_queries: Custom search terms for post discovery.
            include_trending: Fetch trending topics and search for posts.
            min_likes: Minimum like count to include a post.
            min_engagement: Minimum total engagement (likes + reposts×3 + replies×2).
            exclude_domains: Domains to skip in shared links.
        """
        self.limit = limit
        self.feeds = feeds or list(BSKY_FEEDS.keys())
        self.search_queries = search_queries
        self.include_trending = include_trending
        self.min_likes = min_likes
        self.min_engagement = min_engagement
        self.exclude_domains = set(d.lower() for d in (exclude_domains or []))

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        seen_urls: Set[str] = set()

        # 1. Curated feeds
        for feed_key in self.feeds:
            feed_uri = BSKY_FEEDS.get(feed_key)
            if not feed_uri:
                logger.warning(f"[Bluesky] Unknown feed key: {feed_key}")
                continue
            url = (
                f"{BSKY_PUBLIC_API}/xrpc/app.bsky.feed.getFeed"
                f"?feed={quote(feed_uri, safe='')}&limit={min(self.limit, 100)}"
            )
            data = self.fetch_json(url)
            if data and "feed" in data:
                self._extract_posts(data["feed"], articles, seen_urls, source_tag=f"bsky:feed:{feed_key}")

        # 2. Search queries
        queries = list(self.search_queries or DEFAULT_SEARCH_QUERIES)

        # 3. Trending topics → additional search queries
        if self.include_trending:
            trending = self._fetch_trending_topics()
            queries.extend(trending[:5])

        for query in queries:
            url = (
                f"{BSKY_PUBLIC_API}/xrpc/app.bsky.feed.searchPosts"
                f"?q={quote(query)}&limit=25&sort=top"
            )
            data = self.fetch_json(url)
            if data and "posts" in data:
                # searchPosts returns posts directly (not wrapped in feed items)
                feed_items = [{"post": p} for p in data["posts"]]
                self._extract_posts(feed_items, articles, seen_urls, source_tag=f"bsky:search:{query}")

        # Sort by quality score descending, then trim to limit
        articles.sort(key=lambda a: a.quality_score or 0, reverse=True)
        articles = articles[: self.limit]

        logger.info(f"[Bluesky] Collected {len(articles)} articles from shared links")
        return articles

    def _fetch_trending_topics(self) -> List[str]:
        """Fetch trending/suggested topics from Bluesky."""
        topics: List[str] = []
        url = f"{BSKY_PUBLIC_API}/xrpc/app.bsky.unspecced.getTaggedSuggestions"
        data = self.fetch_json(url)
        if data and "suggestions" in data:
            for s in data["suggestions"]:
                tag = s.get("tag", "").strip()
                if tag and len(tag) > 2:
                    topics.append(tag)
        return topics

    def _extract_posts(
        self,
        feed_items: List[dict],
        articles: List[Article],
        seen_urls: Set[str],
        source_tag: str = "",
    ) -> None:
        """Parse feed items and extract articles with external links."""
        for item in feed_items:
            post = item.get("post", {})
            record = post.get("record", {})
            embed = post.get("embed", {})

            # Extract external link embed
            external = None
            embed_type = embed.get("$type", "")
            if embed_type == "app.bsky.embed.external#view":
                external = embed.get("external", {})
            elif embed_type == "app.bsky.embed.recordWithMedia#view":
                media = embed.get("media", {})
                if media.get("$type") == "app.bsky.embed.external#view":
                    external = media.get("external", {})

            if not external:
                continue

            link_url = external.get("uri", "").strip()
            if not link_url or link_url in seen_urls:
                continue
            # Skip internal bsky links
            if "bsky.app" in link_url or "bsky.social" in link_url:
                continue
            # Skip excluded domains
            if self.exclude_domains:
                domain = re.sub(r"https?://(?:www\.)?", "", link_url).split("/")[0].lower()
                if domain in self.exclude_domains:
                    continue
            seen_urls.add(link_url)

            title = external.get("title", "").strip()
            if not title:
                continue

            description = external.get("description", "").strip()

            # Engagement metrics
            like_count = post.get("likeCount", 0) or 0
            repost_count = post.get("repostCount", 0) or 0
            reply_count = post.get("replyCount", 0) or 0

            # Engagement filters
            if like_count < self.min_likes:
                continue
            total_engagement = like_count + repost_count * 3 + reply_count * 2
            if total_engagement < self.min_engagement:
                continue

            # Timestamp
            created_at = record.get("createdAt", "")
            timestamp = None
            if created_at:
                try:
                    timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    timestamp = datetime.now(tz=timezone.utc)
            else:
                timestamp = datetime.now(tz=timezone.utc)

            # Author info
            author_info = post.get("author", {})
            display_name = author_info.get("displayName", "")
            handle = author_info.get("handle", "")
            author = display_name or handle

            # Quality score
            score = _quality_score(like_count, repost_count, reply_count)

            # Build summary
            summary_parts = []
            if description:
                summary_parts.append(description[:280])
            engagement_parts = []
            if like_count:
                engagement_parts.append(f"❤️ {_format_count(like_count)}")
            if repost_count:
                engagement_parts.append(f"🔁 {_format_count(repost_count)}")
            if reply_count:
                engagement_parts.append(f"💬 {_format_count(reply_count)}")
            if engagement_parts:
                summary_parts.append(" ".join(engagement_parts))
            if author:
                summary_parts.append(f"👤 @{handle}" if handle else f"👤 {author}")

            category = _guess_category(title, description)

            # Build discussion URL
            post_uri = post.get("uri", "")
            discussion_url = ""
            if post_uri and handle:
                parts = post_uri.split("/")
                if len(parts) >= 5:
                    rkey = parts[-1]
                    discussion_url = f"https://bsky.app/profile/{handle}/post/{rkey}"

            # Tags
            tags = ["bluesky", "social"]
            if source_tag:
                tags.append(source_tag)
            if handle:
                tags.append(f"bsky:author:{handle}")
            tags.append(f"bsky:category:{category}")

            # Extract hashtags from post text
            post_text = record.get("text", "")
            hashtags = re.findall(r"#(\w{2,30})", post_text)
            for ht in hashtags[:5]:
                tags.append(f"bsky:hashtag:{ht.lower()}")

            articles.append(Article(
                title=title,
                url=link_url,
                source="Bluesky",
                summary=" | ".join(summary_parts),
                timestamp=timestamp,
                category=category,
                tags=tags,
                author=author,
                discussion_url=discussion_url,
                quality_score=score,
            ))
