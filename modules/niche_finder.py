"""
Niche Finder
============
Uses research-backed proven niches + Claude + Google Trends to identify
the highest-potential niches for YouTube Shorts.

Top niches are based on real 2025-2026 data:
  - Entertainment/Pranks: 32% of all Shorts views
  - Gaming: 21% of views
  - How-To/Tutorials: 18% of views
  - AI & Tech: fastest growing (18x YoY), $15-22 CPM
  - Finance: highest CPM ($4.50/1000 views)
  - Food & Cooking: hundreds of millions of views
  - Fitness/Transformation: top 10 consistently
  - Sports highlights: high share rate
  - Pet content: evergreen viral
  - Comedy/Relatable: 48% of viewers prefer humorous content
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
# Research-backed proven niches (2025-2026 data)
# ---------------------------------------------------------------------------

PROVEN_NICHES: dict[str, dict] = {
    "entertainment_pranks": {
        "name": "Entertainment & Pranks",
        "score": 9.8,
        "share_of_views": "32%",
        "keywords": ["pranks", "funny moments", "comedy shorts", "viral pranks", "funny fails", "prank videos"],
        "content_angles": [
            "Reaction to something shocking or unexpected",
            "Prank gone wrong compilation",
            "Hidden camera funny moments",
            "Dare challenge with friends",
            "Awkward social experiment",
        ],
        "hooks": [
            "I can't believe this happened…",
            "Nobody expected this…",
            "Watch what happens next…",
            "This prank went too far…",
            "They had no idea…",
        ],
        "style": "Fast cuts every 1-2s, reaction shots, loud sound effects, dramatic zoom on face",
        "optimal_length": 25,
        "cpm": 2.50,
        "rationale": "32% of all YouTube Shorts views. No language barrier. Global audience. High rewatch.",
    },
    "ai_tech": {
        "name": "AI & Tech Tutorials",
        "score": 9.5,
        "share_of_views": "18% (fastest growing: 18x YoY)",
        "keywords": ["AI tools", "tech hacks", "ChatGPT tips", "AI tutorial", "tech shortcuts", "iPhone hacks", "AI money", "free AI tools"],
        "content_angles": [
            "5 AI tools that will replace your job",
            "Free AI tool nobody knows about",
            "iPhone trick Apple doesn't want you to know",
            "This AI makes money while you sleep",
            "ChatGPT prompt that does everything",
        ],
        "hooks": [
            "This free AI tool will change your life…",
            "Nobody is talking about this AI…",
            "Stop doing this on your iPhone…",
            "This AI made me $500 in one day…",
            "The AI tool that replaces 10 apps…",
        ],
        "style": "Screen recording + voiceover, text captions every word, fast jump cuts",
        "optimal_length": 30,
        "cpm": 18.50,
        "rationale": "18x year-over-year growth. Highest CPM ($15-22). Huge Gen Z + millennial audience.",
    },
    "personal_finance": {
        "name": "Personal Finance & Money",
        "score": 9.2,
        "share_of_views": "High CPM niche",
        "keywords": ["money tips", "save money", "investing for beginners", "passive income", "side hustle", "budget hacks", "get rich", "financial freedom"],
        "content_angles": [
            "Save $1000 in 30 days challenge",
            "Side hustle that makes $200/day",
            "Money mistake 90% of people make",
            "How to invest with $100",
            "Budgeting hack nobody teaches you",
        ],
        "hooks": [
            "Stop wasting money on this right now…",
            "This one habit will make you rich…",
            "I made $500 last week doing this…",
            "Most people lose money because of this…",
            "The $100 investment strategy that works…",
        ],
        "style": "Talking head or text-on-screen, bold captions, urgency tone, stat overlays",
        "optimal_length": 45,
        "cpm": 4.50,
        "rationale": "Highest CPM at $4.50/1000 views. Economic uncertainty drives demand. High subscriber loyalty.",
    },
    "food_cooking": {
        "name": "Food & Cooking",
        "score": 9.0,
        "share_of_views": "2nd most viewed category",
        "keywords": ["easy recipe", "quick recipe", "food hack", "cooking tips", "viral recipe", "5 minute meal", "satisfying food"],
        "content_angles": [
            "3-ingredient recipe ready in 5 minutes",
            "Restaurant hack you can do at home",
            "The most satisfying food compilation",
            "Gordon Ramsay technique made simple",
            "Viral TikTok recipe everyone is trying",
        ],
        "hooks": [
            "The easiest recipe you'll ever make…",
            "Stop buying this — make it at home…",
            "This 3-ingredient meal is unbelievable…",
            "The viral recipe everyone is obsessed with…",
            "You've been cooking this wrong your whole life…",
        ],
        "style": "Close-up food shots, ASMR audio, fast time-lapse, satisfying reveals, bright lighting",
        "optimal_length": 30,
        "cpm": 3.00,
        "rationale": "Hundreds of millions of views. Visually satisfying = high rewatch. Universal appeal.",
    },
    "gaming": {
        "name": "Gaming Highlights",
        "score": 8.9,
        "share_of_views": "21%",
        "keywords": ["gaming highlights", "insane play", "clutch moment", "funny gaming", "game clip", "best plays", "gaming fails"],
        "content_angles": [
            "Insane 1v5 clutch nobody expected",
            "Funniest gaming fails of the week",
            "New game mechanic nobody discovered yet",
            "Speed run world record attempt",
            "Crazy glitch that breaks the game",
        ],
        "hooks": [
            "Nobody has ever done this in the game…",
            "This clip broke the internet…",
            "The most insane clutch you'll ever see…",
            "This glitch changes everything…",
            "Watch this in slow motion…",
        ],
        "style": "Hype music, slow-mo on key moments, reaction cam in corner, bold text on screen",
        "optimal_length": 20,
        "cpm": 2.00,
        "rationale": "21% of all Shorts views. Massive built-in audience. Trending titles drive search traffic.",
    },
    "fitness_transformation": {
        "name": "Fitness & Body Transformation",
        "score": 8.7,
        "share_of_views": "Top 10 consistently",
        "keywords": ["workout tips", "body transformation", "gym motivation", "fitness hack", "lose weight fast", "6 pack", "home workout"],
        "content_angles": [
            "30-day transformation nobody believed possible",
            "One exercise that changes everything",
            "Gym mistake killing your gains",
            "Home workout with zero equipment",
            "What I eat in a day to get shredded",
        ],
        "hooks": [
            "I lost 20 pounds doing this one thing…",
            "The gym exercise everyone does wrong…",
            "30 days — this is what happened to my body…",
            "You don't need a gym for this…",
            "This workout takes 5 minutes and works…",
        ],
        "style": "Before/after reveals, time-lapse workouts, motivational music, split-screen comparisons",
        "optimal_length": 40,
        "cpm": 3.50,
        "rationale": "Emotional transformation stories drive shares. High subscriber conversion. Evergreen demand.",
    },
    "sports_highlights": {
        "name": "Sports Highlights",
        "score": 8.5,
        "share_of_views": "4th most viewed category",
        "keywords": ["sports highlights", "best plays", "incredible moment", "sports fails", "epic sports", "athlete highlights"],
        "content_angles": [
            "The most insane play in sports history",
            "Nobody saw this coming — sports shock",
            "Athlete does the impossible",
            "Sports moment that changed everything",
            "Funniest sports blooper compilation",
        ],
        "hooks": [
            "Nobody has ever done this in sports history…",
            "This moment broke the internet…",
            "Watch this in slow motion…",
            "This athlete is not human…",
            "The referee couldn't believe it…",
        ],
        "style": "Slow-mo on key moments, crowd reaction, dramatic music swell, score/stat overlays",
        "optimal_length": 25,
        "cpm": 2.50,
        "rationale": "Intense moments = high rewatch + share rate. Trending events boost search traffic.",
    },
    "motivational": {
        "name": "Motivational & Mindset",
        "score": 8.4,
        "share_of_views": "High engagement niche",
        "keywords": ["motivation", "success mindset", "discipline", "self improvement", "hustle", "mindset shift", "success habits"],
        "content_angles": [
            "The one habit that separates winners from losers",
            "What successful people do before 6am",
            "Stop making excuses — watch this",
            "The mindset shift that changed my life",
            "Why 99% of people never get rich",
        ],
        "hooks": [
            "Most people will watch this and do nothing…",
            "This one habit changed my life completely…",
            "Stop making excuses right now…",
            "The secret successful people never talk about…",
            "If you're struggling, watch this…",
        ],
        "style": "Dark dramatic background, powerful music, bold text captions, deep voice narration",
        "optimal_length": 45,
        "cpm": 3.00,
        "rationale": "High subscriber loyalty. Strong share rate. Works without showing your face.",
    },
    "life_hacks": {
        "name": "Life Hacks & Productivity",
        "score": 8.3,
        "share_of_views": "Top 10 most shared",
        "keywords": ["life hacks", "productivity tips", "useful tricks", "time saving hack", "study hacks", "daily hacks", "smart tips"],
        "content_angles": [
            "5 life hacks that save hours every week",
            "Phone trick 99% of people don't know",
            "Cleaning hack that actually works",
            "Productivity system that changed my day",
            "Kitchen hack that blows people's minds",
        ],
        "hooks": [
            "This changed the way I do everything…",
            "I can't believe I didn't know this earlier…",
            "Try this right now — you'll thank me…",
            "This hack will save you hours every week…",
            "Nobody teaches this in school…",
        ],
        "style": "POV hands-on demo, text overlay on each step, fast transitions, satisfying result reveal",
        "optimal_length": 30,
        "cpm": 2.50,
        "rationale": "Top 10 most shared content type. Practical value = saves/bookmarks. Evergreen.",
    },
    "pet_content": {
        "name": "Pet Content",
        "score": 8.0,
        "share_of_views": "Evergreen top 10",
        "keywords": ["funny dog", "cute cat", "pet videos", "animal moments", "funny animals", "cute pets", "pet fails"],
        "content_angles": [
            "Dog does something hilariously unexpected",
            "Cat vs. cucumber compilation",
            "Pet's first reaction to baby",
            "Animals being bros to each other",
            "Pet fails that are too relatable",
        ],
        "hooks": [
            "This dog just made my day…",
            "I've never seen an animal do this before…",
            "Watch this until the end…",
            "This is the cutest thing on the internet…",
            "Nobody warned me this would make me cry…",
        ],
        "style": "Natural lighting, genuine reactions, no heavy editing, warm music, minimal text",
        "optimal_length": 20,
        "cpm": 1.50,
        "rationale": "Evergreen universal appeal. High share rate to family/friends. Zero production cost.",
    },
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Niche:
    name: str
    score: float
    keywords: list[str] = field(default_factory=list)
    content_angles: list[str] = field(default_factory=list)
    hooks: list[str] = field(default_factory=list)
    style: str = ""
    optimal_length: int = 30
    cpm: float = 0.0
    trending_score: Optional[float] = None
    rationale: str = ""

    def __str__(self) -> str:
        return (
            f"[{self.score:.1f}/10] {self.name} | "
            f"CPM ${self.cpm:.2f} | {len(self.content_angles)} angles"
        )

    def best_hook(self) -> str:
        return self.hooks[0] if self.hooks else ""

    def best_angle(self) -> str:
        return self.content_angles[0] if self.content_angles else self.name


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_niches(
    target_niche: str = "",
    count: int = 5,
    use_trends: bool = True,
) -> list[Niche]:
    """
    Return the best YouTube Shorts niches, anchored to real 2025-2026 data.

    If target_niche is set: find the best sub-angles within that niche.
    If blank: return the top proven niches ranked by score + trends.
    """
    logger.info("🔍 Finding best YouTube Shorts niches…")

    if target_niche:
        niches = _research_specific_niche(target_niche, count)
    else:
        niches = _get_top_proven_niches(count)

    if use_trends and niches:
        _enrich_with_trends(niches)
        niches.sort(
            key=lambda n: (n.score * 0.6) + ((n.trending_score or 0) / 100 * 10 * 0.4),
            reverse=True,
        )

    for i, n in enumerate(niches[:count], 1):
        trend_str = f" | trend: {n.trending_score:.0f}" if n.trending_score else ""
        logger.info(f"  #{i} {n}{trend_str}")

    return niches[:count]


# ---------------------------------------------------------------------------
# Proven niche loader
# ---------------------------------------------------------------------------

def _get_top_proven_niches(count: int) -> list[Niche]:
    """Load from the research-backed PROVEN_NICHES dict, then ask Claude to
    add any emerging niches to fill the count if needed."""
    base = [_dict_to_niche(v) for v in PROVEN_NICHES.values()]
    base.sort(key=lambda n: n.score, reverse=True)

    if len(base) >= count:
        return base[:count]

    # Ask Claude for additional emerging niches to fill the rest
    extras = _ask_claude_for_niches("", count - len(base))
    return (base + extras)[:count]


# ---------------------------------------------------------------------------
# Specific niche research
# ---------------------------------------------------------------------------

def _research_specific_niche(niche: str, count: int) -> list[Niche]:
    """
    Use Claude to find the best sub-angles within a given niche,
    grounded in what's proven to work on YouTube Shorts.
    """
    prompt = f"""You are a YouTube Shorts growth expert with access to real 2025-2026 analytics.

