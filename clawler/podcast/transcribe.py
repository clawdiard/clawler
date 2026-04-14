"""Podcast transcription module using Whisper."""
import hashlib
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from clawler.models import Episode

logger = logging.getLogger(__name__)

# Cache directory for transcripts
DEFAULT_CACHE_DIR = Path.home() / ".clawler" / "podcast_cache" / "transcripts"


@dataclass
class TranscriptSegment:
    """A timestamped segment of transcript."""
    start_seconds: float
    end_seconds: float
    text: str

    @property
    def start_formatted(self) -> str:
        """Format start time as HH:MM:SS."""
        hours, remainder = divmod(int(self.start_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def to_dict(self) -> dict:
        return {
            "start": self.start_seconds,
            "end": self.end_seconds,
            "start_formatted": self.start_formatted,
            "text": self.text,
        }


@dataclass
class TranscriptResult:
    """Result of podcast transcription."""
    text: str                                   # Full transcript text
    segments: List[TranscriptSegment] = field(default_factory=list)
    language: str = "en"
    duration_seconds: float = 0.0
    model_used: str = ""
    cached: bool = False

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "segments": [s.to_dict() for s in self.segments],
            "language": self.language,
            "duration_seconds": self.duration_seconds,
            "word_count": self.word_count,
            "model_used": self.model_used,
        }


class PodcastTranscriber:
    """Transcribe podcast audio using OpenAI Whisper.

    Supports both local Whisper (via openai-whisper or faster-whisper)
    and OpenAI's API-based transcription.
    """

    SUPPORTED_MODELS = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]

    def __init__(
        self,
        model: str = "base",
        device: str = "auto",
        language: str = "en",
        use_api: bool = False,
        cache_dir: Optional[str] = None,
    ):
        """Initialize transcriber.

        Args:
            model: Whisper model size (tiny, base, small, medium, large).
            device: Device to use (auto, cpu, cuda, mps).
            language: Language code for transcription.
            use_api: If True, use OpenAI API instead of local model.
            cache_dir: Directory to cache transcripts.
        """
        self.model_name = model if model in self.SUPPORTED_MODELS else "base"
        self.device = device
        self.language = language
        self.use_api = use_api
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._whisper_model = None
        self._api_key = os.environ.get("OPENAI_API_KEY", "")

    def _get_cache_key(self, audio_url: str) -> str:
        """Generate cache key from audio URL."""
        return hashlib.md5(audio_url.encode()).hexdigest()

    def _get_cached_transcript(self, cache_key: str) -> Optional[TranscriptResult]:
        """Load transcript from cache if exists."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                segments = [
                    TranscriptSegment(
                        start_seconds=s["start"],
                        end_seconds=s["end"],
                        text=s["text"],
                    )
                    for s in data.get("segments", [])
                ]
                return TranscriptResult(
                    text=data["text"],
                    segments=segments,
                    language=data.get("language", "en"),
                    duration_seconds=data.get("duration_seconds", 0),
                    model_used=data.get("model_used", ""),
                    cached=True,
                )
            except Exception as e:
                logger.debug(f"Error loading cached transcript: {e}")
        return None

    def _save_to_cache(self, cache_key: str, result: TranscriptResult):
        """Save transcript to cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2)
        except Exception as e:
            logger.debug(f"Error saving transcript to cache: {e}")

    def transcribe_url(self, audio_url: str, skip_cache: bool = False) -> TranscriptResult:
        """Download audio from URL and transcribe.

        Args:
            audio_url: URL to audio/video file.
            skip_cache: If True, ignore cached transcript.

        Returns:
            TranscriptResult with full transcript and segments.
        """
        cache_key = self._get_cache_key(audio_url)

        # Check cache first
        if not skip_cache:
            cached = self._get_cached_transcript(cache_key)
            if cached:
                logger.info(f"Using cached transcript for {audio_url[:50]}...")
                return cached

        # Download audio
        audio_path = self._download_audio(audio_url)
        if not audio_path:
            return TranscriptResult(text="", model_used=self.model_name)

        try:
            result = self.transcribe(audio_path)
            # Cache the result
            self._save_to_cache(cache_key, result)
            return result
        finally:
            # Clean up downloaded file
            if audio_path and Path(audio_path).exists():
                try:
                    Path(audio_path).unlink()
                except Exception:
                    pass

    def transcribe(self, audio_path: str) -> TranscriptResult:
        """Transcribe a local audio file.

        Args:
            audio_path: Path to local audio file.

        Returns:
            TranscriptResult with full transcript and segments.
        """
        if self.use_api and self._api_key:
            return self._transcribe_api(audio_path)
        return self._transcribe_local(audio_path)

    def _transcribe_local(self, audio_path: str) -> TranscriptResult:
        """Transcribe using local Whisper model."""
        try:
            # Try faster-whisper first (much faster with CTranslate2)
            return self._transcribe_faster_whisper(audio_path)
        except ImportError:
            pass

        try:
            # Fall back to openai-whisper
            return self._transcribe_openai_whisper(audio_path)
        except ImportError:
            logger.error(
                "No Whisper library found. Install with: "
                "pip install faster-whisper  OR  pip install openai-whisper"
            )
            return TranscriptResult(text="", model_used=self.model_name)

    def _transcribe_faster_whisper(self, audio_path: str) -> TranscriptResult:
        """Transcribe using faster-whisper (CTranslate2)."""
        from faster_whisper import WhisperModel

        # Determine compute type based on device
        device = self.device
        if device == "auto":
            # Try to detect CUDA/MPS without requiring torch
            try:
                import torch
                if torch.cuda.is_available():
                    device = "cuda"
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    device = "cpu"  # faster-whisper doesn't support MPS directly
                else:
                    device = "cpu"
            except ImportError:
                device = "cpu"  # Default to CPU if torch not available

        compute_type = "float16" if device == "cuda" else "int8"

        logger.info(f"Loading faster-whisper model '{self.model_name}' on {device}...")
        model = WhisperModel(self.model_name, device=device, compute_type=compute_type)

        logger.info(f"Transcribing {audio_path}...")
        segments_gen, info = model.transcribe(
            audio_path,
            language=self.language if self.language != "auto" else None,
            beam_size=5,
            vad_filter=True,
        )

        segments = []
        full_text_parts = []
        for segment in segments_gen:
            segments.append(TranscriptSegment(
                start_seconds=segment.start,
                end_seconds=segment.end,
                text=segment.text.strip(),
            ))
            full_text_parts.append(segment.text.strip())

        return TranscriptResult(
            text=" ".join(full_text_parts),
            segments=segments,
            language=info.language,
            duration_seconds=info.duration,
            model_used=f"faster-whisper/{self.model_name}",
        )

    def _transcribe_openai_whisper(self, audio_path: str) -> TranscriptResult:
        """Transcribe using openai-whisper."""
        import whisper

        device = self.device
        if device == "auto":
            import torch
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"

        logger.info(f"Loading whisper model '{self.model_name}' on {device}...")
        model = whisper.load_model(self.model_name, device=device)

        logger.info(f"Transcribing {audio_path}...")
        result = model.transcribe(
            audio_path,
            language=self.language if self.language != "auto" else None,
            verbose=False,
        )

        segments = []
        for seg in result.get("segments", []):
            segments.append(TranscriptSegment(
                start_seconds=seg["start"],
                end_seconds=seg["end"],
                text=seg["text"].strip(),
            ))

        # Calculate duration from last segment
        duration = segments[-1].end_seconds if segments else 0.0

        return TranscriptResult(
            text=result.get("text", "").strip(),
            segments=segments,
            language=result.get("language", self.language),
            duration_seconds=duration,
            model_used=f"openai-whisper/{self.model_name}",
        )

    def _transcribe_api(self, audio_path: str) -> TranscriptResult:
        """Transcribe using OpenAI Whisper API."""
        import requests

        logger.info(f"Transcribing via OpenAI API: {audio_path}...")

        # Check file size (API limit is 25MB)
        file_size = Path(audio_path).stat().st_size
        if file_size > 25 * 1024 * 1024:
            logger.warning("File too large for API (>25MB), falling back to local")
            return self._transcribe_local(audio_path)

        try:
            with open(audio_path, "rb") as f:
                response = requests.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    files={"file": f},
                    data={
                        "model": "whisper-1",
                        "language": self.language if self.language != "auto" else "",
                        "response_format": "verbose_json",
                    },
                    timeout=300,
                )
                response.raise_for_status()
                data = response.json()

            segments = []
            for seg in data.get("segments", []):
                segments.append(TranscriptSegment(
                    start_seconds=seg.get("start", 0),
                    end_seconds=seg.get("end", 0),
                    text=seg.get("text", "").strip(),
                ))

            return TranscriptResult(
                text=data.get("text", "").strip(),
                segments=segments,
                language=data.get("language", self.language),
                duration_seconds=data.get("duration", 0),
                model_used="openai-api/whisper-1",
            )
        except Exception as e:
            logger.error(f"OpenAI API transcription failed: {e}")
            return TranscriptResult(text="", model_used="openai-api/whisper-1")

    def _is_direct_audio_url(self, url: str) -> bool:
        """Check if URL is a direct audio file (MP3, M4A, etc.)."""
        # Check URL path for audio extensions
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path_lower = parsed.path.lower()
        audio_exts = ('.mp3', '.m4a', '.wav', '.ogg', '.opus', '.aac', '.flac')
        if any(path_lower.endswith(ext) for ext in audio_exts):
            return True
        # Common podcast hosting patterns (even without extension in path)
        audio_hosts = ('pdst.fm', 'megaphone.fm', 'traffic.megaphone.fm', 'anchor.fm',
                       'buzzsprout.com', 'simplecast.com', 'libsyn.com', 'omnycontent.com',
                       'omny.fm', 'podbean.com', 'spreaker.com', 'captivate.fm', 'chrt.fm')
        if any(h in parsed.netloc for h in audio_hosts):
            return True
        return False

    def _download_direct_audio(self, url: str) -> Optional[str]:
        """Download audio directly via HTTP (for direct MP3/audio URLs)."""
        import requests

        try:
            logger.info(f"Direct downloading audio from {url[:60]}...")

            # Create temp file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                output_path = tmp.name

            # Stream download with timeout
            response = requests.get(url, stream=True, timeout=300, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            response.raise_for_status()

            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'audio' not in content_type and 'octet-stream' not in content_type:
                logger.debug(f"Unexpected content-type: {content_type}, trying anyway...")

            # Download in chunks
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            # Verify file was downloaded
            if Path(output_path).exists() and Path(output_path).stat().st_size > 1000:
                logger.info(f"Downloaded {Path(output_path).stat().st_size / 1024 / 1024:.1f}MB")
                return output_path

            logger.error("Downloaded file too small or missing")
            return None

        except Exception as e:
            logger.error(f"Direct download failed: {e}")
            return None

    def _download_audio(self, url: str) -> Optional[str]:
        """Download audio from URL - tries direct download first, then yt-dlp."""
        # Try direct download for audio URLs (faster, no yt-dlp dependency)
        if self._is_direct_audio_url(url):
            result = self._download_direct_audio(url)
            if result:
                return result
            logger.debug("Direct download failed, falling back to yt-dlp...")

        # Fall back to yt-dlp for YouTube, web pages, etc.
        try:
            # Create temp file for audio
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                output_path = tmp.name

            # Use yt-dlp to download audio
            cmd = [
                "yt-dlp",
                "-x",  # Extract audio
                "--audio-format", "mp3",
                "--audio-quality", "0",  # Best quality
                "-o", output_path.replace(".mp3", ".%(ext)s"),
                "--no-playlist",
                "--quiet",
                url,
            ]

            logger.info(f"Downloading audio via yt-dlp from {url[:50]}...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode != 0:
                logger.error(f"yt-dlp failed: {result.stderr}")
                return None

            # Find the actual output file (yt-dlp may change extension)
            output_dir = Path(output_path).parent
            base_name = Path(output_path).stem.replace(".%(ext)s", "")
            for ext in [".mp3", ".m4a", ".webm", ".opus", ".wav"]:
                candidate = output_dir / f"{base_name}{ext}"
                if candidate.exists():
                    return str(candidate)

            # Check if original path exists
            if Path(output_path).exists():
                return output_path

            logger.error("Downloaded audio file not found")
            return None

        except subprocess.TimeoutExpired:
            logger.error("Audio download timed out")
            return None
        except FileNotFoundError:
            logger.error("yt-dlp not found. Install with: pip install yt-dlp")
            return None
        except Exception as e:
            logger.error(f"Audio download failed: {e}")
            return None

    def transcribe_episode(self, episode: Episode, skip_cache: bool = False) -> TranscriptResult:
        """Transcribe a podcast episode.

        Args:
            episode: Episode to transcribe.
            skip_cache: If True, ignore cached transcript.

        Returns:
            TranscriptResult with full transcript and segments.
        """
        # Prefer audio_url if available, otherwise use main URL (works for YouTube)
        url = episode.audio_url or episode.url
        if not url:
            logger.warning(f"No URL available for episode: {episode.title}")
            return TranscriptResult(text="", model_used=self.model_name)

        return self.transcribe_url(url, skip_cache=skip_cache)
