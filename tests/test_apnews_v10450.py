"""Tests for AP News source enhancements (v10.45.0).

Covers: keyword category detection, quality scoring, prominent authors,
cross-section dedup, filters, rich summaries, provenance tags.
"""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.apnews import (
    APNewsSource,
    _detect_category,
    _compute_quality,
    PROMINENT_AUTHORS,
    KEYWORD_CATEGORIES,
    SECTION_PROMINENCE,
    AP_FEEDS,
)


# --- Category detection ---

class TestCategoryDetection:
    def test_ai_keywords(self):
        assert _detect_category("OpenAI releases new GPT model", "", "tech") == "ai"

    def test_security_keywords(self):
        assert _detect_category("Major ransomware attack hits hospitals", "", "tech") == "security"

    def test_crypto_keywords(self):
        assert _detect_category("Bitcoin surges past $100k", "", "business") == "crypto"

    def test_health_from_summary(self):
        assert _detect_category("New study", "FDA approves vaccine for rare disease", "science") == "health"

    def test_science_keywords(self):
        assert _detect_category("NASA launches new telescope mission", "", "tech") == "science"

    def test_business_keywords(self):
        assert _detect_category("Fed raises interest rate again", "", "world") == "business"

    def test_environment_keywords(self):
        assert _detect_category("Wildfire threatens California communities", "", "world") == "environment"

    def test_education_keywords(self):
        assert _detect_category("University tuition costs rise sharply", "", "world") == "education"

    def test_culture_keywords(self):
        assert _detect_category("Oscar nominations announced", "", "world") == "culture"

    def test_fallback_to_section(self):
        assert _detect_category("Local event happening today", "", "sports") == "sports"

    def test_specific_over_generic(self):
        # AI should win over section fallback
        assert _detect_category("Machine learning transforms healthcare", "", "tech") == "ai"

    def test_world_keywords(self):
        assert _detect_category("NATO summit addresses Ukraine crisis", "", "tech") == "world"

    def test_gaming_keywords(self):
        assert _detect_category("New video game breaks sales records on Steam", "", "tech") == "gaming"


# --- Quality scoring ---

class TestQualityScoring:
    def test_top_news_highest_base(self):
        q = _compute_quality("Top News", 0, "world", "")
        assert q >= 0.50

    def test_position_decay(self):
        q0 = _compute_quality("World", 0, "world", "")
        q5 = _compute_quality("World", 5, "world", "")
        q10 = _compute_quality("World", 10, "world", "")
        assert q0 > q5 > q10

    def test_prominent_author_boost(self):
        base = _compute_quality("Technology", 0, "tech", "")
        boosted = _compute_quality("Technology", 0, "tech", "Zeke Miller")
        assert boosted > base

    def test_boosted_category_bonus(self):
        base = _compute_quality("Technology", 0, "tech", "")
        boosted = _compute_quality("Technology", 0, "ai", "")
        assert boosted > base

    def test_score_capped_at_1(self):
        q = _compute_quality("Top News", 0, "ai", "Zeke Miller")
        assert q <= 1.0

    def test_unknown_section_gets_default(self):
        q = _compute_quality("Unknown Section", 0, "tech", "")
        assert 0.3 <= q <= 0.5

    def test_oddities_lower_than_world(self):
        q_odd = _compute_quality("Oddities", 0, "culture", "")
        q_world = _compute_quality("World", 0, "world", "")
        assert q_world > q_odd


# --- Prominent authors ---

class TestProminentAuthors:
    def test_known_authors_exist(self):
        assert "zeke miller" in PROMINENT_AUTHORS
        assert "seth borenstein" in PROMINENT_AUTHORS
        assert "matt o'brien" in PROMINENT_AUTHORS

    def test_case_insensitive_match(self):
        # The quality function lowercases author
        q = _compute_quality("Technology", 0, "tech", "ZEKE MILLER")
        q_base = _compute_quality("Technology", 0, "tech", "")
        assert q > q_base


# --- Feed configuration ---

class TestFeedConfig:
    def test_feeds_have_required_keys(self):
        for feed in AP_FEEDS:
            assert "url" in feed
            assert "section" in feed
            assert "category" in feed

    def test_twelve_feeds(self):
        assert len(AP_FEEDS) == 12  # 10 original + 2 new (Oddities, Lifestyle)

    def test_all_sections_have_prominence(self):
        for feed in AP_FEEDS:
            assert feed["section"] in SECTION_PROMINENCE


