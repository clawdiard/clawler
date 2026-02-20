"""Story clustering for Clawler.

Groups related articles into "stories" — collections of articles about the
same event or topic from different sources. Unlike dedup (which removes
duplicates), clustering preserves all articles but groups them for display.

This enables:
  - "Top stories" mode showing the biggest news by cross-source coverage
  - Multi-perspective views of the same event
  - Better signal-to-noise ratio for busy feeds

Usage:
    clawler --stories              # group articles into stories
    clawler --stories --limit 10   # top 10 stories

API:
    from clawler.stories import cluster_stories
    stories = cluster_stories(articles)
    for story in stories:
        print(f"[{story.source_count} sources] {story.headline}")
        for a in story.articles:
            print(f"  - {a.source}: {a.title}")
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import List, Optional

from clawler.models import Article


@dataclass
class Story:
    """A cluster of related articles about the same event/topic."""
    headline: str  # representative headline (from highest-quality article)
    articles: List[Article] = field(default_factory=list)
    category: str = "general"

    @property
    def source_count(self) -> int:
        """Number of unique sources covering this story."""
        return len(set(a.source for a in self.articles))

    @property
    def sources(self) -> List[str]:
        """Unique source names covering this story."""
        seen = []
        for a in self.articles:
            if a.source not in seen:
                seen.append(a.source)
        return seen

    @property
    def best_article(self) -> Article:
        """The highest-quality article in the cluster."""
        return max(self.articles, key=lambda a: a.quality_score)

    @property
    def latest_timestamp(self):
        """Most recent timestamp across all articles."""
        timestamps = [a.timestamp for a in self.articles if a.timestamp]
        return max(timestamps) if timestamps else None

    @property
    def avg_quality(self) -> float:
        """Average quality score across articles."""
        if not self.articles:
            return 0.0
        return sum(a.quality_score for a in self.articles) / len(self.articles)

    @property
    def story_score(self) -> float:
        """Composite score: breadth of coverage × quality.

        Stories covered by more sources and with higher quality get ranked higher.
        """
        coverage_boost = min(self.source_count / 3.0, 2.0)  # cap at 2x for 6+ sources
        return self.avg_quality * (1.0 + coverage_boost)


def cluster_stories(
    articles: List[Article],
    similarity_threshold: float = 0.65,
) -> List[Story]:
    """Cluster articles into stories using fuzzy title matching.

    Similar to dedup but preserves all articles in grouped clusters.
    Uses the same fingerprint + fuzzy approach as the dedup engine.

    Args:
        articles: Pre-deduped or raw article list.
        similarity_threshold: Title similarity threshold for clustering (0.0-1.0).
            Lower than dedup threshold since we want to catch related (not just
            duplicate) articles.

    Returns:
        List of Story objects, sorted by story_score (most significant first).
    """
    stories: List[Story] = []
    # Index: (title_lower, title_len, story_index, title_words)
    title_index: List[tuple] = []

    def _significant_words(text: str) -> frozenset:
        """Extract significant words (len>3) for fast overlap check."""
        return frozenset(w for w in text.split() if len(w) > 3)

    for article in articles:
        title_lower = article.title.lower().strip()
        title_len = len(title_lower)
        title_words = _significant_words(title_lower)
        matched_idx: Optional[int] = None

        # Try to match against existing stories
        for i, (prev_title, prev_len, story_idx, prev_words) in enumerate(title_index):
            # Quick length filter
            if abs(title_len - prev_len) > max(title_len, prev_len) * (1 - similarity_threshold):
                continue
            # Quick word-overlap filter: require at least 1 shared significant word
            if title_words and prev_words and not (title_words & prev_words):
                continue
            if SequenceMatcher(None, title_lower, prev_title).ratio() > similarity_threshold:
                matched_idx = story_idx
                break

        if matched_idx is not None:
            stories[matched_idx].articles.append(article)
            # Update headline if this article has higher quality
            story = stories[matched_idx]
            if article.quality_score > story.best_article.quality_score:
                story.headline = article.title
                # Update title index entry for better future matching
                title_index[matched_idx] = (title_lower, title_len, matched_idx, title_words)
        else:
            idx = len(stories)
            story = Story(
                headline=article.title,
                articles=[article],
                category=article.category,
            )
            stories.append(story)
            title_index.append((title_lower, title_len, idx, title_words))

    # Sort by story score (most significant first)
    stories.sort(key=lambda s: s.story_score, reverse=True)
    return stories


def format_stories(stories: List[Story], limit: int = 20, show_sources: bool = True) -> str:
    """Format stories for console display.

    Args:
        stories: List of Story clusters.
        limit: Max stories to display.
        show_sources: Whether to list individual sources under each story.

    Returns:
        Formatted string ready for printing.
    """
    lines = []
    for i, story in enumerate(stories[:limit], 1):
        source_tag = f" [{story.source_count} sources]" if story.source_count > 1 else ""
        ts = ""
        if story.latest_timestamp:
            ts = f" • {story.latest_timestamp.strftime('%H:%M UTC')}"
        lines.append(f"  {i:>3}. {story.headline}{source_tag}{ts}")
        if show_sources and story.source_count > 1:
            for src in story.sources:
                lines.append(f"       └─ {src}")
        best = story.best_article
        if best.url:
            lines.append(f"       {best.url}")
        lines.append("")
    return "\n".join(lines)
