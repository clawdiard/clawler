"""Tests for enhanced HackerNoon source (v10.55.0)."""
import math
from datetime import datetime, timezone
from unittest.mock import patch
from xml.etree import ElementTree as ET

import pytest

from clawler.sources.hackernoon import (
    HackerNoonSource,
    _compute_quality,
    _detect_category,
    _estimate_reading_time,
    _fmt_count,
    BASE_FEED,
    TAGGED_FEEDS,
)


# ── Helpers ──────────────────────────────────────────────────────────

def _make_item(title="Test Article", link="https://hackernoon.com/test",
               author="Jane Doe", tags=None, description="Short desc.",
               content_words=500, pub_date="Mon, 20 Feb 2026 12:00:00 GMT"):
    """Build a single RSS <item> XML string."""
    tags = tags or ["programming", "javascript"]
    cats = "".join(f"<category>{t}</category>" for t in tags)
    body = " ".join(["word"] * content_words)
    return f"""<item>
        <title>{title}</title>
        <link>{link}</link>
        <dc:creator><![CDATA[{author}]]></dc:creator>
        <description><![CDATA[{description}]]></description>
        <content:encoded><![CDATA[<p>{body}</p>]]></content:encoded>
        {cats}
        <pubDate>{pub_date}</pubDate>
    </item>"""


