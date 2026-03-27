# YouTube Shorts Automation Bot

Fully automated pipeline that finds trending niches, downloads clips, generates AI voiceovers, edits vertical videos, and uploads them to YouTube — powered by **Claude AI**.

---

## Features

| Step | What it does |
|------|-------------|
| **Niche Finder** | Uses Claude + Google Trends to rank the hottest niches right now |
| **Clip Finder** | Downloads royalty-free footage from Pexels, Pixabay, Reddit & YouTube |
| **Voiceover** | Writes a viral script with Claude → renders audio via ElevenLabs or gTTS |
| **Video Editor** | Auto-crops to 9:16, burns captions, adds hook/CTA overlays, fades, music |
| **Thumbnail** | Extracts best frame + bold text overlay |
| **Metadata** | Claude generates SEO-optimised title, description, tags & hashtags |
| **Uploader** | Posts directly to YouTube via Data API v3 with all metadata |
| **Scheduler** | Run on a cron schedule for fully hands-off daily posting |

---

## Quick Start

### 1. Clone & install dependencies

```bash
git clone <your-repo>
cd Youtube-shorts

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

> **Note:** MoviePy requires `ffmpeg`. Install it:
> - macOS: `brew install ffmpeg`
> - Ubuntu: `sudo apt install ffmpeg`
> - Windows: Download from https://ffmpeg.org/download.html

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in:

| Variable | Required | Notes |
|----------|----------|-------|
| `ANTHROPIC_API_KEY` | **YES** | Get from https://console.anthropic.com |
| `PEXELS_API_KEY` | Recommended | Free at https://www.pexels.com/api/ |
| `PIXABAY_API_KEY` | Recommended | Free at https://pixabay.com/api/docs/ |
| `ELEVENLABS_API_KEY` | Optional | Premium voices — free tier available |
| `YOUTUBE_CLIENT_SECRETS_FILE` | For upload | See YouTube setup below |
| `REDDIT_CLIENT_ID` | Optional | For Reddit viral clips |

### 3. Set up YouTube API (one-time)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project → **Enable "YouTube Data API v3"**
3. Go to **Credentials** → **Create OAuth 2.0 Client ID** (Desktop App)
4. Download `client_secrets.json` → place it in the project root
5. Run the auth flow:

```bash
python main.py auth
```

This opens your browser once for consent and saves `token.json`.

### 4. Add background music (optional)

Drop any `.mp3` / `.wav` files into `assets/music/`. The bot will automatically mix them at low volume behind the voiceover.

---

## Usage

### Run the full pipeline

```bash
# Auto-detect best niche + produce 3 Shorts
python main.py run

# Target a specific niche
python main.py run --niche "motivational quotes"

# Produce 5 Shorts
python main.py run --count 5

# Dry run (produce videos but don't upload)
python main.py run --dry-run
```

### Research niches only

```bash
# Broad scan — AI picks top niches
python main.py niches

# Research a specific niche's sub-angles
python main.py niches --niche "finance tips" --count 8
```

### Schedule automated daily posting

```bash
# Post every day at 9am
python main.py schedule --cron "0 9 * * *"

# Post every day at 9am with a specific niche
python main.py schedule --niche "motivational" --cron "0 9 * * *"
```

---

## Project Structure

```
Youtube-shorts/
├── main.py                        # CLI orchestrator
├── config.py                      # All settings from .env
├── requirements.txt
├── .env.example                   # Copy to .env
├── client_secrets.json            # YouTube OAuth (you add this)
├── token.json                     # Auto-generated after auth
│
├── modules/
│   ├── niche_finder.py            # Claude + Google Trends niche research
│   ├── clip_finder.py             # Pexels / Pixabay / Reddit / YouTube download
│   ├── voiceover.py               # Script writing + TTS (ElevenLabs / gTTS)
│   ├── video_editor.py            # MoviePy editing pipeline
│   ├── thumbnail_generator.py     # Pillow thumbnail creation
│   ├── metadata_generator.py      # SEO title / description / tags via Claude
│   └── youtube_uploader.py        # YouTube Data API v3 upload
│
├── assets/
│   ├── music/                     # Drop background music files here
│   └── fonts/                     # Optional custom fonts (bold.ttf)
│
└── output/
    ├── downloads/                 # Raw downloaded clips
    ├── edited/                    # Voiceover audio files
    ├── final/                     # Finished Short videos + thumbnails
    └── bot.log                    # Run logs
