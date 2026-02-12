"""Tests for feeds config loader."""
import json
import os
import tempfile
import pytest
from clawler.feeds_config import load_feeds_file


class TestLoadFeedsFile:
    def test_load_json(self):
        data = {"feeds": [
            {"url": "https://example.com/feed.xml", "source": "Example", "category": "tech"},
        ]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            feeds = load_feeds_file(f.name)
        os.unlink(f.name)
        assert len(feeds) == 1
        assert feeds[0]["source"] == "Example"

    def test_defaults_filled(self):
        data = {"feeds": [{"url": "https://example.com/feed.xml"}]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            feeds = load_feeds_file(f.name)
        os.unlink(f.name)
        assert feeds[0]["source"] == "https://example.com/feed.xml"
        assert feeds[0]["category"] == "general"

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_feeds_file("/nonexistent/feeds.json")

    def test_invalid_format_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello")
            f.flush()
        with pytest.raises(ValueError):
            load_feeds_file(f.name)
        os.unlink(f.name)

    def test_missing_feeds_key_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"sources": []}, f)
            f.flush()
        with pytest.raises(ValueError, match="feeds"):
            load_feeds_file(f.name)
        os.unlink(f.name)

    def test_missing_url_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"feeds": [{"source": "No URL"}]}, f)
            f.flush()
        with pytest.raises(ValueError, match="url"):
            load_feeds_file(f.name)
        os.unlink(f.name)
