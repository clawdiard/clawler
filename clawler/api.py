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

All 48 sources (RSS, HN, Reddit, GitHub, Mastodon, Wikipedia, Lobsters,
Dev.to, ArXiv, TechMeme, ProductHunt, Bluesky, Tildes, Lemmy, Slashdot,
Stack Overflow, Pinboard, Indie Hackers, EchoJS, Hashnode, freeCodeCamp,
Changelog, Hacker Noon, YouTube, Medium, Substack, Google News, DZone,
ScienceDaily, NPR, Ars Technica, AllTop, Wired, The Verge, Reuters,
Phys.org, Nature, AP News, The Guardian, InfoQ, The Register, BBC News,
The Hacker News, Flipboard, TechCrunch, Engadget, CNBC, MarketWatch)
are enabled by default.
Disable any with disabled={"flipboard", "bbc"} or no_<source>=True.

"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Union

from clawler.engine import CrawlEngine
from clawler.models import Article
from clawler.registry import build_sources, get_all_keys


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
    only: Optional[str] = None,
    disabled: Optional[Set[str]] = None,
    dedupe_threshold: float = 0.75,
    dedupe_enabled: bool = True,
    timeout: int = 15,
    max_workers: int = 6,
    source_timeout: Optional[float] = 60,
    profile: Optional[Union[str, dict]] = None,
    interests: Optional[str] = None,
    min_relevance: float = 0.0,
    min_quality: float = 0.0,
    sample: int = 0,
    # Legacy no_<source> kwargs accepted for backward compatibility
    **kwargs,
) -> List[Article]:
    """One-liner crawl with filtering, dedup, and optional profile scoring.

    Args:
        category: Comma-separated category filter (e.g. "tech,science").
        source: Source name substring filter (case-insensitive).
        search: Keyword filter on title/summary (case-insensitive).
        exclude: Exclude articles matching keyword in title/summary.
        since: Relative time filter (e.g. "2h", "30m", "1d").
        limit: Max articles to return.
        exclude_source: Exclude sources matching this substring.
        exclude_category: Comma-separated categories to exclude.
        only: Comma-separated source keys to enable (disables all others).
        disabled: Set of source keys to skip (e.g. {"reddit", "hn"}).
        dedupe_threshold: Fuzzy dedup threshold (0.0-1.0).
        dedupe_enabled: Set False to disable deduplication entirely.
        timeout: HTTP timeout in seconds.
        max_workers: Max parallel workers for crawling (default: 6).
        source_timeout: Per-source crawl timeout in seconds (default: 60).
        profile: Path to a YAML profile file, or a dict with 'interests' key.
        interests: Comma-separated interest keywords (e.g. "AI,skateboarding").
        min_relevance: Minimum relevance score (0.0-1.0) when profile is used.
        min_quality: Minimum source quality score (0.0-1.0).
        sample: Randomly sample N articles from results (0 = disabled).
        **kwargs: Legacy no_<source>=True flags (e.g. no_hn=True, no_reddit=True).

    Returns:
        List of Article objects, sorted by time (or relevance if profile given).
    """
    # Build disabled set from multiple input methods
    skip: set = set(disabled or set())

    # Legacy no_<key>=True kwargs
    all_keys = get_all_keys()
    for key in all_keys:
        if kwargs.get(f"no_{key}", False):
            skip.add(key)

    # --only: enable only specified sources
    if only:
        enabled = set(s.strip().lower() for s in only.split(",") if s.strip())
        for key in all_keys:
            if key not in enabled:
                skip.add(key)

    sources = build_sources(disabled=skip, timeout=timeout)
    if not sources:
        return []

    engine = CrawlEngine(sources=sources, max_workers=max_workers, source_timeout=source_timeout)
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
