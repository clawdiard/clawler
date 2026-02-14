"""Source plugins for Clawler."""
from .rss import RSSSource
from .hackernews import HackerNewsSource
from .reddit import RedditSource
from .github_trending import GitHubTrendingSource
from .mastodon import MastodonSource

__all__ = ["RSSSource", "HackerNewsSource", "RedditSource", "GitHubTrendingSource", "MastodonSource"]
