"""Tests for enhanced Mastodon source — v9.1.0.

Covers trending links, statuses, hashtags, filtering, deduplication,
category detection, and configuration options.
"""
import json
from unittest.mock import patch, MagicMock
import pytest

from clawler.sources.mastodon import MastodonSource, _guess_category, _strip_html


# --- Fixtures ---

def _make_link(url="https://example.com/article", title="Test Article",
               description="A test article", provider="Example", shares=10, accounts=5):
    return {
        "url": url, "title": title, "description": description,
        "provider_name": provider,
        "history": [{"uses": str(shares), "accounts": str(accounts)}],
    }


def _make_status(url="https://mastodon.social/@user/123", content="<p>Hello world</p>",
                 author="TestUser", acct="testuser", reblogs=5, favourites=10,
                 replies=2, created_at="2026-02-16T10:00:00Z", tags=None):
    return {
        "url": url, "content": content,
        "account": {"display_name": author, "username": author.lower(), "acct": acct},
        "reblogs_count": reblogs, "favourites_count": favourites, "replies_count": replies,
        "created_at": created_at, "tags": tags or [],
    }


def _make_hashtag(name="python", uses=50, accounts=20, url=None):
    return {
        "name": name,
        "url": url or f"https://mastodon.social/tags/{name}",
        "history": [{"uses": str(uses), "accounts": str(accounts)}],
    }


def _mock_fetch_json(responses):
    """Return a side_effect function that maps URLs to responses."""
    def fetch(url):
        for pattern, data in responses.items():
            if pattern in url:
                return data
        return []
    return fetch


# --- Tests ---

class TestMastodonLinks:
    def test_crawl_links_basic(self):
        src = MastodonSource(instances=["mastodon.social"], include_statuses=False, include_hashtags=False)
        src.fetch_json = _mock_fetch_json({
            "trends/links": [_make_link()],
        })
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].title == "Test Article"
        assert "link" in articles[0].tags
        assert "fediverse" in articles[0].tags

    def test_crawl_links_dedup_across_instances(self):
        link = _make_link()
        src = MastodonSource(instances=["mastodon.social", "fosstodon.org"],
                             include_statuses=False, include_hashtags=False)
        src.fetch_json = _mock_fetch_json({
            "trends/links": [link],
        })
        articles = src.crawl()
        assert len(articles) == 1  # same URL, only counted once

    def test_crawl_links_min_shares_filter(self):
        src = MastodonSource(instances=["mastodon.social"], min_shares=100,
                             include_statuses=False, include_hashtags=False)
        src.fetch_json = _mock_fetch_json({
            "trends/links": [_make_link(shares=5)],
        })
        articles = src.crawl()
        assert len(articles) == 0

    def test_crawl_links_skip_empty_title(self):
        src = MastodonSource(instances=["mastodon.social"],
                             include_statuses=False, include_hashtags=False)
        src.fetch_json = _mock_fetch_json({
            "trends/links": [_make_link(title="")],
        })
        articles = src.crawl()
        assert len(articles) == 0


class TestMastodonStatuses:
    def test_crawl_statuses_basic(self):
        src = MastodonSource(instances=["mastodon.social"], include_links=False, include_hashtags=False)
        src.fetch_json = _mock_fetch_json({
            "trends/statuses": [_make_status()],
        })
        articles = src.crawl()
        assert len(articles) == 1
        assert "Hello world" in articles[0].title
        assert "status" in articles[0].tags
        assert "5 boosts" in articles[0].summary

    def test_crawl_statuses_with_hashtags(self):
        src = MastodonSource(instances=["mastodon.social"], include_links=False, include_hashtags=False)
        status = _make_status(tags=[{"name": "python"}, {"name": "coding"}])
        src.fetch_json = _mock_fetch_json({
            "trends/statuses": [status],
        })
        articles = src.crawl()
        assert "#python" in articles[0].tags
        assert "#coding" in articles[0].tags

    def test_crawl_statuses_author_tag(self):
        src = MastodonSource(instances=["mastodon.social"], include_links=False, include_hashtags=False)
        src.fetch_json = _mock_fetch_json({
            "trends/statuses": [_make_status(acct="alice@mastodon.social")],
        })
        articles = src.crawl()
        assert "author:alice@mastodon.social" in articles[0].tags

    def test_crawl_statuses_skip_empty_content(self):
        src = MastodonSource(instances=["mastodon.social"], include_links=False, include_hashtags=False)
        src.fetch_json = _mock_fetch_json({
            "trends/statuses": [_make_status(content="")],
        })
        articles = src.crawl()
        assert len(articles) == 0

    def test_crawl_statuses_parses_timestamp(self):
        src = MastodonSource(instances=["mastodon.social"], include_links=False, include_hashtags=False)
        src.fetch_json = _mock_fetch_json({
            "trends/statuses": [_make_status(created_at="2026-02-16T08:30:00Z")],
        })
        articles = src.crawl()
        assert articles[0].timestamp.hour == 8
        assert articles[0].timestamp.minute == 30


class TestMastodonHashtags:
    def test_crawl_hashtags_basic(self):
        src = MastodonSource(instances=["mastodon.social"], include_links=False, include_statuses=False)
        src.fetch_json = _mock_fetch_json({
            "trends/tags": [_make_hashtag("rust")],
        })
        articles = src.crawl()
        assert len(articles) == 1
        assert "#rust" in articles[0].title
        assert "hashtag" in articles[0].tags

    def test_crawl_hashtags_min_accounts_filter(self):
        src = MastodonSource(instances=["mastodon.social"], min_accounts=100,
                             include_links=False, include_statuses=False)
        src.fetch_json = _mock_fetch_json({
            "trends/tags": [_make_hashtag(accounts=5)],
        })
        articles = src.crawl()
        assert len(articles) == 0


class TestCategoryDetection:
    @pytest.mark.parametrize("text,expected", [
        ("New AI model released", "ai"),
        ("Linux kernel update", "tech"),
        ("NASA discovers new exoplanet", "science"),
        ("Critical CVE vulnerability found", "security"),
        ("Stock market crash", "business"),
        ("New election results", "politics"),
        ("Cancer treatment breakthrough", "health"),
        ("Steam summer sale", "gaming"),
        ("New Figma features", "design"),
        ("Random cat photo", "general"),
    ])
    def test_category_keywords(self, text, expected):
        assert _guess_category(text, "", "") == expected


class TestStripHtml:
    def test_basic_strip(self):
        assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_empty_input(self):
        assert _strip_html("") == ""

    def test_none_input(self):
        assert _strip_html(None) == ""

    def test_truncates_long_content(self):
        long = "<p>" + "x" * 500 + "</p>"
        result = _strip_html(long)
        assert len(result) <= 300


class TestConfiguration:
    def test_default_instances(self):
        src = MastodonSource()
        assert "mastodon.social" in src.instances
        assert len(src.instances) == 6

    def test_custom_instances(self):
        src = MastodonSource(instances=["my.instance"])
        assert src.instances == ["my.instance"]

    def test_disable_feeds(self):
        src = MastodonSource(instances=["mastodon.social"],
                             include_links=False, include_statuses=False, include_hashtags=False)
        src.fetch_json = lambda url: []
        articles = src.crawl()
        assert len(articles) == 0
