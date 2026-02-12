"""Tests for the HTML formatter."""
from datetime import datetime, timezone
from clawler.models import Article
from clawler.formatters import HTMLFormatter


def _articles():
    return [
        Article(title="Python 4.0 Released", url="https://example.com/python4",
                source="TechCrunch", summary="Big release.", category="tech",
                timestamp=datetime(2026, 2, 12, 6, 0, tzinfo=timezone.utc)),
        Article(title='XSS <script>alert("x")</script>', url="https://example.com/xss",
                source="Test", summary='<b>bold</b>', category="tech"),
    ]


class TestHTMLFormatter:
    def test_contains_doctype(self):
        output = HTMLFormatter().format(_articles())
        assert "<!DOCTYPE html>" in output

    def test_contains_title(self):
        output = HTMLFormatter().format(_articles())
        assert "Python 4.0 Released" in output

    def test_escapes_html(self):
        output = HTMLFormatter().format(_articles())
        assert "<script>" not in output
        assert "&lt;script&gt;" in output

    def test_empty(self):
        output = HTMLFormatter().format([])
        assert "0 stories" in output
