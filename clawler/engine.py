"""Core crawl engine."""
import logging
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from clawler.models import Article
from clawler.sources.base import BaseSource
from clawler.sources import RSSSource, HackerNewsSource, RedditSource
from clawler.dedup import deduplicate
from clawler.weights import get_quality_score
from clawler.health import HealthTracker

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
        self.health = HealthTracker()

    def crawl(self, dedupe_threshold: float = 0.75) -> Tuple[List[Article], Dict[str, int]]:
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
                    self.health.record_success(src.name, len(articles))
                    all_articles.extend(articles)
                except Exception as e:
                    logger.error(f"[Engine] {src.name} failed: {e}")
                    stats[src.name] = -1
                    self.health.record_failure(src.name)

        logger.info(f"[Engine] Total raw: {len(all_articles)}")
        unique = deduplicate(all_articles, similarity_threshold=dedupe_threshold)
        logger.info(f"[Engine] After dedup: {len(unique)}")

        # Inject quality scores with health modifier
        for article in unique:
            base_score = get_quality_score(article.source)
            modifier = self.health.get_health_modifier(article.source)
            article.quality_score = base_score * modifier

        # Sort by blended score: 0.6 * recency + 0.4 * quality_score
        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc)
        def blended_key(a: Article):
            if a.timestamp:
                ts = a.timestamp if a.timestamp.tzinfo else a.timestamp.replace(tzinfo=timezone.utc)
                age_hours = max(0, (now - ts).total_seconds() / 3600)
            else:
                age_hours = 48
                ts = datetime.min.replace(tzinfo=timezone.utc)
            recency = max(0.0, 1.0 - (age_hours / 48.0))
            # Use timestamp as tiebreaker when blended scores are equal
            return (0.6 * recency + 0.4 * a.quality_score, ts)
        unique.sort(key=blended_key, reverse=True)

        self.health.save()
        return unique, stats
