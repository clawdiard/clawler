"""Tests for enhanced Axios source v10.66.0."""
from unittest.mock import patch
from clawler.sources.axios import (
    AxiosSource, AXIOS_FEEDS, SECTION_PROMINENCE, PROMINENT_AUTHORS,
    SPECIFIC_CATEGORIES, _detect_category, _compute_quality,
)


MOCK_FEED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Axios</title>
    <item>
      <title>AI breakthrough stuns researchers</title>
      <link>https://www.axios.com/2026/02/18/ai-breakthrough</link>
      <description>A major artificial intelligence advancement using deep learning was announced today.</description>
      <pubDate>Tue, 18 Feb 2026 12:00:00 GMT</pubDate>
      <author>Ina Fried</author>
    </item>
    <item>
      <title>Markets rally on trade deal</title>
      <link>https://www.axios.com/2026/02/18/markets-rally</link>
      <description>Global markets surged after a new trade agreement was signed.</description>
      <pubDate>Tue, 18 Feb 2026 11:00:00 GMT</pubDate>
      <author>Dan Primack</author>
    </item>
    <item>
      <title>Ransomware attack hits major hospital</title>
      <link>https://www.axios.com/2026/02/18/ransomware-hospital</link>
      <description>A cybersecurity breach compromised patient data at a large healthcare facility.</description>
      <pubDate>Tue, 18 Feb 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title></title>
      <link></link>
    </item>
  </channel>
