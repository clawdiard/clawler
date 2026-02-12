"""Tests for JSON Feed formatter."""
import json
from datetime import datetime, timezone
from clawler.models import Article
from clawler.formatters import JSONFeedFormatter


def _articles():
    return [
        Article(title="Test Story", url="https://example.com/1", source="TestSrc",
                summary="A test.", timestamp=datetime(2026, 2, 12, 6, 0, tzinfo=timezone.utc),
                category="tech"),
        Article(title="No Time", url="https://example.com/2", source="TestSrc",
                summary="", category="general"),
    ]


class TestJSONFeedFormatter:
    def test_valid_jsonfeed(self):
        output = JSONFeedFormatter().format(_articles())
        data = json.loads(output)
        assert data["version"] == "https://jsonfeed.org/version/1.1"
        assert len(data["items"]) == 2

    def test_item_fields(self):
        data = json.loads(JSONFeedFormatter().format(_articles()))
        item = data["items"][0]
        assert item["title"] == "Test Story"
        assert item["url"] == "https://example.com/1"
        assert "2026-02-12" in item["date_published"]
        assert item["tags"] == ["tech"]

    def test_no_timestamp_omitted(self):
        data = json.loads(JSONFeedFormatter().format(_articles()))
        item = data["items"][1]
        assert "date_published" not in item

    def test_general_category_no_tags(self):
        data = json.loads(JSONFeedFormatter().format(_articles()))
        item = data["items"][1]
        assert item["tags"] == []

    def test_empty(self):
        data = json.loads(JSONFeedFormatter().format([]))
        assert data["items"] == []
