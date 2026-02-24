"""Tests for Forbes source."""
from unittest.mock import patch
from clawler.sources.forbes import ForbesSource, FORBES_FEEDS

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel><title>Forbes</title>
<item>
  <title>The Best AI Startups To Watch In 2026</title>
  <link>https://www.forbes.com/sites/author/2026/02/24/ai-startups/</link>
  <description>These emerging companies are reshaping artificial intelligence.</description>
  <pubDate>Mon, 24 Feb 2026 10:00:00 GMT</pubDate>
</item>
<item>
  <title>How Remote Work Is Changing Real Estate Markets</title>
  <link>https://www.forbes.com/sites/author/2026/02/24/remote-work-real-estate/</link>
  <description>The shift to remote work continues to reshape housing demand.</description>
  <pubDate>Mon, 24 Feb 2026 09:00:00 GMT</pubDate>
</item>
</channel></rss>"""


def test_forbes_feed_config():
    assert len(FORBES_FEEDS) >= 8
    for feed in FORBES_FEEDS:
        assert "url" in feed
        assert "section" in feed
        assert "category" in feed


def test_forbes_crawl():
    src = ForbesSource(sections=["Innovation"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    assert len(articles) == 2
    assert "AI Startups" in articles[0].title or "Remote Work" in articles[0].title
    assert all(a.source.startswith("Forbes") for a in articles)


def test_forbes_empty_feed():
    src = ForbesSource(sections=["Innovation"])
    with patch.object(src, "fetch_url", return_value=""):
        articles = src.crawl()
    assert articles == []
