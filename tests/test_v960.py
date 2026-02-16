"""Tests for Medium source enhancements (v9.6.0): reading time, quality scoring, category detection, provenance tags."""
import xml.etree.ElementTree as ET
from unittest.mock import patch
from clawler.sources.medium import (
    MediumSource,
    _estimate_reading_time,
    _detect_category,
    _compute_quality_score,
    _strip_html,
    SPECIFIC_CATEGORY_MAP,
    GENERIC_TECH_TAGS,
)


def _make_rss(items_xml: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Test</title>
    {items_xml}
  </channel>
</rss>"""


def _make_item(title="Test Article", url="https://medium.com/test-article",
               author="Jane Doe", categories=None, content="", desc=""):
    cats = ""
    if categories:
        cats = "".join(f"<category>{c}</category>" for c in categories)
    return f"""<item>
      <title>{title}</title>
      <link>{url}</link>
      <dc:creator>{author}</dc:creator>
      <pubDate>Mon, 16 Feb 2026 10:00:00 GMT</pubDate>
      {cats}
      <content:encoded><![CDATA[{content}]]></content:encoded>
      <description>{desc}</description>
    </item>"""


# --- Reading time estimation ---

def test_reading_time_short():
    """Short content should be 1 min minimum."""
    assert _estimate_reading_time("<p>Hello world</p>") == 1


def test_reading_time_medium():
    """~500 words ≈ 2 min."""
    content = "<p>" + " ".join(["word"] * 500) + "</p>"
    rt = _estimate_reading_time(content)
    assert 1 <= rt <= 3


def test_reading_time_long():
    """~2000 words ≈ 8 min."""
    content = "<p>" + " ".join(["word"] * 2000) + "</p>"
    rt = _estimate_reading_time(content)
    assert 7 <= rt <= 10


# --- Category detection ---

def test_category_specific_ai():
    """AI tags should map to 'ai' not 'tech'."""
    assert _detect_category(["machine-learning", "python"], "ml-tag", "tag") == "ai"


def test_category_specific_security():
    assert _detect_category(["cybersecurity"], "cybersecurity", "tag") == "security"


def test_category_specific_crypto():
    assert _detect_category(["bitcoin", "finance"], "bitcoin", "tag") == "crypto"


def test_category_specific_design():
    assert _detect_category(["ux-design"], "design", "tag") == "design"


def test_category_specific_health():
    assert _detect_category(["mental-health"], "health", "tag") == "health"


def test_category_generic_tech_fallback():
    """Tags only in generic tech set should map to 'tech'."""
    assert _detect_category(["react"], "react", "tag") == "tech"


def test_category_publication_override():
    assert _detect_category([], "towards-data-science", "publication") == "ai"


def test_category_label_specific():
    """Label itself can match specific map."""
    assert _detect_category([], "cryptocurrency", "tag") == "crypto"


# --- Quality scoring ---

def test_quality_score_short_article():
    """1 min, 0 tags = low score."""
    score = _compute_quality_score(1, 0)
    assert 0 < score < 0.4


def test_quality_score_long_well_tagged():
    """10 min, 5 tags = high score."""
    score = _compute_quality_score(10, 5)
    assert score > 0.7


# --- Provenance tags ---

def test_provenance_tags_tag_feed():
    src = MediumSource(tag_feeds=["ai"], publication_feeds=[], max_per_feed=1)
    content = " ".join(["word"] * 300)
    xml = _make_rss(_make_item(categories=["AI", "Python"], content=content))
    with patch.object(src, "fetch_url", return_value=xml):
        articles = src.crawl()
    assert len(articles) == 1
    tags = articles[0].tags
    assert "medium:tag:ai" in tags
    assert "medium:tag:python" in tags
    assert any(t.startswith("medium:tag:") for t in tags)


def test_provenance_tags_publication_feed():
    src = MediumSource(tag_feeds=[], publication_feeds=["better-programming"], max_per_feed=1)
    xml = _make_rss(_make_item(content="some content here"))
    with patch.object(src, "fetch_url", return_value=xml):
        articles = src.crawl()
    assert len(articles) == 1
    assert "medium:publication:better-programming" in articles[0].tags


# --- Reading time in summary ---

def test_summary_contains_reading_time():
    src = MediumSource(tag_feeds=["tech"], publication_feeds=[], max_per_feed=1)
    content = " ".join(["word"] * 500)
    xml = _make_rss(_make_item(content=content))
    with patch.object(src, "fetch_url", return_value=xml):
        articles = src.crawl()
    assert "📖" in articles[0].summary
    assert "min read" in articles[0].summary


# --- min_reading_time filter ---

def test_min_reading_time_filters():
    src = MediumSource(tag_feeds=["tech"], publication_feeds=[], max_per_feed=5, min_reading_time=5)
    short = _make_item(title="Short", url="https://medium.com/short", content="tiny")
    long_content = " ".join(["word"] * 1500)
    long = _make_item(title="Long", url="https://medium.com/long", content=long_content)
    xml = _make_rss(short + long)
    with patch.object(src, "fetch_url", return_value=xml):
        articles = src.crawl()
    assert len(articles) == 1
    assert articles[0].title == "Long"


# --- Limit ---

def test_limit():
    src = MediumSource(tag_feeds=["tech"], publication_feeds=[], max_per_feed=10, limit=1)
    items = _make_item(title="A", url="https://medium.com/a") + _make_item(title="B", url="https://medium.com/b")
    xml = _make_rss(items)
    with patch.object(src, "fetch_url", return_value=xml):
        articles = src.crawl()
    assert len(articles) == 1


# --- Quality score is set ---

def test_quality_score_set():
    src = MediumSource(tag_feeds=["tech"], publication_feeds=[], max_per_feed=1)
    content = " ".join(["word"] * 800)
    xml = _make_rss(_make_item(categories=["AI", "ML", "Python"], content=content))
    with patch.object(src, "fetch_url", return_value=xml):
        articles = src.crawl()
    assert articles[0].quality_score > 0


# --- Dedup still works ---

def test_dedup_across_feeds():
    src = MediumSource(tag_feeds=["ai", "ml"], publication_feeds=[], max_per_feed=5)
    xml = _make_rss(_make_item(title="Same", url="https://medium.com/same"))
    with patch.object(src, "fetch_url", return_value=xml):
        articles = src.crawl()
    assert len(articles) == 1
