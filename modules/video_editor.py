"""
Video Editor
============
Takes raw clips + a voiceover audio file and produces a polished
YouTube Short (1080×1920, ≤60 s) with:
  - Auto-crop / resize to vertical 9:16
  - Trim to target duration
  - Burned-in subtitles / captions
  - Animated text overlays (hook at start, CTA at end)
  - Optional background music at low volume
  - Watermark
  - Smooth fade-in / fade-out
"""

from __future__ import annotations

import os
import textwrap
import uuid
from pathlib import Path
from typing import Optional

from loguru import logger

import config

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field

@dataclass
class EditedVideo:
    path: Path
    duration: float
    title: str = ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def edit_clip(
    clip_path: Path,
    voiceover_path: Optional[Path] = None,
    script_lines: Optional[list[str]] = None,
    hook_text: str = "",
    cta_text: str = "Follow for more!",
    background_music_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> EditedVideo:
    """
    Produce a finished YouTube Short from a raw clip.

    Parameters
    ----------
    clip_path : Path
        Source video file.
    voiceover_path : Path, optional
        Pre-rendered voiceover audio file (.mp3 / .wav).
    script_lines : list[str], optional
        Lines of the script to burn as on-screen captions.
    hook_text : str
        Bold text shown in the first 2 seconds (the "hook").
    cta_text : str
        Call-to-action text shown in the last 2 seconds.
    background_music_path : Path, optional
        Background music audio file.
    output_path : Path, optional
        Where to save the final video. Auto-generated if None.

    Returns
    -------
    EditedVideo
    """
    try:
        from moviepy.editor import (
            VideoFileClip,
            AudioFileClip,
            CompositeVideoClip,
            CompositeAudioClip,
            TextClip,
            ColorClip,
        )
        import numpy as np
    except ImportError as exc:
        raise ImportError("moviepy is required: pip install moviepy") from exc

    config.EDITED_DIR.mkdir(parents=True, exist_ok=True)
    config.FINAL_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        output_path = config.FINAL_DIR / f"short_{uuid.uuid4().hex[:8]}.mp4"

    logger.info(f"✂️  Editing clip: {clip_path.name} → {output_path.name}")

    # ── 1. Load & trim source clip ───────────────────────────────────────────
    clip = VideoFileClip(str(clip_path), audio=voiceover_path is None)
    target_duration = _target_duration(clip.duration, voiceover_path)
    if clip.duration > target_duration:
        clip = clip.subclip(0, target_duration)

    # ── 2. Resize to 9:16 vertical (1080×1920) ───────────────────────────────
    clip = _to_vertical(clip)

    # ── 3. Swap audio to voiceover if provided ──────────────────────────────
    if voiceover_path and voiceover_path.exists():
        vo_audio = AudioFileClip(str(voiceover_path))
        if vo_audio.duration > clip.duration:
            vo_audio = vo_audio.subclip(0, clip.duration)
        clip = clip.set_audio(vo_audio)

    # ── 4. Add background music (low volume) ────────────────────────────────
    if background_music_path and background_music_path.exists():
        clip = _mix_background_music(clip, background_music_path)

    # ── 5. Build overlays ───────────────────────────────────────────────────
    overlays: list = [clip]

    # Hook overlay (first 2.5 s)
    if hook_text:
        hook = _make_text_overlay(
            hook_text,
            duration=min(2.5, clip.duration),
            start=0,
            fontsize=72,
            color="white",
            stroke_color="black",
            stroke_width=3,
            position=("center", 0.18),
            size=(config.VIDEO_WIDTH - 80, None),
        )
        if hook:
            overlays.append(hook)

    # Captions / subtitles
    if script_lines:
        caption_clips = _build_captions(script_lines, clip.duration)
        overlays.extend(caption_clips)

    # CTA overlay (last 2.5 s)
    if cta_text and clip.duration > 5:
        cta_start = clip.duration - 2.5
        cta = _make_text_overlay(
            cta_text,
            duration=2.5,
            start=cta_start,
            fontsize=56,
            color="yellow",
            stroke_color="black",
            stroke_width=2,
            position=("center", 0.82),
            size=(config.VIDEO_WIDTH - 80, None),
        )
        if cta:
            overlays.append(cta)

    # Watermark
    if config.WATERMARK_TEXT:
        wm = _make_text_overlay(
            config.WATERMARK_TEXT,
            duration=clip.duration,
            start=0,
            fontsize=30,
            color="white",
            stroke_color="black",
            stroke_width=1,
            position=(30, 30),
            size=(400, None),
        )
        if wm:
            overlays.append(wm)

    # ── 6. Composite & fade ─────────────────────────────────────────────────
    final = CompositeVideoClip(overlays, size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT))
    final = final.fadein(0.4).fadeout(0.4)

    # ── 7. Export ───────────────────────────────────────────────────────────
    logger.info(f"  🎞  Rendering → {output_path}  ({final.duration:.1f}s)")
    final.write_videofile(
        str(output_path),
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        bitrate="6000k",
        threads=os.cpu_count() or 4,
        logger=None,
    )

    clip.close()
    final.close()

    logger.info(f"  ✅ Edit complete: {output_path.name}")
    return EditedVideo(path=output_path, duration=final.duration)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _target_duration(clip_duration: float, voiceover_path: Optional[Path]) -> float:
    """Determine ideal Short duration."""
    if voiceover_path and voiceover_path.exists():
        try:
            from moviepy.editor import AudioFileClip
            vo = AudioFileClip(str(voiceover_path))
            vo_dur = vo.duration + 0.5          # slight buffer
            vo.close()
            return min(vo_dur, config.MAX_CLIP_DURATION)
        except Exception:
            pass
    return min(clip_duration, config.MAX_CLIP_DURATION)


