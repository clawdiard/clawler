"""Tests for enhanced Economist source (v10.72.0)."""
import pytest
from unittest.mock import patch
from clawler.sources.economist import (
    EconomistSource,
    ECONOMIST_FEEDS,
    DEFAULT_SECTIONS,
    SPECIFIC_CATEGORIES,
    _detect_category,
    _truncate_at_sentence,
    _compute_quality,
    _parse_rss_date,
)


# ── Sample RSS XML ─────────────────────────────────────────────────────
SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>The Economist: Leaders</title>
<item>
  <title>The AI revolution is transforming the global economy</title>
  <link>https://www.economist.com/leaders/2026/02/24/ai-economy</link>
  <description>Artificial intelligence and machine learning are reshaping industries. Generative AI tools are boosting productivity across sectors.</description>
  <pubDate>Mon, 24 Feb 2026 00:00:00 GMT</pubDate>
  <dc:creator>The Economist</dc:creator>
  <category>Technology</category>
  <category>AI</category>
</item>
<item>
  <title>Why central banks must act on inflation now</title>
  <link>https://www.economist.com/leaders/2026/02/24/inflation</link>
  <description>The Federal Reserve and ECB face tough choices as consumer prices remain stubbornly high. Earnings reports show corporate resilience.</description>
  <pubDate>Mon, 24 Feb 2026 00:00:00 GMT</pubDate>
  <dc:creator>The Economist</dc:creator>
</item>
<item>
  <title>Bitcoin's surge raises questions about crypto regulation</title>
  <link>https://www.economist.com/leaders/2026/02/24/bitcoin</link>
  <description>Cryptocurrency markets are booming again as bitcoin approaches new highs. Blockchain technology adoption accelerates.</description>
  <pubDate>Mon, 24 Feb 2026 00:00:00 GMT</pubDate>
</item>
<item>
  <title>The war in Ukraine enters a new phase</title>
  <link>https://www.economist.com/leaders/2026/02/24/ukraine</link>
  <description>Diplomatic efforts intensify as the conflict reshapes European security architecture.</description>
  <pubDate>Mon, 24 Feb 2026 00:00:00 GMT</pubDate>
</item>
</channel>
</rss>"""

SAMPLE_RSS_SCIENCE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Economist: Science</title>
<item>
  <title>CRISPR gene editing cures a rare disease</title>
  <link>https://www.economist.com/science/2026/02/24/crispr</link>
  <description>A breakthrough clinical trial shows genome editing can cure sickle cell disease.</description>
  <pubDate>Mon, 24 Feb 2026 00:00:00 GMT</pubDate>
</item>
<item>
  <title>Climate change threatens coral reefs worldwide</title>
  <link>https://www.economist.com/science/2026/02/24/coral</link>
  <description>Rising ocean temperatures and pollution are devastating biodiversity in marine ecosystems.</description>
  <pubDate>Mon, 24 Feb 2026 00:00:00 GMT</pubDate>
</item>
</channel></rss>"""


def _make_source(**kwargs):
    src = EconomistSource(**kwargs)
    return src


# ── Feed configuration tests ──────────────────────────────────────────

def test_feed_count():
    assert len(ECONOMIST_FEEDS) == 16

def test_default_sections():
    assert len(DEFAULT_SECTIONS) == 10
    for s in DEFAULT_SECTIONS:
        assert s in ECONOMIST_FEEDS

def test_all_feeds_have_required_keys():
    for key, info in ECONOMIST_FEEDS.items():
        assert "url" in info
        assert "label" in info
        assert "default_cat" in info
        assert "prominence" in info

def test_prominence_range():
    for key, info in ECONOMIST_FEEDS.items():
        assert 0 < info["prominence"] <= 1.0, f"{key} prominence out of range"

def test_regional_feeds_have_region():
    regional = ["united-states", "asia", "europe", "china", "middle-east-and-africa", "the-americas", "britain"]
    for s in regional:
        assert "region" in ECONOMIST_FEEDS[s], f"{s} missing region"


# ── Category detection tests ──────────────────────────────────────────

def test_detect_ai_category():
    assert _detect_category("OpenAI launches GPT-5", "", "world") == "ai"

