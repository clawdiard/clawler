"""Tests for BBC News source v10.34 enhancements."""
import types
from unittest.mock import patch

import pytest

from clawler.sources.bbc import (
    BBC_FEEDS,
    BBCNewsSource,
    KEYWORD_CATEGORIES,
    PROMINENT_AUTHORS,
    _detect_category,
    _quality_score,
)

# ── helpers ────────────────────────────────────────────────────────

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>BBC News</title>
<item>
  <title>OpenAI launches new AI safety board</title>
  <link>https://www.bbc.co.uk/news/technology-123</link>
  <description>The company announced a new safety initiative for artificial intelligence models.</description>
  <pubDate>Tue, 18 Feb 2026 12:00:00 GMT</pubDate>
  <author>Zoe Kleinman</author>
</item>
<item>
  <title>UK economy grows faster than expected</title>
  <link>https://www.bbc.co.uk/news/business-456</link>
  <description>GDP figures show stronger growth in the latest quarter.</description>
  <pubDate>Tue, 18 Feb 2026 11:00:00 GMT</pubDate>
  <author>Faisal Islam</author>
</item>
<item>
  <title>New ransomware attack hits hospitals</title>
  <link>https://www.bbc.co.uk/news/tech-789</link>
  <description>NHS trusts affected by widespread ransomware campaign.</description>
  <pubDate>Tue, 18 Feb 2026 10:00:00 GMT</pubDate>
</item>
<item>
  <title>Bitcoin reaches new all-time high</title>
  <link>https://www.bbc.co.uk/news/business-101</link>
  <description>Cryptocurrency markets surge as bitcoin tops $150,000.</description>
  <pubDate>Tue, 18 Feb 2026 09:00:00 GMT</pubDate>
</item>
<item>
  <title>Local council approves new park</title>
  <link>https://www.bbc.co.uk/news/local-202</link>
  <description>Plans approved for a new community green space.</description>
  <pubDate>Tue, 18 Feb 2026 08:00:00 GMT</pubDate>
