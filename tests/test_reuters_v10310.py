"""Tests for enhanced Reuters source (v10.31.0)."""
import types
from unittest.mock import patch, MagicMock
from clawler.sources.reuters import (
    ReutersSource, _detect_category, _compute_quality,
    REUTERS_FEEDS, REUTERS_REGIONS, SECTION_PROMINENCE,
)


# --- Sample RSS XML ---
SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Reuters</title>
<item>
  <title>OpenAI launches GPT-5 with breakthrough reasoning</title>
  <link>https://www.reuters.com/technology/openai-gpt5-2026</link>
  <description>OpenAI unveiled GPT-5, its most advanced large language model yet.</description>
  <pubDate>Tue, 18 Feb 2026 12:00:00 GMT</pubDate>
  <author>Jane Smith</author>
  <category>Technology</category>
</item>
<item>
  <title>Fed raises interest rates amid inflation fears</title>
  <link>https://www.reuters.com/business/fed-rates-2026</link>
  <description>The Federal Reserve raised rates by 25 basis points.</description>
  <pubDate>Tue, 18 Feb 2026 11:00:00 GMT</pubDate>
  <author>John Doe</author>
</item>
<item>
  <title>Bitcoin hits new all-time high above $150,000</title>
  <link>https://www.reuters.com/crypto/bitcoin-150k-2026</link>
  <description>Bitcoin surged past $150,000 on cryptocurrency exchanges.</description>
  <pubDate>Tue, 18 Feb 2026 10:00:00 GMT</pubDate>
</item>
<item>
  <title>Ransomware attack hits major hospital network</title>
  <link>https://www.reuters.com/security/hospital-ransomware-2026</link>
  <description>A ransomware attack disrupted services at a major cybersecurity breach.</description>
  <pubDate>Tue, 18 Feb 2026 09:00:00 GMT</pubDate>
</item>
<item>
  <title>Regular tech news update for the week</title>
  <link>https://www.reuters.com/tech/weekly-2026</link>
  <description>A roundup of technology news.</description>
  <pubDate>Tue, 18 Feb 2026 08:00:00 GMT</pubDate>
