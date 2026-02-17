"""Tests for enhanced Stack Overflow / Stack Exchange source (v10.4.0)."""
import json
import math
from unittest.mock import patch, MagicMock
import pytest
from clawler.sources.stackoverflow import (
    StackOverflowSource, _detect_category, _quality_score, _human_count, _decode_entities,
    DEFAULT_SITES, KEYWORD_CATEGORIES,
)


# --- Helper fixtures ---

def _make_item(title="Test Q", link="https://stackoverflow.com/q/1", score=10,
               answer_count=3, view_count=500, is_answered=True, tags=None,
               accepted_answer_id=123, creation_date=1700000000,
               owner_name="testuser"):
    return {
        "title": title, "link": link, "score": score,
        "answer_count": answer_count, "view_count": view_count,
        "is_answered": is_answered, "tags": tags or ["python"],
        "accepted_answer_id": accepted_answer_id,
        "creation_date": creation_date,
        "owner": {"display_name": owner_name},
    }


def _mock_source(items_by_site=None, **kwargs):
    """Create source with mocked fetch_json returning items per site."""
    src = StackOverflowSource(**kwargs)
    items_by_site = items_by_site or {}

    def fake_fetch(url):
        for site, items in items_by_site.items():
            if f"site={site}" in url:
                return {"items": items}
        return {"items": []}

    src.fetch_json = MagicMock(side_effect=fake_fetch)
    return src


# --- Unit tests for helpers ---

class TestHumanCount:
    def test_small(self):
        assert _human_count(42) == "42"

    def test_thousands(self):
        assert _human_count(1500) == "1.5K"

    def test_millions(self):
        assert _human_count(2_300_000) == "2.3M"

    def test_zero(self):
        assert _human_count(0) == "0"


class TestDecodeEntities:
    def test_all(self):
        assert _decode_entities("&#39;&amp;&quot;&lt;&gt;") == "'&\"<>"


class TestDetectCategory:
    def test_ai_tags(self):
        assert _detect_category(["tensorflow", "python"]) == "ai"

    def test_security_tags(self):
        assert _detect_category(["encryption", "java"]) == "security"

    def test_crypto_tags(self):
        assert _detect_category(["solidity", "ethereum"]) == "crypto"

    def test_design_tags(self):
        assert _detect_category(["css", "tailwind-css"]) == "design"

    def test_gaming_tags(self):
        assert _detect_category(["unity", "c#"]) == "gaming"

    def test_fallback_to_site_default(self):
        assert _detect_category(["python", "flask"], "tech") == "tech"

    def test_fallback_custom(self):
        assert _detect_category(["bash"], "security") == "security"


class TestQualityScore:
    def test_zero_engagement(self):
        assert _quality_score(0, 0, 0, False) == 0.0

    def test_high_engagement(self):
        qs = _quality_score(500, 20, 100_000, True)
        assert qs > 0.7

    def test_answered_bonus(self):
        q1 = _quality_score(10, 2, 100, False)
        q2 = _quality_score(10, 2, 100, True)
        assert q2 > q1

    def test_range(self):
        qs = _quality_score(1000, 50, 1_000_000, True)
        assert 0.0 <= qs <= 1.0


# --- Integration tests ---

class TestBasicCrawl:
    def test_single_site(self):
        src = _mock_source(
            items_by_site={"stackoverflow": [_make_item()]},
            sites={"stackoverflow": "tech"},
        )
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].title == "Test Q"
        assert "so:site:stackoverflow" in articles[0].tags

    def test_empty_response(self):
        src = _mock_source(items_by_site={}, sites={"stackoverflow": "tech"})
        assert src.crawl() == []


class TestMultiSite:
    def test_two_sites(self):
        src = _mock_source(
            items_by_site={
                "stackoverflow": [_make_item(title="SO Q", link="https://so.com/1")],
                "security": [_make_item(title="Sec Q", link="https://sec.com/1", tags=["encryption"])],
            },
            sites={"stackoverflow": "tech", "security": "security"},
        )
        articles = src.crawl()
        assert len(articles) == 2
        sources = {a.source for a in articles}
        assert "Stack Overflow" in sources
        assert "SE/security" in sources

    def test_cross_site_dedup(self):
        same_link = "https://stackoverflow.com/q/123"
        src = _mock_source(
            items_by_site={
                "stackoverflow": [_make_item(link=same_link)],
                "serverfault": [_make_item(link=same_link)],
            },
            sites={"stackoverflow": "tech", "serverfault": "tech"},
        )
        articles = src.crawl()
        assert len(articles) == 1


