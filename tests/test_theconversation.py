"""Tests for The Conversation source."""
from unittest.mock import patch
from clawler.sources.theconversation import TheConversationSource, CONVERSATION_FEEDS

SAMPLE_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>The Conversation - Technology</title>
  <entry>
    <title>How AI Is Reshaping Scientific Discovery</title>
    <link href="https://theconversation.com/how-ai-reshaping-discovery-12345" />
    <summary>Machine learning tools are accelerating research.</summary>
    <published>2026-02-19T11:00:00Z</published>
    <author><name>Dr. Jane Smith</name></author>
  </entry>
  <entry>
    <title>The Economics of Carbon Markets</title>
    <link href="https://theconversation.com/carbon-markets-12346" />
    <summary>A look at how carbon trading affects the economy.</summary>
    <published>2026-02-19T09:00:00Z</published>
  </entry>
</feed>"""


def test_conversation_source_name():
    src = TheConversationSource()
    assert src.name == "theconversation"


def test_conversation_feeds_defined():
    assert len(CONVERSATION_FEEDS) >= 5
    for feed in CONVERSATION_FEEDS:
        assert "url" in feed
        assert "section" in feed
        assert "category" in feed


def test_conversation_parse_feed():
    src = TheConversationSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
        articles = src._parse_feed(CONVERSATION_FEEDS[0], set())
    assert len(articles) == 2
    assert articles[0].title == "How AI Is Reshaping Scientific Discovery"
    assert articles[0].quality_score == 0.82


def test_conversation_dedup_across_sections():
    src = TheConversationSource()
    seen = set()
    with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
        a1 = src._parse_feed(CONVERSATION_FEEDS[0], seen)
        a2 = src._parse_feed(CONVERSATION_FEEDS[1], seen)
    # Second call should skip already-seen URLs
    assert len(a1) == 2
    assert len(a2) == 0


def test_conversation_empty_feed():
    src = TheConversationSource()
    with patch.object(src, "fetch_url", return_value=""):
        articles = src._parse_feed(CONVERSATION_FEEDS[0], set())
    assert articles == []


def test_conversation_section_filter():
    src = TheConversationSource(sections=["Technology", "Science"])
    assert src.sections == ["technology", "science"]


def test_conversation_crawl():
    src = TheConversationSource(sections=["Technology"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
        articles = src.crawl()
    assert len(articles) >= 1


def test_conversation_in_registry():
    from clawler.registry import get_entry
    entry = get_entry("theconversation")
    assert entry is not None
    assert entry.display_name == "The Conversation"
