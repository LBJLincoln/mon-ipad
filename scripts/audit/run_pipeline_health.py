#!/usr/bin/env python3
"""THE PLUMBER runner — data-pipeline health across 6 SLAs.

Every 4h at :35 verify:
  1. Odds ingestion      — data/odds/nba-odds.csv           < 12h stale on game days
  2. Predictions         — predictions-<date>.json exists for today
  3. Engine parity       — features/engine.py sha256 matches HF Space copy
  4. Political data      — nomos-political-alpha/data/ latest file < 24h
  5. TF state            — trading-floor-*-state.json valid + required keys
  6. CSV integrity       — odds + predictions CSVs: no NaN explosion / truncation

Writes data/pipeline-health.json (live snapshot THE BOSS + HERALD read).
Appends data/pipeline-health-history.jsonl.
On critical: data/pipeline-health/ALERT.json.

THE PLUMBER diagnoses only. It never modifies engine.py (DR FRANKENSTEIN),
never restarts Spaces (SWITCHBOARD), never fetches odds (THE TICKER).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
HEALTH_JSON = REPO / "data" / "pipeline-health.json"
HEALTH_HISTORY = REPO / "data" / "pipeline-health-history.jsonl"
ALERT_DIR = REPO / "data" / "pipeline-health"
ALERT_DIR.mkdir(parents=True, exist_ok=True)
HEALTH_JSON.parent.mkdir(parents=True, exist_ok=True)

NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date().isoformat()


def _age_hours(path: Path) -> float | None:
    if not path.exists():
        return None
    mtime = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc)
    return (NOW - mtime).total_seconds() / 3600.0


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _hf_token() -> str | None:
    """Resolve HF token from env.local (same chain as run_audit.py)."""
    if os.environ.get("HF_TOKEN_2"):
        return os.environ["HF_TOKEN_2"]
    env = REPO / ".env.local"
    if not env.exists():
        return os.environ.get("HF_TOKEN")
    vals: dict[str, str] = {}
    for raw in env.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        if v.startswith("$"):
            v = vals.get(v[1:].strip("{}"), v)
        vals[k.strip()] = v
    for k in ("HF_TOKEN_2", "HF_TOKEN_NBA", "HF_TOKEN", "HF_TOKEN_3"):
        if vals.get(k):
            return vals[k]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. Odds ingestion
# ─────────────────────────────────────────────────────────────────────────────
def check_odds() -> dict[str, Any]:
    # Live odds land at data/nba-agent/odds-latest.json (fetch_free_odds.py every 30min).
    # Historical rolling CSV is optional (data/odds/nba-odds.csv if present).
    candidates = [
        REPO / "data" / "nba-agent" / "odds-latest.json",
        REPO / "data" / "nba-agent" / "live-odds.json",
        REPO / "data" / "odds" / "nba-odds.csv",
    ]
    best: tuple[Path, float] | None = None
    for c in candidates:
        age = _age_hours(c)
        if age is not None and (best is None or age < best[1]):
            best = (c, age)
    if best is None:
        return {
            "status": "broken",
            "note": "no odds file in any known location",
            "searched": [str(c.relative_to(REPO)) for c in candidates],
        }
    path, age = best
    sla = 12
    status = "ok" if age < sla else ("stale" if age < sla * 2 else "sla-breach")
    try:
        size = path.stat().st_size
    except OSError:
        size = -1
    return {
        "status": status,
        "age_hours": round(age, 2),
        "sla_hours": sla,
        "size_bytes": size,
        "path": str(path.relative_to(REPO)),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. Predictions (today's file exists)
# ─────────────────────────────────────────────────────────────────────────────
def check_predictions() -> dict[str, Any]:
    """
    Active pipeline writes data/nba-agent/latest-picks.json (autonomous-cycle.sh).
    Legacy pipeline writes predictions-<date>.json (evaluator.py — largely dead).
    Accept either, but prefer latest-picks.json.
    """
    picks = REPO / "data" / "nba-agent" / "latest-picks.json"
    if picks.exists():
        age = _age_hours(picks) or 999.0
        try:
            d = json.loads(picks.read_text())
        except Exception as e:
            return {"status": "broken", "note": f"invalid json: {e}", "path": str(picks.relative_to(REPO))}
        games = d.get("games", []) if isinstance(d, dict) else d
        date = d.get("date") if isinstance(d, dict) else None
        # Fresh if today's date AND <6h old
        today_match = date == TODAY
        fresh = age < 6
        status = "ok" if (today_match and fresh) else ("stale" if age < 48 else "sla-breach")
        return {
            "status": status,
            "games": len(games),
            "date": date,
            "today_match": today_match,
            "age_hours": round(age, 2),
            "path": str(picks.relative_to(REPO)),
        }
    # Legacy fallback
    legacy = [
        REPO / "data" / "results" / f"predictions-{TODAY}.json",
        REPO.parent / "nomos-nba-agent" / "data" / "results" / f"predictions-{TODAY}.json",
    ]
    for c in legacy:
        if c.exists():
            try:
                data = json.loads(c.read_text())
                n = len(data) if isinstance(data, list) else len(data.get("games", []) or [])
            except Exception as e:
                return {"status": "broken", "note": f"invalid json: {e}", "path": str(c)}
            return {"status": "ok", "games": n, "path": str(c), "legacy": True}
    return {
        "status": "missing",
        "note": "no latest-picks.json or legacy predictions-<today>.json",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Engine parity (local ↔ HF Space)
# ─────────────────────────────────────────────────────────────────────────────
def check_engine_parity() -> dict[str, Any]:
    local = REPO / "features" / "engine.py"
    local_sha = _sha256(local)
    if not local_sha:
        return {"status": "broken", "note": "features/engine.py missing"}

    # Try fetching HF Space copy from a canonical island. THE PLUMBER only reads.
    results: dict[str, Any] = {"local_sha": local_sha[:12], "spaces": {}}
    token = _hf_token()
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        results["status"] = "unknown"
        results["note"] = "huggingface_hub not installed on this VM"
        return results

    targets = [
        ("LBJLincoln26/nba-evo-s17", "features/engine.py"),
        ("LBJLincoln26/nba-evo-s20", "features/engine.py"),
    ]
    all_match = True
    any_fetched = False
    for repo_id, rf in targets:
        try:
            p = hf_hub_download(
                repo_id, rf, repo_type="space", token=token,
                cache_dir="/tmp/plumber-engine-cache", force_download=True,
            )
            sha = _sha256(Path(p))
            match = sha == local_sha
            all_match &= match
            any_fetched = True
            results["spaces"][repo_id] = {"sha": sha[:12] if sha else None, "match": match}
        except Exception as e:
            results["spaces"][repo_id] = {"error": str(e)[:120]}

    if not any_fetched:
        results["status"] = "unknown"
        results["note"] = "no HF Space reachable (token or network)"
    else:
        results["status"] = "ok" if all_match else "sha-mismatch"
    return results


# ─────────────────────────────────────────────────────────────────────────────
# 4. Political data freshness
# ─────────────────────────────────────────────────────────────────────────────
def check_political_data() -> dict[str, Any]:
    pol_root = REPO.parent / "nomos-political-alpha" / "data"
    if not pol_root.exists():
        return {"status": "unknown", "note": "sibling repo nomos-political-alpha/data not mounted on this VM"}
    latest: tuple[Path, float] | None = None
    for p in pol_root.rglob("*.json"):
        try:
            mt = p.stat().st_mtime
        except OSError:
            continue
        if latest is None or mt > latest[1]:
            latest = (p, mt)
    if latest is None:
        return {"status": "broken", "note": "no .json in nomos-political-alpha/data/"}
    age = (NOW - dt.datetime.fromtimestamp(latest[1], tz=dt.timezone.utc)).total_seconds() / 3600
    sla = 24
    status = "ok" if age < sla else ("stale" if age < sla * 2 else "sla-breach")
    return {
        "status": status,
        "age_hours": round(age, 2),
        "sla_hours": sla,
        "latest_file": str(latest[0].relative_to(pol_root.parent)),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. TF state validity
# ─────────────────────────────────────────────────────────────────────────────
REQUIRED_TF_KEYS = {"agents", "days_processed", "days_total"}


def check_tf_state() -> dict[str, Any]:
    # Pull live from the 3 TF /api/status endpoints (THE PLUMBER reads, never writes).
    import urllib.request
    floors = {
        "nba-tf": "https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/status",
        "pol-tf": "https://lbjlincoln26-political-llm-trading-floor.hf.space/api/status",
        "pqtf":   "https://lbjlincoln26-political-quant-trading-floor.hf.space/api/status",
    }
    out: dict[str, Any] = {}
    for name, url in floors.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "plumber/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read())
            missing = REQUIRED_TF_KEYS - set(payload.keys())
            status = "ok" if not missing else "broken"
            out[name] = {
                "status": status,
                "missing_keys": list(missing),
                "days_processed": payload.get("days_processed"),
                "days_total": payload.get("days_total"),
                "agents": len(payload.get("agents", {}) or {}),
                "running": payload.get("running"),
            }
        except Exception as e:
            out[name] = {"status": "unreachable", "error": str(e)[:140]}
    # Roll up
    statuses = [v.get("status") for v in out.values()]
    if all(s == "ok" for s in statuses):
        roll = "ok"
    elif any(s == "broken" for s in statuses):
        roll = "broken"
    elif any(s == "unreachable" for s in statuses):
        roll = "unreachable"
    else:
        roll = "degraded"
    return {"status": roll, "floors": out}


# ─────────────────────────────────────────────────────────────────────────────
# 6. CSV integrity
# ─────────────────────────────────────────────────────────────────────────────
def check_csv_integrity() -> dict[str, Any]:
    """Integrity of the odds data — accepts JSON or CSV source."""
    json_path = REPO / "data" / "nba-agent" / "odds-latest.json"
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text())
        except Exception as e:
            return {"status": "broken", "note": f"json parse failed: {e}", "path": str(json_path.relative_to(REPO))}
        games = data if isinstance(data, list) else (data.get("games") or [])
        if not games:
            return {"status": "broken", "note": "zero games in odds-latest.json"}
        # Count NaN-ish prices
        bad = 0
        priced = 0
        for g in games:
            for side_key in ("home_odds", "away_odds", "price_home", "price_away",
                             "ml_home", "ml_away", "decimal_home", "decimal_away"):
                v = g.get(side_key)
                if v is None:
                    continue
                priced += 1
                try:
                    fv = float(v)
                    if fv != fv or fv <= 1.0:  # NaN or invalid decimal odds
                        bad += 1
                except (TypeError, ValueError):
                    bad += 1
        nan_pct = (bad / max(priced, 1)) * 100
        status = "ok" if nan_pct < 10 else ("degraded" if nan_pct < 25 else "broken")
        return {
            "status": status,
            "games": len(games),
            "price_cells": priced,
            "bad_cells": bad,
            "nan_pct": round(nan_pct, 2),
            "path": str(json_path.relative_to(REPO)),
        }

    csv_path = REPO / "data" / "odds" / "nba-odds.csv"
    if not csv_path.exists():
        return {"status": "unknown", "note": "no odds-latest.json or odds csv"}
    try:
        lines = csv_path.read_text(errors="replace").splitlines()
    except Exception as e:
        return {"status": "broken", "note": f"read failed: {e}"}
    if len(lines) < 2:
        return {"status": "broken", "note": "csv has no data rows"}
    header = lines[0].split(",")
    ncols = len(header)
    truncated = nan_count = scanned = 0
    for row in lines[1:]:
        if not row.strip():
            continue
        scanned += 1
        cells = row.split(",")
        if len(cells) != ncols:
            truncated += 1
        for c in cells:
            if c.strip().lower() in ("nan", "none", "null", ""):
                nan_count += 1
    nan_pct = (nan_count / max(scanned * ncols, 1)) * 100
    trunc_pct = (truncated / max(scanned, 1)) * 100
    status = "ok"
    if trunc_pct > 1.0 or nan_pct > 10.0:
        status = "broken"
    elif nan_pct > 5.0:
        status = "degraded"
    return {
        "status": status, "rows": scanned, "cols": ncols,
        "nan_pct": round(nan_pct, 3), "truncated_rows": truncated,
        "trunc_pct": round(trunc_pct, 3),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    checks = {
        "odds_ingestion": check_odds(),
        "predictions": check_predictions(),
        "engine_parity": check_engine_parity(),
        "political_data": check_political_data(),
        "tf_state": check_tf_state(),
        "csv_integrity": check_csv_integrity(),
    }

    # Roll-up status.
    critical = [k for k, v in checks.items() if v.get("status") == "broken"]
    stale = [k for k, v in checks.items() if v.get("status") in ("stale", "sla-breach", "sha-mismatch", "degraded")]
    unknown = [k for k, v in checks.items() if v.get("status") in ("unknown", "unreachable", "missing")]

    if critical:
        roll = "CRITICAL"
    elif stale:
        roll = "DEGRADED"
    elif unknown:
        roll = "UNKNOWN"
    else:
        roll = "HEALTHY"

    healthy = sum(1 for v in checks.values() if v.get("status") == "ok")
    total = len(checks)

    snapshot = {
        "agent": "THE PLUMBER",
        "timestamp": NOW.isoformat(),
        "rollup": roll,
        "summary": f"{healthy}/{total} healthy. broken={critical} stale={stale} unknown={unknown}",
        "checks": checks,
    }

    HEALTH_JSON.write_text(json.dumps(snapshot, indent=2))
    with HEALTH_HISTORY.open("a") as fh:
        fh.write(json.dumps({"ts": NOW.isoformat(), "rollup": roll, "healthy": healthy, "total": total}) + "\n")

    if roll == "CRITICAL":
        alert = ALERT_DIR / f"{NOW.strftime('%Y-%m-%dT%H%MZ')}.json"
        alert.write_text(json.dumps(snapshot, indent=2))

    print(f"[PLUMBER] {roll} — {healthy}/{total} healthy")
    if critical:
        print(f"  BROKEN: {critical}")
    if stale:
        print(f"  STALE:  {stale}")
    if unknown:
        print(f"  UNKNOWN: {unknown}")
    return 0 if roll in ("HEALTHY", "UNKNOWN") else (2 if roll == "CRITICAL" else 1)


if __name__ == "__main__":
    sys.exit(main())
