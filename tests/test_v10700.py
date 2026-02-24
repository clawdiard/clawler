"""Tests for v10.70.0 enhancements.

- TheAtlantic: quality_score based on section + prominent author boost
- TheHackerNews: quality_score with CVE detection, topic specificity, prominent authors
- RSS: 20 new feeds in 4 categories (nuclear_energy, cartography, supply_chain, remote_work)
"""
from unittest.mock import patch, MagicMock
import pytest


class TestTheAtlanticQualityScore:
    """The Atlantic should now produce articles with quality_score."""

    def test_prominent_author_boost(self):
        from clawler.sources.theatlantic import PROMINENT_AUTHORS
        assert "ed yong" in PROMINENT_AUTHORS
        assert "derek thompson" in PROMINENT_AUTHORS

    def test_category_keywords_exist(self):
        from clawler.sources.theatlantic import _CATEGORY_KEYWORDS
        assert "tech" in _CATEGORY_KEYWORDS
        assert "security" in _CATEGORY_KEYWORDS
        assert "investigative" in _CATEGORY_KEYWORDS

    def test_detect_category_tech(self):
        from clawler.sources.theatlantic import _detect_category
        assert _detect_category("AI Is Changing Everything", "", "technology") == "tech"

    def test_detect_category_section_fallback(self):
        from clawler.sources.theatlantic import _detect_category
        assert _detect_category("A Random Title", "", "politics") == "world"
        assert _detect_category("A Random Title", "", "science") == "science"


class TestTheHackerNewsQualityScore:
    """The Hacker News should now produce quality_score with topic-aware scoring."""

    def test_classify_compliance(self):
        from clawler.sources.thehackernews import _classify_security_topic
        tags = _classify_security_topic("New NIST Framework", "compliance audit regulation")
        assert "compliance" in tags

    def test_classify_threat_intel(self):
        from clawler.sources.thehackernews import _classify_security_topic
        tags = _classify_security_topic("APT29 Campaign Targets NATO", "threat actor espionage")
        assert "threat-intel" in tags

    def test_compute_quality_base(self):
        from clawler.sources.thehackernews import _compute_quality
        q = _compute_quality("Generic Security News", "Some summary", "unknown", [])
        assert 0.69 < q < 0.75

    def test_compute_quality_cve_boost(self):
        from clawler.sources.thehackernews import _compute_quality
        q = _compute_quality("Critical CVE-2026-1234 Exploited", "actively exploited", "unknown", ["vulnerability"])
        assert q > 0.80  # CVE + critical + topic tag

    def test_compute_quality_prominent_author(self):
        from clawler.sources.thehackernews import _compute_quality
        q1 = _compute_quality("News", "summary", "ravie lakshmanan", [])
        q2 = _compute_quality("News", "summary", "unknown", [])
        assert q1 > q2


class TestNewRSSFeeds:
    """Verify the 20 new RSS feeds are registered."""

    def test_new_categories_present(self):
        from clawler.sources.rss import DEFAULT_FEEDS
        categories = {f["category"] for f in DEFAULT_FEEDS}
        assert "nuclear_energy" in categories
        assert "cartography" in categories
        assert "supply_chain" in categories
        assert "remote_work" in categories

    def test_five_feeds_per_new_category(self):
        from clawler.sources.rss import DEFAULT_FEEDS
        for cat in ("nuclear_energy", "cartography", "supply_chain", "remote_work"):
            count = sum(1 for f in DEFAULT_FEEDS if f["category"] == cat)
            assert count >= 5, f"{cat} has only {count} feeds"

    def test_total_feed_count_increased(self):
        from clawler.sources.rss import DEFAULT_FEEDS
        assert len(DEFAULT_FEEDS) >= 769
