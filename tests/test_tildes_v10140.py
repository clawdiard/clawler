"""Tests for enhanced Tildes source (v10.14.0).

Covers: multi-group, sort modes, quality scoring, keyword categories,
filters, domain extraction, deduplication, global limit.
"""
import math
from unittest.mock import patch, MagicMock
import pytest
from clawler.sources.tildes import (
    TildesSource,
    _detect_category,
    _quality_score,
    _human_count,
)


# ── Sample HTML ──────────────────────────────────────────────────────

SAMPLE_TOPIC = """
<article class="topic">
  <div class="topic-voting"><div class="topic-voting-votes">42</div></div>
  <h1 class="topic-title"><a href="/~comp/abc123">New LLM breakthrough announced</a></h1>
  <div class="topic-info">
    <a class="topic-group" href="/~comp">~comp</a>
    <a class="topic-info-comments" href="/~comp/abc123#comments">18 comments</a>
    <time datetime="2026-02-17T10:00:00Z">2h ago</time>
  </div>
  <ul class="topic-tags"><a>artificial intelligence</a><a>research</a></ul>
</article>
"""

SAMPLE_LINK_TOPIC = """
<article class="topic">
  <div class="topic-voting"><div class="topic-voting-votes">15</div></div>
  <h1 class="topic-title"><a href="/~news/def456">Election results shake markets</a></h1>
  <a class="topic-info-source" href="https://www.reuters.com/article/election">reuters.com</a>
  <div class="topic-info">
    <a class="topic-group" href="/~news">~news</a>
    <a class="topic-info-comments" href="/~news/def456#comments">5 comments</a>
    <time datetime="2026-02-17T08:00:00Z">4h ago</time>
  </div>
</article>
"""

SAMPLE_GAMING_TOPIC = """
<article class="topic">
  <div class="topic-voting"><div class="topic-voting-votes">8</div></div>
  <h1 class="topic-title"><a href="/~games/ghi789">Steam's new indie game showcase</a></h1>
  <div class="topic-info">
    <a class="topic-group" href="/~games">~games</a>
    <a class="topic-info-comments" href="/~games/ghi789#comments">3 comments</a>
    <time datetime="2026-02-17T06:00:00Z">6h ago</time>
  </div>
</article>
"""

SAMPLE_MINIMAL_TOPIC = """
<article class="topic">
  <h1 class="topic-title"><a href="/~misc/jkl012">Just a thought</a></h1>
  <div class="topic-info">
    <a class="topic-group" href="/~misc">~misc</a>
    <time datetime="2026-02-17T01:00:00Z">11h ago</time>
  </div>
</article>
"""

FULL_PAGE = f"<html><body>{SAMPLE_TOPIC}{SAMPLE_LINK_TOPIC}{SAMPLE_GAMING_TOPIC}{SAMPLE_MINIMAL_TOPIC}</body></html>"
COMP_PAGE = f"<html><body>{SAMPLE_TOPIC}</body></html>"
NEWS_PAGE = f"<html><body>{SAMPLE_LINK_TOPIC}</body></html>"
GAMES_PAGE = f"<html><body>{SAMPLE_GAMING_TOPIC}</body></html>"


# ── Unit tests: helpers ──────────────────────────────────────────────

class TestDetectCategory:
    def test_ai_keyword(self):
        assert _detect_category("New LLM breakthrough", "comp") == "ai"

    def test_security_keyword(self):
        assert _detect_category("Critical vulnerability found in OpenSSL", "comp") == "security"

    def test_crypto_keyword(self):
        assert _detect_category("Bitcoin hits new ATH", "finance") == "crypto"

    def test_health_keyword(self):
        assert _detect_category("FDA approves new vaccine", "health") == "health"

    def test_gaming_keyword(self):
        assert _detect_category("Steam summer sale starts", "comp") == "gaming"

    def test_world_keyword(self):
        assert _detect_category("Congress passes new legislation", "news") == "world"

    def test_group_fallback(self):
        assert _detect_category("Something generic here", "science") == "science"

    def test_unknown_group_fallback(self):
        assert _detect_category("Something generic", "unknown_group") == "tech"

    def test_design_keyword(self):
        assert _detect_category("New Figma features for UX", "comp") == "design"

    def test_business_keyword(self):
        assert _detect_category("Revenue growth drives stock market rally", "finance") == "business"


