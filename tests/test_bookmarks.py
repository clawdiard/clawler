"""Tests for bookmarks module."""
import json
import tempfile
from pathlib import Path
from clawler.bookmarks import add_bookmarks, list_bookmarks, remove_bookmark, clear_bookmarks, load_bookmarks
from clawler.models import Article


def _make_article(title="Test", url="https://example.com", source="Test Source"):
    return Article(title=title, url=url, source=source)


def test_add_and_list_bookmarks():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    path.unlink(missing_ok=True)
    try:
        articles = [_make_article(url="https://a.com"), _make_article(url="https://b.com")]
        added = add_bookmarks(articles, path=path)
        assert added == 2
        bookmarks = list_bookmarks(path=path)
        assert len(bookmarks) == 2
    finally:
        path.unlink(missing_ok=True)


def test_add_deduplicates_by_url():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    path.unlink(missing_ok=True)
    try:
        articles = [_make_article(url="https://a.com")]
        add_bookmarks(articles, path=path)
        added = add_bookmarks(articles, path=path)
        assert added == 0
        assert len(load_bookmarks(path)) == 2 or len(load_bookmarks(path)) == 1
        # Should be 1 since same URL
        assert len(load_bookmarks(path)) == 1
    finally:
        path.unlink(missing_ok=True)


def test_remove_bookmark():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    path.unlink(missing_ok=True)
    try:
        add_bookmarks([_make_article(url="https://a.com")], path=path)
        assert remove_bookmark("https://a.com", path=path) is True
        assert len(load_bookmarks(path)) == 0
        assert remove_bookmark("https://nonexistent.com", path=path) is False
    finally:
        path.unlink(missing_ok=True)


def test_clear_bookmarks():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    path.unlink(missing_ok=True)
    try:
        add_bookmarks([_make_article(url="https://a.com"), _make_article(url="https://b.com")], path=path)
        n = clear_bookmarks(path=path)
        assert n == 2
        assert len(load_bookmarks(path)) == 0
    finally:
        path.unlink(missing_ok=True)
