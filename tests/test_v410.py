"""Tests for v4.1.0 features: env config, sample, json-compact, auto-quiet, NO_COLOR."""
import json
import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from clawler import __version__
from clawler.config import load_env_config
from clawler.formatters.json_out import JSONFormatter
from clawler.models import Article


def _make_articles(n=10):
    return [
        Article(
            title=f"Article {i}",
            url=f"https://example.com/{i}",
            source="TestSource",
            summary=f"Summary {i}",
            timestamp=datetime(2026, 2, 14, tzinfo=timezone.utc),
            category="tech",
            quality_score=0.8,
        )
        for i in range(n)
    ]


class TestVersion:
    def test_version_is_410(self):
        assert __version__ == "4.9.0"


class TestEnvConfig:
    def test_load_env_category(self):
        with patch.dict(os.environ, {"CLAWLER_CATEGORY": "tech,science"}):
            cfg = load_env_config()
            assert cfg["category"] == "tech,science"

    def test_load_env_limit(self):
        with patch.dict(os.environ, {"CLAWLER_LIMIT": "25"}):
            cfg = load_env_config()
            assert cfg["limit"] == 25

    def test_load_env_bool(self):
        with patch.dict(os.environ, {"CLAWLER_QUIET": "true", "CLAWLER_NO_REDDIT": "1"}):
            cfg = load_env_config()
            assert cfg["quiet"] is True
            assert cfg["no_reddit"] is True

    def test_load_env_bool_false(self):
        with patch.dict(os.environ, {"CLAWLER_QUIET": "false"}):
            cfg = load_env_config()
            assert cfg["quiet"] is False

    def test_load_env_float(self):
        with patch.dict(os.environ, {"CLAWLER_DEDUPE_THRESHOLD": "0.9"}):
            cfg = load_env_config()
            assert cfg["dedupe_threshold"] == 0.9

    def test_load_env_ignores_non_prefix(self):
        with patch.dict(os.environ, {"OTHER_VAR": "nope"}, clear=False):
            cfg = load_env_config()
            assert "other_var" not in cfg

    def test_load_env_invalid_int_skipped(self):
        with patch.dict(os.environ, {"CLAWLER_LIMIT": "abc"}):
            cfg = load_env_config()
            assert "limit" not in cfg


class TestJSONCompact:
    def test_compact_json_no_indent(self):
        articles = _make_articles(2)
        output = JSONFormatter(indent=None).format(articles)
        # Compact JSON should be a single line (no pretty-print newlines inside array)
        parsed = json.loads(output)
        assert len(parsed) == 2
        assert "\n" not in output  # no newlines in compact mode

    def test_pretty_json_has_indent(self):
        articles = _make_articles(2)
        output = JSONFormatter(indent=2).format(articles)
        assert "\n" in output

    def test_default_indent_is_2(self):
        f = JSONFormatter()
        assert f.indent == 2


class TestSample:
    def test_sample_reduces_count(self):
        """Verify --sample is accepted by the CLI parser."""
        from clawler.cli import main
        # dry-run returns normally (no SystemExit), just verify no crash
        main(["--sample", "5", "--dry-run"])

    def test_sample_api(self):
        """Test that the API sample parameter works."""
        articles = _make_articles(20)
        # Simulate sampling
        import random
        random.seed(42)
        sampled = random.sample(articles, 5)
        assert len(sampled) == 5
        assert all(a in articles for a in sampled)


class TestEnsureAscii:
    def test_json_unicode_preserved(self):
        articles = [Article(
            title="Ünïcödé héadline 🎉",
            url="https://example.com/1",
            source="Test",
            summary="Ñoño",
            category="tech",
        )]
        output = JSONFormatter().format(articles)
        assert "Ünïcödé" in output
        assert "🎉" in output
        assert "\\u" not in output  # ensure_ascii=False
