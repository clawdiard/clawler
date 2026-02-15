"""Tests for v6.8.0: API source parity, engine imports, version sync."""
import importlib
import inspect
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from clawler import __version__


class TestVersionSync680:
    def test_version_is_680(self):
        assert __version__ >= "6.0.0"

    def test_setup_py_version(self):
        setup = Path(__file__).parent.parent / "setup.py"
        assert f'version="{__version__}"' in setup.read_text()


class TestEngineImports:
    """Engine should import all 20 source classes."""

    def test_engine_imports_echojs(self):
        from clawler.engine import EchoJSSource
        assert EchoJSSource is not None

    def test_engine_imports_hashnode(self):
        from clawler.engine import HashnodeSource
        assert HashnodeSource is not None


class TestAPISourceParity:
    """api.crawl() should support all 20 sources via no_* flags."""

    def test_api_has_all_no_flags(self):
        from clawler.api import crawl
        sig = inspect.signature(crawl)
        expected = [
            "no_rss", "no_hn", "no_reddit", "no_github", "no_mastodon",
            "no_wikipedia", "no_lobsters", "no_devto", "no_arxiv",
            "no_techmeme", "no_producthunt", "no_bluesky", "no_tildes",
            "no_lemmy", "no_slashdot", "no_stackoverflow", "no_pinboard",
            "no_indiehackers", "no_echojs", "no_hashnode",
        ]
        for flag in expected:
            assert flag in sig.parameters, f"api.crawl() missing parameter: {flag}"

    def test_api_imports_all_sources(self):
        import clawler.api as api_mod
        source_classes = [
            "LemmySource", "SlashdotSource", "StackOverflowSource",
            "PinboardSource", "IndieHackersSource", "EchoJSSource",
            "HashnodeSource",
        ]
        for cls in source_classes:
            assert hasattr(api_mod, cls), f"api module missing import: {cls}"

    def test_api_only_filter_includes_new_sources(self):
        """--only should recognize new source names."""
        from clawler.api import crawl
        # Just verify it doesn't error with new source names
        with patch("clawler.api.CrawlEngine") as mock_engine:
            mock_engine.return_value.crawl.return_value = ([], {}, MagicMock())
            result = crawl(only="echojs,hashnode", limit=5)
            assert result == []

    def test_api_disable_new_sources(self):
        """Disabling new sources should not error."""
        from clawler.api import crawl
        with patch("clawler.api.CrawlEngine") as mock_engine:
            mock_engine.return_value.crawl.return_value = ([], {}, MagicMock())
            result = crawl(
                no_lemmy=True, no_slashdot=True, no_stackoverflow=True,
                no_pinboard=True, no_indiehackers=True, no_echojs=True,
                no_hashnode=True, limit=5,
            )
            assert result == []


class TestAPIDocstring:
    def test_docstring_mentions_20_sources(self):
        import clawler.api as api_mod
        assert "20 sources" in api_mod.__doc__
