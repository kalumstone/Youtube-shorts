"""
Video Editor
============
Produces a polished YouTube Short (1080×1920, ≤60 s) with:
  - Auto-crop / resize to 9:16 vertical
  - Trim to voiceover length
  - Dynamic zoom cuts every ~3-5 seconds (punchy, viral feel)
  - TikTok-style word-synced captions (2-3 words at a time, centered,
    white bold text + thick black stroke + semi-transparent backing bar)
  - Hook overlay (first 2 s) with animated scale-in
  - CTA overlay (last 2.5 s)
  - Background music mixed at low volume
  - Watermark
  - Smooth fade-in / fade-out
"""

from __future__ import annotations

import os
import random
import textwrap
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

import config
from modules.caption_sync import (
    CaptionChunk,
    transcribe_voiceover,
    fallback_captions,
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

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
        Pre-rendered voiceover .mp3 / .wav file.
    script_lines : list[str], optional
        Script lines used as fallback captions if transcription fails.
    hook_text : str
        Bold hook text shown for first 2 seconds.
    cta_text : str
        Call-to-action shown in the last 2.5 seconds.
    background_music_path : Path, optional
        Background music file.
    output_path : Path, optional
        Output file path. Auto-generated if None.

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
            ImageClip,
        )
    except ImportError as exc:
        raise ImportError("moviepy is required: pip install moviepy") from exc

    config.EDITED_DIR.mkdir(parents=True, exist_ok=True)
    config.FINAL_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        output_path = config.FINAL_DIR / f"short_{uuid.uuid4().hex[:8]}.mp4"

    logger.info(f"✂️  Editing: {clip_path.name} → {output_path.name}")

    # ── 1. Load & trim to voiceover length ──────────────────────────────────
    clip = VideoFileClip(str(clip_path), audio=(voiceover_path is None))
    target_dur = _target_duration(clip.duration, voiceover_path)
    if clip.duration > target_dur:
        clip = clip.subclip(0, target_dur)

    # ── 2. Resize to 9:16 (1080×1920) ───────────────────────────────────────
    clip = _to_vertical(clip)

    # ── 3. Apply dynamic zoom cuts ──────────────────────────────────────────
    clip = _apply_zoom_cuts(clip)

    # ── 4. Swap in voiceover audio ───────────────────────────────────────────
    if voiceover_path and voiceover_path.exists():
        vo_audio = AudioFileClip(str(voiceover_path))
        if vo_audio.duration > clip.duration:
            vo_audio = vo_audio.subclip(0, clip.duration)
        clip = clip.set_audio(vo_audio)

    # ── 5. Mix background music ──────────────────────────────────────────────
    if background_music_path and background_music_path.exists():
        clip = _mix_background_music(clip, background_music_path)

    # ── 6. Build caption chunks ──────────────────────────────────────────────
    caption_chunks: list[CaptionChunk] = []
    if voiceover_path and voiceover_path.exists():
        caption_chunks = transcribe_voiceover(voiceover_path, words_per_chunk=3)
    if not caption_chunks and script_lines:
        caption_chunks = fallback_captions(script_lines, clip.duration, words_per_chunk=3)

    # ── 7. Render all overlays ───────────────────────────────────────────────
    overlays: list = [clip]

    # Hook — large centred text for first 2 s
    if hook_text:
        hook_clips = _make_hook_overlay(hook_text, duration=min(2.2, clip.duration))
        overlays.extend(hook_clips)

    # TikTok-style word-synced captions
    caption_clips = _build_tiktok_captions(caption_chunks)
    overlays.extend(caption_clips)

    # CTA
    if cta_text and clip.duration > 5:
        cta_clips = _make_cta_overlay(cta_text, clip.duration)
        overlays.extend(cta_clips)

    # Watermark
    if config.WATERMARK_TEXT:
        wm = _make_simple_text(
            config.WATERMARK_TEXT,
            start=0,
            duration=clip.duration,
            fontsize=28,
            color="white",
            stroke_width=1,
            y_pos=50,
        )
        if wm:
            overlays.append(wm)

    # ── 8. Composite, fade, export ───────────────────────────────────────────
    final = CompositeVideoClip(overlays, size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT))
    final = final.fadein(0.3).fadeout(0.3)

    logger.info(f"  🎞  Rendering {final.duration:.1f}s → {output_path.name}")
    final.write_videofile(
        str(output_path),
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        bitrate="8000k",
        threads=os.cpu_count() or 4,
        logger=None,
    )

    clip.close()
    final.close()
    logger.info(f"  ✅ Done: {output_path.name}")
    return EditedVideo(path=output_path, duration=final.duration)


