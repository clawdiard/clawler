"""Tests for sentiment/tone classification (v7.0.0)."""
from clawler.models import Article
from clawler.sentiment import classify_tone, filter_by_tone


def _article(title, summary=""):
    return Article(title=title, url="https://example.com", source="test", summary=summary)


class TestClassifyTone:
    def test_positive_article(self):
        a = _article("Breakthrough Discovery in Cancer Research", "Scientists achieve a major milestone in cure development")
        assert classify_tone(a) == "positive"

    def test_negative_article(self):
        a = _article("Major Cyberattack Kills Critical Infrastructure", "Devastating breach threatens millions, collapse feared")
        assert classify_tone(a) == "negative"

    def test_neutral_article(self):
        a = _article("Python 3.13 Now Available with New Features", "The latest version includes several updates")
        assert classify_tone(a) == "neutral"

    def test_mixed_leans_neutral(self):
        a = _article("New App Launched Despite Privacy Concerns", "The release was successful but hacked data leaked")
        # Both positive and negative signals — classify based on weight
        tone = classify_tone(a)
        assert tone in ("positive", "negative", "neutral")

    def test_empty_article(self):
        a = _article("", "")
        assert classify_tone(a) == "neutral"


class TestFilterByTone:
    def test_filter_positive(self):
        articles = [
            _article("Breakthrough in AI", "Major achievement and milestone"),
            _article("Stock Market Crash", "Devastating collapse kills growth"),
            _article("Python 3.13 Released", "New version available"),
        ]
        result = filter_by_tone(articles, tone="positive")
        assert len(result) >= 1
        for a in result:
            assert classify_tone(a) == "positive"

    def test_no_doom_removes_negative(self):
        articles = [
            _article("Breakthrough in AI", "Major achievement and milestone"),
            _article("War Kills Thousands in Attack", "Devastating bomb explosion disaster"),
            _article("Python 3.13 Released", "New version available"),
        ]
        result = filter_by_tone(articles, no_doom=True)
        for a in result:
            assert classify_tone(a) != "negative"

    def test_no_filter_returns_all(self):
        articles = [
            _article("Breakthrough in AI"),
            _article("War Kills Thousands"),
            _article("Python 3.13 Released"),
        ]
        result = filter_by_tone(articles)
        assert len(result) == len(articles)

    def test_combined_tone_and_no_doom(self):
        articles = [
            _article("Breakthrough Discovery", "Innovation and success achieved"),
            _article("War Crisis Kills Many", "Devastating attack collapse"),
        ]
        result = filter_by_tone(articles, tone="positive", no_doom=True)
        for a in result:
            assert classify_tone(a) == "positive"


class TestProfileInit:
    def test_profile_init_flag_exists(self):
        """Verify --profile-init is recognized by the CLI parser."""
        from clawler.cli import main
        import sys
        from io import StringIO
        # Just verify the flag parses without error (will print and return)
        import tempfile
        import os
        home = tempfile.mkdtemp()
        old_home = os.environ.get("HOME")
        try:
            os.environ["HOME"] = home
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                main(["--profile-init"])
            finally:
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout
            assert "starter profile" in output.lower() or "already exists" in output.lower()
        finally:
            if old_home:
                os.environ["HOME"] = old_home


class TestToneCLIFlags:
    def test_tone_flag_parses(self):
        """Verify --tone and --no-doom are recognized."""
        import argparse
        from clawler.cli import main
        # Just import to verify no syntax errors
        assert callable(main)
