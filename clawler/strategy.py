"""LLM-powered content sourcing strategy filter."""
from __future__ import annotations

import json
import logging
import os
from typing import List

from clawler.models import Article

logger = logging.getLogger(__name__)


class StrategyFilter:
    """Filter articles by relevance to an editorial sourcing strategy using an LLM."""

    def __init__(
        self,
        strategy_text: str,
        model: str | None = None,
        batch_size: int = 20,
        min_score: float = 0.3,
    ):
        self.strategy_text = strategy_text.strip()
        self.batch_size = batch_size
        self.min_score = min_score

        # Determine provider
        self._anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        self._openai_key = os.environ.get("OPENAI_API_KEY")

        if self._anthropic_key:
            self._provider = "anthropic"
            self.model = model or "claude-sonnet-4-20250514"
        elif self._openai_key:
            self._provider = "openai"
            self.model = model or "gpt-4o-mini"
        else:
            self._provider = None
            self.model = None
            logger.warning("No ANTHROPIC_API_KEY or OPENAI_API_KEY found; strategy filter will pass all articles through")

    def filter(self, articles: List[Article]) -> List[Article]:
        """Score and filter articles by relevance to the strategy."""
        if not articles:
            return []
        if not self._provider:
            logger.warning("No LLM API key available — returning all articles unfiltered")
            for a in articles:
                if a.relevance is None:
                    a.relevance = 0.0
            return articles

        # Process in batches
        scored: list[tuple[Article, float, str]] = []
        for i in range(0, len(articles), self.batch_size):
            batch = articles[i : i + self.batch_size]
            results = self._score_batch(batch, start_index=i)
            if results is None:
                # LLM call failed — return all articles unfiltered
                logger.warning("LLM scoring failed — returning all articles unfiltered")
                for a in articles:
                    if a.relevance is None:
                        a.relevance = 0.0
                return articles
            for article, score, reason in results:
                article.relevance = score
                scored.append((article, score, reason))

        # Filter and sort
        filtered = [(a, s, r) for a, s, r in scored if s >= self.min_score]
        filtered.sort(key=lambda x: x[1], reverse=True)
        return [a for a, s, r in filtered]

    def _score_batch(
        self, batch: List[Article], start_index: int = 0
    ) -> list[tuple[Article, float, str]] | None:
        """Score a batch of articles via LLM. Returns None on failure."""
        import requests

        # Format articles for prompt
        lines = []
        for i, a in enumerate(batch):
            lines.append(f"[{i}] Title: {a.title}")
            lines.append(f"    Source: {a.source}")
            if a.summary:
                lines.append(f"    Summary: {a.summary[:500]}")
            lines.append("")

        prompt = (
            "You are a content strategist. Given an editorial strategy and a batch of articles, "
            "score each article's relevance to the strategy from 0.0 (completely irrelevant) to 1.0 (perfectly aligned).\n\n"
            f"Editorial Strategy:\n{self.strategy_text}\n\n"
            f"Articles to evaluate:\n{''.join(l + chr(10) for l in lines)}\n"
            'Respond with ONLY a JSON array of objects: [{"index": 0, "score": 0.85, "reason": "brief reason"}, ...]'
        )

        try:
            if self._provider == "anthropic":
                resp = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self._anthropic_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 4096,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["content"][0]["text"]
            else:  # openai
                resp = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._openai_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 4096,
                    },
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["choices"][0]["message"]["content"]

            # Parse JSON from response (handle markdown code blocks)
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            scores = json.loads(text)
            results = []
            score_map = {item["index"]: item for item in scores}
            for i, article in enumerate(batch):
                if i in score_map:
                    s = float(score_map[i].get("score", 0.0))
                    r = score_map[i].get("reason", "")
                    results.append((article, max(0.0, min(1.0, s)), r))
                else:
                    results.append((article, 0.0, "not scored"))
            return results

        except Exception as e:
            logger.warning(f"Strategy filter LLM call failed: {e}")
            return None
