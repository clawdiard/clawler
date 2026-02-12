"""Tests for feed autodiscovery."""
from unittest.mock import patch, MagicMock
from clawler.discover import discover_feeds, _guess_source


class TestGuessSource:
    def test_simple_domain(self):
        assert _guess_source("https://www.example.com/page") == "Example"

    def test_no_www(self):
        assert _guess_source("https://techcrunch.com/feed") == "Techcrunch"

    def test_subdomain(self):
        assert _guess_source("https://blog.example.com/rss") == "Example"


class TestDiscoverFeeds:
    def test_finds_link_alternate(self):
        html = '''<html><head>
        <link rel="alternate" type="application/rss+xml" title="My Feed" href="/feed.xml">
        </head><body></body></html>'''

        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        with patch("clawler.discover.requests.get", return_value=mock_resp):
            feeds = discover_feeds("https://example.com")
            assert len(feeds) == 1
            assert feeds[0]["url"] == "https://example.com/feed.xml"
            assert feeds[0]["title"] == "My Feed"

    def test_returns_empty_on_failure(self):
        import requests as _req
        with patch("clawler.discover.requests.get", side_effect=_req.RequestException("boom")):
            feeds = discover_feeds("https://example.com")
            assert feeds == []

    def test_no_dupes(self):
        html = '''<html><head>
        <link rel="alternate" type="application/rss+xml" href="/feed.xml">
        <link rel="alternate" type="application/atom+xml" href="/feed.xml">
        </head><body></body></html>'''

        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        with patch("clawler.discover.requests.get", return_value=mock_resp):
            feeds = discover_feeds("https://example.com")
            assert len(feeds) == 1
