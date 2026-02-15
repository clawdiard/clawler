"""Reading time estimation for articles.

Estimates reading time based on available text (title + summary).
Since we only have metadata (not full article text), estimates are conservative
and based on the summary length as a proxy for article complexity.

Average adult reading speed: ~238 WPM (Brysbaert 2019).
We use 200 WPM to account for technical content.
"""
from __future__ import annotations

from typing import List, Optional

from clawler.models import Article

WPM = 200  # words per minute for technical content


def estimate_read_minutes(article: Article) -> int:
    """Estimate reading time in minutes from title + summary.

    Since we only have the summary (not full text), we use heuristics:
    - Short summary (<50 words): likely a brief post → 2 min
    - Medium summary (50-150 words): typical article → 3-5 min
    - Long summary (>150 words): in-depth piece → scale by WPM with 3x multiplier

    The 3x multiplier accounts for summaries being much shorter than full articles.

    Returns at least 1 minute.
    """
    text = f"{article.title} {article.summary}".strip()
    word_count = len(text.split())

    if word_count < 50:
        return 2
    elif word_count < 150:
        return max(3, round(word_count * 3 / WPM))
    else:
        return max(5, round(word_count * 3 / WPM))


def format_read_time(minutes: int) -> str:
    """Format reading time for display."""
    if minutes < 1:
        return "<1 min"
    return f"{minutes} min read"


def filter_by_read_time(
    articles: List[Article],
    min_minutes: Optional[int] = None,
    max_minutes: Optional[int] = None,
) -> List[Article]:
    """Filter articles by estimated reading time.

    Args:
        articles: List of articles to filter.
        min_minutes: Minimum reading time in minutes (inclusive).
        max_minutes: Maximum reading time in minutes (inclusive).

    Returns:
        Filtered list of articles.
    """
    if min_minutes is None and max_minutes is None:
        return articles

    result = []
    for a in articles:
        rt = estimate_read_minutes(a)
        if min_minutes is not None and rt < min_minutes:
            continue
        if max_minutes is not None and rt > max_minutes:
            continue
        result.append(a)
    return result
