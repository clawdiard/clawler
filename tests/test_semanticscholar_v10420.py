"""Tests for Semantic Scholar source (v10.42.0)."""
import json
from unittest.mock import patch, MagicMock
from clawler.sources.semanticscholar import (
    SemanticScholarSource,
    _detect_category,
    _human_count,
    _quality_score,
)


def _mock_paper(title="Test Paper", paper_id="abc123", citations=10,
                influential=2, abstract="A study on machine learning.",
                venue="NeurIPS", year=2025, fields=None, is_oa=True,
                authors=None, pub_date="2025-01-15"):
    return {
        "paperId": paper_id,
        "title": title,
        "url": f"https://www.semanticscholar.org/paper/{paper_id}",
        "abstract": abstract,
        "venue": venue,
        "year": year,
        "citationCount": citations,
        "influentialCitationCount": influential,
        "isOpenAccess": is_oa,
        "openAccessPdf": {"url": f"https://arxiv.org/pdf/{paper_id}"} if is_oa else None,
        "authors": authors or [{"name": "Alice Smith"}, {"name": "Bob Jones"}],
        "fieldsOfStudy": fields or ["Computer Science"],
        "publicationDate": pub_date,
        "externalIds": {"DOI": f"10.1234/{paper_id}"},
    }


def _mock_response(papers):
    return {"total": len(papers), "data": papers}


class TestCategoryDetection:
    def test_ai_keywords(self):
        assert _detect_category("A Transformer Model for NLP", "We use deep learning and neural networks", []) == "ai"

    def test_security_keywords(self):
        assert _detect_category("Malware Detection", "Cybersecurity vulnerability analysis encryption", []) == "security"

    def test_health_keywords(self):
        assert _detect_category("Cancer Drug Discovery", "Clinical trial results for patient treatment", []) == "health"

    def test_crypto_keywords(self):
        assert _detect_category("Smart Contract Verification", "Blockchain ethereum decentralized", []) == "crypto"

    def test_field_fallback(self):
        assert _detect_category("Some Paper", "", ["Medicine"]) == "health"
        assert _detect_category("Some Paper", "", ["Physics"]) == "science"
        assert _detect_category("Some Paper", "", ["Economics"]) == "business"
        assert _detect_category("Some Paper", "", ["Environmental Science"]) == "environment"

    def test_generic_fallback(self):
        assert _detect_category("Untitled", "", []) == "science"

    def test_environment_keywords(self):
        assert _detect_category("Carbon Capture Methods", "Renewable energy solar wind emission reduction", []) == "environment"

    def test_gaming_keywords(self):
        assert _detect_category("Game Engine Design", "Virtual reality augmented reality 3D rendering", []) == "gaming"

    def test_single_keyword_match(self):
        cat = _detect_category("Blockchain Overview", "", [])
        assert cat == "crypto"


class TestQualityScore:
    def test_zero_citations(self):
        score = _quality_score(0, 0, False)
        assert score == 0.0

    def test_moderate_citations(self):
        score = _quality_score(100, 5, True)
        assert 0.4 < score < 0.8

    def test_high_citations(self):
        score = _quality_score(1000, 50, True)
        assert score > 0.7

    def test_open_access_bonus(self):
        no_oa = _quality_score(10, 0, False)
        with_oa = _quality_score(10, 0, True)
        assert with_oa > no_oa
        assert with_oa - no_oa == 0.1  # 10% bonus

    def test_influential_boost(self):
        no_infl = _quality_score(50, 0, False)
        with_infl = _quality_score(50, 10, False)
        assert with_infl > no_infl


class TestHumanCount:
    def test_small(self):
        assert _human_count(42) == "42"

    def test_thousands(self):
        assert _human_count(1500) == "1.5K"

    def test_millions(self):
        assert _human_count(2300000) == "2.3M"


