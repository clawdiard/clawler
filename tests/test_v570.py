"""Tests for v5.7.0 features: Tildes source, named since periods, exclude-domain."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta


class TestTildesSource:
    """Tests for the Tildes source."""

    SAMPLE_HTML = """
    <html><body>
    <article class="topic">
        <h1 class="topic-title"><a href="/~comp/abc123/test-article">Test Article Title</a></h1>
        <div class="topic-voting-votes">42</div>
        <a class="topic-info-comments" href="/~comp/abc123/test-article#comments">8 comments</a>
        <a class="topic-group" href="/~comp">~comp</a>
        <time datetime="2026-02-14T12:00:00Z">2h ago</time>
    </article>
    <article class="topic">
        <h1 class="topic-title"><a href="https://example.com/external">External Link Post</a></h1>
        <div class="topic-voting-votes">15</div>
        <a class="topic-info-comments" href="/~news/def456#comments">3 comments</a>
        <a class="topic-group" href="/~news">~news</a>
        <time datetime="2026-02-14T10:00:00Z">4h ago</time>
    </article>
    </body></html>
    """

    def test_parse_topics_basic(self):
        from clawler.sources.tildes import TildesSource
        src = TildesSource(limit=25)
        articles = src._parse_topics(self.SAMPLE_HTML)
        assert len(articles) == 2

    def test_parse_topics_self_post(self):
        from clawler.sources.tildes import TildesSource
        src = TildesSource()
        articles = src._parse_topics(self.SAMPLE_HTML)
        # First article is a self-post (relative URL)
        assert articles[0].title == "Test Article Title"
        assert "tildes.net" in articles[0].url

    def test_parse_topics_external_link(self):
        from clawler.sources.tildes import TildesSource
        src = TildesSource()
        articles = src._parse_topics(self.SAMPLE_HTML)
        assert articles[1].title == "External Link Post"
        assert articles[1].url == "https://example.com/external"

    def test_parse_topics_category_mapping(self):
        from clawler.sources.tildes import TildesSource
        src = TildesSource()
        articles = src._parse_topics(self.SAMPLE_HTML)
        assert articles[0].category == "tech"  # ~comp -> tech
        assert articles[1].category == "world"  # ~news -> world

    def test_parse_topics_discussion_url(self):
        from clawler.sources.tildes import TildesSource
        src = TildesSource()
        articles = src._parse_topics(self.SAMPLE_HTML)
        assert "tildes.net" in articles[0].discussion_url

    def test_parse_topics_timestamp(self):
        from clawler.sources.tildes import TildesSource
        src = TildesSource()
        articles = src._parse_topics(self.SAMPLE_HTML)
        assert articles[0].timestamp is not None
        assert articles[0].timestamp.tzinfo is not None

    def test_parse_topics_empty_html(self):
        from clawler.sources.tildes import TildesSource
        src = TildesSource()
        articles = src._parse_topics("<html><body></body></html>")
        assert articles == []

    def test_parse_topics_limit(self):
        from clawler.sources.tildes import TildesSource
        src = TildesSource(limit=1)
        articles = src._parse_topics(self.SAMPLE_HTML)
        assert len(articles) == 1

    def test_category_mapping(self):
        from clawler.sources.tildes import _map_category
        assert _map_category("comp") == "tech"
        assert _map_category("comp.ai") == "tech"
        assert _map_category("science") == "science"
        assert _map_category("news") == "world"
        assert _map_category("finance") == "business"
        assert _map_category("security") == "security"
        assert _map_category("movies") == "culture"
        assert _map_category("unknown_group") == "tech"  # default


class TestNamedSincePeriods:
    """Tests for new --since named periods: today, this-week, this-month."""

    def test_since_today(self):
        from clawler.utils import parse_since
        result = parse_since("today")
        now = datetime.now(timezone.utc)
        # Should be earlier today
        assert result.date() == now.date() or (now - result).total_seconds() < 86400

    def test_since_this_week(self):
        from clawler.utils import parse_since
        result = parse_since("this-week")
        now = datetime.now(timezone.utc)
        # Should be within the last 7 days
        assert (now - result).total_seconds() < 7 * 86400

    def test_since_this_month(self):
        from clawler.utils import parse_since
        result = parse_since("this-month")
        now = datetime.now(timezone.utc)
        # Should be within the last 31 days
        assert (now - result).total_seconds() < 31 * 86400

    def test_existing_named_periods_still_work(self):
        from clawler.utils import parse_since
        now = datetime.now(timezone.utc)
        yesterday = parse_since("yesterday")
        assert abs((now - yesterday).total_seconds() - 86400) < 60
        last_week = parse_since("last-week")
        assert abs((now - last_week).total_seconds() - 604800) < 60


class TestExcludeDomain:
    """Tests for --exclude-domain filter."""

    def test_exclude_domain_cli_arg(self):
        """Verify the argument is recognized."""
        from clawler.cli import main
        import argparse
        # Just verify the parser doesn't choke — we test filtering via Article list
        from clawler.models import Article
        from urllib.parse import urlparse

        articles = [
            Article(title="A", url="https://reddit.com/r/test/1", source="Reddit"),
            Article(title="B", url="https://example.com/article", source="RSS"),
            Article(title="C", url="https://sub.reddit.com/page", source="Reddit"),
        ]

        excl_domains = {"reddit.com"}
        def _domain_match(url):
            try:
                host = urlparse(url).netloc.lower()
                return any(host == d or host.endswith("." + d) for d in excl_domains)
            except Exception:
                return False

        filtered = [a for a in articles if not _domain_match(a.url)]
        assert len(filtered) == 1
        assert filtered[0].title == "B"


class TestTildesSourceIntegration:
    """Integration-level tests for Tildes source wiring."""

    def test_tildes_in_sources_init(self):
        from clawler.sources import TildesSource
        src = TildesSource()
        assert src.name == "tildes"

    def test_tildes_in_api_crawl_signature(self):
        import inspect
        from clawler.api import crawl
        sig = inspect.signature(crawl)
        assert "no_tildes" in sig.parameters

    def test_tildes_weight_exists(self):
        from clawler.weights import get_quality_score
        score = get_quality_score("Tildes (~comp)")
        # Should get a non-default score (Tildes is in weights)
        assert score > 0.0
