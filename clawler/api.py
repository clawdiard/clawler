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

"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Union

from clawler.engine import CrawlEngine
from clawler.models import Article
from clawler.sources import GitHubTrendingSource, HackerNewsSource, RedditSource, RSSSource


def _parse_since(value: str) -> datetime:
    from clawler.utils import parse_since
    return parse_since(value)


def crawl(
    *,
    category: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
    exclude_source: Optional[str] = None,
    exclude_category: Optional[str] = None,
    no_rss: bool = False,
    no_hn: bool = False,
    no_reddit: bool = False,
    no_github: bool = False,
    dedupe_threshold: float = 0.75,
    timeout: int = 15,
    profile: Optional[Union[str, dict]] = None,
    min_relevance: float = 0.0,
) -> List[Article]:
    """One-liner crawl with filtering, dedup, and optional profile scoring.

    Args:
        category: Comma-separated category filter (e.g. "tech,science").
        source: Source name substring filter (case-insensitive).
        search: Keyword filter on title/summary (case-insensitive).
        since: Relative time filter (e.g. "2h", "30m", "1d").
        limit: Max articles to return.
        exclude_source: Exclude sources matching this substring.
        exclude_category: Comma-separated categories to exclude.
        no_rss/no_hn/no_reddit/no_github: Disable individual sources.
        dedupe_threshold: Fuzzy dedup threshold (0.0-1.0).
        timeout: HTTP timeout in seconds.
        profile: Path to a YAML profile file, or a dict with 'interests' key.
                 Each interest has keywords and an optional weight.
        min_relevance: Minimum relevance score (0.0-1.0) when profile is used.

    Returns:
        List of Article objects, sorted by time (or relevance if profile given).
    """
    # Build sources
    sources = []
    if not no_rss:
        src = RSSSource()
        src.timeout = timeout
        sources.append(src)
    if not no_hn:
        src = HackerNewsSource()
        src.timeout = timeout
        sources.append(src)
    if not no_reddit:
        src = RedditSource()
        src.timeout = timeout
        sources.append(src)
    if not no_github:
        src = GitHubTrendingSource()
        src.timeout = timeout
        sources.append(src)

    if not sources:
        return []

    engine = CrawlEngine(sources=sources)
    articles, _stats, _dedup_stats = engine.crawl(dedupe_threshold=dedupe_threshold)

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
    if since:
        cutoff = _parse_since(since)
        articles = [a for a in articles if a.timestamp and a.timestamp >= cutoff]

    # Profile-based relevance scoring
    if profile:
        from clawler.profile import score_articles
        articles = score_articles(articles, profile, min_relevance=min_relevance)

    return articles[:limit]
