"""Tests for YouTube source enhancements v9.9.0 — quality scoring, keyword categories, shorts filter, playlists."""
import math
from unittest.mock import patch, MagicMock
from clawler.sources.youtube import (
    YouTubeSource, _detect_category_from_title, _format_views,
    _quality_score, _channel_category, DEFAULT_CHANNELS,
)

SAMPLE_ENTRY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/"
      xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <yt:videoId>abc123</yt:videoId>
    <title>{title}</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=abc123"/>
    <published>2026-02-17T00:00:00+00:00</published>
    <author><name>Test Channel</name></author>
    <media:group>
      <media:description>A test video description</media:description>
      <media:community>
        <media:starRating count="100" average="4.5"/>
        <media:statistics views="{views}"/>
      </media:community>
    </media:group>
  </entry>
</feed>"""


def test_keyword_category_ai():
    assert _detect_category_from_title("How GPT-4 changed machine learning forever") == "ai"

def test_keyword_category_security():
    assert _detect_category_from_title("Critical zero-day exploit found in Linux kernel") == "security"

def test_keyword_category_crypto():
    assert _detect_category_from_title("Bitcoin hits new ATH as ethereum surges") == "crypto"

def test_keyword_category_science():
    assert _detect_category_from_title("NASA telescope discovers new exoplanet") == "science"

def test_keyword_category_none():
    assert _detect_category_from_title("My morning routine vlog") is None

def test_keyword_category_business():
    assert _detect_category_from_title("This startup just raised $50M in venture capital") == "business"

def test_format_views_millions():
    assert _format_views(1_500_000) == "1.5M"

def test_format_views_thousands():
    assert _format_views(42_300) == "42.3K"

def test_format_views_small():
    assert _format_views(500) == "500"

def test_quality_score_high_views():
    score = _quality_score(1_000_000, "Test")
    assert 0.7 <= score <= 0.85

def test_quality_score_low_views():
    score = _quality_score(100, "Test")
    assert 0.15 <= score <= 0.35

def test_quality_score_zero_views():
    assert _quality_score(0, "Test") == 0.3

def test_channel_category_mapping():
    assert _channel_category("Fireship") == "tech"
    assert _channel_category("AI Explained") == "ai"
    assert _channel_category("Vsauce") == "science"
    assert _channel_category("CNN") == "world"
    assert _channel_category("SciShow") == "science"
    assert _channel_category("sentdex") == "ai"
    assert _channel_category("Random Channel") == "general"

def test_new_channels_added():
    src = YouTubeSource()
    names = set(src.channels.values())
    assert "SciShow" in names
    assert "Computerphile" in names
    assert "sentdex" in names
    assert "TLDR News Global" in names
    assert "Jordan Harbinger" in names

def test_exclude_shorts_default():
    src = YouTubeSource()
    assert src.exclude_shorts is True

def test_playlist_support():
    src = YouTubeSource(playlists={"PLtest123": "My Playlist"})
    assert src.playlists == {"PLtest123": "My Playlist"}

def test_min_views_filter():
    src = YouTubeSource(min_views=1000)
    assert src.min_views == 1000

def test_category_filter():
    src = YouTubeSource(category_filter=["AI", "Science"])
    assert src.category_filter == ["ai", "science"]

def test_global_limit():
    src = YouTubeSource(limit=10)
    assert src.limit == 10

def test_parse_entry_with_views():
    src = YouTubeSource(channels={"UCtest": "Test Channel"})
    xml = SAMPLE_ENTRY_XML.format(title="Testing GPT-4 performance", views="500000")
    with patch.object(src, "fetch_url", return_value=xml):
        articles = src.crawl()
    assert len(articles) == 1
    a = articles[0]
    assert a.category == "ai"  # keyword detection from title
    assert "👁 500.0K" in a.summary
    assert a.quality_score > 0.5
    assert "yt:id:abc123" in a.tags
    assert "yt:category:ai" in a.tags

def test_parse_entry_star_rating():
    src = YouTubeSource(channels={"UCtest": "Test Channel"})
    xml = SAMPLE_ENTRY_XML.format(title="A cool video about stuff", views="1000")
    with patch.object(src, "fetch_url", return_value=xml):
        articles = src.crawl()
    assert len(articles) == 1
    assert "⭐ 4.5" in articles[0].summary

def test_min_views_filters_out():
    src = YouTubeSource(channels={"UCtest": "Test Channel"}, min_views=100000)
    xml = SAMPLE_ENTRY_XML.format(title="Low views video", views="500")
    with patch.object(src, "fetch_url", return_value=xml):
        articles = src.crawl()
    assert len(articles) == 0

def test_dedup_across_channels():
    """Same video from two channels should be deduped."""
    src = YouTubeSource(channels={"UCtest1": "Ch1", "UCtest2": "Ch2"})
    xml = SAMPLE_ENTRY_XML.format(title="Duplicate Video", views="1000")
    with patch.object(src, "fetch_url", return_value=xml):
        articles = src.crawl()
    assert len(articles) == 1

def test_category_filter_applied():
    src = YouTubeSource(channels={"UCtest": "Test"}, category_filter=["science"])
    xml = SAMPLE_ENTRY_XML.format(title="GPT-4 AI breakthrough", views="1000")
    with patch.object(src, "fetch_url", return_value=xml):
        articles = src.crawl()
    # category would be "ai", filtered out
    assert len(articles) == 0
