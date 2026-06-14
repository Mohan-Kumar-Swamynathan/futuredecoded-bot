"""CLI entry point for FutureDecoded V4."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure src is on path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from futuredecoded.config.logging_config import configure_logging
from futuredecoded.config.settings import get_settings
from futuredecoded.pipeline.orchestrator import run_daily_pipeline
from futuredecoded.publish.youtube_uploader import get_authenticated_service


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FutureDecoded V4 — AI & Tech News YouTube Automation"
    )
    parser.add_argument("--daily", action="store_true", help="Run daily pipeline")
    parser.add_argument("--upload", action="store_true", help="Upload to YouTube")
    parser.add_argument("--dry-run", action="store_true", help="Skip uploads")
    parser.add_argument("--auth-youtube", action="store_true", help="Run YouTube OAuth")
    args = parser.parse_args()

    settings = get_settings()
    if args.dry_run:
        settings.dry_run = True
    configure_logging(settings.log_level)
    settings.ensure_dirs()

    logger = logging.getLogger("futuredecoded.main")

    if args.auth_youtube:
        service = get_authenticated_service()
        if service:
            logger.info("YouTube auth successful → %s", settings.youtube_token_file)
        else:
            logger.error("YouTube auth failed")
            sys.exit(1)
        return

    if args.daily:
        result = run_daily_pipeline(upload=args.upload and not args.dry_run)
        if result.success:
            logger.info(
                "Pipeline complete: %s | long=%s short=%s",
                result.story_title[:50],
                result.long_video_id,
                result.short_video_id,
            )
        else:
            logger.error("Pipeline failed: %s", result.error)
            sys.exit(1)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
