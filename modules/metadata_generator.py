"""
Metadata Generator
==================
Uses Claude to generate SEO-optimised YouTube metadata for each Short:
  - Title      (≤100 chars, hook-driven)
  - Description (with keywords, timestamps, CTA, hashtags)
  - Tags        (up to 500 chars total, mix of broad & specific)
  - Category ID
  - Thumbnail text suggestions
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import anthropic
from loguru import logger

import config


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class VideoMetadata:
    title: str
    description: str
    tags: list[str] = field(default_factory=list)
    category_id: str = config.YOUTUBE_CATEGORY_ID
    thumbnail_text: str = ""
    hashtags: list[str] = field(default_factory=list)

    def tags_string(self) -> str:
        """Comma-separated tags (YouTube accepts up to 500 chars)."""
        result = []
        total = 0
        for tag in self.tags:
            if total + len(tag) + 2 > 500:
                break
            result.append(tag)
            total += len(tag) + 2
        return ", ".join(result)

    def full_description(self) -> str:
        """Description with hashtags appended."""
        hashtag_str = " ".join(self.hashtags[:15])
        return f"{self.description}\n\n{hashtag_str}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_metadata(
    niche: str,
    content_angle: str,
    script_excerpt: str = "",
    hook_text: str = "",
) -> VideoMetadata:
    """
    Generate complete YouTube Short metadata using Claude.

    Parameters
    ----------
    niche : str
        The content niche (e.g. "motivational", "finance tips").
    content_angle : str
        Specific topic or angle for this video.
    script_excerpt : str
        First few lines of the script (helps Claude write relevant metadata).
    hook_text : str
        The opening hook line (used as basis for title).

    Returns
    -------
    VideoMetadata
    """
    logger.info(f"🏷️  Generating metadata for '{content_angle}'…")

    prompt = _build_prompt(niche, content_angle, script_excerpt, hook_text)

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    metadata = _parse_metadata(raw)

    logger.info(f"  Title: {metadata.title}")
    logger.info(f"  Tags ({len(metadata.tags)}): {', '.join(metadata.tags[:5])}…")
    return metadata


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(
    niche: str,
    content_angle: str,
    script_excerpt: str,
    hook_text: str,
) -> str:
    script_section = f'\n- Script excerpt: "{script_excerpt[:200]}"' if script_excerpt else ""
    hook_section = f'\n- Hook line: "{hook_text}"' if hook_text else ""

    return f"""You are an expert YouTube SEO specialist who creates viral metadata for YouTube Shorts.

Create optimised metadata for this YouTube Short:
- Niche: {niche}
- Content angle: {content_angle}{hook_section}{script_section}

Requirements:
1. TITLE: Max 70 characters. Start with a number or power word. Must make people click. Include 1-2 keywords naturally.
2. DESCRIPTION: 150-300 words. Open with the strongest benefit/hook. Include relevant keywords naturally. Add CTA ("Like & subscribe", "Comment below", etc.). Add 3-5 relevant hashtags at the end.
3. TAGS: 20-30 tags mixing: broad niche tags, specific topic tags, trending terms, long-tail phrases. Each tag max 30 chars.
4. HASHTAGS: 10-15 hashtags starting with # (for the description). Mix broad (#Shorts, #YouTube) with niche-specific.
5. CATEGORY_ID: Choose the most appropriate YouTube category number:
   - 1=Film, 2=Autos, 10=Music, 15=Pets, 17=Sports, 19=Travel, 20=Gaming, 22=People&Blogs, 23=Comedy, 24=Entertainment, 25=News, 26=Howto, 27=Education, 28=Science
6. THUMBNAIL_TEXT: 3-6 word bold text for the thumbnail image.

Return ONLY a valid JSON object:
{{
  "title": "...",
  "description": "...",
  "tags": ["tag1", "tag2", ...],
  "hashtags": ["#Shorts", "#YouTube", ...],
  "category_id": "22",
  "thumbnail_text": "..."
}}

Return ONLY valid JSON, nothing else.
"""


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _parse_metadata(raw: str) -> VideoMetadata:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    try:
        data = json.loads(text)
        return VideoMetadata(
            title=data.get("title", "Amazing YouTube Short")[:100],
            description=data.get("description", ""),
            tags=data.get("tags", []),
            category_id=str(data.get("category_id", config.YOUTUBE_CATEGORY_ID)),
            thumbnail_text=data.get("thumbnail_text", ""),
            hashtags=data.get("hashtags", ["#Shorts", "#YouTube"]),
        )
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error(f"Metadata parse error: {exc}\nRaw: {raw[:200]}")
        return VideoMetadata(
            title="Amazing YouTube Short",
            description="Watch this incredible short video! Don't forget to like and subscribe.",
            tags=["Shorts", "YouTube", "viral"],
            hashtags=["#Shorts", "#YouTube"],
        )
