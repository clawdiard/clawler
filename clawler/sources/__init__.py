"""Source plugins for Clawler."""
from .rss import RSSSource
from .hackernews import HackerNewsSource
from .reddit import RedditSource

__all__ = ["RSSSource", "HackerNewsSource", "RedditSource"]
