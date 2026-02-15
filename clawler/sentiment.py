"""Lightweight sentiment/tone classification for articles.

No external dependencies — uses keyword heuristics to classify article tone.
Useful for filtering doom-scrolling content or surfacing positive/constructive news.

Usage:
    clawler --tone positive        # only uplifting/constructive articles
    clawler --tone negative        # only critical/warning articles
    clawler --tone neutral         # factual/informational articles
    clawler --no-doom              # exclude strongly negative articles
"""
from __future__ import annotations

import re
from typing import List, Optional

from clawler.models import Article

# Keyword lists for lightweight tone classification
_POSITIVE_WORDS = frozenset({
    "breakthrough", "launch", "launched", "launches", "innovation", "innovate",
    "milestone", "award", "awarded", "success", "successful", "achieve",
    "achievement", "discover", "discovered", "discovery", "cure", "solution",
    "improve", "improved", "improvement", "grow", "growth", "record-breaking",
    "celebrate", "exciting", "open-source", "free", "release", "released",
    "upgrade", "progress", "win", "winning", "won", "partnership", "fund",
    "funded", "funding", "grant", "save", "saved", "rescue", "rescued",
    "volunteer", "donate", "donation", "community", "empower", "thrive",
})

_NEGATIVE_WORDS = frozenset({
    "crash", "crisis", "disaster", "catastrophe", "catastrophic", "collapse",
    "collapsed", "kill", "killed", "killing", "death", "dead", "die", "dies",
    "attack", "attacked", "war", "bomb", "bombing", "explosion", "explode",
    "threat", "threaten", "hack", "hacked", "breach", "breached", "leak",
    "leaked", "scandal", "fraud", "scam", "arrest", "arrested", "prison",
    "jail", "lawsuit", "layoff", "layoffs", "fired", "shutdown", "bankrupt",
    "bankruptcy", "recession", "decline", "plunge", "plunged", "suffer",
    "victim", "devastate", "devastating", "surge", "worst", "fail", "failed",
    "failure", "warning", "danger", "dangerous", "toxic", "pollution",
})

_WORD_RE = re.compile(r"[a-z]+(?:-[a-z]+)*")


def classify_tone(article: Article) -> str:
    """Classify an article's tone as 'positive', 'negative', or 'neutral'.

    Uses keyword frequency in title (weighted 3x) and summary.
    Returns one of: 'positive', 'negative', 'neutral'.
    """
    title_words = set(_WORD_RE.findall(article.title.lower()))
    summary_words = set(_WORD_RE.findall(article.summary.lower()))

    # Title matches weighted 3x
    pos_score = len(title_words & _POSITIVE_WORDS) * 3 + len(summary_words & _POSITIVE_WORDS)
    neg_score = len(title_words & _NEGATIVE_WORDS) * 3 + len(summary_words & _NEGATIVE_WORDS)

    if pos_score > neg_score and pos_score >= 2:
        return "positive"
    elif neg_score > pos_score and neg_score >= 2:
        return "negative"
    return "neutral"


def filter_by_tone(
    articles: List[Article],
    tone: Optional[str] = None,
    no_doom: bool = False,
) -> List[Article]:
    """Filter articles by tone classification.

    Args:
        articles: List of articles to filter.
        tone: If set, keep only articles matching this tone ('positive', 'negative', 'neutral').
        no_doom: If True, exclude articles classified as 'negative'.

    Returns:
        Filtered list of articles.
    """
    if not tone and not no_doom:
        return articles

    result = []
    for a in articles:
        t = classify_tone(a)
        if no_doom and t == "negative":
            continue
        if tone and t != tone:
            continue
        result.append(a)
    return result