The creator wants to make Shorts in the niche: "{niche}"

Based on what is ACTUALLY performing well on YouTube Shorts right now (2025-2026),
give me {count} specific content angles within "{niche}" ranked by viral potential.

For each angle, use these facts as context:
- Best performing Shorts are 20-45 seconds long
- 72% of viral Shorts use fast-paced editing with cuts every 2-3 seconds
- Strong hooks in the first 1-2 words are critical
- Word-synced captions increase watch time by 18%
- Videos posted 6-10 PM get highest engagement

Return ONLY a JSON array:
[
  {{
    "name": "Specific angle name",
    "score": 9.0,
    "keywords": ["kw1", "kw2", "kw3", "kw4", "kw5"],
    "content_angles": ["Specific video idea 1", "Specific video idea 2", "Specific video idea 3"],
    "hooks": ["Hook line 1", "Hook line 2", "Hook line 3"],
    "style": "Describe the editing style, visuals, music",
    "optimal_length": 30,
    "cpm": 3.50,
    "rationale": "Why this angle goes viral on Shorts"
  }}
]

Return ONLY valid JSON, nothing else.
"""
    raw = _call_claude(prompt)
    return _parse_niches_from_json(raw)


# ---------------------------------------------------------------------------
# Claude helpers
# ---------------------------------------------------------------------------

def _ask_claude_for_niches(context: str, count: int) -> list[Niche]:
    prompt = f"""You are a YouTube Shorts analyst. Based on real 2025-2026 performance data,
