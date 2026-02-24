"""Tests for enhanced Engadget, ScienceDaily, TechRadar sources (v10.78.0)."""
import pytest
from unittest.mock import patch, MagicMock

from clawler.sources.engadget import EngadgetSource, _detect_category as engadget_detect, PROMINENT_AUTHORS as ENGADGET_AUTHORS
from clawler.sources.sciencedaily import ScienceDailySource, _detect_category as sd_detect
from clawler.sources.techradar import TechRadarSource, _detect_category as tr_detect


# ── Engadget ──────────────────────────────────────────────────

class TestEngadgetCategoryDetection:
    def test_ai_detected(self):
        assert engadget_detect("OpenAI launches new GPT model", "") == "ai"

    def test_gaming_detected(self):
        assert engadget_detect("Nintendo Switch 2 review", "") == "gaming"

    def test_security_detected(self):
        assert engadget_detect("Major data breach affects millions", "") == "security"

    def test_mobile_detected(self):
        assert engadget_detect("Samsung Galaxy S26 unveiled", "") == "mobile"

    def test_automotive_detected(self):
        assert engadget_detect("Tesla launches new EV model", "") == "automotive"

    def test_fallback_none(self):
        assert engadget_detect("Some random headline", "no keywords") is None

    def test_prominent_authors_not_empty(self):
        assert len(ENGADGET_AUTHORS) >= 10


class TestEngadgetSource:
    def test_init_defaults(self):
        src = EngadgetSource()
        assert src.limit == 20
        assert src.global_limit is None
        assert src.min_quality == 0.0
        assert src.category_filter is None

    def test_init_custom(self):
        src = EngadgetSource(limit=5, global_limit=10, min_quality=0.3, category_filter=["ai", "gaming"])
        assert src.limit == 5
        assert src.global_limit == 10
        assert src.min_quality == 0.3
        assert src.category_filter == {"ai", "gaming"}

    def test_name(self):
        assert EngadgetSource().name == "engadget"


# ── ScienceDaily ──────────────────────────────────────────────

class TestScienceDailyCategoryDetection:
    def test_ai_detected(self):
        assert sd_detect("New artificial intelligence breakthrough", "") == "ai"

    def test_space_detected(self):
        assert sd_detect("NASA discovers new exoplanet", "") == "space"

    def test_health_detected(self):
        assert sd_detect("New cancer treatment shows promise", "") == "health"

    def test_environment_detected(self):
        assert sd_detect("Climate change accelerating", "") == "environment"

    def test_biology_detected(self):
        assert sd_detect("CRISPR gene editing advance", "") == "biology"

    def test_fallback_none(self):
        assert sd_detect("Some random headline", "") is None


class TestScienceDailySource:
    def test_init_defaults(self):
        src = ScienceDailySource()
        assert src.limit == 15
        assert src.global_limit is None
        assert len(src.feeds) == 10  # expanded from 7

    def test_init_custom(self):
        src = ScienceDailySource(limit=5, global_limit=20, min_quality=0.2, category_filter=["space"])
        assert src.limit == 5
        assert src.category_filter == {"space"}

    def test_name(self):
        assert ScienceDailySource().name == "sciencedaily"


# ── TechRadar ─────────────────────────────────────────────────

class TestTechRadarCategoryDetection:
    def test_ai_detected(self):
        assert tr_detect("ChatGPT gets major upgrade", "") == "ai"

    def test_security_detected(self):
        assert tr_detect("Best VPN services for 2026", "") == "security"

    def test_gaming_detected(self):
        assert tr_detect("PS5 Pro review roundup", "") == "gaming"

    def test_mobile_detected(self):
        assert tr_detect("iPhone 18 leak reveals design", "") == "mobile"

    def test_smart_home_detected(self):
        assert tr_detect("Best smart home devices", "") == "smart_home"

    def test_fallback_none(self):
        assert tr_detect("Random article title", "") is None


class TestTechRadarSource:
    def test_init_defaults(self):
        src = TechRadarSource()
        assert src.limit == 20
        assert src.global_limit is None

    def test_init_custom(self):
        src = TechRadarSource(limit=10, global_limit=30, min_quality=0.2, category_filter=["ai"])
        assert src.limit == 10
        assert src.category_filter == {"ai"}

    def test_name(self):
        assert TechRadarSource().name == "techradar"


# ── Quality score propagation ─────────────────────────────────

class TestQualityScorePresent:
    """Verify all three enhanced sources set quality_score on Articles."""

    SAMPLE_ENGADGET_XML = """<?xml version="1.0" encoding="UTF-8"?>
    <rss><channel><item>
        <title>Test AI article</title>
        <link>https://engadget.com/test-1</link>
        <description>OpenAI launches new model</description>
        <pubDate>Mon, 24 Feb 2026 08:00:00 +0000</pubDate>
    </item></channel></rss>"""

    def test_engadget_quality_score(self):
        src = EngadgetSource(limit=5)
        with patch.object(src, "fetch_url", return_value=self.SAMPLE_ENGADGET_XML):
            articles = src.crawl()
            assert len(articles) >= 1
            assert articles[0].quality_score > 0

    SAMPLE_SD_XML = """<?xml version="1.0" encoding="UTF-8"?>
    <rss><channel>
    <item><title><![CDATA[NASA finds water on Mars]]></title>
    <link>https://sciencedaily.com/test-1</link>
    <description><![CDATA[Exciting discovery]]></description>
    <pubDate>Mon, 24 Feb 2026 08:00:00 +0000</pubDate></item>
    </channel></rss>"""

    def test_sciencedaily_quality_score(self):
        src = ScienceDailySource(limit=5)
        with patch.object(src, "fetch_url", return_value=self.SAMPLE_SD_XML):
            articles = src.crawl()
            assert len(articles) >= 1
            assert articles[0].quality_score > 0

    SAMPLE_TR_XML = """<?xml version="1.0" encoding="UTF-8"?>
    <rss><channel><item>
        <title>Best VPN for privacy in 2026</title>
        <link>https://techradar.com/test-1</link>
        <description>Top picks for security</description>
        <pubDate>Mon, 24 Feb 2026 08:00:00 +0000</pubDate>
    </item></channel></rss>"""

    def test_techradar_quality_score(self):
        src = TechRadarSource(limit=5)
        with patch.object(src, "fetch_url", return_value=self.SAMPLE_TR_XML):
            articles = src.crawl()
            assert len(articles) >= 1
            assert articles[0].quality_score > 0
