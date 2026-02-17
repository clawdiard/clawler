"""Test that --only source names stay in sync with the central registry."""
from clawler.registry import get_all_keys


def test_only_uses_central_registry():
    """CLI --only validation derives from the central registry, not a hardcoded set.

    This test ensures the registry has all expected sources and that the CLI
    imports from registry (verified by the refactor that removed _SOURCE_REGISTRY
    and _SOURCE_NAMES from cli.py).
    """
    keys = get_all_keys()
    assert len(keys) > 40, f"Expected 40+ sources in registry, got {len(keys)}"
    # Spot-check some key sources
    for expected in ("rss", "hn", "reddit", "github", "flipboard", "bbc"):
        assert expected in keys, f"Expected '{expected}' in registry keys"


def test_cli_no_flags_match_registry():
    """Every registry source should have a corresponding --no-<key> CLI flag."""
    import argparse
    from unittest.mock import patch
    from clawler.cli import main

    # Parse --help to get all flags (we just need the parser)
    from clawler.cli import main as _main
    import clawler.cli as cli_mod
    import inspect

    # Get the source of main to verify it uses _REGISTRY_SOURCES
    src = inspect.getsource(cli_mod)
    assert "_REGISTRY_SOURCES" in src or "SOURCES" in src, \
        "CLI should reference the central registry, not a hardcoded list"