def test_detect_security_category():
    assert _detect_category("Major ransomware attack hits hospitals", "", "tech") == "security"

def test_detect_crypto_category():
    assert _detect_category("Bitcoin reaches new all-time high", "cryptocurrency markets surge", "business") == "crypto"

def test_detect_health_category():
    assert _detect_category("New vaccine approved by FDA", "clinical trial results", "science") == "health"

def test_detect_environment_category():
    assert _detect_category("Carbon emissions reach record levels", "fossil fuel deforestation", "world") == "environment"

def test_detect_fallback_to_section():
    assert _detect_category("A quiet week in politics", "nothing special", "world") == "world"

def test_specific_categories_coverage():
    assert len(SPECIFIC_CATEGORIES) == 12


# ── Truncation tests ──────────────────────────────────────────────────

def test_truncate_short():
    assert _truncate_at_sentence("Hello world.", 300) == "Hello world."

def test_truncate_at_sentence_boundary():
    text = "First sentence. Second sentence. " + "x" * 300
    result = _truncate_at_sentence(text, 300)
    assert result.endswith(".")
    assert len(result) <= 300

def test_truncate_no_sentence():
    text = "a" * 400
    result = _truncate_at_sentence(text, 300)
    assert len(result) == 300
    assert result.endswith("...")


# ── Quality scoring tests ─────────────────────────────────────────────

def test_quality_leaders_high():
    q = _compute_quality("leaders", 0.60, "ai", "world", 0)
    assert q > 0.65

def test_quality_position_decay():
    q0 = _compute_quality("leaders", 0.60, "world", "world", 0)
    q5 = _compute_quality("leaders", 0.60, "world", "world", 5)
    assert q0 > q5

def test_quality_keyword_boost():
    q_section = _compute_quality("business", 0.52, "business", "business", 0)
    q_keyword = _compute_quality("business", 0.52, "ai", "business", 0)
    assert q_keyword > q_section

def test_quality_boosted_category():
    q_ai = _compute_quality("leaders", 0.60, "ai", "world", 0)
    q_culture = _compute_quality("leaders", 0.60, "culture", "world", 0)
    assert q_ai > q_culture

def test_quality_max_one():
    q = _compute_quality("leaders", 0.60, "ai", "world", 0)
    assert q <= 1.0


# ── Date parsing tests ────────────────────────────────────────────────

def test_parse_rss_date_rfc2822():
    dt = _parse_rss_date("Mon, 24 Feb 2026 00:00:00 GMT")
    assert dt is not None
    assert dt.year == 2026

def test_parse_rss_date_iso():
    dt = _parse_rss_date("2026-02-24T12:00:00Z")
    assert dt is not None

def test_parse_rss_date_none():
    assert _parse_rss_date(None) is None

def test_parse_rss_date_garbage():
    assert _parse_rss_date("not a date") is None


# ── Source init tests ─────────────────────────────────────────────────

def test_default_init():
    src = _make_source()
    assert src._sections == DEFAULT_SECTIONS
    assert src.min_quality == 0.0
    assert src.global_limit is None

def test_all_sections():
    src = _make_source(sections=["all"])
    assert len(src._sections) == 16

def test_custom_sections():
    src = _make_source(sections=["leaders", "culture"])
    assert src._sections == ["leaders", "culture"]

def test_invalid_sections_filtered():
    src = _make_source(sections=["leaders", "nonexistent"])
    assert src._sections == ["leaders"]

def test_exclude_sections():
    src = _make_source(exclude_sections=["culture"])
    assert src.exclude_sections == ["culture"]


# ── Crawl tests (mocked) ─────────────────────────────────────────────

