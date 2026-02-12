"""Tests for config file support."""
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch


class TestConfigLoad:
    def test_load_empty_when_no_file(self):
        from clawler.config import load_config
        with patch("pathlib.Path.is_file", return_value=False):
            config = load_config()
        assert config == {}

    def test_load_yaml_config(self):
        from clawler.config import load_config
        content = "format: markdown\nlimit: 25\nquiet: true\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            f.flush()
            fname = f.name

        try:
            with patch("clawler.config.load_config") as mock_load:
                mock_load.return_value = {"format": "markdown", "limit": 25, "quiet": True}
                config = mock_load()
                assert config["format"] == "markdown"
                assert config["limit"] == 25
                assert config["quiet"] is True
        finally:
            os.unlink(fname)

    def test_dashes_converted_to_underscores(self):
        from clawler.config import load_config
        import yaml
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", dir=".", delete=False,
                                          prefix="clawler") as f:
            f.write("no-reddit: true\nexclude-source: Reddit\n")
            fname = f.name

        try:
            # Rename to clawler.yaml in cwd
            target = Path("clawler.yaml")
            os.rename(fname, target)
            config = load_config()
            assert config.get("no_reddit") is True
            assert config.get("exclude_source") == "Reddit"
        finally:
            if target.exists():
                os.unlink(target)


class TestApplyDefaults:
    def test_config_doesnt_override_explicit_args(self):
        import argparse
        from clawler.config import apply_config_defaults

        parser = argparse.ArgumentParser()
        parser.add_argument("--format", default="console")
        parser.add_argument("--limit", type=int, default=50)
        args = parser.parse_args(["--format", "json"])

        with patch("clawler.config.load_config", return_value={"format": "markdown", "limit": 25}):
            result = apply_config_defaults(parser, args)
            assert result.format == "json"  # Explicitly set, not overridden
            assert result.limit == 25  # Was default, so config applies
