"""Tests for Quanta Magazine source."""
import unittest
from unittest.mock import patch, MagicMock
from clawler.sources.quantamagazine import QuantaMagazineSource
from clawler.registry import SOURCES


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Quanta Magazine</title>
<item>
  <title>New Proof Settles Long-Standing Conjecture</title>
  <link>https://www.quantamagazine.org/new-proof-conjecture-20260218/</link>
  <description>Mathematicians have found an elegant proof for a decades-old problem.</description>
  <pubDate>Tue, 18 Feb 2026 12:00:00 +0000</pubDate>
  <author>Jane Smith</author>
  <category>Mathematics</category>
</item>
<item>
  <title>Quantum Computing Breakthrough Uses Topological Qubits</title>
  <link>https://www.quantamagazine.org/quantum-topological-20260217/</link>
  <description>A new approach to error correction brings fault-tolerant quantum computers closer.</description>
  <pubDate>Mon, 17 Feb 2026 14:00:00 +0000</pubDate>
  <category>Computer Science</category>
</item>
<item>
  <title>How Cells Remember Their Identity</title>
  <link>https://www.quantamagazine.org/cell-identity-20260216/</link>
  <description>Biologists uncover the epigenetic mechanisms that lock in cell fate.</description>
  <pubDate>Sun, 16 Feb 2026 10:00:00 +0000</pubDate>
  <category>Biology</category>
</item>
</channel>
</rss>"""


class TestQuantaMagazineSource(unittest.TestCase):
    def setUp(self):
        self.source = QuantaMagazineSource()

    @patch.object(QuantaMagazineSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_crawl_returns_articles(self, mock_fetch):
        articles = self.source.crawl()
        self.assertEqual(len(articles), 3)
        self.assertEqual(articles[0].title, "New Proof Settles Long-Standing Conjecture")
        self.assertEqual(articles[0].source, "Quanta Magazine")
        self.assertIn("mathematicians", articles[0].summary.lower())

    @patch.object(QuantaMagazineSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_categories_mapped(self, mock_fetch):
        articles = self.source.crawl()
        # Mathematics -> science
        self.assertEqual(articles[0].category, "science")
        # Computer Science -> tech
        self.assertEqual(articles[1].category, "tech")

    @patch.object(QuantaMagazineSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_quality_score_high(self, mock_fetch):
        articles = self.source.crawl()
        for a in articles:
            self.assertEqual(a.quality_score, 0.85)

    @patch.object(QuantaMagazineSource, "fetch_url", return_value="")
    def test_empty_response(self, mock_fetch):
        articles = self.source.crawl()
        self.assertEqual(articles, [])

    @patch.object(QuantaMagazineSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_timestamps_parsed(self, mock_fetch):
        articles = self.source.crawl()
        for a in articles:
            self.assertIsNotNone(a.timestamp)


class TestRegistryIncludesQuanta(unittest.TestCase):
    def test_quanta_in_registry(self):
        keys = [s.key for s in SOURCES]
        self.assertIn("quantamagazine", keys)

    def test_total_sources_52(self):
        self.assertEqual(len(SOURCES), 73)


if __name__ == "__main__":
    unittest.main()
