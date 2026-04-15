"""Podcast ingestion pipeline — download, transcribe, and summarize."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

from clawler.models import Episode
from clawler.podcast.transcribe import PodcastTranscriber, TranscriptResult
from clawler.podcast.summarize import PodcastSummarizer, SummaryResult, Chapter

logger = logging.getLogger(__name__)

# Default cache directory for ingested episodes
DEFAULT_CACHE_DIR = Path.home() / ".clawler" / "podcast_cache" / "ingested"


@dataclass
class IngestedEpisode:
    """Result of full podcast ingestion (transcription + summarization)."""
    episode: Episode
    transcript: TranscriptResult
    summary: SummaryResult
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cached: bool = False

    @property
    def title(self) -> str:
        return self.episode.title

    @property
    def podcast_name(self) -> str:
        return self.episode.podcast_name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode": {
                "title": self.episode.title,
                "url": self.episode.url,
                "podcast_name": self.episode.podcast_name,
                "source_platform": self.episode.source_platform,
                "audio_url": self.episode.audio_url,
                "timestamp": self.episode.timestamp.isoformat() if self.episode.timestamp else None,
                "duration_seconds": self.episode.duration_seconds,
                "duration_formatted": self.episode.duration_formatted,
                "host": self.episode.host,
                "guests": self.episode.guests,
            },
            "transcript": self.transcript.to_dict(),
            "summary": self.summary.to_dict(),
            "ingested_at": self.ingested_at.isoformat(),
        }

    def to_markdown(self) -> str:
        """Format as a comprehensive Markdown document."""
        lines = [
            f"# {self.episode.title}",
            "",
            f"**Podcast:** {self.episode.podcast_name}",
        ]

        if self.episode.host:
            lines.append(f"**Host:** {self.episode.host}")
        if self.episode.guests:
            lines.append(f"**Guests:** {', '.join(self.episode.guests)}")
        if self.episode.duration_formatted:
            lines.append(f"**Duration:** {self.episode.duration_formatted}")
        if self.episode.timestamp:
            lines.append(f"**Published:** {self.episode.timestamp.strftime('%Y-%m-%d')}")
        lines.append(f"**URL:** {self.episode.url}")
        lines.append("")

        # Summary section
        lines.append(self.summary.to_markdown())

        # Full transcript
        lines.append("\n---\n")
        lines.append("## Full Transcript\n")
        if self.transcript.segments:
            for seg in self.transcript.segments:
                lines.append(f"**[{seg.start_formatted}]** {seg.text}\n")
        else:
            lines.append(self.transcript.text)

        return "\n".join(lines)

    def to_slack_markdown(self) -> str:
        """Format as Slack-friendly markdown (no transcript, URL prominent)."""
        lines = [
            f"🎙️ *{self.episode.podcast_name}* — {self.episode.title}",
            "",
        ]

        # Summary
        if self.summary.summary:
            lines.append(self.summary.summary)
            lines.append("")

        # Key takeaways
        if self.summary.key_takeaways:
            lines.append("*Key Takeaways:*")
            for takeaway in self.summary.key_takeaways:
                lines.append(f"• {takeaway}")
            lines.append("")

        # Notable quote (just one)
        if self.summary.notable_quotes:
            lines.append(f"> \"{self.summary.notable_quotes[0]}\"")
            lines.append("")

        # URL - prominent at the bottom
        lines.append(f"🔗 {self.episode.url}")

        return "\n".join(lines)

    def get_transcript_text(self) -> str:
        """Get the full transcript text for posting in threads."""
        if self.transcript.segments:
            lines = []
            for seg in self.transcript.segments:
                lines.append(f"[{seg.start_formatted}] {seg.text}")
            return "\n\n".join(lines)
        return self.transcript.text or ""

    def get_transcript_chunks(self, max_chars: int = 3500) -> List[str]:
        """Split transcript into chunks suitable for Slack messages (max ~4000 chars).

        Returns list of chunks, each under max_chars.
        """
        full_text = self.get_transcript_text()
        if not full_text:
            return []

        # Split by paragraphs first
        paragraphs = full_text.split("\n\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= max_chars:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # If single paragraph is too long, split by sentences
                if len(para) > max_chars:
                    sentences = para.replace(". ", ".\n").split("\n")
                    current_chunk = ""
                    for sent in sentences:
                        if len(current_chunk) + len(sent) + 1 <= max_chars:
                            current_chunk += sent + " "
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = sent + " "
                else:
                    current_chunk = para + "\n\n"

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks


class PodcastIngestPipeline:
    """Full pipeline for podcast ingestion: download → transcribe → summarize."""

    def __init__(
        self,
        transcriber: Optional[PodcastTranscriber] = None,
        summarizer: Optional[PodcastSummarizer] = None,
        cache_dir: Optional[str] = None,
        save_transcripts: bool = True,
        save_summaries: bool = True,
        summary_style: str = "executive",
    ):
        """Initialize the ingest pipeline.

        Args:
            transcriber: PodcastTranscriber instance. Created with defaults if None.
            summarizer: PodcastSummarizer instance. Created with defaults if None.
            cache_dir: Directory to cache ingested results.
            save_transcripts: Whether to save full transcripts to disk.
            save_summaries: Whether to save summaries to disk.
            summary_style: Default summary style ('executive', 'detailed', 'bullets', 'chapters').
        """
        self.transcriber = transcriber or PodcastTranscriber()
        self.summarizer = summarizer or PodcastSummarizer()
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.save_transcripts = save_transcripts
        self.save_summaries = save_summaries
        self.summary_style = summary_style

    def _get_cache_path(self, episode: Episode) -> Path:
        """Get cache file path for an episode."""
        # Use podcast name + episode title as identifier
        safe_podcast = "".join(c if c.isalnum() else "_" for c in episode.podcast_name)[:30]
        safe_title = "".join(c if c.isalnum() else "_" for c in episode.title)[:50]
        return self.cache_dir / f"{safe_podcast}_{safe_title}.json"

    def _load_cached(self, episode: Episode) -> Optional[IngestedEpisode]:
        """Load cached ingested episode if available."""
        cache_path = self._get_cache_path(episode)
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Reconstruct transcript
            transcript = TranscriptResult(
                text=data["transcript"]["text"],
                language=data["transcript"].get("language", "en"),
                duration_seconds=data["transcript"].get("duration_seconds", 0),
                model_used=data["transcript"].get("model_used", ""),
                cached=True,
            )

            # Reconstruct summary
            summary_data = data.get("summary", {})
            chapters = [
                Chapter(
                    title=ch["title"],
                    start_seconds=ch["start"],
                    end_seconds=ch["end"],
                    summary=ch.get("summary", ""),
                )
                for ch in summary_data.get("chapters", [])
            ]
            summary = SummaryResult(
                summary=summary_data.get("summary", ""),
                key_topics=summary_data.get("key_topics", []),
                key_takeaways=summary_data.get("key_takeaways", []),
                chapters=chapters,
                notable_quotes=summary_data.get("notable_quotes", []),
                mentioned_resources=summary_data.get("mentioned_resources", []),
                style=summary_data.get("style", "executive"),
                model_used=summary_data.get("model_used", ""),
            )

            # Parse ingested_at
            ingested_at = datetime.now(timezone.utc)
            if data.get("ingested_at"):
                try:
                    ingested_at = datetime.fromisoformat(data["ingested_at"])
                except ValueError:
                    pass

            return IngestedEpisode(
                episode=episode,
                transcript=transcript,
                summary=summary,
                ingested_at=ingested_at,
                cached=True,
            )

        except Exception as e:
            logger.debug(f"Error loading cached episode: {e}")
            return None

    def _save_to_cache(self, result: IngestedEpisode):
        """Save ingested episode to cache."""
        cache_path = self._get_cache_path(result.episode)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2)
        except Exception as e:
            logger.debug(f"Error saving to cache: {e}")

    def ingest(
        self,
        episode: Episode,
        skip_cache: bool = False,
        summary_style: Optional[str] = None,
        generate_chapters: bool = False,
    ) -> IngestedEpisode:
        """Run full ingest pipeline on a single episode.

        Args:
            episode: Episode to ingest.
            skip_cache: If True, ignore cached results.
            summary_style: Override default summary style.
            generate_chapters: If True, generate chapter markers.

        Returns:
            IngestedEpisode with transcript and summary.
        """
        style = summary_style or self.summary_style

        # Check cache
        if not skip_cache:
            cached = self._load_cached(episode)
            if cached:
                logger.info(f"Using cached ingest for: {episode.title[:50]}...")
                return cached

        logger.info(f"Ingesting episode: {episode.title[:50]}...")

        # Step 1: Transcribe
        logger.info("  → Transcribing...")
        transcript = self.transcriber.transcribe_episode(episode, skip_cache=skip_cache)

        if not transcript.text:
            logger.warning(f"  → Transcription failed for: {episode.title}")
            return IngestedEpisode(
                episode=episode,
                transcript=transcript,
                summary=SummaryResult(summary="Transcription failed.", style=style),
            )

        logger.info(f"  → Transcribed {transcript.word_count} words")

        # Step 2: Summarize
        logger.info("  → Summarizing...")
        summary = self.summarizer.summarize(transcript, episode, style=style)

        # Step 3: Generate chapters if requested
        if generate_chapters and not summary.chapters:
            logger.info("  → Generating chapters...")
            chapters = self.summarizer.generate_chapters(transcript)
            summary.chapters = chapters

        logger.info(f"  → Generated {style} summary with {len(summary.key_topics)} topics")

        # Create result
        result = IngestedEpisode(
            episode=episode,
            transcript=transcript,
            summary=summary,
        )

        # Update episode with AI-generated content
        episode.transcript = transcript.text
        episode.ai_summary = summary.summary
        episode.key_topics = summary.key_topics
        episode.chapters = [ch.to_dict() for ch in summary.chapters]

        # Save to cache
        self._save_to_cache(result)

        # Optionally save individual files
        if self.save_transcripts:
            self._save_transcript(episode, transcript)
        if self.save_summaries:
            self._save_summary(episode, summary)

        return result

    def batch_ingest(
        self,
        episodes: List[Episode],
        max_parallel: int = 2,
        skip_existing: bool = True,
        summary_style: Optional[str] = None,
        progress_callback: Optional[callable] = None,
    ) -> List[IngestedEpisode]:
        """Batch process multiple episodes.

        Args:
            episodes: List of episodes to ingest.
            max_parallel: Maximum parallel ingestions (be careful with API rate limits).
            skip_existing: If True, skip episodes already in cache.
            summary_style: Override default summary style.
            progress_callback: Optional callback(current, total, episode) for progress.

        Returns:
            List of IngestedEpisode results.
        """
        results: List[IngestedEpisode] = []
        total = len(episodes)

        # Filter to only episodes not in cache if skip_existing
        to_process = []
        for ep in episodes:
            if skip_existing:
                cached = self._load_cached(ep)
                if cached:
                    results.append(cached)
                    if progress_callback:
                        progress_callback(len(results), total, ep)
                    continue
            to_process.append(ep)

        if not to_process:
            logger.info(f"All {total} episodes already cached")
            return results

        logger.info(f"Processing {len(to_process)} episodes ({total - len(to_process)} cached)")

        # Process with limited parallelism
        # Note: Transcription can be CPU/GPU intensive, so we limit parallelism
        if max_parallel <= 1:
            # Sequential processing
            for ep in to_process:
                try:
                    result = self.ingest(ep, skip_cache=True, summary_style=summary_style)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to ingest {ep.title}: {e}")
                    results.append(IngestedEpisode(
                        episode=ep,
                        transcript=TranscriptResult(text=""),
                        summary=SummaryResult(summary=f"Ingest failed: {e}"),
                    ))
                if progress_callback:
                    progress_callback(len(results), total, ep)
        else:
            # Parallel processing
            with ThreadPoolExecutor(max_workers=max_parallel) as executor:
                futures = {
                    executor.submit(self.ingest, ep, True, summary_style): ep
                    for ep in to_process
                }
                for future in as_completed(futures):
                    ep = futures[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Failed to ingest {ep.title}: {e}")
                        results.append(IngestedEpisode(
                            episode=ep,
                            transcript=TranscriptResult(text=""),
                            summary=SummaryResult(summary=f"Ingest failed: {e}"),
                        ))
                    if progress_callback:
                        progress_callback(len(results), total, ep)

        return results

    def _save_transcript(self, episode: Episode, transcript: TranscriptResult):
        """Save transcript to a separate file."""
        transcripts_dir = self.cache_dir / "transcripts"
        transcripts_dir.mkdir(exist_ok=True)

        safe_name = "".join(c if c.isalnum() else "_" for c in episode.title)[:60]
        filepath = transcripts_dir / f"{safe_name}.txt"

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {episode.title}\n")
                f.write(f"# Podcast: {episode.podcast_name}\n")
                f.write(f"# URL: {episode.url}\n")
                f.write(f"# Duration: {episode.duration_formatted}\n")
                f.write(f"# Transcribed with: {transcript.model_used}\n\n")

                if transcript.segments:
                    for seg in transcript.segments:
                        f.write(f"[{seg.start_formatted}] {seg.text}\n\n")
                else:
                    f.write(transcript.text)

            logger.debug(f"Saved transcript to {filepath}")
        except Exception as e:
            logger.debug(f"Error saving transcript: {e}")

    def _save_summary(self, episode: Episode, summary: SummaryResult):
        """Save summary to a separate file."""
        summaries_dir = self.cache_dir / "summaries"
        summaries_dir.mkdir(exist_ok=True)

        safe_name = "".join(c if c.isalnum() else "_" for c in episode.title)[:60]
        filepath = summaries_dir / f"{safe_name}.md"

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {episode.title}\n\n")
                f.write(f"**Podcast:** {episode.podcast_name}  \n")
                f.write(f"**URL:** {episode.url}  \n")
                if episode.duration_formatted:
                    f.write(f"**Duration:** {episode.duration_formatted}  \n")
                f.write(f"**Summarized with:** {summary.model_used}  \n\n")
                f.write("---\n\n")
                f.write(summary.to_markdown())

            logger.debug(f"Saved summary to {filepath}")
        except Exception as e:
            logger.debug(f"Error saving summary: {e}")

    def list_cached(self) -> List[str]:
        """List all cached episode titles."""
        cached = []
        for path in self.cache_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cached.append(data.get("episode", {}).get("title", path.stem))
            except Exception:
                cached.append(path.stem)
        return cached

    def clear_cache(self) -> int:
        """Clear all cached ingested episodes. Returns count of files removed."""
        count = 0
        for path in self.cache_dir.glob("*.json"):
            try:
                path.unlink()
                count += 1
            except Exception:
                pass
        return count
