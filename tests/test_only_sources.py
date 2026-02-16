"""Test that --only source names stay in sync with _SOURCE_REGISTRY."""
import re
from pathlib import Path


def _extract_set(name: str, text: str) -> set:
    """Extract a set literal assigned to `name` from source text."""
    # Match: name = {..."..."}  (possibly multi-line)
    pattern = rf"{re.escape(name)}\s*=\s*\{{([^}}]+)\}}"
    m = re.search(pattern, text, re.DOTALL)
    assert m, f"Could not find {name} in cli.py"
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def test_only_names_match_registry():
    """--only _SOURCE_NAMES must contain every key in _SOURCE_REGISTRY."""
    cli_text = (Path(__file__).parent.parent / "clawler" / "cli.py").read_text()

    # Extract registry keys from the list of tuples
    registry_pattern = r"_SOURCE_REGISTRY\s*=\s*\[(.+?)\]"
    m = re.search(registry_pattern, cli_text, re.DOTALL)
    assert m, "Could not find _SOURCE_REGISTRY in cli.py"
    registry_keys = set(re.findall(r'\("([^"]+)"', m.group(1)))

    source_names = _extract_set("_SOURCE_NAMES", cli_text)

    missing = registry_keys - source_names
    extra = source_names - registry_keys
    assert not missing, f"_SOURCE_NAMES missing registry keys: {missing}"
    assert not extra, f"_SOURCE_NAMES has extra keys not in registry: {extra}"
