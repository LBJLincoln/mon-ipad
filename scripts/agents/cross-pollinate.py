#!/usr/bin/env python3
"""
Cross-Pollination Agent — Weekly migration between 6 NBA evolution islands
==========================================================================
Reads /api/status from each HF Space, identifies the global best individual,
and injects its config into underperforming islands via POST /api/config or
POST /api/command (diversify).

Also detects stagnation and triggers diversity injection.

Cron: 0 4 * * 0 (every Sunday at 4am UTC)
"""

import json
import os
import sys
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ── Load .env.local ──
ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env.local"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = "6582544948"

# ── Island definitions ──
ISLANDS = {
    "S10": {"url": "nomos42-nba-quant", "role": "exploitation"},
    "S11": {"url": "nomos42-nba-quant-2", "role": "exploration"},
    "S12": {"url": "nomos42-nba-evo-3", "role": "extra_trees_specialist"},
    "S13": {"url": "nomos42-nba-evo-4", "role": "catboost_specialist"},
    "S14": {"url": "nomos42-nba-evo-5", "role": "lightgbm_specialist"},
    "S15": {"url": "nomos42-nba-evo-6", "role": "wide_search"},
    "S16": {"url": "lbjlincoln26-nba-evo-s16", "role": "gradient_boost"},
    "S17": {"url": "lbjlincoln26-nba-evo-s17", "role": "ensemble"},
}

# Thresholds
BRIER_MIGRATION_THRESHOLD = 0.005    # Migrate if island is >0.005 worse than best
STAGNATION_WARNING = 20              # Recommend diversity at this level
STAGNATION_CRITICAL = 25             # Auto-inject diversity at this level
STAGNATION_RESET = 40                # Recommend population reset at this level

# ── Logging ──
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs" / "agents"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
LOG_FILE = LOG_DIR / f"cross-pollinate-{TODAY}.log"


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def send_telegram(msg):
    """Send summary to Telegram."""
    if not TELEGRAM_TOKEN:
        log("WARN: No TELEGRAM_BOT_TOKEN set, skipping notification")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = json.dumps({
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "HTML",
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15)
        return True
    except Exception as e:
        log(f"Telegram error: {e}")
        return False


def get_island_status(label, space_url):
    """GET /api/status from an HF Space island."""
    url = f"https://{space_url}.hf.space/api/status"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Nomos42CrossPollinate/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
            return {
                "status": "UP",
                "best_brier": data.get("best_brier", 1.0),
                "best_model_type": data.get("best_model_type", "unknown"),
                "generation": data.get("generation", 0),
                "stagnation": data.get("stagnation", 0),
                "pop_size": data.get("pop_size", 0),
                "best_features": data.get("best_features", 0),
                "mutation_rate": data.get("mutation_rate", 0),
                "top5": data.get("top5", []),
                "raw": data,
            }
    except Exception as e:
        return {"status": "DOWN", "error": str(e)[:200]}


def post_config(space_url, params):
    """POST /api/config to update an island's GA parameters."""
    url = f"https://{space_url}.hf.space/api/config"
    try:
        payload = json.dumps(params).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "Nomos42CrossPollinate/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def post_command(space_url, command):
    """POST /api/command to execute a command on an island."""
    url = f"https://{space_url}.hf.space/api/command"
    try:
        payload = json.dumps({"command": command}).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "Nomos42CrossPollinate/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def post_reset(space_url):
    """POST /api/reset to trigger population reset on an island."""
    url = f"https://{space_url}.hf.space/api/reset"
    try:
        payload = json.dumps({}).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "Nomos42CrossPollinate/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def run_diversity_injector(label, space_url, stagnation):
    """Call the diversity injector for a stagnant island."""
    injector = Path(__file__).resolve().parent / "diversity-injector.py"
    if injector.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(injector), label, space_url, str(stagnation)],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                log(f"  Diversity injector ran OK for {label}: {result.stdout.strip()}")
                return True
            else:
                log(f"  Diversity injector failed for {label}: {result.stderr.strip()}")
                return False
        except Exception as e:
            log(f"  Diversity injector error for {label}: {e}")
            return False
    else:
        log(f"  Diversity injector script not found at {injector}")
        return False


