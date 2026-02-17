"""Tests for v4.9.0: ArXiv source."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.arxiv import ArXivSource, DEFAULT_CATEGORIES

SAMPLE_ARXIV_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Attention Is All You Need (Again)</title>
    <link href="http://arxiv.org/abs/2602.12345v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2602.12345v1" rel="related" type="application/pdf"/>
    <summary>We propose a novel transformer variant that improves efficiency by 40 percent on standard benchmarks.</summary>
    <published>2026-02-14T00:00:00Z</published>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <category term="cs.AI"/>
    <category term="cs.LG"/>
  </entry>
  <entry>
    <title>Quantum Speedup for Graph Problems</title>
    <link href="http://arxiv.org/abs/2602.12346v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2602.12346v1" rel="related" type="application/pdf"/>
    <summary>A short summary of quantum graph algorithms.</summary>
    <published>2026-02-13T12:00:00Z</published>
    <author><name>Carol White</name></author>
    <author><name>Dan Black</name></author>
    <author><name>Eve Green</name></author>
    <author><name>Frank Red</name></author>
    <category term="quant-ph"/>
  </entry>
  <entry>
    <title></title>
    <link href="http://arxiv.org/abs/2602.99999v1"/>
    <summary>No title entry should be skipped.</summary>
    <published>2026-02-12T00:00:00Z</published>
    <category term="cs.SE"/>
  </entry>
</feed>"""


def test_arxiv_source_init():
    src = ArXivSource()
    assert src.name == "arxiv"
    assert src.categories == DEFAULT_CATEGORIES
    assert src.limit == 25


def test_arxiv_source_custom_init():
    src = ArXivSource(categories=["math.CO"], limit=10)
    assert src.categories == ["math.CO"]
    assert src.limit == 10


def test_arxiv_parse_feed():
    src = ArXivSource()
    articles = src._parse_feed(SAMPLE_ARXIV_ATOM)
    # Empty-title entry should be skipped
    assert len(articles) == 2

    a1 = articles[0]
    assert "Attention" in a1.title
    assert a1.url == "http://arxiv.org/abs/2602.12345v1"
    assert a1.source == "ArXiv"
    assert a1.category == "ai"
    assert a1.author == "Alice Smith, Bob Jones"
    assert a1.discussion_url == "http://arxiv.org/pdf/2602.12345v1"
    assert "cs.AI" in a1.tags
    assert a1.timestamp is not None

    a2 = articles[1]
    assert "Quantum" in a2.title
    assert a2.category == "science"
    # 4 authors, show first 3 + count
    assert "+1 more" in a2.author


def test_arxiv_parse_empty():
    src = ArXivSource()
    assert src._parse_feed("") == []
    assert src._parse_feed("<feed></feed>") == []


def test_arxiv_crawl_returns_articles():
    src = ArXivSource(limit=5)
    with patch.object(src, "fetch_url", return_value=SAMPLE_ARXIV_ATOM):
        articles = src.crawl()
        assert len(articles) == 2


def test_arxiv_crawl_fetch_failure():
    src = ArXivSource()
    with patch.object(src, "fetch_url", return_value=""):
        assert src.crawl() == []


def test_arxiv_category_mapping():
    assert ArXivSource._map_category(["cs.AI", "cs.LG"]) == "ai"
    assert ArXivSource._map_category(["cs.SE"]) == "tech"
    assert ArXivSource._map_category(["quant-ph"]) == "science"
    assert ArXivSource._map_category(["math.CO"]) == "science"
    assert ArXivSource._map_category(["q-bio.GN"]) == "health"
    assert ArXivSource._map_category(["econ.GN"]) == "science"  # fallback


def test_arxiv_long_summary_truncated():
    src = ArXivSource()
    long_abstract = "A" * 500
    xml = f"""<feed><entry>
        <title>Long Paper</title>
        <link href="http://arxiv.org/abs/1234"/>
        <summary>{long_abstract}</summary>
        <published>2026-01-01T00:00:00Z</published>
        <category term="cs.AI"/>
    </entry></feed>"""
    articles = src._parse_feed(xml)
    assert len(articles) == 1
    assert len(articles[0].summary) <= 303  # 300 + "..."


def test_arxiv_in_sources_init():
    from clawler.sources import ArXivSource as ImportedArXiv
    assert ImportedArXiv is not None


def test_arxiv_source_list_entry():
    """ArXiv should appear in the source weight config."""
    from clawler.weights import get_quality_score
    score = get_quality_score("ArXiv")
    assert score > 0.5
