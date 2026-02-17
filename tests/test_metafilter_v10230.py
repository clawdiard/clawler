"""Tests for MetaFilter source (v10.23.0)."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.metafilter import (
    MetaFilterSource,
    _strip_html,
    _extract_comment_count,
    _extract_favorites,
    _extract_domain,
    _map_category,
    _quality_score,
    _format_count,
    METAFILTER_FEEDS,
    SUBSITE_CATEGORY,
)


# ── Helper utilities ────────────────────────────────────────────────

class TestStripHtml:
    def test_removes_tags(self):
        assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_removes_entities(self):
        assert "Hello" in _strip_html("Hello&amp;world")

    def test_collapses_whitespace(self):
        assert _strip_html("  a   b  ") == "a b"


class TestExtractCommentCount:
    def test_slash_comments(self):
        entry = {"slash_comments": "42"}
        assert _extract_comment_count(entry) == 42

    def test_from_summary(self):
        entry = {"summary": "posted by user (73 comments)"}
        assert _extract_comment_count(entry) == 73

    def test_zero_when_missing(self):
        assert _extract_comment_count({}) == 0

    def test_invalid_value(self):
        entry = {"slash_comments": "abc"}
        assert _extract_comment_count(entry) == 0


class TestExtractFavorites:
    def test_from_summary(self):
        entry = {"summary": "posted by user (15 favorites)"}
        assert _extract_favorites(entry) == 15

    def test_zero_when_missing(self):
        assert _extract_favorites({}) == 0


class TestExtractDomain:
    def test_extracts_first_external(self):
        entry = {"summary": '<a href="https://www.example.com/article">link</a>'}
        assert _extract_domain(entry) == "example.com"

    def test_skips_metafilter(self):
        entry = {"summary": '<a href="https://www.metafilter.com/123">link</a> <a href="https://nytimes.com/article">nyt</a>'}
        assert _extract_domain(entry) == "nytimes.com"

    def test_empty_when_no_links(self):
        assert _extract_domain({}) == ""

    def test_strips_www(self):
        entry = {"summary": '<a href="https://www.bbc.co.uk/news">link</a>'}
        assert _extract_domain(entry) == "bbc.co.uk"


class TestMapCategory:
    def test_ai_keywords(self):
        assert _map_category("AI is changing everything", "", "main") == "ai"

    def test_science_keywords(self):
        assert _map_category("NASA launches new telescope", "", "main") == "science"

    def test_world_keywords(self):
        assert _map_category("Supreme Court ruling on elections", "", "main") == "world"

    def test_culture_keywords(self):
        assert _map_category("New film about poetry and museums", "", "main") == "culture"

    def test_gaming_keywords(self):
        assert _map_category("Steam announces new tabletop game", "", "main") == "gaming"

    def test_health_keywords(self):
        assert _map_category("FDA approves new vaccine", "", "main") == "health"

    def test_generic_tech_fallback(self):
        assert _map_category("New database release", "", "main") == "tech"

    def test_subsite_fallback(self):
        assert _map_category("Some random post", "", "ask") == "culture"
        assert _map_category("Some random post", "", "main") == SUBSITE_CATEGORY["main"]

    def test_summary_also_checked(self):
        assert _map_category("Interesting link", "about bitcoin trading", "main") == "crypto"

    def test_environment(self):
        assert _map_category("Sustainability and renewable energy", "", "main") == "environment"


class TestQualityScore:
    def test_baseline(self):
        assert _quality_score(0, 0) == 0.4

    def test_increases_with_comments(self):
        assert _quality_score(10) > _quality_score(0)
        assert _quality_score(100) > _quality_score(10)

    def test_favorites_boost(self):
        assert _quality_score(10, 20) > _quality_score(10, 0)

    def test_capped_at_1(self):
        assert _quality_score(999999, 999999) <= 1.0

    def test_monotonic(self):
        scores = [_quality_score(n) for n in [0, 5, 10, 50, 100, 500]]
        for i in range(len(scores) - 1):
            assert scores[i] <= scores[i + 1]


class TestFormatCount:
    def test_small(self):
        assert _format_count(42) == "42"

    def test_thousands(self):
        assert _format_count(1500) == "1.5K"

    def test_millions(self):
        assert _format_count(2300000) == "2.3M"


# ── Feed constants ──────────────────────────────────────────────────

class TestFeedConstants:
    def test_all_feeds_have_urls(self):
        for name, url in METAFILTER_FEEDS.items():
            assert url.startswith("https://"), f"{name} has invalid URL"

    def test_expected_subsites(self):
        assert "main" in METAFILTER_FEEDS
        assert "ask" in METAFILTER_FEEDS
        assert "fanfare" in METAFILTER_FEEDS
        assert "projects" in METAFILTER_FEEDS
        assert "music" in METAFILTER_FEEDS

    def test_subsite_categories(self):
        for subsite in METAFILTER_FEEDS:
            assert subsite in SUBSITE_CATEGORY


# ── Crawl integration ──────────────────────────────────────────────

MOCK_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:slash="http://purl.org/rss/1.0/modules/slash/">
<channel>
<title>MetaFilter</title>
<item>
  <title>The Future of AI in Healthcare</title>
  <link>https://www.metafilter.com/200001/ai-healthcare</link>
  <description>&lt;p&gt;A fascinating look at &lt;a href="https://example.com/ai"&gt;AI in hospitals&lt;/a&gt;&lt;/p&gt;</description>
  <author>cooluser</author>
  <pubDate>Mon, 17 Feb 2026 12:00:00 GMT</pubDate>
  <slash:comments>87</slash:comments>
</item>
<item>
  <title>Gardening in Small Spaces</title>
  <link>https://www.metafilter.com/200002/small-gardens</link>
  <description>&lt;p&gt;Tips for &lt;a href="https://gardenblog.org/tips"&gt;container gardening&lt;/a&gt;&lt;/p&gt;</description>
  <author>plantfan</author>
  <pubDate>Mon, 17 Feb 2026 10:00:00 GMT</pubDate>
  <slash:comments>23</slash:comments>
</item>
<item>
  <title>Supreme Court Ruling on Digital Privacy</title>
  <link>https://www.metafilter.com/200003/scotus-privacy</link>
  <description>&lt;p&gt;The &lt;a href="https://reuters.com/law"&gt;latest ruling&lt;/a&gt; on digital surveillance&lt;/p&gt;</description>
  <author>lawbuff</author>
  <pubDate>Mon, 17 Feb 2026 08:00:00 GMT</pubDate>
  <slash:comments>142</slash:comments>
</item>
</channel>
</rss>"""


