"""Tests for TechMeme source v10.6.0 enhancements."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.techmeme import (
    TechMemeSource,
    _detect_category,
    _extract_publication,
    _count_related_links,
    _compute_quality,
    _fmt_count,
)


# --- Unit tests for helper functions ---

class TestDetectCategory:
    def test_ai_keywords(self):
        assert _detect_category("OpenAI launches new LLM", "") == "ai"

    def test_security_keywords(self):
        assert _detect_category("Major data breach at company", "") == "security"

    def test_crypto_keywords(self):
        assert _detect_category("Bitcoin hits new high", "") == "crypto"

    def test_business_keywords(self):
        assert _detect_category("Startup raises $500M in Series B funding", "") == "business"

    def test_health_keywords(self):
        assert _detect_category("FDA approves new drug for patients", "") == "health"

    def test_world_keywords(self):
        assert _detect_category("EU sanctions on China trade war", "") == "world"

    def test_design_keywords(self):
        assert _detect_category("Figma announces new UX features", "") == "design"

    def test_gaming_keywords(self):
        assert _detect_category("Nintendo announces new gaming console", "") == "gaming"

    def test_default_tech(self):
        assert _detect_category("Some random tech thing", "") == "tech"

    def test_specific_preferred_over_generic(self):
        # "OpenAI chatgpt" has ai keywords; even with a business keyword, ai wins (specific boost)
        cat = _detect_category("OpenAI ChatGPT revenue soars", "")
        assert cat == "ai"


class TestExtractPublication:
    def test_known_domain(self):
        assert _extract_publication("https://www.nytimes.com/2026/article") == "NYT"

    def test_known_domain_verge(self):
        assert _extract_publication("https://www.theverge.com/story") == "The Verge"

    def test_unknown_domain(self):
        pub = _extract_publication("https://www.coolsite.com/article")
        assert pub == "Coolsite"

    def test_empty_url(self):
        assert _extract_publication("") == ""

    def test_bbc_couk(self):
        assert _extract_publication("https://www.bbc.co.uk/news/tech") == "BBC"


class TestCountRelatedLinks:
    def test_no_summary(self):
        assert _count_related_links("") == 0

    def test_single_link(self):
        html = '<a href="https://example.com/story">Story</a>'
        assert _count_related_links(html) == 0  # minus 1 for main link

    def test_multiple_links(self):
        html = (
            '<a href="https://example.com/main">Main</a> '
            '<a href="https://other.com/a">A</a> '
            '<a href="https://third.com/b">B</a>'
        )
        assert _count_related_links(html) == 2

    def test_no_links(self):
        assert _count_related_links("Just plain text with no links") == 0


class TestComputeQuality:
    def test_zero_related(self):
        assert _compute_quality(0) == 0.5

    def test_some_related(self):
        q = _compute_quality(5)
        assert 0.5 < q < 0.9

    def test_many_related(self):
        q = _compute_quality(20)
        assert q > 0.8

    def test_never_exceeds_one(self):
        assert _compute_quality(1000) <= 1.0


class TestFmtCount:
    def test_small(self):
        assert _fmt_count(42) == "42"

    def test_thousands(self):
        assert _fmt_count(1500) == "1.5K"

    def test_millions(self):
        assert _fmt_count(2_300_000) == "2.3M"


# --- Integration tests for TechMemeSource.crawl ---

SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Techmeme</title>
<item>
  <title>OpenAI launches GPT-5 with breakthrough reasoning</title>
  <link>https://www.theverge.com/openai-gpt5</link>
  <guid>https://www.techmeme.com/260217/p1</guid>
  <pubDate>Mon, 17 Feb 2026 06:00:00 GMT</pubDate>
  <description>&lt;a href="https://theverge.com/openai-gpt5"&gt;The Verge&lt;/a&gt; reports. Also: &lt;a href="https://nytimes.com/ai"&gt;NYT&lt;/a&gt;, &lt;a href="https://wired.com/gpt5"&gt;Wired&lt;/a&gt;</description>
</item>
<item>
  <title>Major ransomware breach hits hospitals</title>
  <link>https://www.bbc.co.uk/news/ransomware</link>
  <guid>https://www.bbc.co.uk/news/ransomware</guid>
  <pubDate>Mon, 17 Feb 2026 05:00:00 GMT</pubDate>
  <description>Hospitals across Europe affected.</description>
</item>
<item>
  <title>Boring generic update</title>
  <link>https://www.example.com/boring</link>
  <guid>https://www.example.com/boring</guid>
  <pubDate>Mon, 17 Feb 2026 04:00:00 GMT</pubDate>
  <description>Nothing special here.</description>
</item>
</channel>
</rss>"""


