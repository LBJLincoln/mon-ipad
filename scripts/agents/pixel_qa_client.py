#!/usr/bin/env python3
"""
pixel_qa_client — triggers TESTforge42/nomos-browser-qa after a PIXEL commit.

Usage:
    python scripts/agents/pixel_qa_client.py

Env:
    BROWSER_QA_URL   override base URL (default: TESTforge42/nomos-browser-qa)
    PIXEL_WORLD_URL  override target pixel world (default: Nomos42/pixel-world)
    QA_MIN_SPRITES   minimum expected sprite count (default: 40)

Exits non-zero if QA run fails (pipes into CI / GitHub Actions).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "data" / "qa" / "pixel"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_URL = "https://testforge42-nomos-browser-qa.hf.space"
BASE = os.environ.get("BROWSER_QA_URL", DEFAULT_URL).rstrip("/")
PIXEL_URL = os.environ.get(
    "PIXEL_WORLD_URL", "https://nomos42-pixel-world.static.hf.space"
)
MIN_SPRITES = int(os.environ.get("QA_MIN_SPRITES", "40"))


def main() -> int:
    payload = {"url": PIXEL_URL, "min_sprites": MIN_SPRITES, "capture_screenshot": True}

    try:
        probe = httpx.get(f"{BASE}/api/status", timeout=15).json()
    except Exception as e:
        print(f"[pixel-qa] status probe failed: {e}", file=sys.stderr)
        return 2

    if not probe.get("playwright_available"):
        print(
            f"[pixel-qa] Space reports playwright unavailable: "
            f"{probe.get('playwright_import_error')}",
            file=sys.stderr,
        )
        return 3

    print(f"[pixel-qa] POST {BASE}/api/qa-pixel  target={PIXEL_URL}")
    try:
        r = httpx.post(f"{BASE}/api/qa-pixel", json=payload, timeout=180)
        r.raise_for_status()
        run = r.json()
    except Exception as e:
        print(f"[pixel-qa] run failed: {e}", file=sys.stderr)
        return 4

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = OUT_DIR / f"pixel-qa-{ts}.json"
    # Drop the base64 screenshot payload from the local cache (too heavy for git).
    if isinstance(run.get("details"), dict):
        run["details"].pop("screenshot_b64_preview", None)
    out.write_text(json.dumps(run, indent=2))

    passed = bool(run.get("passed"))
    details = run.get("details", {})
    print(
        f"[pixel-qa] passed={passed}  sprites={details.get('sprite_count')} "
        f"hp_bars={details.get('hp_bar_count')} "
        f"console_errors={len(details.get('console_errors', []))}  -> {out}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
