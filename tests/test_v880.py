"""Tests for Wired and The Verge sources + v8.8.0 integration."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.wired import WiredSource, WIRED_FEEDS, SECTION_CATEGORY_MAP
from clawler.sources.theverge import TheVergeSource, _detect_category
from clawler import __version__
from pathlib import Path

# --- Wired ---

SAMPLE_WIRED_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>Wired</title>
<item>
  <title>AI Is Changing Everything</title>
  <link>https://www.wired.com/story/ai-changing-everything/</link>
  <description>&lt;p&gt;A deep look at artificial intelligence trends.&lt;/p&gt;</description>
  <pubDate>Mon, 16 Feb 2026 06:00:00 +0000</pubDate>
  <dc:creator>Jane Doe</dc:creator>
  <category>AI</category>
</item>
<item>
  <title>The Future of Quantum Computing</title>
  <link>https://www.wired.com/story/quantum-computing-future/</link>
  <description>Quantum computers are getting closer to practical use.</description>
  <pubDate>Sun, 15 Feb 2026 12:00:00 +0000</pubDate>
  <dc:creator>John Smith</dc:creator>
</item>
</channel>
</rss>"""


class TestWiredSource:
    def test_init_defaults(self):
        src = WiredSource()
        assert src.name == "wired"
        assert src._feeds == ["main", "science", "security"]
        assert src.limit == 20

    def test_init_custom_feeds(self):
        src = WiredSource(feeds=["main", "gear", "nonexistent"])
        assert src._feeds == ["main", "gear"]

    def test_feed_config(self):
        assert "main" in WIRED_FEEDS
        assert "science" in WIRED_FEEDS
        assert "security" in WIRED_FEEDS
        assert len(WIRED_FEEDS) >= 6

    def test_category_mapping(self):
        assert SECTION_CATEGORY_MAP["science"] == "science"
        assert SECTION_CATEGORY_MAP["security"] == "security"
        assert SECTION_CATEGORY_MAP["business"] == "business"

    @patch.object(WiredSource, "fetch_url")
    def test_crawl_parses_rss(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_WIRED_RSS
        src = WiredSource(feeds=["main"])
        articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].title == "AI Is Changing Everything"
        assert articles[0].source == "Wired (main)"
        assert articles[0].author == "Jane Doe"
        assert "wired:ai" in [t.lower() for t in articles[0].tags]
        assert articles[1].url == "https://www.wired.com/story/quantum-computing-future/"

    @patch.object(WiredSource, "fetch_url")
    def test_crawl_dedup_across_sections(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_WIRED_RSS
        src = WiredSource(feeds=["main", "science"])
        articles = src.crawl()
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))  # no duplicates

    @patch.object(WiredSource, "fetch_url")
    def test_crawl_empty_feed(self, mock_fetch):
        mock_fetch.return_value = ""
        src = WiredSource(feeds=["main"])
        articles = src.crawl()
        assert articles == []


# --- The Verge ---

SAMPLE_VERGE_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>The Verge</title>
<entry>
  <title>Apple Launches New MacBook</title>
  <link rel="alternate" href="https://www.theverge.com/2026/2/16/apple-macbook"/>
  <summary>Apple announced a new MacBook with M5 chip.</summary>
  <published>2026-02-16T05:00:00Z</published>
  <author><name>Nilay Patel</name></author>
  <category term="Apple"/>
  <category term="Laptops"/>
</entry>
<entry>
  <title>NASA Discovers New Exoplanet</title>
  <link rel="alternate" href="https://www.theverge.com/2026/2/15/nasa-exoplanet"/>
  <summary>A potentially habitable exoplanet was detected by the James Webb telescope.</summary>
  <published>2026-02-15T18:00:00Z</published>
  <author><name>Loren Grush</name></author>
  <category term="Science"/>
  <category term="Space"/>
</entry>
</feed>"""


class TestTheVergeSource:
    def test_init(self):
        src = TheVergeSource()
        assert src.name == "theverge"
        assert src.limit == 25

    @patch.object(TheVergeSource, "fetch_url")
    def test_crawl_parses_atom(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_VERGE_ATOM
        src = TheVergeSource()
        articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].title == "Apple Launches New MacBook"
        assert articles[0].source == "The Verge"
        assert articles[0].author == "Nilay Patel"
        assert "verge:apple" in articles[0].tags
        assert articles[1].url == "https://www.theverge.com/2026/2/15/nasa-exoplanet"

    @patch.object(TheVergeSource, "fetch_url")
    def test_crawl_empty(self, mock_fetch):
        mock_fetch.return_value = ""
        src = TheVergeSource()
        assert src.crawl() == []

    def test_detect_category_ai(self):
        assert _detect_category("OpenAI launches GPT-5", []) == "ai"

    def test_detect_category_science(self):
        assert _detect_category("NASA finds water on Mars", []) == "science"

    def test_detect_category_gaming(self):
        assert _detect_category("Nintendo announces new console", []) == "gaming"

    def test_detect_category_default(self):
        assert _detect_category("Some tech news", []) == "tech"


# --- Version sync ---

class TestV880:
    def test_version(self):
        assert __version__ == "8.8.0"

    def test_version_sync_pyproject(self):
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        assert f'version = "{__version__}"' in pyproject.read_text()

    def test_version_sync_setup(self):
        setup = Path(__file__).parent.parent / "setup.py"
        assert f'version="{__version__}"' in setup.read_text()

    def test_source_imports(self):
        from clawler.sources import WiredSource, TheVergeSource
        assert WiredSource.name == "wired"
        assert TheVergeSource.name == "theverge"

    def test_engine_imports(self):
        from clawler.engine import CrawlEngine
        # Should import without error
        assert CrawlEngine is not None

    def test_wired_weights(self):
        from clawler.weights import get_quality_score
        score = get_quality_score("Wired (main)")
        assert score >= 0.5

    def test_verge_weights(self):
        from clawler.weights import get_quality_score
        score = get_quality_score("The Verge")
        assert score >= 0.5
