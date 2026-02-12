"""Source health tracking for Clawler."""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict

logger = logging.getLogger(__name__)

HEALTH_PATH = os.path.expanduser("~/.clawler/health.json")


class HealthTracker:
    """Track per-source crawl health and apply modifiers."""

    def __init__(self):
        self.data: Dict[str, dict] = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(HEALTH_PATH):
                with open(HEALTH_PATH) as f:
                    self.data = json.load(f)
        except Exception as e:
            logger.debug(f"[Health] Could not load health data: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(HEALTH_PATH), exist_ok=True)
            with open(HEALTH_PATH, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.debug(f"[Health] Could not save health data: {e}")

    def _ensure(self, source: str):
        if source not in self.data:
            self.data[source] = {
                "total_crawls": 0,
                "failures": 0,
                "total_articles": 0,
                "last_success": None,
            }

    def record_success(self, source: str, article_count: int):
        self._ensure(source)
        d = self.data[source]
        d["total_crawls"] += 1
        d["total_articles"] += article_count
        d["last_success"] = datetime.now(tz=timezone.utc).isoformat()

    def record_failure(self, source: str):
        self._ensure(source)
        d = self.data[source]
        d["total_crawls"] += 1
        d["failures"] += 1

    def get_health_modifier(self, source: str) -> float:
        """Return a modifier (0.5-1.0) based on source health."""
        for key, d in self.data.items():
            if key in source.lower() or source.lower() in key:
                total = d.get("total_crawls", 0)
                if total == 0:
                    return 1.0
                success_rate = 1.0 - (d.get("failures", 0) / total)
                if success_rate < 0.5:
                    return 0.5
                elif success_rate < 0.8:
                    return 0.8
                return 1.0
        return 1.0

    @property
    def summary(self) -> Dict[str, dict]:
        """Return health summary with computed stats."""
        result = {}
        for source, d in self.data.items():
            total = d.get("total_crawls", 0)
            failures = d.get("failures", 0)
            successes = total - failures
            result[source] = {
                "total_crawls": total,
                "failures": failures,
                "success_rate": round(1.0 - (failures / total), 2) if total > 0 else 0,
                "avg_articles": round(d.get("total_articles", 0) / max(1, successes), 1),
                "last_success": d.get("last_success"),
            }
        return result
