"""Core crawl engine."""
import logging
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from clawler.models import Article
from clawler.sources.base import BaseSource
from clawler.sources import RSSSource, HackerNewsSource, RedditSource
from clawler.dedup import deduplicate

logger = logging.getLogger(__name__)


class CrawlEngine:
    """Orchestrates crawling across all sources."""

    def __init__(self, sources: Optional[List[BaseSource]] = None, max_workers: int = 6):
        self.sources = sources or [
            RSSSource(),
            HackerNewsSource(),
            RedditSource(),
        ]
        self.max_workers = max_workers

    def crawl(self) -> Tuple[List[Article], Dict[str, int]]:
        """Run all sources in parallel, deduplicate, and return sorted articles + per-source stats."""
        all_articles: List[Article] = []
        stats: Dict[str, int] = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(src.crawl): src for src in self.sources}
            for future in as_completed(futures):
                src = futures[future]
                try:
                    articles = future.result()
                    logger.info(f"[Engine] {src.name} returned {len(articles)} articles")
                    stats[src.name] = len(articles)
                    all_articles.extend(articles)
                except Exception as e:
                    logger.error(f"[Engine] {src.name} failed: {e}")
                    stats[src.name] = -1  # -1 indicates failure

        logger.info(f"[Engine] Total raw: {len(all_articles)}")
        unique = deduplicate(all_articles)
        logger.info(f"[Engine] After dedup: {len(unique)}")

        # Sort by timestamp (newest first), None timestamps last
        from datetime import datetime, timezone
        epoch = datetime.min.replace(tzinfo=timezone.utc)
        def sort_key(a: Article):
            ts = a.timestamp
            if ts is None:
                return epoch
            if ts.tzinfo is None:
                return ts.replace(tzinfo=timezone.utc)
            return ts.astimezone(timezone.utc)
        unique.sort(key=sort_key, reverse=True)
        return unique, stats
