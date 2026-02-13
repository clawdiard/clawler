"""Tests for clawler.profile — interest-based relevance scoring."""
import tempfile
import json
from pathlib import Path

from clawler.models import Article
from clawler.profile import score_articles, _score_article


def _article(title, summary=""):
    return Article(title=title, url=f"https://ex.com/{title}", source="Test", summary=summary)


class TestScoreArticle:
    def test_keyword_match(self):
        profile_interests = [{"keywords": ["AI", "machine learning"], "weight": 2.0}]
        a = _article("New AI breakthrough in machine learning")
        score = _score_article(a, profile_interests)
        assert score > 0

    def test_no_match(self):
        profile_interests = [{"keywords": ["skateboarding"], "weight": 1.0}]
        a = _article("Stock market reaches new highs")
        score = _score_article(a, profile_interests)
        assert score == 0.0

    def test_weight_affects_score(self):
        high = [{"keywords": ["AI"], "weight": 5.0}]
        low = [{"keywords": ["AI"], "weight": 1.0}]
        a = _article("AI news")
        assert _score_article(a, high) > _score_article(a, low)


class TestScoreArticles:
    def test_sorts_by_relevance(self):
        profile = {"interests": [{"keywords": ["python"], "weight": 2.0}]}
        articles = [
            _article("Stock market update"),
            _article("Python 3.13 released"),
            _article("New python web framework"),
        ]
        result = score_articles(articles, profile)
        assert result[0].title in ("Python 3.13 released", "New python web framework")
        assert all(a.relevance is not None for a in result)

    def test_min_relevance_filter(self):
        profile = {"interests": [{"keywords": ["AI"], "weight": 2.0}]}
        articles = [_article("AI news"), _article("Cooking tips")]
        result = score_articles(articles, profile, min_relevance=0.5)
        assert len(result) == 1
        assert result[0].title == "AI news"

    def test_file_profile(self):
        profile_data = {"interests": [{"keywords": ["rust"], "weight": 1.5}]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(profile_data, f)
            f.flush()
            articles = [_article("Rust 2.0 announced"), _article("Java news")]
            result = score_articles(articles, f.name)
            assert result[0].title == "Rust 2.0 announced"
