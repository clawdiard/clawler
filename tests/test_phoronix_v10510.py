"""Tests for Phoronix source (v10.51.0)."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.phoronix import (
    PhoronixSource,
    _detect_category,
    _detect_section,
    _compute_quality,
    _parse_timestamp,
    _human_count,
)

# ── Sample RSS XML ──

SAMPLE_RSS = """<?xml version="1.0"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
 <channel>
  <title>Phoronix</title>
  <item>
   <title>Linux 7.0 Shows Significant PostgreSQL Performance Gains On AMD EPYC</title>
   <link>https://www.phoronix.com/review/linux-70-amd-epyc-turin</link>
   <guid>https://www.phoronix.com/review/linux-70-amd-epyc-turin</guid>
   <description>When beginning some early Linux 7.0 kernel benchmarking this week for looking at its performance.</description>
   <pubDate>Fri, 20 Feb 2026 10:30:00 -0500</pubDate>
   <dc:creator>Michael Larabel</dc:creator>
  </item>
  <item>
   <title>GNOME 50 Lands Updated Wayland Color Management v2 Support</title>
   <link>https://www.phoronix.com/news/GNOME-50-Color-Management-v2</link>
   <guid>https://www.phoronix.com/news/GNOME-50-Color-Management-v2</guid>
   <description>Following GNOME 50's Mutter merging sdr-native color mode support for wide color gamut displays.</description>
   <pubDate>Fri, 20 Feb 2026 09:21:22 -0500</pubDate>
   <dc:creator>Michael Larabel</dc:creator>
  </item>
  <item>
   <title>New Vulnerability Found In Intel CPU Spectre Mitigations</title>
   <link>https://www.phoronix.com/news/Intel-Spectre-CVE-2026-1234</link>
   <guid>https://www.phoronix.com/news/Intel-Spectre-CVE-2026-1234</guid>
   <description>A new spectre vulnerability has been discovered affecting Intel processors with security implications.</description>
   <pubDate>Fri, 20 Feb 2026 08:00:00 -0500</pubDate>
   <dc:creator>Michael Larabel</dc:creator>
  </item>
  <item>
   <title>Steam Gaming On Linux Hits New Record With Proton Updates</title>
   <link>https://www.phoronix.com/news/Steam-Linux-Gaming-Record</link>
   <guid>https://www.phoronix.com/news/Steam-Linux-Gaming-Record</guid>
   <description>Steam gaming on Linux has hit a new all-time record with the latest Proton and Wine updates.</description>
   <pubDate>Fri, 20 Feb 2026 07:00:00 -0500</pubDate>
   <dc:creator>Michael Larabel</dc:creator>
  </item>
  <item>
   <title>PyTorch 3.0 Brings Major CUDA And ROCm Performance Improvements</title>
   <link>https://www.phoronix.com/news/PyTorch-3-CUDA-ROCm</link>
   <guid>https://www.phoronix.com/news/PyTorch-3-CUDA-ROCm</guid>
   <description>PyTorch 3.0 brings significant deep learning inference performance improvements for CUDA and ROCm.</description>
   <pubDate>Fri, 20 Feb 2026 06:00:00 -0500</pubDate>
   <dc:creator>Michael Larabel</dc:creator>
  </item>
  <item>
   <title></title>
   <link></link>
   <description>Empty item that should be skipped.</description>
  </item>
 </channel>
</rss>"""

EMPTY_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Phoronix</title></channel></rss>"""


# ── Unit tests for helper functions ──

class TestDetectCategory:
    def test_ai_keywords(self):
        assert _detect_category("PyTorch CUDA deep learning", "") == "ai"

    def test_security_keywords(self):
        assert _detect_category("New vulnerability CVE-2026", "security exploit") == "security"

    def test_gaming_keywords(self):
        assert _detect_category("Steam Proton gaming performance", "") == "gaming"

    def test_design_keywords(self):
        assert _detect_category("Wayland color management HDR display", "") == "design"

    def test_crypto_keywords(self):
        assert _detect_category("Bitcoin mining on Linux", "") == "crypto"

    def test_environment_keywords(self):
        assert _detect_category("Power consumption energy efficiency", "") == "environment"

    def test_generic_tech_fallback(self):
        assert _detect_category("Linux kernel 7.0 driver update", "") == "tech"

    def test_generic_gpu_cpu(self):
        assert _detect_category("AMD GPU benchmark results", "") == "tech"

    def test_business_keywords(self):
        assert _detect_category("Red Hat Enterprise market share acquisition", "") == "business"

    def test_science_keywords(self):
        assert _detect_category("HPC supercomputer simulation scientific computing", "") == "science"


class TestDetectSection:
    def test_review(self):
        assert _detect_section("https://www.phoronix.com/review/linux-70-amd") == "review"

    def test_news(self):
        assert _detect_section("https://www.phoronix.com/news/GNOME-50") == "news"

    def test_benchmark(self):
        assert _detect_section("https://www.phoronix.com/benchmark/cpu-2026") == "benchmark"

    def test_scan(self):
        assert _detect_section("https://www.phoronix.com/scan/something") == "scan"

    def test_unknown_defaults_to_news(self):
        assert _detect_section("https://www.phoronix.com/") == "news"


