"""Deduplication engine for Clawler."""
from typing import List
from clawler.models import Article
from difflib import SequenceMatcher


def deduplicate(articles: List[Article], similarity_threshold: float = 0.75) -> List[Article]:
    """Remove duplicate articles using exact key + fingerprint + fuzzy title matching.

    Three-tier dedup strategy:
    1. Exact key match (title+url hash) — O(1) lookup
    2. Title fingerprint match (sorted significant words) — O(1) lookup, catches
       obvious cross-source duplicates cheaply
    3. Fuzzy SequenceMatcher — O(n) per article, only reached if tiers 1-2 miss
    """
    seen_keys: set = set()
    seen_fingerprints: set = set()
    seen_titles: List[tuple] = []
    unique: List[Article] = []

    for article in articles:
        # Tier 1: exact dedup
        if article.dedup_key in seen_keys:
            continue

        # Tier 2: fingerprint dedup (cheap cross-source catch)
        fp = article.title_fingerprint
        if fp and fp in seen_fingerprints:
            continue

        # Tier 3: fuzzy title dedup
        title_lower = article.title.lower().strip()
        title_len = len(title_lower)
        is_dupe = False
        for prev_title, prev_len in seen_titles:
            # Quick length check: if lengths differ by more than allowed,
            # SequenceMatcher can't possibly exceed threshold
            if abs(title_len - prev_len) > max(title_len, prev_len) * (1 - similarity_threshold):
                continue
            if SequenceMatcher(None, title_lower, prev_title).ratio() > similarity_threshold:
                is_dupe = True
                break

        if is_dupe:
            continue

        seen_keys.add(article.dedup_key)
        if fp:
            seen_fingerprints.add(fp)
        seen_titles.append((title_lower, title_len))
        unique.append(article)

    return unique
