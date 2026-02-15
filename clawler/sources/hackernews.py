"""Hacker News source — uses the free Firebase API (no key needed).

Supports multiple story feeds (top, best, new, ask, show, job),
min-score filtering, and automatic category detection.
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List, Optional, Set
import requests
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

HN_BASE = "https://hacker-news.firebaseio.com/v0"
HN_ITEM = f"{HN_BASE}/item/{{}}.json"

FEED_ENDPOINTS = {
    "top": f"{HN_BASE}/topstories.json",
    "best": f"{HN_BASE}/beststories.json",
    "new": f"{HN_BASE}/newstories.json",
    "ask": f"{HN_BASE}/askstories.json",
    "show": f"{HN_BASE}/showstories.json",
    "job": f"{HN_BASE}/jobstories.json",
}

# Keyword-based category detection applied to title + URL domain
_CATEGORY_RULES = [
    ("ai", re.compile(r"\b(ai|llm|gpt|openai|anthropic|claude|gemini|machine.?learn|neural|deep.?learn|transformer|diffusion)\b", re.I)),
    ("security", re.compile(r"\b(security|vulnerabilit\w*|exploit\w*|cve-?\d*|ransomware|malware|hack(?:ed|ing)|breach|zero.?day|phish\w*)\b", re.I)),
    ("science", re.compile(r"\b(research|study|paper|physics|biology|chemistry|space|nasa|climate|quantum)\b", re.I)),
    ("business", re.compile(r"\b(startup|funding|ipo|acquisition|layoff|revenue|valuation|vc|series.[a-d])\b", re.I)),
    ("programming", re.compile(r"\b(rust|python|javascript|typescript|golang|compiler|database|sql|api|framework|library|open.?source)\b", re.I)),
    ("crypto", re.compile(r"\b(bitcoin|ethereum|crypto|blockchain|web3|defi|nft)\b", re.I)),
]


def _detect_category(title: str, url: str) -> str:
    text = f"{title} {url}"
    for cat, pattern in _CATEGORY_RULES:
        if pattern.search(text):
            return cat
    return "tech"


class HackerNewsSource(BaseSource):
    """Crawl Hacker News stories via the Firebase API.

    Parameters
    ----------
    feeds : list of str
        Which feeds to pull. Default ``["top"]``.
        Options: top, best, new, ask, show, job.
    limit : int
        Max stories **per feed**. Default 30.
    min_score : int
        Skip stories below this score (0 = no filter). Default 0.
    max_workers : int
        Concurrent item fetches. Default 10.
    """

    name = "hackernews"

    def __init__(
        self,
        feeds: Optional[List[str]] = None,
        limit: int = 30,
        min_score: int = 0,
        max_workers: int = 10,
    ):
        self.feeds = feeds or ["top"]
        self.limit = limit
        self.min_score = min_score
        self.max_workers = max_workers

    def _fetch_item(self, story_id: int, feed_type: str) -> Optional[Article]:
        """Fetch a single HN item and return an Article or None."""
        try:
            item = self.fetch_json(HN_ITEM.format(story_id))
            if not item or item.get("type") not in ("story", "job"):
                return None

            score = item.get("score", 0)
            if self.min_score and score < self.min_score:
                return None

            title = item.get("title", "")
            url = item.get("url", f"https://news.ycombinator.com/item?id={story_id}")
            author = item.get("by", "")
            comments = item.get("descendants", 0)
            ts = item.get("time")
            discussion = f"https://news.ycombinator.com/item?id={story_id}"

            # Prefix for special feeds
            prefix = ""
            if feed_type == "ask":
                prefix = "Ask HN: "
            elif feed_type == "show":
                prefix = "Show HN: "
            elif feed_type == "job":
                prefix = "Job: "

            # Build tags
            tags = []
            if author:
                tags.append(f"hn:{author}")
            if feed_type != "top":
                tags.append(f"hn-feed:{feed_type}")

            category = "jobs" if feed_type == "job" else _detect_category(title, url)

            display_title = title if title.startswith(("Ask HN", "Show HN")) else f"{prefix}{title}" if prefix else title

            return Article(
                title=display_title,
                url=url,
                source=f"Hacker News (↑{score})",
                summary=f"Score: {score} | By: {author} | Comments: {comments} | HN discussion: {discussion}",
                timestamp=datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None,
                category=category,
                tags=tags,
                author=author,
                discussion_url=discussion,
            )
        except Exception as e:
            logger.debug(f"[HN] Failed item {story_id}: {e}")
            return None

    def crawl(self) -> List[Article]:
        # Collect story IDs from all requested feeds, deduplicating
        all_ids: List[tuple] = []  # (id, feed_type)
        seen: Set[int] = set()

        for feed in self.feeds:
            endpoint = FEED_ENDPOINTS.get(feed)
            if not endpoint:
                logger.warning(f"[HN] Unknown feed type: {feed}")
                continue
            try:
                ids = self.fetch_json(endpoint)
                if not ids:
                    continue
                for sid in ids[: self.limit]:
                    if sid not in seen:
                        seen.add(sid)
                        all_ids.append((sid, feed))
            except Exception as e:
                logger.warning(f"[HN] Failed to get {feed} stories: {e}")

        if not all_ids:
            return []

        articles = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._fetch_item, sid, ft): sid for sid, ft in all_ids}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    articles.append(result)

        logger.info(f"[HN] Fetched {len(articles)} stories from {len(self.feeds)} feed(s)")
        return articles
