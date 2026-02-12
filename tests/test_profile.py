"""Tests for profile scoring and the public API."""
from clawler.models import Article
from clawler.profile import _score_article, score_articles


PROFILE = {
    "name": "test",
    "interests": [
        {"keywords": ["AI", "machine learning", "LLM"], "weight": 2.0},
        {"keywords": ["python", "rust"], "weight": 1.0},
        {"keywords": ["skateboarding"], "weight": 1.5},
    ],
}


def _art(title, summary=""):
    return Article(title=title, url=f"https://x.com/{hash(title)}", source="test", summary=summary)


class TestScoreArticle:
    def test_no_match_returns_zero(self):
        a = _art("Weather forecast for tomorrow")
        assert _score_article(a, PROFILE["interests"]) == 0.0

    def test_single_keyword_match(self):
        a = _art("New AI model released today")
        score = _score_article(a, PROFILE["interests"])
        assert score > 0

    def test_higher_weight_scores_more(self):
        ai_art = _art("AI breakthrough announced")
        py_art = _art("Python update released")
        ai_score = _score_article(ai_art, PROFILE["interests"])
        py_score = _score_article(py_art, PROFILE["interests"])
        assert ai_score > py_score

    def test_multiple_keyword_hits_diminish(self):
        one_hit = _art("AI is great")
        multi = _art("AI and machine learning and LLM progress")
        s1 = _score_article(one_hit, PROFILE["interests"])
        sm = _score_article(multi, PROFILE["interests"])
        assert sm > s1
        # But not 3x (diminishing returns)
        assert sm < s1 * 3


class TestScoreArticles:
    def test_sorts_by_relevance(self):
        arts = [
            _art("Weather is nice"),
            _art("AI model beats benchmarks"),
            _art("Skateboarding in NYC parks"),
        ]
        result = score_articles(arts, PROFILE)
        assert result[0].title == "AI model beats benchmarks"
        assert hasattr(result[0], "relevance")

    def test_min_relevance_filter(self):
        arts = [
            _art("Weather is nice"),
            _art("AI model released"),
        ]
        result = score_articles(arts, PROFILE, min_relevance=0.5)
        assert all(a.relevance >= 0.5 for a in result)

    def test_empty_profile_returns_all(self):
        arts = [_art("Hello"), _art("World")]
        result = score_articles(arts, {"interests": []})
        assert len(result) == 2


class TestPublicAPI:
    def test_import(self):
        from clawler.api import crawl
        assert callable(crawl)
