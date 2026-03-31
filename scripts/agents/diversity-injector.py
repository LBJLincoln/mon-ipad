#!/usr/bin/env python3
"""
Diversity Injector — Injects randomized configs into stagnant evolution islands
================================================================================
Called by cross-pollinate.py when an island has stagnation > 25.
Can also be run standalone:
    python diversity-injector.py S10 nomos42-nba-quant 30

Actions:
  1. Generates a random but valid individual config
  2. POSTs mutation boost via /api/config (increases mutation rate temporarily)
  3. POSTs /api/command diversify (replaces 1/3 of population with fresh individuals)
  4. Logs the injection
"""

import json
import os
import sys
import random
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

# Valid tree-based model types (CPU-only islands)
CPU_MODEL_TYPES = [
    "random_forest",
    "extra_trees",
    "gradient_boosting",
    "catboost",
    "lightgbm",
    "xgboost",
]

# ── Logging ──
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs" / "agents"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
LOG_FILE = LOG_DIR / f"diversity-injector-{TODAY}.log"


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def send_telegram(msg):
    """Send notification to Telegram."""
    if not TELEGRAM_TOKEN:
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


def generate_random_config():
    """Generate a random but valid individual configuration."""
    model_type = random.choice(CPU_MODEL_TYPES)
    n_features = random.randint(30, 150)

    config = {
        "model_type": model_type,
        "n_features": n_features,
        "n_estimators": random.randint(50, 300),
        "max_depth": random.randint(3, 10),
        "learning_rate": round(10 ** random.uniform(-2.5, -0.5), 6),
        "subsample": round(random.uniform(0.5, 1.0), 3),
        "colsample_bytree": round(random.uniform(0.3, 1.0), 3),
        "min_child_weight": random.randint(1, 15),
        "reg_alpha": round(10 ** random.uniform(-6, 1), 8),
        "reg_lambda": round(10 ** random.uniform(-6, 1), 8),
        "calibration": random.choice(["none", "sigmoid", "venn_abers", "beta"]),
    }

    return config


def post_config(space_url, params):
    """POST /api/config to update GA parameters."""
    url = f"https://{space_url}.hf.space/api/config"
    try:
        payload = json.dumps(params).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "Nomos42DiversityInjector/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)[:200]}


def post_command(space_url, command):
    """POST /api/command to execute a command."""
    url = f"https://{space_url}.hf.space/api/command"
    try:
        payload = json.dumps({"command": command}).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "Nomos42DiversityInjector/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)[:200]}


def inject_diversity(label, space_url, stagnation):
    """Perform diversity injection on a stagnant island."""
    log(f"DIVERSITY INJECTION: {label} ({space_url}) — stagnation={stagnation}")

    actions_taken = []
    random_config = generate_random_config()
    log(f"  Generated random config: model={random_config['model_type']}, "
        f"features={random_config['n_features']}, depth={random_config['max_depth']}")

    # Step 1: Boost mutation rate via /api/config
    # Push target_features from the random config to introduce variety
    config_params = {
        "mutation_rate": 0.15,  # Max allowed mutation (capped at 0.15 in app.py)
        "target_features": random_config["n_features"],
    }
    log(f"  Step 1: Boosting mutation to 0.15, target_features={random_config['n_features']}")
    result = post_config(space_url, config_params)
    if "error" not in result:
        log(f"    Config update OK: {result}")
        actions_taken.append("mutation_boost")
    else:
        log(f"    Config update FAILED: {result}")

    # Step 2: Send diversify command (replaces 1/3 of population)
    log(f"  Step 2: Sending diversify command")
    result = post_command(space_url, "diversify")
    if "error" not in result:
        log(f"    Diversify OK: {result}")
        actions_taken.append("diversify")
    else:
        log(f"    Diversify FAILED: {result}")

    # Step 3: If stagnation is extreme, also boost mutation further
    if stagnation >= 35:
        log(f"  Step 3: Extreme stagnation ({stagnation}), sending boost_mutation command")
        result = post_command(space_url, "boost_mutation")
        if "error" not in result:
            log(f"    Boost mutation OK: {result}")
            actions_taken.append("boost_mutation_cmd")
        else:
            log(f"    Boost mutation FAILED: {result}")

    # Log summary
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "island": label,
        "space_url": space_url,
        "stagnation": stagnation,
        "random_config": random_config,
        "actions_taken": actions_taken,
    }

    # Save injection log
    inject_dir = Path(__file__).resolve().parent.parent.parent / "data" / "cross-pollination"
    inject_dir.mkdir(parents=True, exist_ok=True)
    inject_file = inject_dir / f"injection-{label}-{TODAY}.json"
    inject_file.write_text(json.dumps(summary, indent=2))
    log(f"  Injection log saved: {inject_file}")

    success = len(actions_taken) > 0
    if success:
        log(f"  INJECTION COMPLETE: {len(actions_taken)} actions taken for {label}")
    else:
        log(f"  INJECTION FAILED: No actions succeeded for {label}")

    return success


def main():
    """
    Usage: diversity-injector.py <label> <space_url> <stagnation>
    Example: diversity-injector.py S10 nomos42-nba-quant 30
    """
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <label> <space_url> <stagnation>")
        print(f"Example: {sys.argv[0]} S10 nomos42-nba-quant 30")
        sys.exit(1)

    label = sys.argv[1]
    space_url = sys.argv[2]
    stagnation = int(sys.argv[3])

    success = inject_diversity(label, space_url, stagnation)

    if success:
        send_telegram(
            f"<b>Diversity Injected</b>\n"
            f"Island: {label} (stagnation={stagnation})\n"
            f"Actions: mutation boost + diversify"
        )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
