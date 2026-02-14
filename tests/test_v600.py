"""Tests for Stack Overflow source (v6.0.0)."""
from datetime import timezone
from unittest.mock import patch
import pytest
from clawler.sources.stackoverflow import StackOverflowSource, _decode_entities


SAMPLE_ITEMS = [
    {
        "title": "How to merge two dictionaries in Python?",
        "link": "https://stackoverflow.com/questions/1/how-to-merge",
        "creation_date": 1707868800,
        "tags": ["python", "dictionary"],
        "score": 42,
        "answer_count": 5,
        "view_count": 12000,
        "owner": {"display_name": "testuser"},
    },
    {
        "title": "Understanding async/await in JavaScript",
        "link": "https://stackoverflow.com/questions/2/async-await",
        "creation_date": 1707872400,
        "tags": ["javascript", "async-await", "promise"],
        "score": 18,
        "answer_count": 3,
        "view_count": 5000,
        "owner": {"display_name": "jsdev"},
    },
    {
        "title": "Docker container won&#39;t start",
        "link": "https://stackoverflow.com/questions/3/docker-start",
        "creation_date": 1707876000,
        "tags": ["docker", "containers"],
        "score": 7,
        "answer_count": 1,
        "view_count": 800,
        "owner": {},
    },
]


def _make_response(items):
    return {"items": items, "has_more": False, "quota_remaining": 299}


class TestStackOverflowSource:
    def test_name_and_type(self):
        src = StackOverflowSource()
        assert src.name == "Stack Overflow"
        assert src.source_type == "api"

    @patch.object(StackOverflowSource, "fetch_json")
    def test_crawl_basic(self, mock_fetch):
        mock_fetch.return_value = _make_response(SAMPLE_ITEMS)
        assert len(StackOverflowSource().crawl()) == 3

    @patch.object(StackOverflowSource, "fetch_json")
    def test_article_fields(self, mock_fetch):
        mock_fetch.return_value = _make_response(SAMPLE_ITEMS[:1])
        a = StackOverflowSource().crawl()[0]
        assert a.title == "How to merge two dictionaries in Python?"
        assert a.source == "Stack Overflow"
        assert a.category == "tech"
        assert a.author == "testuser"
        assert "python" in a.tags
        assert "Score: 42" in a.summary

    @patch.object(StackOverflowSource, "fetch_json")
    def test_html_entity_decode(self, mock_fetch):
        mock_fetch.return_value = _make_response(SAMPLE_ITEMS[2:3])
        a = StackOverflowSource().crawl()[0]
        assert "'" in a.title
        assert "&#39;" not in a.title

    @patch.object(StackOverflowSource, "fetch_json")
    def test_timestamp_utc(self, mock_fetch):
        mock_fetch.return_value = _make_response(SAMPLE_ITEMS[:1])
        a = StackOverflowSource().crawl()[0]
        assert a.timestamp is not None
        assert a.timestamp.tzinfo == timezone.utc

    @patch.object(StackOverflowSource, "fetch_json")
    def test_empty_response(self, mock_fetch):
        mock_fetch.return_value = _make_response([])
        assert StackOverflowSource().crawl() == []

    @patch.object(StackOverflowSource, "fetch_json")
    def test_missing_owner(self, mock_fetch):
        mock_fetch.return_value = _make_response(SAMPLE_ITEMS[2:3])
        assert StackOverflowSource().crawl()[0].author == ""

    @patch.object(StackOverflowSource, "fetch_json")
    def test_network_error(self, mock_fetch):
        mock_fetch.return_value = None
        assert StackOverflowSource().crawl() == []

    @patch.object(StackOverflowSource, "fetch_json")
    def test_tags_limited(self, mock_fetch):
        item = {**SAMPLE_ITEMS[0], "tags": ["a", "b", "c", "d", "e", "f", "g"]}
        mock_fetch.return_value = _make_response([item])
        assert len(StackOverflowSource().crawl()[0].tags) <= 5

    @patch.object(StackOverflowSource, "fetch_json")
    def test_no_items_key(self, mock_fetch):
        mock_fetch.return_value = {"error_id": 502}
        assert StackOverflowSource().crawl() == []

    @patch.object(StackOverflowSource, "fetch_json")
    def test_skips_empty_title(self, mock_fetch):
        item = {"title": "", "link": "https://so.com/q/1", "tags": [], "score": 0, "answer_count": 0, "view_count": 0, "owner": {}}
        mock_fetch.return_value = _make_response([item])
        assert StackOverflowSource().crawl() == []

    @patch.object(StackOverflowSource, "fetch_json")
    def test_order_preserved(self, mock_fetch):
        mock_fetch.return_value = _make_response(SAMPLE_ITEMS)
        arts = StackOverflowSource().crawl()
        assert arts[0].title.startswith("How to merge")
        assert arts[1].title.startswith("Understanding")

    def test_import(self):
        from clawler.sources import StackOverflowSource as SO
        assert SO is not None

    @patch.object(StackOverflowSource, "fetch_json")
    def test_summary_format(self, mock_fetch):
        mock_fetch.return_value = _make_response(SAMPLE_ITEMS[:1])
        s = StackOverflowSource().crawl()[0].summary
        assert "Tags: python, dictionary" in s
        assert "Answers: 5" in s
        assert "Views: 12000" in s

    def test_decode_entities(self):
        assert _decode_entities("a&#39;b&amp;c&quot;d&lt;e&gt;f") == "a'b&c\"d<e>f"
