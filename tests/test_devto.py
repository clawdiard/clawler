"""Tests for Dev.to source."""
import json
from unittest.mock import patch
from clawler.sources.devto import DevToSource, TAG_CATEGORY_MAP

SAMPLE_DEVTO_ARTICLES = [
    {
        "title": "Building a CLI in Rust",
        "url": "https://dev.to/alice/building-cli-rust-123",
        "user": {"name": "Alice"},
        "published_at": "2026-02-16T15:00:00Z",
        "description": "A guide to building CLIs with Rust.",
        "tag_list": ["rust", "cli", "tutorial"],
        "positive_reactions_count": 42,
        "comments_count": 7,
        "reading_time_minutes": 5,
    },
    {
        "title": "Intro to Kubernetes",
        "url": "https://dev.to/bob/intro-kubernetes-456",
        "user": {"name": "Bob"},
        "published_at": "2026-02-16T12:00:00Z",
        "description": "Getting started with K8s.",
        "tag_list": ["kubernetes", "devops"],
        "positive_reactions_count": 10,
        "comments_count": 2,
        "reading_time_minutes": 3,
    },
]


def test_devto_source_name():
    src = DevToSource()
    assert src.name == "dev.to"


def test_devto_tag_map():
    assert "ai" in TAG_CATEGORY_MAP
    assert "security" in TAG_CATEGORY_MAP


def test_devto_crawl():
    src = DevToSource(per_page=10)
    with patch.object(src, "fetch_json", return_value=SAMPLE_DEVTO_ARTICLES):
        articles = src.crawl()
    assert len(articles) == 2
    assert articles[0].title == "Building a CLI in Rust"
    assert articles[0].author == "Alice"
    assert articles[0].timestamp is not None


def test_devto_min_reactions_filter():
    src = DevToSource(min_reactions=20)
    with patch.object(src, "fetch_json", return_value=SAMPLE_DEVTO_ARTICLES):
        articles = src.crawl()
    assert len(articles) == 1
    assert articles[0].title == "Building a CLI in Rust"


def test_devto_empty_response():
    src = DevToSource()
    with patch.object(src, "fetch_json", return_value=[]):
        articles = src.crawl()
    assert articles == []


def test_devto_none_response():
    src = DevToSource()
    with patch.object(src, "fetch_json", return_value=None):
        articles = src.crawl()
    assert articles == []
