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
    seen_fingerprints: dict = {}  # fingerprint -> index in unique
    seen_titles: List[tuple] = []  # (title_lower, title_len, index in unique)
    unique: List[Article] = []

    for article in articles:
        # Tier 1: exact dedup
        if article.dedup_key in seen_keys:
            continue

        # Tier 2: fingerprint dedup (cheap cross-source catch)
        fp = article.title_fingerprint
        if fp and fp in seen_fingerprints:
            # Keep the one with higher quality_score
            idx = seen_fingerprints[fp]
            unique[idx].source_count += 1
            if article.quality_score > unique[idx].quality_score:
                seen_keys.discard(unique[idx].dedup_key)
                seen_keys.add(article.dedup_key)
                unique[idx] = article
                # Update title entry
                for i, (t, tl, tidx) in enumerate(seen_titles):
                    if tidx == idx:
                        seen_titles[i] = (article.title.lower().strip(), len(article.title.lower().strip()), idx)
                        break
            continue

        # Tier 3: fuzzy title dedup
        title_lower = article.title.lower().strip()
        title_len = len(title_lower)
        is_dupe = False
        for i, (prev_title, prev_len, prev_idx) in enumerate(seen_titles):
            if abs(title_len - prev_len) > max(title_len, prev_len) * (1 - similarity_threshold):
                continue
            if SequenceMatcher(None, title_lower, prev_title).ratio() > similarity_threshold:
                # Keep higher quality
                unique[prev_idx].source_count += 1
                if article.quality_score > unique[prev_idx].quality_score:
                    seen_keys.discard(unique[prev_idx].dedup_key)
                    seen_keys.add(article.dedup_key)
                    unique[prev_idx] = article
                    # Update title entry for future comparisons
                    seen_titles[i] = (title_lower, title_len, prev_idx)
                    # Update fingerprint map if new article has one
                    if fp:
                        seen_fingerprints[fp] = prev_idx
                is_dupe = True
                break

        if is_dupe:
            continue

        idx = len(unique)
        seen_keys.add(article.dedup_key)
        if fp:
            seen_fingerprints[fp] = idx
        seen_titles.append((title_lower, title_len, idx))
        unique.append(article)

    return unique
