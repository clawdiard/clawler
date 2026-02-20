"""Tests for enhanced Wired source v10.48.0."""
import pytest
from unittest.mock import patch
from clawler.sources.wired import (
    WiredSource, WIRED_FEEDS, PROMINENT_AUTHORS,
    _detect_category, _compute_quality, KEYWORD_CATEGORIES,
)

# Minimal RSS item XML for building test feeds
def _make_item(title="Test Article", url="https://www.wired.com/story/test",
               desc="A test article.", author=None, categories=None):
    parts = [f"<item><title>{title}</title><link>{url}</link>"]
    if desc:
        parts.append(f"<description>{desc}</description>")
    if author:
        parts.append(f"<dc:creator>{author}</dc:creator>")
    for cat in (categories or []):
        parts.append(f"<category>{cat}</category>")
    parts.append("</item>")
    return "".join(parts)


def _make_feed(*items):
    return (
        '<?xml version="1.0"?><rss xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<channel><title>Wired</title>" + "".join(items) + "</channel></rss>"
    )


class TestCategoryDetection:
    def test_ai_keywords(self):
        assert _detect_category("OpenAI launches GPT-4 successor", "", [], "tech") == "ai"

    def test_security_keywords(self):
        assert _detect_category("Major ransomware attack hits hospitals", "", [], "tech") == "security"

    def test_crypto_keywords(self):
        assert _detect_category("Bitcoin hits new all-time high", "", [], "tech") == "crypto"

    def test_health_keywords(self):
        assert _detect_category("New vaccine shows promise in clinical trials", "", [], "tech") == "health"

    def test_science_keywords(self):
        assert _detect_category("NASA discovers new exoplanet", "", [], "tech") == "science"

    def test_gaming_keywords(self):
        assert _detect_category("Nintendo reveals next console", "", [], "tech") == "gaming"

    def test_environment_keywords(self):
        assert _detect_category("Climate change drives record carbon emissions", "", [], "tech") == "environment"

    def test_falls_back_to_section(self):
        assert _detect_category("Regular article title", "", [], "business") == "business"

    def test_description_keywords(self):
        assert _detect_category("Regular title", "artificial intelligence breakthrough", [], "tech") == "ai"

    def test_rss_tags_keywords(self):
        assert _detect_category("Regular title", "", ["cybersecurity", "hacking"], "tech") == "security"

    def test_world_keywords(self):
        assert _detect_category("Election results shake government", "", [], "tech") == "world"

    def test_education_keywords(self):
        assert _detect_category("University curriculum changes", "", [], "tech") == "education"


class TestQualityScoring:
    def test_first_position_high_prominence(self):
        score = _compute_quality(0, 0.55, False, "tech")
        assert 0.5 <= score <= 0.6

    def test_position_decay(self):
        s0 = _compute_quality(0, 0.50, False, "tech")
        s5 = _compute_quality(5, 0.50, False, "tech")
        s10 = _compute_quality(10, 0.50, False, "tech")
        assert s0 > s5 > s10

    def test_prominent_author_boost(self):
        base = _compute_quality(0, 0.50, False, "tech")
        boosted = _compute_quality(0, 0.50, True, "tech")
        assert boosted > base
        assert abs(boosted - base - 0.08) < 0.001

    def test_boosted_category(self):
        base = _compute_quality(0, 0.50, False, "tech")
        boosted = _compute_quality(0, 0.50, False, "ai")
        assert boosted > base

    def test_score_clamped_to_one(self):
        score = _compute_quality(0, 1.0, True, "ai")
        assert score <= 1.0

    def test_low_prominence_low_score(self):
        score = _compute_quality(15, 0.35, False, "tech")
        assert score < 0.2


class TestWiredSource:
    def test_default_feeds(self):
        src = WiredSource()
        assert "main" in src._feeds
        assert "security" in src._feeds
        assert len(src._feeds) == 6

    def test_custom_feeds(self):
        src = WiredSource(feeds=["science", "backchannel"])
        assert src._feeds == ["science", "backchannel"]

    def test_invalid_feeds_filtered(self):
        src = WiredSource(feeds=["science", "nonexistent"])
        assert src._feeds == ["science"]

    def test_exclude_sections(self):
        src = WiredSource(exclude_sections=["gear", "reviews"])
        assert "gear" not in src._feeds or "gear" in src.exclude_sections


