"""Tests for Engadget source."""
from unittest.mock import patch
from clawler.sources.engadget import EngadgetSource, _detect_category

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
  <title>Engadget</title>
  <item>
    <title>PlayStation 6 specs leaked ahead of announcement</title>
    <link>https://www.engadget.com/gaming/playstation-6-specs/</link>
    <description>Sony's next console details emerge.</description>
    <pubDate>Mon, 17 Feb 2026 14:00:00 +0000</pubDate>
    <dc:creator>Kris Holt</dc:creator>
    <category>Gaming</category>
  </item>
  <item>
    <title>Best noise-canceling headphones of 2026</title>
    <link>https://www.engadget.com/audio/best-headphones-2026/</link>
    <description>Our top picks for this year.</description>
    <pubDate>Mon, 17 Feb 2026 10:00:00 +0000</pubDate>
    <dc:creator>Billy Steele</dc:creator>
  </item>
</channel>
</rss>"""


class TestEngadgetSource:
    def test_parse_articles(self):
        src = EngadgetSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].source == "Engadget (Main)"
        assert articles[0].author == "Kris Holt"
        assert articles[0].timestamp is not None

    def test_category_gaming(self):
        assert _detect_category("PlayStation 6 revealed", "") == "gaming"

    def test_category_ai(self):
        assert _detect_category("New AI chatbot launches", "") == "ai"

    def test_category_default(self):
        assert _detect_category("Best laptops", "") == "tech"

    def test_dedup(self):
        doubled = SAMPLE_RSS.replace("</channel>", """
  <item>
    <title>PlayStation 6 specs leaked ahead of announcement</title>
    <link>https://www.engadget.com/gaming/playstation-6-specs/</link>
    <description>Dup.</description>
    <pubDate>Mon, 17 Feb 2026 14:00:00 +0000</pubDate>
  </item>
</channel>""")
        src = EngadgetSource()
        with patch.object(src, "fetch_url", return_value=doubled):
            articles = src.crawl()
        assert len(articles) == 2

    def test_empty_feed(self):
        src = EngadgetSource()
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []

    def test_tags(self):
        src = EngadgetSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        assert "engadget:gaming" in articles[0].tags
