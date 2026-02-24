"""Tests for quality scoring enhancements in v10.84.0.

Covers: DZone, freeCodeCamp, Changelog, Hashnode, Phys.org
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


class TestDZoneQualityScoring:
    """Test DZone quality scoring."""

    def test_compute_quality_ai_topic(self):
        from clawler.sources.dzone import _compute_quality
        score = _compute_quality("ai", "Deep Dive into Machine Learning Pipelines", "A comprehensive guide...", ["AI", "ML"])
        assert 0.0 <= score <= 1.0
        assert score > 0.3  # AI topic + quality signals + keyword hit

    def test_compute_quality_general_short_title(self):
        from clawler.sources.dzone import _compute_quality
        score = _compute_quality("general", "Quick tip", "", [])
        assert 0.0 <= score <= 1.0
        assert score < 0.2  # Low prominence, short title, no categories

    def test_compute_quality_security_keywords(self):
        from clawler.sources.dzone import _compute_quality
        score = _compute_quality("security", "Authentication Best Practices for OAuth 2.0",
                                 "How to handle vulnerability scanning", ["security", "oauth"])
        assert score > 0.4  # Security topic + keywords + quality signals

    def test_quality_score_set_on_article(self):
        from clawler.sources.dzone import DZoneSource
        src = DZoneSource(feeds=[{"url": "https://feeds.dzone.com/ai", "topic": "ai"}])

        mock_xml = """<rss><channel>
        <item>
          <title><![CDATA[Best Practices for Kubernetes Deployments]]></title>
          <link>https://dzone.com/articles/k8s-deploy</link>
          <description><![CDATA[A guide to production deployments]]></description>
          <pubDate>Mon, 24 Feb 2026 12:00:00 GMT</pubDate>
          <dc:creator><![CDATA[John Doe]]></dc:creator>
          <category><![CDATA[DevOps]]></category>
        </item>
        </channel></rss>"""

        with patch.object(src, 'fetch_url', return_value=mock_xml):
            articles = src.crawl()
            assert len(articles) == 1
            assert articles[0].quality_score > 0  # quality_score is set
            assert articles[0].quality_score <= 1.0

    def test_expanded_feeds(self):
        from clawler.sources.dzone import DZONE_FEEDS
        topics = [f["topic"] for f in DZONE_FEEDS]
        assert "agile" in topics
        assert "integration" in topics
        assert "big-data" in topics

    def test_keyword_category_override(self):
        from clawler.sources.dzone import DZoneSource
        src = DZoneSource(feeds=[{"url": "https://feeds.dzone.com/home", "topic": "general"}])

        mock_xml = """<rss><channel>
        <item>
          <title>Understanding Machine Learning Algorithms</title>
          <link>https://dzone.com/articles/ml-algos</link>
          <description>Deep learning and neural network fundamentals</description>
          <pubDate>Mon, 24 Feb 2026 12:00:00 GMT</pubDate>
        </item>
        </channel></rss>"""

        with patch.object(src, 'fetch_url', return_value=mock_xml):
            articles = src.crawl()
            assert len(articles) == 1
            assert articles[0].category == "ai"  # overridden from keyword detection


class TestFreeCodeCampQualityScoring:
    """Test freeCodeCamp quality scoring."""

    def test_compute_quality_tutorial(self):
        from clawler.sources.freecodecamp import _compute_quality
        score = _compute_quality(
            "The Complete Guide to React Hooks — A Step-by-Step Tutorial",
            ["react", "javascript", "tutorial"],
            "Quincy Larson"
        )
        assert score > 0.4  # Multiple signals + tags + author + long title

    def test_compute_quality_minimal(self):
        from clawler.sources.freecodecamp import _compute_quality
        score = _compute_quality("Short post", [], "")
        assert score < 0.25  # Minimal article

    def test_ai_category_mapping(self):
        from clawler.sources.freecodecamp import TAG_CATEGORY_MAP
        assert TAG_CATEGORY_MAP["machine-learning"] == "ai"
        assert TAG_CATEGORY_MAP["deep-learning"] == "ai"

    def test_quality_score_on_article(self):
        from clawler.sources.freecodecamp import FreeCodeCampSource
        src = FreeCodeCampSource(limit=5)

        mock_rss = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel>
        <item>
          <title>How to Build a REST API with Python Flask</title>
          <link>https://www.freecodecamp.org/news/rest-api-flask/</link>
          <description>A complete tutorial on building REST APIs</description>
          <pubDate>Mon, 24 Feb 2026 12:00:00 GMT</pubDate>
          <dc:creator>John Smith</dc:creator>
        </item>
        </channel></rss>"""

        with patch.object(src, 'fetch_url', return_value=mock_rss):
            articles = src.crawl()
            assert len(articles) == 1
            assert articles[0].quality_score > 0


class TestChangelogQualityScoring:
    """Test Changelog quality scoring."""

    def test_compute_quality_news(self):
        from clawler.sources.changelog import _compute_quality
        score = _compute_quality(
            "Why open source maintainers are burning out",
            ["open-source", "career"],
            "Adam Stacoviak",
            0.25
        )
        assert score > 0.4

    def test_feeds_have_prominence(self):
        from clawler.sources.changelog import CHANGELOG_FEEDS
        for feed_url, label, prominence in CHANGELOG_FEEDS:
            assert isinstance(prominence, float)
            assert 0 < prominence <= 1.0


class TestHashnodeQualityScoring:
    """Test Hashnode quality scoring."""

    def test_compute_quality(self):
        from clawler.sources.hashnode import _compute_quality
        score = _compute_quality(
            "A Complete Guide to Building Microservices with Node.js",
            ["hashnode:javascript", "hashnode:webdev", "hashnode:devblog"],
            "dev_blogger",
            0.25
        )
        assert score > 0.4

    def test_expanded_feeds(self):
        from clawler.sources.hashnode import HASHNODE_FEEDS
        feed_names = [f[1] for f in HASHNODE_FEEDS]
        assert "Hashnode React" in feed_names
        assert "Hashnode Cloud" in feed_names

    def test_keyword_category_ai(self):
        from clawler.sources.hashnode import KEYWORD_CATEGORIES
        assert "ai" in KEYWORD_CATEGORIES
        assert "machine learning" in KEYWORD_CATEGORIES["ai"]


class TestPhysOrgQualityScoring:
    """Test Phys.org quality scoring."""

    def test_compute_quality_breaking(self):
        from clawler.sources.physorg import _compute_quality
        score = _compute_quality(
            "breaking",
            "Scientists discover new breakthrough in quantum computing that could revolutionize technology",
            "Researchers at MIT have found evidence of a novel quantum state..."
        )
        assert score > 0.5  # Breaking + multiple title signals + long title + summary

    def test_compute_quality_minimal(self):
        from clawler.sources.physorg import _compute_quality
        score = _compute_quality("ecology", "Short update", "Brief")
        assert score < 0.3

    def test_expanded_feeds(self):
        from clawler.sources.physorg import PHYSORG_FEEDS
        sections = [f["section"] for f in PHYSORG_FEEDS]
        assert "medicine" in sections
        assert "math" in sections
        assert "ecology" in sections

    def test_quality_score_on_article(self):
        from clawler.sources.physorg import PhysOrgSource
        src = PhysOrgSource(feeds=[{"url": "https://phys.org/rss-feed/space-news/", "section": "space"}])

        mock_xml = """<rss><channel>
        <item>
          <title>New discovery reveals first evidence of water on distant exoplanet</title>
          <link>https://phys.org/news/2026-02-water-exoplanet.html</link>
          <description>Astronomers using the James Webb Space Telescope have found evidence...</description>
          <pubDate>Mon, 24 Feb 2026 10:00:00 GMT</pubDate>
        </item>
        </channel></rss>"""

        with patch.object(src, 'fetch_url', return_value=mock_xml):
            articles = src.crawl()
            assert len(articles) == 1
            assert articles[0].quality_score > 0.3
            assert articles[0].category == "science"