class TestComputeQuality:
    def test_review_base(self):
        q = _compute_quality("review", "tech")
        assert q == 0.75

    def test_news_base(self):
        q = _compute_quality("news", "tech")
        assert q == 0.50

    def test_specific_category_boost(self):
        q_generic = _compute_quality("news", "tech")
        q_specific = _compute_quality("news", "ai")
        assert q_specific > q_generic

    def test_review_specific_capped(self):
        q = _compute_quality("review", "security")
        assert q <= 0.95


class TestParseTimestamp:
    def test_valid_rfc2822(self):
        ts = _parse_timestamp("Fri, 20 Feb 2026 10:30:00 -0500")
        assert ts is not None
        assert ts.year == 2026

    def test_empty_string(self):
        assert _parse_timestamp("") is None

    def test_invalid_string(self):
        assert _parse_timestamp("not a date") is None


class TestHumanCount:
    def test_millions(self):
        assert _human_count(2_500_000) == "2.5M"

    def test_thousands(self):
        assert _human_count(1_500) == "1.5K"

    def test_small(self):
        assert _human_count(42) == "42"


# ── Integration tests for PhoronixSource ──

class TestPhoronixSource:
    def _make_source(self, **kwargs):
        return PhoronixSource(**kwargs)

    @patch.object(PhoronixSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_basic_crawl(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        # 5 valid items (empty one skipped)
        assert len(articles) == 5
        assert all(a.url for a in articles)
        assert all(a.title for a in articles)

    @patch.object(PhoronixSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_author_extraction(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        for a in articles:
            assert a.author == "Michael Larabel"

    @patch.object(PhoronixSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_section_detection(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        # First article is a review
        review = [a for a in articles if "review" in a.url]
        assert len(review) == 1
        assert "phoronix:section:review" in review[0].tags

    @patch.object(PhoronixSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_category_detection_security(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        security = [a for a in articles if a.category == "security"]
        assert len(security) >= 1

    @patch.object(PhoronixSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_category_detection_gaming(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        gaming = [a for a in articles if a.category == "gaming"]
        assert len(gaming) >= 1

    @patch.object(PhoronixSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_category_detection_ai(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        ai = [a for a in articles if a.category == "ai"]
        assert len(ai) >= 1

    @patch.object(PhoronixSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_quality_review_higher_than_news(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        reviews = [a for a in articles if "review" in a.url]
        news = [a for a in articles if "news" in a.url and a.category == "tech"]
        if reviews and news:
            assert reviews[0].quality_score >= news[0].quality_score

    @patch.object(PhoronixSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_min_quality_filter(self, mock_fetch):
        src = self._make_source(min_quality=0.70)
        articles = src.crawl()
        assert all(a.quality_score >= 0.70 for a in articles)

    @patch.object(PhoronixSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_category_filter(self, mock_fetch):
        src = self._make_source(category_filter="security")
        articles = src.crawl()
        assert all(a.category == "security" for a in articles)

    @patch.object(PhoronixSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_global_limit(self, mock_fetch):
        src = self._make_source(global_limit=2)
        articles = src.crawl()
        assert len(articles) <= 2

    @patch.object(PhoronixSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_sorted_by_quality(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        scores = [a.quality_score for a in articles]
        assert scores == sorted(scores, reverse=True)

    @patch.object(PhoronixSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_provenance_tags(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        for a in articles:
            assert any(t.startswith("phoronix:section:") for t in a.tags)
            assert any(t.startswith("phoronix:category:") for t in a.tags)
            assert any(t.startswith("phoronix:author:") for t in a.tags)

    @patch.object(PhoronixSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_summary_contains_author_and_section(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        for a in articles:
            assert "✍️" in a.summary
            assert "📰" in a.summary

    @patch.object(PhoronixSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_timestamp_parsed(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        for a in articles:
            assert a.timestamp is not None
            assert a.timestamp.year == 2026

    @patch.object(PhoronixSource, "fetch_url", return_value=EMPTY_RSS)
    def test_empty_feed(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        assert articles == []

    @patch.object(PhoronixSource, "fetch_url", return_value="not xml")
    def test_invalid_xml(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        assert articles == []

    @patch.object(PhoronixSource, "fetch_url", side_effect=Exception("Network error"))
    def test_network_error(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        assert articles == []

    @patch.object(PhoronixSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_deduplication(self, mock_fetch):
        """Duplicate URLs in feed should be deduplicated."""
        src = self._make_source()
        articles = src.crawl()
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))

    @patch.object(PhoronixSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_source_name_includes_section(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        review = [a for a in articles if "review" in a.url]
        if review:
            assert "Review" in review[0].source

    @patch.object(PhoronixSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_empty_items_skipped(self, mock_fetch):
        """Items with empty title/link should be skipped."""
        src = self._make_source()
        articles = src.crawl()
        assert all(a.title for a in articles)
        assert all(a.url for a in articles)


class TestPhoronixRegistered:
    def test_in_registry(self):
        from clawler.registry import get_entry
        entry = get_entry("phoronix")
        assert entry is not None
        assert entry.display_name == "Phoronix"

    def test_class_loads(self):
        from clawler.registry import get_entry
        entry = get_entry("phoronix")
        cls = entry.load_class()
        assert cls is PhoronixSource

    def test_in_sources_init(self):
        from clawler.sources import PhoronixSource as PS
        assert PS is not None
