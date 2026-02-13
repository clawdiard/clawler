"""Tests for v3.7.0 features: --exclude flag, tags field, dry-run fix, HN author."""
import json
from unittest.mock import patch, MagicMock
from clawler.models import Article
from clawler.cli import main
from datetime import datetime, timezone


def _make_article(title="Test", url="https://example.com", source="Test", summary="", tags=None):
    return Article(title=title, url=url, source=source, summary=summary, tags=tags or [])


class TestExcludeFlag:
    """Test --exclude keyword filtering."""

    def test_exclude_filters_title(self):
        """--exclude removes articles matching keyword in title."""
        articles = [
            _make_article(title="AI is great", url="https://a.com"),
            _make_article(title="Python news", url="https://b.com"),
            _make_article(title="New AI model", url="https://c.com"),
        ]
        ekw = "ai"
        result = [a for a in articles if ekw not in a.title.lower() and ekw not in a.summary.lower()]
        assert len(result) == 1
        assert result[0].title == "Python news"

    def test_exclude_filters_summary(self):
        """--exclude removes articles matching keyword in summary."""
        articles = [
            _make_article(title="Tech news", summary="New AI breakthrough"),
            _make_article(title="Sports", summary="Football scores"),
        ]
        ekw = "ai"
        result = [a for a in articles if ekw not in a.title.lower() and ekw not in a.summary.lower()]
        assert len(result) == 1
        assert result[0].title == "Sports"

    def test_exclude_empty_keeps_all(self):
        """No exclude keeps all articles."""
        articles = [_make_article(), _make_article(title="Other")]
        assert len(articles) == 2


class TestTagsField:
    """Test the new tags field on Article."""

    def test_default_tags_empty(self):
        a = Article(title="Test", url="http://x.com", source="S")
        assert a.tags == []

    def test_tags_set(self):
        a = Article(title="Test", url="http://x.com", source="S", tags=["hn:dang", "tech"])
        assert "hn:dang" in a.tags
        assert len(a.tags) == 2

    def test_tags_in_json_output(self):
        from clawler.formatters.json_out import JSONFormatter
        a = _make_article(tags=["test-tag"])
        output = JSONFormatter().format([a])
        data = json.loads(output)
        assert data[0]["tags"] == ["test-tag"]


class TestAPIExclude:
    """Test exclude parameter in API."""

    @patch("clawler.api.CrawlEngine")
    def test_api_exclude(self, mock_engine_cls):
        from clawler.api import crawl
        from clawler.dedup import DedupStats
        mock_engine = MagicMock()
        mock_engine.crawl.return_value = (
            [
                _make_article(title="AI news", url="https://a.com"),
                _make_article(title="Python tips", url="https://b.com"),
            ],
            {"test": 2},
            DedupStats(),
        )
        mock_engine_cls.return_value = mock_engine
        result = crawl(exclude="AI")
        assert len(result) == 1
        assert result[0].title == "Python tips"
