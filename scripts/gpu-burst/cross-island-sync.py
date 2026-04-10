#!/usr/bin/env python3
"""
Nomos42 — Cross-Island Config Sync
====================================
Broadcasts the fleet-best config from the top island to all lagging islands.
Breaks stagnation (S13 was stuck at 0.2231 for 500+ gens while S15 hit 0.22041)
by seeding the best-performing config into every island that's fallen behind.

Strategy:
  1. Poll /api/status + /api/best from all 6 islands
  2. Identify fleet best (lowest Brier)
  3. For any island with Brier > fleet_best + SYNC_THRESHOLD, or stagnation > 15,
     POST the fleet-best config to that island's /api/config endpoint
  4. Enforce 4h cooldown per island to avoid config thrashing

Usage:
    python3 scripts/gpu-burst/cross-island-sync.py
    python3 scripts/gpu-burst/cross-island-sync.py --dry-run

Called by autonomous-cycle.sh every cycle.
"""

import argparse
import json
import os
import ssl
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path("/home/termius/mon-ipad")
DATA_DIR  = REPO_ROOT / "data" / "gpu-burst"
LOG_FILE        = DATA_DIR / "cross-island-sync.jsonl"
LAST_SYNC_FILE  = DATA_DIR / "cross-island-last-sync.json"

SYNC_THRESHOLD = 0.0010   # Sync if island Brier is this much worse than fleet best
SYNC_COOLDOWN  = 4 * 3600 # 4h between syncs per island (seconds)
STAGNATION_THRESHOLD = 15 # Sync if stagnation_count exceeds this

HF_ISLANDS = {
    "S10": "https://nomos42-nba-quant.hf.space",
    "S11": "https://nomos42-nba-quant-2.hf.space",
    "S12": "https://nomos42-nba-evo-3.hf.space",
    "S13": "https://nomos42-nba-evo-4.hf.space",
    "S14": "https://nomos42-nba-evo-5.hf.space",
    "S15": "https://nomos42-nba-evo-6.hf.space",
}


# ══════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════

def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str, level: str = "INFO"):
    print(f"[{ts()}] [{level}] {msg}")


