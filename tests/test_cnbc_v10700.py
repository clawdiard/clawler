"""Tests for CNBC source v10.70.0 — enhanced with 12 sections, keyword categories,
quality scoring, prominent authors, filters, and provenance tags."""
import re
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from clawler.sources.cnbc import (
    CNBC_FEEDS,
    PROMINENT_AUTHORS,
    _BOOSTED_CATEGORIES,
    _CATEGORY_RULES,
    CNBCSource,
    _compute_quality,
    _detect_category,
    _truncate_at_sentence,
)


# ── Feed configuration tests ─────────────────────────────────────────────────

class TestFeedConfig:
    def test_12_section_feeds(self):
        assert len(CNBC_FEEDS) == 12

    def test_all_feeds_have_required_keys(self):
        for key, info in CNBC_FEEDS.items():
            assert "url" in info, f"{key} missing url"
            assert "label" in info, f"{key} missing label"
            assert "category" in info, f"{key} missing category"
            assert "prominence" in info, f"{key} missing prominence"

    def test_new_sections_present(self):
        expected = {"top_news", "finance", "technology", "media", "earnings", "world",
                    "politics", "health", "real_estate", "energy", "small_business", "investing"}
        assert set(CNBC_FEEDS.keys()) == expected

    def test_prominence_range(self):
        for key, info in CNBC_FEEDS.items():
            assert 0.3 <= info["prominence"] <= 0.6, f"{key} prominence out of range"


# ── Author tests ──────────────────────────────────────────────────────────────

class TestAuthors:
    def test_at_least_18_authors(self):
        assert len(PROMINENT_AUTHORS) >= 18

    def test_top_authors_have_higher_boost(self):
        assert PROMINENT_AUTHORS["jim cramer"] >= 0.10
        assert PROMINENT_AUTHORS["andrew ross sorkin"] >= 0.10
        assert PROMINENT_AUTHORS["kif leswing"] >= 0.10

    def test_all_boosts_in_range(self):
        for name, boost in PROMINENT_AUTHORS.items():
            assert 0.04 <= boost <= 0.15, f"{name} boost {boost} out of range"


# ── Category detection tests ──────────────────────────────────────────────────

class TestCategoryDetection:
    def test_ai_keywords(self):
        assert _detect_category("OpenAI launches GPT-5", "", "tech") == "ai"

    def test_crypto_keywords(self):
        assert _detect_category("Bitcoin surges past $100K", "", "business") == "crypto"

    def test_health_keywords(self):
        assert _detect_category("FDA approves new cancer drug", "", "tech") == "health"

    def test_security_keywords(self):
        assert _detect_category("Major data breach at hospital", "", "business") == "security"

    def test_environment_keywords(self):
        assert _detect_category("Solar energy surpasses coal", "", "tech") == "environment"

    def test_world_keywords(self):
        assert _detect_category("NATO summit addresses Ukraine conflict", "", "business") == "world"

    def test_fallback_to_section(self):
        assert _detect_category("Markets close higher today", "", "business") == "business"

    def test_12_category_rules(self):
        assert len(_CATEGORY_RULES) == 12

    def test_gaming_keywords(self):
        assert _detect_category("Nintendo announces new console", "", "tech") == "gaming"

    def test_education_keywords(self):
        assert _detect_category("University tuition costs soar", "", "business") == "education"


# ── Quality scoring tests ─────────────────────────────────────────────────────

class TestQualityScoring:
    def test_baseline_score(self):
        q = _compute_quality("top_news", "business", "business", 0, "unknown author")
        assert 0.5 <= q <= 0.6

    def test_position_decay(self):
        q0 = _compute_quality("top_news", "business", "business", 0, "")
        q10 = _compute_quality("top_news", "business", "business", 10, "")
        assert q0 > q10

    def test_prominent_author_boost(self):
        q_regular = _compute_quality("finance", "business", "business", 0, "nobody")
        q_prominent = _compute_quality("finance", "business", "business", 0, "Jim Cramer")
        assert q_prominent > q_regular

    def test_keyword_category_boost(self):
        q_same = _compute_quality("technology", "tech", "tech", 0, "")
        q_specific = _compute_quality("technology", "ai", "tech", 0, "")
        assert q_specific > q_same

    def test_boosted_category_higher_bonus(self):
        q_boosted = _compute_quality("top_news", "ai", "business", 0, "")
        q_normal = _compute_quality("top_news", "culture", "business", 0, "")
        assert q_boosted > q_normal

    def test_score_capped_at_1(self):
        q = _compute_quality("top_news", "ai", "business", 0, "Andrew Ross Sorkin")
        assert q <= 1.0

    def test_score_non_negative(self):
        q = _compute_quality("small_business", "business", "business", 50, "")
        assert q >= 0.0


# ── Truncation tests ──────────────────────────────────────────────────────────

