"""
YouTube Uploader
================
Authenticates with the YouTube Data API v3 (OAuth 2.0) and uploads
finished Short videos with full metadata.

First-time setup
----------------
1. Create a project at https://console.cloud.google.com
2. Enable "YouTube Data API v3"
3. Create OAuth 2.0 credentials (Desktop App)
4. Download client_secrets.json to the project root
5. Run: python -m modules.youtube_uploader --auth
   → Opens browser for one-time consent; saves token.json
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

import config
from modules.metadata_generator import VideoMetadata


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upload_short(
    video_path: Path,
    metadata: VideoMetadata,
    privacy: str = config.YOUTUBE_DEFAULT_PRIVACY,
    thumbnail_path: Optional[Path] = None,
) -> Optional[str]:
    """
    Upload a Short to YouTube.

    Parameters
    ----------
    video_path : Path
        Path to the final .mp4 file.
    metadata : VideoMetadata
        Title, description, tags, category.
    privacy : str
        "public" | "private" | "unlisted"
    thumbnail_path : Path, optional
        Custom thumbnail image.

    Returns
    -------
    str | None
        YouTube video ID on success, None on failure.
    """
    youtube = _get_authenticated_service()
    if youtube is None:
        logger.error("YouTube authentication failed — skipping upload")
        return None

    logger.info(f"📤 Uploading to YouTube: {metadata.title}")

    try:
        from googleapiclient.http import MediaFileUpload

        body = {
            "snippet": {
                "title": metadata.title,
                "description": metadata.full_description(),
                "tags": metadata.tags,
                "categoryId": metadata.category_id,
                "defaultLanguage": "en",
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 5,  # 5 MB chunks
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        video_id = _resumable_upload(request)
        if not video_id:
            return None

        youtube_url = f"https://www.youtube.com/shorts/{video_id}"
        logger.info(f"  ✅ Uploaded! → {youtube_url}")

        # Upload custom thumbnail if provided
        if thumbnail_path and thumbnail_path.exists():
            _upload_thumbnail(youtube, video_id, thumbnail_path)

        return video_id

    except Exception as exc:
        logger.error(f"Upload failed: {exc}")
        return None


def authenticate() -> None:
    """
    Run the OAuth flow interactively to generate token.json.
    Call once from the command line:  python -m modules.youtube_uploader --auth
    """
    _get_authenticated_service(force_auth=True)
    logger.info("Authentication complete. token.json saved.")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def _get_authenticated_service(force_auth: bool = False):
    """Return an authenticated YouTube API service object."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError as exc:
        logger.error(
            "Google API packages not installed.\n"
            "Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )
        return None

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = None
    token_file = Path(config.YOUTUBE_TOKEN_FILE)
    secrets_file = Path(config.YOUTUBE_CLIENT_SECRETS_FILE)

    if not secrets_file.exists():
        logger.error(
            f"client_secrets.json not found at '{secrets_file}'.\n"
            "Download it from https://console.cloud.google.com → APIs → Credentials"
        )
        return None

    # Load saved token
    if token_file.exists() and not force_auth:
        try:
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        except Exception:
            creds = None

    # Refresh or re-authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_file), SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token
        with open(str(token_file), "w") as f:
            f.write(creds.to_json())
        logger.info(f"Token saved to {token_file}")

    return build("youtube", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# Resumable upload with progress
# ---------------------------------------------------------------------------

def _resumable_upload(request) -> Optional[str]:
    """Execute a resumable upload, returning the video ID."""
    from googleapiclient.errors import HttpError

    response = None
    error = None
    retry_count = 0
    max_retries = 5

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                logger.debug(f"  Upload progress: {pct}%")
        except HttpError as exc:
            if exc.resp.status in [500, 502, 503, 504]:
                error = exc
                retry_count += 1
                if retry_count > max_retries:
                    logger.error(f"Upload failed after {max_retries} retries: {exc}")
                    return None
                import time
                sleep_time = 2 ** retry_count
                logger.warning(f"Server error {exc.resp.status} — retrying in {sleep_time}s")
                time.sleep(sleep_time)
            else:
                logger.error(f"Upload HTTP error: {exc}")
                return None
        except Exception as exc:
            logger.error(f"Upload error: {exc}")
            return None

    if response:
        return response.get("id")
    return None


# ---------------------------------------------------------------------------
# Thumbnail upload
# ---------------------------------------------------------------------------

def _upload_thumbnail(youtube, video_id: str, thumbnail_path: Path) -> None:
    try:
        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")
        youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
        logger.info(f"  🖼️  Thumbnail uploaded for {video_id}")
    except Exception as exc:
        logger.warning(f"Thumbnail upload failed: {exc}")


# ---------------------------------------------------------------------------
# CLI entry point for auth
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--auth" in sys.argv:
        authenticate()
    else:
        print("Usage: python -m modules.youtube_uploader --auth")
