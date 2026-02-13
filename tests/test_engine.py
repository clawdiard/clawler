"""Tests for clawler.engine — crawl orchestration."""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from clawler.engine import CrawlEngine
from clawler.models import Article
from clawler.sources.base import BaseSource


class StubSource(BaseSource):
    """Deterministic source for testing."""

    def __init__(self, name: str, articles: list[Article]):
        self.name = name
        self._articles = articles

    def crawl(self):
        return list(self._articles)


class FailingSource(BaseSource):
    name = "failing"

    def crawl(self):
        raise RuntimeError("boom")


def _article(title, source="Test", hours_ago=1, quality=0.7):
    ts = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    a = Article(title=title, url=f"https://ex.com/{title}", source=source,
                timestamp=ts, category="tech")
    a.quality_score = quality
    return a


class TestCrawlEngine:
    def test_basic_crawl(self):
        src = StubSource("stub", [_article("Hello"), _article("World")])
        engine = CrawlEngine(sources=[src])
        articles, stats, dedup_stats = engine.crawl()
        assert len(articles) == 2
        assert stats["stub"] == 2

    def test_dedup_across_sources(self):
        a1 = _article("Breaking news today", source="A", quality=0.5)
        a2 = _article("Breaking news today", source="B", quality=0.9)
        s1 = StubSource("s1", [a1])
        s2 = StubSource("s2", [a2])
        engine = CrawlEngine(sources=[s1, s2])
        articles, stats, _ = engine.crawl()
        assert len(articles) == 1

    def test_failing_source_doesnt_crash(self):
        good = StubSource("good", [_article("OK")])
        bad = FailingSource()
        engine = CrawlEngine(sources=[good, bad])
        articles, stats, _ = engine.crawl()
        assert len(articles) == 1
        assert stats["failing"] == -1

    def test_sort_by_blended_score(self):
        recent = _article("Recent", hours_ago=0.5, quality=0.5)
        old_quality = _article("Old Quality", hours_ago=40, quality=0.95)
        src = StubSource("s", [old_quality, recent])
        engine = CrawlEngine(sources=[src])
        articles, _, _ = engine.crawl()
        # Recent article should rank higher due to recency weight
        assert articles[0].title == "Recent"

    def test_empty_sources(self):
        engine = CrawlEngine(sources=[StubSource("empty", [])])
        articles, stats, _ = engine.crawl()
        assert len(articles) == 0
        assert stats["empty"] == 0
