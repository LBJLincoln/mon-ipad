"""Nomos42 prompt mutator — daily loop closing the scientific feedback loop.

Reads:
  - data/research/tf-proposals-*.json (tf_to_proposals output)
  - data/tf-analytics/{nba,pqtf}/day-*.json (behavior stats)
  - data/audit/*.json (integrity alerts)

Writes:
  - data/prompts/overrides.json  {"nba": {prompt_vN, text, applies_since}, ...}

The TF app.py reads overrides.json at startup (if present) and uses the
override prompt instead of the hardcoded template. Each override is tagged
with prompt_vN + timestamp so post-mortems can compare eras.

Rules:
  1. Only ACT on priority-1 pending proposals touching prompt text.
  2. Each mutation is a STRUCTURAL diff (add rule, tighten threshold, forbid
     a pattern) — never a prose rewrite.
  3. Mutations are versioned (prompt_v1, v2, …) — never overwritten.
  4. After writing, mark the source proposal as `status: "applied"` +
     `applied_via: "prompt_mutator@prompt_v<N>"`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
RESEARCH = REPO / "data" / "research"
ANALYTICS = REPO / "data" / "tf-analytics"
PROMPTS_DIR = REPO / "data" / "prompts"
PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
OVERRIDES_PATH = PROMPTS_DIR / "overrides.json"


def _load_overrides() -> Dict[str, Any]:
    if OVERRIDES_PATH.exists():
        try:
            return json.loads(OVERRIDES_PATH.read_text())
        except Exception:
            pass
    return {"nba": {"history": []}, "pol": {"history": []}, "pqtf": {"history": []},
            "itf": {"history": []}}


def _save_overrides(ov: Dict[str, Any]) -> None:
    OVERRIDES_PATH.write_text(json.dumps(ov, indent=2, sort_keys=True))


def _next_version(history: List[Dict[str, Any]]) -> str:
    n = len(history) + 1
    return f"prompt_v{n}"


def _latest_proposals_file() -> Optional[Path]:
    files = sorted(RESEARCH.glob("tf-proposals-*.json"))
    return files[-1] if files else None


def _load_proposals(path: Path) -> List[Dict[str, Any]]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


def _save_proposals(path: Path, proposals: List[Dict[str, Any]]) -> None:
    path.write_text(json.dumps(proposals, indent=2))


# ───────────── Proposal → prompt-rule translators ─────────────

def _rule_lockstep(fleet: str, jaccard: float) -> Optional[str]:
    if jaccard < 0.50:
        return None
    # Structural rule — dropped into prompt as a numbered directive.
    return (
        f"RULE (prompt_mutator — lockstep={jaccard:.2f} on {fleet}): "
        f"You MUST exclude from your bet list at least ONE category that the "
        f"morning-council named as consensus. Pick the second- or third-ranked "
        f"edge instead. Repeating peers verbatim is DEFECT behavior."
    )


def _rule_wr_outlier(wr: float, n: int) -> Optional[str]:
    if wr < 0.80 or n < 10:
        return None
    return (
        f"RULE (prompt_mutator — WR={wr:.2f} n={n}): "
        f"If you find yourself above 80% WR across the last 10 bets, TAKE LESS "
        f"EDGE. Halve your Kelly multiplier for the next 5 bets until WR "
        f"settles below 70%. Above-80% streaks indicate leakage or outcome-peeking."
    )


def _rule_fabricated_fallback(keyword: str) -> Optional[str]:
    return (
        f"RULE (prompt_mutator — forbidden fallback): "
        f"NEVER emit the category string '{keyword}' as a default/placeholder. "
        f"If model edges are empty for a game, PASS that game (no bet) — do not "
        f"fabricate a baseline category."
    )


# ───────────── Main mutation ─────────────

def mutate(dry_run: bool = False) -> Dict[str, Any]:
    pfile = _latest_proposals_file()
    if not pfile:
        return {"status": "no_proposals"}

    proposals = _load_proposals(pfile)
    ov = _load_overrides()
    touched: Dict[str, List[str]] = {"nba": [], "pol": [], "pqtf": [], "itf": []}
    now = dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    for p in proposals:
        if p.get("status") != "pending" or p.get("priority") != 1:
            continue
        title = (p.get("title") or "").lower()
        target = (p.get("target_file") or "").lower()
        finding = p.get("source_finding") or ""
        fleet = None
        # Title wins over target_file (titles may say POL/PQTF while target_file
        # drifted to the NBA app.py copy — seen in tf-proposals-2026-04-19.json).
        if "pqtf" in title:
            fleet = "pqtf"
        elif "political" in title or "pol tf" in title or "pol_tf" in title:
            fleet = "pol"
        elif "intraday" in title or "itf" in title:
            fleet = "itf"
        elif "nba tf" in title or "nba_tf" in title or "nba" in title:
            fleet = "nba"
        elif "hf-political" in target:
            fleet = "pol"
        elif "pqtf-trading-floor" in target:
            fleet = "pqtf"
        elif "hf-intraday" in target:
            fleet = "itf"
        elif "hf-llm-trading-floor" in target:
            fleet = "nba"
        if not fleet:
            continue

        rule: Optional[str] = None

        if "lockstep" in title or "jaccard" in title:
            # Extract jaccard value from finding if possible
            import re
            m = re.search(r"Jaccard=([0-9.]+)", finding) or re.search(r"([0-9.]+)%\s*shared", finding)
            j = float(m.group(1)) if m else 0.88
            if j > 1.5:  # percent form
                j = j / 100.0
            rule = _rule_lockstep(fleet, j)
        elif "wr outlier" in title or "wr_outlier" in title or "100% wr" in title:
            import re
            m = re.search(r"WR=([0-9.]+)%?\s*n=(\d+)", finding)
            wr = float(m.group(1)) / 100.0 if m else 1.0
            n = int(m.group(2)) if m else 20
            rule = _rule_wr_outlier(wr, n)
        elif "fabricated" in title or "ml_home" in finding.lower():
            rule = _rule_fabricated_fallback("ml_home")

        if not rule:
            continue

        ov_fleet = ov.setdefault(fleet, {"history": []})
        hist = ov_fleet.setdefault("history", [])
        version = _next_version(hist)
        hist.append({
            "version": version,
            "ts": now,
            "proposal_id": p.get("id"),
            "rule": rule,
            "rule_hash": hashlib.sha256(rule.encode()).hexdigest()[:12],
        })
        ov_fleet["current_version"] = version
        ov_fleet["current_text"] = rule
        ov_fleet["applies_since"] = now
        touched[fleet].append(version)
        p["status"] = "applied"
        p["applied_via"] = f"prompt_mutator@{version}"
        p["applied_ts"] = now

    if dry_run:
        return {"status": "dry_run", "touched": touched, "overrides": ov}

    if any(touched.values()):
        _save_overrides(ov)
        _save_proposals(pfile, proposals)

    return {"status": "ok", "touched": touched, "pfile": str(pfile)}


def deploy_hf() -> Dict[str, Any]:
    """Upload overrides.json to all 3 TF Spaces so running containers pick it up.
    Uses HF_TOKEN_NBA for LBJLincoln26 account (hosts NBA+POL+PQTF TFs).
    """
    if not OVERRIDES_PATH.exists():
        return {"status": "no-overrides", "path": str(OVERRIDES_PATH)}
    try:
        from huggingface_hub import HfApi  # type: ignore
    except ImportError:
        return {"status": "hfapi-missing"}
    token = os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN_2") or os.environ.get("HF_TOKEN")
    if not token:
        return {"status": "no-token"}
    api = HfApi(token=token)
    targets = [
        ("LBJLincoln26/nba-llm-trading-floor",       "data/prompts/overrides.json"),
        ("LBJLincoln26/political-llm-trading-floor", "data/prompts/overrides.json"),
        ("LBJLincoln26/political-quant-trading-floor", "data/prompts/overrides.json"),
    ]
    out = []
    for repo, dest in targets:
        try:
            api.upload_file(
                path_or_fileobj=str(OVERRIDES_PATH),
                path_in_repo=dest,
                repo_id=repo,
                repo_type="space",
                commit_message="prompt_mutator: auto-deploy overrides",
            )
            out.append({"repo": repo, "ok": True})
        except Exception as e:
            out.append({"repo": repo, "ok": False, "err": str(e)[:200]})
    return {"status": "deployed", "targets": out}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--deploy-hf", action="store_true",
                   help="After mutation, upload overrides.json to all 3 TF Spaces")
    args = p.parse_args()
    result = mutate(dry_run=args.dry_run)
    if args.deploy_hf and not args.dry_run:
        result["deploy_hf"] = deploy_hf()
    print(json.dumps(result, indent=2))
