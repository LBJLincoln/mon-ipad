#!/usr/bin/env python3
"""TF Improvement Cycle — every 4h, read the last 5 days of bets per TF,
detect losers/winners, and auto-tune each agent's Kelly cap up or down.

Scope:
- NBA:  reads data/tf-analytics/nba/day-*.json  (per_bet drill-down)
- POL:  reads data/tf-analytics/pol/day-*.json
- Both Spaces have _AGENT_KELLY_OVERRIDE dicts in app.py that we surgically
  patch via HfApi.upload_file when a change fires.

Rules (simple, conservative, audit-friendly):
- Windowed W/L = wins / (wins + losses) over the last WINDOW_DAYS day files.
- Need MIN_BETS total bets in the window for a decision (else HOLD).
- If W/L < LOSER_WR and agent PnL in window is negative -> Kelly -= KELLY_STEP.
- If W/L > WINNER_WR and agent PnL > +WINNER_PNL_PCT * seed -> Kelly += KELLY_STEP.
- Cap: [KELLY_MIN, KELLY_MAX].
- Rate limit: at most one adjustment per agent per 24h (checked vs history).

Kill switch: env TF_IMPROVE_APPLY=0 puts the script in proposal-only mode
(writes proposals to data/ops/tf-improvement-proposals.json + history jsonl,
no Space writes, no restarts). Default is APPLY (user directive 2026-04-24
"improve really all").

Audit trail: every change appends to data/ops/tf-improvement-history.jsonl
with before/after + full reasoning, so reverts are one-shot from the log.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
TFA = REPO / "data" / "tf-analytics"
OUT_DIR = REPO / "data" / "ops"
PROPOSALS = OUT_DIR / "tf-improvement-proposals.json"
HISTORY = OUT_DIR / "tf-improvement-history.jsonl"

WINDOW_DAYS = 10       # how many recent day-files to consider (matches scorecard)
MIN_BETS = 15          # minimum bets in window to make a call
LOSER_WR = 0.45        # W/L below this + negative PnL => reduce Kelly
WINNER_WR = 0.55       # W/L above this + positive PnL => bump Kelly
WINNER_PNL_PCT = 0.10  # PnL gain as fraction of implied-seed before bumping
KELLY_STEP = 0.03      # how much each adjustment moves Kelly
KELLY_MIN = 0.02
KELLY_MAX = 0.30
AGENT_COOLDOWN_H = 24

SPACES = {
    "nba": "LBJLincoln26/nba-llm-trading-floor",
    "pol": "LBJLincoln26/political-llm-trading-floor",
}


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _load_history() -> list[dict]:
    if not HISTORY.exists():
        return []
    out = []
    for line in HISTORY.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _append_history(entry: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    entry["ts"] = _now().isoformat()
    with HISTORY.open("a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def _recent_day_files_from_hub(tf: str) -> list[dict]:
    """Pull the last WINDOW_DAYS day-decision files directly from the Space Hub.
    Bypasses the local tf-analytics cache which only snapshots the latest day."""
    import urllib.parse, urllib.request
    repo = SPACES[tf]
    tok = os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN") or ""
    headers = {"Authorization": f"Bearer {tok}"} if tok else {}
    try:
        tree_url = f"https://huggingface.co/api/spaces/{repo}/tree/main?recursive=true"
        req = urllib.request.Request(tree_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            tree = json.loads(r.read())
    except Exception:
        return []
    day_paths = sorted(
        str(f.get("path"))
        for f in tree
        if isinstance(f, dict)
        and str(f.get("path", "")).startswith("data/decisions/day-")
        and str(f.get("path", "")).endswith(".json")
    )[-WINDOW_DAYS:]
    out = []
    for rf in day_paths:
        url = f"https://huggingface.co/spaces/{repo}/resolve/main/{urllib.parse.quote(rf)}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as r:
                out.append(json.loads(r.read()))
        except Exception:
            continue
    return out


def _compute_agent_metrics(tf: str) -> dict[str, dict[str, Any]]:
    """Returns {tid: {wins, losses, n_bets, pnl, brier, n_conf}} aggregated over window from Hub."""
    out: dict[str, dict[str, Any]] = {}
    for day in _recent_day_files_from_hub(tf):
        agents = day.get("agents") or {}
        for tid, a in agents.items():
            for bet in (a.get("allocations") or a.get("bets") or []):
                slot = out.setdefault(tid, {
                    "wins": 0, "losses": 0, "n_bets": 0, "pnl": 0.0,
                    "brier_sum": 0.0, "n_conf": 0,
                })
                slot["n_bets"] += 1
                won = bet.get("won")
                if won is None:
                    res = str(bet.get("result", "")).lower()
                    won = res in ("win", "won", "w")
                if won:
                    slot["wins"] += 1
                else:
                    slot["losses"] += 1
                try:
                    slot["pnl"] += float(bet.get("profit") or bet.get("pnl") or 0.0)
                except Exception:
                    pass
                # Accumulate Brier from confidence when present
                conf = bet.get("confidence")
                if conf is not None and won is not None:
                    try:
                        cv = float(conf)
                        if 0.0 <= cv <= 1.0:
                            slot["brier_sum"] += (cv - (1.0 if won else 0.0)) ** 2
                            slot["n_conf"] += 1
                    except Exception:
                        pass
    # Finalize: attach brier avg
    for tid, slot in out.items():
        slot["brier"] = (slot["brier_sum"] / slot["n_conf"]) if slot["n_conf"] > 0 else None
    return out


def _decide(tid: str, m: dict[str, Any]) -> tuple[str, str]:
    """Return (decision, reason). decision ∈ {HOLD, REDUCE, BUMP}.
    Triggers are ANY-OF: WR, PnL direction, OR Brier calibration.
    Brier adds a pure-calibration lane: an agent with bad WR but also bad
    calibration (Brier > 0.30) is REDUCEd even if PnL is marginally positive.
    An agent with Brier < 0.23 (clearly better than random) can earn a BUMP."""
    if m["n_bets"] < MIN_BETS:
        return "HOLD", f"only {m['n_bets']} bets in {WINDOW_DAYS}-day window (need >={MIN_BETS})"
    wr = m["wins"] / max(1, m["wins"] + m["losses"])
    brier = m.get("brier")
    # REDUCE trigger: WR+PnL loss OR inverse-calibrated (Brier > 0.32)
    if wr < LOSER_WR and m["pnl"] < 0:
        return "REDUCE", f"WR={wr:.2f} (<{LOSER_WR}) + PnL=${m['pnl']:+.1f}"
    if brier is not None and brier > 0.32 and m["n_conf"] >= MIN_BETS:
        return "REDUCE", f"Brier={brier:.3f} > 0.32 ({m['n_conf']} confident bets) -- inverse-calibrated"
    # BUMP trigger: WR+PnL win OR clean calibration (Brier < 0.23)
    if wr > WINNER_WR and m["pnl"] > WINNER_PNL_PCT * 100:
        return "BUMP", f"WR={wr:.2f} (>{WINNER_WR}) + PnL=${m['pnl']:+.1f}"
    if brier is not None and brier < 0.23 and m["n_conf"] >= MIN_BETS and m["pnl"] > 0:
        return "BUMP", f"Brier={brier:.3f} < 0.23 + PnL=${m['pnl']:+.1f} -- well-calibrated winner"
    return "HOLD", f"WR={wr:.2f} PnL=${m['pnl']:+.1f} Brier={brier} inside band"


def _on_cooldown(tf: str, tid: str, history: list[dict]) -> bool:
    cutoff = _now() - dt.timedelta(hours=AGENT_COOLDOWN_H)
    for entry in reversed(history):
        if entry.get("tf") != tf or entry.get("tid") != tid:
            continue
        try:
            t = dt.datetime.fromisoformat(entry["ts"])
        except Exception:
            continue
        if t > cutoff and entry.get("applied"):
            return True
    return False


def _read_space_app(tf: str) -> str:
    path = {
        "nba": REPO / "scripts" / "arena" / "hf-llm-trading-floor" / "app.py",
        "pol": REPO / "scripts" / "arena" / "hf-political-trading-floor" / "app.py",
    }[tf]
    return path.read_text()


def _write_space_app(tf: str, src: str) -> Path:
    path = {
        "nba": REPO / "scripts" / "arena" / "hf-llm-trading-floor" / "app.py",
        "pol": REPO / "scripts" / "arena" / "hf-political-trading-floor" / "app.py",
    }[tf]
    path.write_text(src)
    return path


def _current_kelly(tf: str, tid: str, src: str) -> float | None:
    """Regex-extract the current Kelly for a tid from _AGENT_KELLY_OVERRIDE block."""
    block_m = re.search(r"_AGENT_KELLY_OVERRIDE[^{]*\{(.*?)^}", src, re.DOTALL | re.MULTILINE)
    if not block_m:
        return None
    block = block_m.group(1)
    m = re.search(rf'"{re.escape(tid)}"\s*:\s*([0-9.]+)', block)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def _patch_kelly(tf: str, tid: str, new_val: float, src: str) -> str | None:
    """Return new source with tid's Kelly set to new_val. None if not present."""
    pattern = re.compile(rf'("{re.escape(tid)}"\s*:\s*)([0-9.]+)(\s*,)')
    if not pattern.search(src):
        return None
    new_src = pattern.sub(rf"\g<1>{new_val:.3f}\g<3>", src, count=1)
    return new_src


