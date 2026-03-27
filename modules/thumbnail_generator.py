"""
Thumbnail Generator
===================
Creates eye-catching YouTube Shorts thumbnails from a video frame +
bold overlay text using Pillow.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from loguru import logger

import config


def generate_thumbnail(
    video_path: Path,
    text: str,
    output_path: Optional[Path] = None,
    time_offset: float = 1.0,
) -> Optional[Path]:
    """
    Extract a frame from the video and add bold overlay text.

    Parameters
    ----------
    video_path : Path
        The finished Short video.
    text : str
        Text to overlay on the thumbnail.
    output_path : Path, optional
        Where to save the thumbnail image.
    time_offset : float
        Seconds into the video to capture the frame.

    Returns
    -------
    Path | None
    """
    try:
        from moviepy.editor import VideoFileClip
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
    except ImportError as exc:
        logger.warning(f"Thumbnail generation skipped: {exc}")
        return None

    if output_path is None:
        config.FINAL_DIR.mkdir(parents=True, exist_ok=True)
        output_path = config.FINAL_DIR / f"thumb_{uuid.uuid4().hex[:8]}.jpg"

    try:
        # Extract frame
        clip = VideoFileClip(str(video_path))
        t = min(time_offset, clip.duration - 0.1)
        frame = clip.get_frame(t)
        clip.close()

        img = Image.fromarray(frame)
        img = img.resize((config.VIDEO_WIDTH, config.VIDEO_HEIGHT), Image.LANCZOS)

        # Dark gradient overlay at top for text readability
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for y in range(0, 300):
            alpha = int(180 * (1 - y / 300))
            draw.line([(0, y), (config.VIDEO_WIDTH, y)], fill=(0, 0, 0, alpha))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

        # Add text
        draw = ImageDraw.Draw(img)
        _draw_text_with_shadow(draw, text, img.size)

        img.save(str(output_path), "JPEG", quality=95)
        logger.info(f"  🖼️  Thumbnail saved: {output_path.name}")
        return output_path

    except Exception as exc:
        logger.warning(f"Thumbnail error: {exc}")
        return None


def _draw_text_with_shadow(draw, text: str, img_size: tuple) -> None:
    """Draw bold text with drop shadow."""
    from PIL import ImageFont
    import textwrap

    width, height = img_size
    font_size = 90
    font = None

    # Try to load a bold font
    font_candidates = [
        str(config.FONTS_DIR / "bold.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for font_path in font_candidates:
        try:
            font = ImageFont.truetype(font_path, font_size)
            break
        except Exception:
            continue

    if font is None:
        font = ImageFont.load_default()

    wrapped = "\n".join(textwrap.wrap(text.upper(), width=12))

    # Shadow
    draw.multiline_text(
        (width // 2 + 4, 54),
        wrapped,
        font=font,
        fill=(0, 0, 0, 200),
        anchor="ma",
        align="center",
        spacing=8,
    )
    # Main text
    draw.multiline_text(
        (width // 2, 50),
        wrapped,
        font=font,
        fill="white",
        anchor="ma",
        align="center",
        spacing=8,
    )
