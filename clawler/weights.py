"""Source quality weight lookups for Clawler."""
import os
import logging
from typing import Dict

import yaml

logger = logging.getLogger(__name__)

_weights: Dict[str, float] = {}
_loaded = False
DEFAULT_SCORE = 0.5


def _load():
    global _weights, _loaded
    if _loaded:
        return
    yaml_path = os.path.join(os.path.dirname(__file__), "source_weights.yaml")
    try:
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        _weights = {k: float(v) for k, v in data.get("sources", {}).items()}
        logger.debug(f"[Weights] Loaded {len(_weights)} source weights")
    except Exception as e:
        logger.warning(f"[Weights] Failed to load source_weights.yaml: {e}")
        _weights = {}
    _loaded = True


def get_quality_score(source_name: str) -> float:
    """Return quality score for a source name. Tries exact match then substring."""
    _load()
    if source_name in _weights:
        return _weights[source_name]
    source_lower = source_name.lower()
    for key, score in _weights.items():
        if key.lower() in source_lower or source_lower in key.lower():
            return score
    if source_name.startswith("r/"):
        return _weights.get("Reddit", DEFAULT_SCORE)
    if "hacker news" in source_lower:
        return _weights.get("Hacker News", DEFAULT_SCORE)
    return DEFAULT_SCORE


def get_all_weights() -> Dict[str, float]:
    """Return all loaded source weights."""
    _load()
    return dict(_weights)
