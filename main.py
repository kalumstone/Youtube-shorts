"""
YouTube Shorts Automation Bot
==============================
Main orchestrator — ties together all modules into a complete pipeline:

  1. Find trending niches (AI + Google Trends)
  2. Find & download source clips (Pexels, Pixabay, Reddit, YouTube)
  3. Generate voiceover script + audio (Claude + ElevenLabs/gTTS)
  4. Edit video (resize, captions, hook, CTA, music)
  5. Generate SEO metadata (Claude)
  6. Generate thumbnail
  7. Upload to YouTube

Usage
-----
  # Run full pipeline once
  python main.py run

  # Run with a specific niche
  python main.py run --niche "motivational quotes"

  # Just find niches (research mode)
  python main.py niches

  # Authenticate YouTube (run once)
  python main.py auth

  # Schedule automated runs
  python main.py schedule --cron "0 9 * * *"

  # Dry run (no upload)
  python main.py run --dry-run
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

import click
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

import config

console = Console()


# ---------------------------------------------------------------------------
# CLI setup
# ---------------------------------------------------------------------------

@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def cli(verbose: bool) -> None:
    """YouTube Shorts Automation Bot powered by Claude AI."""
    level = "DEBUG" if verbose else "INFO"
    logger.remove()
    logger.add(sys.stderr, level=level, colorize=True, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
    logger.add("output/bot.log", level="DEBUG", rotation="10 MB")


@cli.command()
@click.option("--niche", "-n", default="", help="Target niche (leave blank for AI to choose)")
@click.option("--count", "-c", default=None, type=int, help="Number of Shorts to produce")
@click.option("--dry-run", is_flag=True, help="Produce videos but do not upload")
@click.option("--no-trends", is_flag=True, help="Skip Google Trends enrichment")
def run(niche: str, count: Optional[int], dry_run: bool, no_trends: bool) -> None:
    """Run the full Short-creation pipeline."""
    try:
        config.validate()
    except EnvironmentError as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        sys.exit(1)

    shorts_count = count or config.SHORTS_PER_RUN
    target_niche = niche or config.TARGET_NICHE

    console.print(
        Panel.fit(
            f"[bold cyan]YouTube Shorts Bot[/bold cyan]\n"
            f"Producing [bold]{shorts_count}[/bold] Short(s)"
            + (f" in niche: [yellow]{target_niche}[/yellow]" if target_niche else " (AI picks niche)")
            + ("\n[yellow]DRY RUN — will not upload[/yellow]" if dry_run else ""),
            border_style="cyan",
        )
    )

    _run_pipeline(
        target_niche=target_niche,
        shorts_count=shorts_count,
        dry_run=dry_run,
        use_trends=not no_trends,
    )


@cli.command()
@click.option("--niche", "-n", default="", help="Niche to research (blank = broad scan)")
@click.option("--count", "-c", default=5, help="Number of niches to return")
def niches(niche: str, count: int) -> None:
    """Research and display top YouTube Shorts niches."""
    try:
        config.validate()
    except EnvironmentError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)

    from modules.niche_finder import find_niches

    results = find_niches(target_niche=niche, count=count)

    table = Table(title="Top YouTube Shorts Niches (2025-2026 Data)", border_style="cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Niche", style="bold white")
    table.add_column("Score", style="green", justify="center")
    table.add_column("CPM", style="yellow", justify="center")
    table.add_column("Length", style="magenta", justify="center")
    table.add_column("Trend", style="cyan", justify="center")
    table.add_column("Best Hook", style="white")

    for i, n in enumerate(results, 1):
        trend_str = f"{n.trending_score:.0f}" if n.trending_score is not None else "—"
        cpm_str = f"${n.cpm:.2f}" if hasattr(n, "cpm") and n.cpm else "—"
        length_str = f"{n.optimal_length}s" if hasattr(n, "optimal_length") else "—"
        hook = n.hooks[0][:45] + "…" if hasattr(n, "hooks") and n.hooks else "—"
        table.add_row(
            str(i),
            n.name,
            f"{n.score:.1f}/10",
            cpm_str,
            length_str,
            trend_str,
            hook,
        )

    console.print(table)

    # Also print content angles
    for i, n in enumerate(results, 1):
        angles = getattr(n, "content_angles", [])
        if angles:
            console.print(f"\n[bold cyan]#{i} {n.name} — Content Angles:[/bold cyan]")
            for a in angles[:3]:
                console.print(f"  [white]• {a}[/white]")


@cli.command()
def auth() -> None:
    """Authenticate with YouTube (run once to set up OAuth)."""
    from modules.youtube_uploader import authenticate
    console.print("[cyan]Opening browser for YouTube OAuth authentication…[/cyan]")
    authenticate()
    console.print("[green]✅ Authentication complete![/green]")


@cli.command()
@click.option("--cron", default="0 9 * * *", help="Cron expression (default: daily at 9am)")
@click.option("--niche", "-n", default="", help="Target niche")
def schedule(cron: str, niche: str) -> None:
    """Run the bot on a recurring schedule."""
    try:
        import schedule as sched
        import croniter
    except ImportError:
        console.print("[red]Install schedule and croniter: pip install schedule croniter[/red]")
        sys.exit(1)

    console.print(f"[cyan]Scheduling bot with cron: [bold]{cron}[/bold][/cyan]")

    def job():
        logger.info("⏰ Scheduled run triggered")
        _run_pipeline(target_niche=niche, shorts_count=config.SHORTS_PER_RUN)

    # Simple daily scheduler using the schedule library
    sched.every().day.at("09:00").do(job)

    console.print("[green]Scheduler running. Press Ctrl+C to stop.[/green]")
    while True:
        sched.run_pending()
        time.sleep(60)


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def _run_pipeline(
    target_niche: str = "",
    shorts_count: int = 1,
    dry_run: bool = False,
    use_trends: bool = True,
) -> None:
    """Execute the end-to-end pipeline for `shorts_count` videos."""
    from modules.niche_finder import find_niches, Niche
    from modules.clip_finder import find_clips
    from modules.voiceover import create_voiceover_from_niche
    from modules.video_editor import edit_clip
    from modules.metadata_generator import generate_metadata
    from modules.thumbnail_generator import generate_thumbnail
    from modules.youtube_uploader import upload_short

    produced: list[dict] = []

    # ── Step 1: Discover niches ──────────────────────────────────────────────
    console.rule("[bold cyan]Step 1: Niche Discovery[/bold cyan]")
    niches = find_niches(
        target_niche=target_niche,
        count=max(shorts_count, 3),
        use_trends=use_trends,
    )
    if not niches:
        logger.error("No niches found — check ANTHROPIC_API_KEY")
        return

    for short_idx in range(shorts_count):
        niche = niches[short_idx % len(niches)]
        angle = niche.content_angles[0] if niche.content_angles else niche.name

        console.rule(f"[bold yellow]Short #{short_idx + 1}/{shorts_count} — {niche.name}[/bold yellow]")
        logger.info(f"Niche: {niche.name} | Angle: {angle}")

        # ── Step 2: Find clips ───────────────────────────────────────────────
        console.rule("[cyan]Step 2: Finding Clips[/cyan]")
        clips = find_clips(
            niche_keywords=niche.keywords,
            count=3,
            max_duration=config.MAX_CLIP_DURATION,
        )
        if not clips:
            logger.warning("No clips found — skipping this Short")
            continue

        clip = clips[0]   # Use best available clip

        # ── Step 3: Voiceover ────────────────────────────────────────────────
        console.rule("[cyan]Step 3: Voiceover Generation[/cyan]")
        try:
            vo_path, script, lines, hook, cta = create_voiceover_from_niche(
                niche=niche.name,
                content_angle=angle,
                duration_seconds=getattr(niche, "optimal_length", 30),
                hook_suggestion=niche.best_hook() if hasattr(niche, "best_hook") else "",
                style_notes=getattr(niche, "style", ""),
            )
        except Exception as exc:
            logger.error(f"Voiceover failed: {exc}")
            vo_path, script, lines, hook, cta = None, "", [], "", "Follow for more!"

        # ── Step 4: Edit video ───────────────────────────────────────────────
        console.rule("[cyan]Step 4: Video Editing[/cyan]")
        try:
            edited = edit_clip(
                clip_path=clip.local_path,
                voiceover_path=vo_path,
                script_lines=lines,
                hook_text=hook or niche.best_hook() if hasattr(niche, "best_hook") else hook or niche.name,
                cta_text=cta,
                background_music_path=_find_background_music(),
            )
        except Exception as exc:
            logger.error(f"Video editing failed: {exc}")
            continue

        # ── Step 5: Metadata ─────────────────────────────────────────────────
        console.rule("[cyan]Step 5: Metadata Generation[/cyan]")
        metadata = generate_metadata(
            niche=niche.name,
            content_angle=angle,
            script_excerpt=" ".join(lines[:3]),
            hook_text=hook,
        )

        # ── Step 6: Thumbnail ────────────────────────────────────────────────
        console.rule("[cyan]Step 6: Thumbnail Creation[/cyan]")
        thumb_path = generate_thumbnail(
            video_path=edited.path,
            text=metadata.thumbnail_text or metadata.title,
        )

        # ── Step 7: Upload ───────────────────────────────────────────────────
        console.rule("[cyan]Step 7: YouTube Upload[/cyan]")
        video_id = None
        if dry_run:
            logger.info("DRY RUN — skipping upload")
        elif config.AUTO_UPLOAD:
            video_id = upload_short(
                video_path=edited.path,
                metadata=metadata,
                thumbnail_path=thumb_path,
            )
        else:
            logger.info("AUTO_UPLOAD=false — video saved locally only")

        produced.append({
            "niche": niche.name,
            "angle": angle,
            "title": metadata.title,
            "video_path": str(edited.path),
            "video_id": video_id,
            "url": f"https://www.youtube.com/shorts/{video_id}" if video_id else "not uploaded",
        })

        logger.info(f"✅ Short #{short_idx + 1} complete")

    # ── Summary ──────────────────────────────────────────────────────────────
    console.rule("[bold green]Pipeline Complete[/bold green]")
    table = Table(title="Produced Shorts", border_style="green")
    table.add_column("#", width=3)
    table.add_column("Title", style="bold white")
    table.add_column("Niche", style="cyan")
    table.add_column("URL / Path", style="yellow")

    for i, item in enumerate(produced, 1):
        table.add_row(
            str(i),
            item["title"][:60],
            item["niche"],
            item["url"] if item["video_id"] else item["video_path"],
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_background_music() -> Optional[Path]:
    """Return first available background music file, or None."""
    music_dir = config.MUSIC_DIR
    if not music_dir.exists():
        return None
    for ext in ("*.mp3", "*.wav", "*.m4a"):
        matches = list(music_dir.glob(ext))
        if matches:
            return matches[0]
    return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
