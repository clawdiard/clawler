"""Tests for GitHub Trending source."""
from clawler.sources.github_trending import GitHubTrendingSource


def test_github_trending_init():
    src = GitHubTrendingSource()
    assert src.name == "github_trending"
    assert src.since == "daily"


def test_github_trending_custom_since():
    src = GitHubTrendingSource(since="weekly")
    assert src.since == "weekly"


def test_github_trending_returns_list():
    """Crawl returns a list (may be empty if network unavailable in CI)."""
    src = GitHubTrendingSource()
    src.timeout = 5
    src.max_retries = 0
    result = src.crawl()
    assert isinstance(result, list)
