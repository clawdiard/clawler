"""Tests for Wikipedia Current Events v2 enhancements (v9.2.0)."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.wikipedia import (
    WikipediaCurrentEventsSource,
    _map_category,
    PORTAL_URL,
    MAIN_PAGE_URL,
)

# ── category mapping tests ────────────────────────────────────────────────────

def test_category_armed_conflict():
    assert _map_category("Armed conflicts and attacks") == "world"

def test_category_politics():
    assert _map_category("International relations and diplomacy") == "world"

def test_category_science():
    assert _map_category("Science and technology breakthroughs") == "science"

def test_category_health():
    assert _map_category("WHO declares pandemic over") == "health"

def test_category_tech():
    assert _map_category("New AI chip from semiconductor giant") == "tech"

def test_category_business():
    assert _map_category("Stock market crashes amid recession fears") == "business"

def test_category_environment():
    assert _map_category("Wildfire destroys thousands of acres") == "environment"

def test_category_culture():
    assert _map_category("Oscar nominations announced") == "culture"

def test_category_fallback():
    assert _map_category("Something completely unrelated xyz") == "world"

# ── constructor tests ─────────────────────────────────────────────────────────

def test_default_params():
    src = WikipediaCurrentEventsSource()
    assert src.days == 1
    assert src.include_itn is True
    assert src.limit == 50

def test_days_clamped():
    assert WikipediaCurrentEventsSource(days=0).days == 1
    assert WikipediaCurrentEventsSource(days=10).days == 7

# ── portal parsing tests ─────────────────────────────────────────────────────

SAMPLE_PORTAL_HTML = """
<div class="current-events-content">
  <b>Armed conflicts and attacks</b>
  <ul>
    <li>A major <a href="/wiki/Battle_of_Example">battle</a> takes place in the region,
    resulting in heavy casualties.
    <a href="https://example.com/news/battle">(Reuters)</a></li>
  </ul>
  <b>Science and technology</b>
  <ul>
    <li><a href="/wiki/Mars_mission">NASA launches</a> a new rover mission to Mars.
    <a href="https://example.com/news/mars">(AP)</a></li>
    <li>Short item</li>
  </ul>
</div>
"""

def test_parse_portal_extracts_articles():
    src = WikipediaCurrentEventsSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_PORTAL_HTML):
        articles = []
        seen = set()
        src._parse_portal_page(PORTAL_URL, articles, seen)
        assert len(articles) == 2
        assert articles[0].category == "world"
        assert articles[0].url == "https://example.com/news/battle"
        assert articles[1].category == "science"
        assert "wiki:section:science-and-technology" in articles[1].tags

def test_parse_portal_deduplicates():
    src = WikipediaCurrentEventsSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_PORTAL_HTML):
        articles = []
        seen = set()
        src._parse_portal_page(PORTAL_URL, articles, seen)
        src._parse_portal_page(PORTAL_URL, articles, seen)
        assert len(articles) == 2  # no duplicates

# ── ITN parsing tests ─────────────────────────────────────────────────────────

SAMPLE_MAIN_PAGE_HTML = """
<div id="mp-itn">
  <ul>
    <li>The <b><a href="/wiki/2026_Election">2026 election</a></b> results in a surprise outcome.</li>
    <li>A devastating <a href="/wiki/Earthquake">earthquake</a> strikes the Pacific region.</li>
  </ul>
</div>
"""

def test_parse_itn_extracts_articles():
    src = WikipediaCurrentEventsSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_MAIN_PAGE_HTML):
        articles = []
        seen = set()
        src._parse_itn(articles, seen)
        assert len(articles) == 2
        assert articles[0].source == "Wikipedia In the News"
        assert articles[0].quality_score == 0.85
        assert "in-the-news" in articles[0].tags
        assert "wikipedia.org" in articles[0].url

def test_parse_itn_bold_link_preferred():
    src = WikipediaCurrentEventsSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_MAIN_PAGE_HTML):
        articles = []
        seen = set()
        src._parse_itn(articles, seen)
        # First item has bold link — should use that
        assert "2026_Election" in articles[0].url

# ── full crawl integration ────────────────────────────────────────────────────

def test_crawl_single_day_with_itn():
    src = WikipediaCurrentEventsSource(days=1, include_itn=True)
    with patch.object(src, "fetch_url") as mock_fetch:
        mock_fetch.side_effect = lambda url, **kw: (
            SAMPLE_PORTAL_HTML if "Portal" in url else SAMPLE_MAIN_PAGE_HTML
        )
        articles = src.crawl()
        assert len(articles) == 4  # 2 portal + 2 ITN

def test_crawl_respects_limit():
    src = WikipediaCurrentEventsSource(days=1, include_itn=True, limit=2)
    with patch.object(src, "fetch_url") as mock_fetch:
        mock_fetch.side_effect = lambda url, **kw: (
            SAMPLE_PORTAL_HTML if "Portal" in url else SAMPLE_MAIN_PAGE_HTML
        )
        articles = src.crawl()
        assert len(articles) == 2

def test_crawl_without_itn():
    src = WikipediaCurrentEventsSource(days=1, include_itn=False)
    with patch.object(src, "fetch_url", return_value=SAMPLE_PORTAL_HTML):
        articles = src.crawl()
        assert len(articles) == 2
        assert all("in-the-news" not in a.tags for a in articles)

def test_crawl_multi_day():
    src = WikipediaCurrentEventsSource(days=3, include_itn=False)
    call_count = 0
    def mock_fetch(url, **kw):
        nonlocal call_count
        call_count += 1
        return SAMPLE_PORTAL_HTML
    with patch.object(src, "fetch_url", side_effect=mock_fetch):
        articles = src.crawl()
        assert call_count == 3  # one per day
