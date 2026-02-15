"""Tests for ArXiv source."""
from unittest.mock import patch
from clawler.sources.arxiv import ArXivSource

SAMPLE_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title>ArXiv Query Results</title>
  <entry>
    <title>Attention Is All You Need (Again)</title>
    <link href="http://arxiv.org/abs/2602.12345v1" rel="alternate" type="text/html"/>
    <link href="http://arxiv.org/pdf/2602.12345v1" rel="related" title="pdf" type="application/pdf"/>
    <summary>We propose a new transformer architecture that achieves state-of-the-art results on multiple benchmarks.</summary>
    <published>2026-02-15T00:00:00Z</published>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <author><name>Charlie Brown</name></author>
    <author><name>Diana Prince</name></author>
    <arxiv:primary_category term="cs.AI"/>
    <category term="cs.AI"/>
    <category term="cs.LG"/>
  </entry>
  <entry>
    <title>Quantum Computing for Breakfast</title>
    <link href="http://arxiv.org/abs/2602.99999v1" rel="alternate" type="text/html"/>
    <summary>A practical guide to quantum algorithms.</summary>
    <published>2026-02-14T00:00:00Z</published>
    <author><name>Eve Quantum</name></author>
    <category term="quant-ph"/>
  </entry>
</feed>"""


def test_arxiv_crawl():
    """Test ArXiv source parses Atom feed correctly."""
    src = ArXivSource(categories=["cs.AI"], limit=10)
    with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
        articles = src.crawl()

    assert len(articles) == 2
    assert articles[0].title == "Attention Is All You Need (Again)"
    assert articles[0].source == "ArXiv"
    assert "arxiv.org/abs" in articles[0].url
    assert articles[0].timestamp is not None
    # Author truncation (3 shown + 1 more)
    assert "+1 more" in articles[0].author
    # Tags from categories
    assert "cs.AI" in articles[0].tags


def test_arxiv_category_mapping():
    """Test category mapping for different ArXiv categories."""
    src = ArXivSource()
    assert src._map_category(["cs.AI", "cs.LG"]) == "tech"
    assert src._map_category(["quant-ph"]) == "science"
    assert src._map_category(["math.AG"]) == "science"
    assert src._map_category(["econ.GN"]) == "science"


def test_arxiv_empty_response():
    """Test ArXiv handles empty response."""
    src = ArXivSource()
    with patch.object(src, "fetch_url", return_value=""):
        articles = src.crawl()
    assert articles == []
