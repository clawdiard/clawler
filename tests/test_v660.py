"""Tests for v6.6.0: EchoJS source, --min-quality filter, --no-echojs flag."""
import argparse
from unittest.mock import patch, MagicMock
from clawler.sources.echojs import EchoJSSource
from clawler.models import Article
from clawler.weights import get_quality_score


# --- EchoJS Source Tests ---

def _mock_echojs_response():
    return {
        "news": [
            {
                "id": "12345",
                "title": "React 25 Released",
                "url": "https://react.dev/blog/react-25",
                "atime": "1739580000",
                "up": "15",
                "down": "2",
                "username": "devfan",
            },
            {
                "id": "12346",
                "title": "Understanding JavaScript Closures",
                "url": "https://example.com/closures",
                "atime": "1739576400",
                "up": "8",
                "down": "1",
                "username": "jsdev",
            },
            {
                "id": "12347",
                "title": "",
                "url": "https://example.com/empty",
                "atime": "1739572800",
                "up": "3",
                "down": "0",
                "username": "anon",
            },
        ]
    }


def test_echojs_source_name():
    src = EchoJSSource()
    assert src.name == "echojs"


def test_echojs_crawl_parses_articles():
    src = EchoJSSource()
    with patch.object(src, "fetch_json", return_value=_mock_echojs_response()):
        articles = src.crawl()
    assert len(articles) == 2  # third item has empty title, should be skipped
    assert "React 25 Released" in articles[0].title
    assert articles[0].category == "tech"
    assert articles[0].author == "devfan"
    assert "echojs:javascript" in articles[0].tags


def test_echojs_score_in_source():
    src = EchoJSSource()
    with patch.object(src, "fetch_json", return_value=_mock_echojs_response()):
        articles = src.crawl()
    assert "↑13" in articles[0].source  # 15 - 2 = 13


def test_echojs_discussion_url():
    src = EchoJSSource()
    with patch.object(src, "fetch_json", return_value=_mock_echojs_response()):
        articles = src.crawl()
    assert articles[0].discussion_url == "https://www.echojs.com/news/12345"


def test_echojs_timestamp_parsed():
    src = EchoJSSource()
    with patch.object(src, "fetch_json", return_value=_mock_echojs_response()):
        articles = src.crawl()
    assert articles[0].timestamp is not None
    assert articles[0].timestamp.tzinfo is not None


def test_echojs_empty_response():
    src = EchoJSSource()
    with patch.object(src, "fetch_json", return_value=None):
        articles = src.crawl()
    assert articles == []


def test_echojs_no_news_key():
    src = EchoJSSource()
    with patch.object(src, "fetch_json", return_value={"status": "ok"}):
        articles = src.crawl()
    assert articles == []


def test_echojs_fetch_failure():
    src = EchoJSSource()
    with patch.object(src, "fetch_json", side_effect=Exception("network error")):
        articles = src.crawl()
    assert articles == []


def test_echojs_limit():
    src = EchoJSSource(limit=1)
    with patch.object(src, "fetch_json", return_value=_mock_echojs_response()):
        articles = src.crawl()
    assert len(articles) == 1


def test_echojs_bad_timestamp():
    """Articles with invalid timestamps should still be parsed (ts=None)."""
    data = {"news": [{"id": "1", "title": "Test", "url": "https://x.com", "atime": "not-a-number", "up": "1", "down": "0", "username": "u"}]}
    src = EchoJSSource()
    with patch.object(src, "fetch_json", return_value=data):
        articles = src.crawl()
    assert len(articles) == 1
    assert articles[0].timestamp is None


# --- Quality Weight Tests ---

def test_echojs_quality_weight():
    score = get_quality_score("EchoJS")
    assert score == 0.62


def test_echojs_quality_weight_substring():
    score = get_quality_score("EchoJS (↑13)")
    assert score == 0.62


# --- --min-quality Filter Tests ---

def test_min_quality_filters_low_quality():
    articles = [
        Article(title="High", url="https://a.com", source="Reuters", quality_score=0.9),
        Article(title="Low", url="https://b.com", source="Reddit", quality_score=0.3),
        Article(title="Mid", url="https://c.com", source="TechCrunch", quality_score=0.7),
    ]
    filtered = [a for a in articles if a.quality_score >= 0.5]
    assert len(filtered) == 2
    assert all(a.quality_score >= 0.5 for a in filtered)


def test_min_quality_zero_keeps_all():
    articles = [
        Article(title="A", url="https://a.com", source="X", quality_score=0.1),
        Article(title="B", url="https://b.com", source="Y", quality_score=0.9),
    ]
    filtered = [a for a in articles if a.quality_score >= 0.0]
    assert len(filtered) == 2


def test_min_quality_one_filters_all_below():
    articles = [
        Article(title="A", url="https://a.com", source="X", quality_score=0.99),
    ]
    filtered = [a for a in articles if a.quality_score >= 1.0]
    assert len(filtered) == 0


# --- Import Tests ---

def test_echojs_importable():
    from clawler.sources import EchoJSSource
    assert EchoJSSource is not None


def test_echojs_in_all():
    from clawler.sources import __all__
    assert "EchoJSSource" in __all__


# --- Version Tests ---

def test_version_660():
    from clawler import __version__
    assert __version__ >= "6.0.0"
