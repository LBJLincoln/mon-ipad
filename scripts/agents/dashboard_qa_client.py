#!/usr/bin/env python3
"""
dashboard_qa_client — cross-repo guardrail that pings the browser-use QA Space
(TESTforge42/nomos-browser-qa) against the Vercel-hosted nomos-dashboard.

Purpose:
    Catch dashboard regressions BEFORE the user sees them. Runs from the
    mon-ipad CI (`.github/workflows/dashboard-qa.yml`) + optionally from the
    nomos-dashboard repo's own `main` push workflow.

Exit codes:
    0  QA returned status=pass
    1  QA returned status!=pass (fails CI)
    2  Space probe failed (network, 503, etc.)
    3  QA run itself failed (timeout, 5xx on /api/qa-dashboard)

Env:
    BROWSER_QA_URL    override base URL (default TESTforge42/nomos-browser-qa)
    DASHBOARD_URL     URL to QA (default https://nomosdashboard.vercel.app)
    QA_ROUTES         comma-separated routes to click through
                      (default: /,/nba,/political,/trading-floor,/world)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "data" / "qa" / "dashboard"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_URL = "https://testforge42-nomos-browser-qa.hf.space"
BASE = os.environ.get("BROWSER_QA_URL", DEFAULT_URL).rstrip("/")
TARGET = os.environ.get("DASHBOARD_URL", "https://nomosdashboard.vercel.app").rstrip("/")
ROUTES = [
    r.strip()
    for r in os.environ.get(
        "QA_ROUTES", "/,/nba,/political,/trading-floor,/world"
    ).split(",")
    if r.strip()
]
TIMEOUT = float(os.environ.get("BROWSER_QA_TIMEOUT", "240"))


def main() -> int:
    # 1. Probe Space.
    try:
        probe = httpx.get(f"{BASE}/api/status", timeout=15).json()
    except Exception as e:
        print(f"[dashboard-qa] status probe failed: {e}", file=sys.stderr)
        return 2

    if not probe.get("playwright_available"):
        print(
            f"[dashboard-qa] Space reports playwright unavailable: "
            f"{probe.get('playwright_import_error')}",
            file=sys.stderr,
        )
        return 2

    # 2. Trigger QA run.
    payload = {
        "url": TARGET,
        "routes": ROUTES,
        "assert_no_ts_errors": True,
        "assert_stripe_link_present": True,
    }
    print(f"[dashboard-qa] POST {BASE}/api/qa-dashboard  target={TARGET}  routes={ROUTES}")

    try:
        r = httpx.post(f"{BASE}/api/qa-dashboard", json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        run = r.json()
    except Exception as e:
        print(f"[dashboard-qa] run failed: {e}", file=sys.stderr)
        return 3

    # 3. Persist (without heavy screenshot payload).
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = OUT_DIR / f"dashboard-qa-{ts}.json"
    if isinstance(run.get("details"), dict):
        run["details"].pop("screenshot_b64_preview", None)
    out.write_text(json.dumps(run, indent=2))

    # The QA Space returns either status="pass"|"fail" or a bool `passed`.
    status = run.get("status", "pass" if run.get("passed") else "fail")
    details = run.get("details", {})
    print(
        f"[dashboard-qa] status={status}  routes_checked={details.get('routes_checked')}"
        f"  console_errors={len(details.get('console_errors', []))}"
        f"  -> {out}"
    )
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