def _to_vertical(clip):
    """
    Crop / resize a clip to 1080×1920 (9:16 portrait).
    Strategy: scale so height = 1920, then center-crop width to 1080.
    """
    from moviepy.editor import VideoFileClip
    from moviepy.video.fx.all import crop, resize

    target_w, target_h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    orig_w, orig_h = clip.size

    # Scale to fill height
    scale = target_h / orig_h
    new_w = int(orig_w * scale)
    new_h = target_h

    if new_w < target_w:
        # Not wide enough after height scale — scale by width instead
        scale = target_w / orig_w
        new_w = target_w
        new_h = int(orig_h * scale)

    clip = clip.resize((new_w, new_h))

    # Center-crop
    x_center = new_w / 2
    y_center = new_h / 2
    clip = clip.crop(
        x_center=x_center,
        y_center=y_center,
        width=target_w,
        height=target_h,
    )
    return clip


def _mix_background_music(video_clip, music_path: Path):
    """Mix low-volume background music under the video's existing audio."""
    try:
        from moviepy.editor import AudioFileClip, CompositeAudioClip

        music = AudioFileClip(str(music_path)).volumex(config.MUSIC_VOLUME)
        if music.duration < video_clip.duration:
            from moviepy.audio.fx.all import audio_loop
            music = audio_loop(music, duration=video_clip.duration)
        else:
            music = music.subclip(0, video_clip.duration)

        existing = video_clip.audio
        if existing:
            mixed = CompositeAudioClip([existing, music])
        else:
            mixed = music
        return video_clip.set_audio(mixed)
    except Exception as exc:
        logger.warning(f"Background music mix failed: {exc}")
        return video_clip


def _make_text_overlay(
    text: str,
    duration: float,
    start: float,
    fontsize: int,
    color: str,
    stroke_color: str,
    stroke_width: int,
    position,
    size,
):
    """Create a TextClip overlay. Returns None on failure."""
    try:
        from moviepy.editor import TextClip

        # Wrap long text
        wrapped = "\n".join(textwrap.wrap(text, width=28))

        tc = (
            TextClip(
                wrapped,
                fontsize=fontsize,
                color=color,
                font="DejaVu-Sans-Bold",
                stroke_color=stroke_color,
                stroke_width=stroke_width,
                method="caption",
                size=size,
                align="center",
            )
            .set_duration(duration)
            .set_start(start)
        )

        # Resolve position
        if isinstance(position, tuple) and isinstance(position[0], str):
            tc = tc.set_position(position)
        elif isinstance(position, tuple) and isinstance(position[1], float):
            # Fractional vertical position
            x_pos, y_frac = position
            y_pos = int(config.VIDEO_HEIGHT * y_frac - tc.size[1] / 2)
            tc = tc.set_position(("center", y_pos))
        else:
            tc = tc.set_position(position)

        return tc
    except Exception as exc:
        logger.warning(f"TextClip error ('{text[:30]}'): {exc}")
        return None


def _build_captions(script_lines: list[str], total_duration: float) -> list:
    """
    Evenly distribute script lines as caption overlays across the video.
    Returns a list of TextClip objects.
    """
    clips = []
    if not script_lines:
        return clips

    per_line = total_duration / len(script_lines)
    for i, line in enumerate(script_lines):
        start = i * per_line
        tc = _make_text_overlay(
            line,
            duration=per_line - 0.1,
            start=start,
            fontsize=52,
            color="white",
            stroke_color="black",
            stroke_width=2,
            position=("center", 0.72),
            size=(config.VIDEO_WIDTH - 60, None),
        )
        if tc:
            clips.append(tc)
    return clips
