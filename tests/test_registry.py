"""Tests for the source registry."""
import pytest
from clawler.registry import SOURCES, get_all_keys, get_entry, build_sources


def test_registry_has_all_sources():
    """Registry should contain all registered sources."""
    assert len(SOURCES) == 73


def test_keys_are_unique():
    keys = get_all_keys()
    assert len(keys) == len(set(keys)), "Duplicate keys in registry"


def test_get_entry():
    entry = get_entry("hn")
    assert entry is not None
    assert entry.display_name == "Hacker News"


def test_get_entry_missing():
    assert get_entry("nonexistent") is None


def test_flag_names():
    entry = get_entry("reddit")
    assert entry.flag_name == "no_reddit"


def test_load_class():
    entry = get_entry("rss")
    cls = entry.load_class()
    assert cls.__name__ == "RSSSource"


def test_build_sources_all():
    sources = build_sources()
    assert len(sources) == 73


def test_build_sources_disabled():
    sources = build_sources(disabled={"reddit", "hn", "rss"})
    assert len(sources) == 70
    names = {type(s).__name__ for s in sources}
    assert "RedditSource" not in names
    assert "HackerNewsSource" not in names


def test_build_sources_timeout():
    sources = build_sources(disabled=set(get_all_keys()) - {"hn"}, timeout=30)
    assert len(sources) == 1
    assert sources[0].timeout == 30
