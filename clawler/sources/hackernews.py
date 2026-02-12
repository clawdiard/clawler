"""Hacker News source — uses the free Firebase API (no key needed)."""
import logging
from datetime import datetime
from typing import List
import requests
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"


class HackerNewsSource(BaseSource):
    name = "hackernews"

    def __init__(self, limit: int = 30):
        self.limit = limit

    def crawl(self) -> List[Article]:
        articles = []
        try:
            resp = requests.get(HN_TOP, timeout=self.timeout)
            resp.raise_for_status()
            ids = resp.json()[:self.limit]
        except Exception as e:
            logger.warning(f"[HN] Failed to get top stories: {e}")
            return []

        for story_id in ids:
            try:
                r = requests.get(HN_ITEM.format(story_id), timeout=self.timeout)
                item = r.json()
                if not item or item.get("type") != "story":
                    continue
                title = item.get("title", "")
                url = item.get("url", f"https://news.ycombinator.com/item?id={story_id}")
                score = item.get("score", 0)
                ts = item.get("time")
                articles.append(Article(
                    title=title,
                    url=url,
                    source=f"Hacker News (↑{score})",
                    summary=f"Score: {score} | Comments: {item.get('descendants', 0)} | HN discussion: https://news.ycombinator.com/item?id={story_id}",
                    timestamp=datetime.utcfromtimestamp(ts) if ts else None,
                    category="tech",
                ))
            except Exception as e:
                logger.debug(f"[HN] Failed item {story_id}: {e}")
        logger.info(f"[HN] Fetched {len(articles)} stories")
        return articles
