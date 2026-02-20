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
from .changelog import ChangelogSource
from .hackernoon import HackerNoonSource
from .youtube import YouTubeSource
from .medium import MediumSource
from .substack import SubstackSource
from .googlenews import GoogleNewsSource
from .dzone import DZoneSource
from .sciencedaily import ScienceDailySource
from .npr import NPRSource
from .arstechnica import ArsTechnicaSource
from .alltop import AllTopSource
from .wired import WiredSource
from .theverge import TheVergeSource
from .reuters import ReutersSource
from .physorg import PhysOrgSource
from .nature import NatureSource
from .apnews import APNewsSource
from .guardian import GuardianSource
from .infoq import InfoQSource
from .theregister import TheRegisterSource
from .bbc import BBCNewsSource
from .thehackernews import TheHackerNewsSource
from .flipboard import FlipboardSource
from .metafilter import MetaFilterSource
from .axios import AxiosSource
from .techcrunch import TechCrunchSource
from .engadget import EngadgetSource
from .cnbc import CNBCSource
from .marketwatch import MarketWatchSource
from .venturebeat import VentureBeatSource
from .techradar import TechRadarSource
from .politico import PoliticoSource
from .aljazeera import AlJazeeraSource
from .quantamagazine import QuantaMagazineSource
from .restofworld import RestOfWorldSource
from .semafor import SemaforSource
from .fourzerofourmedia import FourZeroFourMediaSource
from .propublica import ProPublicaSource
from .forbes import ForbesSource
from .economist import EconomistSource
from .nytimes import NYTimesSource
from .wsj import WSJSource
from .washingtonpost import WashingtonPostSource
from .semanticscholar import SemanticScholarSource
from .thehill import TheHillSource

__all__ = [
    "RSSSource", "HackerNewsSource", "RedditSource", "GitHubTrendingSource",
    "MastodonSource", "WikipediaCurrentEventsSource", "LobstersSource",
    "DevToSource", "ArXivSource", "TechMemeSource", "ProductHuntSource",
    "BlueskySource", "TildesSource", "LemmySource", "SlashdotSource",
    "StackOverflowSource", "PinboardSource", "IndieHackersSource",
    "EchoJSSource", "HashnodeSource", "FreeCodeCampSource", "ChangelogSource",
    "HackerNoonSource", "YouTubeSource", "MediumSource", "SubstackSource",
    "GoogleNewsSource", "DZoneSource", "ScienceDailySource", "NPRSource",
    "ArsTechnicaSource", "AllTopSource", "WiredSource", "TheVergeSource",
    "ReutersSource", "PhysOrgSource", "NatureSource", "APNewsSource",
    "GuardianSource", "InfoQSource", "TheRegisterSource", "BBCNewsSource",
    "TheHackerNewsSource", "FlipboardSource", "MetaFilterSource", "AxiosSource",
    "TechCrunchSource", "EngadgetSource", "CNBCSource", "MarketWatchSource",
    "VentureBeatSource", "TechRadarSource", "PoliticoSource", "AlJazeeraSource",
    "QuantaMagazineSource", "RestOfWorldSource", "SemaforSource",
    "FourZeroFourMediaSource", "ProPublicaSource",
    "ForbesSource", "EconomistSource",
    "NYTimesSource", "WSJSource", "WashingtonPostSource",
    "SemanticScholarSource",
    "TheHillSource",
]
