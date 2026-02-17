"""Tests for ArXiv source enhancements (v10.1.0)."""
import pytest
from clawler.sources.arxiv import ArXivSource, CATEGORY_MAP, TITLE_KEYWORDS


class TestArXivCategoryMapping:
    def test_ai_categories(self):
        assert ArXivSource._map_category(["cs.AI", "cs.LG"], "") == "ai"
        assert ArXivSource._map_category(["cs.CL"], "") == "ai"
        assert ArXivSource._map_category(["stat.ML"], "") == "ai"

    def test_security_category(self):
        assert ArXivSource._map_category(["cs.CR"], "") == "security"

    def test_tech_categories(self):
        assert ArXivSource._map_category(["cs.SE"], "") == "tech"
        assert ArXivSource._map_category(["cs.DB"], "") == "tech"
        assert ArXivSource._map_category(["cs.PL"], "") == "tech"

    def test_science_categories(self):
        assert ArXivSource._map_category(["quant-ph"], "") == "science"
        assert ArXivSource._map_category(["math.AG"], "") == "science"
        assert ArXivSource._map_category(["astro-ph.CO"], "") == "science"

    def test_finance_category(self):
        assert ArXivSource._map_category(["q-fin.ST"], "") == "business"

    def test_fallback(self):
        assert ArXivSource._map_category(["unknown.XY"], "") == "science"
        assert ArXivSource._map_category([], "") == "science"

    def test_title_keyword_override(self):
        assert ArXivSource._map_category(["math.AG"], "LLM-based Theorem Proving") == "ai"
        assert ArXivSource._map_category(["cs.SE"], "Security Vulnerabilities in CI/CD") == "security"
        assert ArXivSource._map_category(["cs.AI"], "Blockchain Consensus Protocol") == "crypto"
        assert ArXivSource._map_category(["cs.AI"], "Clinical Drug Discovery with AI") == "health"


class TestArXivQualityScore:
    def test_baseline(self):
        score = ArXivSource._compute_quality(["Alice"], [], "Some paper")
        assert 0.4 <= score <= 0.6

    def test_many_authors_boost(self):
        authors = [f"Author{i}" for i in range(6)]
        score = ArXivSource._compute_quality(authors, [], "Some paper")
        assert score >= 0.6

    def test_cross_disciplinary_boost(self):
        tags = ["cs.AI", "cs.CL", "stat.ML"]
        score = ArXivSource._compute_quality(["Alice", "Bob"], tags, "Paper")
        assert score >= 0.6

    def test_hot_topic_boost(self):
        score = ArXivSource._compute_quality(["Alice"], [], "GPT-5 Architecture Analysis")
        assert score >= 0.6

    def test_max_capped(self):
        authors = [f"A{i}" for i in range(10)]
        tags = ["cs.AI", "cs.CL", "stat.ML", "cs.LG"]
        score = ArXivSource._compute_quality(authors, tags, "LLM Transformer Quantum GPT")
        assert score <= 1.0


class TestArXivIdExtraction:
    def test_standard_id(self):
        assert ArXivSource._extract_arxiv_id("http://arxiv.org/abs/2401.12345") == "2401.12345"

    def test_versioned_id(self):
        assert ArXivSource._extract_arxiv_id("http://arxiv.org/abs/2401.12345v2") == "2401.12345"

    def test_no_id(self):
        assert ArXivSource._extract_arxiv_id("http://example.com") is None


class TestArXivSummary:
    def test_short_abstract(self):
        text = "This is a short abstract."
        assert ArXivSource._build_summary(text, "") == text

    def test_long_abstract_sentence_break(self):
        text = "A" * 160 + ". This is the second sentence that goes on and on for a while to exceed the limit."
        result = ArXivSource._build_summary(text, "")
        assert result.endswith(".")
        assert len(result) <= 310

    def test_long_abstract_ellipsis(self):
        text = "A" * 400  # no sentence breaks
        result = ArXivSource._build_summary(text, "")
        assert result.endswith("...")
        assert len(result) == 280


class TestArXivInit:
    def test_defaults(self):
        src = ArXivSource()
        assert src.limit == 25
        assert src.per_category is False
        assert src.min_authors == 0

    def test_per_category_mode(self):
        src = ArXivSource(per_category=True, per_category_limit=5, limit=20)
        assert src.per_category is True
        assert src.per_category_limit == 5

    def test_min_authors(self):
        src = ArXivSource(min_authors=2)
        assert src.min_authors == 2


class TestArXivParseFeed:
    def test_parse_empty(self):
        src = ArXivSource()
        result = src._parse_feed("<feed></feed>")
        assert result == []

    def test_parse_sample_entry(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Test Paper on LLMs</title>
            <link href="http://arxiv.org/abs/2401.99999"/>
            <link href="http://arxiv.org/pdf/2401.99999" title="pdf"/>
            <summary>This is a test abstract about large language models.</summary>
            <published>2026-02-17T00:00:00Z</published>
            <author><name>Alice Smith</name></author>
            <author><name>Bob Jones</name></author>
            <category term="cs.AI"/>
            <category term="cs.CL"/>
          </entry>
        </feed>"""
        src = ArXivSource()
        articles = src._parse_feed(xml)
        assert len(articles) == 1
        a = articles[0]
        assert a.title == "Test Paper on LLMs"
        assert a.category == "ai"  # title keyword "LLM" → ai
        assert a.source == "ArXiv"
        assert "Alice Smith" in a.author
        assert "Bob Jones" in a.author
        assert a.discussion_url == "http://arxiv.org/pdf/2401.99999"
        assert a.quality_score > 0.5  # hot keyword + 2 authors
        assert any("arxiv:id:2401.99999" in t for t in a.tags)
        assert any("arxiv:primary:cs.AI" in t for t in a.tags)

    def test_min_authors_filter(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Solo Paper</title>
            <link href="http://arxiv.org/abs/2401.11111"/>
            <summary>Test</summary>
            <published>2026-02-17T00:00:00Z</published>
            <author><name>Solo Author</name></author>
            <category term="cs.AI"/>
          </entry>
        </feed>"""
        src = ArXivSource(min_authors=2)
        articles = src._parse_feed(xml)
        assert len(articles) == 0  # filtered out

    def test_enriched_summary_has_author_and_category(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Paper</title>
            <link href="http://arxiv.org/abs/2401.22222"/>
            <summary>Abstract text here.</summary>
            <published>2026-02-17T00:00:00Z</published>
            <author><name>Jane Doe</name></author>
            <category term="cs.SE"/>
          </entry>
        </feed>"""
        src = ArXivSource()
        articles = src._parse_feed(xml)
        assert "👤 Jane Doe" in articles[0].summary
        assert "📂 cs.SE" in articles[0].summary


class TestCategoryMapCompleteness:
    def test_all_default_categories_mapped(self):
        for cat in ArXivSource().categories:
            assert cat.lower() in CATEGORY_MAP, f"{cat} not in CATEGORY_MAP"
