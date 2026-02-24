"""Tests for the Ars Technica source."""
from unittest.mock import patch, MagicMock
from clawler.sources.arstechnica import ArsTechnicaSource, ARS_FEEDS, SECTION_CATEGORY_MAP, _parse_rss_date
from datetime import datetime, timezone

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>Ars Technica</title>
<item>
  <title>AI models can now reason about code</title>
  <link>https://arstechnica.com/ai/2026/02/ai-models-reason/</link>
  <description>&lt;p&gt;New benchmarks show significant improvement in code understanding.&lt;/p&gt;</description>
  <pubDate>Sun, 15 Feb 2026 18:30:00 +0000</pubDate>
  <dc:creator>Benj Edwards</dc:creator>
  <category>AI</category>
  <category>Machine Learning</category>
</item>
<item>
  <title>Linux kernel 7.0 released with major performance gains</title>
  <link>https://arstechnica.com/gadgets/2026/02/linux-7/</link>
  <description>Performance improvements across the board.</description>
  <pubDate>Sat, 14 Feb 2026 12:00:00 +0000</pubDate>
  <dc:creator>Jim Salter</dc:creator>
  <category>Linux</category>
</item>
<item>
  <title>Duplicate without link</title>
  <link></link>
  <description>Should be skipped.</description>
</item>
</channel>
</rss>"""

EMPTY_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Ars Technica</title></channel></rss>"""


def test_arstechnica_crawl():
    src = ArsTechnicaSource(feeds=["main"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    assert len(articles) == 2
    assert articles[0].title == "AI models can now reason about code"
    assert articles[0].source == "Ars Technica (main)"
    assert articles[0].author == "Benj Edwards"
    assert "ars:tag:ai" in articles[0].tags
    assert "ars:section:main" in articles[0].tags
    assert articles[0].timestamp is not None


def test_arstechnica_empty_feed():
    src = ArsTechnicaSource(feeds=["science"])
    with patch.object(src, "fetch_url", return_value=EMPTY_RSS):
        articles = src.crawl()
    assert len(articles) == 0


def test_arstechnica_dedup_across_feeds():
    """Articles with the same URL across feeds should be deduplicated."""
    src = ArsTechnicaSource(feeds=["main", "ai"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    # Both feeds return same URLs — should dedup to 2 unique articles
    assert len(articles) == 2


def test_arstechnica_default_feeds():
    src = ArsTechnicaSource()
    assert set(src._feeds) == {"main", "science", "ai", "security"}


def test_arstechnica_all_feeds_known():
    """All default feeds should exist in ARS_FEEDS."""
    src = ArsTechnicaSource()
    for f in src._feeds:
        assert f in ARS_FEEDS


def test_arstechnica_category_mapping():
    assert SECTION_CATEGORY_MAP["science"] == "science"
    assert SECTION_CATEGORY_MAP["ai"] == "ai"
    assert SECTION_CATEGORY_MAP["security"] == "security"
    assert SECTION_CATEGORY_MAP["gaming"] == "gaming"


def test_arstechnica_limit():
    src = ArsTechnicaSource(limit=1, feeds=["main"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    assert len(articles) == 1


def test_parse_rss_date():
    dt = _parse_rss_date("Sun, 15 Feb 2026 18:30:00 +0000")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 2
    assert dt.tzinfo is not None


def test_parse_rss_date_none():
    assert _parse_rss_date(None) is None
    assert _parse_rss_date("") is None


def test_arstechnica_html_strip():
    """HTML tags in descriptions should be stripped."""
    src = ArsTechnicaSource(feeds=["main"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    # First article has HTML in description
    assert "<p>" not in articles[0].summary


def test_arstechnica_fetch_failure():
    """Source should handle fetch failures gracefully."""
    src = ArsTechnicaSource(feeds=["main"])
    with patch.object(src, "fetch_url", return_value=""):
        articles = src.crawl()
    assert len(articles) == 0


def test_arstechnica_invalid_xml():
    """Source should handle invalid XML gracefully."""
    src = ArsTechnicaSource(feeds=["main"])
    with patch.object(src, "fetch_url", return_value="not xml at all"):
        articles = src.crawl()
    assert len(articles) == 0
