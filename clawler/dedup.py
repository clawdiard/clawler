"""Deduplication engine for Clawler."""
from typing import List
from clawler.models import Article
from difflib import SequenceMatcher


def deduplicate(articles: List[Article], similarity_threshold: float = 0.75) -> List[Article]:
    """Remove duplicate articles using exact key + fuzzy title matching."""
    seen_keys = set()
    seen_titles = []
    unique = []

    for article in articles:
        # Exact dedup
        if article.dedup_key in seen_keys:
            continue

        # Fuzzy title dedup (catch same story from different sources)
        title_lower = article.title.lower().strip()
        is_dupe = False
        for prev_title in seen_titles:
            if SequenceMatcher(None, title_lower, prev_title).ratio() > similarity_threshold:
                is_dupe = True
                break

        if is_dupe:
            continue

        seen_keys.add(article.dedup_key)
        seen_titles.append(title_lower)
        unique.append(article)

    return unique
