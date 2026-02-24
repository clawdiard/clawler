"""Tests for CNET, ProPublica, InfoQ quality scoring enhancements (v10.83.0)."""
from unittest.mock import patch
from clawler.sources.cnet import CNETSource, _detect_category, _compute_quality
from clawler.sources.propublica import (
    ProPublicaSource,
    _categorize as pp_categorize,
    _compute_quality as pp_compute_quality,
)
from clawler.sources.infoq import (
    InfoQSource,
    _detect_category as iq_detect_category,
    _compute_quality as iq_compute_quality,
)


# --- CNET tests ---

class TestCNETCategoryDetection:
    def test_ai_detection(self):
        assert _detect_category("ChatGPT gets major update", "", "news") == "ai"

    def test_security_detection(self):
        assert _detect_category("Major data breach at company", "", "news") == "security"

    def test_culture_detection(self):
        assert _detect_category("Netflix releases new show", "", "news") == "culture"

    def test_fallback_to_section(self):
        assert _detect_category("Generic headline", "", "reviews") == "tech"
        assert _detect_category("Generic headline", "", "deals") == "business"


class TestCNETQualityScoring:
    def test_news_higher_than_deals(self):
        q_news = _compute_quality("news", "tech", "tech", 0, "")
        q_deals = _compute_quality("deals", "business", "business", 0, "")
        assert q_news > q_deals

    def test_position_decay(self):
        q0 = _compute_quality("news", "tech", "tech", 0, "")
        q5 = _compute_quality("news", "tech", "tech", 5, "")
        assert q0 > q5

    def test_prominent_author_boost(self):
        q_no = _compute_quality("news", "tech", "tech", 0, "nobody")
        q_yes = _compute_quality("news", "tech", "tech", 0, "Dan Ackerman")
        assert q_yes > q_no

    def test_keyword_specificity_boost(self):
        q_default = _compute_quality("news", "tech", "tech", 0, "")
        q_specific = _compute_quality("news", "ai", "tech", 0, "")
        assert q_specific > q_default

    def test_score_capped_at_one(self):
        q = _compute_quality("news", "ai", "tech", 0, "Dan Ackerman")
        assert q <= 1.0


class TestCNETSource:
    def test_init_defaults(self):
        s = CNETSource()
        assert s.sections == ["news", "reviews"]
        assert s.min_quality == 0.0

    def test_init_custom(self):
        s = CNETSource(sections=["tech"], min_quality=0.5, global_limit=10)
        assert s.sections == ["tech"]
        assert s.min_quality == 0.5
        assert s.global_limit == 10


# --- ProPublica tests ---

class TestProPublicaCategorize:
    def test_criminal_justice(self):
        assert pp_categorize("Police reform bill advances", "") == "criminal_justice"

    def test_healthcare(self):
        assert pp_categorize("Hospital prices hidden from patients", "") == "healthcare"

    def test_environment(self):
        assert pp_categorize("Toxic pollution in water supply", "") == "environment"

    def test_fallback(self):
        assert pp_categorize("Something generic", "no keywords") == "investigative"


class TestProPublicaQuality:
    def test_top_stories_higher(self):
        q_top = pp_compute_quality("Top Stories", "investigative", "investigative", 0, "")
        q_local = pp_compute_quality("Local", "government", "government", 0, "")
        assert q_top > q_local

    def test_author_boost(self):
        q_no = pp_compute_quality("Articles", "investigative", "investigative", 0, "")
        q_yes = pp_compute_quality("Articles", "investigative", "investigative", 0, "Jane Smith")
        assert q_yes > q_no

    def test_capped(self):
        q = pp_compute_quality("Top Stories", "tech", "investigative", 0, "Author")
        assert q <= 1.0


class TestProPublicaSource:
    def test_init_defaults(self):
        s = ProPublicaSource()
        assert s.limit == 20
        assert s.min_quality == 0.0

    def test_init_filters(self):
        s = ProPublicaSource(categories=["tech"], min_quality=0.3, global_limit=5)
        assert s.categories == ["tech"]
        assert s.global_limit == 5


# --- InfoQ tests ---

class TestInfoQCategoryDetection:
    def test_ai(self):
        assert iq_detect_category("Deep learning advances", "", "all") == "ai"

    def test_devops(self):
        assert iq_detect_category("Kubernetes best practices", "", "all") == "devops"

    def test_security(self):
        assert iq_detect_category("New zero-day vulnerability found", "", "all") == "security"

    def test_fallback(self):
        assert iq_detect_category("Generic article", "", "java") == "tech"


class TestInfoQQuality:
    def test_ai_higher_than_all(self):
        q_ai = iq_compute_quality("ai", "ai", "ai", 0, "")
        q_all = iq_compute_quality("all", "tech", "tech", 0, "")
        assert q_ai > q_all

    def test_position_decay(self):
        q0 = iq_compute_quality("ai", "ai", "ai", 0, "")
        q10 = iq_compute_quality("ai", "ai", "ai", 10, "")
        assert q0 > q10

    def test_author_boost(self):
        q_no = iq_compute_quality("cloud", "tech", "tech", 0, "")
        q_yes = iq_compute_quality("cloud", "tech", "tech", 0, "Author")
        assert q_yes > q_no

    def test_capped(self):
        q = iq_compute_quality("ai", "security", "ai", 0, "Author")
        assert q <= 1.0


class TestInfoQSource:
    def test_init_defaults(self):
        s = InfoQSource()
        assert len(s.feeds) == 7
        assert s.min_quality == 0.0

    def test_topic_filter(self):
        s = InfoQSource(topics=["ai", "cloud"])
        assert len(s.feeds) == 2

    def test_init_custom(self):
        s = InfoQSource(min_quality=0.4, global_limit=15)
        assert s.min_quality == 0.4
        assert s.global_limit == 15
