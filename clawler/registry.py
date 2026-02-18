"""Centralized source registry for Clawler.

Single source of truth for all available sources. Adding a new source only
requires:
1. Create the source module in clawler/sources/
2. Add one entry to SOURCES below

Everything else (engine defaults, CLI flags, API kwargs, __init__ exports)
derives from this registry automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Type

from clawler.sources.base import BaseSource


@dataclass(frozen=True)
class SourceEntry:
    """Metadata for a registered source."""
    key: str                    # CLI flag name, e.g. "hn", "reddit"
    cls_path: str               # Dotted import path, e.g. "clawler.sources.hackernews.HackerNewsSource"
    display_name: str           # Human-friendly name

    @property
    def flag_name(self) -> str:
        """CLI --no-<key> flag."""
        return f"no_{self.key}"

    def load_class(self) -> Type[BaseSource]:
        """Lazily import and return the source class."""
        module_path, class_name = self.cls_path.rsplit(".", 1)
        import importlib
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)


# ── Registry ──────────────────────────────────────────────────────────
# Order here determines default crawl order.
SOURCES: List[SourceEntry] = [
    SourceEntry("rss",            "clawler.sources.rss.RSSSource",                            "RSS"),
    SourceEntry("hn",             "clawler.sources.hackernews.HackerNewsSource",               "Hacker News"),
    SourceEntry("reddit",         "clawler.sources.reddit.RedditSource",                       "Reddit"),
    SourceEntry("github",         "clawler.sources.github_trending.GitHubTrendingSource",      "GitHub Trending"),
    SourceEntry("mastodon",       "clawler.sources.mastodon.MastodonSource",                   "Mastodon"),
    SourceEntry("wikipedia",      "clawler.sources.wikipedia.WikipediaCurrentEventsSource",    "Wikipedia"),
    SourceEntry("lobsters",       "clawler.sources.lobsters.LobstersSource",                   "Lobsters"),
    SourceEntry("devto",          "clawler.sources.devto.DevToSource",                         "Dev.to"),
    SourceEntry("arxiv",          "clawler.sources.arxiv.ArXivSource",                         "ArXiv"),
    SourceEntry("techmeme",       "clawler.sources.techmeme.TechMemeSource",                   "TechMeme"),
    SourceEntry("producthunt",    "clawler.sources.producthunt.ProductHuntSource",             "Product Hunt"),
    SourceEntry("bluesky",        "clawler.sources.bluesky.BlueskySource",                     "Bluesky"),
    SourceEntry("tildes",         "clawler.sources.tildes.TildesSource",                       "Tildes"),
    SourceEntry("lemmy",          "clawler.sources.lemmy.LemmySource",                         "Lemmy"),
    SourceEntry("slashdot",       "clawler.sources.slashdot.SlashdotSource",                   "Slashdot"),
    SourceEntry("stackoverflow",  "clawler.sources.stackoverflow.StackOverflowSource",         "Stack Overflow"),
    SourceEntry("pinboard",       "clawler.sources.pinboard.PinboardSource",                   "Pinboard"),
    SourceEntry("indiehackers",   "clawler.sources.indiehackers.IndieHackersSource",           "Indie Hackers"),
    SourceEntry("echojs",         "clawler.sources.echojs.EchoJSSource",                       "EchoJS"),
    SourceEntry("hashnode",       "clawler.sources.hashnode.HashnodeSource",                   "Hashnode"),
    SourceEntry("freecodecamp",   "clawler.sources.freecodecamp.FreeCodeCampSource",           "freeCodeCamp"),
    SourceEntry("changelog",      "clawler.sources.changelog.ChangelogSource",                 "Changelog"),
    SourceEntry("hackernoon",     "clawler.sources.hackernoon.HackerNoonSource",               "Hacker Noon"),
    SourceEntry("youtube",        "clawler.sources.youtube.YouTubeSource",                     "YouTube"),
    SourceEntry("medium",         "clawler.sources.medium.MediumSource",                       "Medium"),
    SourceEntry("substack",       "clawler.sources.substack.SubstackSource",                   "Substack"),
    SourceEntry("googlenews",     "clawler.sources.googlenews.GoogleNewsSource",               "Google News"),
    SourceEntry("dzone",          "clawler.sources.dzone.DZoneSource",                         "DZone"),
    SourceEntry("sciencedaily",   "clawler.sources.sciencedaily.ScienceDailySource",           "ScienceDaily"),
    SourceEntry("npr",            "clawler.sources.npr.NPRSource",                             "NPR"),
    SourceEntry("arstechnica",    "clawler.sources.arstechnica.ArsTechnicaSource",             "Ars Technica"),
    SourceEntry("alltop",         "clawler.sources.alltop.AllTopSource",                       "AllTop"),
    SourceEntry("wired",          "clawler.sources.wired.WiredSource",                         "Wired"),
    SourceEntry("theverge",       "clawler.sources.theverge.TheVergeSource",                   "The Verge"),
    SourceEntry("reuters",        "clawler.sources.reuters.ReutersSource",                     "Reuters"),
    SourceEntry("physorg",        "clawler.sources.physorg.PhysOrgSource",                     "Phys.org"),
    SourceEntry("nature",         "clawler.sources.nature.NatureSource",                       "Nature"),
    SourceEntry("apnews",         "clawler.sources.apnews.APNewsSource",                       "AP News"),
    SourceEntry("guardian",       "clawler.sources.guardian.GuardianSource",                    "The Guardian"),
    SourceEntry("infoq",          "clawler.sources.infoq.InfoQSource",                         "InfoQ"),
    SourceEntry("theregister",    "clawler.sources.theregister.TheRegisterSource",             "The Register"),
    SourceEntry("bbc",            "clawler.sources.bbc.BBCNewsSource",                         "BBC News"),
    SourceEntry("thehackernews",  "clawler.sources.thehackernews.TheHackerNewsSource",         "The Hacker News"),
    SourceEntry("flipboard",      "clawler.sources.flipboard.FlipboardSource",                 "Flipboard"),
    SourceEntry("techcrunch",    "clawler.sources.techcrunch.TechCrunchSource",               "TechCrunch"),
    SourceEntry("engadget",      "clawler.sources.engadget.EngadgetSource",                   "Engadget"),
    SourceEntry("cnbc",          "clawler.sources.cnbc.CNBCSource",                           "CNBC"),
    SourceEntry("marketwatch",   "clawler.sources.marketwatch.MarketWatchSource",             "MarketWatch"),
    SourceEntry("venturebeat",   "clawler.sources.venturebeat.VentureBeatSource",             "VentureBeat"),
    SourceEntry("techradar",     "clawler.sources.techradar.TechRadarSource",                 "TechRadar"),
    SourceEntry("metafilter",    "clawler.sources.metafilter.MetaFilterSource",               "MetaFilter"),
    SourceEntry("quantamagazine", "clawler.sources.quantamagazine.QuantaMagazineSource",   "Quanta Magazine"),
    SourceEntry("politico",       "clawler.sources.politico.PoliticoSource",                 "Politico"),
    SourceEntry("aljazeera",      "clawler.sources.aljazeera.AlJazeeraSource",               "Al Jazeera"),
    SourceEntry("restofworld",    "clawler.sources.restofworld.RestOfWorldSource",           "Rest of World"),
    SourceEntry("semafor",        "clawler.sources.semafor.SemaforSource",                   "Semafor"),
]

# Quick lookups
_BY_KEY: Dict[str, SourceEntry] = {s.key: s for s in SOURCES}


def get_all_keys() -> List[str]:
    """Return all registered source keys."""
    return [s.key for s in SOURCES]


def get_entry(key: str) -> Optional[SourceEntry]:
    """Look up a source entry by key."""
    return _BY_KEY.get(key)


def build_sources(*, disabled: Optional[set] = None, timeout: int = 15) -> List[BaseSource]:
    """Instantiate all enabled sources.

    Args:
        disabled: Set of source keys to skip (e.g. {"reddit", "hn"}).
        timeout: HTTP timeout to set on each source.
    """
    disabled = disabled or set()
    result = []
    for entry in SOURCES:
        if entry.key not in disabled:
            cls = entry.load_class()
            src = cls()
            src.timeout = timeout
            result.append(src)
    return result
