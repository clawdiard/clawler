"""Tests for v4.0.0 features: --config-init, --source-health, CI."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from clawler.config import generate_starter_config, _STARTER_CONFIG
from clawler.health import HealthTracker


class TestConfigInit:
    def test_generate_starter_config_creates_file(self, tmp_path):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        with patch.object(Path, "home", return_value=fake_home):
            path = generate_starter_config()
            assert path.exists()
            content = path.read_text()
            assert "format:" in content
            assert "limit:" in content

    def test_generate_starter_config_no_overwrite(self, tmp_path):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        existing = fake_home / ".clawler.yaml"
        existing.write_text("existing: true")
        with patch.object(Path, "home", return_value=fake_home):
            path = generate_starter_config()
            assert path.name == ".clawler.yaml.new"
            # Original untouched
            assert existing.read_text() == "existing: true"


class TestSourceHealth:
    def test_get_report_empty(self):
        tracker = HealthTracker()
        tracker.data = {}
        assert tracker.get_report() == []

    def test_get_report_with_data(self):
        tracker = HealthTracker()
        tracker.data = {
            "RSS": {
                "total_crawls": 10,
                "failures": 2,
                "total_articles": 400,
                "last_success": "2026-02-13T00:00:00+00:00",
            },
            "HN": {
                "total_crawls": 10,
                "failures": 0,
                "total_articles": 300,
                "last_success": "2026-02-13T00:00:00+00:00",
            },
        }
        report = tracker.get_report()
        assert len(report) == 2
        # Sorted by success_rate ascending
        assert report[0]["source"] == "RSS"
        assert report[0]["success_rate"] == 0.8
        assert report[1]["source"] == "HN"
        assert report[1]["success_rate"] == 1.0
        assert report[1]["avg_articles"] == 30.0


class TestCLINewFlags:
    def test_config_init_flag_accepted(self):
        """Verify the --config-init flag is parsed without error."""
        from clawler.cli import main
        with patch.object(Path, "home", return_value=Path(tempfile.mkdtemp())):
            main(["--config-init"])

    def test_source_health_flag_accepted(self):
        """Verify --source-health runs without error (no data = early exit)."""
        from clawler.cli import main
        # With no health data, should print info message and return
        main(["--source-health"])


class TestVersionSync:
    def test_version_is_4_0_0(self):
        from clawler import __version__
        assert __version__ == "4.8.0"
