"""Tests for v8.0.0 — Substack source integration."""
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from clawler.sources.substack import SubstackSource, SUBSTACK_FEEDS
from clawler.models import Article


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Test Newsletter</title>
    <item>
      <title>Understanding AI Alignment</title>
      <link>https://test.substack.com/p/understanding-ai-alignment</link>
      <description>&lt;p&gt;A deep dive into the challenges of aligning artificial intelligence.&lt;/p&gt;</description>
      <dc:creator>Test Author</dc:creator>
      <pubDate>Sat, 15 Feb 2026 12:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Weekly Roundup</title>
      <link>https://test.substack.com/p/weekly-roundup</link>
      <description>This week in tech and AI</description>
      <pubDate>Fri, 14 Feb 2026 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title></title>
      <link></link>
    </item>
  </channel>
</rss>"""


class TestSubstackSource(unittest.TestCase):

    def test_source_name(self):
        src = SubstackSource()
        self.assertEqual(src.name, "Substack")

    def test_default_feeds(self):
        src = SubstackSource()
        self.assertEqual(len(src.feeds), len(SUBSTACK_FEEDS))
        self.assertGreaterEqual(len(src.feeds), 20)

    def test_feeds_have_required_keys(self):
        for feed in SUBSTACK_FEEDS:
            self.assertIn("slug", feed)
            self.assertIn("source", feed)
            self.assertIn("category", feed)

    @patch.object(SubstackSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_parse_articles(self, mock_fetch):
        src = SubstackSource(feeds=[{"slug": "test", "source": "Test", "category": "tech"}])
        articles = src.crawl()
        # 2 valid items (3rd has empty title/link)
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0].title, "Understanding AI Alignment")
        self.assertIn("substack.com", articles[0].url)
        self.assertEqual(articles[0].category, "tech")

    @patch.object(SubstackSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_author_in_summary(self, mock_fetch):
        src = SubstackSource(feeds=[{"slug": "test", "source": "Test", "category": "tech"}])
        articles = src.crawl()
        self.assertIn("Test Author", articles[0].summary)

    @patch.object(SubstackSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_timestamp_parsed(self, mock_fetch):
        src = SubstackSource(feeds=[{"slug": "test", "source": "Test", "category": "tech"}])
        articles = src.crawl()
        self.assertIsNotNone(articles[0].timestamp)
        self.assertEqual(articles[0].timestamp.year, 2026)

    @patch.object(SubstackSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_html_stripped_from_description(self, mock_fetch):
        src = SubstackSource(feeds=[{"slug": "test", "source": "Test", "category": "tech"}])
        articles = src.crawl()
        self.assertNotIn("<p>", articles[0].summary)
        self.assertNotIn("</p>", articles[0].summary)

    @patch.object(SubstackSource, "fetch_url", return_value="")
    def test_empty_response(self, mock_fetch):
        src = SubstackSource(feeds=[{"slug": "test", "source": "Test", "category": "tech"}])
        articles = src.crawl()
        self.assertEqual(articles, [])

    @patch.object(SubstackSource, "fetch_url", return_value="not xml")
    def test_invalid_xml(self, mock_fetch):
        src = SubstackSource(feeds=[{"slug": "test", "source": "Test", "category": "tech"}])
        articles = src.crawl()
        self.assertEqual(articles, [])

    @patch.object(SubstackSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_max_per_feed(self, mock_fetch):
        src = SubstackSource(
            feeds=[{"slug": "test", "source": "Test", "category": "tech"}],
            max_per_feed=1,
        )
        articles = src.crawl()
        self.assertEqual(len(articles), 1)

    @patch.object(SubstackSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_source_label(self, mock_fetch):
        src = SubstackSource(feeds=[{"slug": "test", "source": "Cool Newsletter", "category": "tech"}])
        articles = src.crawl()
        self.assertEqual(articles[0].source, "Substack (Cool Newsletter)")

    def test_custom_feeds(self):
        custom = [{"slug": "custom", "source": "Custom", "category": "science"}]
        src = SubstackSource(feeds=custom)
        self.assertEqual(len(src.feeds), 1)

    @patch.object(SubstackSource, "fetch_url", side_effect=Exception("network error"))
    def test_crawl_handles_exception(self, mock_fetch):
        src = SubstackSource(feeds=[{"slug": "test", "source": "Test", "category": "tech"}])
        articles = src.crawl()
        self.assertEqual(articles, [])

    def test_feed_slugs_unique(self):
        slugs = [f["slug"] for f in SUBSTACK_FEEDS]
        self.assertEqual(len(slugs), len(set(slugs)))


class TestSubstackWeights(unittest.TestCase):

    def test_substack_in_weights(self):
        from clawler.weights import get_quality_score
        score = get_quality_score("Substack")
        self.assertGreater(score, 0.0)

    def test_named_substack_weight(self):
        from clawler.weights import get_quality_score
        score = get_quality_score("Substack (Stratechery)")
        self.assertGreaterEqual(score, 0.75)


class TestSubstackInEngine(unittest.TestCase):

    def test_substack_importable(self):
        from clawler.sources import SubstackSource
        self.assertTrue(callable(SubstackSource))

    def test_substack_in_all_exports(self):
        from clawler import sources
        self.assertIn("SubstackSource", sources.__all__)


class TestSubstackAPI(unittest.TestCase):

    def test_no_substack_param_exists(self):
        import inspect
        from clawler.api import crawl
        sig = inspect.signature(crawl)
        self.assertIn("no_substack", sig.parameters)


if __name__ == "__main__":
    unittest.main()
