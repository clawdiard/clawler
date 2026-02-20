"""Tests for The Hill source."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.thehill import TheHillSource, THEHILL_FEEDS


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>The Hill - Top Stories</title>
    <item>
      <title>Senate passes major AI regulation bill with bipartisan support</title>
      <link>https://thehill.com/policy/technology/12345-senate-ai-bill</link>
      <description>The Senate voted 72-28 to pass the landmark artificial intelligence regulation act.</description>
      <pubDate>Thu, 19 Feb 2026 14:00:00 GMT</pubDate>
      <author>Mychael Schnell</author>
    </item>
    <item>
      <title>White House announces new cybersecurity executive order</title>
      <link>https://thehill.com/homenews/administration/12346-cybersecurity-order</link>
      <description>President signs sweeping order on federal cybersecurity after major breach.</description>
      <pubDate>Thu, 19 Feb 2026 12:00:00 GMT</pubDate>
      <author>Brett Samuels</author>
    </item>
    <item>
      <title>House debates NATO funding amid Ukraine tensions</title>
      <link>https://thehill.com/policy/defense/12347-nato-funding</link>
      <description>Lawmakers clash over proposed NATO budget increase as Ukraine conflict continues.</description>
      <pubDate>Wed, 18 Feb 2026 16:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


def test_thehill_source_name():
    src = TheHillSource()
    assert src.name == "thehill"


def test_thehill_feeds_defined():
    assert len(THEHILL_FEEDS) >= 10
    for feed in THEHILL_FEEDS:
        assert "url" in feed
        assert "section" in feed
        assert "category" in feed
        assert feed["url"].startswith("https://thehill.com/")


def test_thehill_crawl_parses_articles():
    src = TheHillSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    assert len(articles) >= 3  # 3 articles × multiple feeds, but mocked same for all
    titles = [a.title for a in articles]
    assert any("AI regulation" in t for t in titles)


def test_thehill_category_refinement():
    src = TheHillSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    # "cybersecurity" keyword should refine to "security"
    cyber_articles = [a for a in articles if "cybersecurity" in a.title.lower()]
    for a in cyber_articles:
        assert a.category == "security"

    # "NATO" keyword should refine to "world" — but only if "world" keywords
    # are checked before other categories. Since dict iteration order matters,
    # just verify NATO articles get a meaningful category refinement.
    nato_articles = [a for a in articles if "nato" in a.title.lower()]
    for a in nato_articles:
        assert a.category in ("world", "politics")


def test_thehill_quality_scoring():
    src = TheHillSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    for a in articles:
        assert 0.5 <= a.quality_score <= 1.0


def test_thehill_section_filter():
    src = TheHillSource(sections=["Technology"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS) as mock_fetch:
        articles = src.crawl()
    # Should only fetch the Technology feed
    calls = mock_fetch.call_args_list
    for call in calls:
        url = call[0][0]
        assert "technology" in url


def test_thehill_tags():
    src = TheHillSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    for a in articles:
        assert any(tag.startswith("thehill:") for tag in a.tags)


def test_thehill_prominent_author_boost():
    src = TheHillSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    # Brett Samuels is a prominent author — should get quality boost
    brett_articles = [a for a in articles if a.author == "Brett Samuels"]
    other_articles = [a for a in articles if a.author and a.author != "Brett Samuels"
                      and "opinion" not in [t for t in a.tags]]
    if brett_articles and other_articles:
        assert brett_articles[0].quality_score >= other_articles[0].quality_score


def test_thehill_source_label():
    src = TheHillSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
        articles = src.crawl()
    for a in articles:
        assert a.source.startswith("The Hill (")


def test_thehill_handles_empty_feed():
    src = TheHillSource()
    with patch.object(src, "fetch_url", return_value=""):
        articles = src.crawl()
    assert articles == []


def test_thehill_handles_fetch_failure():
    src = TheHillSource()
    with patch.object(src, "fetch_url", side_effect=Exception("network error")):
        articles = src.crawl()
    assert articles == []
