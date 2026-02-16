"""Tests for Lobsters source enhancements (v9.4.0):
- Tag filtering (filter_tags, exclude_tags)
- min_comments filtering
- Quality scoring
- Domain extraction
- Specific-over-generic category preference
"""
import math
from unittest.mock import patch

from clawler.sources.lobsters import (
    LobstersSource,
    _compute_quality,
    _extract_domain,
    _map_category,
)


def _make_item(title="Test", url="https://example.com/test", score=10,
               comment_count=5, tags=None, submitter="alice"):
    return {
        "title": title,
        "url": url,
        "score": score,
        "comment_count": comment_count,
        "tags": tags or ["python"],
        "comments_url": f"https://lobste.rs/s/abc/{title.lower().replace(' ', '-')}",
        "short_id": "abc",
        "submitter_user": {"username": submitter},
        "created_at": "2026-02-16T12:00:00Z",
    }


class TestTagFiltering:
    def test_filter_tags_includes_matching(self):
        src = LobstersSource(filter_tags=["security"])
        with patch.object(src, "fetch_json", return_value=[
            _make_item(tags=["security", "linux"]),
            _make_item(title="Other", url="https://other.com", tags=["python"]),
        ]):
            articles = src.crawl()
        assert len(articles) == 1
        assert "security" in articles[0].title or articles[0].category == "security"

    def test_exclude_tags_removes_matching(self):
        src = LobstersSource(exclude_tags=["meta"])
        with patch.object(src, "fetch_json", return_value=[
            _make_item(tags=["meta"]),
            _make_item(title="Good", url="https://good.com", tags=["rust"]),
        ]):
            articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].title == "Good"

    def test_filter_and_exclude_combined(self):
        src = LobstersSource(filter_tags=["python", "rust"], exclude_tags=["meta"])
        with patch.object(src, "fetch_json", return_value=[
            _make_item(tags=["python", "meta"]),  # has filter tag but also excluded
            _make_item(title="Rust post", url="https://rust.com", tags=["rust"]),
        ]):
            articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].title == "Rust post"


class TestMinComments:
    def test_filters_below_threshold(self):
        src = LobstersSource(min_comments=10)
        with patch.object(src, "fetch_json", return_value=[
            _make_item(comment_count=3),
            _make_item(title="Popular", url="https://pop.com", comment_count=15),
        ]):
            articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].title == "Popular"


class TestQualityScoring:
    def test_high_score_high_quality(self):
        q = _compute_quality(50, 20)
        assert q > 0.7

    def test_low_score_low_quality(self):
        q = _compute_quality(1, 0)
        assert q < 0.6

    def test_zero_score(self):
        q = _compute_quality(0, 0)
        assert 0.25 <= q <= 0.35

    def test_capped_at_one(self):
        q = _compute_quality(10000, 10000)
        assert q <= 1.0

    def test_quality_in_article(self):
        src = LobstersSource()
        with patch.object(src, "fetch_json", return_value=[
            _make_item(score=50, comment_count=20),
        ]):
            articles = src.crawl()
        assert articles[0].quality_score > 0.7


class TestDomainExtraction:
    def test_extracts_domain(self):
        assert _extract_domain("https://www.example.com/page") == "example.com"

    def test_strips_www(self):
        assert _extract_domain("https://www.blog.dev/post") == "blog.dev"

    def test_empty_on_bad_url(self):
        assert _extract_domain("") == ""

    def test_domain_in_summary(self):
        src = LobstersSource(include_domain=True, include_comments_url=False)
        with patch.object(src, "fetch_json", return_value=[
            _make_item(url="https://blog.rust-lang.org/post"),
        ]):
            articles = src.crawl()
        assert "🔗blog.rust-lang.org" in articles[0].summary

    def test_domain_tag_added(self):
        src = LobstersSource()
        with patch.object(src, "fetch_json", return_value=[
            _make_item(url="https://example.com/post"),
        ]):
            articles = src.crawl()
        assert "lobsters-domain:example.com" in articles[0].tags

    def test_lobsters_domain_hidden(self):
        """Self-links (lobste.rs) should not show domain in summary."""
        src = LobstersSource(include_domain=True, include_comments_url=False)
        item = _make_item()
        item["url"] = ""  # force fallback to comments_url
        with patch.object(src, "fetch_json", return_value=[item]):
            articles = src.crawl()
        if articles:
            assert "🔗lobste.rs" not in articles[0].summary


class TestCategoryPreference:
    def test_specific_over_generic(self):
        """security tag should win over linux tag (specific > generic)."""
        assert _map_category(["linux", "security"]) == "security"

    def test_ai_over_python(self):
        assert _map_category(["python", "ai"]) == "ai"

    def test_generic_fallback(self):
        assert _map_category(["rust"]) == "tech"

    def test_design_is_specific(self):
        assert _map_category(["css", "web"]) == "design"

    def test_unknown_tags_default_tech(self):
        assert _map_category(["unknowntag123"]) == "tech"
