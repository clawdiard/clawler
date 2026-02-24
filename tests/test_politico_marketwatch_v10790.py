"""Tests for enhanced Politico + MarketWatch sources (v10.79.0).

Covers:
- Feed configuration (section count, prominence weights)
- Quality scoring (position decay, keyword boost, author boost)
- Category refinement via keywords
- Cross-feed URL deduplication
- Prominent author detection (Politico)
- Filters: min_quality, category_filter, global_limit
- Rich summary formatting
- Provenance tags
"""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.politico import (
    PoliticoSource, POLITICO_FEEDS, _position_decay, _compute_quality,
    _PROMINENT_AUTHORS, _CATEGORY_KEYWORDS,
)
from clawler.sources.marketwatch import (
    MarketWatchSource, MARKETWATCH_FEEDS, _position_decay as mw_position_decay,
    _compute_quality as mw_compute_quality, _keyword_boost,
    _KEYWORD_TIERS, _CATEGORY_KEYWORDS as MW_CATEGORY_KEYWORDS,
)


# ── Politico Tests ───────────────────────────────────────────────────

class TestPoliticoFeedConfig:
    def test_feed_count(self):
        assert len(POLITICO_FEEDS) == 12

    def test_all_feeds_have_prominence(self):
        for f in POLITICO_FEEDS:
            assert "prominence" in f
            assert 0.0 < f["prominence"] <= 1.0

    def test_all_feeds_have_required_keys(self):
        for f in POLITICO_FEEDS:
            assert all(k in f for k in ("url", "section", "category", "prominence"))

    def test_sections_unique(self):
        sections = [f["section"] for f in POLITICO_FEEDS]
        assert len(sections) == len(set(sections))

    def test_new_sections_present(self):
        sections = {f["section"] for f in POLITICO_FEEDS}
        for s in ["White House", "Foreign Policy", "Trade", "Justice"]:
            assert s in sections


class TestPoliticoQualityScoring:
    def test_position_decay_single(self):
        assert _position_decay(0, 1) == 1.0

    def test_position_decay_first(self):
        assert _position_decay(0, 10) == 1.0

    def test_position_decay_last(self):
        assert abs(_position_decay(9, 10) - 0.6) < 0.01

    def test_position_decay_middle(self):
        val = _position_decay(5, 10)
        assert 0.6 < val < 1.0

    def test_quality_prominent_author_boost(self):
        q_normal = _compute_quality(0.8, 5, 10, False)
        q_prominent = _compute_quality(0.8, 5, 10, True)
        assert q_prominent > q_normal
        assert q_prominent - q_normal == pytest.approx(0.06, abs=0.01)

    def test_quality_range(self):
        for prom in [0.7, 0.85, 1.0]:
            for pos in [0, 5, 9]:
                q = _compute_quality(prom, pos, 10, False)
                assert 0.0 <= q <= 1.0


class TestPoliticoProminentAuthors:
    def test_authors_are_lowercase(self):
        for a in _PROMINENT_AUTHORS:
            assert a == a.lower()

    def test_minimum_author_count(self):
        assert len(_PROMINENT_AUTHORS) >= 12


class TestPoliticoCategoryKeywords:
    def test_keyword_categories_exist(self):
        expected = {"security", "tech", "world", "business", "health", "science", "investigative", "politics"}
        assert expected == set(_CATEGORY_KEYWORDS.keys())


class TestPoliticoCrawl:
    def _make_entry(self, title="Test Article", link="https://politico.com/test",
                    author="", summary="A test summary"):
        entry = MagicMock()
        entry.get = lambda k, d="": {
            "title": title, "link": link, "summary": summary,
            "author": author, "published": "Mon, 24 Feb 2026 08:00:00 GMT",
        }.get(k, d)
        return entry

    @patch.object(PoliticoSource, "fetch_url")
    def test_basic_crawl(self, mock_fetch):
        import feedparser
        feed = MagicMock()
        feed.entries = [self._make_entry()]
        with patch("clawler.sources.politico.feedparser.parse", return_value=feed):
            mock_fetch.return_value = "<rss></rss>"
            src = PoliticoSource(sections=["politics"])
            articles = src.crawl()
            assert len(articles) >= 1
            assert articles[0].source.startswith("Politico")

    @patch.object(PoliticoSource, "fetch_url")
    def test_cross_feed_dedup(self, mock_fetch):
        import feedparser
        feed = MagicMock()
        feed.entries = [self._make_entry(link="https://politico.com/same")]
        with patch("clawler.sources.politico.feedparser.parse", return_value=feed):
            mock_fetch.return_value = "<rss></rss>"
            src = PoliticoSource()
            articles = src.crawl()
            urls = [a.url for a in articles]
            assert len(urls) == len(set(urls))

    @patch.object(PoliticoSource, "fetch_url")
    def test_prominent_author_tag(self, mock_fetch):
        import feedparser
        feed = MagicMock()
        feed.entries = [self._make_entry(author="Jonathan Martin")]
        with patch("clawler.sources.politico.feedparser.parse", return_value=feed):
            mock_fetch.return_value = "<rss></rss>"
            src = PoliticoSource(sections=["politics"])
            articles = src.crawl()
            assert any("politico:prominent-author" in a.tags for a in articles)

    @patch.object(PoliticoSource, "fetch_url")
    def test_min_quality_filter(self, mock_fetch):
        import feedparser
        feed = MagicMock()
        feed.entries = [self._make_entry(link=f"https://politico.com/{i}") for i in range(10)]
        with patch("clawler.sources.politico.feedparser.parse", return_value=feed):
            mock_fetch.return_value = "<rss></rss>"
            src = PoliticoSource(sections=["politics"], min_quality=0.99)
            articles = src.crawl()
            assert all(a.quality_score >= 0.99 for a in articles)

    @patch.object(PoliticoSource, "fetch_url")
    def test_global_limit(self, mock_fetch):
        import feedparser
        feed = MagicMock()
        feed.entries = [self._make_entry(link=f"https://politico.com/{i}") for i in range(10)]
        with patch("clawler.sources.politico.feedparser.parse", return_value=feed):
            mock_fetch.return_value = "<rss></rss>"
            src = PoliticoSource(sections=["politics"], global_limit=3)
            articles = src.crawl()
            assert len(articles) <= 3


