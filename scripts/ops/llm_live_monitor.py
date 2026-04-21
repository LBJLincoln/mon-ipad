#!/usr/bin/env python3
"""Live LLM health monitor — probes gateway + each underlying Space every 3 min.

Writes one JSON line per cycle to data/ops/llm-health.jsonl, plus a running
snapshot at data/ops/llm-health.json. Exits non-zero if the gateway cannot
reach even one model — cron captures that in stderr.

Intended cadence: `*/3 * * * *` via crontab. Keep probes tight: each cycle is
one /api/health call + one /api/stats call + per-selfhost-Space HEAD / model
list. The full sweep must finish in <60s so cycles don't overlap.

Dead-alias detection logic:
    status == "down"     for >= 3 consecutive cycles  -> flagged DEAD
    median_latency_ms    > 30000 over last 5 cycles   -> flagged SLOW
    calls_fail / total   > 0.5                          -> flagged BROKEN

DEAD aliases get appended to data/ops/llm-deadlist.json which callers
(TF personas) can consult to avoid routing. No live gateway mutation from here.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "ops"
DATA_DIR.mkdir(parents=True, exist_ok=True)

JSONL_PATH = DATA_DIR / "llm-health.jsonl"
SNAPSHOT_PATH = DATA_DIR / "llm-health.json"
DEADLIST_PATH = DATA_DIR / "llm-deadlist.json"
HISTORY_PATH = DATA_DIR / "llm-health-history.json"

GATEWAY = "https://lbjlincoln26-llm-gateway.hf.space"
HEALTH_URL = f"{GATEWAY}/api/health"
STATS_URL = f"{GATEWAY}/api/stats"
MODELS_URL = f"{GATEWAY}/api/models"

SELFHOST_SPACES = [
    "https://lbjlincoln-phi35-mini-cpu.hf.space",
    "https://testforge42-qwen3-4b-cpu.hf.space",
    "https://lbjlincoln26-gemma3-4b-cpu.hf.space",
    "https://testforge42-llama32-1b-cpu.hf.space",
    "https://lbjlincoln-qwen25-05b-cpu.hf.space",
]

PROBE_TIMEOUT = 20.0


def _http_json(url: str, timeout: float = PROBE_TIMEOUT) -> dict[str, Any]:
    """HTTP GET → JSON. ok=True if server replied with parseable JSON (any status).
    A 503 with a JSON body still counts as reachable."""
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
            latency_ms = (time.monotonic() - t0) * 1000.0
            try:
                return {"ok": True, "code": r.status, "body": json.loads(body), "latency_ms": latency_ms}
            except json.JSONDecodeError:
                return {"ok": False, "code": r.status, "error": "not-json", "latency_ms": latency_ms}
    except urllib.error.HTTPError as e:
        latency_ms = (time.monotonic() - t0) * 1000.0
        try:
            parsed = json.loads(e.read().decode("utf-8", errors="replace"))
            return {"ok": True, "code": e.code, "body": parsed, "latency_ms": latency_ms}
        except Exception:
            return {"ok": False, "code": e.code, "error": f"HTTP {e.code}", "latency_ms": latency_ms}
    except Exception as e:
        return {"ok": False, "code": 0, "error": str(e)[:120], "latency_ms": (time.monotonic() - t0) * 1000.0}


def _http_head(url: str, timeout: float = PROBE_TIMEOUT) -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": True, "code": r.status, "latency_ms": (time.monotonic() - t0) * 1000.0}
    except urllib.error.HTTPError as e:
        return {"ok": True, "code": e.code, "latency_ms": (time.monotonic() - t0) * 1000.0}
    except Exception as e:
        return {"ok": False, "code": 0, "error": str(e)[:80], "latency_ms": (time.monotonic() - t0) * 1000.0}


def _load_history() -> dict[str, Any]:
    if HISTORY_PATH.exists():
        try:
            return json.loads(HISTORY_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_history(hist: dict[str, Any]) -> None:
    tmp = HISTORY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(hist, indent=2))
    tmp.replace(HISTORY_PATH)


def _update_rolling(hist: dict[str, Any], key: str, status: str, latency_ms: float) -> dict[str, Any]:
    rec = hist.setdefault(key, {"status_history": [], "latency_history": [], "consecutive_down": 0})
    rec["status_history"].append(status)
    rec["status_history"] = rec["status_history"][-20:]
    rec["latency_history"].append(latency_ms)
    rec["latency_history"] = rec["latency_history"][-20:]
    if status == "down":
        rec["consecutive_down"] = rec.get("consecutive_down", 0) + 1
    else:
        rec["consecutive_down"] = 0
    return rec


def run_cycle() -> dict[str, Any]:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    gateway = _http_json(HEALTH_URL)
    stats = _http_json(STATS_URL) if gateway["ok"] else {"ok": False, "body": {}}
    models_resp = _http_json(MODELS_URL) if gateway["ok"] else {"ok": False, "body": {}}

    hist = _load_history()
    selfhost_results: dict[str, Any] = {}
    for url in SELFHOST_SPACES:
        root_probe = _http_head(url)
        v1_probe = _http_json(f"{url}/v1/models", timeout=5.0)
        alive = bool(root_probe["ok"] and v1_probe["ok"])
        selfhost_results[url] = {
            "root_code": root_probe["code"],
            "v1_models_code": v1_probe["code"],
            "alive": alive,
            "latency_ms": v1_probe.get("latency_ms", 0.0),
        }

    model_snap = {}
    if stats["ok"]:
        for mid, h in (stats["body"].get("models") or {}).items():
            status = h.get("status", "unknown")
            latency = float(h.get("avg_latency_ms") or 0)
            _update_rolling(hist, mid, status, latency)
            rec = hist[mid]
            consecutive_down = rec.get("consecutive_down", 0)
            recent_lat = rec.get("latency_history", [])
            median_lat = sorted(recent_lat)[len(recent_lat) // 2] if recent_lat else 0.0
            calls_ok = int(h.get("calls_ok") or 0)
            calls_fail = int(h.get("calls_fail") or 0)
            total = calls_ok + calls_fail
            fail_ratio = (calls_fail / total) if total else 0.0
            flag = None
            if consecutive_down >= 3:
                flag = "DEAD"
            elif median_lat > 30000:
                flag = "SLOW"
            elif total >= 5 and fail_ratio > 0.5:
                flag = "BROKEN"
            model_snap[mid] = {
                "status": status,
                "latency_ms": latency,
                "calls_ok": calls_ok,
                "calls_fail": calls_fail,
                "consecutive_down": consecutive_down,
                "median_latency_ms_20w": median_lat,
                "fail_ratio": round(fail_ratio, 3),
                "flag": flag,
            }

    _save_history(hist)

    dead_aliases = [mid for mid, s in model_snap.items() if s["flag"] == "DEAD"]
    slow_aliases = [mid for mid, s in model_snap.items() if s["flag"] == "SLOW"]
    broken_aliases = [mid for mid, s in model_snap.items() if s["flag"] == "BROKEN"]

    snapshot = {
        "ts": ts,
        "gateway_ok": gateway["ok"],
        "gateway_code": gateway["code"],
        "gateway_body": gateway.get("body", {}),
        "gateway_latency_ms": gateway.get("latency_ms", 0.0),
        "models_registered": len((models_resp.get("body") or {}).get("models", [])),
        "selfhost_spaces_alive": sum(1 for r in selfhost_results.values() if r["alive"]),
        "selfhost_spaces_total": len(selfhost_results),
        "selfhost_detail": selfhost_results,
        "model_snap": model_snap,
        "dead_aliases": dead_aliases,
        "slow_aliases": slow_aliases,
        "broken_aliases": broken_aliases,
    }

    SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2))
    with JSONL_PATH.open("a") as fh:
        fh.write(json.dumps({
            "ts": ts,
            "gw": gateway["ok"],
            "selfhost_alive": snapshot["selfhost_spaces_alive"],
            "dead": dead_aliases,
            "slow": slow_aliases,
            "broken": broken_aliases,
        }) + "\n")

    if dead_aliases or broken_aliases:
        DEADLIST_PATH.write_text(json.dumps({
            "ts": ts,
            "dead": dead_aliases,
            "broken": broken_aliases,
            "slow": slow_aliases,
            "action": "TF personas should NOT route to these aliases until they clear 3+ cycles of ok.",
        }, indent=2))
    else:
        DEADLIST_PATH.write_text(json.dumps({"ts": ts, "dead": [], "broken": [], "slow": [], "action": "all clear"}, indent=2))

    return snapshot


if __name__ == "__main__":
    snap = run_cycle()
    print(json.dumps({
        "ts": snap["ts"],
        "gw_ok": snap["gateway_ok"],
        "selfhost": f"{snap['selfhost_spaces_alive']}/{snap['selfhost_spaces_total']}",
        "dead": snap["dead_aliases"],
        "slow": snap["slow_aliases"],
        "broken": snap["broken_aliases"],
    }))
    if not snap["gateway_ok"]:
        sys.exit(2)
