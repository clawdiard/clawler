"""Tests for TechCrunch source."""
from unittest.mock import patch
from clawler.sources.techcrunch import TechCrunchSource, _detect_category

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
  <title>TechCrunch</title>
  <item>
    <title>OpenAI raises $10B in Series C funding</title>
    <link>https://techcrunch.com/2026/02/17/openai-raises-10b/</link>
    <description>OpenAI announced a massive funding round.</description>
    <pubDate>Mon, 17 Feb 2026 12:00:00 +0000</pubDate>
    <dc:creator>Sarah Perez</dc:creator>
    <category>AI</category>
    <category>Startups</category>
  </item>
  <item>
    <title>New gaming laptop review</title>
    <link>https://techcrunch.com/2026/02/17/gaming-laptop/</link>
    <description>A look at the latest hardware.</description>
    <pubDate>Mon, 17 Feb 2026 10:00:00 +0000</pubDate>
    <dc:creator>Brian Heater</dc:creator>
  </item>
</channel>
</rss>"""


class TestTechCrunchSource:
    def test_parse_articles(self):
        src = TechCrunchSource(feeds=["main"])
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].title == "OpenAI raises $10B in Series C funding"
        assert articles[0].author == "Sarah Perez"
        assert articles[0].source == "TechCrunch"
        assert articles[0].timestamp is not None

    def test_dedup_within_feed(self):
        doubled = SAMPLE_RSS.replace("</channel>", """
  <item>
    <title>OpenAI raises $10B in Series C funding</title>
    <link>https://techcrunch.com/2026/02/17/openai-raises-10b/</link>
    <description>Duplicate.</description>
    <pubDate>Mon, 17 Feb 2026 12:00:00 +0000</pubDate>
  </item>
</channel>""")
        src = TechCrunchSource(feeds=["main"])
        with patch.object(src, "fetch_url", return_value=doubled):
            articles = src.crawl()
        assert len(articles) == 2

    def test_category_detection_ai(self):
        assert _detect_category("GPT-5 launches today", "", "main") == "ai"

    def test_category_detection_business(self):
        assert _detect_category("Startup raises $50M", "", "main") == "business"

    def test_section_category(self):
        assert _detect_category("Some article", "", "security") == "security"

    def test_tags_include_rss_categories(self):
        src = TechCrunchSource(feeds=["main"])
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        tags = articles[0].tags
        assert "tc:ai" in tags
        assert "tc:startups" in tags

    def test_empty_feed(self):
        src = TechCrunchSource(feeds=["main"])
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []
