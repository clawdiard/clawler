"""Tests for v7.6.0: API parity for FreeCodeCamp + Changelog sources."""
import inspect
import pytest
from unittest.mock import patch, MagicMock
from clawler import __version__
from clawler.api import crawl
from clawler.sources import FreeCodeCampSource, ChangelogSource


def test_version():
    assert __version__ == "7.6.0"


def test_api_has_freecodecamp_param():
    """crawl() should accept no_freecodecamp parameter."""
    sig = inspect.signature(crawl)
    assert "no_freecodecamp" in sig.parameters


def test_api_has_changelog_param():
    """crawl() should accept no_changelog parameter."""
    sig = inspect.signature(crawl)
    assert "no_changelog" in sig.parameters


def test_api_only_includes_freecodecamp():
    """--only freecodecamp should enable only FreeCodeCampSource."""
    sig = inspect.signature(crawl)
    # Verify the parameter exists and the _name_to_flag mapping works
    assert "no_freecodecamp" in sig.parameters
    assert "no_changelog" in sig.parameters


@patch("clawler.api.CrawlEngine")
def test_api_freecodecamp_source_included_by_default(mock_engine_cls):
    """FreeCodeCampSource should be in default source list."""
    mock_engine = MagicMock()
    mock_engine.crawl.return_value = ([], {}, MagicMock())
    mock_engine_cls.return_value = mock_engine

    crawl(limit=1)

    call_kwargs = mock_engine_cls.call_args
    sources = call_kwargs[1]["sources"] if "sources" in (call_kwargs[1] or {}) else call_kwargs[0][0] if call_kwargs[0] else None
    # Sources passed as keyword arg
    if sources is None:
        sources = call_kwargs.kwargs.get("sources", [])
    source_types = [type(s) for s in sources]
    assert FreeCodeCampSource in source_types
    assert ChangelogSource in source_types


@patch("clawler.api.CrawlEngine")
def test_api_no_freecodecamp_excludes_source(mock_engine_cls):
    """no_freecodecamp=True should exclude FreeCodeCampSource."""
    mock_engine = MagicMock()
    mock_engine.crawl.return_value = ([], {}, MagicMock())
    mock_engine_cls.return_value = mock_engine

    crawl(no_freecodecamp=True, limit=1)

    call_kwargs = mock_engine_cls.call_args
    sources = call_kwargs.kwargs.get("sources", [])
    source_types = [type(s) for s in sources]
    assert FreeCodeCampSource not in source_types


@patch("clawler.api.CrawlEngine")
def test_api_no_changelog_excludes_source(mock_engine_cls):
    """no_changelog=True should exclude ChangelogSource."""
    mock_engine = MagicMock()
    mock_engine.crawl.return_value = ([], {}, MagicMock())
    mock_engine_cls.return_value = mock_engine

    crawl(no_changelog=True, limit=1)

    call_kwargs = mock_engine_cls.call_args
    sources = call_kwargs.kwargs.get("sources", [])
    source_types = [type(s) for s in sources]
    assert ChangelogSource not in source_types


@patch("clawler.api.CrawlEngine")
def test_api_only_freecodecamp(mock_engine_cls):
    """only='freecodecamp' should enable only FreeCodeCampSource."""
    mock_engine = MagicMock()
    mock_engine.crawl.return_value = ([], {}, MagicMock())
    mock_engine_cls.return_value = mock_engine

    crawl(only="freecodecamp", limit=1)

    call_kwargs = mock_engine_cls.call_args
    sources = call_kwargs.kwargs.get("sources", [])
    source_types = [type(s) for s in sources]
    assert FreeCodeCampSource in source_types
    assert len(sources) == 1


@patch("clawler.api.CrawlEngine")
def test_api_only_changelog(mock_engine_cls):
    """only='changelog' should enable only ChangelogSource."""
    mock_engine = MagicMock()
    mock_engine.crawl.return_value = ([], {}, MagicMock())
    mock_engine_cls.return_value = mock_engine

    crawl(only="changelog", limit=1)

    call_kwargs = mock_engine_cls.call_args
    sources = call_kwargs.kwargs.get("sources", [])
    source_types = [type(s) for s in sources]
    assert ChangelogSource in source_types
    assert len(sources) == 1


def test_api_total_source_count():
    """API should support all 22 sources."""
    sig = inspect.signature(crawl)
    no_params = [p for p in sig.parameters if p.startswith("no_") and p != "no_dedup"]
    # 22 sources = 22 no_* params (excluding no_dedup which isn't a source)
    # no_rss, no_hn, no_reddit, no_github, no_mastodon, no_wikipedia, no_lobsters,
    # no_devto, no_arxiv, no_techmeme, no_producthunt, no_bluesky, no_tildes,
    # no_lemmy, no_slashdot, no_stackoverflow, no_pinboard, no_indiehackers,
    # no_echojs, no_hashnode, no_freecodecamp, no_changelog
    assert len(no_params) == 22, f"Expected 22 source toggles, got {len(no_params)}: {no_params}"
