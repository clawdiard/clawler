"""Tests for v6.5.0: cache field roundtrip fix, --cache-info."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from clawler.cache import (
    _article_to_dict,
    _dict_to_article,
    cache_info,
    clear_cache,
    load_cache,
    save_cache,
)
from clawler.models import Article


# ---------- cache roundtrip: author & discussion_url ----------

def _make_article(**overrides):
    defaults = dict(
        title="Test Article",
        url="https://example.com/test",
        source="TestSource",
        summary="A summary",
        timestamp=datetime(2026, 2, 15, tzinfo=timezone.utc),
        author="Alice",
        discussion_url="https://news.ycombinator.com/item?id=123",
        tags=["python", "ai"],
        quality_score=0.8,
    )
    defaults.update(overrides)
    return Article(**defaults)


def test_article_to_dict_includes_author_and_discussion_url():
    a = _make_article()
    d = _article_to_dict(a)
    assert d["author"] == "Alice"
    assert d["discussion_url"] == "https://news.ycombinator.com/item?id=123"


def test_dict_to_article_restores_author_and_discussion_url():
    d = _article_to_dict(_make_article())
    restored = _dict_to_article(d)
    assert restored.author == "Alice"
    assert restored.discussion_url == "https://news.ycombinator.com/item?id=123"


def test_dict_to_article_defaults_missing_fields():
    """Old cached dicts without author/discussion_url should still load."""
    d = {
        "title": "Old Article",
        "url": "https://example.com/old",
        "source": "OldSource",
    }
    a = _dict_to_article(d)
    assert a.author == ""
    assert a.discussion_url == ""


def test_cache_roundtrip_preserves_all_fields(tmp_path):
    articles = [_make_article(), _make_article(title="Second", author="Bob", discussion_url="")]
    save_cache("testkey", articles, {"TestSource": 2}, cache_dir=tmp_path)
    result = load_cache("testkey", ttl=600, cache_dir=tmp_path)
    assert result is not None
    loaded, stats = result
    assert len(loaded) == 2
    assert loaded[0].author == "Alice"
    assert loaded[0].discussion_url == "https://news.ycombinator.com/item?id=123"
    assert loaded[1].author == "Bob"
    assert loaded[1].discussion_url == ""


# ---------- cache_info ----------

def test_cache_info_empty(tmp_path):
    info = cache_info(cache_dir=tmp_path)
    assert info["file_count"] == 0
    assert info["total_size_human"] == "0 B"


def test_cache_info_nonexistent(tmp_path):
    info = cache_info(cache_dir=tmp_path / "nope")
    assert info["file_count"] == 0


def test_cache_info_with_files(tmp_path):
    save_cache("k1", [_make_article()], {"TestSource": 1}, cache_dir=tmp_path)
    save_cache("k2", [_make_article()], {"TestSource": 1}, cache_dir=tmp_path)
    info = cache_info(cache_dir=tmp_path)
    assert info["file_count"] == 2
    assert info["total_size_bytes"] > 0
    assert "B" in info["total_size_human"] or "KB" in info["total_size_human"]
    assert info["newest_age_human"]  # non-empty string


# ---------- version ----------

def test_version_is_650():
    from clawler import __version__
    assert __version__ == "6.5.0"
