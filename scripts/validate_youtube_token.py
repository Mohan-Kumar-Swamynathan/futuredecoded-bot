#!/usr/bin/env python3
"""Validate YouTube OAuth token before CI upload attempts."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def main() -> int:
    try:
        from futuredecoded.publish.youtube_uploader import get_authenticated_service

        service = get_authenticated_service()
        if service is None:
            print("ERROR: Could not authenticate YouTube service")
            return 1
        print("OK: YouTube token is valid for upload")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