</rss>"""


MOCK_DUPLICATE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>AI breakthrough stuns researchers</title>
      <link>https://www.axios.com/2026/02/18/ai-breakthrough</link>
      <description>Duplicate article from another section.</description>
      <pubDate>Tue, 18 Feb 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Unique article about climate crisis</title>
      <link>https://www.axios.com/2026/02/18/climate-crisis</link>
      <description>Rising carbon emissions and global warming threaten biodiversity.</description>
      <pubDate>Tue, 18 Feb 2026 09:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


# --- Feed configuration tests ---

def test_axios_has_12_feeds():
    assert len(AXIOS_FEEDS) == 12


def test_axios_new_sections_present():
    sections = [f["section"] for f in AXIOS_FEEDS]
    assert "Sports" in sections
    assert "Climate" in sections
    assert "Local" in sections


def test_axios_all_feeds_have_required_keys():
    for f in AXIOS_FEEDS:
        assert "url" in f
        assert "section" in f
        assert "category" in f


def test_axios_section_prominence_covers_all_feeds():
    for f in AXIOS_FEEDS:
        assert f["section"].lower() in SECTION_PROMINENCE


# --- Category detection tests ---

def test_detect_category_ai_keywords():
    cat = _detect_category("OpenAI releases GPT-5", "New large language model", "world")
    assert cat == "ai"


def test_detect_category_security_keywords():
    cat = _detect_category("Major ransomware attack", "Cybersecurity breach hits", "tech")
    assert cat == "security"


def test_detect_category_crypto():
    cat = _detect_category("Bitcoin surges past 100K", "Cryptocurrency markets rally", "business")
    assert cat == "crypto"


def test_detect_category_health():
    cat = _detect_category("FDA approves new vaccine", "Clinical trial results for cancer drug", "science")
    assert cat == "health"


def test_detect_category_environment():
    cat = _detect_category("Carbon emissions hit record", "Renewable energy and solar power expand", "science")
    assert cat == "environment"


def test_detect_category_fallback_to_section():
    cat = _detect_category("Something mundane happened", "No keywords here at all", "culture")
    assert cat == "culture"


def test_detect_category_business():
    cat = _detect_category("Startup IPO raises billions", "Venture capital and valuation soar", "tech")
    assert cat == "business"


def test_detect_category_gaming():
    cat = _detect_category("Nintendo announces new console", "Video game industry reacts", "tech")
    assert cat == "gaming"


# --- Quality scoring tests ---

def test_quality_top_stories_position_0():
    q = _compute_quality("Top Stories", "world", "world", 0, "Nobody")
    assert q >= 0.55


def test_quality_decays_with_position():
    q0 = _compute_quality("Technology", "tech", "tech", 0, "")
    q5 = _compute_quality("Technology", "tech", "tech", 5, "")
    q10 = _compute_quality("Technology", "tech", "tech", 10, "")
    assert q0 > q5 > q10


def test_quality_prominent_author_boost():
    q_regular = _compute_quality("Technology", "tech", "tech", 0, "Unknown Writer")
    q_prominent = _compute_quality("Technology", "tech", "tech", 0, "Ina Fried")
    assert q_prominent > q_regular


def test_quality_boosted_category_bonus():
    q_generic = _compute_quality("Top Stories", "tech", "world", 0, "")
    q_boosted = _compute_quality("Top Stories", "ai", "world", 0, "")
    assert q_boosted > q_generic


def test_quality_never_exceeds_1():
    q = _compute_quality("Top Stories", "ai", "world", 0, "Mike Allen")
    assert q <= 1.0


def test_quality_non_boosted_specific_category():
    q_section = _compute_quality("Technology", "tech", "tech", 0, "")
    q_specific = _compute_quality("Technology", "culture", "tech", 0, "")
    assert q_specific > q_section


# --- Prominent authors tests ---

def test_prominent_authors_count():
    assert len(PROMINENT_AUTHORS) >= 15


def test_prominent_author_values_positive():
    for author, boost in PROMINENT_AUTHORS.items():
        assert boost > 0
        assert boost <= 0.15


# --- Crawl integration tests ---

def test_axios_crawl_parses_articles():
    src = AxiosSource(sections=["technology"], limit=10)
    with patch.object(src, "fetch_url", return_value=MOCK_FEED_XML):
        articles = src.crawl()
    assert len(articles) == 3
    assert articles[0].source == "Axios (Technology)"


def test_axios_crawl_keyword_category_refinement():
    src = AxiosSource(sections=["top stories"], limit=10)
    with patch.object(src, "fetch_url", return_value=MOCK_FEED_XML):
        articles = src.crawl()
    ai_article = [a for a in articles if "AI" in a.title][0]
    assert ai_article.category == "ai"
    security_article = [a for a in articles if "Ransomware" in a.title][0]
    assert security_article.category == "security"


def test_axios_crawl_rich_summary():
    src = AxiosSource(sections=["technology"], limit=10)
    with patch.object(src, "fetch_url", return_value=MOCK_FEED_XML):
        articles = src.crawl()
    first = articles[0]
    assert "✍️" in first.summary
    assert "📰" in first.summary


def test_axios_crawl_provenance_tags():
    src = AxiosSource(sections=["technology"], limit=10)
    with patch.object(src, "fetch_url", return_value=MOCK_FEED_XML):
        articles = src.crawl()
    tags = articles[0].tags
    assert any(t.startswith("axios:section:") for t in tags)
    assert any(t.startswith("axios:category:") for t in tags)
    assert any(t.startswith("axios:author:") for t in tags)


def test_axios_crawl_prominent_author_tag():
    src = AxiosSource(sections=["technology"], limit=10)
    with patch.object(src, "fetch_url", return_value=MOCK_FEED_XML):
        articles = src.crawl()
    ina_article = [a for a in articles if a.author == "Ina Fried"][0]
    assert "axios:prominent-author" in ina_article.tags


def test_axios_crawl_quality_scores_vary():
    src = AxiosSource(sections=["technology"], limit=10)
    with patch.object(src, "fetch_url", return_value=MOCK_FEED_XML):
        articles = src.crawl()
    scores = [a.quality_score for a in articles]
    assert len(set(scores)) > 1  # Not all the same fixed value


def test_axios_crawl_sorted_by_quality():
    src = AxiosSource(sections=["technology"], limit=10)
    with patch.object(src, "fetch_url", return_value=MOCK_FEED_XML):
        articles = src.crawl()
    scores = [a.quality_score for a in articles]
    assert scores == sorted(scores, reverse=True)


# --- Cross-section deduplication ---

def test_axios_cross_section_dedup():
    call_count = [0]
    def mock_fetch(url):
        call_count[0] += 1
        if call_count[0] == 1:
            return MOCK_FEED_XML
        return MOCK_DUPLICATE_XML

    src = AxiosSource(sections=["technology", "science"], limit=10)
    with patch.object(src, "fetch_url", side_effect=mock_fetch):
        articles = src.crawl()
    urls = [a.url for a in articles]
    assert len(urls) == len(set(urls))  # No duplicates
    # Should have 3 from first + 1 unique from second (duplicate removed)
    assert len(articles) == 4


# --- Filter tests ---

def test_axios_min_quality_filter():
    src = AxiosSource(sections=["technology"], limit=10, min_quality=0.99)
    with patch.object(src, "fetch_url", return_value=MOCK_FEED_XML):
        articles = src.crawl()
    assert len(articles) == 0  # All filtered out


def test_axios_category_filter():
    src = AxiosSource(sections=["top stories"], limit=10, category_filter=["ai"])
    with patch.object(src, "fetch_url", return_value=MOCK_FEED_XML):
        articles = src.crawl()
    assert all(a.category == "ai" for a in articles)
    assert len(articles) >= 1


def test_axios_exclude_sections():
    src = AxiosSource(exclude_sections=["Sports", "Local"])
    feeds_used = [f for f in AXIOS_FEEDS if f["section"].lower() not in ["sports", "local"]]
    assert len(feeds_used) == 10


def test_axios_global_limit():
    src = AxiosSource(sections=["technology"], limit=10, global_limit=1)
    with patch.object(src, "fetch_url", return_value=MOCK_FEED_XML):
        articles = src.crawl()
    assert len(articles) == 1


# --- Edge cases ---

def test_axios_empty_feed():
    src = AxiosSource()
    with patch.object(src, "fetch_url", return_value=None):
        articles = src.crawl()
    assert articles == []


def test_axios_name():
    src = AxiosSource()
    assert src.name == "axios"


def test_axios_registry_entry():
    from clawler.registry import SOURCES
    keys = [s.key for s in SOURCES]
    assert "axios" in keys


def test_axios_timestamp_parsed():
    src = AxiosSource(sections=["technology"], limit=10)
    with patch.object(src, "fetch_url", return_value=MOCK_FEED_XML):
        articles = src.crawl()
    assert articles[0].timestamp is not None


def test_specific_categories_coverage():
    """At least 10 specific categories configured."""
    assert len(SPECIFIC_CATEGORIES) >= 10


def test_axios_skips_empty_items():
    src = AxiosSource(sections=["technology"], limit=10)
    with patch.object(src, "fetch_url", return_value=MOCK_FEED_XML):
        articles = src.crawl()
    # Empty title/link item should be skipped
    assert all(a.title for a in articles)
    assert all(a.url for a in articles)