# ---------------------------------------------------------------------------
# Zoom cuts
# ---------------------------------------------------------------------------

def _apply_zoom_cuts(clip):
    """
    Split the clip into ~3-5 second segments and apply alternating
    zoom-in / zoom-out to each segment. This gives the punchy "cuts"
    feel that keeps viewers watching.
    """
    try:
        from moviepy.editor import concatenate_videoclips

        duration = clip.duration
        if duration < 4:
            return clip

        # Build segment boundaries (~3-4 s each, slight randomness)
        boundaries = [0.0]
        t = 0.0
        while t < duration - 2:
            step = random.uniform(2.8, 4.2)
            t = min(t + step, duration)
            boundaries.append(t)
        if boundaries[-1] < duration:
            boundaries.append(duration)

        segments = []
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            seg = clip.subclip(start, end)

            # Alternate zoom-in and zoom-out
            zoom_type = "in" if i % 2 == 0 else "out"
            seg = _zoom_segment(seg, zoom_type=zoom_type, zoom_amount=0.06)
            segments.append(seg)

        if not segments:
            return clip

        return concatenate_videoclips(segments, method="compose")

    except Exception as exc:
        logger.warning(f"Zoom cuts failed — using plain clip: {exc}")
        return clip


def _zoom_segment(clip, zoom_type: str = "in", zoom_amount: float = 0.06):
    """
    Apply a smooth Ken-Burns zoom to a clip segment using a per-frame
    resize effect.
    zoom_amount: how much to zoom (0.06 = 6% zoom over the segment)
    """
    try:
        duration = clip.duration

        def zoom_frame(get_frame, t):
            frame = get_frame(t)
            progress = t / duration if duration > 0 else 0

            if zoom_type == "in":
                scale = 1.0 + zoom_amount * progress
            else:
                scale = (1.0 + zoom_amount) - zoom_amount * progress

            h, w = frame.shape[:2]
            new_h = int(h * scale)
            new_w = int(w * scale)

            # Use PIL for resizing (fast and available via moviepy deps)
            from PIL import Image
            img = Image.fromarray(frame)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            arr = np.array(img)

            # Centre-crop back to original size
            y0 = (new_h - h) // 2
            x0 = (new_w - w) // 2
            return arr[y0:y0 + h, x0:x0 + w]

        return clip.fl(zoom_frame, apply_to=["mask"])
    except Exception as exc:
        logger.warning(f"Zoom segment error: {exc}")
        return clip


# ---------------------------------------------------------------------------
# TikTok-style captions
# ---------------------------------------------------------------------------

def _build_tiktok_captions(chunks: list[CaptionChunk]) -> list:
    """
    Render each caption chunk as a styled overlay:
      - Bold white text, thick black stroke
      - Semi-transparent dark pill/bar background
      - Positioned in lower-centre (70% down screen)
    """
    clips = []
    for chunk in chunks:
        c = _make_caption_clip(chunk)
        if c is not None:
            clips.append(c)
    return clips


