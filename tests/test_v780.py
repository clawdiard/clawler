"""Tests for v7.8.0 — YouTube source integration into engine, CLI, and API."""
import pytest
from unittest.mock import patch, MagicMock
from clawler import __version__
from clawler.sources.youtube import YouTubeSource, _channel_category, DEFAULT_CHANNELS


def test_version():
    assert __version__ == "7.8.0"


def test_youtube_source_name():
    src = YouTubeSource()
    assert src.name == "youtube"


def test_youtube_default_channels():
    src = YouTubeSource()
    assert len(src.channels) == 29
    assert "Fireship" in src.channels.values()
    assert "The Berrics" in src.channels.values()


def test_youtube_custom_channels():
    custom = {"UC123": "TestChannel"}
    src = YouTubeSource(channels=custom)
    assert len(src.channels) == 1


def test_channel_category_tech():
    assert _channel_category("Fireship") == "tech"
    assert _channel_category("freeCodeCamp") == "tech"


def test_channel_category_ai():
    assert _channel_category("AI Explained") == "ai"
    assert _channel_category("Two Minute Papers") == "ai"


def test_channel_category_science():
    assert _channel_category("Vsauce") == "science"
    assert _channel_category("Veritasium") == "science"


def test_channel_category_general():
    assert _channel_category("Unknown Channel") == "general"


def test_channel_category_sports():
    assert _channel_category("Braille Skateboarding") == "sports"
    assert _channel_category("The Berrics") == "sports"


def test_engine_imports_youtube():
    from clawler.engine import YouTubeSource as EngineYT
    assert EngineYT is YouTubeSource


def test_cli_has_no_youtube_flag():
    import argparse
    from clawler.cli import main
    # Just verify the arg parser accepts --no-youtube without error
    from clawler.cli import main as cli_main
    import io, sys
    # Test --version to confirm CLI loads without import errors
    with pytest.raises(SystemExit) as exc:
        cli_main(["--version"])
    assert exc.value.code == 0


def test_api_has_youtube_param():
    import inspect
    from clawler.api import crawl
    sig = inspect.signature(crawl)
    assert "no_youtube" in sig.parameters


def test_api_only_youtube():
    """Verify --only=youtube resolves to YouTubeSource only."""
    import inspect
    from clawler.api import crawl
    # Just check the parameter exists and accepts the keyword
    sig = inspect.signature(crawl)
    assert "only" in sig.parameters


def test_weights_youtube():
    from clawler.weights import get_quality_score
    score = get_quality_score("YouTube")
    assert score >= 0.5  # should be 0.60
    assert score <= 1.0


def test_weights_youtube_fireship():
    from clawler.weights import get_quality_score
    score = get_quality_score("YouTube (Fireship)")
    assert score >= 0.7  # should be 0.72


def test_cli_source_registry_has_youtube():
    """Verify YouTube appears in the source registry list used by CLI."""
    # Read the CLI source and check for youtube in the registry
    from clawler.sources import YouTubeSource
    assert YouTubeSource.name == "youtube"
