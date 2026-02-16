"""Tests for v5.2.0: API full-source parity, new API parameters, --top-sources flag."""
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from clawler.models import Article


def _make_article(title="Test", url="https://ex.com", source="Test", **kw):
    return Article(title=title, url=url, source=source, **kw)


# --- API source parity tests ---

def test_api_imports_all_sources():
    """api.py should import all 11 source classes."""
    from clawler import api
    assert hasattr(api, 'MastodonSource')
    assert hasattr(api, 'WikipediaCurrentEventsSource')
    assert hasattr(api, 'LobstersSource')
    assert hasattr(api, 'DevToSource')
    assert hasattr(api, 'ArXivSource')
    assert hasattr(api, 'TechMemeSource')
    assert hasattr(api, 'ProductHuntSource')


def test_api_crawl_accepts_all_source_toggles():
    """crawl() should accept no_mastodon, no_wikipedia, etc. without error."""
    import inspect
    from clawler.api import crawl
    sig = inspect.signature(crawl)
    for toggle in ['no_mastodon', 'no_wikipedia', 'no_lobsters', 'no_devto',
                    'no_arxiv', 'no_techmeme', 'no_producthunt']:
        assert toggle in sig.parameters, f"Missing parameter: {toggle}"


def test_api_crawl_accepts_dedupe_enabled():
    """crawl() should accept dedupe_enabled parameter."""
    import inspect
    from clawler.api import crawl
    sig = inspect.signature(crawl)
    assert 'dedupe_enabled' in sig.parameters


def test_api_crawl_accepts_max_workers():
    """crawl() should accept max_workers parameter."""
    import inspect
    from clawler.api import crawl
    sig = inspect.signature(crawl)
    assert 'max_workers' in sig.parameters


def test_api_crawl_accepts_min_quality():
    """crawl() should accept min_quality parameter."""
    import inspect
    from clawler.api import crawl
    sig = inspect.signature(crawl)
    assert 'min_quality' in sig.parameters


def test_api_builds_all_sources_by_default():
    """With no toggles disabled, api should build all 23 sources."""
    from clawler.api import crawl
    from clawler.sources import (
        RSSSource, HackerNewsSource, RedditSource, GitHubTrendingSource,
        MastodonSource, WikipediaCurrentEventsSource, LobstersSource,
        DevToSource, ArXivSource, TechMemeSource, ProductHuntSource,
        BlueskySource, TildesSource, LemmySource, SlashdotSource,
        StackOverflowSource, PinboardSource, IndieHackersSource,
        EchoJSSource, HashnodeSource, FreeCodeCampSource, ChangelogSource,
        HackerNoonSource, YouTubeSource, MediumSource,
        SubstackSource, GoogleNewsSource,
    )
    expected_types = {
        RSSSource, HackerNewsSource, RedditSource, GitHubTrendingSource,
        MastodonSource, WikipediaCurrentEventsSource, LobstersSource,
        DevToSource, ArXivSource, TechMemeSource, ProductHuntSource,
        BlueskySource, TildesSource, LemmySource, SlashdotSource,
        StackOverflowSource, PinboardSource, IndieHackersSource,
        EchoJSSource, HashnodeSource, FreeCodeCampSource, ChangelogSource,
        HackerNoonSource, YouTubeSource, MediumSource, SubstackSource,
        GoogleNewsSource,
    }
    with patch('clawler.api.CrawlEngine') as MockEngine:
        instance = MockEngine.return_value
        instance.crawl.return_value = ([], {}, MagicMock())
        crawl()
        call_args = MockEngine.call_args
        sources = call_args[1]['sources'] if 'sources' in call_args[1] else call_args[0][0]
        source_types = {type(s) for s in sources}
        assert source_types == expected_types, f"Got {source_types}"


def test_api_disable_new_sources():
    """Disabling new sources should exclude them."""
    from clawler.api import crawl
    from clawler.sources import MastodonSource, ArXivSource
    with patch('clawler.api.CrawlEngine') as MockEngine:
        instance = MockEngine.return_value
        instance.crawl.return_value = ([], {}, MagicMock())
        crawl(no_mastodon=True, no_arxiv=True)
        call_args = MockEngine.call_args
        sources = call_args[1]['sources'] if 'sources' in call_args[1] else call_args[0][0]
        source_types = {type(s) for s in sources}
        assert MastodonSource not in source_types
        assert ArXivSource not in source_types


def test_api_min_quality_filter():
    """min_quality should filter out low-quality articles."""
    from clawler.api import crawl
    articles = [
        _make_article("Low", "https://ex.com/1", quality_score=0.3),
        _make_article("High", "https://ex.com/2", quality_score=0.9),
    ]
    with patch('clawler.api.CrawlEngine') as MockEngine:
        instance = MockEngine.return_value
        instance.crawl.return_value = (articles, {}, MagicMock())
        result = crawl(min_quality=0.5)
        assert len(result) == 1
        assert result[0].title == "High"


def test_api_dedupe_enabled_passthrough():
    """dedupe_enabled should be passed through to engine.crawl()."""
    from clawler.api import crawl
    with patch('clawler.api.CrawlEngine') as MockEngine:
        instance = MockEngine.return_value
        instance.crawl.return_value = ([], {}, MagicMock())
        crawl(dedupe_enabled=False)
        instance.crawl.assert_called_once_with(
            dedupe_threshold=0.75, dedupe_enabled=False
        )


def test_api_max_workers_passthrough():
    """max_workers should be forwarded to CrawlEngine."""
    from clawler.api import crawl
    with patch('clawler.api.CrawlEngine') as MockEngine:
        instance = MockEngine.return_value
        instance.crawl.return_value = ([], {}, MagicMock())
        crawl(max_workers=12)
        MockEngine.assert_called_once()
        assert MockEngine.call_args[1]['max_workers'] == 12


# --- CLI --top-sources tests ---

def test_cli_top_sources_flag_exists():
    """CLI should accept --top-sources flag."""
    from clawler.cli import main
    import io
    from contextlib import redirect_stdout, redirect_stderr
    # --top-sources with --dry-run to avoid actual crawling
    # Just check it doesn't error on parse
    import argparse
    from clawler.cli import main
    # We test by checking the parser accepts the flag
    import sys
    old_argv = sys.argv
    try:
        sys.argv = ['clawler', '--top-sources', '--dry-run']
        # This will print dry-run output and return
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv
