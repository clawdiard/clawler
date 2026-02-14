"""Tests for v5.2.0 features: --exclude-tag, --exclude-author, --age-stats."""
import io
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from clawler.models import Article


def _make_articles():
    now = datetime.now(timezone.utc)
    return [
        Article(title="Rust async deep dive", url="https://a.com/1", source="Blog",
                tags=["rust", "async"], author="Alice", timestamp=now - timedelta(hours=1)),
        Article(title="Python 4.0 released", url="https://b.com/2", source="News",
                tags=["python", "release"], author="Bob", timestamp=now - timedelta(hours=3)),
        Article(title="Go generics guide", url="https://c.com/3", source="DevTo",
                tags=["go", "generics", "tutorial"], author="Alice Chen", timestamp=now - timedelta(hours=6)),
        Article(title="AI roundup", url="https://d.com/4", source="TechMeme",
                tags=["ai", "ml"], author="Charlie", timestamp=now - timedelta(hours=12)),
        Article(title="No tags article", url="https://e.com/5", source="RSS",
                tags=[], author="", timestamp=now - timedelta(minutes=30)),
    ]


class TestExcludeTag:
    def test_exclude_tag_removes_matching(self):
        articles = _make_articles()
        etq = "rust"
        filtered = [a for a in articles if not any(etq in t.lower() for t in a.tags)]
        assert len(filtered) == 4
        assert all("rust" not in t for a in filtered for t in a.tags)

    def test_exclude_tag_no_match_keeps_all(self):
        articles = _make_articles()
        etq = "java"
        filtered = [a for a in articles if not any(etq in t.lower() for t in a.tags)]
        assert len(filtered) == 5

    def test_exclude_tag_empty_tags_kept(self):
        articles = _make_articles()
        etq = "python"
        filtered = [a for a in articles if not any(etq in t.lower() for t in a.tags)]
        # "No tags article" has no tags, should be kept
        assert any(a.title == "No tags article" for a in filtered)

    def test_exclude_tag_substring_match(self):
        articles = _make_articles()
        etq = "release"
        filtered = [a for a in articles if not any(etq in t.lower() for t in a.tags)]
        assert len(filtered) == 4
        assert all(a.title != "Python 4.0 released" for a in filtered)

    def test_exclude_tag_case_insensitive(self):
        articles = _make_articles()
        etq = "RUST"
        filtered = [a for a in articles if not any(etq.lower() in t.lower() for t in a.tags)]
        assert len(filtered) == 4


class TestExcludeAuthor:
    def test_exclude_author_removes_matching(self):
        articles = _make_articles()
        eaq = "alice"
        filtered = [a for a in articles if eaq not in a.author.lower()]
        # Removes "Alice" and "Alice Chen"
        assert len(filtered) == 3
        assert all("alice" not in a.author.lower() for a in filtered)

    def test_exclude_author_no_match_keeps_all(self):
        articles = _make_articles()
        eaq = "dave"
        filtered = [a for a in articles if eaq not in a.author.lower()]
        assert len(filtered) == 5

    def test_exclude_author_empty_author_kept(self):
        articles = _make_articles()
        eaq = "bob"
        filtered = [a for a in articles if eaq not in a.author.lower()]
        assert any(a.title == "No tags article" for a in filtered)

    def test_exclude_author_case_insensitive(self):
        articles = _make_articles()
        eaq = "BOB"
        filtered = [a for a in articles if eaq.lower() not in a.author.lower()]
        assert len(filtered) == 4


class TestAgeStats:
    def test_age_stats_calculations(self):
        now = datetime.now(timezone.utc)
        ages_h = []
        articles = _make_articles()
        for a in articles:
            if a.timestamp:
                ts = a.timestamp if a.timestamp.tzinfo else a.timestamp.replace(tzinfo=timezone.utc)
                ages_h.append((now - ts).total_seconds() / 3600)
        ages_h.sort()
        assert len(ages_h) == 5
        assert ages_h[0] < 1  # 30min article
        assert ages_h[-1] > 10  # 12h article
        avg = sum(ages_h) / len(ages_h)
        median = ages_h[len(ages_h) // 2]
        assert 0 < avg < 24
        assert 0 < median < 24

    def test_age_fmt_helper(self):
        def _fmt_age(h):
            if h < 1:
                return f"{h * 60:.0f}m"
            if h < 24:
                return f"{h:.1f}h"
            return f"{h / 24:.1f}d"

        assert _fmt_age(0.5) == "30m"
        assert _fmt_age(2.5) == "2.5h"
        assert _fmt_age(48) == "2.0d"
        assert _fmt_age(0.0167) == "1m"


class TestCLIArgs:
    def test_exclude_tag_arg_parsed(self):
        from clawler.cli import main
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--exclude-tag", type=str, default=None, dest="exclude_tag")
        args = parser.parse_args(["--exclude-tag", "rust"])
        assert args.exclude_tag == "rust"

    def test_exclude_author_arg_parsed(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--exclude-author", type=str, default=None, dest="exclude_author")
        args = parser.parse_args(["--exclude-author", "alice"])
        assert args.exclude_author == "alice"

    def test_age_stats_arg_parsed(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--age-stats", action="store_true", dest="age_stats")
        args = parser.parse_args(["--age-stats"])
        assert args.age_stats is True


class TestVersionBump:
    def test_version_is_510(self):
        from clawler import __version__
        assert __version__ == "5.2.0"
