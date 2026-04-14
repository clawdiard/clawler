"""Podcast summarization module using LLMs."""
import json
import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from clawler.models import Episode
from clawler.podcast.transcribe import TranscriptResult

logger = logging.getLogger(__name__)


@dataclass
class Chapter:
    """A chapter/section in a podcast episode."""
    title: str
    start_seconds: float
    end_seconds: float
    summary: str = ""

    @property
    def start_formatted(self) -> str:
        hours, remainder = divmod(int(self.start_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "start": self.start_seconds,
            "end": self.end_seconds,
            "start_formatted": self.start_formatted,
            "summary": self.summary,
        }


@dataclass
class SummaryResult:
    """Result of podcast summarization."""
    summary: str                                # Main summary
    key_topics: List[str] = field(default_factory=list)
    key_takeaways: List[str] = field(default_factory=list)
    chapters: List[Chapter] = field(default_factory=list)
    notable_quotes: List[str] = field(default_factory=list)
    mentioned_resources: List[Dict[str, str]] = field(default_factory=list)  # [{name, url}]
    style: str = "executive"
    model_used: str = ""

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "key_topics": self.key_topics,
            "key_takeaways": self.key_takeaways,
            "chapters": [c.to_dict() for c in self.chapters],
            "notable_quotes": self.notable_quotes,
            "mentioned_resources": self.mentioned_resources,
            "style": self.style,
            "model_used": self.model_used,
        }

    def to_markdown(self) -> str:
        """Format summary as Markdown."""
        lines = [f"## Summary\n\n{self.summary}\n"]

        if self.key_topics:
            lines.append("\n## Key Topics\n")
            for topic in self.key_topics:
                lines.append(f"- {topic}")

        if self.key_takeaways:
            lines.append("\n\n## Key Takeaways\n")
            for takeaway in self.key_takeaways:
                lines.append(f"- {takeaway}")

        if self.chapters:
            lines.append("\n\n## Chapters\n")
            for ch in self.chapters:
                lines.append(f"\n### [{ch.start_formatted}] {ch.title}\n")
                if ch.summary:
                    lines.append(ch.summary)

        if self.notable_quotes:
            lines.append("\n\n## Notable Quotes\n")
            for quote in self.notable_quotes:
                lines.append(f"> {quote}\n")

        if self.mentioned_resources:
            lines.append("\n\n## Mentioned Resources\n")
            for res in self.mentioned_resources:
                if res.get("url"):
                    lines.append(f"- [{res['name']}]({res['url']})")
                else:
                    lines.append(f"- {res['name']}")

        return "\n".join(lines)