class TestQualityScore:
    def test_zero_engagement(self):
        assert _quality_score(0, 0) == 0.2

    def test_moderate_engagement(self):
        score = _quality_score(20, 10)
        assert 0.5 < score < 0.9

    def test_high_engagement(self):
        score = _quality_score(100, 50)
        assert score > 0.7

    def test_max_cap(self):
        score = _quality_score(10000, 5000)
        assert score <= 1.0

    def test_comments_weighted_higher(self):
        # 10 comments (×3=30 engagement) vs 30 votes (30 engagement) should be equal
        s1 = _quality_score(0, 10)
        s2 = _quality_score(30, 0)
        assert abs(s1 - s2) < 0.05


class TestHumanCount:
    def test_small(self):
        assert _human_count(42) == "42"

    def test_thousands(self):
        assert _human_count(1500) == "1.5K"

    def test_millions(self):
        assert _human_count(2300000) == "2.3M"


# ── Integration tests: crawl ─────────────────────────────────────────

class TestTildesCrawl:
    def _mock_source(self, **kwargs):
        src = TildesSource(**kwargs)
        return src

    @patch.object(TildesSource, "fetch_url", return_value=FULL_PAGE)
    def test_basic_crawl(self, mock_fetch):
        src = self._mock_source()
        articles = src.crawl()
        assert len(articles) == 4
        mock_fetch.assert_called_once()

    @patch.object(TildesSource, "fetch_url", return_value=FULL_PAGE)
    def test_quality_scores_present(self, mock_fetch):
        articles = self._mock_source().crawl()
        for a in articles:
            assert a.quality_score is not None
            assert 0 <= a.quality_score <= 1.0

    @patch.object(TildesSource, "fetch_url", return_value=FULL_PAGE)
    def test_sorted_by_quality(self, mock_fetch):
        articles = self._mock_source().crawl()
        scores = [a.quality_score for a in articles]
        assert scores == sorted(scores, reverse=True)

    @patch.object(TildesSource, "fetch_url", return_value=FULL_PAGE)
    def test_category_detection(self, mock_fetch):
        articles = self._mock_source().crawl()
        cats = {a.title: a.category for a in articles}
        assert cats["New LLM breakthrough announced"] == "ai"
        assert cats["Election results shake markets"] in ("world", "business")  # "market" keyword
        assert cats["Steam's new indie game showcase"] == "gaming"

    @patch.object(TildesSource, "fetch_url", return_value=FULL_PAGE)
    def test_domain_extraction(self, mock_fetch):
        articles = self._mock_source().crawl()
        link_article = [a for a in articles if "reuters" in a.url][0]
        assert "tildes:domain:reuters.com" in link_article.tags
        assert "🔗 reuters.com" in link_article.summary

    @patch.object(TildesSource, "fetch_url", return_value=FULL_PAGE)
    def test_provenance_tags(self, mock_fetch):
        articles = self._mock_source().crawl()
        a = articles[0]  # highest quality
        assert any(t.startswith("tildes:group:") for t in a.tags)
        assert any(t.startswith("tildes:category:") for t in a.tags)

    @patch.object(TildesSource, "fetch_url", return_value=FULL_PAGE)
    def test_discussion_url(self, mock_fetch):
        articles = self._mock_source().crawl()
        for a in articles:
            if a.discussion_url:
                assert a.discussion_url.startswith("https://tildes.net/")
                assert "tildes:has-discussion" in a.tags

    @patch.object(TildesSource, "fetch_url", return_value=FULL_PAGE)
    def test_min_votes_filter(self, mock_fetch):
        articles = self._mock_source(min_votes=10).crawl()
        assert all("⬆" in a.summary for a in articles)
        # Should exclude the minimal topic (0 votes) and gaming (8 votes)
        assert len(articles) == 2

    @patch.object(TildesSource, "fetch_url", return_value=FULL_PAGE)
    def test_min_comments_filter(self, mock_fetch):
        articles = self._mock_source(min_comments=10).crawl()
        assert len(articles) == 1
        assert articles[0].title == "New LLM breakthrough announced"

    @patch.object(TildesSource, "fetch_url", return_value=FULL_PAGE)
    def test_min_quality_filter(self, mock_fetch):
        articles_all = self._mock_source().crawl()
        high_q = self._mock_source(min_quality=0.5).crawl()
        assert len(high_q) <= len(articles_all)
        for a in high_q:
            assert a.quality_score >= 0.5

    @patch.object(TildesSource, "fetch_url", return_value=FULL_PAGE)
    def test_category_filter(self, mock_fetch):
        articles = self._mock_source(category_filter=["ai"]).crawl()
        assert all(a.category == "ai" for a in articles)
        assert len(articles) == 1

    @patch.object(TildesSource, "fetch_url", return_value=FULL_PAGE)
    def test_global_limit(self, mock_fetch):
        articles = self._mock_source(global_limit=2).crawl()
        assert len(articles) == 2

    @patch.object(TildesSource, "fetch_url", return_value=FULL_PAGE)
    def test_rich_summary_format(self, mock_fetch):
        articles = self._mock_source().crawl()
        for a in articles:
            assert "⬆" in a.summary
            assert "💬" in a.summary
            assert "📂" in a.summary


