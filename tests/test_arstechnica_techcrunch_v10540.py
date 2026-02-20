"""Tests for enhanced Ars Technica and TechCrunch sources (v10.54.0)."""
import pytest
from unittest.mock import patch, MagicMock

from clawler.sources.arstechnica import (
    ArsTechnicaSource,
    _detect_category as ars_detect,
    _compute_quality as ars_quality,
    PROMINENT_AUTHORS as ARS_AUTHORS,
    SECTION_PROMINENCE as ARS_PROMINENCE,
    SPECIFIC_CATEGORIES as ARS_CATEGORIES,
)
from clawler.sources.techcrunch import (
    TechCrunchSource,
    _detect_category as tc_detect,
    _compute_quality as tc_quality,
    PROMINENT_AUTHORS as TC_AUTHORS,
    SECTION_PROMINENCE as TC_PROMINENCE,
)


# --- Ars Technica keyword category detection ---

class TestArsDetectCategory:
    def test_ai_keywords(self):
        assert ars_detect("OpenAI launches GPT-5", "", "tech") == "ai"

    def test_security_keywords(self):
        assert ars_detect("Critical zero-day vulnerability found", "", "tech") == "security"

    def test_science_keywords(self):
        assert ars_detect("NASA confirms new exoplanet discovery", "", "tech") == "science"

    def test_space_keywords(self):
        assert ars_detect("SpaceX Starship completes orbit", "", "tech") == "space"

    def test_gaming_keywords(self):
        assert ars_detect("Nintendo reveals new console", "", "tech") == "gaming"

    def test_fallback_to_section(self):
        assert ars_detect("Something generic happened today", "", "tech") == "tech"

    def test_summary_detection(self):
        assert ars_detect("New discovery", "researchers use machine learning to find patterns", "science") == "ai"


class TestArsQualityScore:
    def test_base_score(self):
        score = ars_quality("main", "tech", "tech", 0, "unknown author")
        assert 0.5 <= score <= 0.6

    def test_position_decay(self):
        score_0 = ars_quality("main", "tech", "tech", 0, "")
        score_10 = ars_quality("main", "tech", "tech", 10, "")
        assert score_0 > score_10

    def test_keyword_boost(self):
        base = ars_quality("main", "tech", "tech", 0, "")
        boosted = ars_quality("main", "ai", "tech", 0, "")
        assert boosted > base

    def test_author_boost(self):
        base = ars_quality("main", "tech", "tech", 0, "")
        boosted = ars_quality("main", "tech", "tech", 0, "Dan Goodin")
        assert boosted > base

    def test_score_capped_at_1(self):
        score = ars_quality("main", "ai", "tech", 0, "Dan Goodin")
        assert score <= 1.0

    def test_all_sections_have_prominence(self):
        for section in ARS_PROMINENCE:
            assert 0.0 < ARS_PROMINENCE[section] <= 1.0


class TestArsSourceInit:
    def test_default_feeds(self):
        src = ArsTechnicaSource()
        assert "main" in src._feeds
        assert "ai" in src._feeds

    def test_custom_feeds(self):
        src = ArsTechnicaSource(feeds=["gaming", "science"])
        assert src._feeds == ["gaming", "science"]

    def test_invalid_feeds_filtered(self):
        src = ArsTechnicaSource(feeds=["main", "nonexistent"])
        assert src._feeds == ["main"]

    def test_filters(self):
        src = ArsTechnicaSource(
            min_quality=0.5,
            category_filter=["ai"],
            exclude_sections=["gaming"],
            global_limit=10,
        )
        assert src.min_quality == 0.5
        assert src.category_filter == ["ai"]
        assert src.exclude_sections == ["gaming"]
        assert src.global_limit == 10


# --- TechCrunch keyword category detection ---

class TestTcDetectCategory:
    def test_ai_from_main(self):
        assert tc_detect("OpenAI raises $10B", "", "main") == "ai"

    def test_security_from_main(self):
        assert tc_detect("Major data breach at fintech", "", "main") == "security"

    def test_business_from_main(self):
        assert tc_detect("Startup raises $50M Series B", "", "main") == "business"

    def test_section_override(self):
        # Non-main sections use section category directly
        assert tc_detect("Something about AI", "", "venture") == "business"

    def test_fallback_tech(self):
        assert tc_detect("A new app launched today", "", "main") == "tech"


class TestTcQualityScore:
    def test_base_score(self):
        score = tc_quality("main", "tech", "tech", 0, "unknown")
        assert 0.5 <= score <= 0.6

    def test_position_decay(self):
        s0 = tc_quality("main", "tech", "tech", 0, "")
        s10 = tc_quality("main", "tech", "tech", 10, "")
        assert s0 > s10

    def test_author_boost(self):
        base = tc_quality("main", "tech", "tech", 0, "")
        boosted = tc_quality("main", "tech", "tech", 0, "Zack Whittaker")
        assert boosted > base

    def test_keyword_boost(self):
        base = tc_quality("main", "tech", "tech", 0, "")
        boosted = tc_quality("main", "ai", "tech", 0, "")
        assert boosted > base


class TestTcSourceInit:
    def test_defaults(self):
        src = TechCrunchSource()
        assert src.tc_feeds == ["main"]
        assert src.limit == 25

    def test_filters(self):
        src = TechCrunchSource(
            feeds=["main", "ai"],
            min_quality=0.4,
            category_filter=["ai", "security"],
            global_limit=5,
        )
        assert src.min_quality == 0.4
        assert src.global_limit == 5


# --- Prominent authors sanity checks ---

class TestProminentAuthors:
    def test_ars_authors_have_positive_boost(self):
        for author, boost in ARS_AUTHORS.items():
            assert boost > 0, f"{author} has non-positive boost"
            assert boost <= 0.20, f"{author} boost too high"

    def test_tc_authors_have_positive_boost(self):
        for author, boost in TC_AUTHORS.items():
            assert boost > 0, f"{author} has non-positive boost"
            assert boost <= 0.20, f"{author} boost too high"


# --- Category coverage ---

class TestCategoryCoverage:
    def test_ars_has_core_categories(self):
        cats = set(ARS_CATEGORIES.keys())
        for c in ["ai", "security", "science", "tech", "gaming", "business"]:
            assert c in cats, f"Missing category: {c}"

    def test_ars_keywords_not_empty(self):
        for cat, keywords in ARS_CATEGORIES.items():
            assert len(keywords) >= 3, f"Category {cat} has too few keywords"
