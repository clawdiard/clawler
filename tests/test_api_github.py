"""Test that the public API includes GitHub Trending source."""
from unittest.mock import patch, MagicMock
from clawler.api import crawl


def test_api_includes_github_source_by_default():
    """Verify GitHubTrendingSource is included when no_github is not set."""
    with patch("clawler.api.CrawlEngine") as MockEngine:
        instance = MockEngine.return_value
        instance.crawl.return_value = ([], {})
        crawl(limit=1)
        # Check that GitHubTrendingSource was passed
        call_args = MockEngine.call_args
        source_types = [type(s).__name__ for s in call_args[1]["sources"]]
        assert "GitHubTrendingSource" in source_types


def test_api_excludes_github_when_disabled():
    """Verify GitHubTrendingSource is excluded when no_github=True."""
    with patch("clawler.api.CrawlEngine") as MockEngine:
        instance = MockEngine.return_value
        instance.crawl.return_value = ([], {})
        crawl(no_github=True, limit=1)
        call_args = MockEngine.call_args
        source_types = [type(s).__name__ for s in call_args[1]["sources"]]
        assert "GitHubTrendingSource" not in source_types
