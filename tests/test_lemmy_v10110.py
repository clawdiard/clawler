"""Tests for Lemmy source v10.11.0 enhancements."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.lemmy import (
    LemmySource, _detect_category, _quality_score, _human_count,
    LEMMY_INSTANCES, VALID_SORTS,
)


# --- Unit tests for helpers ---

class TestDetectCategory:
    def test_ai_community(self):
        assert _detect_category("machinelearning") == "ai"

    def test_ai_in_title(self):
        assert _detect_category("technology", "New LLM breakthrough announced") == "ai"

    def test_security_community(self):
        assert _detect_category("cybersecurity") == "security"

    def test_gaming_community(self):
        assert _detect_category("pcgaming") == "gaming"

    def test_science_community(self):
        assert _detect_category("astronomy") == "science"

    def test_health_community(self):
        assert _detect_category("mentalhealth") == "health"

    def test_world_community(self):
        assert _detect_category("worldnews") == "world"

    def test_culture_community(self):
        assert _detect_category("movies") == "culture"

    def test_business_community(self):
        assert _detect_category("economics") == "business"

    def test_crypto_community(self):
        assert _detect_category("bitcoin") == "crypto"

    def test_design_community(self):
        assert _detect_category("graphicdesign") == "design"

    def test_education_community(self):
        assert _detect_category("education") == "education"

    def test_generic_tech(self):
        assert _detect_category("linux") == "tech"

    def test_unknown_fallback(self):
        assert _detect_category("somethingweird") == "tech"

    def test_title_keyword_override(self):
        # Even in a generic community, AI title triggers ai category
        assert _detect_category("technology", "ChatGPT releases new model") == "ai"


class TestQualityScore:
    def test_zero_engagement(self):
        assert _quality_score(0, 0) == 0.1

    def test_negative_score(self):
        assert _quality_score(-5, 0) == 0.1

    def test_moderate_engagement(self):
        qs = _quality_score(50, 10)
        assert 0.4 < qs < 0.8

    def test_high_engagement(self):
        qs = _quality_score(500, 100)
        assert qs > 0.7

    def test_low_engagement(self):
        qs = _quality_score(5, 1)
        assert 0.1 < qs < 0.5

    def test_capped_at_one(self):
        assert _quality_score(100000, 100000) <= 1.0


class TestHumanCount:
    def test_small(self):
        assert _human_count(42) == "42"

    def test_thousands(self):
        assert _human_count(1500) == "1.5K"

    def test_millions(self):
        assert _human_count(2300000) == "2.3M"


# --- Integration tests with mocked API ---

def _make_post(id=1, title="Test Post", score=10, comments=5, community="technology",
               url=None, nsfw=False, author="testuser", published="2026-02-17T10:00:00Z"):
    return {
        "post": {
            "id": id,
            "name": title,
            "url": url,
            "published": published,
            "nsfw": nsfw,
        },
        "community": {"name": community, "title": community.title(), "nsfw": False},
        "counts": {"score": score, "comments": comments},
        "creator": {"name": author},
    }


class TestLemmyCrawl:
    @patch.object(LemmySource, "fetch_json")
    def test_basic_crawl(self, mock_fetch):
        mock_fetch.return_value = {"posts": [_make_post()]}
        src = LemmySource(instances=[LEMMY_INSTANCES[0]])
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].title == "Test Post"
        assert articles[0].quality_score > 0

    @patch.object(LemmySource, "fetch_json")
    def test_deduplication(self, mock_fetch):
        mock_fetch.return_value = {"posts": [
            _make_post(id=1, url="https://example.com/a"),
            _make_post(id=2, url="https://example.com/a"),  # same URL
        ]}
        src = LemmySource(instances=[LEMMY_INSTANCES[0]])
        articles = src.crawl()
        assert len(articles) == 1

    @patch.object(LemmySource, "fetch_json")
    def test_min_score_filter(self, mock_fetch):
        mock_fetch.return_value = {"posts": [
            _make_post(score=5),
            _make_post(id=2, title="High", score=50, url="https://other.com"),
        ]}
        src = LemmySource(instances=[LEMMY_INSTANCES[0]], min_score=10)
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].title == "High"

    @patch.object(LemmySource, "fetch_json")
    def test_min_comments_filter(self, mock_fetch):
        mock_fetch.return_value = {"posts": [
            _make_post(comments=2),
            _make_post(id=2, title="Discussed", comments=20, url="https://other.com"),
        ]}
        src = LemmySource(instances=[LEMMY_INSTANCES[0]], min_comments=10)
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].title == "Discussed"

    @patch.object(LemmySource, "fetch_json")
    def test_nsfw_filtered_by_default(self, mock_fetch):
        mock_fetch.return_value = {"posts": [_make_post(nsfw=True)]}
        src = LemmySource(instances=[LEMMY_INSTANCES[0]])
        articles = src.crawl()
        assert len(articles) == 0

    @patch.object(LemmySource, "fetch_json")
    def test_nsfw_allowed(self, mock_fetch):
        mock_fetch.return_value = {"posts": [_make_post(nsfw=True)]}
        src = LemmySource(instances=[LEMMY_INSTANCES[0]], nsfw=True)
        articles = src.crawl()
        assert len(articles) == 1

    @patch.object(LemmySource, "fetch_json")
    def test_category_filter(self, mock_fetch):
        mock_fetch.return_value = {"posts": [
            _make_post(community="cybersecurity"),
            _make_post(id=2, community="linux", url="https://other.com"),
        ]}
        src = LemmySource(instances=[LEMMY_INSTANCES[0]], category_filter=["security"])
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].category == "security"

    @patch.object(LemmySource, "fetch_json")
    def test_exclude_communities(self, mock_fetch):
        mock_fetch.return_value = {"posts": [
            _make_post(community="memes"),
            _make_post(id=2, community="linux", url="https://other.com"),
        ]}
        src = LemmySource(instances=[LEMMY_INSTANCES[0]], exclude_communities=["memes"])
        articles = src.crawl()
        assert len(articles) == 1
        assert "lemmy:community:linux" in articles[0].tags

    @patch.object(LemmySource, "fetch_json")
    def test_global_limit(self, mock_fetch):
        mock_fetch.return_value = {"posts": [
            _make_post(id=i, url=f"https://example.com/{i}") for i in range(10)
        ]}
        src = LemmySource(instances=[LEMMY_INSTANCES[0]], global_limit=3)
        articles = src.crawl()
        assert len(articles) == 3

    @patch.object(LemmySource, "fetch_json")
    def test_quality_sorted(self, mock_fetch):
        mock_fetch.return_value = {"posts": [
            _make_post(id=1, title="Low", score=1, comments=0),
            _make_post(id=2, title="High", score=500, comments=100, url="https://other.com"),
        ]}
        src = LemmySource(instances=[LEMMY_INSTANCES[0]])
        articles = src.crawl()
        assert articles[0].title == "High"

    @patch.object(LemmySource, "fetch_json")
    def test_provenance_tags(self, mock_fetch):
        mock_fetch.return_value = {"posts": [_make_post(community="linux", comments=15)]}
        src = LemmySource(instances=[LEMMY_INSTANCES[0]])
        articles = src.crawl()
        tags = articles[0].tags
        assert any("lemmy:instance:" in t for t in tags)
        assert any("lemmy:community:linux" in t for t in tags)
        assert any("lemmy:category:" in t for t in tags)
        assert "lemmy:has-discussion" in tags

    @patch.object(LemmySource, "fetch_json")
    def test_community_specific_fetch(self, mock_fetch):
        mock_fetch.return_value = {"posts": [_make_post(community="python")]}
        src = LemmySource(instances=[LEMMY_INSTANCES[0]], communities=["python"])
        articles = src.crawl()
        assert len(articles) == 1
        # Verify the API was called with community_name param
        call_url = mock_fetch.call_args[0][0]
        assert "community_name=python" in call_url

    @patch.object(LemmySource, "fetch_json")
    def test_summary_format(self, mock_fetch):
        mock_fetch.return_value = {"posts": [_make_post(score=1500, comments=42)]}
        src = LemmySource(instances=[LEMMY_INSTANCES[0]])
        articles = src.crawl()
        summary = articles[0].summary
        assert "⬆ 1.5K" in summary
        assert "💬 42" in summary
        assert "📂" in summary
        assert "🏠" in summary

    @patch.object(LemmySource, "fetch_json")
    def test_min_quality_filter(self, mock_fetch):
        mock_fetch.return_value = {"posts": [
            _make_post(id=1, score=1, comments=0),
            _make_post(id=2, title="Quality", score=200, comments=50, url="https://q.com"),
        ]}
        src = LemmySource(instances=[LEMMY_INSTANCES[0]], min_quality=0.5)
        articles = src.crawl()
        assert all(a.quality_score >= 0.5 for a in articles)

    def test_default_instances(self):
        assert len(LEMMY_INSTANCES) == 8

    def test_valid_sorts(self):
        assert "Hot" in VALID_SORTS
        assert "TopWeek" in VALID_SORTS
        assert "MostComments" in VALID_SORTS

    @patch.object(LemmySource, "fetch_json")
    def test_sort_param_in_url(self, mock_fetch):
        mock_fetch.return_value = {"posts": []}
        src = LemmySource(instances=[LEMMY_INSTANCES[0]], sort="TopWeek")
        src.crawl()
        call_url = mock_fetch.call_args[0][0]
        assert "sort=TopWeek" in call_url

    @patch.object(LemmySource, "fetch_json")
    def test_invalid_sort_defaults_hot(self, mock_fetch):
        mock_fetch.return_value = {"posts": []}
        src = LemmySource(instances=[LEMMY_INSTANCES[0]], sort="Invalid")
        src.crawl()
        call_url = mock_fetch.call_args[0][0]
        assert "sort=Hot" in call_url

    @patch.object(LemmySource, "fetch_json")
    def test_fallback_url_when_no_external_link(self, mock_fetch):
        mock_fetch.return_value = {"posts": [_make_post(url=None)]}
        src = LemmySource(instances=[LEMMY_INSTANCES[0]])
        articles = src.crawl()
        assert "/post/" in articles[0].url

    @patch.object(LemmySource, "fetch_json")
    def test_cross_instance_dedup(self, mock_fetch):
        mock_fetch.return_value = {"posts": [_make_post(url="https://shared.com/article")]}
        src = LemmySource(instances=[LEMMY_INSTANCES[0], LEMMY_INSTANCES[1]])
        articles = src.crawl()
        assert len(articles) == 1
