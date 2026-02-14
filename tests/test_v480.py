"""Tests for v4.8.0: discussion_url field, --source-list, --show-discussions, CSV/JSON/JSONL discussion_url."""
import csv
import io
import json
from datetime import datetime, timezone

from clawler.models import Article
from clawler.formatters.json_out import JSONFormatter
from clawler.formatters.csv_out import CSVFormatter
from clawler.formatters.jsonl_out import JSONLFormatter


def _make_article(**kwargs):
    defaults = dict(
        title="Test Article",
        url="https://example.com/article",
        source="TestSource",
        summary="A test summary",
        timestamp=datetime(2026, 2, 14, tzinfo=timezone.utc),
        category="tech",
    )
    defaults.update(kwargs)
    return Article(**defaults)


# --- Article model ---

def test_article_discussion_url_default():
    a = _make_article()
    assert a.discussion_url == ""


def test_article_discussion_url_set():
    a = _make_article(discussion_url="https://news.ycombinator.com/item?id=123")
    assert a.discussion_url == "https://news.ycombinator.com/item?id=123"


# --- JSON formatter ---

def test_json_includes_discussion_url():
    a = _make_article(discussion_url="https://lobste.rs/s/abc")
    out = JSONFormatter().format([a])
    data = json.loads(out)
    assert data[0]["discussion_url"] == "https://lobste.rs/s/abc"


def test_json_discussion_url_null_when_empty():
    a = _make_article()
    out = JSONFormatter().format([a])
    data = json.loads(out)
    assert data[0]["discussion_url"] is None


# --- CSV formatter ---

def test_csv_header_includes_discussion_url():
    a = _make_article(discussion_url="https://reddit.com/r/test/123")
    out = CSVFormatter().format([a])
    reader = csv.reader(io.StringIO(out))
    header = next(reader)
    assert "discussion_url" in header
    row = next(reader)
    idx = header.index("discussion_url")
    assert row[idx] == "https://reddit.com/r/test/123"


def test_csv_discussion_url_empty():
    a = _make_article()
    out = CSVFormatter().format([a])
    reader = csv.reader(io.StringIO(out))
    header = next(reader)
    row = next(reader)
    idx = header.index("discussion_url")
    assert row[idx] == ""


# --- JSONL formatter ---

def test_jsonl_includes_discussion_url():
    a = _make_article(discussion_url="https://news.ycombinator.com/item?id=456")
    out = JSONLFormatter().format([a])
    data = json.loads(out.strip())
    assert data["discussion_url"] == "https://news.ycombinator.com/item?id=456"


def test_jsonl_omits_empty_discussion_url():
    a = _make_article()
    out = JSONLFormatter().format([a])
    data = json.loads(out.strip())
    assert "discussion_url" not in data


# --- CLI --source-list ---

def test_source_list_flag():
    from clawler.cli import main
    import sys
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = buf = StringIO()
    try:
        main(["--source-list"])
    except SystemExit:
        pass
    finally:
        sys.stdout = old_stdout
    output = buf.getvalue()
    assert "Configured Sources" in output
    assert "Hacker News" in output
    assert "rss" in output.lower()


# --- Version ---

def test_version_480():
    from clawler import __version__
    assert __version__ == "5.0.0"