def _make_caption_clip(chunk: CaptionChunk):
    """Render one caption chunk with a background bar."""
    try:
        from moviepy.editor import TextClip, ImageClip, CompositeVideoClip
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np

        text = chunk.text.upper()
        duration = chunk.duration
        start = chunk.start

        fontsize = 72
        pad_x, pad_y = 40, 20
        bar_opacity = 170    # 0-255
        bar_color = (0, 0, 0)

        # ── Render text to measure its size ─────────────────────────────────
        font = _load_font(fontsize)
        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)

        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        except AttributeError:
            # Older Pillow
            text_w, text_h = draw.textsize(text, font=font)

        # ── Build background bar ─────────────────────────────────────────────
        bar_w = min(text_w + pad_x * 2, config.VIDEO_WIDTH - 40)
        bar_h = text_h + pad_y * 2

        bar_img = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
        bar_draw = ImageDraw.Draw(bar_img)
        # Rounded rectangle
        radius = bar_h // 3
        bar_draw.rounded_rectangle(
            [(0, 0), (bar_w - 1, bar_h - 1)],
            radius=radius,
            fill=(*bar_color, bar_opacity),
        )

        # ── Draw text with thick stroke ──────────────────────────────────────
        stroke_width = 4
        tx = (bar_w - text_w) // 2
        ty = pad_y

        # Stroke (draw offset in 8 directions)
        for dx, dy in [(-stroke_width, 0), (stroke_width, 0),
                       (0, -stroke_width), (0, stroke_width),
                       (-stroke_width, -stroke_width), (stroke_width, stroke_width),
                       (-stroke_width, stroke_width), (stroke_width, -stroke_width)]:
            bar_draw.text((tx + dx, ty + dy), text, font=font, fill=(0, 0, 0, 255))

        # Main text
        bar_draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 255))

        # ── Position on frame ────────────────────────────────────────────────
        x_pos = (config.VIDEO_WIDTH - bar_w) // 2
        y_pos = int(config.VIDEO_HEIGHT * 0.70)

        arr = np.array(bar_img)
        caption_clip = (
            ImageClip(arr, ismask=False)
            .set_duration(duration)
            .set_start(start)
            .set_position((x_pos, y_pos))
        )
        return caption_clip

    except Exception as exc:
        logger.warning(f"Caption render error ('{chunk.text}'): {exc}")
        return None


def _load_font(size: int):
    """Load best available bold font."""
    from PIL import ImageFont

    candidates = [
        str(config.FONTS_DIR / "bold.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Impact.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Hook overlay
# ---------------------------------------------------------------------------

def _make_hook_overlay(text: str, duration: float) -> list:
    """
    Large, bold hook text in the upper third of the screen for the
    first `duration` seconds. Uses a Pillow-rendered image for better
    styling than MoviePy TextClip.
    """
    try:
        from moviepy.editor import ImageClip
        from PIL import Image, ImageDraw
        import numpy as np

        text_upper = text.upper()
        fontsize = 80
        font = _load_font(fontsize)
        max_width = config.VIDEO_WIDTH - 80
        pad = 24

        # Wrap text
        lines = _wrap_text_to_width(text_upper, font, max_width)

        # Measure
        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)
        line_heights = []
        line_widths = []
        for line in lines:
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                lw = bbox[2] - bbox[0]
                lh = bbox[3] - bbox[1]
            except AttributeError:
                lw, lh = draw.textsize(line, font=font)
            line_widths.append(lw)
            line_heights.append(lh)

        total_h = sum(line_heights) + (len(lines) - 1) * 12
        total_w = max(line_widths) if line_widths else 400

        img_w = min(total_w + pad * 2, config.VIDEO_WIDTH - 40)
        img_h = total_h + pad * 2

        img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Semi-transparent background
        draw.rounded_rectangle(
            [(0, 0), (img_w - 1, img_h - 1)],
            radius=img_h // 4,
            fill=(0, 0, 0, 160),
        )

        # Draw each line
        y = pad
        for line, lw, lh in zip(lines, line_widths, line_heights):
            x = (img_w - lw) // 2
            stroke = 5
            for dx, dy in [(-stroke, 0), (stroke, 0), (0, -stroke), (0, stroke),
                           (-stroke, -stroke), (stroke, stroke)]:
                draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 255))
            draw.text((x, y), line, font=font, fill=(255, 230, 0, 255))  # Yellow
            y += lh + 12

        arr = np.array(img)
        x_pos = (config.VIDEO_WIDTH - img_w) // 2
        y_pos = int(config.VIDEO_HEIGHT * 0.12)

        clip = (
            ImageClip(arr, ismask=False)
            .set_duration(duration)
            .set_start(0)
            .set_position((x_pos, y_pos))
            .crossfadein(0.2)
        )
        return [clip]

    except Exception as exc:
        logger.warning(f"Hook overlay error: {exc}")
        return []


# ---------------------------------------------------------------------------
# CTA overlay
# ---------------------------------------------------------------------------

