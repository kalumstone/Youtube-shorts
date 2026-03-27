"""
Caption Sync
============
Uses faster-whisper to transcribe the voiceover audio and get
word-level timestamps, then groups them into TikTok-style caption
chunks (2-3 words at a time) with exact start/end times.

Falls back to evenly-spaced script lines if faster-whisper is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from loguru import logger


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CaptionChunk:
    text: str
    start: float   # seconds
    end: float     # seconds

    @property
    def duration(self) -> float:
        return max(self.end - self.start, 0.1)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transcribe_voiceover(
    audio_path: Path,
    words_per_chunk: int = 3,
    model_size: str = "base",
) -> list[CaptionChunk]:
    """
    Transcribe a voiceover file and return timed caption chunks.

    Parameters
    ----------
    audio_path : Path
        Voiceover .mp3 / .wav file.
    words_per_chunk : int
        How many words per caption card (2-3 looks best on screen).
    model_size : str
        faster-whisper model: "tiny", "base", "small", "medium".
        "base" is a good balance of speed and accuracy.

    Returns
    -------
    list[CaptionChunk]
        Time-stamped caption chunks ready to burn onto video.
    """
    if not audio_path or not audio_path.exists():
        logger.warning("No audio file for transcription")
        return []

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.warning("faster-whisper not installed — using fallback captions")
        return []

    logger.info(f"🎤 Transcribing voiceover ({model_size} model)…")

    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(
            str(audio_path),
            word_timestamps=True,
            language="en",
        )

        words: list[tuple[str, float, float]] = []
        for segment in segments:
            for word in (segment.words or []):
                clean = word.word.strip()
                if clean:
                    words.append((clean, word.start, word.end))

        if not words:
            logger.warning("Transcription returned no words")
            return []

        chunks = _group_into_chunks(words, words_per_chunk)
        logger.info(f"  ✅ {len(chunks)} caption chunks from {len(words)} words")
        return chunks

    except Exception as exc:
        logger.warning(f"Transcription failed: {exc}")
        return []


def fallback_captions(
    script_lines: list[str],
    total_duration: float,
    words_per_chunk: int = 3,
) -> list[CaptionChunk]:
    """
    Build evenly-spaced caption chunks from script lines when
    faster-whisper is unavailable.
    """
    if not script_lines or total_duration <= 0:
        return []

    # Split all lines into individual words
    all_words = []
    for line in script_lines:
        all_words.extend(line.split())

    if not all_words:
        return []

    secs_per_word = total_duration / len(all_words)
    chunks = []
    i = 0
    t = 0.0

    while i < len(all_words):
        chunk_words = all_words[i : i + words_per_chunk]
        start = t
        end = t + secs_per_word * len(chunk_words)
        chunks.append(CaptionChunk(
            text=" ".join(chunk_words),
            start=start,
            end=min(end, total_duration),
        ))
        t = end
        i += words_per_chunk

    return chunks


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _group_into_chunks(
    words: list[tuple[str, float, float]],
    words_per_chunk: int,
) -> list[CaptionChunk]:
    """Group word tuples (text, start, end) into fixed-size chunks."""
    chunks = []
    for i in range(0, len(words), words_per_chunk):
        group = words[i : i + words_per_chunk]
        text = " ".join(w[0] for w in group)
        start = group[0][1]
        end = group[-1][2]
        # Small gap between chunks so they don't bleed together
        end = min(end, start + 2.5)
        chunks.append(CaptionChunk(text=text, start=start, end=end))
    return chunks