# ── MarketWatch Tests ────────────────────────────────────────────────

class TestMarketWatchFeedConfig:
    def test_feed_count(self):
        assert len(MARKETWATCH_FEEDS) == 8

    def test_all_feeds_have_prominence(self):
        for f in MARKETWATCH_FEEDS:
            assert "prominence" in f
            assert 0.0 < f["prominence"] <= 1.0

    def test_new_sections_present(self):
        sections = {f["section"] for f in MARKETWATCH_FEEDS}
        for s in ["Real Estate", "Retirement", "Bonds & Rates"]:
            assert s in sections


class TestMarketWatchQualityScoring:
    def test_position_decay(self):
        assert mw_position_decay(0, 10) == 1.0
        assert abs(mw_position_decay(9, 10) - 0.6) < 0.01

    def test_keyword_boost_high(self):
        assert _keyword_boost("Fed raises interest rate", "") == _KEYWORD_TIERS["high"]["boost"]

    def test_keyword_boost_medium(self):
        assert _keyword_boost("Stock market opens higher", "") == _KEYWORD_TIERS["medium"]["boost"]

    def test_keyword_boost_none(self):
        assert _keyword_boost("Weather forecast", "") == 0.0

    def test_quality_range(self):
        for prom in [0.68, 0.82, 1.0]:
            for pos in [0, 7, 14]:
                q = mw_compute_quality(prom, pos, 15, 0.0)
                assert 0.0 <= q <= 1.0

    def test_keyword_boost_increases_quality(self):
        q_no_boost = mw_compute_quality(1.0, 0, 10, 0.0)
        q_boost = mw_compute_quality(1.0, 0, 10, 0.10)
        assert q_boost > q_no_boost


class TestMarketWatchCategoryKeywords:
    def test_categories_exist(self):
        assert "tech" in MW_CATEGORY_KEYWORDS
        assert "security" in MW_CATEGORY_KEYWORDS


class TestMarketWatchCrawl:
    def _make_entry(self, title="Market Update", link="https://marketwatch.com/test",
                    author="", summary="Markets rose today"):
        entry = MagicMock()
        entry.get = lambda k, d="": {
            "title": title, "link": link, "summary": summary,
            "author": author, "published": "Mon, 24 Feb 2026 08:00:00 GMT",
        }.get(k, d)
        return entry

    @patch.object(MarketWatchSource, "fetch_url")
    def test_basic_crawl(self, mock_fetch):
        import feedparser
        feed = MagicMock()
        feed.entries = [self._make_entry()]
        with patch("clawler.sources.marketwatch.feedparser.parse", return_value=feed):
            mock_fetch.return_value = "<rss></rss>"
            src = MarketWatchSource(sections=["top stories"])
            articles = src.crawl()
            assert len(articles) >= 1
            assert articles[0].source.startswith("MarketWatch")

    @patch.object(MarketWatchSource, "fetch_url")
    def test_cross_feed_dedup(self, mock_fetch):
        import feedparser
        feed = MagicMock()
        feed.entries = [self._make_entry(link="https://marketwatch.com/same")]
        with patch("clawler.sources.marketwatch.feedparser.parse", return_value=feed):
            mock_fetch.return_value = "<rss></rss>"
            src = MarketWatchSource()
            articles = src.crawl()
            urls = [a.url for a in articles]
            assert len(urls) == len(set(urls))

    @patch.object(MarketWatchSource, "fetch_url")
    def test_category_refinement_tech(self, mock_fetch):
        import feedparser
        feed = MagicMock()
        feed.entries = [self._make_entry(title="AI startup raises $1B")]
        with patch("clawler.sources.marketwatch.feedparser.parse", return_value=feed):
            mock_fetch.return_value = "<rss></rss>"
            src = MarketWatchSource(sections=["top stories"])
            articles = src.crawl()
            assert articles[0].category == "tech"

    @patch.object(MarketWatchSource, "fetch_url")
    def test_global_limit(self, mock_fetch):
        import feedparser
        feed = MagicMock()
        feed.entries = [self._make_entry(link=f"https://mw.com/{i}") for i in range(10)]
        with patch("clawler.sources.marketwatch.feedparser.parse", return_value=feed):
            mock_fetch.return_value = "<rss></rss>"
            src = MarketWatchSource(sections=["top stories"], global_limit=2)
            articles = src.crawl()
            assert len(articles) <= 2

    @patch.object(MarketWatchSource, "fetch_url")
    def test_tags_format(self, mock_fetch):
        import feedparser
        feed = MagicMock()
        feed.entries = [self._make_entry()]
        with patch("clawler.sources.marketwatch.feedparser.parse", return_value=feed):
            mock_fetch.return_value = "<rss></rss>"
            src = MarketWatchSource(sections=["top stories"])
            articles = src.crawl()
            assert any(t.startswith("marketwatch:") for t in articles[0].tags)