def _make_cta_overlay(text: str, clip_duration: float) -> list:
    """Animated CTA bar sliding in from the bottom for the last 2.5 s."""
    try:
        from moviepy.editor import ImageClip
        from PIL import Image, ImageDraw
        import numpy as np

        cta_duration = 2.5
        cta_start = clip_duration - cta_duration
        fontsize = 56
        font = _load_font(fontsize)
        pad = 20

        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except AttributeError:
            tw, th = draw.textsize(text, font=font)

        img_w = min(tw + pad * 3, config.VIDEO_WIDTH - 40)
        img_h = th + pad * 2

        img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle(
            [(0, 0), (img_w - 1, img_h - 1)],
            radius=img_h // 2,
            fill=(255, 60, 60, 220),   # Red pill
        )
        x = (img_w - tw) // 2
        y = pad
        stroke = 2
        for dx, dy in [(-stroke, 0), (stroke, 0), (0, -stroke), (0, stroke)]:
            draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 200))
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

        arr = np.array(img)
        x_pos = (config.VIDEO_WIDTH - img_w) // 2
        y_pos = int(config.VIDEO_HEIGHT * 0.83)

        clip = (
            ImageClip(arr, ismask=False)
            .set_duration(cta_duration)
            .set_start(cta_start)
            .set_position((x_pos, y_pos))
            .crossfadein(0.3)
        )
        return [clip]

    except Exception as exc:
        logger.warning(f"CTA overlay error: {exc}")
        return []


# ---------------------------------------------------------------------------
# Simple text helper (watermark)
# ---------------------------------------------------------------------------

def _make_simple_text(
    text: str,
    start: float,
    duration: float,
    fontsize: int,
    color: str,
    stroke_width: int,
    y_pos: int,
):
    try:
        from moviepy.editor import TextClip
        tc = (
            TextClip(
                text,
                fontsize=fontsize,
                color=color,
                font="DejaVu-Sans-Bold",
                stroke_color="black",
                stroke_width=stroke_width,
            )
            .set_duration(duration)
            .set_start(start)
            .set_position(("right", y_pos))
            .set_opacity(0.6)
        )
        return tc
    except Exception as exc:
        logger.warning(f"Watermark error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Resize / crop helpers
# ---------------------------------------------------------------------------

def _to_vertical(clip):
    """Scale + center-crop to 1080×1920."""
    target_w, target_h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    orig_w, orig_h = clip.size

    scale = target_h / orig_h
    new_w = int(orig_w * scale)
    new_h = target_h

    if new_w < target_w:
        scale = target_w / orig_w
        new_w = target_w
        new_h = int(orig_h * scale)

    clip = clip.resize((new_w, new_h))
    clip = clip.crop(
        x_center=new_w / 2,
        y_center=new_h / 2,
        width=target_w,
        height=target_h,
    )
    return clip


def _target_duration(clip_duration: float, voiceover_path: Optional[Path]) -> float:
    if voiceover_path and voiceover_path.exists():
        try:
            from moviepy.editor import AudioFileClip
            vo = AudioFileClip(str(voiceover_path))
            dur = vo.duration + 0.5
            vo.close()
            return min(dur, config.MAX_CLIP_DURATION)
        except Exception:
            pass
    return min(clip_duration, config.MAX_CLIP_DURATION)


def _mix_background_music(video_clip, music_path: Path):
    try:
        from moviepy.editor import AudioFileClip, CompositeAudioClip
        from moviepy.audio.fx.all import audio_loop

        music = AudioFileClip(str(music_path)).volumex(config.MUSIC_VOLUME)
        if music.duration < video_clip.duration:
            music = audio_loop(music, duration=video_clip.duration)
        else:
            music = music.subclip(0, video_clip.duration)

        existing = video_clip.audio
        mixed = CompositeAudioClip([existing, music]) if existing else music
        return video_clip.set_audio(mixed)
    except Exception as exc:
        logger.warning(f"Music mix failed: {exc}")
        return video_clip


def _wrap_text_to_width(text: str, font, max_width: int) -> list[str]:
    """Wrap text so no line exceeds max_width pixels."""
    from PIL import ImageDraw, Image

    words = text.split()
    lines = []
    current = []
    draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    for word in words:
        test = " ".join(current + [word])
        try:
            bbox = draw.textbbox((0, 0), test, font=font)
            w = bbox[2] - bbox[0]
        except AttributeError:
            w, _ = draw.textsize(test, font=font)
        if w <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]

    if current:
        lines.append(" ".join(current))
    return lines or [text]