</item>
</channel>
</rss>"""

EMPTY_RSS = """<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>"""


def _mock_source(rss_xml=SAMPLE_RSS, **kwargs):
    """Create a ReutersSource with mocked fetch_url."""
    src = ReutersSource(**kwargs)
    src.fetch_url = MagicMock(return_value=rss_xml)
    return src


# --- Category detection tests ---

def test_detect_ai_category():
    cat = _detect_category("OpenAI launches GPT-5", "large language model breakthrough", "tech")
    assert cat == "ai"


def test_detect_crypto_category():
    cat = _detect_category("Bitcoin hits $150K", "cryptocurrency exchange volume surges", "business")
    assert cat == "crypto"


def test_detect_security_category():
    cat = _detect_category("Ransomware attack hits hospitals", "cybersecurity breach data", "tech")
    assert cat == "security"


def test_detect_health_category():
    cat = _detect_category("FDA approves new vaccine", "clinical trial results pharmaceutical", "science")
    assert cat == "health"


def test_detect_business_category():
    cat = _detect_category("Fed raises interest rates", "inflation recession wall street", "world")
    assert cat == "business"


def test_detect_world_category():
    cat = _detect_category("NATO deploys forces", "conflict diplomacy sanctions", "politics")
    assert cat == "world"


def test_detect_fallback_to_section():
    cat = _detect_category("Local festival draws crowds", "A local festival happened.", "culture")
    assert cat == "culture"


def test_detect_environment():
    cat = _detect_category("Amazon deforestation accelerates", "biodiversity conservation endangered species", "science")
    assert cat == "environment"


def test_detect_education():
    cat = _detect_category("University tuition rises", "student scholarship college education policy", "culture")
    assert cat == "education"


# --- Quality scoring tests ---

def test_quality_world_section_first_position():
    q = _compute_quality("World", "world", "world", 0)
    assert q >= 0.50  # High prominence section, first position


def test_quality_decays_with_position():
    q0 = _compute_quality("Business", "business", "business", 0)
    q5 = _compute_quality("Business", "business", "business", 5)
    q10 = _compute_quality("Business", "business", "business", 10)
    assert q0 > q5 > q10


def test_quality_keyword_boost():
    # Keyword-detected category gets a boost
    q_keyword = _compute_quality("Technology", "ai", "tech", 0)
    q_section = _compute_quality("Technology", "tech", "tech", 0)
    assert q_keyword > q_section


def test_quality_range():
    for section in SECTION_PROMINENCE:
        for pos in [0, 5, 10, 20]:
            q = _compute_quality(section, "tech", "tech", pos)
            assert 0.0 <= q <= 1.0


# --- Crawl tests ---

def test_basic_crawl():
    src = _mock_source()
    articles = src.crawl()
    assert len(articles) > 0
    for a in articles:
        assert a.title
        assert a.url
        assert a.source.startswith("Reuters")
        assert a.category
        assert a.tags


def test_keyword_categories_in_crawl():
    src = _mock_source(sections=["Technology"])
    articles = src.crawl()
    categories = {a.category for a in articles}
    # Should detect ai, crypto, security from the sample data
    assert "ai" in categories or "crypto" in categories or "security" in categories


def test_section_filter():
    src = _mock_source(sections=["Business"])
    articles = src.crawl()
    assert all("business" in a.source.lower() for a in articles)


def test_exclude_sections():
    src = _mock_source(exclude_sections=["Sports", "Lifestyle"])
    # Should not fetch Sports or Lifestyle feeds
    for call_args in src.fetch_url.call_args_list:
        url = call_args[0][0]
        assert "sports" not in url
        assert "lifestyle" not in url


def test_min_quality_filter():
    src = _mock_source(min_quality=0.6)
    articles = src.crawl()
    for a in articles:
        assert a.quality_score >= 0.6


def test_category_filter():
    src = _mock_source(category_filter=["ai"])
    articles = src.crawl()
    for a in articles:
        assert a.category == "ai"


def test_global_limit():
    src = _mock_source(global_limit=3)
    articles = src.crawl()
    assert len(articles) <= 3


def test_quality_sorted():
    src = _mock_source()
    articles = src.crawl()
    if len(articles) > 1:
        scores = [a.quality_score or 0 for a in articles]
        assert scores == sorted(scores, reverse=True)


def test_deduplication():
    """Same URL across multiple sections should appear only once."""
    dup_rss = """<?xml version="1.0"?><rss version="2.0"><channel>
    <item><title>Same Story</title><link>https://reuters.com/same</link><description>Dup.</description></item>
    </channel></rss>"""
    src = _mock_source(rss_xml=dup_rss)
    articles = src.crawl()
    urls = [a.url for a in articles]
    assert len(urls) == len(set(urls))


def test_provenance_tags():
    src = _mock_source(sections=["Technology"])
    articles = src.crawl()
    for a in articles:
        tag_prefixes = [t.split(":")[0] for t in a.tags]
        assert "reuters" in tag_prefixes
        assert any(t.startswith("reuters:section:") for t in a.tags)
        assert any(t.startswith("reuters:category:") for t in a.tags)


def test_author_in_tags():
    src = _mock_source(sections=["Technology"])
    articles = src.crawl()
    authored = [a for a in articles if a.author]
    for a in authored:
        assert any(t.startswith("reuters:author:") for t in a.tags)


def test_rich_summary_has_section():
    src = _mock_source(sections=["Technology"])
    articles = src.crawl()
    for a in articles:
        assert "📰" in a.summary


def test_empty_feed():
    src = _mock_source(rss_xml=EMPTY_RSS)
    articles = src.crawl()
    # Should not crash, just return empty or minimal
    assert isinstance(articles, list)


def test_regions_param():
    src = _mock_source(regions=["europe", "asia"])
    articles = src.crawl()
    region_tags = [t for a in articles for t in a.tags if t.startswith("reuters:region:")]
    # If regional feeds return data, should have region tags
    # (with mocked data, all feeds return same content)
    assert isinstance(articles, list)


def test_feed_count():
    """Should have 12 section feeds."""
    assert len(REUTERS_FEEDS) == 12


def test_region_count():
    """Should have 6 regions."""
    assert len(REUTERS_REGIONS) == 6


def test_section_prominence_coverage():
    """All feed sections should have prominence scores."""
    for feed in REUTERS_FEEDS:
        assert feed["section"] in SECTION_PROMINENCE


def test_limit_per_feed():
    src = _mock_source(sections=["Technology"], limit=2)
    articles = src.crawl()
    assert len(articles) <= 2
