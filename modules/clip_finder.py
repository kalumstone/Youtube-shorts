"""
Clip Finder & Downloader
========================
Discovers and downloads short video clips from multiple sources:
  - YouTube (via yt-dlp, Creative Commons / licensed content)
  - Reddit (video posts from relevant subreddits)
  - Pexels (royalty-free stock footage)
  - Pixabay (royalty-free stock footage)

Returns a list of ClipResult objects pointing to local files.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

import config

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ClipResult:
    local_path: Path
    source: str          # "youtube" | "reddit" | "pexels" | "pixabay"
    title: str = ""
    duration: float = 0.0
    url: str = ""
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_clips(
    niche_keywords: list[str],
    count: int = 5,
    max_duration: int = 60,
) -> list[ClipResult]:
    """
    Search multiple sources and return up to `count` downloaded clips.

    Parameters
    ----------
    niche_keywords : list[str]
        Search terms derived from the chosen niche.
    count : int
        Target number of clips to collect.
    max_duration : int
        Maximum clip length in seconds.

    Returns
    -------
    list[ClipResult]
    """
    logger.info(f"🎬 Searching for clips — keywords: {niche_keywords[:3]} …")
    config.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    clips: list[ClipResult] = []
    query = " ".join(niche_keywords[:3])

    # Try sources in priority order
    if len(clips) < count:
        clips += _search_pexels(query, count - len(clips), max_duration)

    if len(clips) < count:
        clips += _search_pixabay(query, count - len(clips), max_duration)

    if len(clips) < count:
        clips += _search_reddit(niche_keywords, count - len(clips), max_duration)

    if len(clips) < count:
        clips += _search_youtube(query, count - len(clips), max_duration)

    logger.info(f"  ✅ {len(clips)} clips ready")
    return clips[:count]


# ---------------------------------------------------------------------------
# Pexels
# ---------------------------------------------------------------------------

def _search_pexels(query: str, count: int, max_duration: int) -> list[ClipResult]:
    if not config.PEXELS_API_KEY:
        return []

    clips: list[ClipResult] = []
    try:
        headers = {"Authorization": config.PEXELS_API_KEY}
        params = {"query": query, "per_page": min(count * 2, 20), "size": "medium"}
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        for video in data.get("videos", []):
            duration = video.get("duration", 999)
            if duration > max_duration:
                continue
            # Pick highest quality available
            files = sorted(
                video.get("video_files", []),
                key=lambda f: f.get("width", 0),
                reverse=True,
            )
            if not files:
                continue
            video_url = files[0]["link"]
            local = _download_file(video_url, "pexels")
            if local:
                clips.append(
                    ClipResult(
                        local_path=local,
                        source="pexels",
                        title=f"pexels_{video.get('id')}",
                        duration=duration,
                        url=video_url,
                        tags=[query],
                    )
                )
            if len(clips) >= count:
                break
    except Exception as exc:
        logger.warning(f"Pexels error: {exc}")
    return clips


# ---------------------------------------------------------------------------
# Pixabay
# ---------------------------------------------------------------------------

def _search_pixabay(query: str, count: int, max_duration: int) -> list[ClipResult]:
    if not config.PIXABAY_API_KEY:
        return []

    clips: list[ClipResult] = []
    try:
        params = {
            "key": config.PIXABAY_API_KEY,
            "q": query,
            "video_type": "film",
            "per_page": min(count * 2, 20),
        }
        resp = requests.get(
            "https://pixabay.com/api/videos/",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        for hit in data.get("hits", []):
            duration = hit.get("duration", 999)
            if duration > max_duration:
                continue
            videos = hit.get("videos", {})
            # Prefer medium quality
            for quality in ("medium", "large", "small", "tiny"):
                vid_info = videos.get(quality, {})
                if vid_info.get("url"):
                    local = _download_file(vid_info["url"], "pixabay")
                    if local:
                        clips.append(
                            ClipResult(
                                local_path=local,
                                source="pixabay",
                                title=f"pixabay_{hit.get('id')}",
                                duration=duration,
                                url=vid_info["url"],
                                tags=hit.get("tags", "").split(","),
                            )
                        )
                    break
            if len(clips) >= count:
                break
    except Exception as exc:
        logger.warning(f"Pixabay error: {exc}")
    return clips


# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------

def _search_reddit(keywords: list[str], count: int, max_duration: int) -> list[ClipResult]:
    if not (config.REDDIT_CLIENT_ID and config.REDDIT_CLIENT_SECRET):
        return []

    clips: list[ClipResult] = []
    try:
        import praw

        reddit = praw.Reddit(
            client_id=config.REDDIT_CLIENT_ID,
            client_secret=config.REDDIT_CLIENT_SECRET,
            user_agent=config.REDDIT_USER_AGENT,
        )

        # Map keywords to likely subreddits
        subreddits = _keywords_to_subreddits(keywords)
        query = " ".join(keywords[:2])

        for sub_name in subreddits[:3]:
            try:
                subreddit = reddit.subreddit(sub_name)
                for post in subreddit.search(query, sort="hot", limit=count * 3):
                    if not post.is_video:
                        continue
                    try:
                        video_url = post.media["reddit_video"]["fallback_url"]
                        local = _download_with_ytdlp(post.url, "reddit")
                        if local:
                            clips.append(
                                ClipResult(
                                    local_path=local,
                                    source="reddit",
                                    title=post.title[:100],
                                    url=post.url,
                                    tags=keywords,
                                )
                            )
                    except Exception:
                        pass
                    if len(clips) >= count:
                        break
            except Exception as exc:
                logger.warning(f"Reddit subreddit '{sub_name}' error: {exc}")

            if len(clips) >= count:
                break
    except ImportError:
        logger.warning("praw not installed — skipping Reddit source")
    except Exception as exc:
        logger.warning(f"Reddit error: {exc}")
    return clips[:count]


def _keywords_to_subreddits(keywords: list[str]) -> list[str]:
    """Very simple keyword→subreddit mapping."""
    keyword_map = {
        "motivat": "GetMotivated",
        "inspir": "GetMotivated",
        "funny": "funny",
        "animal": "AnimalsBeingBros",
        "gaming": "gaming",
        "finance": "personalfinance",
        "money": "financialindependence",
        "life hack": "lifehacks",
        "hack": "lifehacks",
        "food": "food",
        "cook": "Cooking",
        "sport": "sports",
        "workout": "fitness",
        "gym": "gym",
        "travel": "travel",
        "nature": "EarthPorn",
    }
    subreddits = []
    kw_str = " ".join(keywords).lower()
    for key, sub in keyword_map.items():
        if key in kw_str and sub not in subreddits:
            subreddits.append(sub)
    if not subreddits:
        subreddits = ["videos", "PublicFreakout", "oddlysatisfying"]
    return subreddits


# ---------------------------------------------------------------------------
# YouTube (yt-dlp)
# ---------------------------------------------------------------------------

def _search_youtube(query: str, count: int, max_duration: int) -> list[ClipResult]:
    clips: list[ClipResult] = []
    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "match_filter": yt_dlp.utils.match_filter_func(
                f"duration < {max_duration} & duration > 5"
            ),
        }

        search_url = f"ytsearch{count * 3}:{query} short"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            results = ydl.extract_info(search_url, download=False)

        for entry in (results.get("entries") or []):
            if not entry:
                continue
            video_url = f"https://www.youtube.com/watch?v={entry.get('id', '')}"
            local = _download_with_ytdlp(video_url, "youtube")
            if local:
                clips.append(
                    ClipResult(
                        local_path=local,
                        source="youtube",
                        title=entry.get("title", "")[:100],
                        duration=entry.get("duration", 0),
                        url=video_url,
                    )
                )
            if len(clips) >= count:
                break
    except ImportError:
        logger.warning("yt-dlp not installed — skipping YouTube source")
    except Exception as exc:
        logger.warning(f"YouTube search error: {exc}")
    return clips


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _download_file(url: str, source: str) -> Optional[Path]:
    """Stream-download a direct video URL to DOWNLOADS_DIR."""
    try:
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        ext = _guess_extension(url, resp.headers.get("Content-Type", ""))
        filename = config.DOWNLOADS_DIR / f"{source}_{uuid.uuid4().hex[:8]}{ext}"
        with open(filename, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
        logger.debug(f"  ↓ Downloaded: {filename.name}")
        return filename
    except Exception as exc:
        logger.warning(f"  Download failed ({url[:60]}…): {exc}")
        return None


def _download_with_ytdlp(url: str, source: str) -> Optional[Path]:
    """Use yt-dlp to download a video URL."""
    try:
        import yt_dlp

        out_template = str(config.DOWNLOADS_DIR / f"{source}_{uuid.uuid4().hex[:8]}.%(ext)s")
        ydl_opts = {
            "outtmpl": out_template,
            "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": "mp4",
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Find actual output file
            pattern = out_template.replace("%(ext)s", "*")
            import glob
            matches = glob.glob(pattern)
            if matches:
                return Path(matches[0])
    except Exception as exc:
        logger.warning(f"yt-dlp download error ({url[:60]}): {exc}")
    return None


def _guess_extension(url: str, content_type: str) -> str:
    if "mp4" in url or "mp4" in content_type:
        return ".mp4"
    if "webm" in url or "webm" in content_type:
        return ".webm"
    if "mov" in url or "quicktime" in content_type:
        return ".mov"
    return ".mp4"
