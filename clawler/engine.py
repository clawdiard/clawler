"""Core crawl engine."""
import logging
import time
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from clawler.models import Article
from clawler.sources.base import BaseSource
from clawler.sources import RSSSource, HackerNewsSource, RedditSource, MastodonSource, TechMemeSource, ProductHuntSource, BlueskySource, TildesSource, LemmySource, SlashdotSource, StackOverflowSource, PinboardSource, IndieHackersSource, EchoJSSource, HashnodeSource, FreeCodeCampSource, ChangelogSource
from clawler.dedup import deduplicate, DedupStats
from clawler.weights import get_quality_score
from clawler.health import HealthTracker

logger = logging.getLogger(__name__)


class CrawlEngine:
    """Orchestrates crawling across all sources."""

    def __init__(self, sources: Optional[List[BaseSource]] = None, max_workers: int = 6, retries: int = 1):
        self.sources = sources or [
            RSSSource(),
            HackerNewsSource(),
            RedditSource(),
        ]
        self.max_workers = max_workers
        self.retries = retries
        self.health = HealthTracker()

    @staticmethod
    def _timed_crawl(src: BaseSource):
        """Run a source's crawl and return (articles, elapsed_ms)."""
        t0 = time.monotonic()
        articles = src.crawl()
        elapsed_ms = (time.monotonic() - t0) * 1000
        return articles, elapsed_ms

    def crawl(self, dedupe_threshold: float = 0.75, dedupe_enabled: bool = True) -> Tuple[List[Article], Dict[str, int], DedupStats]:
        """Run all sources in parallel, deduplicate, and return sorted articles + per-source stats + dedup stats."""
        all_articles: List[Article] = []
        stats: Dict[str, int] = {}
        dedup_stats = DedupStats()

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._timed_crawl, src): src for src in self.sources}
            failed_sources = []
            for future in as_completed(futures):
                src = futures[future]
                try:
                    articles, elapsed_ms = future.result()
                    logger.info(f"[Engine] {src.name} returned {len(articles)} articles in {elapsed_ms:.0f}ms")
                    stats[src.name] = len(articles)
                    self.health.record_success(src.name, len(articles), response_ms=elapsed_ms)
                    all_articles.extend(articles)
                except Exception as e:
                    logger.error(f"[Engine] {src.name} failed: {e}")
                    failed_sources.append(src)

            # Retry failed sources (sequential, with backoff)
            for src in failed_sources:
                retried = False
                for attempt in range(1, self.retries + 1):
                    time.sleep(2 * attempt)
                    try:
                        articles, elapsed_ms = self._timed_crawl(src)
                        logger.info(f"[Engine] {src.name} retry {attempt} succeeded: {len(articles)} articles in {elapsed_ms:.0f}ms")
                        stats[src.name] = len(articles)
                        self.health.record_success(src.name, len(articles), response_ms=elapsed_ms)
                        all_articles.extend(articles)
                        retried = True
                        break
                    except Exception as e:
                        logger.error(f"[Engine] {src.name} retry {attempt} failed: {e}")
                if not retried:
                    stats[src.name] = -1
                    self.health.record_failure(src.name)

        logger.info(f"[Engine] Total raw: {len(all_articles)}")
        unique = deduplicate(all_articles, similarity_threshold=dedupe_threshold, stats=dedup_stats, enabled=dedupe_enabled)
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
        return unique, stats, dedup_stats