class TestTildesMultiGroup:
    @patch.object(TildesSource, "fetch_url")
    def test_multi_group_fetching(self, mock_fetch):
        mock_fetch.side_effect = [COMP_PAGE, NEWS_PAGE]
        src = TildesSource(groups=["comp", "news"])
        articles = src.crawl()
        assert len(articles) == 2
        assert mock_fetch.call_count == 2

    @patch.object(TildesSource, "fetch_url")
    def test_cross_group_dedup(self, mock_fetch):
        # Same page returned for both groups → duplicates removed
        mock_fetch.side_effect = [COMP_PAGE, COMP_PAGE]
        src = TildesSource(groups=["comp", "comp.ai"])
        articles = src.crawl()
        assert len(articles) == 1

    @patch.object(TildesSource, "fetch_url")
    def test_exclude_groups(self, mock_fetch):
        mock_fetch.return_value = FULL_PAGE
        src = TildesSource(exclude_groups=["games"])
        articles = src.crawl()
        assert not any("~games" in a.source for a in articles)

    @patch.object(TildesSource, "fetch_url")
    def test_sort_param(self, mock_fetch):
        mock_fetch.return_value = COMP_PAGE
        src = TildesSource(sort="votes")
        src.crawl()
        call_url = mock_fetch.call_args[0][0]
        assert "order=votes" in call_url

    @patch.object(TildesSource, "fetch_url")
    def test_sort_default_no_param(self, mock_fetch):
        mock_fetch.return_value = COMP_PAGE
        src = TildesSource(sort="activity")
        src.crawl()
        call_url = mock_fetch.call_args[0][0]
        assert "order=" not in call_url

    @patch.object(TildesSource, "fetch_url")
    def test_tag_extraction(self, mock_fetch):
        mock_fetch.return_value = COMP_PAGE
        articles = TildesSource().crawl()
        a = articles[0]
        assert "tildes:tag:artificial intelligence" in a.tags
        assert "tildes:tag:research" in a.tags
        assert "🏷" in a.summary


class TestTildesEdgeCases:
    @patch.object(TildesSource, "fetch_url", return_value="<html><body></body></html>")
    def test_empty_page(self, mock_fetch):
        assert TildesSource().crawl() == []

    @patch.object(TildesSource, "fetch_url", side_effect=Exception("timeout"))
    def test_network_error(self, mock_fetch):
        assert TildesSource().crawl() == []

    @patch.object(TildesSource, "fetch_url", return_value=SAMPLE_MINIMAL_TOPIC)
    def test_minimal_topic(self, mock_fetch):
        """Topic with no votes, no comments, no tags."""
        articles = TildesSource().crawl()
        assert len(articles) == 1
        assert articles[0].quality_score == 0.2
        assert articles[0].category == "tech"
