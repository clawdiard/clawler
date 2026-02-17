"""Tests for Slashdot source v10.9.0 enhancements."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.slashdot import (
    SlashdotSource,
    _map_category,
    _quality_score,
    _strip_html,
    _extract_comment_count,
    _format_count,
    SLASHDOT_FEEDS,
)


# --- Helper ---

def _make_entry(title="Test Story", url="https://slashdot.org/story/1",
                summary="<p>Summary</p>", author="editor", department="the-dept",
                comments=42, tags=None):
    """Build a fake feedparser entry."""
    e = MagicMock()
    e.get = lambda k, d="": {
        "title": title, "link": url, "summary": summary,
        "author": author, "slash_department": department,
        "slash_comments": str(comments), "slash_hit_parade": "",
        "comments": url, "published_parsed": None, "updated_parsed": None,
    }.get(k, d)
    tag_objs = [MagicMock(get=lambda k, d="", t=t: t if k == "term" else d) for t in (tags or [])]
    e.get_tags = lambda: tag_objs
    # feedparser uses .tags attribute
    type(e).tags = property(lambda self: tag_objs)
    # Also make e.get("tags", []) return the list
    orig_get = e.get
    def patched_get(k, d=""):
        if k == "tags":
            return tag_objs
        return orig_get(k, d)
    e.get = patched_get
    return e


def _make_feed(*entries):
    feed = MagicMock()
    feed.entries = list(entries)
    return feed


# --- _strip_html ---

def test_strip_html():
    assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"
    assert _strip_html("  no  tags  here  ") == "no tags here"


# --- _extract_comment_count ---

def test_comment_count_from_slash_comments():
    e = MagicMock()
    e.get = lambda k, d="": {"slash_comments": "150", "slash_hit_parade": ""}.get(k, d)
    assert _extract_comment_count(e) == 150


def test_comment_count_from_hit_parade():
    e = MagicMock()
    e.get = lambda k, d="": {"slash_comments": "", "slash_hit_parade": "88,5,3,2,1"}.get(k, d)
    assert _extract_comment_count(e) == 88


def test_comment_count_zero():
    e = MagicMock()
    e.get = lambda k, d="": {"slash_comments": "", "slash_hit_parade": ""}.get(k, d)
    assert _extract_comment_count(e) == 0


# --- _quality_score ---

def test_quality_zero_comments():
    assert _quality_score(0) == pytest.approx(0.3)


def test_quality_increases():
    assert _quality_score(10) > _quality_score(1)
    assert _quality_score(100) > _quality_score(10)
    assert _quality_score(500) > _quality_score(100)


def test_quality_cap():
    assert _quality_score(100000) <= 1.0


# --- _format_count ---

def test_format_count():
    assert _format_count(42) == "42"
    assert _format_count(1500) == "1.5K"
    assert _format_count(2300000) == "2.3M"


# --- _map_category ---

def test_category_ai():
    assert _map_category([], "OpenAI launches new LLM") == "ai"


def test_category_security():
    assert _map_category(["slashdot:tag:security"], "Data breach") == "security"


def test_category_science():
    assert _map_category([], "NASA discovers new exoplanet") == "science"


def test_category_business():
    assert _map_category([], "Big acquisition announced") == "business"


def test_category_world():
    assert _map_category([], "Congress passes new legislation") == "world"


def test_category_culture():
    assert _map_category([], "Netflix releases new movie") == "culture"


def test_category_gaming():
    assert _map_category([], "Steam summer sale begins") == "gaming"


def test_category_health():
    assert _map_category([], "FDA approves new vaccine") == "health"


def test_category_crypto():
    assert _map_category([], "Bitcoin hits new high") == "crypto"


def test_category_section_fallback():
    assert _map_category([], "Some generic title", "science") == "science"
    assert _map_category([], "Some generic title", "politics") == "world"


def test_category_tech_fallback():
    assert _map_category([], "Linux kernel update released") == "tech"


# --- SlashdotSource crawl ---

@patch("clawler.sources.slashdot.SlashdotSource.fetch_url")
def test_basic_crawl(mock_fetch):
    import feedparser
    e = _make_entry(comments=50)
    with patch("feedparser.parse", return_value=_make_feed(e)):
        mock_fetch.return_value = "<xml/>"
        src = SlashdotSource()
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].source == "Slashdot"
        assert articles[0].quality_score > 0


@patch("clawler.sources.slashdot.SlashdotSource.fetch_url")
def test_dedup_across_sections(mock_fetch):
    import feedparser
    e = _make_entry(url="https://slashdot.org/story/same")
    with patch("feedparser.parse", return_value=_make_feed(e)):
        mock_fetch.return_value = "<xml/>"
        src = SlashdotSource(sections=["main", "science"])
        articles = src.crawl()
        assert len(articles) == 1


@patch("clawler.sources.slashdot.SlashdotSource.fetch_url")
def test_min_comments_filter(mock_fetch):
    import feedparser
    e = _make_entry(comments=2)
    with patch("feedparser.parse", return_value=_make_feed(e)):
        mock_fetch.return_value = "<xml/>"
        src = SlashdotSource(min_comments=10)
        articles = src.crawl()
        assert len(articles) == 0


@patch("clawler.sources.slashdot.SlashdotSource.fetch_url")
def test_min_quality_filter(mock_fetch):
    import feedparser
    e = _make_entry(comments=0)
    with patch("feedparser.parse", return_value=_make_feed(e)):
        mock_fetch.return_value = "<xml/>"
        src = SlashdotSource(min_quality=0.5)
        articles = src.crawl()
        assert len(articles) == 0


@patch("clawler.sources.slashdot.SlashdotSource.fetch_url")
def test_category_filter(mock_fetch):
    import feedparser
    e = _make_entry(title="NASA space mission")
    with patch("feedparser.parse", return_value=_make_feed(e)):
        mock_fetch.return_value = "<xml/>"
        src = SlashdotSource(category_filter=["tech"])
        articles = src.crawl()
        assert len(articles) == 0  # story is science, filtered out


@patch("clawler.sources.slashdot.SlashdotSource.fetch_url")
def test_global_limit(mock_fetch):
    import feedparser
    entries = [_make_entry(url=f"https://slashdot.org/{i}", comments=i*10) for i in range(10)]
    with patch("feedparser.parse", return_value=_make_feed(*entries)):
        mock_fetch.return_value = "<xml/>"
        src = SlashdotSource(global_limit=3)
        articles = src.crawl()
        assert len(articles) == 3
        # Highest quality first
        assert articles[0].quality_score >= articles[1].quality_score


@patch("clawler.sources.slashdot.SlashdotSource.fetch_url")
def test_department_in_summary(mock_fetch):
    import feedparser
    e = _make_entry(department="the-future-is-now", comments=10)
    with patch("feedparser.parse", return_value=_make_feed(e)):
        mock_fetch.return_value = "<xml/>"
        src = SlashdotSource()
        articles = src.crawl()
        assert "the-future-is-now" in articles[0].summary


@patch("clawler.sources.slashdot.SlashdotSource.fetch_url")
def test_tags_include_section(mock_fetch):
    import feedparser
    e = _make_entry()
    with patch("feedparser.parse", return_value=_make_feed(e)):
        mock_fetch.return_value = "<xml/>"
        src = SlashdotSource()
        articles = src.crawl()
        assert "slashdot:section:main" in articles[0].tags


@patch("clawler.sources.slashdot.SlashdotSource.fetch_url")
def test_quality_sorted_output(mock_fetch):
    import feedparser
    e_low = _make_entry(url="https://slashdot.org/low", comments=1)
    e_high = _make_entry(url="https://slashdot.org/high", comments=500)
    with patch("feedparser.parse", return_value=_make_feed(e_low, e_high)):
        mock_fetch.return_value = "<xml/>"
        src = SlashdotSource()
        articles = src.crawl()
        assert articles[0].quality_score > articles[1].quality_score


@patch("clawler.sources.slashdot.SlashdotSource.fetch_url")
def test_all_sections(mock_fetch):
    import feedparser
    with patch("feedparser.parse", return_value=_make_feed()):
        mock_fetch.return_value = "<xml/>"
        src = SlashdotSource(sections=["all"])
        src.crawl()
        assert mock_fetch.call_count == len(SLASHDOT_FEEDS)


@patch("clawler.sources.slashdot.SlashdotSource.fetch_url")
def test_comment_count_in_summary(mock_fetch):
    import feedparser
    e = _make_entry(comments=150)
    with patch("feedparser.parse", return_value=_make_feed(e)):
        mock_fetch.return_value = "<xml/>"
        src = SlashdotSource()
        articles = src.crawl()
        assert "150 comments" in articles[0].summary


def test_feeds_dict_has_main():
    assert "main" in SLASHDOT_FEEDS
    assert len(SLASHDOT_FEEDS) >= 10
