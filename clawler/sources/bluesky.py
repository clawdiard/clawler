"""Bluesky trending source — uses public AT Protocol API (no key needed).

Fetches the public trending/popular feed from Bluesky's AppView API.
Extracts posts with external link embeds as articles.
"""
import logging
from datetime import datetime, timezone
from typing import List

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Public AppView endpoint (no auth required for public data)
BSKY_PUBLIC_API = "https://public.api.bsky.app"


class BlueskySource(BaseSource):
    """Crawl trending posts with links from Bluesky."""

    name = "bluesky"

    def __init__(self, limit: int = 40):
        self.limit = limit

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        seen_urls: set = set()

        # Use the public "What's Hot" / popular feed generator
        # Try the discover feed first, fall back to searching recent popular posts
        feeds_to_try = [
            f"{BSKY_PUBLIC_API}/xrpc/app.bsky.feed.getFeed?feed=at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/whats-hot&limit={self.limit}",
            f"{BSKY_PUBLIC_API}/xrpc/app.bsky.feed.getFeed?feed=at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/with-friends&limit={self.limit}",
        ]

        for feed_url in feeds_to_try:
            data = self.fetch_json(feed_url)
            if not data or "feed" not in data:
                logger.info(f"[Bluesky] No data from feed endpoint")
                continue

            for item in data.get("feed", []):
                post = item.get("post", {})
                record = post.get("record", {})
                embed = post.get("embed", {})

                # We want posts that share external links
                external = None
                if embed.get("$type") == "app.bsky.embed.external#view":
                    external = embed.get("external", {})
                elif embed.get("$type") == "app.bsky.embed.recordWithMedia#view":
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
                seen_urls.add(link_url)

                title = external.get("title", "").strip()
                if not title:
                    continue

                description = external.get("description", "").strip()

                # Parse timestamp
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

                # Engagement metrics
                like_count = post.get("likeCount", 0)
                repost_count = post.get("repostCount", 0)
                reply_count = post.get("replyCount", 0)

                # Build summary
                summary_parts = []
                if description:
                    summary_parts.append(description[:200])
                engagement = []
                if like_count:
                    engagement.append(f"❤️ {like_count}")
                if repost_count:
                    engagement.append(f"🔁 {repost_count}")
                if reply_count:
                    engagement.append(f"💬 {reply_count}")
                if engagement:
                    summary_parts.append(" ".join(engagement) + " on Bluesky")
                if author:
                    summary_parts.append(f"shared by {author}")

                category = _guess_category(title, description)

                # Build discussion URL from post URI
                post_uri = post.get("uri", "")
                discussion_url = ""
                if post_uri and handle:
                    # at://did:plc:xxx/app.bsky.feed.post/yyy → https://bsky.app/profile/handle/post/yyy
                    parts = post_uri.split("/")
                    if len(parts) >= 5:
                        rkey = parts[-1]
                        discussion_url = f"https://bsky.app/profile/{handle}/post/{rkey}"

                articles.append(Article(
                    title=title,
                    url=link_url,
                    source="Bluesky",
                    summary=" | ".join(summary_parts),
                    timestamp=timestamp,
                    category=category,
                    tags=["bluesky", "social"],
                    author=author,
                    discussion_url=discussion_url,
                ))

        logger.info(f"[Bluesky] Collected {len(articles)} articles from shared links")
        return articles


def _guess_category(title: str, description: str) -> str:
    """Simple keyword-based category inference."""
    text = f"{title} {description}".lower()
    if any(kw in text for kw in ("ai ", "software", "programming", "code", "github",
                                   "open source", "linux", "developer", "tech", "cyber",
                                   "hack", "startup", "app ", "api ", "llm", "model")):
        return "tech"
    if any(kw in text for kw in ("climate", "space", "research", "study", "scientist",
                                   "physics", "biology", "nature", "arxiv")):
        return "science"
    if any(kw in text for kw in ("market", "stock", "economy", "finance", "bank",
                                   "trade", "gdp", "inflation")):
        return "business"
    if any(kw in text for kw in ("security", "vulnerability", "exploit", "breach",
                                   "ransomware", "malware", "cve", "zero-day")):
        return "security"
    if any(kw in text for kw in ("investigation", "leaked", "whistleblow", "corruption",
                                   "exclusive")):
        return "investigative"
    return "general"
