#!/usr/bin/env python3
"""Champion-preserve — auto-checkpoint any NBA/POL agent that crosses 5x seed.

The April 22 post-mortem pattern: qwen-arb compounded from $100 -> $10,310 in
4h and got reset. PQTF is our only $100K+ artifact because it was frozen
before anyone could reset it.

Rule: every run, pull the NBA and POL leaderboards. For any agent whose
bankroll >= 5x its seed ($500 with default $100 seeds), snapshot the agent's
full state to data/champions/<tf>/<agent_id>/<ts>.json. These snapshots are
committed and indexed so the $500 agent is preserved before the next reset,
regardless of whether the reset is legitimate or false-positive leakage.

Usage:
  scripts/ops/champion_preserve.py scan            # snapshot all current champions
  scripts/ops/champion_preserve.py list            # list preserved champions
  scripts/ops/champion_preserve.py threshold 1000  # change the $ threshold

Stored at data/champions/<tf>/<agent>/<ts>.json plus data/champions/index.json.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHAMP_DIR = REPO / "data" / "champions"
INDEX_FILE = CHAMP_DIR / "index.json"
CONFIG_FILE = CHAMP_DIR / "config.json"

DEFAULT_THRESHOLD_USD = 500.0  # 5x default $100 seed
DEFAULT_SEED_USD = 100.0

LEADERBOARDS = {
    "nba": "https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/leaderboard",
    "pol": "https://lbjlincoln26-political-llm-trading-floor.hf.space/api/leaderboard",
}

HTTP_TIMEOUT = 15


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {"threshold_usd": DEFAULT_THRESHOLD_USD, "seed_usd": DEFAULT_SEED_USD}


def _save_config(cfg: dict) -> None:
    CHAMP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, sort_keys=True))


def _load_index() -> dict:
    if INDEX_FILE.exists():
        try:
            return json.loads(INDEX_FILE.read_text())
        except Exception:
            pass
    return {"champions": [], "updated_at": None}


def _save_index(idx: dict) -> None:
    idx["updated_at"] = _now().isoformat()
    CHAMP_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(idx, indent=2, sort_keys=True))


def _http_get_json(url: str) -> tuple[dict | list | None, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "nomos-champion-preserve"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", errors="replace")), ""
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _snapshot_agent(tf: str, agent: dict, threshold: float) -> Path | None:
    tid = agent.get("trader_id") or agent.get("id")
    if not tid:
        return None
    bankroll = float(agent.get("bankroll") or 0.0)
    if bankroll < threshold:
        return None

    ts = _now().strftime("%Y%m%dT%H%M%SZ")
    agent_dir = CHAMP_DIR / tf / str(tid)
    agent_dir.mkdir(parents=True, exist_ok=True)
    snap_path = agent_dir / f"{ts}.json"

    payload = {
        "tf": tf,
        "trader_id": tid,
        "captured_at": _now().isoformat(),
        "threshold_usd": threshold,
        "agent": agent,
    }
    snap_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return snap_path


def scan() -> int:
    cfg = _load_config()
    threshold = float(cfg.get("threshold_usd") or DEFAULT_THRESHOLD_USD)
    idx = _load_index()
    champions = idx.get("champions", [])

    captured: list[dict] = []
    errors: list[str] = []

    for tf, url in LEADERBOARDS.items():
        data, err = _http_get_json(url)
        if err:
            errors.append(f"{tf}: {err}")
            continue
        # Accept either a bare list or {"leaderboard": [...]}.
        if isinstance(data, dict):
            rows = data.get("leaderboard") or data.get("agents") or []
            if isinstance(rows, dict):
                rows = list(rows.values())
        elif isinstance(data, list):
            rows = data
        else:
            rows = []

        for agent in rows:
            if not isinstance(agent, dict):
                continue
            p = _snapshot_agent(tf, agent, threshold)
            if p is None:
                continue
            entry = {
                "tf": tf,
                "trader_id": agent.get("trader_id") or agent.get("id"),
                "bankroll": float(agent.get("bankroll") or 0.0),
                "roi_pct": agent.get("roi_pct"),
                "days_traded": agent.get("days_traded"),
                "captured_at": _now().isoformat(),
                "snapshot_path": str(p.relative_to(REPO)),
            }
            champions.append(entry)
            captured.append(entry)

    idx["champions"] = champions
    _save_index(idx)

    print(json.dumps({
        "ok": True,
        "ts": _now().isoformat(),
        "threshold_usd": threshold,
        "captured_this_run": len(captured),
        "total_preserved": len(champions),
        "captured": captured,
        "errors": errors,
    }, indent=2))
    return 0 if not errors else 1


def list_cmd() -> int:
    idx = _load_index()
    champions = idx.get("champions") or []
    if not champions:
        print("no champions preserved.")
        return 0
    print(f"{'TF':<5} {'AGENT':<20} {'BANKROLL':>10} {'ROI%':>7} {'DAYS':>5} {'CAPTURED':<22}")
    print("-" * 80)
    for c in sorted(champions, key=lambda x: x.get("bankroll") or 0, reverse=True)[:40]:
        print(
            f"{c.get('tf',''):<5} "
            f"{str(c.get('trader_id',''))[:20]:<20} "
            f"{c.get('bankroll',0):>10.2f} "
            f"{(c.get('roi_pct') or 0):>7.2f} "
            f"{(c.get('days_traded') or 0):>5} "
            f"{(c.get('captured_at') or '')[:22]:<22}"
        )
    print(f"\ntotal preserved: {len(champions)}")
    return 0


def threshold_cmd(value: str) -> int:
    try:
        v = float(value)
    except Exception:
        print(f"invalid threshold: {value}", file=sys.stderr)
        return 2
    cfg = _load_config()
    cfg["threshold_usd"] = v
    _save_config(cfg)
    print(f"threshold set to ${v:.2f}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[1]
    if cmd == "scan":
        return scan()
    if cmd == "list":
        return list_cmd()
    if cmd == "threshold":
        if len(argv) < 3:
            print("usage: threshold <usd>", file=sys.stderr)
            return 2
        return threshold_cmd(argv[2])
    print(f"unknown cmd: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
