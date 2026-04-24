#!/usr/bin/env python3
"""Unified TF control surface — one tool to verify / restart / stop any TF.

The 3 live TFs (NBA / POL / ITF) + frozen PQTF drifted into different API
shapes over months of per-TF hotfixes. This tool normalizes them:
  status  -> {running, tick_age_sec, fleet_value_usd, n_agents, issues}
  run     -> fire /api/run correctly per TF (NBA+POL need it, ITF auto-starts)
  stop    -> /api/stop
  restart -> HfApi soft restart + auto-resume
  reboot  -> HfApi factory_reboot + auto-resume (destructive wipe)
  health  -> PASS/FAIL on every TF using tf_baseline_check internals

Usage:
  scripts/ops/tf_unified_control.py status [nba|pol|itf|all]
  scripts/ops/tf_unified_control.py run <nba|pol|itf>
  scripts/ops/tf_unified_control.py restart <nba|pol|itf>
  scripts/ops/tf_unified_control.py reboot <nba|pol|itf>   # factory -- wipes state
  scripts/ops/tf_unified_control.py health all

PQTF is mechanically blocked from all write-actions in this tool.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

TFS = {
    "nba": {
        "repo":      "LBJLincoln26/nba-llm-trading-floor",
        "url":       "https://lbjlincoln26-nba-llm-trading-floor.hf.space",
        "run_is_post": True,
        "run_body":   None,
        "status_fleet_source": "leaderboard_sum",  # sum of trader bankrolls
    },
    "pol": {
        "repo":      "LBJLincoln26/political-llm-trading-floor",
        "url":       "https://lbjlincoln26-political-llm-trading-floor.hf.space",
        "run_is_post": True,
        "run_body":   None,
        "status_fleet_source": "leaderboard_sum",
    },
    "itf": {
        "repo":      "LBJLincoln26/intraday-trading-floor",
        "url":       "https://lbjlincoln26-intraday-trading-floor.hf.space",
        "run_is_post": True,
        "run_body":   {"request": "tick"},
        "status_fleet_source": "bankrolls_fleet_equity",
    },
    "pqtf": {
        "repo":      "LBJLincoln26/political-quant-trading-floor",
        "url":       "https://lbjlincoln26-political-quant-trading-floor.hf.space",
        "run_is_post": True,
        "run_body":   None,
        "status_fleet_source": "frozen",
        "frozen": True,
    },
}


def _http(method: str, url: str, body: dict | None = None, timeout: int = 12) -> tuple[int | str, object | None, str]:
    try:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            try:
                return r.status, json.loads(raw), ""
            except Exception:
                return r.status, raw.decode("utf-8", errors="replace"), ""
    except urllib.error.HTTPError as e:
        try: return e.code, e.read().decode("utf-8", errors="replace"), f"HTTP {e.code}"
        except Exception: return e.code, None, f"HTTP {e.code}"
    except Exception as e:
        return "ERR", None, f"{type(e).__name__}: {e}"


def _fleet_value(tf: str) -> float | None:
    cfg = TFS[tf]
    source = cfg["status_fleet_source"]
    if source == "frozen":
        return 602353.97
    if source == "leaderboard_sum":
        st, d, _ = _http("GET", f"{cfg['url']}/api/leaderboard")
        if st == 200 and isinstance(d, dict):
            return sum(float(r.get("bankroll") or 0) for r in (d.get("leaderboard") or []))
    if source == "bankrolls_fleet_equity":
        st, d, _ = _http("GET", f"{cfg['url']}/api/bankrolls")
        if st == 200 and isinstance(d, dict):
            return float(d.get("fleet_equity") or 0)
    return None


def status_one(tf: str) -> dict:
    cfg = TFS[tf]
    out = {"tf": tf, "repo": cfg["repo"], "frozen": cfg.get("frozen", False)}
    st, d, err = _http("GET", f"{cfg['url']}/api/status")
    if st != 200 or not isinstance(d, dict):
        out["running"] = False
        out["issue"] = err or f"status {st}"
        return out
    out["running"] = bool(d.get("running"))
    last = d.get("last_tick_at") or d.get("last_update")
    if last:
        try:
            age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(str(last).replace("Z", "+00:00"))).total_seconds()
            out["tick_age_sec"] = int(age)
        except Exception: out["tick_age_sec"] = None
    agents = d.get("agents") or {}
    out["n_agents"] = len(agents) if isinstance(agents, dict) else len(agents)
    out["fleet_value_usd"] = round(_fleet_value(tf) or 0, 2)
    issues = []
    if not out["running"] and not cfg.get("frozen"): issues.append("not_running")
    if out.get("tick_age_sec") and out["tick_age_sec"] > 900: issues.append(f"stale_tick_{out['tick_age_sec']}s")
    if out["n_agents"] not in (17, 6): issues.append(f"agent_count={out['n_agents']}")
    out["issues"] = issues
    out["ok"] = len(issues) == 0 or cfg.get("frozen", False)
    return out


def run_one(tf: str) -> dict:
    cfg = TFS[tf]
    if cfg.get("frozen"):
        return {"tf": tf, "action": "run", "blocked": "frozen"}
    st, d, err = _http("POST", f"{cfg['url']}/api/run", body=cfg.get("run_body"))
    return {"tf": tf, "action": "run", "http": st, "body": d, "err": err}


def stop_one(tf: str) -> dict:
    cfg = TFS[tf]
    if cfg.get("frozen"):
        return {"tf": tf, "action": "stop", "blocked": "frozen"}
    st, d, err = _http("POST", f"{cfg['url']}/api/stop", body={})
    return {"tf": tf, "action": "stop", "http": st, "body": d, "err": err}


def _hf_api():
    try:
        from huggingface_hub import HfApi
    except ImportError:
        return None
    tok = os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN") or ""
    return HfApi(token=tok) if tok else None


def restart_one(tf: str, factory: bool = False) -> dict:
    cfg = TFS[tf]
    if cfg.get("frozen"):
        return {"tf": tf, "action": "restart", "blocked": "frozen"}
    api = _hf_api()
    if api is None:
        return {"tf": tf, "action": "restart", "err": "no HF token"}
    try:
        api.restart_space(cfg["repo"], factory_reboot=factory)
    except Exception as e:
        return {"tf": tf, "action": "restart", "err": str(e)}
    # Wait for boot
    for _ in range(60):
        st, _, _ = _http("GET", f"{cfg['url']}/api/status", timeout=5)
        if st == 200: break
        time.sleep(5)
    # Auto-run (all 3 need it after restart)
    run_res = run_one(tf)
    return {"tf": tf, "action": "reboot" if factory else "restart", "restart": "ok", "run": run_res}


def print_status_table(rows: list[dict]) -> None:
    print(f"{'TF':<6} {'ok':<4} {'running':<8} {'agents':<7} {'tick_age':<10} {'fleet $':>12}  issues")
    print("-" * 80)
    for r in rows:
        print(f"{r['tf']:<6} "
              f"{'yes' if r.get('ok') else 'no':<4} "
              f"{str(r.get('running','?')):<8} "
              f"{str(r.get('n_agents','?')):<7} "
              f"{str(r.get('tick_age_sec','?'))+'s':<10} "
              f"${r.get('fleet_value_usd',0):>11,.0f}  "
              f"{','.join(r.get('issues') or [])}")


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__); return 0
    cmd = argv[1]; arg = argv[2] if len(argv) >= 3 else "all"
    targets = list(TFS.keys()) if arg == "all" else [arg]
    if arg != "all" and arg not in TFS:
        print(f"unknown TF: {arg}. valid: {list(TFS.keys())}", file=sys.stderr)
        return 2

    if cmd == "status":
        rows = [status_one(t) for t in targets]
        print_status_table(rows)
        payload = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(), "targets": rows}
        (REPO / "data" / "ops" / "tf-unified-latest.json").write_text(json.dumps(payload, indent=2))
        return 0 if all(r.get("ok") for r in rows) else 1
    if cmd == "run":
        r = run_one(targets[0])
        print(json.dumps(r, indent=2)); return 0
    if cmd == "stop":
        r = stop_one(targets[0])
        print(json.dumps(r, indent=2)); return 0
    if cmd == "restart":
        r = restart_one(targets[0], factory=False)
        print(json.dumps(r, indent=2)); return 0
    if cmd == "reboot":
        r = restart_one(targets[0], factory=True)
        print(json.dumps(r, indent=2)); return 0
    if cmd == "health":
        # Delegate to baseline_check
        import subprocess
        rc = subprocess.call([sys.executable, str(REPO / "scripts" / "ops" / "tf_baseline_check.py")])
        return rc
    print(f"unknown cmd: {cmd}", file=sys.stderr); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
