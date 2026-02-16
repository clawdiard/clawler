"""Tests for The Register source."""
import pytest
from unittest.mock import patch
from clawler.sources.theregister import TheRegisterSource, _strip_html, _parse_atom_date

SAMPLE_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>The Register</title>
  <entry>
    <title>Cloud costs keep climbing despite optimization efforts</title>
    <link href="https://www.theregister.com/2026/02/16/cloud_costs/" />
    <summary>Companies are still struggling to manage their cloud bills</summary>
    <updated>2026-02-16T14:30:00Z</updated>
    <author><name>Jane Doe</name></author>
  </entry>
  <entry>
    <title>New Linux kernel vulnerability discovered</title>
    <link href="https://www.theregister.com/2026/02/16/linux_vuln/" />
    <summary>Critical flaw affects kernels 6.x</summary>
    <updated>2026-02-16T12:00:00Z</updated>
    <author><name>John Smith</name></author>
  </entry>
  <entry>
    <title></title>
    <link href="https://www.theregister.com/2026/02/16/empty/" />
  </entry>
</feed>"""


def test_strip_html():
    assert _strip_html("<b>hello</b> world") == "hello world"
    assert _strip_html("no tags") == "no tags"
    assert _strip_html("") == ""


def test_parse_atom_date_iso():
    dt = _parse_atom_date("2026-02-16T14:30:00Z")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 2
    assert dt.hour == 14


def test_parse_atom_date_none():
    assert _parse_atom_date("") is None
    assert _parse_atom_date(None) is None


def test_parse_atom_entries():
    src = TheRegisterSource()
    entries = src._parse_atom(SAMPLE_ATOM)
    # Empty title entry should still parse but will be filtered in crawl()
    assert len(entries) == 2  # only entries with title AND link
    assert entries[0]["title"] == "Cloud costs keep climbing despite optimization efforts"
    assert entries[1]["link"] == "https://www.theregister.com/2026/02/16/linux_vuln/"
    assert entries[1]["author"] == "John Smith"


def test_crawl_deduplicates():
    """Articles with the same URL from different feeds should be deduped."""
    src = TheRegisterSource()
    # Mock fetch_url to return the same feed for all requests
    with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
        articles = src.crawl()
    # Should have exactly 2 unique articles regardless of how many feeds
    assert len(articles) == 2
    urls = [a.url for a in articles]
    assert len(set(urls)) == 2


def test_crawl_handles_empty_response():
    src = TheRegisterSource()
    with patch.object(src, "fetch_url", return_value=""):
        articles = src.crawl()
    assert articles == []


def test_article_fields():
    src = TheRegisterSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
        articles = src.crawl()
    a = articles[0]
    assert a.source == "theregister"
    assert a.category in ("tech", "security", "culture")
    assert a.author == "Jane Doe"
    assert a.timestamp is not None


def test_source_name():
    src = TheRegisterSource()
    assert src.name == "theregister"
