"""Tests for v6.7.0: Hashnode source."""
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from clawler.sources.hashnode import HashnodeSource, HASHNODE_FEEDS, _TOPIC_TAGS


class TestHashnodeSource(unittest.TestCase):
    """Tests for the Hashnode dev blog source."""

    def test_source_name(self):
        src = HashnodeSource()
        self.assertEqual(src.name, "hashnode")

    def test_default_limit(self):
        src = HashnodeSource()
        self.assertEqual(src.limit, 30)

    def test_custom_limit(self):
        src = HashnodeSource(limit=10)
        self.assertEqual(src.limit, 10)

    def test_feeds_defined(self):
        self.assertGreaterEqual(len(HASHNODE_FEEDS), 5)

    def test_feeds_have_url_and_name(self):
        for url, name in HASHNODE_FEEDS:
            self.assertTrue(url.startswith("https://"), f"Bad URL: {url}")
            self.assertTrue(len(name) > 0, "Empty feed name")

    def test_topic_tags_mapping(self):
        self.assertIn("javascript", _TOPIC_TAGS)
        self.assertIn("ai", _TOPIC_TAGS)
        self.assertIn("python", _TOPIC_TAGS)

    @patch.object(HashnodeSource, "fetch_url")
    def test_crawl_empty_response(self, mock_fetch):
        mock_fetch.return_value = ""
        src = HashnodeSource()
        articles = src.crawl()
        self.assertEqual(articles, [])

    @patch.object(HashnodeSource, "fetch_url")
    def test_crawl_valid_rss(self, mock_fetch):
        mock_fetch.return_value = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
        <channel>
        <title>Hashnode</title>
        <item>
          <title>Building APIs with FastAPI</title>
          <link>https://blog.example.com/fastapi-guide</link>
          <author>devwriter</author>
          <pubDate>Sat, 15 Feb 2026 04:00:00 GMT</pubDate>
          <description>A comprehensive guide to FastAPI</description>
        </item>
        <item>
          <title>React Hooks Deep Dive</title>
          <link>https://blog.example.com/react-hooks</link>
          <author>jsdev</author>
          <pubDate>Sat, 15 Feb 2026 03:00:00 GMT</pubDate>
          <description>Everything about React hooks</description>
        </item>
        </channel>
        </rss>"""
        src = HashnodeSource(limit=50)
        articles = src.crawl()
        # Should get articles from each feed (but deduped by URL)
        self.assertGreater(len(articles), 0)
        art = articles[0]
        self.assertEqual(art.title, "Building APIs with FastAPI")
        self.assertEqual(art.category, "tech")
        self.assertIn("hashnode:devblog", art.tags)

    @patch.object(HashnodeSource, "fetch_url")
    def test_crawl_deduplicates_urls(self, mock_fetch):
        rss = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel><title>H</title>
        <item><title>Same Article</title><link>https://example.com/same</link></item>
        </channel></rss>"""
        mock_fetch.return_value = rss
        src = HashnodeSource(limit=50)
        articles = src.crawl()
        urls = [a.url for a in articles]
        self.assertEqual(len(urls), len(set(urls)), "Duplicate URLs found")

    @patch.object(HashnodeSource, "fetch_url")
    def test_crawl_skips_missing_title(self, mock_fetch):
        mock_fetch.return_value = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel><title>H</title>
        <item><title></title><link>https://example.com/no-title</link></item>
        <item><title>Good Title</title><link>https://example.com/good</link></item>
        </channel></rss>"""
        src = HashnodeSource()
        articles = src.crawl()
        titles = [a.title for a in articles]
        self.assertNotIn("", titles)

    @patch.object(HashnodeSource, "fetch_url")
    def test_crawl_skips_missing_url(self, mock_fetch):
        mock_fetch.return_value = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel><title>H</title>
        <item><title>No URL Article</title><link></link></item>
        </channel></rss>"""
        src = HashnodeSource()
        articles = src.crawl()
        self.assertEqual(len(articles), 0)

    @patch.object(HashnodeSource, "fetch_url")
    def test_crawl_truncates_long_summary(self, mock_fetch):
        long_summary = "A" * 500
        mock_fetch.return_value = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel><title>H</title>
        <item><title>Long Post</title><link>https://example.com/long</link>
        <description>{long_summary}</description></item>
        </channel></rss>"""
        src = HashnodeSource()
        articles = src.crawl()
        if articles:
            self.assertLessEqual(len(articles[0].summary), 300)

    @patch.object(HashnodeSource, "fetch_url")
    def test_ai_feed_tags(self, mock_fetch):
        mock_fetch.side_effect = lambda url, **kw: (
            """<?xml version="1.0" encoding="UTF-8"?>
            <rss version="2.0"><channel><title>H</title>
            <item><title>AI Post</title><link>https://example.com/ai-post</link></item>
            </channel></rss>""" if "/ai/" in url else ""
        )
        src = HashnodeSource()
        articles = src.crawl()
        ai_articles = [a for a in articles if "hashnode:ai" in a.tags]
        self.assertGreater(len(ai_articles), 0)

    def test_inherits_base_source(self):
        from clawler.sources.base import BaseSource
        self.assertTrue(issubclass(HashnodeSource, BaseSource))

    def test_source_in_registry(self):
        from clawler.sources import HashnodeSource as HS
        self.assertIsNotNone(HS)

    @patch.object(HashnodeSource, "fetch_url")
    def test_crawl_exception_resilience(self, mock_fetch):
        mock_fetch.side_effect = Exception("Network error")
        src = HashnodeSource()
        articles = src.crawl()
        self.assertEqual(articles, [])

    def test_source_weight_exists(self):
        from clawler.weights import get_quality_score
        score = get_quality_score("Hashnode")
        self.assertGreater(score, 0.5)
        self.assertLessEqual(score, 1.0)

    def test_source_weight_featured(self):
        from clawler.weights import get_quality_score
        score = get_quality_score("Hashnode Featured")
        self.assertGreaterEqual(score, 0.6)

    @patch.object(HashnodeSource, "fetch_url")
    def test_author_extracted(self, mock_fetch):
        mock_fetch.return_value = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel><title>H</title>
        <item><title>Test</title><link>https://example.com/t</link>
        <author>testauthor</author></item>
        </channel></rss>"""
        src = HashnodeSource()
        articles = src.crawl()
        if articles:
            self.assertEqual(articles[0].author, "testauthor")

    def test_version_bumped(self):
        from clawler import __version__
        self.assertTrue(__version__ >= "6.0.0")


if __name__ == "__main__":
    unittest.main()
