"""Tests for Pinboard v10.21.0 enhancements."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.pinboard import (
    PinboardSource,
    _parse_save_count,
    _extract_domain,
    _human_count,
)


# ── Unit tests for helpers ──────────────────────────────────────────

class TestParseCount:
    def test_plain_number(self):
        assert _parse_save_count("42 saves") == 42

    def test_k_suffix(self):
        assert _parse_save_count("1.5k") == 1500

    def test_m_suffix(self):
        assert _parse_save_count("2.3M") == 2300000

    def test_empty(self):
        assert _parse_save_count("") == 0

    def test_commas(self):
        assert _parse_save_count("1,234 saves") == 1234


class TestExtractDomain:
    def test_basic(self):
        assert _extract_domain("https://www.example.com/path") == "example.com"

    def test_no_www(self):
        assert _extract_domain("https://blog.example.com/x") == "blog.example.com"

    def test_empty(self):
        assert _extract_domain("") is None


class TestHumanCount:
    def test_small(self):
        assert _human_count(42) == "42"

    def test_thousands(self):
        assert _human_count(1500) == "1.5K"

    def test_millions(self):
        assert _human_count(2300000) == "2.3M"


# ── Category detection ──────────────────────────────────────────────

class TestCategorize:
    def test_ai_tags(self):
        assert PinboardSource._categorize_keywords(["machine-learning", "python"], "GPT model") == "ai"

    def test_security_tags(self):
        assert PinboardSource._categorize_keywords(["cybersecurity"], "vulnerability found") == "security"

    def test_crypto_tags(self):
        assert PinboardSource._categorize_keywords(["bitcoin", "defi"], "token launch") == "crypto"

    def test_science_tags(self):
        assert PinboardSource._categorize_keywords(["physics", "research"], "quantum experiment") == "science"

    def test_gaming_tags(self):
        assert PinboardSource._categorize_keywords(["gamedev"], "indie game release") == "gaming"

    def test_design_tags(self):
        assert PinboardSource._categorize_keywords(["ux", "figma"], "UI patterns") == "design"

    def test_business_tags(self):
        assert PinboardSource._categorize_keywords(["startup", "investing"], "funding round") == "business"

    def test_world_tags(self):
        assert PinboardSource._categorize_keywords(["geopolitics"], "election results") == "world"

    def test_culture_tags(self):
        assert PinboardSource._categorize_keywords(["philosophy", "books"], "new novel") == "culture"

    def test_health_tags(self):
        assert PinboardSource._categorize_keywords(["medicine"], "clinical trial") == "health"

    def test_education_tags(self):
        assert PinboardSource._categorize_keywords(["mooc", "learning"], "online course") == "education"

    def test_environment_tags(self):
        assert PinboardSource._categorize_keywords(["climate-change"], "renewable energy") == "environment"

    def test_generic_fallback(self):
        assert PinboardSource._categorize_keywords(["python", "linux"], "server setup") == "tech"

    def test_title_keywords(self):
        assert PinboardSource._categorize_keywords([], "New GPT-4 model released today") == "ai"


# ── Quality scoring ─────────────────────────────────────────────────

class TestQualityScore:
    def test_zero_saves(self):
        score = PinboardSource._quality_score(0, 0)
        assert 0.35 <= score <= 0.45  # baseline

    def test_high_saves(self):
        score = PinboardSource._quality_score(1000, 5)
        assert score > 0.7

    def test_tag_bonus(self):
        score_no_tags = PinboardSource._quality_score(50, 0)
        score_tags = PinboardSource._quality_score(50, 5)
        assert score_tags > score_no_tags

    def test_max_one(self):
        assert PinboardSource._quality_score(1_000_000, 10) <= 1.0


# ── Page URL building ───────────────────────────────────────────────

class TestPageUrl:
    def setup_method(self):
        self.src = PinboardSource()

    def test_popular(self):
        assert self.src._page_url("popular") == "https://pinboard.in/popular/"

    def test_recent(self):
        assert self.src._page_url("recent") == "https://pinboard.in/recent/"

    def test_popular_tag(self):
        assert self.src._page_url("popular/python") == "https://pinboard.in/popular/t:python/"


# ── Integration: crawl with mocked HTML ─────────────────────────────

MOCK_HTML = """
<html><body>
<div class="bookmark">
  <a class="bookmark_title" href="https://example.com/ai-article">AI Revolution</a>
  <a class="tag">machine-learning</a>
  <a class="tag">python</a>
  <span class="bookmark_count">150 saves</span>
</div>
<div class="bookmark">
  <a class="bookmark_title" href="https://example.com/security-post">Zero Day Found</a>
  <a class="tag">cybersecurity</a>
  <span class="bookmark_count">30 saves</span>
</div>
<div class="bookmark">
  <a class="bookmark_title" href="https://example.com/random">Random Post</a>
  <span class="bookmark_count">2 saves</span>
</div>
</body></html>
"""


class TestCrawlIntegration:
    def _mock_crawl(self, **kwargs):
        src = PinboardSource()
        with patch.object(src, "fetch_url", return_value=MOCK_HTML):
            return src.crawl(**kwargs)

    def test_basic_crawl(self):
        articles = self._mock_crawl()
        assert len(articles) == 3

    def test_categories(self):
        articles = self._mock_crawl()
        cats = {a.title: a.category for a in articles}
        assert cats["AI Revolution"] == "ai"
        assert cats["Zero Day Found"] == "security"

    def test_quality_sorted(self):
        articles = self._mock_crawl()
        scores = [a.quality_score for a in articles]
        assert scores == sorted(scores, reverse=True)

    def test_min_saves_filter(self):
        articles = self._mock_crawl(min_saves=100)
        assert len(articles) == 1
        assert articles[0].title == "AI Revolution"

    def test_min_quality_filter(self):
        articles = self._mock_crawl(min_quality=0.6)
        assert all(a.quality_score >= 0.6 for a in articles)

    def test_category_filter(self):
        articles = self._mock_crawl(category_filter=["security"])
        assert len(articles) == 1
        assert articles[0].category == "security"

    def test_global_limit(self):
        articles = self._mock_crawl(global_limit=1)
        assert len(articles) == 1

    def test_provenance_tags(self):
        articles = self._mock_crawl()
        ai_article = [a for a in articles if a.title == "AI Revolution"][0]
        assert "pinboard:page:popular" in ai_article.tags
        assert "pinboard:tag:machine-learning" in ai_article.tags
        assert "pinboard:domain:example.com" in ai_article.tags
        assert "pinboard:category:ai" in ai_article.tags

    def test_summary_content(self):
        articles = self._mock_crawl()
        ai_article = [a for a in articles if a.title == "AI Revolution"][0]
        assert "150" in ai_article.summary
        assert "example.com" in ai_article.summary

    def test_deduplication_across_pages(self):
        src = PinboardSource()
        with patch.object(src, "fetch_url", return_value=MOCK_HTML):
            articles = src.crawl(pages=["popular", "recent"])
        # Same URLs scraped twice, should be deduped
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))

    def test_filter_tags(self):
        articles = self._mock_crawl(filter_tags=["machine-learning"])
        assert len(articles) == 1
        assert articles[0].title == "AI Revolution"

    def test_exclude_tags(self):
        articles = self._mock_crawl(exclude_tags=["cybersecurity"])
        assert all(a.title != "Zero Day Found" for a in articles)
