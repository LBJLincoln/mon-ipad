#!/usr/bin/env python3
"""Cross-TF LLM comparison — normalize all 3 TFs (NBA + POL + ITF) into
a single schema so we can compare the SAME underlying LLM model across
markets.

NBA/POL use LLM-named trader_ids directly (qwen-quant, gemini-anl, ...).
ITF uses strategy-named trader_ids (scalper-1, momentum-1, ...) with an
underlying model_primary field. This script pulls the mapping from
personas.py so ITF performance attributes back to the LLM model.

Output:
- data/audit/cross-llm-latest.json  (machine-readable)
- data/audit/cross-llm-latest.md    (table the user can read)

Answers: "which LLM wins across ALL markets?" — not just one TF.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "data" / "audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# --- TF-to-LLM-name maps -------------------------------------------------
# NBA/POL: trader_id IS the LLM shorthand. Canonical spellings:
NBA_POL_LLM_MAP = {
    "qwen-quant": "cerebras:qwen-3-235b",
    "qwen-arb": "cerebras:qwen-3-235b",
    "llama-contra": "cerebras:llama3.1-8b",
    "gemini-anl": "google:gemini-3-flash",
    "gemini-tact": "google:gemini-3-flash",
    "mistral-large": "mistral:large",
    "mistral-medium": "mistral:medium",
    "mistral-small": "mistral:small",
    "mistral-nemo": "mistral:nemo",
    "mistral-ministral": "mistral:ministral-8b",
    "nemotron-120b": "openrouter:nemotron-120b",
    "selfhost-qwen4b": "selfhost:qwen3-4b",
    "nvidia-minimax": "nvidia:minimax-m2.7",
    "nvidia-llama70": "nvidia:llama-3.3-70b",
    "selfhost-gemma3": "selfhost:gemma-3-4b",
    "selfhost-qwen06": "selfhost:qwen3-0.6b",
    "selfhost-dolphin3": "selfhost:dolphin3-l32-3b",
}


def _load_itf_llm_map() -> dict[str, str]:
    """Parse scripts/arena/hf-intraday-trading-floor/personas.py for tid->model_primary."""
    p = REPO / "scripts" / "arena" / "hf-intraday-trading-floor" / "personas.py"
    if not p.exists():
        return {}
    src = p.read_text()
    out: dict[str, str] = {}
    # Find blocks: "tid": "X", ... "model_primary": "Y"
    for match in re.finditer(
        r'"tid"\s*:\s*"([^"]+)".*?"model_primary"\s*:\s*"([^"]+)"',
        src, re.DOTALL
    ):
        out[match.group(1)] = match.group(2)
    return out


def _http_get(url: str, headers: dict | None = None, timeout: int = 12) -> dict | None:
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


def _nba_pol_snapshot(tf: str, url: str) -> list[dict]:
    d = _http_get(url)
    if not isinstance(d, dict):
        return []
    rows = []
    for r in (d.get("leaderboard") or []):
        tid = r.get("trader_id")
        if not tid:
            continue
        llm = NBA_POL_LLM_MAP.get(tid, "unknown")
        try:
            bk = float(r.get("bankroll") or 0)
            wins = int(r.get("wins") or 0)
            losses = int(r.get("losses") or 0)
            bets = int(r.get("total_bets") or (wins + losses))
        except Exception:
            continue
        rows.append({
            "tf": tf, "tid": tid, "llm": llm,
            "bankroll": bk, "bets": bets, "wins": wins, "losses": losses,
            "wr": wins / max(1, wins + losses),
            "roi_pct": (bk - 100.0),  # seed is $100 per agent
        })
    return rows


def _itf_snapshot(itf_map: dict[str, str]) -> list[dict]:
    bk_url = "https://lbjlincoln26-intraday-trading-floor.hf.space/api/bankrolls"
    d = _http_get(bk_url)
    if not isinstance(d, dict):
        return []
    rows = []
    # Seed per ITF agent = fleet_equity / 17 at start
    seed_per = (d.get("fleet_equity") or 99000.0) / max(1, len(d.get("agents") or {}))
    for tid, a in (d.get("agents") or {}).items():
        llm = itf_map.get(tid, "unknown")
        avail = float(a.get("available") or 0)
        reserved = float(a.get("reserved_open") or 0)
        total = float(a.get("total_equity") or (avail + reserved))
        rows.append({
            "tf": "itf", "tid": tid, "llm": llm,
            "bankroll": total, "bets": None, "wins": None, "losses": None, "wr": None,
            "roi_pct": (total / max(1, seed_per) - 1) * 100,
        })
    return rows


def _aggregate_by_llm(rows: list[dict]) -> list[dict]:
    by_llm: dict[str, dict] = {}
    for r in rows:
        llm = r["llm"]
        slot = by_llm.setdefault(llm, {
            "llm": llm,
            "total_bankroll": 0.0,
            "tfs_present": set(),
            "total_bets": 0,
            "total_wins": 0,
            "total_losses": 0,
            "per_tf": {},
        })
        slot["total_bankroll"] += r["bankroll"]
        slot["tfs_present"].add(r["tf"])
        if r["bets"]: slot["total_bets"] += r["bets"]
        if r["wins"]: slot["total_wins"] += r["wins"]
        if r["losses"]: slot["total_losses"] += r["losses"]
        slot["per_tf"][r["tf"]] = {
            "tid": r["tid"],
            "bankroll": r["bankroll"],
            "wr": r["wr"],
            "bets": r["bets"],
            "roi_pct": r["roi_pct"],
        }
    for slot in by_llm.values():
        slot["tfs_present"] = sorted(slot["tfs_present"])
        w, l = slot["total_wins"], slot["total_losses"]
        slot["wr_combined"] = (w / max(1, w + l)) if (w + l) > 0 else None
    return sorted(by_llm.values(), key=lambda x: -x["total_bankroll"])


def _markdown(rows_by_llm: list[dict], per_row: list[dict]) -> str:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = [f"# Cross-TF LLM Scorecard -- {now}", ""]
    out.append("Same LLM tested across NBA / POL / ITF. Higher total_bankroll = better LLM across markets.")
    out.append("")
    out.append("| LLM | TFs | NBA $ | POL $ | ITF $ | Total $ | Combined WR | Bets |")
    out.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for s in rows_by_llm:
        nba_bk = s["per_tf"].get("nba", {}).get("bankroll")
        pol_bk = s["per_tf"].get("pol", {}).get("bankroll")
        itf_bk = s["per_tf"].get("itf", {}).get("bankroll")
        wr = s["wr_combined"]
        out.append(
            f"| `{s['llm']}` | {','.join(s['tfs_present'])} | "
            f"{('$'+format(nba_bk,'.0f')) if nba_bk is not None else '-'} | "
            f"{('$'+format(pol_bk,'.0f')) if pol_bk is not None else '-'} | "
            f"{('$'+format(itf_bk,'.0f')) if itf_bk is not None else '-'} | "
            f"${s['total_bankroll']:.0f} | "
            f"{('{:.1%}'.format(wr)) if wr is not None else '-'} | "
            f"{s['total_bets'] or '-'} |"
        )
    return "\n".join(out)


def main() -> int:
    nba = _nba_pol_snapshot("nba", "https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/leaderboard")
    pol = _nba_pol_snapshot("pol", "https://lbjlincoln26-political-llm-trading-floor.hf.space/api/leaderboard")
    itf_map = _load_itf_llm_map()
    itf = _itf_snapshot(itf_map)

    all_rows = nba + pol + itf
    by_llm = _aggregate_by_llm(all_rows)

    ts = dt.datetime.now(dt.timezone.utc).isoformat()
    (OUT_DIR / "cross-llm-latest.json").write_text(
        json.dumps({"ts": ts, "by_llm": by_llm, "per_row": all_rows}, indent=2, default=str)
    )
    (OUT_DIR / "cross-llm-latest.md").write_text(_markdown(by_llm, all_rows))

    print(f"ts={ts} llms={len(by_llm)} nba={len(nba)} pol={len(pol)} itf={len(itf)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
