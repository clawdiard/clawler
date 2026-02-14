"""Tests for output formatters."""
import csv
import io
import json
from datetime import datetime, timezone
from clawler.models import Article
from clawler.formatters import ConsoleFormatter, CSVFormatter, JSONFormatter, MarkdownFormatter


def _articles():
    return [
        Article(
            title="Python 4.0 Released",
            url="https://example.com/python4",
            source="TechCrunch",
            summary="Python 4.0 is here with exciting new features.",
            timestamp=datetime(2026, 2, 12, 6, 0, tzinfo=timezone.utc),
            category="tech",
        ),
        Article(
            title="Mars Rover Finds Water",
            url="https://example.com/mars",
            source="BBC News",
            summary="NASA's rover has confirmed water presence.",
            timestamp=datetime(2026, 2, 11, 12, 0, tzinfo=timezone.utc),
            category="science",
        ),
    ]


class TestJSONFormatter:
    def test_valid_json(self):
        output = JSONFormatter().format(_articles())
        data = json.loads(output)
        assert len(data) == 2
        assert data[0]["title"] == "Python 4.0 Released"

    def test_timestamp_iso(self):
        output = JSONFormatter().format(_articles())
        data = json.loads(output)
        assert "2026-02-12" in data[0]["timestamp"]

    def test_empty_list(self):
        output = JSONFormatter().format([])
        assert json.loads(output) == []


class TestMarkdownFormatter:
    def test_contains_titles(self):
        output = MarkdownFormatter().format(_articles())
        assert "Python 4.0 Released" in output
        assert "Mars Rover Finds Water" in output

    def test_header_count(self):
        output = MarkdownFormatter().format(_articles())
        assert output.startswith("# ")
        assert output.count("### ") == 2

    def test_empty(self):
        output = MarkdownFormatter().format([])
        assert "0 stories" in output


class TestConsoleFormatter:
    def test_returns_string(self):
        output = ConsoleFormatter().format(_articles())
        assert isinstance(output, str)
        assert "Python 4.0 Released" in output

    def test_empty(self):
        output = ConsoleFormatter().format([])
        assert "0 stories" in output


class TestNoneTimestamp:
    """Formatters should handle articles with no timestamp."""

    def test_json_none_timestamp(self):
        a = [Article(title="X", url="https://x.com", source="x")]
        data = json.loads(JSONFormatter().format(a))
        assert data[0]["timestamp"] is None

    def test_markdown_none_timestamp(self):
        a = [Article(title="X", url="https://x.com", source="x")]
        output = MarkdownFormatter().format(a)
        assert "unknown" in output


class TestCSVFormatter:
    def test_valid_csv(self):
        output = CSVFormatter().format(_articles())
        reader = csv.reader(io.StringIO(output))
        rows = list(reader)
        assert rows[0] == ["title", "url", "source", "author", "summary", "timestamp", "category", "discussion_url"]
        assert len(rows) == 3  # header + 2 articles

    def test_empty(self):
        output = CSVFormatter().format([])
        reader = csv.reader(io.StringIO(output))
        rows = list(reader)
        assert len(rows) == 1  # header only

    def test_none_timestamp_empty_string(self):
        a = [Article(title="X", url="https://x.com", source="x")]
        output = CSVFormatter().format(a)
        reader = csv.reader(io.StringIO(output))
        rows = list(reader)
        assert rows[1][4] == ""  # timestamp column is empty
