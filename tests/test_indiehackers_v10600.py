"""Tests for enhanced Indie Hackers source (v10.60.0)."""
import pytest
from unittest.mock import patch
from clawler.sources.indiehackers import (
    IndieHackersSource,
    _classify_category,
    _extract_tags,
    _quality_from_position,
)


class TestClassifyCategory:
    def test_revenue_is_business(self):
        assert _classify_category("How I hit $10k MRR in 6 months") == "business"

    def test_ai_is_tech(self):
        assert _classify_category("Building an AI-powered tool") == "tech"

    def test_burnout_is_business(self):
        assert _classify_category("Dealing with burnout as a solo founder") == "business"

    def test_community_is_culture(self):
        assert _classify_category("Building a community around lifestyle products") == "culture"

    def test_default_is_business(self):
        assert _classify_category("Random post about something") == "business"


class TestExtractTags:
    def test_always_has_base_tag(self):
        tags = _extract_tags("Hello world")
        assert "indiehackers:startups" in tags

    def test_saas_tag(self):
        tags = _extract_tags("Launching my SaaS product next week")
        assert "ih:saas" in tags
        assert "ih:launch" in tags

    def test_max_tags(self):
        tags = _extract_tags("saas ai no-code bootstrap launch revenue marketing seo remote freelance open source")
        assert len(tags) <= 8


class TestQualityFromPosition:
    def test_first_item(self):
        assert _quality_from_position(0, 20) == 0.9

    def test_middle_item(self):
        q = _quality_from_position(10, 20)
        assert q == 0.6

    def test_last_item(self):
        q = _quality_from_position(19, 20)
        assert q == 0.45

    def test_single_item(self):
        assert _quality_from_position(0, 1) == 0.6


class TestIndieHackersSource:
    def test_init_defaults(self):
        src = IndieHackersSource()
        assert src.include_podcast is True

    def test_name(self):
        assert IndieHackersSource().name == "Indie Hackers"

    def test_crawl_frontpage_empty(self):
        src = IndieHackersSource(include_podcast=False)
        with patch.object(src, "fetch_url", return_value=None):
            articles = src.crawl()
            assert articles == []

    def test_crawl_frontpage_parses_links(self):
        src = IndieHackersSource(include_podcast=False)
        html = """
        <html><body>
            <a href="/post/test-post-1">How I built my SaaS to $5k MRR</a>
            <a href="/post/test-post-2">AI startup launch story</a>
            <a href="/other/not-a-post">Not a post</a>
        </body></html>
        """
        with patch.object(src, "fetch_url", return_value=html):
            articles = src.crawl()
            assert len(articles) == 2
            assert articles[0].url == "https://www.indiehackers.com/post/test-post-1"
            assert "saas" in [t.split(":")[-1] for t in articles[0].tags]

    def test_crawl_skips_short_titles(self):
        src = IndieHackersSource(include_podcast=False)
        html = '<html><body><a href="/post/x">Hi</a></body></html>'
        with patch.object(src, "fetch_url", return_value=html):
            articles = src.crawl()
            assert len(articles) == 0

    def test_crawl_deduplicates_urls(self):
        src = IndieHackersSource(include_podcast=False)
        html = """
        <html><body>
            <a href="/post/same-post">Same Post Title</a>
            <a href="/post/same-post">Same Post Title Again</a>
        </body></html>
        """
        with patch.object(src, "fetch_url", return_value=html):
            articles = src.crawl()
            assert len(articles) == 1

    def test_podcast_disabled(self):
        src = IndieHackersSource(include_podcast=False)
        html = '<html><body><a href="/post/test">Test Post Title Here</a></body></html>'
        with patch.object(src, "fetch_url", return_value=html):
            articles = src.crawl()
            # Should not include podcast episodes
            assert all("Podcast" not in a.source for a in articles)
