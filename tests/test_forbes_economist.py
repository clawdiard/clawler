"""Tests for Forbes and The Economist sources (v10.36.0)."""
from unittest.mock import patch
from clawler.sources.forbes import ForbesSource, _quality_boost as forbes_boost
from clawler.sources.economist import EconomistSource, _quality_boost as economist_boost


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>AI Startup Raises $2 Billion in Record Funding Round</title>
      <link>https://example.com/article1</link>
      <description>A new AI unicorn emerges from stealth.</description>
      <pubDate>Tue, 18 Feb 2026 12:00:00 GMT</pubDate>
      <author>John Smith</author>
    </item>
    <item>
      <title>Global Markets Steady Amid Trade Tensions</title>
      <link>https://example.com/article2</link>
      <description>Investors weigh policy risks and growth outlook.</description>
      <pubDate>Tue, 18 Feb 2026 11:00:00 GMT</pubDate>
    </item>
    <item>
      <title></title>
      <link>https://example.com/noname</link>
    </item>
  </channel>
</rss>"""


class TestForbesSource:
    def test_crawl_parses_articles(self):
        src = ForbesSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        assert len(articles) >= 2
        assert articles[0].source.startswith("Forbes")
        assert articles[0].timestamp is not None
        assert articles[0].author == "John Smith"

    def test_crawl_filters_sections(self):
        src = ForbesSource(sections=["AI"])
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        assert all("AI" in a.source or "ai" in a.tags[0] for a in articles)

    def test_crawl_handles_empty(self):
        src = ForbesSource()
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []

    def test_crawl_handles_exception(self):
        src = ForbesSource()
        with patch.object(src, "fetch_url", side_effect=Exception("boom")):
            articles = src.crawl()
        assert articles == []

    def test_source_name(self):
        assert ForbesSource().name == "forbes"

    def test_empty_title_skipped(self):
        src = ForbesSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        assert "" not in [a.title for a in articles]

    def test_quality_boost_high(self):
        assert forbes_boost("AI startup funding", "") == 0.15

    def test_quality_boost_medium(self):
        assert forbes_boost("cloud innovation trends", "") == 0.08

    def test_quality_boost_none(self):
        assert forbes_boost("weather report", "") == 0.0


class TestEconomistSource:
    def test_crawl_parses_articles(self):
        src = EconomistSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        assert len(articles) >= 2
        assert articles[0].source.startswith("The Economist")
        assert articles[0].timestamp is not None

    def test_crawl_filters_sections(self):
        src = EconomistSource(sections=["Leaders"])
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        assert all("Leaders" in a.source or "leaders" in a.tags[0] for a in articles)

    def test_crawl_handles_empty(self):
        src = EconomistSource()
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []

    def test_crawl_handles_exception(self):
        src = EconomistSource()
        with patch.object(src, "fetch_url", side_effect=Exception("boom")):
            articles = src.crawl()
        assert articles == []

    def test_source_name(self):
        assert EconomistSource().name == "economist"

    def test_high_base_quality(self):
        src = EconomistSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        # Economist has 0.82 base — higher than most sources
        assert all(a.quality_score >= 0.82 for a in articles)

    def test_quality_boost_high(self):
        assert economist_boost("geopolitics trade war", "") == 0.15

    def test_quality_boost_medium(self):
        assert economist_boost("policy reform outlook", "") == 0.08

    def test_quality_boost_none(self):
        assert economist_boost("book review fiction", "") == 0.0