identify {count} emerging YouTube Shorts niches with high viral potential.

Known top performers for context:
- Entertainment/Pranks: 32% of views
- Gaming: 21% of views
- How-To/Tutorials: 18% of views
- AI & Tech: 18x YoY growth, $15-22 CPM
- Finance: $4.50 CPM (highest)

Return ONLY a JSON array:
[
  {{
    "name": "Niche name",
    "score": 8.5,
    "keywords": ["kw1", "kw2", "kw3", "kw4"],
    "content_angles": ["angle1", "angle2", "angle3"],
    "hooks": ["hook1", "hook2", "hook3"],
    "style": "Editing and visual style description",
    "optimal_length": 30,
    "cpm": 3.00,
    "rationale": "Why this works on Shorts right now"
  }}
]

Return ONLY valid JSON."""
    raw = _call_claude(prompt)
    return _parse_niches_from_json(raw)


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


# ---------------------------------------------------------------------------
# Trend enrichment
# ---------------------------------------------------------------------------

def _enrich_with_trends(niches: list[Niche]) -> None:
    """Add Google Trends scores to each niche in-place."""
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=360)

        for niche in niches:
            kws = niche.keywords[:2]
            if not kws:
                continue
            try:
                pytrends.build_payload(kws, cat=0, timeframe="now 7-d")
                df = pytrends.interest_over_time()
                if not df.empty:
                    scores = [float(df[kw].mean()) for kw in kws if kw in df.columns]
                    niche.trending_score = sum(scores) / len(scores) if scores else 0.0
                time.sleep(1)
            except Exception as exc:
                logger.debug(f"Trends error for '{niche.name}': {exc}")
    except ImportError:
        logger.debug("pytrends not installed — skipping trend enrichment")


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _dict_to_niche(d: dict) -> Niche:
    return Niche(
        name=d.get("name", ""),
        score=float(d.get("score", 5.0)),
        keywords=d.get("keywords", []),
        content_angles=d.get("content_angles", []),
        hooks=d.get("hooks", []),
        style=d.get("style", ""),
        optimal_length=int(d.get("optimal_length", 30)),
        cpm=float(d.get("cpm", 0.0)),
        rationale=d.get("rationale", ""),
    )


def _parse_niches_from_json(raw: str) -> list[Niche]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    try:
        data = json.loads(text)
        return [_dict_to_niche(item) for item in data]
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error(f"Niche JSON parse error: {exc}")
        return []