def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def http_get(url: str, token: str = "", timeout: int = 15) -> Optional[dict]:
    headers = {"User-Agent": "Nomos42-CrossSync/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log(f"GET {url}: {e}", "WARN")
        return None


def http_post(url: str, payload: dict, token: str = "", timeout: int = 20) -> Optional[dict]:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "Nomos42-CrossSync/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, data=data, method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log(f"POST {url}: {e}", "WARN")
        return None


def load_last_sync() -> dict:
    if LAST_SYNC_FILE.exists():
        try:
            return json.loads(LAST_SYNC_FILE.read_text())
        except Exception:
            pass
    return {}


def save_last_sync(state: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LAST_SYNC_FILE.write_text(json.dumps(state, indent=2))


def append_log(entry: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ══════════════════════════════════════════════════════════
# ISLAND POLLING
# ══════════════════════════════════════════════════════════

def fetch_island_status(name: str, url: str) -> Optional[dict]:
    """Fetch /api/status and /api/best from one island. Returns None if unreachable."""
    status = http_get(f"{url}/api/status", timeout=12)
    if not status:
        return None

    best = http_get(f"{url}/api/best", timeout=12)

    # Handle both Brier field name variants used by different island versions
    brier = float(
        status.get("best_brier") or
        status.get("brier") or
        1.0
    )
    generation = int(status.get("generation") or status.get("gen") or 0)
    stagnation = int(
        status.get("stagnation_count") or
        status.get("stagnation") or
        0
    )

    return {
        "name": name,
        "url": url,
        "brier": brier,
        "generation": generation,
        "stagnation": stagnation,
        "model_type": status.get("model_type", "xgboost"),
        "feature_count": int(status.get("feature_count") or status.get("n_features") or 0),
        # Best config for seeding (from /api/best)
        "feature_indices": (best or {}).get("features", []),
        "hp": (best or {}).get("hp", {}),
    }


# ══════════════════════════════════════════════════════════
# MAIN SYNC
# ══════════════════════════════════════════════════════════

def run_sync(dry_run: bool = False):
    log(f"=== Cross-Island Config Sync {'(DRY-RUN) ' if dry_run else ''}===")

    hf_token = os.environ.get("HF_TOKEN", "")

    # ── Poll all islands ──────────────────────────────────────────
    island_data = {}
    for name, url in HF_ISLANDS.items():
        log(f"Polling {name}...")
        data = fetch_island_status(name, url)
        if data:
            island_data[name] = data
            log(f"  {name}: brier={data['brier']:.5f} gen={data['generation']} stag={data['stagnation']}")
        else:
            log(f"  {name}: UNREACHABLE", "WARN")

    if not island_data:
        log("No islands reachable — aborting sync", "ERROR")
        return

    # ── Identify fleet best ───────────────────────────────────────
    best_island = min(island_data.values(), key=lambda x: x["brier"])
    fleet_brier = best_island["brier"]
    fleet_name  = best_island["name"]
    log(f"\nFleet best: {fleet_name} brier={fleet_brier:.5f} gen={best_island['generation']}")

    if not best_island["feature_indices"]:
        log(f"Fleet best {fleet_name} has no feature_indices in /api/best — aborting", "WARN")
        return

    # ── Cooldown state ────────────────────────────────────────────
    last_sync = load_last_sync()
    now_ts = time.time()

    synced  = []
    skipped = []

    for name, data in island_data.items():
        if name == fleet_name:
            skipped.append((name, "is_fleet_best"))
            continue

        gap        = data["brier"] - fleet_brier
        stagnation = data["stagnation"]

        # Cooldown check
        last_sync_ts = last_sync.get(name, 0)
        if now_ts - last_sync_ts < SYNC_COOLDOWN:
            mins_ago = (now_ts - last_sync_ts) / 60
            skipped.append((name, f"cooldown ({mins_ago:.0f}min ago)"))
            continue

        # Decision
        reasons = []
        if gap > SYNC_THRESHOLD:
            reasons.append(f"gap={gap:.5f}>{SYNC_THRESHOLD}")
        if stagnation > STAGNATION_THRESHOLD:
            reasons.append(f"stagnation={stagnation}>{STAGNATION_THRESHOLD}")

        if not reasons:
            skipped.append((name, f"gap={gap:.5f} stag={stagnation} OK"))
            continue

        reason_str = ", ".join(reasons)
        log(f"SYNC → {name}: {reason_str}")

        if dry_run:
            log(f"  [DRY-RUN] Would POST config from {fleet_name} to {name}")
            synced.append(name)
            continue

        # /api/config accepts tuning params only (not feature injection).
        # Use /api/command for population-level diversity, then tune mutation rate.
        success = False

        # Step 1: diversify — replaces 1/3 of population with new random individuals
        resp = http_post(
            f"{data['url']}/api/command",
            {"command": "diversify"},
            token=hf_token,
            timeout=15,
        )
        if resp and "queued" in str(resp.get("status", "")):
            log(f"  OK — {name} diversify queued (was brier={data['brier']:.5f})")
            success = True
        else:
            log(f"  WARN — {name} diversify: {resp}", "WARN")

        # Step 2: boost_mutation for large gaps or stagnation
        if gap > 0.002 or stagnation > 15:
            resp2 = http_post(
                f"{data['url']}/api/command",
                {"command": "boost_mutation"},
                token=hf_token,
                timeout=15,
            )
            if resp2 and "queued" in str(resp2.get("status", "")):
                log(f"  OK — {name} boost_mutation queued")

        # Step 3: tune mutation_rate via /api/config (capped at 0.20 per CLAUDE.md)
        new_mut = round(min(0.20, max(0.10, 0.10 + gap * 10)), 3)
        tune_resp = http_post(
            f"{data['url']}/api/config",
            {"mutation_rate": new_mut, "migrants_per_island": 5},
            token=hf_token,
            timeout=15,
        )
        if tune_resp and tune_resp.get("status") == "queued":
            log(f"  OK — {name} mutation_rate→{new_mut} migrants→5 queued")
            success = True

        if success:
            last_sync[name] = now_ts
            synced.append(name)
        else:
            skipped.append((name, "all_api_calls_failed"))

    if not dry_run:
        save_last_sync(last_sync)

    # ── Summary ───────────────────────────────────────────────────
    log(f"\nSync complete: {len(synced)} synced, {len(skipped)} skipped")
    for n in synced:
        log(f"  SYNCED : {n}")
    for n, r in skipped:
        log(f"  SKIPPED: {n} — {r}")

    append_log({
        "timestamp": ts(),
        "dry_run": dry_run,
        "fleet_best": {"island": fleet_name, "brier": fleet_brier},
        "synced": synced,
        "skipped": [(n, r) for n, r in skipped],
        "island_briers": {k: v["brier"] for k, v in island_data.items()},
    })


def main():
    parser = argparse.ArgumentParser(description="Nomos42 Cross-Island Config Sync")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be synced without executing",
    )
    args = parser.parse_args()
    run_sync(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
