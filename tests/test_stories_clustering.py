"""Tests for story clustering word-overlap optimization."""
from clawler.models import Article
from clawler.stories import cluster_stories


def _make_article(title, source="test", quality=0.5):
    return Article(title=title, url=f"https://example.com/{hash(title)}", source=source, quality_score=quality)


def test_clustering_groups_similar_titles():
    articles = [
        _make_article("Senate passes major AI regulation bill in landmark vote", "Reuters"),
        _make_article("Senate passes major AI regulation bill in landmark bipartisan vote", "The Hill"),
        _make_article("SpaceX launches Starship to orbit successfully", "BBC"),
    ]
    stories = cluster_stories(articles, similarity_threshold=0.6)
    assert len(stories) == 2
    multi = [s for s in stories if s.source_count > 1]
    assert len(multi) == 1
    assert "AI regulation" in multi[0].headline or "Senate" in multi[0].headline


def test_clustering_no_false_match_on_short_titles():
    articles = [
        _make_article("AI news today", "A"),
        _make_article("AI news update", "B"),
        _make_article("Completely different story about economics", "C"),
    ]
    stories = cluster_stories(articles)
    econ = [s for s in stories if "economics" in s.headline.lower()]
    assert len(econ) == 1
    assert econ[0].source_count == 1


def test_clustering_word_overlap_filter_no_regression():
    """Ensure the word-overlap pre-filter doesn't break real matches."""
    articles = [
        _make_article("Google announces new quantum computing breakthrough", "TechCrunch"),
        _make_article("Google announces quantum computing breakthrough in new paper", "Wired"),
    ]
    stories = cluster_stories(articles)
    assert len(stories) == 1
    assert stories[0].source_count == 2
