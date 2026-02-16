"""Tests for AllTop source."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.alltop import AllTopSource, _extract_description

SAMPLE_HTML = '''
<a  class="one-line-ellipsis" style="color: #222222" href="https://example.com/article1" target="_blank" tabindex="0" data-toggle="popover" data-html="true" data-placement="auto" data-content="&lt;a style=&quot;font-weight: bold;&quot; href=&quot;https://example.com/article1&quot;&gt;Test Article One [example.com]&lt;/a&gt;&lt;br&gt;This is the description of article one.&lt;div class=&quot;read-article&quot;&gt;&lt;p&gt;&lt;a href=&quot;https://example.com/article1&quot;&gt;[ Read Article ]&lt;/a&gt;&lt;/p&gt;&lt;/div&gt;">Test Article One </a>
<a  class="one-line-ellipsis" style="color: #222222" href="https://other.com/article2" target="_blank" tabindex="0" data-toggle="popover" data-html="true" data-placement="auto" data-content="&lt;a href=&quot;https://other.com/article2&quot;&gt;Second Article [other.com]&lt;/a&gt;&lt;br&gt;Description two.&lt;div class=&quot;read-article&quot;&gt;&lt;p&gt;&lt;a href=&quot;https://other.com/article2&quot;&gt;[ Read Article ]&lt;/a&gt;&lt;/p&gt;&lt;/div&gt;">Second Article </a>
<a  class="one-line-ellipsis" style="color: #222222" href="https://example.com/article1" target="_blank" tabindex="0" data-toggle="popover" data-html="true" data-placement="auto" data-content="Duplicate">Duplicate Title </a>
'''


class TestAllTopSource:
    def test_defaults(self):
        src = AllTopSource()
        assert src.name == "alltop"
        assert len(src.topics) == 7
        assert src.limit_per_topic == 10

    def test_custom_topics(self):
        src = AllTopSource(topics=["gaming", "music"], limit_per_topic=5)
        assert src.topics == ["gaming", "music"]
        assert src.limit_per_topic == 5

    @patch.object(AllTopSource, "fetch_url")
    def test_crawl_parses_html(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_HTML
        src = AllTopSource(topics=["tech"], limit_per_topic=10)
        articles = src.crawl()

        assert len(articles) == 2  # third is duplicate URL
        assert articles[0].title == "Test Article One"
        assert articles[0].url == "https://example.com/article1"
        assert "alltop:tech" in articles[0].tags
        assert articles[0].category == "tech"
        assert articles[1].title == "Second Article"
        assert articles[1].url == "https://other.com/article2"

    @patch.object(AllTopSource, "fetch_url")
    def test_dedup_across_topics(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_HTML
        src = AllTopSource(topics=["tech", "science"], limit_per_topic=10)
        articles = src.crawl()
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))

    @patch.object(AllTopSource, "fetch_url")
    def test_max_total_limit(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_HTML
        src = AllTopSource(topics=["tech"], max_total=1)
        articles = src.crawl()
        assert len(articles) <= 1

    @patch.object(AllTopSource, "fetch_url")
    def test_handles_fetch_error(self, mock_fetch):
        mock_fetch.side_effect = Exception("Network error")
        src = AllTopSource(topics=["tech"])
        articles = src.crawl()
        assert articles == []

    @patch.object(AllTopSource, "fetch_url")
    def test_empty_html(self, mock_fetch):
        mock_fetch.return_value = "<html></html>"
        src = AllTopSource(topics=["tech"])
        articles = src.crawl()
        assert articles == []

    def test_category_mapping(self):
        src = AllTopSource(topics=["gaming"])
        assert "gaming" in src.topics

    @patch.object(AllTopSource, "fetch_url")
    def test_source_extraction(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_HTML
        src = AllTopSource(topics=["tech"])
        articles = src.crawl()
        assert "example.com" in articles[0].source

    @patch.object(AllTopSource, "fetch_url")
    def test_limit_per_topic(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_HTML
        src = AllTopSource(topics=["tech"], limit_per_topic=1)
        articles = src.crawl()
        assert len(articles) == 1


class TestExtractDescription:
    def test_basic(self):
        raw = "&lt;a&gt;Title [site.com]&lt;/a&gt;&lt;br&gt;Hello world.&lt;div&gt;[ Read Article ]&lt;/div&gt;"
        from html import unescape
        # _extract_description expects already-unescaped from data-content after unescape
        result = _extract_description(unescape(raw))
        assert "Hello world" in result
        assert "Read Article" not in result

    def test_empty(self):
        assert _extract_description("") == ""
        assert _extract_description(None) == ""

    def test_truncation(self):
        long_text = "A" * 500
        result = _extract_description(long_text)
        assert len(result) <= 300
