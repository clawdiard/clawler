"""Tests for InfoQ source (v9.5.0)."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.infoq import InfoQSource, _detect_category, INFOQ_FEEDS

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>InfoQ</title>
<item>
<title><![CDATA[Building Resilient Microservices with Service Mesh]]></title>
<link>https://www.infoq.com/articles/resilient-microservices-service-mesh</link>
<description><![CDATA[An overview of how service mesh architectures improve reliability in distributed systems.]]></description>
<pubDate>Mon, 16 Feb 2026 10:00:00 GMT</pubDate>
<category><![CDATA[Architecture]]></category>
<category><![CDATA[Microservices]]></category>
<author>Jane Doe</author>
</item>
<item>
<title><![CDATA[LLM Fine-Tuning Best Practices for Enterprise]]></title>
<link>https://www.infoq.com/articles/llm-fine-tuning-enterprise</link>
<description><![CDATA[Practical guide to fine-tuning large language models for business applications.]]></description>
<pubDate>Sun, 15 Feb 2026 14:30:00 GMT</pubDate>
<category><![CDATA[AI]]></category>
</item>
<item>
<title><![CDATA[Zero-Day Vulnerability in Popular Framework]]></title>
<link>https://www.infoq.com/news/zero-day-framework</link>
<description><![CDATA[A critical zero-day vulnerability has been discovered affecting millions of applications.]]></description>
<pubDate>Sat, 14 Feb 2026 09:00:00 GMT</pubDate>
</item>
</channel>
</rss>"""


@pytest.fixture
def source():
    return InfoQSource(feeds=[{"url": "https://feed.infoq.com/", "topic": "all"}])


def _mock_fetch(source, xml=SAMPLE_RSS):
    source.fetch_url = MagicMock(return_value=xml)
    return source


class TestInfoQSource:
    def test_crawl_basic(self, source):
        _mock_fetch(source)
        articles = source.crawl()
        assert len(articles) == 3

    def test_article_fields(self, source):
        _mock_fetch(source)
        articles = source.crawl()
        a = articles[0]
        assert a.title == "Building Resilient Microservices with Service Mesh"
        assert a.url == "https://www.infoq.com/articles/resilient-microservices-service-mesh"
        assert "service mesh" in a.summary.lower()
        assert a.timestamp is not None

    def test_author_tag(self, source):
        _mock_fetch(source)
        articles = source.crawl()
        assert "infoq:author:Jane Doe" in articles[0].tags

    def test_category_tags(self, source):
        _mock_fetch(source)
        articles = source.crawl()
        assert "infoq:tag:architecture" in articles[0].tags
        assert "infoq:tag:microservices" in articles[0].tags

    def test_topic_tag(self, source):
        _mock_fetch(source)
        articles = source.crawl()
        assert "infoq:topic:all" in articles[0].tags

    def test_ai_category_detection(self, source):
        _mock_fetch(source)
        articles = source.crawl()
        # LLM article should be detected as AI
        llm_article = [a for a in articles if "LLM" in a.title][0]
        assert llm_article.category == "ai"

    def test_security_category_detection(self, source):
        _mock_fetch(source)
        articles = source.crawl()
        sec_article = [a for a in articles if "Zero-Day" in a.title][0]
        assert sec_article.category == "security"

    def test_dedup_across_feeds(self):
        src = InfoQSource(feeds=[
            {"url": "https://feed.infoq.com/", "topic": "all"},
            {"url": "https://feed.infoq.com/ai", "topic": "ai"},
        ])
        src.fetch_url = MagicMock(return_value=SAMPLE_RSS)
        articles = src.crawl()
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls)), "Duplicate URLs found"

    def test_topic_filter(self):
        src = InfoQSource(topics=["ai", "devops"])
        assert all(f["topic"] in ("ai", "devops") for f in src.feeds)

    def test_limit(self):
        src = InfoQSource(
            feeds=[{"url": "https://feed.infoq.com/", "topic": "all"}],
            limit=1,
        )
        _mock_fetch(src)
        articles = src.crawl()
        assert len(articles) == 1

    def test_empty_feed(self, source):
        source.fetch_url = MagicMock(return_value="")
        articles = source.crawl()
        assert articles == []

    def test_malformed_xml(self, source):
        source.fetch_url = MagicMock(return_value="<rss><channel><item><title>No link</title></item></channel></rss>")
        articles = source.crawl()
        assert articles == []

    def test_default_feeds(self):
        assert len(INFOQ_FEEDS) >= 5

    def test_detect_category_keywords(self):
        assert _detect_category("Deep Learning in Production", "", "all") == "ai"
        assert _detect_category("New CVE Vulnerability Found", "", "all") == "security"
        assert _detect_category("Agile Leadership Tips", "", "all") == "business"

    def test_source_label_topic(self):
        src = InfoQSource(feeds=[{"url": "https://feed.infoq.com/ai", "topic": "ai"}])
        _mock_fetch(src, SAMPLE_RSS)
        articles = src.crawl()
        assert articles[0].source == "InfoQ (ai)"

    def test_source_label_all(self, source):
        _mock_fetch(source)
        articles = source.crawl()
        assert articles[0].source == "InfoQ"


class TestInfoQInAPI:
    def test_infoq_in_init(self):
        from clawler.sources import InfoQSource as IS
        assert IS is not None

    def test_infoq_in_all(self):
        from clawler.sources import __all__
        assert "InfoQSource" in __all__