class TestCrawl:
    def _mock_crawl(self, items_by_section, **kwargs):
        src = WiredSource(**kwargs)
        feeds_data = {}
        for section, items in items_by_section.items():
            feeds_data[WIRED_FEEDS[section]["url"]] = _make_feed(*items)

        def mock_fetch(url):
            return feeds_data.get(url, "")

        with patch.object(src, "fetch_url", side_effect=mock_fetch):
            return src.crawl()

    def test_basic_crawl(self):
        articles = self._mock_crawl(
            {"main": [_make_item("Test", "https://wired.com/1")]},
            feeds=["main"],
        )
        assert len(articles) == 1
        assert articles[0].title == "Test"

    def test_deduplication_across_sections(self):
        item = _make_item("Same Article", "https://wired.com/same")
        articles = self._mock_crawl(
            {"main": [item], "science": [item]},
            feeds=["main", "science"],
        )
        assert len(articles) == 1

    def test_min_quality_filter(self):
        items = [_make_item(f"Art {i}", f"https://wired.com/{i}") for i in range(15)]
        articles = self._mock_crawl(
            {"main": items},
            feeds=["main"], min_quality=0.5,
        )
        assert all((a.quality_score or 0) >= 0.5 for a in articles)

    def test_category_filter(self):
        articles = self._mock_crawl(
            {"main": [
                _make_item("AI breakthrough with artificial intelligence", "https://wired.com/ai1"),
                _make_item("Regular tech news", "https://wired.com/tech1"),
            ]},
            feeds=["main"], category_filter=["ai"],
        )
        assert all(a.category == "ai" for a in articles)

    def test_global_limit(self):
        items = [_make_item(f"Art {i}", f"https://wired.com/{i}") for i in range(10)]
        articles = self._mock_crawl(
            {"main": items},
            feeds=["main"], global_limit=3,
        )
        assert len(articles) == 3

    def test_quality_sorted(self):
        items = [_make_item(f"Art {i}", f"https://wired.com/{i}") for i in range(5)]
        articles = self._mock_crawl(
            {"main": items},
            feeds=["main"],
        )
        scores = [a.quality_score for a in articles]
        assert scores == sorted(scores, reverse=True)

    def test_prominent_author_tagged(self):
        articles = self._mock_crawl(
            {"security": [_make_item("Test", "https://wired.com/1", author="Andy Greenberg")]},
            feeds=["security"],
        )
        assert len(articles) == 1
        assert "wired:prominent-author" in articles[0].tags

    def test_non_prominent_author_no_tag(self):
        articles = self._mock_crawl(
            {"main": [_make_item("Test", "https://wired.com/1", author="Random Writer")]},
            feeds=["main"],
        )
        assert "wired:prominent-author" not in articles[0].tags

    def test_rss_categories_as_tags(self):
        articles = self._mock_crawl(
            {"main": [_make_item("Test", "https://wired.com/1", categories=["Gadgets", "Reviews"])]},
            feeds=["main"],
        )
        assert "wired:tag:gadgets" in articles[0].tags
        assert "wired:tag:reviews" in articles[0].tags

    def test_section_tag(self):
        articles = self._mock_crawl(
            {"science": [_make_item("Test", "https://wired.com/1")]},
            feeds=["science"],
        )
        assert "wired:section:science" in articles[0].tags

    def test_summary_includes_section(self):
        articles = self._mock_crawl(
            {"security": [_make_item("Test", "https://wired.com/1", author="Lily Hay Newman")]},
            feeds=["security"],
        )
        assert "📰 Security" in articles[0].summary
        assert "✍️ Lily Hay Newman" in articles[0].summary

    def test_exclude_sections_works(self):
        articles = self._mock_crawl(
            {"main": [_make_item("Main", "https://wired.com/1")],
             "gear": [_make_item("Gear", "https://wired.com/2")]},
            feeds=["main", "gear"], exclude_sections=["gear"],
        )
        assert len(articles) == 1
        assert articles[0].title == "Main"

    def test_empty_feed_handled(self):
        src = WiredSource(feeds=["main"])
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []


class TestFeedConfig:
    def test_all_feeds_have_required_keys(self):
        for name, info in WIRED_FEEDS.items():
            assert "url" in info
            assert "category" in info
            assert "prominence" in info
            assert 0 < info["prominence"] <= 1.0

    def test_ten_sections(self):
        assert len(WIRED_FEEDS) == 10

    def test_prominent_authors_lowercase(self):
        for author in PROMINENT_AUTHORS:
            assert author == author.lower()