```

---

## Niche Examples

The bot works especially well for these proven Shorts niches:

- **Motivational / Mindset** — quotes, success stories, discipline content
- **Finance Tips** — saving hacks, investing basics, side hustles
- **Life Hacks** — productivity, cooking, cleaning, organization
- **Funny Animals** — curated clips with commentary
- **Did You Know** — surprising facts, history, science
- **Gaming Highlights** — clips with energetic commentary
- **Fitness / Workout** — quick tip videos, transformation clips
- **Relationship Advice** — psychology facts, dating tips
- **True Crime Shorts** — brief summaries of famous cases
- **AI / Tech News** — latest tools and breakthroughs

---

## Voice Options

### ElevenLabs (Premium — recommended)
Set `VOICE_PROVIDER=elevenlabs` in `.env`. Realistic human-like voices.
Popular voice IDs:
- `21m00Tcm4TlvDq8ikWAM` — Rachel (calm, female)
- `AZnzlk1XvdvUeBnXmlld` — Domi (strong, female)
- `EXAVITQu4vr4xnSDxMaL` — Bella (soft, female)
- `ErXwobaYiN019PkySvjV` — Antoni (well-rounded, male)
- `VR6AewLTigWG4xSOukaG` — Arnold (crisp, male)

### gTTS (Free fallback)
Set `VOICE_PROVIDER=gtts`. Uses Google's text-to-speech. Supports 40+ languages via `TTS_LANGUAGE=en`.

---

## Environment Variables Reference

```env
# Required
ANTHROPIC_API_KEY=            # Claude API key

# Video sources (at least one recommended)
PEXELS_API_KEY=               # Free: pexels.com/api
PIXABAY_API_KEY=              # Free: pixabay.com/api/docs
REDDIT_CLIENT_ID=             # Optional: reddit.com/prefs/apps
REDDIT_CLIENT_SECRET=

# Voice
VOICE_PROVIDER=gtts           # "gtts" or "elevenlabs"
ELEVENLABS_API_KEY=           # Only if using ElevenLabs
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM

# YouTube upload
YOUTUBE_CLIENT_SECRETS_FILE=client_secrets.json
YOUTUBE_TOKEN_FILE=token.json
AUTO_UPLOAD=true

# Bot behaviour
SHORTS_PER_RUN=3
TARGET_NICHE=                 # Leave blank for AI to choose
MAX_CLIP_DURATION=59
MUSIC_VOLUME=0.15
WATERMARK_TEXT=               # Optional channel watermark
```

---

## Troubleshooting

**`ffmpeg not found`**
Install ffmpeg and make sure it's on your PATH.

**`No clips found`**
Add at least one of `PEXELS_API_KEY` or `PIXABAY_API_KEY` to `.env`.

**YouTube upload fails with `client_secrets.json not found`**
Download OAuth credentials from Google Cloud Console and place the file in the project root.

**`ANTHROPIC_API_KEY is not set`**
Create a `.env` file by copying `.env.example` and add your Anthropic API key.

**ElevenLabs quota exceeded**
Set `VOICE_PROVIDER=gtts` as fallback — it's completely free.

---

## Legal Notes

- Only download clips you have rights to use (Pexels & Pixabay are royalty-free)
- YouTube downloaded clips may have copyright restrictions — use for personal/test purposes only
- Always review auto-generated content before publishing
- Follow YouTube's Terms of Service regarding automated uploads