def _make_feed(items_xml: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"
         xmlns:dc="http://purl.org/dc/elements/1.1/"
         xmlns:content="http://purl.org/rss/1.0/modules/content/">
    <channel><title>Hacker Noon</title>
    {items_xml}
    </channel></rss>"""


# ── Category detection ───────────────────────────────────────────────

class TestCategoryDetection:
    def test_ai_from_tags(self):
        assert _detect_category(["machine-learning", "python"]) == "ai"

    def test_ai_from_title(self):
        assert _detect_category([], "Building a ChatGPT Plugin") == "ai"

    def test_security(self):
        assert _detect_category(["cybersecurity", "hacking"]) == "security"

    def test_crypto(self):
        assert _detect_category(["blockchain", "ethereum"]) == "crypto"

    def test_business(self):
        assert _detect_category(["startup", "venture-capital"]) == "business"

    def test_gaming(self):
        assert _detect_category(["game-development", "unity"]) == "gaming"

    def test_design(self):
        assert _detect_category(["ux", "figma"]) == "design"

    def test_health(self):
        assert _detect_category(["healthcare", "biotech"]) == "health"

    def test_science(self):
        assert _detect_category(["physics", "quantum"]) == "science"

    def test_world(self):
        assert _detect_category(["geopolitics", "regulation"]) == "world"

    def test_culture(self):
        assert _detect_category(["entertainment", "film"]) == "culture"

    def test_education(self):
        assert _detect_category(["edtech", "online-learning"]) == "education"

    def test_environment(self):
        assert _detect_category(["climate-change", "renewable"]) == "environment"

    def test_generic_tech_fallback(self):
        assert _detect_category(["javascript", "react"]) == "tech"

    def test_unknown_fallback(self):
        assert _detect_category(["random-stuff"]) == "tech"

    def test_specific_over_generic(self):
        # AI tag should beat generic tech tags
        assert _detect_category(["python", "machine-learning", "javascript"]) == "ai"

    def test_title_keywords(self):
        assert _detect_category([], "How Ransomware Attacks Work") == "security"


# ── Reading time ─────────────────────────────────────────────────────

class TestReadingTime:
    def test_short_article(self):
        assert _estimate_reading_time("word " * 100) == 1

    def test_medium_article(self):
        rt = _estimate_reading_time("word " * 1000)
        assert 3 <= rt <= 5

    def test_long_article(self):
        rt = _estimate_reading_time("word " * 3000)
        assert 12 <= rt <= 14

    def test_strips_html(self):
        html = "<p>word</p> " * 500
        rt = _estimate_reading_time(html)
        assert rt >= 1


# ── Quality scoring ──────────────────────────────────────────────────

class TestQualityScoring:
    def test_short_no_tags_generic(self):
        q = _compute_quality(1, 0, False)
        assert 0 <= q < 0.3

    def test_long_many_tags_specific(self):
        q = _compute_quality(15, 10, True)
        assert q > 0.6

    def test_specific_boost(self):
        q_generic = _compute_quality(5, 3, False)
        q_specific = _compute_quality(5, 3, True)
        assert q_specific > q_generic

    def test_max_capped_at_1(self):
        q = _compute_quality(100, 50, True)
        assert q <= 1.0

    def test_monotonic_with_reading_time(self):
        q1 = _compute_quality(2, 3, False)
        q2 = _compute_quality(10, 3, False)
        assert q2 > q1


# ── Format helpers ───────────────────────────────────────────────────

class TestFmtCount:
    def test_small(self):
        assert _fmt_count(42) == "42"

    def test_thousands(self):
        assert _fmt_count(1500) == "1.5K"

    def test_millions(self):
        assert _fmt_count(2_300_000) == "2.3M"


# ── Crawl integration ───────────────────────────────────────────────

class TestCrawl:
    def _mock_source(self, feed_xml, **kwargs):
        src = HackerNoonSource(**kwargs)
        src.fetch_url = lambda url: feed_xml
        return src

    def test_basic_crawl(self):
        xml = _make_feed(_make_item())
        src = self._mock_source(xml, feeds=["latest"])
        arts = src.crawl()
        assert len(arts) == 1
        assert arts[0].title == "Test Article"
        assert arts[0].author == "Jane Doe"
        assert arts[0].quality_score > 0

    def test_deduplication_across_feeds(self):
        item = _make_item()
        xml = _make_feed(item)
        src = HackerNoonSource(feeds=["ai", "programming"])
        src.fetch_url = lambda url: xml
        arts = src.crawl()
        assert len(arts) == 1

    def test_min_reading_time_filter(self):
        xml = _make_feed(_make_item(content_words=50))  # ~0.2 min
        src = self._mock_source(xml, feeds=["latest"], min_reading_time=3)
        arts = src.crawl()
        assert len(arts) == 0

    def test_min_quality_filter(self):
        xml = _make_feed(_make_item(content_words=50, tags=[]))
        src = self._mock_source(xml, feeds=["latest"], min_quality=0.9)
        arts = src.crawl()
        assert len(arts) == 0

    def test_category_filter(self):
        items = _make_item(tags=["machine-learning"], link="https://h.com/1") + \
                _make_item(title="JS Tips", tags=["javascript"], link="https://h.com/2")
        xml = _make_feed(items)
        src = self._mock_source(xml, feeds=["latest"], category_filter=["ai"])
        arts = src.crawl()
        assert all(a.category == "ai" for a in arts)

    def test_global_limit(self):
        items = "".join(_make_item(link=f"https://h.com/{i}") for i in range(10))
        xml = _make_feed(items)
        src = self._mock_source(xml, feeds=["latest"], global_limit=3)
        arts = src.crawl()
        assert len(arts) == 3

    def test_quality_sorted(self):
        items = _make_item(link="https://h.com/short", content_words=50, tags=[]) + \
                _make_item(link="https://h.com/long", content_words=2000, tags=["ai", "deep-learning", "python"])
        xml = _make_feed(items)
        src = self._mock_source(xml, feeds=["latest"])
        arts = src.crawl()
        assert len(arts) == 2
        assert arts[0].quality_score >= arts[1].quality_score

    def test_rich_summary(self):
        xml = _make_feed(_make_item())
        src = self._mock_source(xml, feeds=["latest"])
        arts = src.crawl()
        assert "✍️ Jane Doe" in arts[0].summary
        assert "📖" in arts[0].summary
        assert "min read" in arts[0].summary

    def test_provenance_tags(self):
        xml = _make_feed(_make_item(tags=["ai", "python"]))
        src = self._mock_source(xml, feeds=["latest"])
        arts = src.crawl()
        tags = arts[0].tags
        assert any("hackernoon:feed:" in t for t in tags)
        assert any("hackernoon:tag:" in t for t in tags)
        assert any("hackernoon:author:" in t for t in tags)

    def test_category_provenance_tag(self):
        xml = _make_feed(_make_item(tags=["machine-learning"]))
        src = self._mock_source(xml, feeds=["latest"])
        arts = src.crawl()
        assert "hackernoon:category:ai" in arts[0].tags

    def test_timestamp_parsed(self):
        xml = _make_feed(_make_item())
        src = self._mock_source(xml, feeds=["latest"])
        arts = src.crawl()
        assert arts[0].timestamp is not None
        assert arts[0].timestamp.tzinfo is not None

    def test_xml_parse_error_returns_empty(self):
        src = HackerNoonSource(feeds=["latest"])
        src.fetch_url = lambda url: "not xml"
        arts = src.crawl()
        assert arts == []

    def test_empty_feed_returns_empty(self):
        src = HackerNoonSource(feeds=["latest"])
        src.fetch_url = lambda url: None
        arts = src.crawl()
        assert arts == []


# ── Registration ─────────────────────────────────────────────────────

class TestRegistered:
    def test_in_sources_init(self):
        from clawler.sources import __all__
        assert "HackerNoonSource" in __all__

    def test_class_loads(self):
        from clawler.sources import HackerNoonSource as cls
        assert cls.name == "hackernoon"

    def test_in_registry(self):
        from clawler.registry import SOURCES
        names = [e.key for e in SOURCES]
        assert "hackernoon" in names
