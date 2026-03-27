"""
Niche Finder
============
Uses Claude + Google Trends (pytrends) to identify the highest-potential
niches for YouTube Shorts right now and returns ranked niche objects.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Optional

import anthropic
from loguru import logger

import config

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Niche:
    name: str
    score: float                        # 0.0 – 10.0 AI-assigned score
    keywords: list[str] = field(default_factory=list)
    content_angles: list[str] = field(default_factory=list)
    trending_score: Optional[float] = None   # pytrends interest (0-100)
    rationale: str = ""

    def __str__(self) -> str:
        return (
            f"[{self.score:.1f}/10] {self.name} — "
            f"keywords: {', '.join(self.keywords[:3])}"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_google_trends(keywords: list[str]) -> dict[str, float]:
    """Return pytrends interest-over-time average for each keyword (0-100)."""
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=360)
        scores: dict[str, float] = {}

        # pytrends accepts at most 5 keywords per request
        for i in range(0, len(keywords), 5):
            batch = keywords[i : i + 5]
            try:
                pytrends.build_payload(batch, cat=0, timeframe="now 7-d")
                df = pytrends.interest_over_time()
                if not df.empty:
                    for kw in batch:
                        if kw in df.columns:
                            scores[kw] = float(df[kw].mean())
                time.sleep(1)   # polite delay
            except Exception as exc:
                logger.warning(f"pytrends batch error: {exc}")
        return scores
    except ImportError:
        logger.warning("pytrends not installed — skipping trend scoring")
        return {}


def _ask_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_niches(
    target_niche: str = "",
    count: int = 5,
    use_trends: bool = True,
) -> list[Niche]:
    """
    Discover the best YouTube Shorts niches.

    Parameters
    ----------
    target_niche : str
        If provided, research *that* niche deeply instead of doing a broad scan.
    count : int
        How many niches to return.
    use_trends : bool
        Whether to enrich results with Google Trends data.

    Returns
    -------
    list[Niche]
        Ranked list of niches, best first.
    """
    logger.info("🔍 Finding best YouTube Shorts niches…")

    if target_niche:
        prompt = _build_single_niche_prompt(target_niche, count)
    else:
        prompt = _build_broad_niche_prompt(count)

    raw = _ask_claude(prompt)

    niches = _parse_niches(raw)

    if use_trends and niches:
        all_keywords = [kw for n in niches for kw in n.keywords[:2]]
        trend_scores = _fetch_google_trends(all_keywords)
        for niche in niches:
            kw_scores = [trend_scores.get(kw, 0) for kw in niche.keywords[:2]]
            niche.trending_score = sum(kw_scores) / len(kw_scores) if kw_scores else 0.0
        # Re-sort: blend AI score + trend
        niches.sort(
            key=lambda n: (n.score * 0.6) + ((n.trending_score or 0) / 100 * 10 * 0.4),
            reverse=True,
        )

    for i, n in enumerate(niches, 1):
        logger.info(f"  #{i} {n}")

    return niches[:count]


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_broad_niche_prompt(count: int) -> str:
    return f"""You are a YouTube Shorts growth strategist with deep knowledge of viral content trends.

Identify the TOP {count} highest-potential niches for YouTube Shorts RIGHT NOW (2025-2026).

For each niche return a JSON array (and ONLY a JSON array) in this exact format:
[
  {{
    "name": "Niche name",
    "score": 8.5,
    "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
    "content_angles": ["angle1", "angle2", "angle3"],
    "rationale": "Why this niche is trending and profitable right now"
  }}
]

Selection criteria:
- High engagement rate on Shorts (likes, comments, shares)
- Growing audience, not saturated
- Easy to produce with AI tools and stock footage
- Monetisation potential (AdSense, affiliate, merch)
- Low competition relative to search volume
- Works with voiceover-style content

Return ONLY valid JSON, no markdown, no explanation outside the array.
"""


def _build_single_niche_prompt(niche: str, count: int) -> str:
    return f"""You are a YouTube Shorts growth strategist.

The user wants to create Shorts in the niche: "{niche}"

Provide {count} specific sub-niches or content angles within "{niche}" that are most likely to go viral on YouTube Shorts.

Return a JSON array (and ONLY a JSON array):
[
  {{
    "name": "Sub-niche / angle name",
    "score": 8.5,
    "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
    "content_angles": ["video idea 1", "video idea 2", "video idea 3"],
    "rationale": "Why this specific angle works well for Shorts"
  }}
]

Return ONLY valid JSON, no markdown, no explanation outside the array.
"""


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _parse_niches(raw: str) -> list[Niche]:
    """Parse Claude's JSON response into Niche objects."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    try:
        data = json.loads(text)
        niches = []
        for item in data:
            niches.append(
                Niche(
                    name=item.get("name", "Unknown"),
                    score=float(item.get("score", 5.0)),
                    keywords=item.get("keywords", []),
                    content_angles=item.get("content_angles", []),
                    rationale=item.get("rationale", ""),
                )
            )
        return niches
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error(f"Failed to parse niche JSON: {exc}\nRaw: {raw[:300]}")
        return []