def main():
    log("=" * 70)
    log("CROSS-POLLINATION AGENT START")
    log("=" * 70)

    # ── Phase 1: Collect status from all islands ──
    log("")
    log("--- Phase 1: Collecting status from 6 islands ---")
    statuses = {}
    for label, info in ISLANDS.items():
        status = get_island_status(label, info["url"])
        statuses[label] = status
        if status["status"] == "UP":
            log(f"  {label} ({info['role']}): UP | Brier={status['best_brier']:.5f} | "
                f"Model={status['best_model_type']} | Gen={status['generation']} | "
                f"Stag={status['stagnation']} | Feat={status['best_features']}")
        else:
            log(f"  {label} ({info['role']}): DOWN | {status.get('error', 'unknown')[:80]}")

    # ── Phase 2: Find global best ──
    log("")
    log("--- Phase 2: Identifying global best ---")
    up_islands = {k: v for k, v in statuses.items() if v["status"] == "UP" and v["best_brier"] < 1.0}

    if not up_islands:
        msg = "CROSS-POLLINATION ABORTED: No healthy islands with valid Brier scores"
        log(msg)
        send_telegram(f"<b>Cross-Pollination Failed</b>\n{msg}")
        return

    best_label = min(up_islands, key=lambda k: up_islands[k]["best_brier"])
    best_status = up_islands[best_label]
    best_brier = best_status["best_brier"]
    best_model = best_status["best_model_type"]
    best_gen = best_status["generation"]

    log(f"  GLOBAL BEST: {best_label} | Brier={best_brier:.5f} | Model={best_model} | Gen={best_gen}")

    # ── Phase 3: Cross-pollination — migrate best config to underperformers ──
    log("")
    log("--- Phase 3: Cross-pollination ---")
    migrated_to = []
    recommendations = []

    for label, status in up_islands.items():
        if label == best_label:
            continue

        gap = status["best_brier"] - best_brier
        if gap > BRIER_MIGRATION_THRESHOLD:
            log(f"  {label}: Brier gap = +{gap:.5f} (>{BRIER_MIGRATION_THRESHOLD}) -> MIGRATING")

            # Extract the best individual's config from top5 if available
            # We use /api/config to push GA parameters that nudge the island
            # toward the best individual's characteristics
            best_top5 = best_status.get("top5", [])
            if best_top5:
                best_ind = best_top5[0]
                best_hp = best_ind.get("hyperparams", {})
                target_features = best_ind.get("n_features", 80)

                # Push target_features to nudge feature selection toward the best's count
                config_update = {
                    "target_features": min(target_features, 150),
                }
                result = post_config(ISLANDS[label]["url"], config_update)
                if result["success"]:
                    log(f"    Config updated: target_features={target_features}")
                    migrated_to.append(label)
                else:
                    log(f"    Config update failed: {result.get('error', 'unknown')}")
                    recommendations.append(
                        f"{label}: Manual migration needed (Brier gap +{gap:.5f}). "
                        f"Best model: {best_model}, features: {target_features}"
                    )
            else:
                # No top5 data, just use the diversify command to shake things up
                result = post_command(ISLANDS[label]["url"], "diversify")
                if result["success"]:
                    log(f"    Diversify command sent (no top5 data for precise migration)")
                    migrated_to.append(label)
                else:
                    log(f"    Diversify failed: {result.get('error', 'unknown')}")
                    recommendations.append(
                        f"{label}: Manual diversify needed (Brier gap +{gap:.5f})"
                    )
        else:
            log(f"  {label}: Brier gap = +{gap:.5f} (<={BRIER_MIGRATION_THRESHOLD}) -> OK, no migration needed")

    # ── Phase 4: Stagnation detection and diversity injection ──
    log("")
    log("--- Phase 4: Stagnation detection ---")
    stagnant_islands = []
    critical_islands = []
    reset_islands = []

    for label, status in up_islands.items():
        stag = status.get("stagnation", 0)
        if stag >= STAGNATION_RESET:
            reset_islands.append((label, stag))
            log(f"  {label}: CRITICAL stagnation ({stag} gens) -> RESET RECOMMENDED")
            result = post_reset(ISLANDS[label]["url"])
            if result["success"]:
                log(f"    Reset command sent successfully")
            else:
                log(f"    Reset failed: {result.get('error', 'unknown')}")
                recommendations.append(f"{label}: Manual reset needed (stagnation={stag})")
        elif stag >= STAGNATION_CRITICAL:
            critical_islands.append((label, stag))
            log(f"  {label}: HIGH stagnation ({stag} gens) -> INJECTING DIVERSITY")
            injected = run_diversity_injector(label, ISLANDS[label]["url"], stag)
            if not injected:
                # Fallback: use diversify command
                result = post_command(ISLANDS[label]["url"], "diversify")
                if result["success"]:
                    log(f"    Diversify command sent as fallback")
                else:
                    recommendations.append(f"{label}: Diversity injection failed (stagnation={stag})")
        elif stag >= STAGNATION_WARNING:
            stagnant_islands.append((label, stag))
            log(f"  {label}: WARNING stagnation ({stag} gens) -> monitoring")
            recommendations.append(f"{label}: Stagnation at {stag} gens, consider manual intervention")
        else:
            log(f"  {label}: stagnation={stag} -> OK")

    # ── Phase 5: Down island alerts ──
    down_islands = [k for k, v in statuses.items() if v["status"] == "DOWN"]
    if down_islands:
        log("")
        log("--- Down islands ---")
        for label in down_islands:
            log(f"  {label}: DOWN - {statuses[label].get('error', 'unknown')[:100]}")

    # ── Phase 6: Summary ──
    log("")
    log("=" * 70)
    log("CROSS-POLLINATION SUMMARY")
    log("=" * 70)
    log(f"  Islands checked: {len(statuses)}")
    log(f"  Islands UP: {len(up_islands)}")
    log(f"  Islands DOWN: {len(down_islands)}")
    log(f"  Global best: {best_label} (Brier={best_brier:.5f}, {best_model})")
    log(f"  Migrations performed: {len(migrated_to)} -> {migrated_to}")
    log(f"  Stagnation warnings: {len(stagnant_islands)}")
    log(f"  Critical stagnation: {len(critical_islands)}")
    log(f"  Resets triggered: {len(reset_islands)}")
    log(f"  Recommendations: {len(recommendations)}")
    for r in recommendations:
        log(f"    - {r}")
    log("=" * 70)

    # ── Save report to data file ──
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "global_best": {
            "island": best_label,
            "brier": best_brier,
            "model": best_model,
            "generation": best_gen,
        },
        "islands": {
            label: {
                "status": s["status"],
                "brier": s.get("best_brier"),
                "model": s.get("best_model_type"),
                "generation": s.get("generation"),
                "stagnation": s.get("stagnation"),
            }
            for label, s in statuses.items()
        },
        "migrations": migrated_to,
        "stagnant": [{"island": l, "stagnation": s} for l, s in stagnant_islands],
        "critical": [{"island": l, "stagnation": s} for l, s in critical_islands],
        "resets": [{"island": l, "stagnation": s} for l, s in reset_islands],
        "down": down_islands,
        "recommendations": recommendations,
    }

    report_dir = Path(__file__).resolve().parent.parent.parent / "data" / "cross-pollination"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / f"report-{TODAY}.json"
    report_file.write_text(json.dumps(report, indent=2))
    log(f"Report saved: {report_file}")

    # ── Telegram summary ──
    tg_lines = ["<b>Cross-Pollination Report</b>"]
    tg_lines.append(f"Best: {best_label} ({best_model}) Brier={best_brier:.5f}")

    if migrated_to:
        tg_lines.append(f"Migrated to: {', '.join(migrated_to)}")
    else:
        tg_lines.append("No migrations needed (all within threshold)")

    if down_islands:
        tg_lines.append(f"DOWN: {', '.join(down_islands)}")

    if stagnant_islands or critical_islands or reset_islands:
        stag_labels = [f"{l}({s})" for l, s in stagnant_islands + critical_islands + reset_islands]
        tg_lines.append(f"Stagnation: {', '.join(stag_labels)}")

    # Island leaderboard
    tg_lines.append("")
    tg_lines.append("<b>Leaderboard:</b>")
    sorted_islands = sorted(up_islands.items(), key=lambda x: x[1]["best_brier"])
    for rank, (label, s) in enumerate(sorted_islands, 1):
        marker = " *" if label == best_label else ""
        tg_lines.append(f"  {rank}. {label}: {s['best_brier']:.5f} ({s['best_model_type']}){marker}")

    tg_msg = "\n".join(tg_lines)
    send_telegram(tg_msg)
    log("Telegram notification sent")
    log("CROSS-POLLINATION AGENT COMPLETE")


if __name__ == "__main__":
    main()
