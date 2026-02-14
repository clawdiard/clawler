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

    def record_success(self, source: str, article_count: int, response_ms: float = 0):
        self._ensure(source)
        d = self.data[source]
        d["total_crawls"] += 1
        d["total_articles"] += article_count
        d["last_success"] = datetime.now(tz=timezone.utc).isoformat()
        if response_ms > 0:
            timings = d.setdefault("response_times_ms", [])
            timings.append(round(response_ms, 1))
            # Keep last 50 samples to avoid unbounded growth
            if len(timings) > 50:
                d["response_times_ms"] = timings[-50:]

    def record_failure(self, source: str):
        self._ensure(source)
        d = self.data[source]
        d["total_crawls"] += 1
        d["failures"] += 1

    def get_health_modifier(self, source: str) -> float:
        """Return a modifier (0.5-1.0) based on source health."""
        for key, d in self.data.items():
            if key.lower() in source.lower() or source.lower() in key.lower():
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

    def get_report(self):
        """Return a sorted list of source health entries for display."""
        summary = self.summary
        if not summary:
            return []
        entries = []
        for source, d in summary.items():
            entries.append({
                "source": source,
                "success_rate": d["success_rate"],
                "total_crawls": d["total_crawls"],
                "avg_articles": d["avg_articles"],
                "last_success": d["last_success"],
            })
        entries.sort(key=lambda e: e["success_rate"])
        return entries

    def get_timing_report(self):
        """Return sources sorted by average response time (slowest first)."""
        entries = []
        for source, d in self.data.items():
            timings = d.get("response_times_ms", [])
            if not timings:
                continue
            entries.append({
                "source": source,
                "avg_ms": sum(timings) / len(timings),
                "min_ms": min(timings),
                "max_ms": max(timings),
                "samples": len(timings),
            })
        entries.sort(key=lambda e: e["avg_ms"], reverse=True)
        return entries
