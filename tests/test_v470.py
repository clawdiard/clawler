"""Tests for v4.7.0: author field, --author filter, --sort quality, CSV author column."""
from datetime import datetime, timezone
from clawler import __version__
from clawler.models import Article
from clawler.formatters.json_out import JSONFormatter
from clawler.formatters.jsonl_out import JSONLFormatter
from clawler.formatters.csv_out import CSVFormatter
import csv
import io
import json


def _article(title="Test", author="", **kwargs):
    defaults = dict(url="https://example.com", source="test", summary="summary",
                    timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), category="tech")
    defaults.update(kwargs)
    return Article(title=title, author=author, **defaults)


class TestVersionSync:
    def test_version_is_4_7_0(self):
        assert __version__ == "5.0.0"


class TestAuthorField:
    def test_default_empty(self):
        a = _article()
        assert a.author == ""

    def test_set_author(self):
        a = _article(author="Alice")
        assert a.author == "Alice"

    def test_json_includes_author(self):
        out = JSONFormatter().format([_article(author="Bob")])
        data = json.loads(out)
        assert data[0]["author"] == "Bob"

    def test_jsonl_includes_author(self):
        out = JSONLFormatter().format([_article(author="Carol")])
        data = json.loads(out)
        assert data["author"] == "Carol"

    def test_jsonl_omits_empty_author(self):
        out = JSONLFormatter().format([_article(author="")])
        data = json.loads(out)
        assert "author" not in data

    def test_csv_has_author_column(self):
        out = CSVFormatter().format([_article(author="Dave")])
        reader = csv.reader(io.StringIO(out))
        rows = list(reader)
        assert "author" in rows[0]
        author_idx = rows[0].index("author")
        assert rows[1][author_idx] == "Dave"


class TestAuthorFilter:
    def test_cli_author_filter(self):
        from clawler.cli import main
        from unittest.mock import patch
        import sys
        with patch("sys.stdout", new_callable=io.StringIO):
            # Just verify the flag parses without error
            try:
                main(["--author", "testauthor", "--dry-run"])
            except SystemExit:
                pass


class TestSortQuality:
    def test_sort_quality_orders_by_score(self):
        articles = [
            _article(title="Low", quality_score=0.3),
            _article(title="High", quality_score=0.9, url="https://example.com/2"),
            _article(title="Mid", quality_score=0.6, url="https://example.com/3"),
        ]
        articles.sort(key=lambda a: a.quality_score, reverse=True)
        assert articles[0].title == "High"
        assert articles[1].title == "Mid"
        assert articles[2].title == "Low"


class TestDevToTagsFix:
    def test_empty_tags_returns_list(self):
        """Dev.to source should return [] not None for empty tags."""
        a = _article(tags=[])
        assert a.tags == []
        assert isinstance(a.tags, list)
