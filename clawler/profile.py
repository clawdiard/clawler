"""Interest-profile scoring for personalized news ranking.

Profile format (YAML):

    name: Alexandria
    interests:
      - keywords: [AI, machine learning, LLM, GPT, neural network]
        weight: 2.0
      - keywords: [skateboarding, skatepark, skate]
        weight: 1.5
      - keywords: [python, rust, typescript, open source]
        weight: 1.0
      - keywords: [NYC, "New York"]
        weight: 0.8

Articles are scored by keyword matches in title + summary.
Higher weight = stronger boost. Score is normalized 0.0-1.0.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from clawler.models import Article

logger = logging.getLogger(__name__)


def load_profile(profile: Union[str, dict]) -> dict:
    """Load a profile from a file path or dict."""
    if isinstance(profile, dict):
        return profile
    p = Path(profile)
    if not p.exists():
        raise FileNotFoundError(f"Profile not found: {profile}")
    content = p.read_text(encoding="utf-8")
    if p.suffix in (".yaml", ".yml"):
        import yaml
        return yaml.safe_load(content) or {}
    elif p.suffix == ".json":
        import json
        return json.loads(content)
    else:
        raise ValueError(f"Unsupported profile format: {p.suffix}")


def _score_article(article: Article, interests: List[dict]) -> float:
    """Score a single article against interest groups. Returns raw weighted score."""
    text = f"{article.title} {article.summary}".lower()
    total = 0.0
    for interest in interests:
        keywords = interest.get("keywords", [])
        weight = float(interest.get("weight", 1.0))
        hits = sum(1 for kw in keywords if kw.lower() in text)
        if hits:
            # Diminishing returns for multiple hits in same interest group
            total += weight * (1.0 + 0.3 * (hits - 1))
    return total


def score_articles(
    articles: List[Article],
    profile: Union[str, dict],
    min_relevance: float = 0.0,
) -> List[Article]:
    """Score and sort articles by relevance to an interest profile.

    Adds a `relevance` attribute (0.0-1.0) to each article.
    Filters out articles below min_relevance. Sorts by relevance desc.
    """
    data = load_profile(profile)
    interests = data.get("interests", [])
    if not interests:
        logger.warning("[Profile] No interests defined, returning articles unsorted")
        return articles

    # Score all articles
    scored = []
    for a in articles:
        raw = _score_article(a, interests)
        scored.append((a, raw))

    # Normalize to 0.0-1.0
    max_score = max((s for _, s in scored), default=1.0) or 1.0
    for article, raw in scored:
        article.relevance = raw / max_score

    # Filter and sort
    result = [a for a, raw in scored if (raw / max_score) >= min_relevance]
    result.sort(key=lambda a: a.relevance or 0.0, reverse=True)
    return result