def run(apply: bool) -> int:
    history = _load_history()
    proposals_out: list[dict] = []

    try:
        from huggingface_hub import HfApi  # type: ignore
    except ImportError:
        HfApi = None

    tok = os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN") or ""
    api = HfApi(token=tok) if (HfApi and tok and apply) else None

    for tf, repo in SPACES.items():
        metrics = _compute_agent_metrics(tf)
        src = _read_space_app(tf)
        dirty = False
        for tid, m in metrics.items():
            decision, reason = _decide(tid, m)
            cur = _current_kelly(tf, tid, src)
            proposal = {
                "tf": tf,
                "tid": tid,
                "metrics": m,
                "decision": decision,
                "reason": reason,
                "current_kelly": cur,
                "proposed_kelly": cur,
                "applied": False,
            }
            if decision in ("REDUCE", "BUMP") and cur is not None:
                direction = -1 if decision == "REDUCE" else 1
                target = max(KELLY_MIN, min(KELLY_MAX, round(cur + direction * KELLY_STEP, 3)))
                proposal["proposed_kelly"] = target
                if apply and _on_cooldown(tf, tid, history):
                    proposal["skipped"] = "cooldown"
                elif apply and abs(target - cur) > 1e-6:
                    patched = _patch_kelly(tf, tid, target, src)
                    if patched:
                        src = patched
                        proposal["applied"] = True
                        dirty = True
            proposals_out.append(proposal)
            _append_history(proposal)

        if apply and dirty and api is not None:
            _write_space_app(tf, src)
            try:
                api.upload_file(
                    path_or_fileobj={
                        "nba": str(REPO / "scripts/arena/hf-llm-trading-floor/app.py"),
                        "pol": str(REPO / "scripts/arena/hf-political-trading-floor/app.py"),
                    }[tf],
                    path_in_repo="app.py",
                    repo_id=repo,
                    repo_type="space",
                    commit_message=f"tf_improvement_cycle: Kelly auto-tune {tf} (window={WINDOW_DAYS}d)",
                )
                api.restart_space(repo, factory_reboot=False)
                print(f"[{tf}] uploaded + soft-restarted after Kelly tune", flush=True)
            except Exception as e:
                print(f"[{tf}] HF upload/restart FAILED: {e}", file=sys.stderr, flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROPOSALS.write_text(json.dumps({
        "ts": _now().isoformat(),
        "apply_mode": apply,
        "proposals": proposals_out,
    }, indent=2, default=str))

    applied = sum(1 for p in proposals_out if p.get("applied"))
    print(f"ts={_now().isoformat()} tfs={list(SPACES)} proposals={len(proposals_out)} applied={applied} mode={'APPLY' if apply else 'PROPOSAL_ONLY'}")
    return 0


def main() -> int:
    apply = os.environ.get("TF_IMPROVE_APPLY", "1") == "1"
    try:
        return run(apply=apply)
    except Exception as e:
        print(f"FATAL: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
