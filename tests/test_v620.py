"""Tests for Pinboard Popular source (v6.2.0)."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.pinboard import PinboardSource, PINBOARD_POPULAR_URL

SAMPLE_HTML = """
<html><body>
<div id="bookmarks">
  <div class="bookmark">
    <a class="bookmark_title" href="https://example.com/article1">Understanding LLM Agents</a>
    <a class="tag" href="/t:ai">ai</a>
    <a class="tag" href="/t:llm">llm</a>
    <a class="tag" href="/t:programming">programming</a>
    <span class="bookmark_count">142 saves</span>
  </div>
  <div class="bookmark">
    <a class="bookmark_title" href="https://example.com/article2">Climate Report 2026</a>
    <a class="tag" href="/t:science">science</a>
    <a class="tag" href="/t:climate">climate</a>
    <span class="bookmark_count">87 saves</span>
  </div>
  <div class="bookmark">
    <a class="bookmark_title" href="https://example.com/article3">Encryption Deep Dive</a>
    <a class="tag" href="/t:security">security</a>
    <a class="tag" href="/t:encryption">encryption</a>
  </div>
  <div class="bookmark">
    <a class="bookmark_title" href="">Empty URL Article</a>
  </div>
  <div class="bookmark">
    <span>No link tag here</span>
  </div>
</div>
</body></html>
"""


def _mock_response(html=SAMPLE_HTML, status=200):
    resp = MagicMock()
    resp.text = html
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    return resp


class TestPinboardSource:
    def test_name_and_type(self):
        src = PinboardSource()
        assert src.name == "Pinboard Popular"
        assert src.source_type == "pinboard"

    def test_crawl_parses_bookmarks(self):
        src = PinboardSource()
        src.session = MagicMock()
        src.session.get.return_value = _mock_response()
        articles = src.crawl()
        # Should find 3 valid articles (empty URL and no-link are skipped)
        assert len(articles) == 3
        assert articles[0].title == "Understanding LLM Agents"
        assert articles[0].url == "https://example.com/article1"
        assert articles[0].source == "Pinboard Popular"

    def test_categorize_tech_default(self):
        src = PinboardSource()
        src.session = MagicMock()
        src.session.get.return_value = _mock_response()
        articles = src.crawl()
        assert articles[0].category == "tech"  # ai/llm/programming → tech

    def test_categorize_science(self):
        src = PinboardSource()
        src.session = MagicMock()
        src.session.get.return_value = _mock_response()
        articles = src.crawl()
        assert articles[1].category == "science"  # science/climate → science

    def test_categorize_security(self):
        src = PinboardSource()
        src.session = MagicMock()
        src.session.get.return_value = _mock_response()
        articles = src.crawl()
        assert articles[2].category == "security"  # security/encryption → security

    def test_description_includes_tags_and_count(self):
        src = PinboardSource()
        src.session = MagicMock()
        src.session.get.return_value = _mock_response()
        articles = src.crawl()
        assert "ai" in articles[0].summary
        assert "142 saves" in articles[0].summary

    def test_crawl_failure_raises(self):
        src = PinboardSource()
        src.session = MagicMock()
        src.session.get.return_value = _mock_response(status=503)
        with pytest.raises(Exception):
            src.crawl()

    def test_empty_page_returns_empty(self):
        src = PinboardSource()
        src.session = MagicMock()
        src.session.get.return_value = _mock_response(html="<html><body></body></html>")
        articles = src.crawl()
        assert articles == []

    def test_categorize_business(self):
        assert PinboardSource._categorize(["finance", "investing"]) == "business"

    def test_categorize_culture(self):
        assert PinboardSource._categorize(["art", "music"]) == "culture"

    def test_categorize_world(self):
        assert PinboardSource._categorize(["politics", "war"]) == "world"

    def test_categorize_empty_tags(self):
        assert PinboardSource._categorize([]) == "tech"

    def test_max_30_articles(self):
        """Ensure we cap at 30 bookmarks."""
        bookmarks = ""
        for i in range(50):
            bookmarks += f'<div class="bookmark"><a class="bookmark_title" href="https://example.com/{i}">Article {i}</a></div>'
        html = f'<html><body><div id="bookmarks">{bookmarks}</div></body></html>'
        src = PinboardSource()
        src.session = MagicMock()
        src.session.get.return_value = _mock_response(html=html)
        articles = src.crawl()
        assert len(articles) == 30

    def test_import_from_sources(self):
        from clawler.sources import PinboardSource as PS
        assert PS is PinboardSource

    def test_url_constant(self):
        assert PINBOARD_POPULAR_URL == "https://pinboard.in/popular/"