def test_crawl_parses_articles():
    src = _make_source(sections=["leaders"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    assert len(articles) == 4

def test_crawl_deduplicates():
    src = _make_source(sections=["leaders", "briefing"])
    def mock_fetch(url):
        return SAMPLE_RSS
    with patch.object(src, "fetch_url", side_effect=mock_fetch):
        articles = src.crawl()
    # Same URLs in both feeds → deduped to 4
    assert len(articles) == 4

def test_crawl_ai_detected():
    src = _make_source(sections=["leaders"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    ai_articles = [a for a in articles if a.category == "ai"]
    assert len(ai_articles) >= 1

def test_crawl_crypto_detected():
    src = _make_source(sections=["leaders"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    crypto = [a for a in articles if a.category == "crypto"]
    assert len(crypto) >= 1

def test_crawl_quality_sorted():
    src = _make_source(sections=["leaders"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    scores = [a.quality_score for a in articles]
    assert scores == sorted(scores, reverse=True)

def test_crawl_min_quality_filter():
    src = _make_source(sections=["leaders"], min_quality=0.9)
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    assert all((a.quality_score or 0) >= 0.9 for a in articles)

def test_crawl_category_filter():
    src = _make_source(sections=["leaders"], category_filter=["ai"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    assert all(a.category == "ai" for a in articles)

def test_crawl_global_limit():
    src = _make_source(sections=["leaders"], global_limit=2)
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    assert len(articles) <= 2

def test_crawl_exclude_sections():
    src = _make_source(sections=["leaders", "science-and-technology"], exclude_sections=["leaders"])
    feeds = {"leaders": SAMPLE_RSS, "science-and-technology": SAMPLE_RSS_SCIENCE}
    def mock_fetch(url):
        for key, info in ECONOMIST_FEEDS.items():
            if info["url"] == url:
                return feeds.get(key, "")
        return ""
    with patch.object(src, "fetch_url", side_effect=mock_fetch):
        articles = src.crawl()
    # Leaders excluded, only science articles
    assert all("Leaders" not in a.source for a in articles)

def test_crawl_multi_section():
    src = _make_source(sections=["leaders", "science-and-technology"])
    feeds_map = {}
    for key, info in ECONOMIST_FEEDS.items():
        if key == "leaders":
            feeds_map[info["url"]] = SAMPLE_RSS
        elif key == "science-and-technology":
            feeds_map[info["url"]] = SAMPLE_RSS_SCIENCE
    with patch.object(src, "fetch_url", side_effect=lambda u: feeds_map.get(u, "")):
        articles = src.crawl()
    assert len(articles) == 6  # 4 leaders + 2 science


# ── Article field tests ───────────────────────────────────────────────

def test_article_source_format():
    src = _make_source(sections=["leaders"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    assert all("The Economist" in a.source for a in articles)

def test_article_has_tags():
    src = _make_source(sections=["leaders"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    for a in articles:
        assert any(t.startswith("economist:section:") for t in a.tags)
        assert any(t.startswith("economist:category:") for t in a.tags)

def test_article_rss_category_tags():
    src = _make_source(sections=["leaders"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    ai_art = [a for a in articles if a.category == "ai"][0]
    assert "economist:tag:ai" in ai_art.tags

def test_article_rich_summary():
    src = _make_source(sections=["leaders"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    for a in articles:
        assert "📰" in a.summary

def test_article_timestamp():
    src = _make_source(sections=["leaders"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    assert all(a.timestamp is not None for a in articles)

def test_article_quality_range():
    src = _make_source(sections=["leaders"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    for a in articles:
        assert 0 <= a.quality_score <= 1.0


# ── Regional tag tests ────────────────────────────────────────────────

def test_regional_tags():
    src = _make_source(sections=["united-states"])
    rss = SAMPLE_RSS.replace("Leaders", "United States")
    with patch.object(src, "fetch_url", return_value=rss):
        articles = src.crawl()
    assert any("economist:region:us" in a.tags for a in articles)


# ── Edge cases ────────────────────────────────────────────────────────

def test_empty_feed():
    src = _make_source(sections=["leaders"])
    with patch.object(src, "fetch_url", return_value=""):
        articles = src.crawl()
    assert articles == []

def test_malformed_xml():
    src = _make_source(sections=["leaders"])
    with patch.object(src, "fetch_url", return_value="<not valid xml"):
        articles = src.crawl()
    assert articles == []

def test_fetch_failure():
    src = _make_source(sections=["leaders"])
    with patch.object(src, "fetch_url", side_effect=Exception("network error")):
        articles = src.crawl()
    assert articles == []