class PodcastSummarizer:
    """Generate AI summaries from podcast transcripts.

    Supports Anthropic Claude and OpenAI GPT models.
    """

    STYLES = {
        "executive": "A concise executive summary (2-3 paragraphs) highlighting the main points and actionable insights.",
        "detailed": "A comprehensive summary covering all major topics discussed, with context and nuance.",
        "bullets": "A bullet-point summary with key facts and takeaways, organized by topic.",
        "chapters": "A chapter-by-chapter breakdown with timestamps and summaries for each section.",
    }

    def __init__(
        self,
        provider: str = "auto",
        model: Optional[str] = None,
        max_transcript_tokens: int = 100000,
    ):
        """Initialize summarizer.

        Args:
            provider: LLM provider ('anthropic', 'openai', or 'auto').
            model: Specific model to use. If None, uses sensible defaults.
            max_transcript_tokens: Maximum transcript length to send to LLM.
        """
        self._anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self._openai_key = os.environ.get("OPENAI_API_KEY", "")

        # Auto-detect provider
        if provider == "auto":
            if self._anthropic_key:
                self.provider = "anthropic"
            elif self._openai_key:
                self.provider = "openai"
            else:
                self.provider = None
                logger.warning("No LLM API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.")
        else:
            self.provider = provider

        # Set model based on provider
        if model:
            self.model = model
        elif self.provider == "anthropic":
            self.model = "claude-sonnet-4-6"
        elif self.provider == "openai":
            self.model = "gpt-4o"
        else:
            self.model = None

        self.max_transcript_tokens = max_transcript_tokens

    def summarize(
        self,
        transcript: TranscriptResult,
        episode: Optional[Episode] = None,
        style: str = "executive",
    ) -> SummaryResult:
        """Generate summary from transcript.

        Args:
            transcript: TranscriptResult from transcription.
            episode: Optional Episode for context.
            style: Summary style ('executive', 'detailed', 'bullets', 'chapters').

        Returns:
            SummaryResult with summary, topics, and chapters.
        """
        if not self.provider:
            logger.warning("No LLM provider available for summarization")
            return SummaryResult(summary="", style=style)

        if not transcript.text:
            return SummaryResult(summary="No transcript available.", style=style)

        # Truncate transcript if too long (rough token estimate: 4 chars per token)
        max_chars = self.max_transcript_tokens * 4
        transcript_text = transcript.text
        if len(transcript_text) > max_chars:
            logger.info(f"Truncating transcript from {len(transcript_text)} to {max_chars} chars")
            transcript_text = transcript_text[:max_chars] + "\n\n[Transcript truncated...]"

        # Build prompt
        prompt = self._build_prompt(transcript_text, episode, style)

        # Call LLM
        try:
            if self.provider == "anthropic":
                response = self._call_anthropic(prompt)
            else:
                response = self._call_openai(prompt)

            # Parse response
            return self._parse_response(response, style)
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return SummaryResult(summary=f"Summarization failed: {e}", style=style)

    def _build_prompt(
        self,
        transcript: str,
        episode: Optional[Episode],
        style: str
    ) -> str:
        """Build the summarization prompt."""
        context_parts = []
        if episode:
            context_parts.append(f"Podcast: {episode.podcast_name}")
            context_parts.append(f"Episode: {episode.title}")
            if episode.host:
                context_parts.append(f"Host: {episode.host}")
            if episode.guests:
                context_parts.append(f"Guests: {', '.join(episode.guests)}")
            if episode.duration_formatted:
                context_parts.append(f"Duration: {episode.duration_formatted}")

        context = "\n".join(context_parts) if context_parts else "A podcast episode"

        style_instruction = self.STYLES.get(style, self.STYLES["executive"])

        prompt = f"""You are an expert podcast summarizer. Analyze the following podcast transcript and provide a comprehensive summary.

Context:
{context}

Transcript:
{transcript}

Instructions:
1. {style_instruction}
2. Extract 3-7 key topics discussed
3. List 3-5 key takeaways or actionable insights
4. Identify any notable quotes (verbatim from the transcript)
5. List any books, papers, websites, or resources mentioned

Respond in the following JSON format:
{{
  "summary": "Your summary here...",
  "key_topics": ["topic1", "topic2", ...],
  "key_takeaways": ["takeaway1", "takeaway2", ...],
  "notable_quotes": ["quote1", "quote2", ...],
  "mentioned_resources": [{{"name": "Resource Name", "url": "https://..." or null}}]
}}

Only output valid JSON, no other text."""

        return prompt

    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic Claude API."""
        import requests

        response = requests.post(
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
            timeout=120,
        )
        # Check for billing/credit errors and fallback to OpenAI if available
        if response.status_code == 400:
            try:
                err_data = response.json()
                err_msg = err_data.get("error", {}).get("message", "")
                if "credit" in err_msg.lower() or "billing" in err_msg.lower():
                    if self._openai_key:
                        logger.warning("Anthropic API billing issue, falling back to OpenAI...")
                        self.provider = "openai"
                        self.model = "gpt-4o"
                        return self._call_openai(prompt)
            except Exception:
                pass
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]

    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""
        import requests

        response = requests.post(
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
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _parse_response(self, response: str, style: str) -> SummaryResult:
        """Parse LLM response into SummaryResult."""
        # Clean up response (remove markdown code blocks if present)
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # If JSON parsing fails, use the raw text as summary
            logger.warning("Failed to parse LLM response as JSON, using raw text")
            return SummaryResult(
                summary=response,
                style=style,
                model_used=f"{self.provider}/{self.model}",
            )

        # Parse resources
        resources = []
        for res in data.get("mentioned_resources", []):
            if isinstance(res, dict):
                resources.append({
                    "name": res.get("name", ""),
                    "url": res.get("url") or "",
                })
            elif isinstance(res, str):
                resources.append({"name": res, "url": ""})

        return SummaryResult(
            summary=data.get("summary", ""),
            key_topics=data.get("key_topics", []),
            key_takeaways=data.get("key_takeaways", []),
            notable_quotes=data.get("notable_quotes", []),
            mentioned_resources=resources,
            style=style,
            model_used=f"{self.provider}/{self.model}",
        )

    def generate_chapters(
        self,
        transcript: TranscriptResult,
        num_chapters: int = 5,
    ) -> List[Chapter]:
        """Generate chapter markers from transcript.

        Args:
            transcript: TranscriptResult with segments.
            num_chapters: Target number of chapters.

        Returns:
            List of Chapter objects with timestamps.
        """
        if not self.provider or not transcript.segments:
            return []

        # Build prompt with segment info
        segments_text = []
        for seg in transcript.segments[:500]:  # Limit segments to avoid token overflow
            segments_text.append(f"[{seg.start_formatted}] {seg.text}")

        prompt = f"""Analyze this podcast transcript and divide it into {num_chapters} logical chapters/sections.
Each chapter should represent a distinct topic or phase of the conversation.

Transcript with timestamps:
{chr(10).join(segments_text)}

Respond with JSON array of chapters:
[
  {{
    "title": "Chapter title",
    "start_seconds": 0,
    "summary": "Brief 1-2 sentence summary of this section"
  }},
  ...
]

Only output valid JSON array, no other text."""

        try:
            if self.provider == "anthropic":
                response = self._call_anthropic(prompt)
            else:
                response = self._call_openai(prompt)

            # Parse response
            text = response.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:])
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            data = json.loads(text)
            chapters = []
            for i, ch in enumerate(data):
                start = ch.get("start_seconds", 0)
                # End is start of next chapter, or end of episode
                if i + 1 < len(data):
                    end = data[i + 1].get("start_seconds", start)
                else:
                    end = transcript.duration_seconds or start

                chapters.append(Chapter(
                    title=ch.get("title", f"Chapter {i + 1}"),
                    start_seconds=start,
                    end_seconds=end,
                    summary=ch.get("summary", ""),
                ))

            return chapters

        except Exception as e:
            logger.error(f"Chapter generation failed: {e}")
            return []

    def extract_topics(self, transcript: TranscriptResult) -> List[str]:
        """Extract key topics from transcript.

        A lighter-weight alternative to full summarization.
        """
        if not self.provider or not transcript.text:
            return []

        # Use first portion of transcript for topic extraction
        text = transcript.text[:20000]

        prompt = f"""Extract the 5-10 main topics discussed in this podcast transcript.
Return only a JSON array of topic strings, nothing else.

Transcript:
{text}

Example output: ["artificial intelligence", "climate change", "startup funding"]"""

        try:
            if self.provider == "anthropic":
                response = self._call_anthropic(prompt)
            else:
                response = self._call_openai(prompt)

            # Parse response
            text = response.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:])
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            return json.loads(text)

        except Exception as e:
            logger.error(f"Topic extraction failed: {e}")
            return []
