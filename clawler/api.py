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

All 12 sources (RSS, HN, Reddit, GitHub, Mastodon, Wikipedia, Lobsters,
Dev.to, ArXiv, TechMeme, ProductHunt, Bluesky) are enabled by default.
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
    BlueskySource,
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
        no_devto/no_arxiv/no_techmeme/no_producthunt: Disable individual sources.
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
    # Build sources — all 11 sources, matching CLI parity
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
