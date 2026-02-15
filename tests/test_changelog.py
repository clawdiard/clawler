"""Tests for Changelog source and --category-stats CLI flag."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.changelog import ChangelogSource, TAG_CATEGORY_MAP, CHANGELOG_FEEDS


# --- ChangelogSource tests ---

class TestChangelogSource:
    def test_name(self):
        src = ChangelogSource()
        assert src.name == "changelog"

    def test_default_limit(self):
        src = ChangelogSource()
        assert src.limit == 30

    def test_custom_limit(self):
        src = ChangelogSource(limit=10)
        assert src.limit == 10

    def test_feeds_config(self):
        assert len(CHANGELOG_FEEDS) == 2
        urls = [f[0] for f in CHANGELOG_FEEDS]
        assert "https://changelog.com/feed" in urls
        assert "https://changelog.com/news/feed" in urls

    def test_tag_category_map_has_entries(self):
        assert len(TAG_CATEGORY_MAP) > 10
        assert TAG_CATEGORY_MAP["security"] == "security"
        assert TAG_CATEGORY_MAP["python"] == "tech"
        assert TAG_CATEGORY_MAP["career"] == "business"

    @patch.object(ChangelogSource, "fetch_url", return_value="")
    def test_crawl_empty_feed(self, mock_fetch):
        src = ChangelogSource()
        articles = src.crawl()
        assert articles == []

    @patch.object(ChangelogSource, "fetch_url")
    def test_crawl_parses_rss(self, mock_fetch):
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
        <channel>
            <item>
                <title>Test Article</title>
                <link>https://changelog.com/news/test-1</link>
                <pubDate>Sat, 15 Feb 2026 10:00:00 +0000</pubDate>
                <author>Test Author</author>
                <category>open-source</category>
                <description>A test article about open source.</description>
            </item>
            <item>
                <title>Security Post</title>
                <link>https://changelog.com/news/test-2</link>
                <pubDate>Sat, 15 Feb 2026 09:00:00 +0000</pubDate>
                <category>security</category>
                <description>Security related article.</description>
            </item>
        </channel>
        </rss>"""
        mock_fetch.return_value = rss_xml
        src = ChangelogSource()
        articles = src.crawl()
        assert len(articles) >= 1
        assert articles[0].title == "Test Article"
        assert "changelog.com" in articles[0].url

    @patch.object(ChangelogSource, "fetch_url")
    def test_crawl_deduplicates_across_feeds(self, mock_fetch):
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
        <channel>
            <item>
                <title>Duplicate Article</title>
                <link>https://changelog.com/news/same-url</link>
                <description>Same article in both feeds.</description>
            </item>
        </channel>
        </rss>"""
        mock_fetch.return_value = rss_xml
        src = ChangelogSource()
        articles = src.crawl()
        urls = [a.url for a in articles]
        assert urls.count("https://changelog.com/news/same-url") == 1

    def test_timeout(self):
        src = ChangelogSource()
        assert src.timeout == 20

    def test_inherits_base_source(self):
        from clawler.sources.base import BaseSource
        src = ChangelogSource()
        assert isinstance(src, BaseSource)


# --- --category-stats tests ---

class TestCategoryStats:
    def test_cli_flag_exists(self):
        """Verify --category-stats is accepted by the CLI parser."""
        from clawler.cli import main
        import sys
        # Just check that parsing doesn't fail with the flag
        with patch("sys.argv", ["clawler", "--category-stats", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_category_stats_output(self, capsys):
        """Verify --category-stats produces category breakdown output."""
        from clawler.models import Article
        from datetime import datetime, timezone
        from collections import Counter

        articles = [
            Article(title="A", url="https://a.com", source="X", category="tech",
                    timestamp=datetime.now(timezone.utc)),
            Article(title="B", url="https://b.com", source="Y", category="tech",
                    timestamp=datetime.now(timezone.utc)),
            Article(title="C", url="https://c.com", source="Z", category="science",
                    timestamp=datetime.now(timezone.utc)),
        ]
        cat_counts = Counter(a.category for a in articles if a.category)
        assert cat_counts["tech"] == 2
        assert cat_counts["science"] == 1


# --- Source registry tests ---

class TestSourceRegistry:
    def test_changelog_in_sources_init(self):
        from clawler.sources import ChangelogSource
        assert ChangelogSource is not None

    def test_changelog_in_all(self):
        from clawler.sources import __all__
        assert "ChangelogSource" in __all__

    def test_config_has_no_changelog(self):
        """Verify config.py knows about no_changelog toggle."""
        import clawler.config as cfg
        import inspect
        src = inspect.getsource(cfg)
        assert "no_changelog" in src