</item>
</channel>
</rss>"""


def _mock_source(**kwargs):
    src = BBCNewsSource(**kwargs)
    src.fetch_url = lambda url: SAMPLE_RSS
    return src


# ── feed configuration ─────────────────────────────────────────────

def test_feed_count():
    """Should have 17 section feeds (expanded from 10)."""
    assert len(BBC_FEEDS) == 17


def test_all_feeds_have_required_keys():
    for f in BBC_FEEDS:
        assert "url" in f
        assert "section" in f
        assert "label" in f
        assert "category" in f
        assert "prominence" in f
        assert 0.0 <= f["prominence"] <= 1.0


def test_regional_feeds_present():
    sections = {f["section"] for f in BBC_FEEDS}
    for region in ("africa", "asia", "europe", "latin_america", "middle_east", "us_canada"):
        assert region in sections, f"Missing regional feed: {region}"


# ── category detection ─────────────────────────────────────────────

def test_detect_ai_category():
    assert _detect_category("OpenAI launches GPT-5", "", "tech") == "ai"


def test_detect_security_category():
    assert _detect_category("Major ransomware attack", "", "tech") == "security"


def test_detect_crypto_category():
    assert _detect_category("Bitcoin surges past $200k", "", "business") == "crypto"


def test_detect_health_from_summary():
    assert _detect_category("New findings", "NHS announces vaccine rollout", "general") == "health"


def test_fallback_to_section_category():
    assert _detect_category("Nothing special here", "Just a regular story", "sports") == "sports"


def test_environment_category():
    assert _detect_category("Net zero targets missed", "Carbon emissions rising", "science") == "environment"


# ── quality scoring ────────────────────────────────────────────────

def test_quality_score_position_zero_highest():
    s0 = _quality_score(0.5, 0, "", "tech")
    s5 = _quality_score(0.5, 5, "", "tech")
    assert s0 > s5


def test_prominent_author_boost():
    base = _quality_score(0.5, 0, "Nobody", "tech")
    boosted = _quality_score(0.5, 0, "Laura Kuenssberg", "tech")
    assert boosted > base


def test_specific_category_boost():
    generic = _quality_score(0.5, 0, "", "tech")
    specific = _quality_score(0.5, 0, "", "ai")
    assert specific > generic


def test_quality_score_capped_at_one():
    score = _quality_score(1.0, 0, "Laura Kuenssberg", "ai")
    assert score <= 1.0


def test_quality_score_nonnegative():
    score = _quality_score(0.0, 100, "", "general")
    assert score >= 0.0


# ── crawling ───────────────────────────────────────────────────────

def test_crawl_returns_articles():
    src = _mock_source()
    articles = src.crawl()
    assert len(articles) > 0


def test_crawl_deduplicates_across_sections():
    src = _mock_source()
    articles = src.crawl()
    urls = [a.url for a in articles]
    assert len(urls) == len(set(urls))


def test_crawl_sorted_by_quality():
    src = _mock_source()
    articles = src.crawl()
    scores = [a.quality_score for a in articles]
    assert scores == sorted(scores, reverse=True)


def test_section_filter():
    src = _mock_source(sections=["technology"])
    articles = src.crawl()
    assert all("bbc:section:technology" in a.tags for a in articles)


def test_exclude_sections():
    src = _mock_source(exclude_sections=["sport", "entertainment"])
    articles = src.crawl()
    for a in articles:
        assert "bbc:section:sport" not in a.tags
        assert "bbc:section:entertainment" not in a.tags


def test_global_limit():
    src = _mock_source(global_limit=3)
    articles = src.crawl()
    assert len(articles) <= 3


def test_min_quality_filter():
    src = _mock_source(min_quality=0.99)
    articles = src.crawl()
    # Very high threshold should filter most/all
    for a in articles:
        assert a.quality_score >= 0.99


def test_category_filter():
    src = _mock_source(category_filter=["ai"])
    articles = src.crawl()
    for a in articles:
        assert a.category == "ai"


# ── provenance tags ────────────────────────────────────────────────

def test_provenance_tags_present():
    src = _mock_source(sections=["technology"])
    articles = src.crawl()
    for a in articles:
        section_tags = [t for t in a.tags if t.startswith("bbc:section:")]
        cat_tags = [t for t in a.tags if t.startswith("bbc:category:")]
        assert len(section_tags) == 1
        assert len(cat_tags) == 1


def test_author_provenance_tag():
    src = _mock_source(sections=["technology"])
    articles = src.crawl()
    authored = [a for a in articles if a.author]
    assert len(authored) > 0
    for a in authored:
        author_tags = [t for t in a.tags if t.startswith("bbc:author:")]
        assert len(author_tags) == 1


# ── rich summaries ─────────────────────────────────────────────────

def test_summary_contains_section_label():
    src = _mock_source(sections=["technology"])
    articles = src.crawl()
    assert any("📰 Technology" in (a.summary or "") for a in articles)


def test_summary_contains_author():
    src = _mock_source(sections=["technology"])
    articles = src.crawl()
    assert any("✍️" in (a.summary or "") for a in articles)


# ── keyword coverage ───────────────────────────────────────────────

def test_keyword_categories_non_empty():
    assert len(KEYWORD_CATEGORIES) >= 12
    for cat, kws in KEYWORD_CATEGORIES.items():
        assert len(kws) >= 3, f"Category {cat} has too few keywords"


def test_prominent_authors_non_empty():
    assert len(PROMINENT_AUTHORS) >= 10


# ── backward compatibility ─────────────────────────────────────────

def test_default_params_work():
    """Default constructor should work without arguments."""
    src = BBCNewsSource()
    assert src.sections is None
    assert src.min_quality == 0.0
    assert src.global_limit is None
    assert src.category_filter is None


def test_source_name():
    assert BBCNewsSource.name == "bbc"