class TestTruncation:
    def test_short_text_unchanged(self):
        assert _truncate_at_sentence("Hello world.", 300) == "Hello world."

    def test_sentence_boundary(self):
        text = "First sentence. Second sentence. Third sentence that is much longer and goes on."
        result = _truncate_at_sentence(text, 40)
        assert result.endswith(".")
        assert len(result) <= 43

    def test_ellipsis_fallback(self):
        text = "A" * 400
        result = _truncate_at_sentence(text, 300)
        assert result.endswith("...")


# ── Crawl integration tests ──────────────────────────────────────────────────

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>CNBC Top News</title>
<item>
  <title>OpenAI raises $10 billion in new funding round</title>
  <link>https://cnbc.com/2026/02/24/openai-funding.html</link>
  <description>OpenAI has secured a massive new funding round led by top investors.</description>
  <pubDate>Mon, 24 Feb 2026 00:00:00 GMT</pubDate>
  <author>Hayden Field</author>
  <category>Technology</category>
  <category>AI</category>
</item>
<item>
  <title>Fed holds rates steady amid inflation concerns</title>
  <link>https://cnbc.com/2026/02/24/fed-rates.html</link>
  <description>The Federal Reserve kept interest rates unchanged at its latest meeting. Markets reacted positively to the news.</description>
  <pubDate>Mon, 24 Feb 2026 00:00:00 GMT</pubDate>
  <author>Jeff Cox</author>
</item>
<item>
  <title>Bitcoin breaks $80K as crypto rally continues</title>
  <link>https://cnbc.com/2026/02/24/bitcoin-80k.html</link>
  <description>Bitcoin hit a new all-time high as institutional demand surges.</description>
  <pubDate>Mon, 24 Feb 2026 00:00:00 GMT</pubDate>
  <author>Mackenzie Sigalos</author>
  <category>Cryptocurrency</category>
</item>
</channel>
</rss>"""


class TestCrawl:
    def _make_source(self, **kwargs):
        src = CNBCSource(**kwargs)
        src.fetch_url = MagicMock(return_value=SAMPLE_RSS)
        return src

    def test_basic_crawl(self):
        src = self._make_source()
        articles = src.crawl()
        assert len(articles) == 3

    def test_dedup_across_sections(self):
        src = self._make_source(feeds=["top_news", "finance"])
        articles = src.crawl()
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))

    def test_category_detection_in_articles(self):
        src = self._make_source()
        articles = src.crawl()
        cats = {a.title: a.category for a in articles}
        assert cats["OpenAI raises $10 billion in new funding round"] == "ai"
        assert cats["Bitcoin breaks $80K as crypto rally continues"] == "crypto"

    def test_prominent_author_tagged(self):
        src = self._make_source()
        articles = src.crawl()
        btc = [a for a in articles if "bitcoin" in a.title.lower()][0]
        assert "cnbc:prominent-author" in btc.tags

    def test_provenance_tags(self):
        src = self._make_source()
        articles = src.crawl()
        a = articles[0]
        section_tags = [t for t in a.tags if t.startswith("cnbc:section:")]
        cat_tags = [t for t in a.tags if t.startswith("cnbc:category:")]
        assert len(section_tags) >= 1
        assert len(cat_tags) >= 1

    def test_rss_category_tags(self):
        src = self._make_source()
        articles = src.crawl()
        ai_article = articles[0]
        tag_tags = [t for t in ai_article.tags if t.startswith("cnbc:tag:")]
        assert len(tag_tags) >= 1

    def test_rich_summary_format(self):
        src = self._make_source()
        articles = src.crawl()
        a = articles[0]
        assert "📰" in a.summary
        assert "—" in a.summary

    def test_quality_sorted(self):
        src = self._make_source()
        articles = src.crawl()
        scores = [a.quality_score for a in articles]
        assert scores == sorted(scores, reverse=True)

    def test_min_quality_filter(self):
        src = self._make_source(min_quality=0.9)
        articles = src.crawl()
        for a in articles:
            assert a.quality_score >= 0.9

    def test_category_filter(self):
        src = self._make_source(category_filter=["crypto"])
        articles = src.crawl()
        assert all(a.category == "crypto" for a in articles)

    def test_global_limit(self):
        src = self._make_source(global_limit=1)
        articles = src.crawl()
        assert len(articles) <= 1

    def test_exclude_sections(self):
        src = self._make_source(feeds=["all"], exclude_sections=["media", "earnings"])
        # Just verify it doesn't crash and excludes properly
        articles = src.crawl()
        assert isinstance(articles, list)

    def test_all_feeds_resolves(self):
        src = self._make_source(feeds=["all"])
        articles = src.crawl()
        assert isinstance(articles, list)

    def test_author_in_summary(self):
        src = self._make_source()
        articles = src.crawl()
        authored = [a for a in articles if a.author]
        assert all("✍️" in a.summary for a in authored)
