"""Tests for v7.7.0: Hacker Noon source, fix test_v520 source count, engine import cleanup."""
from unittest.mock import patch, MagicMock
import pytest


def test_hackernoon_source_basic():
    """HackerNoonSource should parse RSS items into Articles."""
    from clawler.sources.hackernoon import HackerNoonSource

    sample_rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
      <channel>
        <title>Hacker Noon</title>
        <item>
          <title>Building LLM Apps in 2026</title>
          <link>https://hackernoon.com/building-llm-apps</link>
          <description>A guide to building LLM applications.</description>
          <dc:creator>Jane Doe</dc:creator>
          <category>ai</category>
          <category>programming</category>
          <pubDate>Sat, 15 Feb 2026 12:00:00 GMT</pubDate>
        </item>
        <item>
          <title>Startup Funding in 2026</title>
          <link>https://hackernoon.com/startup-funding</link>
          <description>VC trends for the year.</description>
          <category>startup</category>
          <pubDate>Sat, 15 Feb 2026 10:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""

    src = HackerNoonSource(limit=10)
    with patch.object(src, "fetch_url", return_value=sample_rss):
        articles = src.crawl()

    assert len(articles) == 2
    assert articles[0].title == "Building LLM Apps in 2026"
    assert articles[0].source == "Hacker Noon"
    assert articles[0].category == "ai"
    assert articles[0].author == "Jane Doe"
    assert articles[0].url == "https://hackernoon.com/building-llm-apps"
    assert articles[1].category == "business"


def test_hackernoon_source_empty_feed():
    """HackerNoonSource should return empty list on empty feed."""
    from clawler.sources.hackernoon import HackerNoonSource

    src = HackerNoonSource()
    with patch.object(src, "fetch_url", return_value=""):
        articles = src.crawl()
    assert articles == []


def test_hackernoon_source_malformed_xml():
    """HackerNoonSource should handle malformed XML gracefully."""
    from clawler.sources.hackernoon import HackerNoonSource

    src = HackerNoonSource()
    with patch.object(src, "fetch_url", return_value="<not valid xml"):
        articles = src.crawl()
    assert articles == []


def test_hackernoon_category_mapping():
    """Category mapping should work for known tags."""
    from clawler.sources.hackernoon import _map_category

    assert _map_category(["ai", "python"]) == "ai"
    assert _map_category(["cybersecurity"]) == "security"
    assert _map_category(["startup", "marketing"]) == "business"
    assert _map_category(["blockchain", "defi"]) == "crypto"
    assert _map_category(["javascript", "react"]) == "tech"


def test_hackernoon_in_sources_init():
    """HackerNoonSource should be importable from sources package."""
    from clawler.sources import HackerNoonSource
    assert HackerNoonSource is not None


def test_hackernoon_weight():
    """Hacker Noon should have a quality weight."""
    from clawler.weights import get_quality_score
    score = get_quality_score("Hacker Noon")
    assert score == 0.64


def test_api_includes_hackernoon():
    """API crawl should include HackerNoonSource by default."""
    from clawler.api import crawl
    from clawler.sources.hackernoon import HackerNoonSource

    with patch('clawler.api.CrawlEngine') as MockEngine:
        instance = MockEngine.return_value
        instance.crawl.return_value = ([], {}, MagicMock())
        crawl()
        call_args = MockEngine.call_args
        sources = call_args[1]['sources'] if 'sources' in call_args[1] else call_args[0][0]
        source_types = {type(s) for s in sources}
        assert HackerNoonSource in source_types


def test_api_disable_hackernoon():
    """API crawl with no_hackernoon=True should exclude HackerNoonSource."""
    from clawler.api import crawl
    from clawler.sources.hackernoon import HackerNoonSource

    with patch('clawler.api.CrawlEngine') as MockEngine:
        instance = MockEngine.return_value
        instance.crawl.return_value = ([], {}, MagicMock())
        crawl(no_hackernoon=True)
        call_args = MockEngine.call_args
        sources = call_args[1]['sources'] if 'sources' in call_args[1] else call_args[0][0]
        source_types = {type(s) for s in sources}
        assert HackerNoonSource not in source_types


def test_version_770():
    """Version should be 7.7.0."""
    from clawler import __version__
    assert __version__ == "7.7.0"
