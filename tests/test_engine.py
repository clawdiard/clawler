"""Tests for the crawl engine."""
from datetime import datetime, timezone
from clawler.engine import CrawlEngine
from clawler.models import Article
from clawler.sources.base import BaseSource


class FakeSource(BaseSource):
    name = "fake"

    def __init__(self, articles):
        self._articles = articles

    def crawl(self):
        return self._articles


class TestCrawlEngine:
    def test_basic_crawl(self):
        titles = ["Python 4.0 released today", "NASA finds water on Mars", "Stock market crashes hard",
                  "New vaccine approved by FDA", "Olympics opening ceremony dazzles"]
        arts = [Article(title=t, url=f"https://a.com/{i}", source="fake") for i, t in enumerate(titles)]
        engine = CrawlEngine(sources=[FakeSource(arts)])
        result, stats, _ds = engine.crawl()
        assert len(result) == 5
        assert stats["fake"] == 5

    def test_dedup_across_sources(self):
        a1 = Article(title="Same story here", url="https://a.com/1", source="s1")
        a2 = Article(title="Same story here", url="https://a.com/1", source="s2")
        engine = CrawlEngine(sources=[FakeSource([a1]), FakeSource([a2])])
        result, stats, _ds = engine.crawl()
        assert len(result) == 1

    def test_sorts_newest_first(self):
        old = Article(title="Old", url="https://a.com/old", source="s",
                      timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc))
        new = Article(title="New", url="https://a.com/new", source="s",
                      timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc))
        engine = CrawlEngine(sources=[FakeSource([old, new])])
        result, stats, _ds = engine.crawl()
        assert result[0].title == "New"

    def test_failed_source_doesnt_break(self):
        class FailSource(BaseSource):
            name = "fail"
            def crawl(self):
                raise RuntimeError("boom")

        ok = Article(title="OK", url="https://a.com/ok", source="ok")
        engine = CrawlEngine(sources=[FailSource(), FakeSource([ok])])
        result, stats, _ds = engine.crawl()
        assert len(result) == 1
        assert stats["fail"] == -1

    def test_stats_returned(self):
        src1 = FakeSource([Article(title="A", url="https://a.com/1", source="s")])
        src1.name = "src1"
        src2 = FakeSource([Article(title="B", url="https://b.com/1", source="s"),
                           Article(title="C", url="https://c.com/1", source="s")])
        src2.name = "src2"
        engine = CrawlEngine(sources=[src1, src2])
        result, stats, _ds = engine.crawl()
        assert stats["src1"] == 1
        assert stats["src2"] == 2
