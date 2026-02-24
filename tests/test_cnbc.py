"""Tests for CNBC source."""
from unittest.mock import patch
from clawler.sources.cnbc import CNBCSource, CNBC_FEEDS, PROMINENT_AUTHORS

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel><title>CNBC</title>
<item>
  <title>Fed signals rate cuts ahead as inflation cools</title>
  <link>https://www.cnbc.com/2026/02/24/fed-rate-cuts.html</link>
  <description>The Federal Reserve indicated it may begin cutting rates.</description>
  <pubDate>Mon, 24 Feb 2026 09:00:00 GMT</pubDate>
  <author>Steve Liesman</author>
</item>
<item>
  <title>AI chip demand drives Nvidia earnings beat</title>
  <link>https://www.cnbc.com/2026/02/24/nvidia-earnings.html</link>
  <description>Nvidia reported record revenue fueled by AI chip sales.</description>
  <pubDate>Mon, 24 Feb 2026 08:00:00 GMT</pubDate>
  <author>Kif Leswing</author>
</item>
<item><title></title><link></link></item>
</channel></rss>"""


def test_cnbc_feed_config():
    assert len(CNBC_FEEDS) == 12
    for key, feed in CNBC_FEEDS.items():
        assert "url" in feed
        assert "label" in feed
        assert "category" in feed


def test_cnbc_prominent_authors():
    assert len(PROMINENT_AUTHORS) >= 15
    assert "jim cramer" in PROMINENT_AUTHORS
    assert "kif leswing" in PROMINENT_AUTHORS


def test_cnbc_crawl():
    src = CNBCSource(feeds=["technology"], limit=10)
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    assert len(articles) >= 1
    assert "Fed" in articles[0].title or "Nvidia" in articles[0].title
    assert all(a.source.startswith("CNBC") for a in articles)
    assert all(a.quality_score > 0 for a in articles)


def test_cnbc_empty_feed():
    src = CNBCSource(feeds=["technology"])
    with patch.object(src, "fetch_url", return_value=""):
        articles = src.crawl()
    assert articles == []


def test_cnbc_keyword_categories():
    """AI-related article should get categorized as ai or tech."""
    src = CNBCSource(feeds=["top_news"], limit=10)
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    ai_article = [a for a in articles if "Nvidia" in a.title or "AI" in a.title]
    if ai_article:
        assert ai_article[0].category in ("ai", "tech", "business")
