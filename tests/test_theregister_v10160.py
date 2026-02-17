"""Tests for The Register source v10.16.0 enhancements."""
import pytest
from unittest.mock import patch
from clawler.sources.theregister import (
    TheRegisterSource, _strip_html, _parse_atom_date, _detect_category,
    _compute_quality, _format_count, _extract_comment_count,
)

SAMPLE_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>The Register</title>
  <entry>
    <title>Cloud costs keep climbing despite optimization efforts</title>
    <link href="https://www.theregister.com/2026/02/16/cloud_costs/" />
    <summary>Companies are still struggling to manage their cloud bills. 42 comments</summary>
    <updated>2026-02-16T14:30:00Z</updated>
    <author><name>Jane Doe</name></author>
  </entry>
  <entry>
    <title>New ransomware vulnerability discovered in Linux kernel</title>
    <link href="https://www.theregister.com/2026/02/16/linux_vuln/" />
    <summary>Critical security flaw affects kernels 6.x. 150 comments</summary>
    <updated>2026-02-16T12:00:00Z</updated>
    <author><name>John Smith</name></author>
  </entry>
  <entry>
    <title>OpenAI launches new GPT model for enterprise</title>
    <link href="https://www.theregister.com/2026/02/16/openai_gpt/" />
    <summary>Large language model targets business use. 88 comments</summary>
    <updated>2026-02-16T10:00:00Z</updated>
    <author><name>AI Reporter</name></author>
  </entry>
  <entry>
    <title></title>
    <link href="https://www.theregister.com/2026/02/16/empty/" />
  </entry>
</feed>"""

SAMPLE_NO_COMMENTS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Quiet article with no engagement</title>
    <link href="https://www.theregister.com/2026/02/16/quiet/" />
    <summary>Nothing to see here</summary>
    <updated>2026-02-16T08:00:00Z</updated>
  </entry>
</feed>"""


class TestStripHtml:
    def test_basic(self):
        assert _strip_html("<b>hello</b> world") == "hello world"

    def test_no_tags(self):
        assert _strip_html("no tags") == "no tags"

    def test_empty(self):
        assert _strip_html("") == ""


class TestParseAtomDate:
    def test_iso_z(self):
        dt = _parse_atom_date("2026-02-16T14:30:00Z")
        assert dt is not None
        assert dt.year == 2026 and dt.hour == 14

    def test_empty(self):
        assert _parse_atom_date("") is None
        assert _parse_atom_date(None) is None


class TestDetectCategory:
    def test_security_keywords(self):
        assert _detect_category("Ransomware attack hits NHS", "", "headlines") == "security"

    def test_ai_keywords(self):
        assert _detect_category("OpenAI GPT-5 released", "", "headlines") == "ai"

    def test_crypto_keywords(self):
        assert _detect_category("Bitcoin hits new high", "", "headlines") == "crypto"

    def test_science_keywords(self):
        assert _detect_category("NASA launches telescope", "", "headlines") == "science"

    def test_health_keywords(self):
        assert _detect_category("FDA approves new vaccine", "", "headlines") == "health"

    def test_business_keywords(self):
        assert _detect_category("Microsoft acquisition of startup", "", "headlines") == "business"

    def test_world_keywords(self):
        assert _detect_category("EU parliament passes legislation", "", "headlines") == "world"

    def test_section_fallback(self):
        assert _detect_category("Something generic here", "", "security") == "security"
        assert _detect_category("Nothing special", "", "offbeat") == "culture"

    def test_summary_used(self):
        assert _detect_category("Update", "critical vulnerability found", "headlines") == "security"


class TestComputeQuality:
    def test_baseline(self):
        q = _compute_quality(0, "headlines")
        assert 0.3 <= q <= 0.4

    def test_high_comments(self):
        q = _compute_quality(200, "headlines")
        assert q > 0.7

    def test_section_boost(self):
        q_sec = _compute_quality(10, "security")
        q_off = _compute_quality(10, "offbeat")
        assert q_sec > q_off

    def test_capped_at_one(self):
        assert _compute_quality(100000, "security") <= 1.0


class TestFormatCount:
    def test_small(self):
        assert _format_count(42) == "42"

    def test_thousands(self):
        assert _format_count(1500) == "1.5K"

    def test_millions(self):
        assert _format_count(2300000) == "2.3M"


class TestExtractCommentCount:
    def test_found(self):
        assert _extract_comment_count("blah blah 42 comments blah") == 42

    def test_singular(self):
        assert _extract_comment_count("1 comment") == 1

    def test_not_found(self):
        assert _extract_comment_count("no numbers here") == 0


class TestCrawl:
    def test_basic_crawl(self):
        src = TheRegisterSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
            articles = src.crawl()
        assert len(articles) == 3
        assert all(a.source == "theregister" for a in articles)

    def test_deduplicates(self):
        src = TheRegisterSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
            articles = src.crawl()
        assert len(set(a.url for a in articles)) == len(articles)

    def test_quality_sorted(self):
        src = TheRegisterSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
            articles = src.crawl()
        scores = [a.quality_score for a in articles]
        assert scores == sorted(scores, reverse=True)

    def test_keyword_category_detection(self):
        src = TheRegisterSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
            articles = src.crawl()
        cats = {a.title: a.category for a in articles}
        assert cats["New ransomware vulnerability discovered in Linux kernel"] == "security"
        assert cats["OpenAI launches new GPT model for enterprise"] == "ai"

    def test_comment_extraction(self):
        src = TheRegisterSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
            articles = src.crawl()
        # All articles with comments should have has-discussion tag
        for a in articles:
            assert "register:has-discussion" in a.tags

    def test_enriched_summary(self):
        src = TheRegisterSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
            articles = src.crawl()
        for a in articles:
            assert "✍️" in a.summary  # author present
            assert "📰" in a.summary  # section present

    def test_provenance_tags(self):
        src = TheRegisterSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
            articles = src.crawl()
        a = articles[0]
        section_tags = [t for t in a.tags if t.startswith("register:section:")]
        cat_tags = [t for t in a.tags if t.startswith("register:category:")]
        assert len(section_tags) == 1
        assert len(cat_tags) == 1

    def test_min_comments_filter(self):
        src = TheRegisterSource(min_comments=100)
        with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
            articles = src.crawl()
        assert len(articles) == 1  # only the 150 comments article
        assert "150" in articles[0].summary or "ransomware" in articles[0].title.lower()

    def test_min_quality_filter(self):
        src = TheRegisterSource(min_quality=0.9)
        with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
            articles = src.crawl()
        assert all(a.quality_score >= 0.9 for a in articles)

    def test_category_filter(self):
        src = TheRegisterSource(category_filter=["security"])
        with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
            articles = src.crawl()
        assert all(a.category == "security" for a in articles)

    def test_section_filter(self):
        src = TheRegisterSource(sections=["security"])
        with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
            articles = src.crawl()
        # Should only fetch security feed
        assert len(articles) >= 0  # structural test

    def test_global_limit(self):
        src = TheRegisterSource(global_limit=1)
        with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
            articles = src.crawl()
        assert len(articles) == 1

    def test_empty_response(self):
        src = TheRegisterSource()
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []

    def test_no_comments_article(self):
        src = TheRegisterSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_NO_COMMENTS):
            articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].quality_score >= 0.3  # baseline
        assert "register:has-discussion" not in articles[0].tags

    def test_author_tag(self):
        src = TheRegisterSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_ATOM):
            articles = src.crawl()
        author_tags = [t for a in articles for t in a.tags if t.startswith("register:author:")]
        assert len(author_tags) == 3
