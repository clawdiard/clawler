"""Tests for story clustering (v10.48.0)."""
from datetime import datetime, timezone

from clawler.models import Article
from clawler.stories import Story, cluster_stories, format_stories


def _make_article(title, source, quality=0.5, url=None, ts=None):
    return Article(
        title=title,
        url=url or f"https://{source.lower().replace(' ', '')}.com/{title.lower().replace(' ', '-')}",
        source=source,
        quality_score=quality,
        timestamp=ts or datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc),
    )


def test_single_article_becomes_one_story():
    articles = [_make_article("AI Breakthrough Announced", "TechCrunch")]
    stories = cluster_stories(articles)
    assert len(stories) == 1
    assert stories[0].headline == "AI Breakthrough Announced"
    assert stories[0].source_count == 1


def test_similar_titles_cluster_together():
    articles = [
        _make_article("OpenAI Announces GPT-5 Model", "TechCrunch", quality=0.8),
        _make_article("OpenAI Announces GPT-5 Model Today", "The Verge", quality=0.7),
        _make_article("OpenAI Announces New GPT-5 Model", "Ars Technica", quality=0.6),
    ]
    stories = cluster_stories(articles)
    assert len(stories) == 1
    assert stories[0].source_count == 3
    assert len(stories[0].articles) == 3


def test_different_titles_stay_separate():
    articles = [
        _make_article("Python 4.0 Released", "HN"),
        _make_article("SpaceX Launches Starship", "Reuters"),
        _make_article("New COVID Variant Detected", "BBC"),
    ]
    stories = cluster_stories(articles)
    assert len(stories) == 3


def test_stories_sorted_by_score():
    articles = [
        _make_article("Minor Update to Library X", "Dev.to", quality=0.3),
        _make_article("Major AI Breakthrough", "Nature", quality=0.9),
        _make_article("Major AI Breakthrough Announced", "Reuters", quality=0.85),
        _make_article("Major AI Breakthrough Is Here", "NYT", quality=0.8),
    ]
    stories = cluster_stories(articles)
    # The multi-source story should rank first
    assert stories[0].source_count >= 2
    assert "AI Breakthrough" in stories[0].headline


def test_story_properties():
    a1 = _make_article("Test Story", "Source A", quality=0.9,
                       ts=datetime(2026, 2, 20, 14, 0, tzinfo=timezone.utc))
    a2 = _make_article("Test Story Update", "Source B", quality=0.5,
                       ts=datetime(2026, 2, 20, 15, 0, tzinfo=timezone.utc))
    story = Story(headline="Test Story", articles=[a1, a2])
    assert story.source_count == 2
    assert story.sources == ["Source A", "Source B"]
    assert story.best_article == a1
    assert story.latest_timestamp == datetime(2026, 2, 20, 15, 0, tzinfo=timezone.utc)
    assert story.avg_quality == 0.7
    assert story.story_score > 0


def test_format_stories_output():
    articles = [
        _make_article("Major Earthquake Strikes Northern California Today", "Reuters", quality=0.9),
        _make_article("Major Earthquake Strikes Northern California Region Today", "AP News", quality=0.8),
    ]
    stories = cluster_stories(articles)
    assert len(stories) == 1
    output = format_stories(stories, limit=5)
    assert "Earthquake" in output
    assert "Reuters" in output
    assert "AP News" in output


def test_empty_input():
    stories = cluster_stories([])
    assert stories == []


def test_cluster_threshold_sensitivity():
    # Very different titles should not cluster even with low threshold
    articles = [
        _make_article("Apple releases new iPhone", "TechCrunch"),
        _make_article("Russia-Ukraine peace talks resume", "Reuters"),
    ]
    stories = cluster_stories(articles, similarity_threshold=0.5)
    assert len(stories) == 2