class TestFilters:
    def test_min_score(self):
        src = _mock_source(
            items_by_site={"stackoverflow": [_make_item(score=5), _make_item(score=50, link="https://so.com/2")]},
            sites={"stackoverflow": "tech"}, min_score=10,
        )
        assert len(src.crawl()) == 1

    def test_min_views(self):
        src = _mock_source(
            items_by_site={"stackoverflow": [_make_item(view_count=50)]},
            sites={"stackoverflow": "tech"}, min_views=100,
        )
        assert len(src.crawl()) == 0

    def test_min_answers(self):
        src = _mock_source(
            items_by_site={"stackoverflow": [_make_item(answer_count=1)]},
            sites={"stackoverflow": "tech"}, min_answers=5,
        )
        assert len(src.crawl()) == 0

    def test_accepted_only(self):
        src = _mock_source(
            items_by_site={"stackoverflow": [
                _make_item(accepted_answer_id=None, link="https://so.com/1"),
                _make_item(accepted_answer_id=99, link="https://so.com/2"),
            ]},
            sites={"stackoverflow": "tech"}, accepted_only=True,
        )
        assert len(src.crawl()) == 1

    def test_tag_filter(self):
        src = _mock_source(
            items_by_site={"stackoverflow": [
                _make_item(tags=["python", "flask"], link="https://so.com/1"),
                _make_item(tags=["java", "spring"], link="https://so.com/2"),
            ]},
            sites={"stackoverflow": "tech"}, tag_filter=["python"],
        )
        assert len(src.crawl()) == 1

    def test_category_filter(self):
        src = _mock_source(
            items_by_site={"stackoverflow": [
                _make_item(tags=["tensorflow"], link="https://so.com/1"),
                _make_item(tags=["java"], link="https://so.com/2"),
            ]},
            sites={"stackoverflow": "tech"}, category_filter=["ai"],
        )
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].category == "ai"

    def test_min_quality(self):
        src = _mock_source(
            items_by_site={"stackoverflow": [
                _make_item(score=0, answer_count=0, view_count=1, is_answered=False, link="https://so.com/1"),
                _make_item(score=200, answer_count=15, view_count=50000, is_answered=True, link="https://so.com/2"),
            ]},
            sites={"stackoverflow": "tech"}, min_quality=0.5,
        )
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].quality_score >= 0.5


class TestQualityScoring:
    def test_sorted_by_quality(self):
        src = _mock_source(
            items_by_site={"stackoverflow": [
                _make_item(score=1, view_count=10, answer_count=0, is_answered=False, link="https://so.com/1"),
                _make_item(score=500, view_count=100000, answer_count=20, is_answered=True, link="https://so.com/2"),
                _make_item(score=50, view_count=5000, answer_count=5, is_answered=True, link="https://so.com/3"),
            ]},
            sites={"stackoverflow": "tech"},
        )
        articles = src.crawl()
        scores = [a.quality_score for a in articles]
        assert scores == sorted(scores, reverse=True)


class TestGlobalLimit:
    def test_global_limit(self):
        items = [_make_item(link=f"https://so.com/{i}") for i in range(10)]
        src = _mock_source(
            items_by_site={"stackoverflow": items},
            sites={"stackoverflow": "tech"}, global_limit=3,
        )
        assert len(src.crawl()) == 3


class TestProvenanceTags:
    def test_tags_present(self):
        src = _mock_source(
            items_by_site={"stackoverflow": [_make_item(tags=["python", "django"])]},
            sites={"stackoverflow": "tech"},
        )
        article = src.crawl()[0]
        assert "so:site:stackoverflow" in article.tags
        assert "so:tag:python" in article.tags
        assert "so:tag:django" in article.tags
        assert any(t.startswith("so:category:") for t in article.tags)

    def test_answered_tag(self):
        src = _mock_source(
            items_by_site={"stackoverflow": [_make_item(is_answered=True)]},
            sites={"stackoverflow": "tech"},
        )
        assert "so:answered" in src.crawl()[0].tags

    def test_no_answered_tag(self):
        src = _mock_source(
            items_by_site={"stackoverflow": [_make_item(is_answered=False)]},
            sites={"stackoverflow": "tech"},
        )
        assert "so:answered" not in src.crawl()[0].tags


class TestSummaryFormat:
    def test_answered_emoji(self):
        src = _mock_source(
            items_by_site={"stackoverflow": [_make_item(is_answered=True)]},
            sites={"stackoverflow": "tech"},
        )
        assert "✅" in src.crawl()[0].summary

    def test_unanswered_emoji(self):
        src = _mock_source(
            items_by_site={"stackoverflow": [_make_item(is_answered=False)]},
            sites={"stackoverflow": "tech"},
        )
        assert "❓" in src.crawl()[0].summary

    def test_human_readable_views(self):
        src = _mock_source(
            items_by_site={"stackoverflow": [_make_item(view_count=15000)]},
            sites={"stackoverflow": "tech"},
        )
        assert "15.0K" in src.crawl()[0].summary


class TestDefaultSites:
    def test_default_sites_exist(self):
        assert "stackoverflow" in DEFAULT_SITES
        assert "security" in DEFAULT_SITES
        assert "datascience" in DEFAULT_SITES
        assert len(DEFAULT_SITES) >= 9