class TestSemanticScholarSource:
    def _make_source(self, **kwargs):
        return SemanticScholarSource(**kwargs)

    @patch.object(SemanticScholarSource, "fetch_json")
    def test_basic_crawl(self, mock_fetch):
        papers = [_mock_paper(title=f"Paper {i}", paper_id=f"id{i}") for i in range(3)]
        mock_fetch.return_value = _mock_response(papers)
        src = self._make_source(searches=["test"], fields=[])
        articles = src.crawl()
        assert len(articles) == 3
        assert all(a.source == "Semantic Scholar" for a in articles)

    @patch.object(SemanticScholarSource, "fetch_json")
    def test_deduplication(self, mock_fetch):
        paper = _mock_paper()
        mock_fetch.return_value = _mock_response([paper, paper])
        src = self._make_source(searches=["q1", "q2"], fields=[])
        articles = src.crawl()
        # Same URL deduped across queries
        assert len(articles) <= 2  # at most 2 from 2 queries hitting same paper

    @patch.object(SemanticScholarSource, "fetch_json")
    def test_min_citations_filter(self, mock_fetch):
        papers = [
            _mock_paper(title="Low", paper_id="low", citations=1),
            _mock_paper(title="High", paper_id="high", citations=100),
        ]
        mock_fetch.return_value = _mock_response(papers)
        src = self._make_source(searches=["test"], fields=[], min_citations=50)
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].title == "High"

    @patch.object(SemanticScholarSource, "fetch_json")
    def test_category_filter(self, mock_fetch):
        papers = [
            _mock_paper(title="ML Paper on Transformers", paper_id="ml1",
                       abstract="Deep learning neural network transformer model"),
            _mock_paper(title="Cancer Treatment", paper_id="med1",
                       abstract="Clinical trial drug discovery patient treatment cancer",
                       fields=["Medicine"]),
        ]
        mock_fetch.return_value = _mock_response(papers)
        src = self._make_source(searches=["test"], fields=[], category_filter="health")
        articles = src.crawl()
        assert all(a.category == "health" for a in articles)

    @patch.object(SemanticScholarSource, "fetch_json")
    def test_open_access_filter(self, mock_fetch):
        papers = [
            _mock_paper(title="Open", paper_id="open1", is_oa=True),
            _mock_paper(title="Closed", paper_id="closed1", is_oa=False),
        ]
        mock_fetch.return_value = _mock_response(papers)
        src = self._make_source(searches=["test"], fields=[], open_access_only=True)
        articles = src.crawl()
        assert all("semscholar:open-access" in a.tags for a in articles)

    @patch.object(SemanticScholarSource, "fetch_json")
    def test_quality_sorted(self, mock_fetch):
        papers = [
            _mock_paper(title="Low Cite", paper_id="low", citations=1, influential=0),
            _mock_paper(title="High Cite", paper_id="high", citations=500, influential=50),
        ]
        mock_fetch.return_value = _mock_response(papers)
        src = self._make_source(searches=["test"], fields=[])
        articles = src.crawl()
        assert articles[0].title == "High Cite"

    @patch.object(SemanticScholarSource, "fetch_json")
    def test_global_limit(self, mock_fetch):
        papers = [_mock_paper(title=f"P{i}", paper_id=f"id{i}") for i in range(20)]
        mock_fetch.return_value = _mock_response(papers)
        src = self._make_source(searches=["test"], fields=[], global_limit=5)
        articles = src.crawl()
        assert len(articles) <= 5

    @patch.object(SemanticScholarSource, "fetch_json")
    def test_provenance_tags(self, mock_fetch):
        mock_fetch.return_value = _mock_response([_mock_paper()])
        src = self._make_source(searches=["machine learning"], fields=[])
        articles = src.crawl()
        assert len(articles) >= 1
        tags = articles[0].tags
        assert any("semscholar:search:" in t for t in tags)
        assert any("semscholar:citations:" in t for t in tags)
        assert any("semscholar:category:" in t for t in tags)
        assert any("semscholar:doi:" in t for t in tags)

    @patch.object(SemanticScholarSource, "fetch_json")
    def test_author_extraction(self, mock_fetch):
        paper = _mock_paper(authors=[
            {"name": "Alice"}, {"name": "Bob"}, {"name": "Carol"},
            {"name": "Dave"}, {"name": "Eve"}, {"name": "Frank"},
        ])
        mock_fetch.return_value = _mock_response([paper])
        src = self._make_source(searches=["test"], fields=[])
        articles = src.crawl()
        assert "+1 more" in articles[0].author

    @patch.object(SemanticScholarSource, "fetch_json")
    def test_open_access_pdf_url(self, mock_fetch):
        paper = _mock_paper(is_oa=True)
        mock_fetch.return_value = _mock_response([paper])
        src = self._make_source(searches=["test"], fields=[])
        articles = src.crawl()
        assert "arxiv.org/pdf" in articles[0].url

    @patch.object(SemanticScholarSource, "fetch_json")
    def test_empty_response(self, mock_fetch):
        mock_fetch.return_value = None
        src = self._make_source(searches=["test"], fields=[])
        articles = src.crawl()
        assert articles == []

    @patch.object(SemanticScholarSource, "fetch_json")
    def test_field_search(self, mock_fetch):
        papers = [_mock_paper(title="Physics Paper", paper_id="phys1", fields=["Physics"])]
        mock_fetch.return_value = _mock_response(papers)
        src = self._make_source(searches=[], fields=["Physics"])
        articles = src.crawl()
        assert len(articles) == 1
        assert any("semscholar:field:Physics" in t for t in articles[0].tags)

    @patch.object(SemanticScholarSource, "fetch_json")
    def test_summary_contains_venue(self, mock_fetch):
        mock_fetch.return_value = _mock_response([_mock_paper(venue="ICML 2025")])
        src = self._make_source(searches=["test"], fields=[])
        articles = src.crawl()
        assert "ICML 2025" in articles[0].summary

    @patch.object(SemanticScholarSource, "fetch_json")
    def test_no_title_skipped(self, mock_fetch):
        paper = _mock_paper()
        paper["title"] = ""
        mock_fetch.return_value = _mock_response([paper])
        src = self._make_source(searches=["test"], fields=[])
        articles = src.crawl()
        assert len(articles) == 0

    @patch.object(SemanticScholarSource, "fetch_json")
    def test_min_quality_filter(self, mock_fetch):
        papers = [
            _mock_paper(title="New", paper_id="new1", citations=0, influential=0, is_oa=False),
            _mock_paper(title="Established", paper_id="est1", citations=200, influential=20),
        ]
        mock_fetch.return_value = _mock_response(papers)
        src = self._make_source(searches=["test"], fields=[], min_quality=0.3)
        articles = src.crawl()
        assert all(a.quality_score >= 0.3 for a in articles)
