"""Tests for v7.9.0 — Medium source integration into engine + CLI."""
import types
import importlib


def test_medium_source_in_engine_import():
    """MediumSource should be importable from clawler.engine module scope."""
    from clawler import engine
    assert hasattr(engine, 'MediumSource'), "engine must import MediumSource"


def test_medium_source_in_sources_init():
    """MediumSource should be in sources __all__."""
    from clawler.sources import __all__ as src_all
    assert "MediumSource" in src_all


def test_medium_source_crawl_returns_list():
    """MediumSource.crawl() should return a list (even if network fails)."""
    from clawler.sources.medium import MediumSource
    src = MediumSource(tag_feeds=[], publication_feeds=[], user_feeds=[])
    result = src.crawl()
    assert isinstance(result, list)
    assert len(result) == 0  # no feeds configured


def test_medium_source_default_feeds():
    """MediumSource should have default tag and publication feeds."""
    from clawler.sources.medium import MediumSource, DEFAULT_TAG_FEEDS, DEFAULT_PUBLICATION_FEEDS
    assert len(DEFAULT_TAG_FEEDS) >= 20
    assert len(DEFAULT_PUBLICATION_FEEDS) >= 10
    src = MediumSource()
    urls = src._build_feed_urls()
    assert len(urls) == len(DEFAULT_TAG_FEEDS) + len(DEFAULT_PUBLICATION_FEEDS)


def test_medium_parse_empty_xml():
    """Parsing empty/invalid XML should return empty list, not crash."""
    from clawler.sources.medium import MediumSource
    src = MediumSource()
    assert src._parse_feed("", "test") == []
    assert src._parse_feed("<invalid>", "test") == []


def test_medium_parse_valid_rss():
    """Parse a minimal valid RSS feed."""
    from clawler.sources.medium import MediumSource
    xml = """<?xml version="1.0"?>
    <rss version="2.0"><channel><title>Test</title>
    <item>
      <title>Test Article</title>
      <link>https://medium.com/@test/article-123</link>
      <pubDate>Sat, 15 Feb 2026 12:00:00 GMT</pubDate>
      <description>A test description</description>
    </item>
    </channel></rss>"""
    src = MediumSource()
    articles = src._parse_feed(xml, "test-tag")
    assert len(articles) == 1
    assert articles[0].title == "Test Article"
    assert articles[0].source == "medium"
    assert "?" not in articles[0].url  # tracking params stripped


def test_medium_url_cleaning():
    """Medium URLs with query params should be cleaned."""
    from clawler.sources.medium import MediumSource
    xml = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
    <item>
      <title>Tracked Article</title>
      <link>https://medium.com/@test/article?source=rss&amp;utm=foo</link>
    </item>
    </channel></rss>"""
    src = MediumSource()
    articles = src._parse_feed(xml, "test")
    assert len(articles) == 1
    assert articles[0].url == "https://medium.com/@test/article"


def test_medium_weight_exists():
    """Medium should have a quality weight."""
    from clawler.weights import get_quality_score
    score = get_quality_score("medium")
    assert score > 0.0
    assert score <= 1.0


def test_medium_in_api():
    """API should support no_medium parameter."""
    import inspect
    from clawler.api import crawl
    sig = inspect.signature(crawl)
    assert "no_medium" in sig.parameters


def test_version_bump():
    """Version should be 7.9.0."""
    from clawler import __version__
    assert __version__ == "7.9.0"
