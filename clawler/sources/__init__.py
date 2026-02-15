"""Source plugins for Clawler."""
from .rss import RSSSource
from .hackernews import HackerNewsSource
from .reddit import RedditSource
from .github_trending import GitHubTrendingSource
from .mastodon import MastodonSource
from .wikipedia import WikipediaCurrentEventsSource
from .lobsters import LobstersSource
from .devto import DevToSource
from .arxiv import ArXivSource
from .techmeme import TechMemeSource
from .producthunt import ProductHuntSource
from .bluesky import BlueskySource
from .tildes import TildesSource
from .lemmy import LemmySource
from .slashdot import SlashdotSource
from .stackoverflow import StackOverflowSource
from .pinboard import PinboardSource
from .indiehackers import IndieHackersSource
from .echojs import EchoJSSource
from .hashnode import HashnodeSource
from .freecodecamp import FreeCodeCampSource

__all__ = ["RSSSource", "HackerNewsSource", "RedditSource", "GitHubTrendingSource", "MastodonSource", "WikipediaCurrentEventsSource", "LobstersSource", "DevToSource", "ArXivSource", "TechMemeSource", "ProductHuntSource", "BlueskySource", "TildesSource", "LemmySource", "SlashdotSource", "StackOverflowSource", "PinboardSource", "IndieHackersSource", "EchoJSSource", "HashnodeSource", "FreeCodeCampSource"]
