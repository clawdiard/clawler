"""Tests for Economist source."""
from unittest.mock import patch
from clawler.sources.economist import EconomistSource, ECONOMIST_FEEDS

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel><title>The Economist</title>
<item>
  <title>The world economy faces a new era of uncertainty</title>
  <link>https://www.economist.com/briefing/2026/02/24/world-economy</link>
  <description>Trade tensions and shifting alliances are reshaping global markets.</description>
  <pubDate>Mon, 24 Feb 2026 00:01:00 GMT</pubDate>
</item>
<item>
  <title>How quantum computing could transform drug discovery</title>
  <link>https://www.economist.com/science/2026/02/24/quantum-drug-discovery</link>
  <description>Advances in quantum hardware are opening new frontiers in pharmaceutical research.</description>
  <pubDate>Sun, 23 Feb 2026 23:00:00 GMT</pubDate>
</item>
</channel></rss>"""


def test_economist_feed_config():
    assert len(ECONOMIST_FEEDS) >= 10
    for key, feed in ECONOMIST_FEEDS.items():
        assert "url" in feed


def test_economist_crawl():
    src = EconomistSource(sections=["briefing"], limit=10)
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    assert len(articles) == 2
    assert all(a.source.startswith("The Economist") for a in articles)
    assert all(a.quality_score > 0 for a in articles)


def test_economist_empty():
    src = EconomistSource(sections=["briefing"])
    with patch.object(src, "fetch_url", return_value=""):
        articles = src.crawl()
    assert articles == []
