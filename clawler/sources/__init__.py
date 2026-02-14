"""Source plugins for Clawler."""
from .rss import RSSSource
from .hackernews import HackerNewsSource
from .reddit import RedditSource
from .github_trending import GitHubTrendingSource
from .mastodon import MastodonSource
from .wikipedia import WikipediaCurrentEventsSource
from .lobsters import LobstersSource

__all__ = ["RSSSource", "HackerNewsSource", "RedditSource", "GitHubTrendingSource", "MastodonSource", "WikipediaCurrentEventsSource", "LobstersSource"]
