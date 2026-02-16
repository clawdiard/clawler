"""Tests for v9.7.0 — API source parity fix."""
from clawler.api import crawl
import inspect


def test_api_has_all_source_disable_flags():
    """Verify the crawl() function exposes no_ flags for all 40 sources."""
    sig = inspect.signature(crawl)
    no_flags = [p for p in sig.parameters if p.startswith("no_")]
    # All 40 sources should have a disable flag
    expected = {
        "no_rss", "no_hn", "no_reddit", "no_github", "no_mastodon",
        "no_wikipedia", "no_lobsters", "no_devto", "no_arxiv", "no_techmeme",
        "no_producthunt", "no_bluesky", "no_tildes", "no_lemmy", "no_slashdot",
        "no_stackoverflow", "no_pinboard", "no_indiehackers", "no_echojs",
        "no_hashnode", "no_freecodecamp", "no_changelog", "no_hackernoon",
        "no_youtube", "no_medium", "no_substack", "no_googlenews",
        "no_dzone", "no_sciencedaily", "no_npr", "no_arstechnica",
        "no_alltop", "no_wired", "no_theverge", "no_reuters",
        "no_physorg", "no_nature", "no_apnews", "no_guardian",
        "no_infoq", "no_theregister",
    }
    actual = set(no_flags)
    missing = expected - actual
    assert not missing, f"Missing no_ flags in crawl(): {missing}"


def test_api_source_map_count():
    """The _source_map in crawl() should have 40 entries."""
    # We can verify by checking that crawl with all disabled returns empty
    result = crawl(
        no_rss=True, no_hn=True, no_reddit=True, no_github=True,
        no_mastodon=True, no_wikipedia=True, no_lobsters=True,
        no_devto=True, no_arxiv=True, no_techmeme=True,
        no_producthunt=True, no_bluesky=True, no_tildes=True,
        no_lemmy=True, no_slashdot=True, no_stackoverflow=True,
        no_pinboard=True, no_indiehackers=True, no_echojs=True,
        no_hashnode=True, no_freecodecamp=True, no_changelog=True,
        no_hackernoon=True, no_youtube=True, no_medium=True,
        no_substack=True, no_googlenews=True, no_dzone=True,
        no_sciencedaily=True, no_npr=True, no_arstechnica=True,
        no_alltop=True, no_wired=True, no_theverge=True,
        no_reuters=True, no_physorg=True, no_nature=True,
        no_apnews=True, no_guardian=True, no_infoq=True,
        no_theregister=True,
    )
    assert result == []


def test_api_only_flag_new_sources():
    """--only should work for newly added sources."""
    # This should not raise — verifies the _name_to_flag mapping
    result = crawl(only="dzone", limit=0)
    # limit=0 still runs the crawl but returns empty slice
    assert isinstance(result, list)
