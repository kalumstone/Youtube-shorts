"""
Voiceover Generator
===================
Converts a text script into an audio file using either:
  - ElevenLabs (premium, realistic voices) — if ELEVENLABS_API_KEY is set
  - gTTS (Google Text-to-Speech, free) — fallback

Also uses Claude to write the voiceover script from a niche + content angle.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

import anthropic
from loguru import logger

import config

# ---------------------------------------------------------------------------
# Script generation
# ---------------------------------------------------------------------------

def generate_script(
    niche: str,
    content_angle: str,
    duration_seconds: int = 45,
    tone: str = "energetic and engaging",
) -> tuple[str, list[str]]:
    """
    Use Claude to write a short voiceover script optimised for Shorts.

    Returns
    -------
    tuple[str, list[str]]
        (full_script_text, list_of_lines_for_captions)
    """
    logger.info(f"📝 Writing script for niche='{niche}', angle='{content_angle}'…")

    word_count = int(duration_seconds * 2.3)   # ~138 wpm reading pace

    prompt = f"""You are a viral YouTube Shorts scriptwriter.

Write a SHORT voiceover script for a YouTube Short about:
- Niche: {niche}
- Content angle / topic: {content_angle}
- Tone: {tone}
- Target duration: {duration_seconds} seconds (~{word_count} words)

Rules:
1. Start with a POWERFUL hook in the first 3 words (make viewers stay)
2. Keep sentences short — one idea per line
3. Build curiosity or value quickly
4. End with a clear call-to-action ("Follow for more!", "Comment below!", etc.)
5. Write for speech — no hashtags, no markdown, no bullet points in the text

Return ONLY a JSON object:
{{
  "full_script": "The complete script as one paragraph for TTS",
  "lines": ["Hook line", "Line 2", "Line 3", ..., "CTA line"],
  "hook": "The opening hook sentence only",
  "cta": "The call-to-action sentence only"
}}

Return ONLY valid JSON, nothing else.
"""

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    import json
    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    try:
        data = json.loads(raw)
        full_script = data.get("full_script", "")
        lines = data.get("lines", [full_script])
        logger.info(f"  Script ready ({len(full_script.split())} words)")
        return full_script, lines
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning(f"Script parse error: {exc} — using raw text")
        return raw, [raw]


# ---------------------------------------------------------------------------
# Audio rendering
# ---------------------------------------------------------------------------

def generate_voiceover(
    script: str,
    output_path: Optional[Path] = None,
) -> Path:
    """
    Convert `script` text to an audio file.

    Provider is chosen by VOICE_PROVIDER env variable:
      "elevenlabs" → ElevenLabs API (high quality)
      "gtts"       → Google TTS (free)

    Returns
    -------
    Path
        Path to the generated .mp3 file.
    """
    config.EDITED_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        output_path = config.EDITED_DIR / f"vo_{uuid.uuid4().hex[:8]}.mp3"

    provider = config.VOICE_PROVIDER.lower()
    logger.info(f"🎙  Generating voiceover via {provider}…")

    if provider == "elevenlabs" and config.ELEVENLABS_API_KEY:
        _render_elevenlabs(script, output_path)
    else:
        if provider == "elevenlabs":
            logger.warning("ElevenLabs API key not set — falling back to gTTS")
        _render_gtts(script, output_path)

    logger.info(f"  ✅ Voiceover saved: {output_path.name}")
    return output_path


# ---------------------------------------------------------------------------
# ElevenLabs
# ---------------------------------------------------------------------------

def _render_elevenlabs(script: str, output_path: Path) -> None:
    try:
        from elevenlabs.client import ElevenLabs
        from elevenlabs import save

        client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)
        audio = client.generate(
            text=script,
            voice=config.ELEVENLABS_VOICE_ID,
            model="eleven_multilingual_v2",
        )
        save(audio, str(output_path))
    except ImportError:
        logger.warning("elevenlabs package not installed — falling back to gTTS")
        _render_gtts(script, output_path)
    except Exception as exc:
        logger.error(f"ElevenLabs error: {exc} — falling back to gTTS")
        _render_gtts(script, output_path)


# ---------------------------------------------------------------------------
# gTTS (free fallback)
# ---------------------------------------------------------------------------

def _render_gtts(script: str, output_path: Path) -> None:
    try:
        from gtts import gTTS

        tts = gTTS(text=script, lang=config.TTS_LANGUAGE, slow=False)
        tts.save(str(output_path))
    except ImportError as exc:
        raise ImportError("gTTS is required: pip install gTTS") from exc
    except Exception as exc:
        raise RuntimeError(f"gTTS rendering failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Convenience: write script + render in one call
# ---------------------------------------------------------------------------

def create_voiceover_from_niche(
    niche: str,
    content_angle: str,
    duration_seconds: int = 45,
) -> tuple[Path, str, list[str], str, str]:
    """
    Full pipeline: write script → render audio.

    Returns
    -------
    tuple[Path, str, list[str], str, str]
        (audio_path, full_script, lines, hook_text, cta_text)
    """
    import json

    # Generate script
    prompt = f"""You are a viral YouTube Shorts scriptwriter.

Write a SHORT voiceover script for a YouTube Short about:
- Niche: {niche}
- Content angle / topic: {content_angle}
- Target duration: {duration_seconds} seconds

Rules:
1. Start with a POWERFUL hook in the first 3 words
2. Keep sentences short
3. End with a clear CTA

Return ONLY a JSON object:
{{
  "full_script": "Complete script for TTS",
  "lines": ["Hook line", "Line 2", ..., "CTA line"],
  "hook": "Opening hook only",
  "cta": "CTA sentence only"
}}"""

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        lines_raw = raw.split("\n")
        raw = "\n".join(lines_raw[1:-1]) if lines_raw[-1].strip() == "```" else "\n".join(lines_raw[1:])

    try:
        data = json.loads(raw)
        full_script = data.get("full_script", "")
        lines = data.get("lines", [])
        hook = data.get("hook", "")
        cta = data.get("cta", "Follow for more!")
    except Exception:
        full_script = raw
        lines = [raw]
        hook = ""
        cta = "Follow for more!"

    audio_path = generate_voiceover(full_script)
    return audio_path, full_script, lines, hook, cta
