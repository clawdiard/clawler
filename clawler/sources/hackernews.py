"""Hacker News source — uses the free Firebase API (no key needed)."""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List, Optional
import requests
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"


class HackerNewsSource(BaseSource):
    name = "hackernews"

    def __init__(self, limit: int = 30, max_workers: int = 10):
        self.limit = limit
        self.max_workers = max_workers

    def _fetch_item(self, story_id: int) -> Optional[Article]:
        """Fetch a single HN item and return an Article or None."""
        try:
            r = requests.get(HN_ITEM.format(story_id), timeout=self.timeout)
            item = r.json()
            if not item or item.get("type") != "story":
                return None
            title = item.get("title", "")
            url = item.get("url", f"https://news.ycombinator.com/item?id={story_id}")
            score = item.get("score", 0)
            ts = item.get("time")
            return Article(
                title=title,
                url=url,
                source=f"Hacker News (↑{score})",
                summary=f"Score: {score} | Comments: {item.get('descendants', 0)} | HN discussion: https://news.ycombinator.com/item?id={story_id}",
                timestamp=datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None,
                category="tech",
            )
        except Exception as e:
            logger.debug(f"[HN] Failed item {story_id}: {e}")
            return None

    def crawl(self) -> List[Article]:
        try:
            resp = requests.get(HN_TOP, timeout=self.timeout)
            resp.raise_for_status()
            ids = resp.json()[:self.limit]
        except Exception as e:
            logger.warning(f"[HN] Failed to get top stories: {e}")
            return []

        articles = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._fetch_item, sid): sid for sid in ids}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    articles.append(result)

        logger.info(f"[HN] Fetched {len(articles)} stories")
        return articles