class TestTechMemeSourceCrawl:
    def _make_source(self, **config):
        src = TechMemeSource.__new__(TechMemeSource)
        src.config = config
        src.timeout = 15
        return src

    @patch.object(TechMemeSource, "fetch_url", return_value=SAMPLE_FEED)
    def test_basic_crawl(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        assert len(articles) == 3

    @patch.object(TechMemeSource, "fetch_url", return_value=SAMPLE_FEED)
    def test_category_detection(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        cats = {a.title[:10]: a.category for a in articles}
        assert cats["OpenAI lau"] == "ai"
        assert cats["Major rans"] == "security"

    @patch.object(TechMemeSource, "fetch_url", return_value=SAMPLE_FEED)
    def test_publication_extraction(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        ai_article = [a for a in articles if "OpenAI" in a.title][0]
        assert any("techmeme:source:the-verge" in t for t in ai_article.tags)

    @patch.object(TechMemeSource, "fetch_url", return_value=SAMPLE_FEED)
    def test_related_count_in_summary(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        ai_article = [a for a in articles if "OpenAI" in a.title][0]
        assert "sources discussing" in ai_article.summary

    @patch.object(TechMemeSource, "fetch_url", return_value=SAMPLE_FEED)
    def test_quality_scoring(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        ai_article = [a for a in articles if "OpenAI" in a.title][0]
        boring = [a for a in articles if "Boring" in a.title][0]
        assert ai_article.quality_score > boring.quality_score

    @patch.object(TechMemeSource, "fetch_url", return_value=SAMPLE_FEED)
    def test_discussion_url(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        ai_article = [a for a in articles if "OpenAI" in a.title][0]
        assert ai_article.discussion_url == "https://www.techmeme.com/260217/p1"

    @patch.object(TechMemeSource, "fetch_url", return_value=SAMPLE_FEED)
    def test_min_quality_filter(self, mock_fetch):
        src = self._make_source(min_quality=0.6)
        articles = src.crawl()
        assert all(a.quality_score >= 0.6 for a in articles)

    @patch.object(TechMemeSource, "fetch_url", return_value=SAMPLE_FEED)
    def test_category_filter(self, mock_fetch):
        src = self._make_source(category_filter=["ai"])
        articles = src.crawl()
        assert all(a.category == "ai" for a in articles)
        assert len(articles) == 1

    @patch.object(TechMemeSource, "fetch_url", return_value=SAMPLE_FEED)
    def test_global_limit(self, mock_fetch):
        src = self._make_source(global_limit=1)
        articles = src.crawl()
        assert len(articles) == 1

    @patch.object(TechMemeSource, "fetch_url", return_value=SAMPLE_FEED)
    def test_sorted_by_quality(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        scores = [a.quality_score for a in articles]
        assert scores == sorted(scores, reverse=True)

    @patch.object(TechMemeSource, "fetch_url", return_value=SAMPLE_FEED)
    def test_provenance_tags(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        for a in articles:
            assert any(t.startswith("techmeme:category:") for t in a.tags)

    @patch.object(TechMemeSource, "fetch_url", return_value=SAMPLE_FEED)
    def test_topic_tags(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        ai_article = [a for a in articles if "OpenAI" in a.title][0]
        assert any("techmeme:topic:ai" in t for t in ai_article.tags)

    @patch.object(TechMemeSource, "fetch_url", return_value="")
    def test_empty_feed(self, mock_fetch):
        src = self._make_source()
        assert src.crawl() == []

    @patch.object(TechMemeSource, "fetch_url", return_value=SAMPLE_FEED)
    def test_deduplication(self, mock_fetch):
        src = self._make_source()
        articles = src.crawl()
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))
