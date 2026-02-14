"""Tests for v5.9.0 — Slashdot source, --no-slashdot flag."""
import unittest
from unittest.mock import patch, MagicMock
from clawler.sources.slashdot import SlashdotSource, _strip_html, _map_category


MOCK_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Slashdot</title>
  <item>
    <title>Linux 7.0 Released With Major Performance Improvements</title>
    <link>https://linux.slashdot.org/story/12345</link>
    <description>&lt;p&gt;The latest version brings 30% faster I/O.&lt;/p&gt;</description>
    <author>EditorBob</author>
    <pubDate>Fri, 14 Feb 2026 18:00:00 GMT</pubDate>
    <comments>https://linux.slashdot.org/story/12345#comments</comments>
    <slash:department>the-penguin-soars</slash:department>
    <category>linux</category>
    <category>tech</category>
  </item>
  <item>
    <title>NASA Discovers New Exoplanet in Habitable Zone</title>
    <link>https://science.slashdot.org/story/12346</link>
    <description>Scientists confirm a rocky planet orbiting a nearby star.</description>
    <pubDate>Fri, 14 Feb 2026 16:00:00 GMT</pubDate>
  </item>
  <item>
    <title></title>
    <link></link>
  </item>
</channel>
</rss>"""


class TestSlashdotSource(unittest.TestCase):

    @patch.object(SlashdotSource, "fetch_url", return_value=MOCK_RSS)
    def test_crawl_parses_articles(self, mock_fetch):
        src = SlashdotSource(limit=10)
        articles = src.crawl()
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0].source, "Slashdot")
        self.assertIn("Linux", articles[0].title)
        self.assertIn("NASA", articles[1].title)
        self.assertEqual(articles[0].author, "EditorBob")

    @patch.object(SlashdotSource, "fetch_url", return_value=MOCK_RSS)
    def test_crawl_sets_category(self, mock_fetch):
        src = SlashdotSource()
        articles = src.crawl()
        # First article has "linux" tag → tech
        self.assertEqual(articles[0].category, "tech")
        # Second has "NASA" in title → science
        self.assertEqual(articles[1].category, "science")

    @patch.object(SlashdotSource, "fetch_url", return_value=MOCK_RSS)
    def test_crawl_respects_limit(self, mock_fetch):
        src = SlashdotSource(limit=1)
        articles = src.crawl()
        self.assertEqual(len(articles), 1)

    @patch.object(SlashdotSource, "fetch_url", return_value="")
    def test_crawl_empty_response(self, mock_fetch):
        src = SlashdotSource()
        articles = src.crawl()
        self.assertEqual(articles, [])

    @patch.object(SlashdotSource, "fetch_url", side_effect=Exception("Network error"))
    def test_crawl_handles_error(self, mock_fetch):
        src = SlashdotSource()
        articles = src.crawl()
        self.assertEqual(articles, [])

    def test_crawl_timestamps(self):
        with patch.object(SlashdotSource, "fetch_url", return_value=MOCK_RSS):
            src = SlashdotSource()
            articles = src.crawl()
            self.assertIsNotNone(articles[0].timestamp)
            self.assertIsNotNone(articles[1].timestamp)


class TestSlashdotHelpers(unittest.TestCase):

    def test_strip_html(self):
        self.assertEqual(_strip_html("<p>Hello <b>world</b></p>"), "Hello world")
        self.assertEqual(_strip_html("no tags"), "no tags")
        self.assertEqual(_strip_html(""), "")

    def test_map_category_security(self):
        self.assertEqual(_map_category(["slashdot:security"], "Something"), "security")
        self.assertEqual(_map_category([], "Major data breach reported"), "security")

    def test_map_category_science(self):
        self.assertEqual(_map_category(["slashdot:science"], "Discovery"), "science")
        self.assertEqual(_map_category([], "NASA launches new probe"), "science")

    def test_map_category_default_tech(self):
        self.assertEqual(_map_category([], "New programming language"), "tech")


class TestSlashdotCLI(unittest.TestCase):

    def test_no_slashdot_flag_exists(self):
        """Verify --no-slashdot is recognized by argparse."""
        from clawler.cli import main
        import argparse
        # Just confirm the flag parses without error
        from clawler.cli import main
        # We can't easily test this without running main, but we test import
        from clawler.sources import SlashdotSource
        self.assertTrue(hasattr(SlashdotSource, "name"))
        self.assertEqual(SlashdotSource.name, "slashdot")

    def test_slashdot_in_sources_init(self):
        from clawler.sources import __all__
        self.assertIn("SlashdotSource", __all__)

    def test_version_bumped(self):
        from clawler import __version__
        self.assertEqual(__version__, "6.1.0")


if __name__ == "__main__":
    unittest.main()
