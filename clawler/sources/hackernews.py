"""Hacker News source — uses the free Firebase API (no key needed).

Supports multiple story feeds (top, best, new, ask, show, job),
min-score filtering, and automatic category detection.

Enhanced features:
- Quality scoring (0–1) based on score percentile, feed prominence, comment engagement, position decay
- Prominent author recognition (prolific HN contributors)
- Keyword-based category detection (8 categories)
- Filters: min_quality, category_filter
- Quality-sorted output
"""
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

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

# Feed prominence — editorial signal value
FEED_PROMINENCE: Dict[str, float] = {
    "best": 0.30,
    "top": 0.25,
    "show": 0.20,
    "ask": 0.20,
    "new": 0.10,
    "job": 0.15,
}

# Prominent HN authors (well-known tech figures active on HN)
PROMINENT_AUTHORS: Dict[str, float] = {
    "pg": 0.15,          # Paul Graham
    "dang": 0.12,        # HN moderator
    "patio11": 0.12,     # Patrick McKenzie
    "tptacek": 0.12,     # Thomas Ptacek
    "jacquesm": 0.10,    # Jacques Mattheij
    "cperciva": 0.10,    # Colin Percival
    "sama": 0.10,        # Sam Altman
    "rauchg": 0.08,      # Guillermo Rauch
    "gdb": 0.08,         # Greg Brockman
    "simonw": 0.08,      # Simon Willison
    "antirez": 0.08,     # Salvatore Sanfilippo
    "karpathy": 0.08,    # Andrej Karpathy
    "mitsuhiko": 0.08,   # Armin Ronacher
    "codinghorror": 0.08, # Jeff Atwood
    "swyx": 0.06,        # Shawn Wang
}

# Keyword-based category detection applied to title + URL domain
_CATEGORY_RULES = [
    ("ai", re.compile(r"\b(ai|llm|gpt|openai|anthropic|claude|gemini|machine.?learn|neural|deep.?learn|transformer|diffusion)\b", re.I)),
    ("security", re.compile(r"\b(security|vulnerabilit\w*|exploit\w*|cve-?\d*|ransomware|malware|hack(?:ed|ing)|breach|zero.?day|phish\w*)\b", re.I)),
    ("science", re.compile(r"\b(research|study|paper|physics|biology|chemistry|space|nasa|climate|quantum)\b", re.I)),
    ("business", re.compile(r"\b(startup|funding|ipo|acquisition|layoff|revenue|valuation|vc|series.[a-d])\b", re.I)),
    ("programming", re.compile(r"\b(rust|python|javascript|typescript|golang|compiler|database|sql|api|framework|library|open.?source)\b", re.I)),
    ("crypto", re.compile(r"\b(bitcoin|ethereum|crypto|blockchain|web3|defi|nft)\b", re.I)),
    ("culture", re.compile(r"\b(book|film|music|art|history|philosophy|culture|society)\b", re.I)),
    ("devops", re.compile(r"\b(docker|kubernetes|k8s|ci.?cd|devops|terraform|aws|cloud|infrastructure|deploy)\b", re.I)),
]


def _detect_category(title: str, url: str) -> str:
    text = f"{title} {url}"
    for cat, pattern in _CATEGORY_RULES:
        if pattern.search(text):
            return cat
    return "tech"


def _score_to_quality(score: int) -> float:
    """Map HN score to a 0–0.4 quality component using log scaling."""
    if score <= 0:
        return 0.0
    # log10(1)=0, log10(10)=1, log10(100)=2, log10(1000)=3
    return min(0.40, 0.10 * math.log10(max(score, 1) + 1))


def _comment_engagement(comments: int, score: int) -> float:
    """Engagement bonus: high comment-to-score ratio indicates discussion."""
    if score <= 0 or comments <= 0:
        return 0.0
    ratio = comments / score
    # Sweet spot: 0.5-2.0 ratio = good discussion
    if ratio >= 0.5:
        return min(0.10, ratio * 0.05)
    return 0.02


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
    min_quality : float
        Skip articles below this quality (0.0 = no filter). Default 0.0.
    category_filter : list of str or None
        Only return articles matching these categories. Default None (all).
    max_workers : int
        Concurrent item fetches. Default 10.
    """

    name = "hackernews"

    def __init__(
        self,
        feeds: Optional[List[str]] = None,
        limit: int = 30,
        min_score: int = 0,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        max_workers: int = 10,
    ):
        self.feeds = feeds or ["top"]
        self.limit = limit
        self.min_score = min_score
        self.min_quality = min_quality
        self.category_filter = category_filter
        self.max_workers = max_workers

    def _compute_quality(self, score: int, comments: int, author: str,
                         feed_type: str, position: int) -> float:
        """Compute quality score (0–1) for a HN story."""
        q = 0.0

        # Feed prominence (0–0.30)
        q += FEED_PROMINENCE.get(feed_type, 0.15)

        # Score component (0–0.40)
        q += _score_to_quality(score)

        # Comment engagement (0–0.10)
        q += _comment_engagement(comments, score)

        # Author prominence (0–0.15)
        q += PROMINENT_AUTHORS.get(author.lower(), 0.0) if author else 0.0

        # Position decay: top stories get a small boost (0–0.05)
        if position < 5:
            q += 0.05 - (position * 0.01)
        elif position < 15:
            q += 0.02

        return min(1.0, round(q, 3))

    def _fetch_item(self, story_id: int, feed_type: str, position: int) -> Optional[Article]:
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

            category = "jobs" if feed_type == "job" else _detect_category(title, url)

            # Quality scoring
            quality = self._compute_quality(score, comments, author, feed_type, position)
            if self.min_quality and quality < self.min_quality:
                return None
            if self.category_filter and category not in self.category_filter:
                return None

            # Build tags
            tags = []
            if author:
                tags.append(f"hn:{author}")
            if feed_type != "top":
                tags.append(f"hn-feed:{feed_type}")
            if author.lower() in PROMINENT_AUTHORS:
                tags.append(f"hn:prominent-author")
            tags.append(f"hn:quality:{quality:.2f}")

            display_title = title if title.startswith(("Ask HN", "Show HN")) else f"{prefix}{title}" if prefix else title

            return Article(
                title=display_title,
                url=url,
                source=f"Hacker News (↑{score})",
                summary=f"Score: {score} | By: {author} | Comments: {comments} | Quality: {quality:.2f} | HN discussion: {discussion}",
                timestamp=datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None,
                category=category,
                quality_score=quality,
                tags=tags,
                author=author,
                discussion_url=discussion,
            )
        except Exception as e:
            logger.debug(f"[HN] Failed item {story_id}: {e}")
            return None

    def crawl(self) -> List[Article]:
        # Collect story IDs from all requested feeds, deduplicating
        all_ids: List[tuple] = []  # (id, feed_type, position)
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
                for pos, sid in enumerate(ids[: self.limit]):
                    if sid not in seen:
                        seen.add(sid)
                        all_ids.append((sid, feed, pos))
            except Exception as e:
                logger.warning(f"[HN] Failed to get {feed} stories: {e}")

        if not all_ids:
            return []

        articles = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._fetch_item, sid, ft, pos): sid for sid, ft, pos in all_ids}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    articles.append(result)

        # Sort by quality descending
        articles.sort(key=lambda a: a.quality_score, reverse=True)

        logger.info(f"[HN] Fetched {len(articles)} stories from {len(self.feeds)} feed(s)")
        return articles
