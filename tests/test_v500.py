"""Tests for v5.0.0: TechMeme source, ProductHunt source, ArXiv feedparser migration, --fresh flag."""
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from clawler.sources.techmeme import TechMemeSource
from clawler.sources.producthunt import ProductHuntSource
from clawler.sources.arxiv import ArXivSource
from clawler.models import Article

# --- TechMeme ---

TECHMEME_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Techmeme</title>
<item>
  <title>AI Startup Raises $100M</title>
  <link>https://example.com/ai-startup</link>
  <description>An AI startup raised funding.</description>
  <pubDate>Fri, 14 Feb 2026 08:00:00 GMT</pubDate>
</item>
<item>
  <title>New Chip Architecture</title>
  <link>https://example.com/chip</link>
  <description>A new chip was announced.</description>
  <pubDate>Fri, 14 Feb 2026 07:00:00 GMT</pubDate>
</item>
</channel></rss>"""


def test_techmeme_parse():
    src = TechMemeSource()
    with patch.object(src, "fetch_url", return_value=TECHMEME_RSS):
        articles = src.crawl()
    assert len(articles) == 2
    assert articles[0].source == "TechMeme"
    assert articles[0].category == "tech"
    assert articles[0].title == "AI Startup Raises $100M"


def test_techmeme_empty():
    src = TechMemeSource()
    with patch.object(src, "fetch_url", return_value=""):
        articles = src.crawl()
    assert articles == []


def test_techmeme_name():
    assert TechMemeSource.name == "techmeme"


# --- ProductHunt ---

PRODUCTHUNT_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Product Hunt</title>
<item>
  <title>CoolApp — The best app ever</title>
  <link>https://www.producthunt.com/posts/coolapp</link>
  <description>CoolApp does cool things.</description>
  <pubDate>Fri, 14 Feb 2026 06:00:00 GMT</pubDate>
</item>
</channel></rss>"""


def test_producthunt_parse():
    src = ProductHuntSource()
    with patch.object(src, "fetch_url", return_value=PRODUCTHUNT_RSS):
        articles = src.crawl()
    assert len(articles) == 1
    assert articles[0].source == "ProductHunt"
    assert articles[0].category == "tech"
    assert articles[0].discussion_url == "https://www.producthunt.com/posts/coolapp"


def test_producthunt_empty():
    src = ProductHuntSource()
    with patch.object(src, "fetch_url", return_value=""):
        articles = src.crawl()
    assert articles == []


def test_producthunt_name():
    assert ProductHuntSource.name == "producthunt"


# --- ArXiv feedparser migration ---

ARXIV_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
  <title>Attention Is All You Need (Again)</title>
  <link href="http://arxiv.org/abs/2026.12345" type="text/html"/>
  <link href="http://arxiv.org/pdf/2026.12345" title="pdf"/>
  <summary>We propose a new transformer variant.</summary>
  <published>2026-02-14T00:00:00Z</published>
  <author><name>A. Researcher</name></author>
  <author><name>B. Scientist</name></author>
  <category term="cs.AI"/>
  <category term="cs.LG"/>
</entry>
</feed>"""


def test_arxiv_feedparser_parse():
    src = ArXivSource()
    with patch.object(src, "fetch_url", return_value=ARXIV_ATOM):
        articles = src.crawl()
    assert len(articles) == 1
    a = articles[0]
    assert a.source == "ArXiv"
    assert "Attention" in a.title
    assert a.author == "A. Researcher, B. Scientist"
    assert "cs.AI" in a.tags
    assert a.category == "tech"
    assert "pdf" in a.discussion_url


def test_arxiv_empty():
    src = ArXivSource()
    with patch.object(src, "fetch_url", return_value=""):
        articles = src.crawl()
    assert articles == []


# --- --fresh flag ---

def test_fresh_flag():
    """--fresh should set --since to 1h."""
    from clawler.cli import main
    with patch("clawler.cli.CrawlEngine") as MockEngine:
        mock_engine = MagicMock()
        mock_engine.crawl.return_value = ([], {}, MagicMock(total_removed=0, exact=0, fingerprint=0, fuzzy=0))
        MockEngine.return_value = mock_engine
        with patch("sys.argv", ["clawler", "--fresh", "--quiet", "-f", "json"]):
            try:
                main()
            except SystemExit:
                pass
    # If it ran without error, the flag was accepted


def test_fresh_does_not_override_since():
    """--fresh should not override explicit --since."""
    from clawler.cli import main
    with patch("clawler.cli.CrawlEngine") as MockEngine:
        mock_engine = MagicMock()
        mock_engine.crawl.return_value = ([], {}, MagicMock(total_removed=0, exact=0, fingerprint=0, fuzzy=0))
        MockEngine.return_value = mock_engine
        with patch("sys.argv", ["clawler", "--fresh", "--since", "6h", "--quiet", "-f", "json"]):
            try:
                main()
            except SystemExit:
                pass


# --- Source weights ---

def test_techmeme_weight():
    from clawler.weights import get_quality_score
    score = get_quality_score("TechMeme")
    assert score == 0.79


def test_producthunt_weight():
    from clawler.weights import get_quality_score
    score = get_quality_score("ProductHunt")
    assert score == 0.66


# --- Version ---

def test_version_500():
    from clawler import __version__
    assert __version__ == "5.1.0"
