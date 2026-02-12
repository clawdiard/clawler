"""Reddit source — uses public JSON endpoints (no API key needed)."""
import logging
from datetime import datetime
from typing import List, Optional
import requests
from clawler.models import Article
from clawler.sources.base import BaseSource, HEADERS

logger = logging.getLogger(__name__)

DEFAULT_SUBREDDITS = ["worldnews", "technology", "science", "news", "programming"]


class RedditSource(BaseSource):
    name = "reddit"

    def __init__(self, subreddits: Optional[List[str]] = None, limit: int = 15):
        self.subreddits = subreddits or DEFAULT_SUBREDDITS
        self.limit = limit

    def crawl(self) -> List[Article]:
        articles = []
        for sub in self.subreddits:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit={self.limit}"
            try:
                resp = requests.get(url, headers={**HEADERS, "Accept": "application/json"}, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                for post in data.get("data", {}).get("children", []):
                    d = post.get("data", {})
                    if d.get("stickied"):
                        continue
                    title = d.get("title", "").strip()
                    link = d.get("url", "")
                    selftext = d.get("selftext", "")[:200]
                    permalink = f"https://reddit.com{d.get('permalink', '')}"
                    score = d.get("score", 0)
                    created = d.get("created_utc")

                    summary = selftext if selftext else f"↑{score} on r/{sub} — {permalink}"
                    articles.append(Article(
                        title=title,
                        url=link if not link.startswith("https://www.reddit.com") else permalink,
                        source=f"r/{sub}",
                        summary=summary[:300],
                        timestamp=datetime.utcfromtimestamp(created) if created else None,
                        category="tech" if sub in ("technology", "programming") else "world",
                    ))
                logger.info(f"[Reddit] r/{sub}: {len(data.get('data', {}).get('children', []))} posts")
            except Exception as e:
                logger.warning(f"[Reddit] Failed r/{sub}: {e}")
        return articles
