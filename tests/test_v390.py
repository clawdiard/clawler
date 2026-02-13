"""Tests for JSONL formatter and --export-feeds."""
import json
from datetime import datetime, timezone
from clawler.models import Article
from clawler.formatters.jsonl_out import JSONLFormatter


class TestJSONLFormatter:
    def _make_article(self, title="Test", url="https://example.com", source="Test Source"):
        return Article(
            title=title, url=url, source=source, summary="A summary",
            timestamp=datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc),
            category="tech", quality_score=0.8,
        )

    def test_empty(self):
        assert JSONLFormatter().format([]) == ""

    def test_single_article(self):
        out = JSONLFormatter().format([self._make_article()])
        lines = out.strip().split("\n")
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["title"] == "Test"
        assert obj["url"] == "https://example.com"
        assert obj["source"] == "Test Source"
        assert obj["category"] == "tech"
        assert obj["quality_score"] == 0.8
        assert obj["timestamp"] == "2026-02-13T12:00:00+00:00"

    def test_multiple_articles(self):
        articles = [self._make_article(title=f"Art {i}") for i in range(5)]
        out = JSONLFormatter().format(articles)
        lines = out.strip().split("\n")
        assert len(lines) == 5
        for i, line in enumerate(lines):
            obj = json.loads(line)
            assert obj["title"] == f"Art {i}"

    def test_tags_included_when_present(self):
        a = self._make_article()
        a.tags = ["hn:user1"]
        out = JSONLFormatter().format([a])
        obj = json.loads(out)
        assert obj["tags"] == ["hn:user1"]

    def test_relevance_included_when_set(self):
        a = self._make_article()
        a.relevance = 0.95
        out = JSONLFormatter().format([a])
        obj = json.loads(out)
        assert obj["relevance"] == 0.95

    def test_no_tags_key_when_empty(self):
        out = JSONLFormatter().format([self._make_article()])
        obj = json.loads(out)
        assert "tags" not in obj

    def test_valid_json_per_line(self):
        articles = [self._make_article(title=f"A {i}") for i in range(10)]
        out = JSONLFormatter().format(articles)
        for line in out.strip().split("\n"):
            json.loads(line)  # should not raise


class TestExportFeedsCLI:
    def test_export_feeds_flag_exists(self):
        """Verify the --export-feeds argument is accepted by the parser."""
        from clawler.cli import main
        import tempfile, os
        path = tempfile.mktemp(suffix=".yaml")
        try:
            main(["--export-feeds", path])
            assert os.path.exists(path)
            with open(path) as f:
                content = f.read()
            assert "url:" in content or "url :" in content
        finally:
            if os.path.exists(path):
                os.unlink(path)
