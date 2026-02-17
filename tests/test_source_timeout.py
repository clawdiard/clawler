"""Tests for per-source crawl timeout in CrawlEngine."""
import time
from unittest.mock import MagicMock
from clawler.engine import CrawlEngine
from clawler.sources.base import BaseSource
from clawler.models import Article
from datetime import datetime, timezone


class SlowSource(BaseSource):
    """A source that sleeps for a configurable duration."""
    name = "SlowSource"

    def __init__(self, delay: float = 5.0):
        self.delay = delay

    def crawl(self):
        time.sleep(self.delay)
        return [Article(title="Slow article", url="https://slow.example.com/1", source=self.name,
                        timestamp=datetime.now(tz=timezone.utc))]


class FastSource(BaseSource):
    """A source that returns instantly."""
    name = "FastSource"

    def crawl(self):
        return [Article(title="Fast article", url="https://fast.example.com/1", source=self.name,
                        timestamp=datetime.now(tz=timezone.utc))]


def test_source_timeout_kills_slow_source():
    """Slow source should be marked as failed (-1) when it exceeds the timeout."""
    slow = SlowSource(delay=10.0)
    fast = FastSource()
    engine = CrawlEngine(sources=[slow, fast], max_workers=2, retries=0, source_timeout=1.0)

    articles, stats, _ = engine.crawl()

    # Fast source should succeed
    assert stats.get("FastSource", 0) == 1
    # Slow source should be timed out (marked as -1 failure)
    assert stats.get("SlowSource") == -1
    # Only fast article should be in results
    assert len(articles) == 1
    assert articles[0].source == "FastSource"


def test_no_timeout_allows_slow_source():
    """With timeout=None, even slow sources should complete."""
    slow = SlowSource(delay=0.5)  # only 0.5s, should finish
    engine = CrawlEngine(sources=[slow], max_workers=1, retries=0, source_timeout=None)

    articles, stats, _ = engine.crawl()

    assert stats.get("SlowSource") == 1
    assert len(articles) == 1


def test_default_timeout_is_60():
    """Default source_timeout should be 60 seconds."""
    engine = CrawlEngine()
    assert engine.source_timeout == 60