# --- Integration (mocked) ---

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>AP News</title>
<item>
  <title>OpenAI announces major AI breakthrough</title>
  <link>https://apnews.com/article/openai-ai-breakthrough</link>
  <description>A new model pushes the boundaries of artificial intelligence.</description>
  <pubDate>Thu, 19 Feb 2026 12:00:00 GMT</pubDate>
  <author>Matt O'Brien</author>
</item>
<item>
  <title>Local park opens after renovation</title>
  <link>https://apnews.com/article/park-renovation</link>
  <description>A community celebrates the reopening of a beloved park.</description>
  <pubDate>Thu, 19 Feb 2026 11:00:00 GMT</pubDate>
  <author>Jane Doe</author>
</item>
<item>
  <title>Bitcoin surges to new record high</title>
  <link>https://apnews.com/article/bitcoin-record</link>
  <description>Cryptocurrency markets rally on institutional adoption.</description>
  <pubDate>Thu, 19 Feb 2026 10:00:00 GMT</pubDate>
</item>
</channel>
</rss>"""


class TestAPNewsCrawl:
    def _make_source(self, **kwargs):
        src = APNewsSource(**kwargs)
        src.fetch_url = MagicMock(return_value=SAMPLE_RSS)
        return src

    def test_basic_crawl(self):
        src = self._make_source(sections=["technology"])
        articles = src.crawl()
        assert len(articles) == 3

    def test_cross_section_dedup(self):
        """Same URLs across sections should be deduped."""
        src = self._make_source(sections=["technology", "top news"])
        articles = src.crawl()
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))

    def test_category_detection_applied(self):
        src = self._make_source(sections=["technology"])
        articles = src.crawl()
        ai_articles = [a for a in articles if a.category == "ai"]
        assert len(ai_articles) >= 1  # "OpenAI announces major AI breakthrough"

    def test_crypto_detected(self):
        src = self._make_source(sections=["technology"])
        articles = src.crawl()
        crypto = [a for a in articles if a.category == "crypto"]
        assert len(crypto) >= 1  # "Bitcoin surges"

    def test_quality_scores_assigned(self):
        src = self._make_source(sections=["technology"])
        articles = src.crawl()
        for a in articles:
            assert a.quality_score is not None
            assert 0 < a.quality_score <= 1.0

    def test_quality_sorted(self):
        src = self._make_source(sections=["technology"])
        articles = src.crawl()
        scores = [a.quality_score for a in articles]
        assert scores == sorted(scores, reverse=True)

    def test_min_quality_filter(self):
        src = self._make_source(sections=["technology"], min_quality=0.99)
        articles = src.crawl()
        assert len(articles) == 0  # Nothing that high

    def test_category_filter(self):
        src = self._make_source(sections=["technology"], category_filter=["crypto"])
        articles = src.crawl()
        for a in articles:
            assert a.category == "crypto"

    def test_global_limit(self):
        src = self._make_source(sections=["technology"], global_limit=1)
        articles = src.crawl()
        assert len(articles) <= 1

    def test_exclude_sections(self):
        src = self._make_source(exclude_sections=["technology"])
        articles = src.crawl()
        for a in articles:
            assert "technology" not in a.source.lower()

    def test_rich_summary_format(self):
        src = self._make_source(sections=["technology"])
        articles = src.crawl()
        first = articles[0]
        assert "📰" in first.summary
        # Author present on at least first article
        authored = [a for a in articles if "✍️" in a.summary]
        assert len(authored) >= 1

    def test_provenance_tags(self):
        src = self._make_source(sections=["technology"])
        articles = src.crawl()
        for a in articles:
            section_tags = [t for t in a.tags if t.startswith("apnews:section:")]
            cat_tags = [t for t in a.tags if t.startswith("apnews:category:")]
            assert len(section_tags) == 1
            assert len(cat_tags) == 1

    def test_prominent_author_tag(self):
        src = self._make_source(sections=["technology"])
        articles = src.crawl()
        matt = [a for a in articles if a.author and "matt" in a.author.lower()]
        assert len(matt) >= 1
        assert "apnews:prominent-author" in matt[0].tags
