"""Reddit source — uses public JSON endpoints (no API key needed).

Supports multiple sort modes, NSFW filtering, expanded subreddit defaults,
and richer metadata extraction (comment count, upvote ratio, flair).
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional
import requests
from clawler.models import Article
from clawler.sources.base import BaseSource, HEADERS

logger = logging.getLogger(__name__)

DEFAULT_SUBREDDITS = [
    # News & World
    "worldnews", "news", "geopolitics",
    # Tech & Programming
    "technology", "programming", "machinelearning", "artificial", "webdev", "netsec",
    # Science
    "science", "space", "futurology",
    # Business & Finance
    "business", "economics", "stocks",
    # Gaming
    "games", "pcgaming",
    # Sports
    "sports",
    # Entertainment
    "movies", "television",
    # Design
    "design",
]

# Map subreddit names to categories
SUBREDDIT_CATEGORIES = {
    "worldnews": "world", "news": "world", "geopolitics": "world",
    "technology": "tech", "programming": "tech", "machinelearning": "tech",
    "artificial": "tech", "webdev": "tech", "netsec": "tech",
    "science": "science", "space": "science", "futurology": "science",
    "business": "business", "economics": "business", "stocks": "business",
    "games": "gaming", "pcgaming": "gaming",
    "sports": "sports",
    "movies": "entertainment", "television": "entertainment",
    "design": "design",
}


class RedditSource(BaseSource):
    name = "reddit"

    def __init__(
        self,
        subreddits: Optional[List[str]] = None,
        limit: int = 15,
        sort: str = "hot",
        time_filter: str = "day",
        allow_nsfw: bool = False,
        min_score: int = 0,
    ):
        self.subreddits = subreddits or DEFAULT_SUBREDDITS
        self.limit = limit
        self.sort = sort if sort in ("hot", "top", "new", "rising") else "hot"
        self.time_filter = time_filter if time_filter in ("hour", "day", "week", "month", "year", "all") else "day"
        self.allow_nsfw = allow_nsfw
        self.min_score = min_score

    def _build_url(self, sub: str) -> str:
        base = f"https://www.reddit.com/r/{sub}/{self.sort}.json?limit={self.limit}"
        if self.sort == "top":
            base += f"&t={self.time_filter}"
        return base

    def crawl(self) -> List[Article]:
        articles = []
        for sub in self.subreddits:
            url = self._build_url(sub)
            try:
                data = self.fetch_json(url, extra_headers={"Accept": "application/json"})
                if not data:
                    continue
                children = data.get("data", {}).get("children", [])
                count = 0
                for post in children:
                    d = post.get("data", {})
                    if d.get("stickied"):
                        continue
                    if not self.allow_nsfw and d.get("over_18"):
                        continue

                    score = d.get("score", 0)
                    if score < self.min_score:
                        continue

                    title = d.get("title", "").strip()
                    if not title:
                        continue

                    link = d.get("url", "")
                    selftext = d.get("selftext", "")[:200]
                    permalink = f"https://reddit.com{d.get('permalink', '')}"
                    author = d.get("author", "")
                    created = d.get("created_utc")
                    num_comments = d.get("num_comments", 0)
                    upvote_ratio = d.get("upvote_ratio", 0)
                    flair = d.get("link_flair_text", "")

                    # Build rich summary
                    parts = []
                    if selftext:
                        parts.append(selftext)
                    parts.append(f"↑{score}")
                    if upvote_ratio:
                        parts.append(f"({int(upvote_ratio * 100)}% upvoted)")
                    parts.append(f"💬{num_comments}")
                    parts.append(f"r/{sub}")
                    if flair:
                        parts.append(f"[{flair}]")
                    summary = " · ".join(parts)

                    # Build tags from flair
                    tags = []
                    if flair:
                        tags.append(flair.lower())

                    articles.append(Article(
                        title=title,
                        url=link if not link.startswith("https://www.reddit.com") else permalink,
                        source=f"r/{sub}",
                        summary=summary[:300],
                        timestamp=datetime.fromtimestamp(created, tz=timezone.utc) if created else None,
                        category=SUBREDDIT_CATEGORIES.get(sub, "general"),
                        author=author,
                        discussion_url=permalink,
                        tags=tags,
                    ))
                    count += 1
                logger.info(f"[Reddit] r/{sub}: {count} posts collected")
            except Exception as e:
                logger.warning(f"[Reddit] Failed r/{sub}: {e}")
        return articles
