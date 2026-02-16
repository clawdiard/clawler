"""Public Python API for Clawler — use as a library.

Quick start:

    from clawler.api import crawl

    articles = crawl()                          # all sources, top 50
    articles = crawl(category="tech", limit=10) # tech only, top 10
    articles = crawl(search="AI", since="2h")   # keyword + time filter

    for a in articles:
        print(a.title, a.url)

Profile-based relevance scoring:

    articles = crawl(profile="interests.yaml")  # score & sort by relevance
    for a in articles:
        print(f"[{a.relevance:.0%}] {a.title}")

Interest-based filtering (no file needed):

    articles = crawl(interests="AI, skateboarding, rust")
    for a in articles:
        print(f"[{a.relevance:.0%}] {a.title}")

All 26 sources (RSS, HN, Reddit, GitHub, Mastodon, Wikipedia, Lobsters,
Dev.to, ArXiv, TechMeme, ProductHunt, Bluesky, Tildes, Lemmy, Slashdot,
Stack Overflow, Pinboard, Indie Hackers, EchoJS, Hashnode, freeCodeCamp,
Changelog, Hacker Noon, YouTube, Medium, Substack) are enabled by default.
Disable any with no_<source>=True.

"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Union

from clawler.engine import CrawlEngine
from clawler.models import Article
from clawler.sources import (
    RSSSource, HackerNewsSource, RedditSource, GitHubTrendingSource,
    MastodonSource, WikipediaCurrentEventsSource, LobstersSource,
    DevToSource, ArXivSource, TechMemeSource, ProductHuntSource,
    BlueskySource, TildesSource, LemmySource, SlashdotSource,
    StackOverflowSource, PinboardSource, IndieHackersSource,
    EchoJSSource, HashnodeSource, FreeCodeCampSource, ChangelogSource,
    HackerNoonSource,
    YouTubeSource,
    MediumSource,
    SubstackSource,
    GoogleNewsSource,
    AllTopSource,
    ArsTechnicaSource,
)


def _parse_since(value: str) -> datetime:
    from clawler.utils import parse_since
    return parse_since(value)


def crawl(
    *,
    category: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    exclude: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
    exclude_source: Optional[str] = None,
    exclude_category: Optional[str] = None,
    no_rss: bool = False,
    no_hn: bool = False,
    no_reddit: bool = False,
    no_github: bool = False,
    no_mastodon: bool = False,
    no_wikipedia: bool = False,
    no_lobsters: bool = False,
    no_devto: bool = False,
    no_arxiv: bool = False,
    no_techmeme: bool = False,
    no_producthunt: bool = False,
    no_bluesky: bool = False,
    no_tildes: bool = False,
    no_lemmy: bool = False,
    no_slashdot: bool = False,
    no_stackoverflow: bool = False,
    no_pinboard: bool = False,
    no_indiehackers: bool = False,
    no_echojs: bool = False,
    no_hashnode: bool = False,
    no_freecodecamp: bool = False,
    no_changelog: bool = False,
    no_hackernoon: bool = False,
    no_youtube: bool = False,
    no_medium: bool = False,
    no_substack: bool = False,
    no_googlenews: bool = False,
    no_alltop: bool = False,
    no_arstechnica: bool = False,
    only: Optional[str] = None,
    dedupe_threshold: float = 0.75,
    dedupe_enabled: bool = True,
    timeout: int = 15,
    max_workers: int = 6,
    profile: Optional[Union[str, dict]] = None,
    interests: Optional[str] = None,
    min_relevance: float = 0.0,
    min_quality: float = 0.0,
    sample: int = 0,
) -> List[Article]:
    """One-liner crawl with filtering, dedup, and optional profile scoring.

    Args:
        category: Comma-separated category filter (e.g. "tech,science").
        source: Source name substring filter (case-insensitive).
        search: Keyword filter on title/summary (case-insensitive).
        exclude: Exclude articles matching keyword in title/summary (case-insensitive).
        since: Relative time filter (e.g. "2h", "30m", "1d").
        limit: Max articles to return.
        exclude_source: Exclude sources matching this substring.
        exclude_category: Comma-separated categories to exclude.
        no_rss/no_hn/no_reddit/no_github/no_mastodon/no_wikipedia/no_lobsters/
        no_devto/no_arxiv/no_techmeme/no_producthunt/no_bluesky/no_tildes/
        no_lemmy/no_slashdot/no_stackoverflow/no_pinboard/no_indiehackers/
        no_echojs/no_hashnode/no_freecodecamp/no_changelog: Disable individual sources.
        dedupe_threshold: Fuzzy dedup threshold (0.0-1.0).
        dedupe_enabled: Set False to disable deduplication entirely.
        timeout: HTTP timeout in seconds.
        max_workers: Max parallel workers for crawling (default: 6).
        profile: Path to a YAML profile file, or a dict with 'interests' key.
                 Each interest has keywords and an optional weight.
        interests: Comma-separated interest keywords (e.g. "AI,skateboarding").
                   Simpler alternative to profile. Ignored if profile is set.
        min_relevance: Minimum relevance score (0.0-1.0) when profile is used.
        min_quality: Minimum source quality score (0.0-1.0).
        sample: Randomly sample N articles from results (0 = disabled).

    Returns:
        List of Article objects, sorted by time (or relevance if profile given).
    """
    # Build sources — all 22 sources, matching CLI parity
    # --only support: if specified, disable all sources not in the list
    if only:
        _name_to_flag = {
            "rss": "no_rss", "hn": "no_hn", "reddit": "no_reddit",
            "github": "no_github", "mastodon": "no_mastodon",
            "wikipedia": "no_wikipedia", "lobsters": "no_lobsters",
            "devto": "no_devto", "arxiv": "no_arxiv",
            "techmeme": "no_techmeme", "producthunt": "no_producthunt",
            "bluesky": "no_bluesky", "tildes": "no_tildes",
            "lemmy": "no_lemmy", "slashdot": "no_slashdot",
            "stackoverflow": "no_stackoverflow", "pinboard": "no_pinboard",
            "indiehackers": "no_indiehackers", "echojs": "no_echojs",
            "hashnode": "no_hashnode",
            "freecodecamp": "no_freecodecamp",
            "changelog": "no_changelog",
            "hackernoon": "no_hackernoon",
            "youtube": "no_youtube",
            "medium": "no_medium",
            "substack": "no_substack",
            "googlenews": "no_googlenews",
        }
        enabled_set = set(s.strip().lower() for s in only.split(",") if s.strip())
        _locals = locals()
        for src_name, flag in _name_to_flag.items():
            if src_name not in enabled_set:
                _locals[flag] = True
        no_rss = _locals.get("no_rss", no_rss)
        no_hn = _locals.get("no_hn", no_hn)
        no_reddit = _locals.get("no_reddit", no_reddit)
        no_github = _locals.get("no_github", no_github)
        no_mastodon = _locals.get("no_mastodon", no_mastodon)
        no_wikipedia = _locals.get("no_wikipedia", no_wikipedia)
        no_lobsters = _locals.get("no_lobsters", no_lobsters)
        no_devto = _locals.get("no_devto", no_devto)
        no_arxiv = _locals.get("no_arxiv", no_arxiv)
        no_techmeme = _locals.get("no_techmeme", no_techmeme)
        no_producthunt = _locals.get("no_producthunt", no_producthunt)
        no_bluesky = _locals.get("no_bluesky", no_bluesky)
        no_tildes = _locals.get("no_tildes", no_tildes)
        no_lemmy = _locals.get("no_lemmy", no_lemmy)
        no_slashdot = _locals.get("no_slashdot", no_slashdot)
        no_stackoverflow = _locals.get("no_stackoverflow", no_stackoverflow)
        no_pinboard = _locals.get("no_pinboard", no_pinboard)
        no_indiehackers = _locals.get("no_indiehackers", no_indiehackers)
        no_echojs = _locals.get("no_echojs", no_echojs)
        no_hashnode = _locals.get("no_hashnode", no_hashnode)
        no_freecodecamp = _locals.get("no_freecodecamp", no_freecodecamp)
        no_changelog = _locals.get("no_changelog", no_changelog)
        no_hackernoon = _locals.get("no_hackernoon", no_hackernoon)
        no_youtube = _locals.get("no_youtube", no_youtube)
        no_medium = _locals.get("no_medium", no_medium)
        no_substack = _locals.get("no_substack", no_substack)
        no_googlenews = _locals.get("no_googlenews", no_googlenews)

    _source_map = [
        (no_rss, RSSSource),
        (no_hn, HackerNewsSource),
        (no_reddit, RedditSource),
        (no_github, GitHubTrendingSource),
        (no_mastodon, MastodonSource),
        (no_wikipedia, WikipediaCurrentEventsSource),
        (no_lobsters, LobstersSource),
        (no_devto, DevToSource),
        (no_arxiv, ArXivSource),
        (no_techmeme, TechMemeSource),
        (no_producthunt, ProductHuntSource),
        (no_bluesky, BlueskySource),
        (no_tildes, TildesSource),
        (no_lemmy, LemmySource),
        (no_slashdot, SlashdotSource),
        (no_stackoverflow, StackOverflowSource),
        (no_pinboard, PinboardSource),
        (no_indiehackers, IndieHackersSource),
        (no_echojs, EchoJSSource),
        (no_hashnode, HashnodeSource),
        (no_freecodecamp, FreeCodeCampSource),
        (no_changelog, ChangelogSource),
        (no_hackernoon, HackerNoonSource),
        (no_youtube, YouTubeSource),
        (no_medium, MediumSource),
        (no_substack, SubstackSource),
        (no_googlenews, GoogleNewsSource),
        (no_alltop, AllTopSource),
        (no_arstechnica, ArsTechnicaSource),
    ]
    sources = []
    for disabled, cls in _source_map:
        if not disabled:
            src = cls()
            src.timeout = timeout
            sources.append(src)

    if not sources:
        return []

    engine = CrawlEngine(sources=sources, max_workers=max_workers)
    articles, _stats, _dedup_stats = engine.crawl(
        dedupe_threshold=dedupe_threshold,
        dedupe_enabled=dedupe_enabled,
    )

    # Filters
    if category:
        cats = set(c.strip().lower() for c in category.split(","))
        articles = [a for a in articles if a.category in cats]
    if source:
        q = source.lower()
        articles = [a for a in articles if q in a.source.lower()]
    if exclude_source:
        eq = exclude_source.lower()
        articles = [a for a in articles if eq not in a.source.lower()]
    if exclude_category:
        excl = set(c.strip().lower() for c in exclude_category.split(","))
        articles = [a for a in articles if a.category not in excl]
    if search:
        kw = search.lower()
        articles = [a for a in articles if kw in a.title.lower() or kw in a.summary.lower()]
    if exclude:
        ekw = exclude.lower()
        articles = [a for a in articles if ekw not in a.title.lower() and ekw not in a.summary.lower()]
    if since:
        cutoff = _parse_since(since)
        articles = [a for a in articles if a.timestamp and a.timestamp >= cutoff]

    # Filter by quality score
    if min_quality > 0:
        articles = [a for a in articles if a.quality_score >= min_quality]

    # Profile-based relevance scoring
    profile_data = profile
    if not profile_data and interests:
        from clawler.profile import interests_to_profile
        profile_data = interests_to_profile(interests)

    if profile_data:
        from clawler.profile import score_articles
        articles = score_articles(articles, profile_data, min_relevance=min_relevance)

    result = articles[:limit]

    # Random sampling
    if sample > 0 and len(result) > sample:
        import random
        result = random.sample(result, sample)

    return result
