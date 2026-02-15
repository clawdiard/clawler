"""Tests for YouTube RSS source."""
import xml.etree.ElementTree as ET
from unittest.mock import patch
from clawler.sources.youtube import YouTubeSource, DEFAULT_CHANNELS

SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/"
      xmlns="http://www.w3.org/2005/Atom">
  <title>Fireship</title>
  <entry>
    <title>JavaScript in 100 Seconds</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=abc123"/>
    <published>2026-02-15T12:00:00+00:00</published>
    <media:group>
      <media:description>Learn JavaScript fast.</media:description>
      <media:community>
        <media:statistics views="1000000"/>
      </media:community>
    </media:group>
  </entry>
  <entry>
    <title>Rust in 100 Seconds</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=def456"/>
    <published>2026-02-14T10:00:00+00:00</published>
    <media:group>
      <media:description>Learn Rust fast.</media:description>
    </media:group>
  </entry>
</feed>"""


def test_youtube_crawl():
    """Test YouTube source parses RSS feed correctly."""
    src = YouTubeSource(channels={"UC_test": "TestChannel"}, limit_per_channel=5)
    with patch.object(src, "fetch_url", return_value=SAMPLE_FEED):
        articles = src.crawl()
    assert len(articles) == 2
    assert articles[0].title == "JavaScript in 100 Seconds"
    assert "youtube.com/watch" in articles[0].url
    assert articles[0].author == "TestChannel"
    assert "youtube" in articles[0].tags
    assert articles[0].timestamp is not None


def test_youtube_empty_feed():
    """Test YouTube source handles empty/error gracefully."""
    src = YouTubeSource(channels={"UC_test": "TestChannel"})
    with patch.object(src, "fetch_url", return_value=""):
        articles = src.crawl()
    assert articles == []


def test_youtube_default_channels():
    """Ensure default channels list is populated."""
    assert len(DEFAULT_CHANNELS) > 10


def test_youtube_limit():
    """Test limit_per_channel is respected."""
    src = YouTubeSource(channels={"UC_test": "TestChannel"}, limit_per_channel=1)
    with patch.object(src, "fetch_url", return_value=SAMPLE_FEED):
        articles = src.crawl()
    assert len(articles) == 1
