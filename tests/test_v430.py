"""Tests for v4.3.0 features: Wikipedia Current Events source, version sync fix."""
import unittest
from unittest.mock import patch, MagicMock
from clawler import __version__
from clawler.sources.wikipedia import WikipediaCurrentEventsSource, _map_category


SAMPLE_HTML = """
<html><body>
<div class="current-events-content">
<b>Armed conflicts and attacks</b>
<li>A <a href="/wiki/Example">major event</a> occurs in the region, reported by
<a href="https://reuters.com/article/123">Reuters</a> and other outlets.</li>
<b>Science and technology</b>
<li>Scientists announce a <a href="https://nature.com/article/456">breakthrough in quantum computing</a>
that could revolutionize the field of cryptography.</li>
<b>Business and economy</b>
<li>The stock market reaches an <a href="https://bloomberg.com/news/789">all-time high</a>
driven by tech earnings reports this quarter.</li>
</div>
</body></html>
"""


class TestWikipediaSource(unittest.TestCase):
    """Test Wikipedia Current Events source."""

    @patch.object(WikipediaCurrentEventsSource, "fetch_url", return_value=SAMPLE_HTML)
    def test_crawl_extracts_articles(self, mock_fetch):
        src = WikipediaCurrentEventsSource()
        articles = src.crawl()
        self.assertGreaterEqual(len(articles), 2)
        # All articles should have valid URLs
        for a in articles:
            self.assertTrue(a.url.startswith("http"))
            self.assertTrue(len(a.title) > 10)
            self.assertEqual(a.source, "Wikipedia Current Events")
            self.assertIn("wikipedia", a.tags)

    @patch.object(WikipediaCurrentEventsSource, "fetch_url", return_value="")
    def test_crawl_handles_empty(self, mock_fetch):
        src = WikipediaCurrentEventsSource()
        articles = src.crawl()
        self.assertEqual(articles, [])

    @patch.object(WikipediaCurrentEventsSource, "fetch_url", return_value="<html><body>no events</body></html>")
    def test_crawl_handles_no_events(self, mock_fetch):
        src = WikipediaCurrentEventsSource()
        articles = src.crawl()
        self.assertEqual(articles, [])

    def test_source_name(self):
        src = WikipediaCurrentEventsSource()
        self.assertEqual(src.name, "wikipedia")

    @patch.object(WikipediaCurrentEventsSource, "fetch_url", return_value=SAMPLE_HTML)
    def test_dedup_within_source(self, mock_fetch):
        """Same URL should not appear twice."""
        src = WikipediaCurrentEventsSource()
        articles = src.crawl()
        urls = [a.url for a in articles]
        self.assertEqual(len(urls), len(set(urls)))

    @patch.object(WikipediaCurrentEventsSource, "fetch_url", return_value=SAMPLE_HTML)
    def test_categories_assigned(self, mock_fetch):
        src = WikipediaCurrentEventsSource()
        articles = src.crawl()
        categories = {a.category for a in articles}
        # At least one non-general category should be assigned
        self.assertTrue(len(categories) >= 1)

    @patch.object(WikipediaCurrentEventsSource, "fetch_url", return_value=SAMPLE_HTML)
    def test_quality_score(self, mock_fetch):
        src = WikipediaCurrentEventsSource()
        articles = src.crawl()
        for a in articles:
            self.assertEqual(a.quality_score, 0.80)


class TestCategoryMapping(unittest.TestCase):
    """Test Wikipedia category heading mapping."""

    def test_armed_conflicts(self):
        self.assertEqual(_map_category("armed conflicts and attacks"), "world")

    def test_science(self):
        self.assertEqual(_map_category("science and technology"), "science")

    def test_business(self):
        self.assertEqual(_map_category("business and economy"), "business")

    def test_sports(self):
        self.assertEqual(_map_category("sports"), "culture")

    def test_unknown(self):
        self.assertEqual(_map_category("something else entirely"), "world")

    def test_politics(self):
        self.assertEqual(_map_category("politics and elections"), "world")

    def test_disasters(self):
        self.assertEqual(_map_category("disasters and accidents"), "science")


class TestVersionSync(unittest.TestCase):
    def test_version_is_430(self):
        self.assertEqual(__version__, "5.0.0")


if __name__ == "__main__":
    unittest.main()
