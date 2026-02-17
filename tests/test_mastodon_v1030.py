"""Tests for Mastodon source v10.3.0 enhancements."""
import json
from unittest.mock import patch, MagicMock
import pytest
from clawler.sources.mastodon import (
    MastodonSource, _guess_category, _format_count,
    _quality_score_links, _quality_score_status, _quality_score_hashtag,
    INSTANCE_CATEGORY_BIAS,
)


# --- Category detection ---

def test_specific_category_ai():
    assert _guess_category("New LLM breakthrough", "", "") == "ai"

def test_specific_category_security():
    assert _guess_category("Critical CVE in OpenSSL", "", "") == "security"

def test_specific_category_crypto():
    assert _guess_category("Bitcoin hits new high", "", "") == "crypto"

def test_specific_over_generic():
    """AI keyword should win over generic tech even if both match."""
    assert _guess_category("AI transformer code on GitHub", "", "") == "ai"

def test_generic_tech_fallback():
    assert _guess_category("New Rust compiler release on GitHub", "", "") == "tech"

def test_instance_bias_fosstodon():
    assert _guess_category("Some random post", "", "", instance="fosstodon.org") == "tech"

def test_instance_bias_infosec():
    assert _guess_category("Some random post", "", "", instance="infosec.exchange") == "security"

def test_hashtag_category_boost():
    """Hashtags should influence category detection."""
    assert _guess_category("Check this out", "", "", hashtags=["machinelearning", "ai"]) == "ai"

def test_general_fallback():
    assert _guess_category("Nice weather today", "", "") == "general"

def test_world_category():
    assert _guess_category("Parliament votes on new legislation", "", "") == "world"

def test_culture_category():
    assert _guess_category("New album from indie band", "", "") == "culture"

def test_gaming_category():
    assert _guess_category("Steam summer sale begins", "", "") == "gaming"

def test_design_category():
    assert _guess_category("New Figma update for designers", "", "") == "design"

def test_health_category():
    assert _guess_category("FDA approves new cancer therapy", "", "") == "health"


# --- Format count ---

def test_format_count_small():
    assert _format_count(42) == "42"

def test_format_count_thousands():
    assert _format_count(1500) == "1.5K"

def test_format_count_millions():
    assert _format_count(2300000) == "2.3M"


# --- Quality scores ---

def test_quality_score_links_zero():
    assert _quality_score_links(0, 0) == 0.0

def test_quality_score_links_moderate():
    score = _quality_score_links(100, 50)
    assert 0.3 < score < 0.9

def test_quality_score_links_high():
    score = _quality_score_links(1000, 500)
    assert score > 0.7

def test_quality_score_status_zero():
    assert _quality_score_status(0, 0, 0) == 0.0

def test_quality_score_status_moderate():
    score = _quality_score_status(50, 100, 20)
    assert 0.3 < score < 0.9

def test_quality_score_hashtag_zero():
    assert _quality_score_hashtag(0, 0) == 0.0

def test_quality_score_hashtag_popular():
    score = _quality_score_hashtag(500, 200)
    assert score > 0.5


# --- Crawl integration ---

def _mock_fetch_json(url):
    if "trends/links" in url:
        return [
            {
                "url": "https://example.com/article",
                "title": "AI breakthrough with transformers",
                "description": "New model beats benchmarks",
                "provider_name": "TechNews",
                "language": "en",
                "history": [
                    {"uses": "50", "accounts": "30"},
                    {"uses": "40", "accounts": "25"},
                ],
            }
        ]
    if "trends/statuses" in url:
        return [
            {
                "url": "https://mastodon.social/@user/123",
                "content": "<p>Check out this new <a>#security</a> tool!</p>",
                "language": "en",
                "account": {"display_name": "Alice", "acct": "alice"},
                "reblogs_count": 20,
                "favourites_count": 50,
                "replies_count": 5,
                "created_at": "2026-02-17T03:00:00Z",
                "tags": [{"name": "security"}, {"name": "infosec"}],
            }
        ]
    if "trends/tags" in url:
        return [
            {
                "name": "machinelearning",
                "url": "https://mastodon.social/tags/machinelearning",
                "history": [
                    {"uses": "200", "accounts": "100"},
                    {"uses": "150", "accounts": "80"},
                ],
            }
        ]
    return []


@patch.object(MastodonSource, "fetch_json", side_effect=_mock_fetch_json)
def test_crawl_links_quality_score(mock):
    src = MastodonSource(instances=["mastodon.social"], include_statuses=False, include_hashtags=False)
    articles = src.crawl()
    assert len(articles) == 1
    assert articles[0].quality_score > 0
    assert articles[0].category == "ai"
    assert any("mastodon:instance:" in t for t in articles[0].tags)
    assert any("mastodon:provider:" in t for t in articles[0].tags)


@patch.object(MastodonSource, "fetch_json", side_effect=_mock_fetch_json)
def test_crawl_statuses_quality_score(mock):
    src = MastodonSource(instances=["mastodon.social"], include_links=False, include_hashtags=False)
    articles = src.crawl()
    assert len(articles) == 1
    assert articles[0].quality_score > 0
    assert articles[0].category == "security"
    assert any("mastodon:author:alice" in t for t in articles[0].tags)
    assert any("mastodon:hashtag:security" in t for t in articles[0].tags)


@patch.object(MastodonSource, "fetch_json", side_effect=_mock_fetch_json)
def test_crawl_hashtags_quality_score(mock):
    src = MastodonSource(instances=["mastodon.social"], include_links=False, include_statuses=False)
    articles = src.crawl()
    assert len(articles) == 1
    assert articles[0].quality_score > 0
    assert articles[0].category == "ai"
    assert any("mastodon:hashtag:machinelearning" in t for t in articles[0].tags)


@patch.object(MastodonSource, "fetch_json", side_effect=_mock_fetch_json)
def test_category_filter(mock):
    src = MastodonSource(instances=["mastodon.social"], category_filter=["security"])
    articles = src.crawl()
    assert all(a.category == "security" for a in articles)


@patch.object(MastodonSource, "fetch_json", side_effect=_mock_fetch_json)
def test_min_quality_filter(mock):
    src = MastodonSource(instances=["mastodon.social"], min_quality=0.99)
    articles = src.crawl()
    assert len(articles) == 0  # nothing scores that high


@patch.object(MastodonSource, "fetch_json", side_effect=_mock_fetch_json)
def test_global_limit(mock):
    src = MastodonSource(instances=["mastodon.social"], global_limit=1)
    articles = src.crawl()
    assert len(articles) <= 1


@patch.object(MastodonSource, "fetch_json", side_effect=_mock_fetch_json)
def test_language_filter(mock):
    src = MastodonSource(instances=["mastodon.social"], language="de",
                         include_statuses=False, include_hashtags=False)
    articles = src.crawl()
    assert len(articles) == 0  # our mock data is "en"


@patch.object(MastodonSource, "fetch_json", side_effect=_mock_fetch_json)
def test_sorted_by_quality(mock):
    src = MastodonSource(instances=["mastodon.social"])
    articles = src.crawl()
    scores = [a.quality_score for a in articles]
    assert scores == sorted(scores, reverse=True)


@patch.object(MastodonSource, "fetch_json", side_effect=_mock_fetch_json)
def test_format_count_in_summary(mock):
    src = MastodonSource(instances=["mastodon.social"], include_statuses=False, include_hashtags=False)
    articles = src.crawl()
    # Should use formatted counts, not raw numbers
    assert "shares" in articles[0].summary
