"""Tests for TechMeme v10.4.0 enhancements: category detection, quality scoring, tags."""
from unittest.mock import patch, MagicMock
from clawler.sources.techmeme import TechMemeSource, _detect_category


class TestDetectCategory:
    def test_security_keywords(self):
        assert _detect_category("Major data breach at company", "") == "security"
        assert _detect_category("New ransomware strain hits hospitals", "") == "security"

    def test_business_keywords(self):
        assert _detect_category("Startup raises $50M in Series B", "") == "business"
        assert _detect_category("FTC launches antitrust probe", "") == "business"

    def test_science_keywords(self):
        assert _detect_category("NASA launches new telescope", "") == "science"
        assert _detect_category("Study finds quantum effect", "") == "science"

    def test_world_keywords(self):
        # "EU proposes new AI regulation" matches both 'ai' and 'world'; ai wins
        # because specific categories get a boost. Use a non-AI world headline.
        assert _detect_category("EU summit addresses trade policy", "") == "world"

    def test_culture_keywords(self):
        assert _detect_category("Netflix launches new original series", "") == "culture"

    def test_default_tech(self):
        assert _detect_category("New programming language released", "") == "tech"
        assert _detect_category("", "") == "tech"


class TestTechMemeEnhancements:
    def _make_feed_xml(self, title="Test Article", link="https://example.com/article",
                       summary="A test summary", pub_date="Mon, 17 Feb 2026 04:00:00 GMT",
                       entry_id="https://techmeme.com/260217/p1"):
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>TechMeme</title>
    <item>
      <title>{title}</title>
      <link>{link}</link>
      <description>{summary}</description>
      <pubDate>{pub_date}</pubDate>
      <guid>{entry_id}</guid>
    </item>
  </channel>
</rss>"""

    @patch.object(TechMemeSource, "fetch_url")
    def test_category_detection_in_crawl(self, mock_fetch):
        mock_fetch.return_value = self._make_feed_xml(
            title="Major data breach exposes millions of users"
        )
        src = TechMemeSource()
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].category == "security"

    @patch.object(TechMemeSource, "fetch_url")
    def test_quality_score_applied(self, mock_fetch):
        mock_fetch.return_value = self._make_feed_xml()
        src = TechMemeSource()
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].quality_score > 0

    @patch.object(TechMemeSource, "fetch_url")
    def test_tags_extracted(self, mock_fetch):
        mock_fetch.return_value = self._make_feed_xml(
            title="OpenAI releases new GPT model for enterprise AI"
        )
        src = TechMemeSource()
        articles = src.crawl()
        assert "ai" in articles[0].tags

    @patch.object(TechMemeSource, "fetch_url")
    def test_discussion_url_from_entry_id(self, mock_fetch):
        mock_fetch.return_value = self._make_feed_xml(
            entry_id="https://techmeme.com/260217/p1"
        )
        src = TechMemeSource()
        articles = src.crawl()
        assert articles[0].discussion_url == "https://techmeme.com/260217/p1"

    @patch.object(TechMemeSource, "fetch_url")
    def test_empty_feed(self, mock_fetch):
        mock_fetch.return_value = ""
        src = TechMemeSource()
        assert src.crawl() == []


class TestSubstackQualityScore:
    @patch.object(__import__("clawler.sources.substack", fromlist=["SubstackSource"]).SubstackSource, "fetch_url")
    def test_quality_score_applied(self, mock_fetch):
        from clawler.sources.substack import SubstackSource
        mock_fetch.return_value = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <item>
      <title>Test Post</title>
      <link>https://astralcodexten.substack.com/p/test</link>
      <description>A test post</description>
      <pubDate>Mon, 17 Feb 2026 04:00:00 GMT</pubDate>
      <dc:creator>Scott Alexander</dc:creator>
    </item>
  </channel>
</rss>"""
        src = SubstackSource(feeds=[{"slug": "astralcodexten", "source": "Astral Codex Ten", "category": "tech"}])
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].quality_score > 0
        assert articles[0].author == "Scott Alexander"


class TestEngineDefaultSources:
    def test_engine_default_has_all_sources(self):
        from clawler.engine import CrawlEngine
        engine = CrawlEngine()
        # Should have all 42+ sources, not just the old default of 3
        assert len(engine.sources) >= 40
        source_names = {s.name for s in engine.sources}
        assert "techmeme" in source_names
        assert "Substack" in source_names
        assert "BBC News" in source_names or "bbc" in source_names
