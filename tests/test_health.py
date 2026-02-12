"""Tests for health tracking."""
from clawler.health import HealthTracker


class TestHealthTracker:
    def test_new_source_modifier_is_1(self):
        tracker = HealthTracker()
        assert tracker.get_health_modifier("Unknown Source") == 1.0

    def test_modifier_after_failures(self):
        tracker = HealthTracker()
        for _ in range(10):
            tracker.record_failure("bad_source")
        mod = tracker.get_health_modifier("bad_source")
        assert mod == 0.5

    def test_modifier_after_successes(self):
        tracker = HealthTracker()
        for _ in range(10):
            tracker.record_success("good_source", 5)
        mod = tracker.get_health_modifier("good_source")
        assert mod == 1.0

    def test_case_insensitive_lookup(self):
        """Regression: health modifier should match case-insensitively."""
        tracker = HealthTracker()
        for _ in range(10):
            tracker.record_failure("Ars Technica")
        # Should find "Ars Technica" when querying with different case
        mod = tracker.get_health_modifier("ars technica")
        assert mod == 0.5

    def test_summary_empty(self):
        tracker = HealthTracker()
        tracker.data = {}  # Reset any loaded data
        assert tracker.summary == {}

    def test_summary_with_data(self):
        tracker = HealthTracker()
        tracker.record_success("s1", 10)
        tracker.record_failure("s1")
        s = tracker.summary["s1"]
        assert s["total_crawls"] == 2
        assert s["failures"] == 1
        assert s["success_rate"] == 0.5
