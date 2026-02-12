"""YAML-based feed configuration loader."""
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def load_feeds_file(path: str) -> Optional[List[dict]]:
    """Load feeds from a YAML or JSON file.

    Expected format (YAML):
        feeds:
          - url: https://example.com/feed.xml
            source: Example
            category: tech
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Feeds file not found: {path}")

    content = p.read_text(encoding="utf-8")

    if p.suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML required for YAML feeds files: pip install pyyaml")
        data = yaml.safe_load(content)
    elif p.suffix == ".json":
        import json
        data = json.loads(content)
    else:
        raise ValueError(f"Unsupported feeds file format: {p.suffix} (use .yaml, .yml, or .json)")

    if not isinstance(data, dict) or "feeds" not in data:
        raise ValueError("Feeds file must contain a top-level 'feeds' key with a list of feed objects")

    feeds = data["feeds"]
    if not isinstance(feeds, list):
        raise ValueError("'feeds' must be a list")

    # Validate each feed
    for i, f in enumerate(feeds):
        if not isinstance(f, dict) or "url" not in f:
            raise ValueError(f"Feed #{i+1} must be a dict with at least 'url'")
        f.setdefault("source", f["url"])
        f.setdefault("category", "general")

    logger.info(f"Loaded {len(feeds)} feeds from {path}")
    return feeds