class TestCrawlBasic:
    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_fetches_articles(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"])
        articles = src.crawl()
        assert len(articles) == 3

    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_quality_sorted(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"])
        articles = src.crawl()
        scores = [a.quality_score for a in articles]
        assert scores == sorted(scores, reverse=True)

    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_categories_detected(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"])
        articles = src.crawl()
        cats = {a.title: a.category for a in articles}
        assert cats["The Future of AI in Healthcare"] == "ai"
        assert cats["Supreme Court Ruling on Digital Privacy"] in ("world", "security")  # "privacy" may match security first

    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_source_name(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"])
        articles = src.crawl()
        assert all(a.source == "MetaFilter" for a in articles)

    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_authors_extracted(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"])
        articles = src.crawl()
        authors = {a.author for a in articles}
        assert "cooluser" in authors

    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_domain_extraction(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"])
        articles = src.crawl()
        ai_article = [a for a in articles if "AI" in a.title][0]
        assert "metafilter:domain:example.com" in ai_article.tags

    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_discussion_url(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"])
        articles = src.crawl()
        for a in articles:
            assert a.discussion_url == a.url  # MeFi posts are the discussion


class TestCrawlFilters:
    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_min_comments(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"], min_comments=50)
        articles = src.crawl()
        assert len(articles) == 2  # only 87 and 142 comments

    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_min_quality(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"], min_quality=0.9)
        articles = src.crawl()
        assert all(a.quality_score >= 0.9 for a in articles)

    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_category_filter(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"], category_filter=["ai"])
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].category == "ai"

    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_global_limit(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"], global_limit=2)
        articles = src.crawl()
        assert len(articles) == 2


class TestCrawlSubsites:
    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_all_subsites(self, mock_fetch):
        src = MetaFilterSource(subsites=["all"])
        articles = src.crawl()
        assert mock_fetch.call_count == len(METAFILTER_FEEDS)

    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_dedup_across_subsites(self, mock_fetch):
        src = MetaFilterSource(subsites=["main", "main"])
        articles = src.crawl()
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))

    @patch.object(MetaFilterSource, "fetch_url", return_value="")
    def test_empty_feed(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"])
        articles = src.crawl()
        assert articles == []

    def test_unknown_subsite(self):
        src = MetaFilterSource(subsites=["nonexistent"])
        with patch.object(MetaFilterSource, "fetch_url") as mock_fetch:
            articles = src.crawl()
            mock_fetch.assert_not_called()
            assert articles == []


class TestCrawlTags:
    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_subsite_tag(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"])
        articles = src.crawl()
        for a in articles:
            assert "metafilter:subsite:main" in a.tags

    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_category_tag(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"])
        articles = src.crawl()
        for a in articles:
            assert any(t.startswith("metafilter:category:") for t in a.tags)

    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_has_discussion_tag(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"])
        articles = src.crawl()
        for a in articles:
            assert "metafilter:has-discussion" in a.tags

    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_author_tag(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"])
        articles = src.crawl()
        ai_article = [a for a in articles if "AI" in a.title][0]
        assert "metafilter:author:cooluser" in ai_article.tags


class TestCrawlEnrichedSummary:
    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_contains_comment_count(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"])
        articles = src.crawl()
        ai_article = [a for a in articles if "AI" in a.title][0]
        assert "💬" in ai_article.summary

    @patch.object(MetaFilterSource, "fetch_url", return_value=MOCK_RSS)
    def test_contains_domain(self, mock_fetch):
        src = MetaFilterSource(subsites=["main"])
        articles = src.crawl()
        ai_article = [a for a in articles if "AI" in a.title][0]
        assert "🔗" in ai_article.summary


# ── Registry integration ────────────────────────────────────────────

class TestRegistration:
    def test_in_registry(self):
        from clawler.registry import get_entry
        entry = get_entry("metafilter")
        assert entry is not None
        assert entry.display_name == "MetaFilter"

    def test_class_loads(self):
        from clawler.registry import get_entry
        entry = get_entry("metafilter")
        cls = entry.load_class()
        assert cls is MetaFilterSource

    def test_in_init(self):
        from clawler.sources import MetaFilterSource as Imported
        assert Imported is MetaFilterSource
