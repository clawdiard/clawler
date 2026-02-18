"""Tests for Politico source."""
from unittest.mock import patch
from clawler.sources.politico import PoliticoSource

MOCK_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Politico - Politics</title>
  <item>
    <title>New AI Regulation Bill Advances in Congress</title>
    <link>https://www.politico.com/news/2026/02/18/ai-regulation-bill</link>
    <description>Lawmakers push new framework for artificial intelligence oversight.</description>
    <pubDate>Wed, 18 Feb 2026 10:00:00 GMT</pubDate>
    <author>Jane Reporter</author>
  </item>
  <item>
    <title>Defense Budget Talks Stall</title>
    <link>https://www.politico.com/news/2026/02/18/defense-budget</link>
    <description>Congressional leaders remain divided on military spending.</description>
    <pubDate>Wed, 18 Feb 2026 09:00:00 GMT</pubDate>
  </item>
</channel>
</rss>"""


class TestPoliticoSource:
    def test_crawl_parses_articles(self):
        src = PoliticoSource(sections=["politics"], limit=5)
        with patch.object(src, "fetch_url", return_value=MOCK_RSS):
            articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].title == "New AI Regulation Bill Advances in Congress"
        assert articles[0].source == "Politico (Politics)"
        # AI keyword should refine to tech
        assert articles[0].category == "tech"
        assert "politico:politics" in articles[0].tags

    def test_empty_feed(self):
        src = PoliticoSource()
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []

    def test_section_filter(self):
        src = PoliticoSource(sections=["economy"], limit=5)
        with patch.object(src, "fetch_url", return_value=MOCK_RSS):
            articles = src.crawl()
        # Only "economy" feed processed; articles get economy source label
        for a in articles:
            assert a.source == "Politico (Economy)"
"""Tests for Al Jazeera source."""
from unittest.mock import patch
from clawler.sources.aljazeera import AlJazeeraSource

MOCK_AJ_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Al Jazeera</title>
  <item>
    <title>Climate summit reaches landmark agreement</title>
    <link>https://www.aljazeera.com/news/2026/2/18/climate-summit</link>
    <description>World leaders agree on new climate research targets.</description>
    <pubDate>Wed, 18 Feb 2026 12:00:00 GMT</pubDate>
    <author>AJ Correspondent</author>
  </item>
  <item>
    <title>Peace talks resume in conflict zone</title>
    <link>https://www.aljazeera.com/news/2026/2/18/peace-talks</link>
    <description>Diplomatic efforts continue amid military tensions.</description>
    <pubDate>Wed, 18 Feb 2026 11:00:00 GMT</pubDate>
  </item>
</channel>
</rss>"""


class TestAlJazeeraSource:
    def test_crawl_parses_articles(self):
        src = AlJazeeraSource(limit=10)
        with patch.object(src, "fetch_url", return_value=MOCK_AJ_RSS):
            articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].title == "Climate summit reaches landmark agreement"
        assert articles[0].source == "Al Jazeera"
        assert articles[0].category == "science"  # "climate" keyword
        assert "aljazeera" in articles[0].tags

    def test_military_categorized_as_security(self):
        src = AlJazeeraSource(limit=10)
        with patch.object(src, "fetch_url", return_value=MOCK_AJ_RSS):
            articles = src.crawl()
        assert articles[1].category == "security"  # "military" keyword

    def test_empty_feed(self):
        src = AlJazeeraSource()
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []
