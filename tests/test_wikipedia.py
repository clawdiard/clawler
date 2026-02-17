"""Tests for Wikipedia Current Events source."""
from unittest.mock import patch
from clawler.sources.wikipedia import WikipediaCurrentEventsSource, _map_category

SAMPLE_PORTAL_HTML = """
<html><body>
<div class="current-events">
<ul>
  <li>The <a href="/wiki/Test_Event" title="Test Event">Test Event</a> takes place in <a href="/wiki/Paris">Paris</a>, affecting climate policy worldwide.</li>
  <li><a href="/wiki/AI_Breakthrough" title="AI Breakthrough">AI Breakthrough</a> — researchers announce a major artificial intelligence advance.</li>
</ul>
</div>
</body></html>
"""


def test_wikipedia_source_name():
    src = WikipediaCurrentEventsSource()
    assert src.name in ("wikipedia", "Wikipedia Current Events")


def test_map_category_tech():
    assert _map_category("New artificial intelligence model released") == "tech"


def test_map_category_environment():
    assert _map_category("Major earthquake strikes region") == "environment"


def test_map_category_default():
    assert _map_category("something unrelated happened") == "world"


def test_map_category_business():
    assert _map_category("Stock market crashes amid inflation fears") == "business"


def test_map_category_science():
    assert _map_category("NASA launches new space telescope") == "science"


def test_wikipedia_empty_fetch():
    src = WikipediaCurrentEventsSource()
    with patch.object(src, "fetch_url", return_value=""):
        articles = src.crawl()
    assert articles == []


def test_wikipedia_none_fetch():
    src = WikipediaCurrentEventsSource()
    with patch.object(src, "fetch_url", return_value=None):
        articles = src.crawl()
    assert articles == []
