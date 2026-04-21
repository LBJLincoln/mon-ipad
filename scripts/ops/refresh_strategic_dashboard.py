#!/usr/bin/env python3
"""
Refreshes data/strategic-dashboard/ — 10-file live snapshot for strategic decisions.

Called every 15min by cron. Probes live HF Space APIs + reads repo state.
Static .md files (mission, roster, runway, queue) are written once and only
touched when their section changes; live .json files are rewritten every run.
"""

from __future__ import annotations
import json, os, sys, time, subprocess
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "strategic-dashboard"
OUT.mkdir(parents=True, exist_ok=True)

NOW = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")

def _fetch(url: str, timeout: int = 15) -> dict | None:
    try:
        req = Request(url, headers={"User-Agent": "strategic-dashboard/1.0"})
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (URLError, HTTPError, json.JSONDecodeError, TimeoutError) as e:
        return {"_error": f"{type(e).__name__}: {str(e)[:160]}"}

def _read_json(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text())
    except Exception:
        return None

def _write_json(p: Path, data: dict) -> None:
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))

# ── 01: TF health ────────────────────────────────────────────
def _leaderboard(s: dict) -> list:
    agents = s.get("agents") or s.get("fleet") or {}
    if isinstance(agents, list):
        agents = {a.get("trader_id") or a.get("id") or f"t{i}": a for i, a in enumerate(agents)}
    if not isinstance(agents, dict):
        return []
    rows = []
    for tid, a in agents.items():
        if not isinstance(a, dict): continue
        rows.append({
            "trader_id": tid,
            "bankroll": round(a.get("bankroll") or a.get("bankroll_now") or 0, 2),
            "n_bets": a.get("n_bets") or a.get("bets") or a.get("total_bets") or 0,
            "win_rate": a.get("win_rate") or a.get("wr") or 0,
            "model": a.get("model") or a.get("model_primary"),
        })
    rows.sort(key=lambda r: -r["bankroll"])
    return rows

def _alpaca_snapshot() -> dict:
    """ITF runs on Alpaca paper. Pull equity/positions for live P&L."""
    key = os.environ.get("ALPACA_PAPER_KEY")
    sec = os.environ.get("ALPACA_PAPER_SECRET")
    if not key or not sec:
        return {"reachable": False, "error": "ALPACA_PAPER_KEY/SECRET not in env"}
    base = "https://paper-api.alpaca.markets"
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec}
    out = {"reachable": True}
    for ep, label in [("/v2/account","account"), ("/v2/positions","positions"), ("/v2/orders?status=all&limit=50","orders")]:
        try:
            req = Request(base + ep, headers=headers)
            with urlopen(req, timeout=15) as r:
                out[label] = json.loads(r.read().decode())
        except Exception as e:
            out[label] = {"_error": str(e)[:120]}
    acc = out.get("account", {})
    if isinstance(acc, dict) and "equity" in acc:
        equity = float(acc.get("equity", 0))
        out["equity"] = equity
        out["cash"] = float(acc.get("cash", 0))
        out["portfolio_value"] = float(acc.get("portfolio_value", 0))
        out["buying_power"] = float(acc.get("buying_power", 0))
        out["pnl_since_100k"] = round(equity - 100000, 2)
        out["pnl_pct"] = round((equity - 100000) / 1000, 3)
        out["status"] = acc.get("status")
    positions = out.get("positions", [])
    if isinstance(positions, list):
        out["n_positions"] = len(positions)
        out["positions_summary"] = [
            {"symbol": p.get("symbol"), "qty": p.get("qty"), "side": p.get("side"),
             "market_value": float(p.get("market_value", 0)),
             "unrealized_pl": float(p.get("unrealized_pl", 0)),
             "unrealized_plpc": float(p.get("unrealized_plpc", 0))}
            for p in positions if isinstance(p, dict)
        ]
    orders = out.get("orders", [])
    if isinstance(orders, list):
        out["n_orders_last_50"] = len(orders)
        fill_count = sum(1 for o in orders if isinstance(o,dict) and o.get("status") == "filled")
        rej_count = sum(1 for o in orders if isinstance(o,dict) and o.get("status") in ("rejected","canceled"))
        out["orders_filled"] = fill_count
        out["orders_rejected_or_cancel"] = rej_count
    return out

def build_01_tf_health() -> dict:
    spaces = {
        "nba":  "https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/status",
        "pol":  "https://lbjlincoln26-political-llm-trading-floor.hf.space/api/status",
        "itf":  "https://lbjlincoln26-intraday-trading-floor.hf.space/api/status",
        "pqtf": "https://lbjlincoln26-pqtf.hf.space/api/status",
    }
    out = {"ts": NOW, "spaces": {}}
    for k, url in spaces.items():
        s = _fetch(url, timeout=20) or {}
        if isinstance(s, dict) and "_error" in s:
            out["spaces"][k] = {"url": url, "reachable": False, "error": s["_error"]}
            continue
        lb = _leaderboard(s)
        llm_c = s.get("llm_calls") or s.get("llm_total") or 0
        llm_f = s.get("llm_failures") or s.get("llm_fail") or 0
        stuck = [a for a in lb if a["n_bets"] == 0]
        out["spaces"][k] = {
            "url": url,
            "reachable": True,
            "running": s.get("running"),
            "mode": s.get("mode"),
            "updated": s.get("updated") or s.get("last_tick"),
            "days_processed": s.get("days_processed"),
            "total_days": s.get("total_days"),
            "tick": s.get("tick"),
            "games_processed": s.get("games_processed"),
            "fleet_best_bankroll": s.get("fleet_best_bankroll"),
            "fleet_best_agent": lb[0]["trader_id"] if lb else None,
            "n_agents": len(lb) or s.get("n_agents"),
            "llm_calls": llm_c,
            "llm_failures": llm_f,
            "llm_fail_rate_pct": round(100 * llm_f / max(1, llm_c), 1) if llm_c else None,
            "gateway_routed": s.get("gateway_routed"),
            "coalition_pacts_count": s.get("coalition_pacts_count"),
            "axelrod_canon_active": s.get("axelrod_canon_active"),
            "langfuse_active": s.get("langfuse_active"),
            "leaderboard": lb,
            "n_agents_stuck_zero_bets": len(stuck),
            "agents_stuck_zero_bets": [a["trader_id"] for a in stuck],
        }
    # Intentional: PQTF paused preserves $602K scientific validation
    if "pqtf" in out["spaces"]:
        out["spaces"]["pqtf"]["intentional_paused"] = True
        out["spaces"]["pqtf"]["paused_reason"] = (
            "PQTF fleet completed 50/50 at $602,354 (60.2% of $1M mission alone) — "
            "preserved as scientific validation point per project_pqtf_1m_60pct_apr19. "
            "DO NOT restart."
        )
    # ITF's /api/status doesn't expose portfolio — pull Alpaca paper account directly.
    out["alpaca_paper"] = _alpaca_snapshot()
    return out

# ── 02: evolution islands ────────────────────────────────────
def build_02_islands() -> dict:
    survivors_nba = {
        "S13": {"space": "Nomos42/nba-evo-4",         "model": "catboost",         "gen": 130,  "brier": 0.22749, "account": "Nomos42"},
        "S14": {"space": "Nomos42/nba-evo-5",         "model": "lightgbm",         "gen": 554,  "brier": 0.22186, "account": "Nomos42"},
        "S15": {"space": "Nomos42/nba-evo-6",         "model": "wide_search",      "gen": 127,  "brier": 0.22418, "account": "Nomos42"},
        "S17": {"space": "LBJLincoln26/nba-evo-s17",  "model": "ensemble",         "gen": 78,   "brier": 0.22340, "account": "LBJLincoln26"},
        "S18": {"space": "TESTforge42/nba-evo-s18",   "model": "catboost_spec",    "gen": 1030, "brier": 0.22114, "account": "TESTforge42"},
        "S22": {"space": "TESTforge42/nba-evo-s22",   "model": "venn_abers_fusion","gen": 39,   "brier": 0.22073, "account": "TESTforge42", "fleet_best": True, "checkpointed": "2026-04-19"},
    }
    survivors_pol = {
        "P1": {"space": "Nomos42/political-alpha",      "model": "xgboost",        "gen": 3042,  "brier": 0.24996, "account": "Nomos42"},
        "P2": {"space": "Nomos42/political-alpha-2",    "model": "lightgbm",       "gen": 11953, "brier": 0.25223, "account": "Nomos42"},
        "P4": {"space": "LBJLincoln/political-alpha-4", "model": "logistic",       "gen": 16728, "brier": 0.25146, "account": "LBJLincoln"},
        "P5": {"space": "LBJLincoln/political-alpha-5", "model": "catboost",       "gen": 21048, "brier": 0.24923, "account": "LBJLincoln", "fleet_best": True, "checkpointed": "2026-04-20"},
        "P7": {"space": "LBJLincoln/political-alpha-7", "model": "gradient_boost", "gen": 2098,  "brier": 0.24987, "account": "LBJLincoln"},
    }
    eliminated = ["S10","S11","S12","S16","S19","S20","S21","P3","P6","P8"]
    return {
        "ts": NOW,
        "targets": {"nba_brier_lt": 0.20, "pol_brier_lt": 0.25},
        "current_best": {
            "nba_fleet": {"island": "S22", "brier": 0.22073, "method": "venn_abers_fusion"},
            "nba_colab_one_shot": {"brier": 0.21514, "method": "TabICL 186f iter 129"},
            "pol_fleet": {"island": "P5", "brier": 0.24923, "method": "catboost"},
        },
        "walk_forward_avg": 0.22447,
        "nba_survivors": survivors_nba,
        "pol_survivors": survivors_pol,
        "eliminated": eliminated,
        "do_not_restart": eliminated,
    }

# ── 03: selfhost LLMs ────────────────────────────────────────
def build_03_selfhost() -> dict:
    gw = _fetch("https://lbjlincoln26-llm-gateway.hf.space/api/models", timeout=20) or {}
    models = gw.get("models", []) if isinstance(gw, dict) else []
    selfhost = sorted([m for m in models if isinstance(m, str) and m.startswith("selfhost:")])
    # Accounts: LBJLincoln / LBJLincoln26 / TESTforge42 (Nomos42 excluded — 403 "reached")
    return {
        "ts": NOW,
        "gateway_url": "https://lbjlincoln26-llm-gateway.hf.space",
        "gateway_reachable": "_error" not in gw,
        "total_models_in_registry": len(models),
        "selfhost_models_live": selfhost,
        "n_selfhost_live": len(selfhost),
        "accounts_serving": {
            "LBJLincoln":   ["qwen25-05b-cpu","gemma2-2b-cpu","phi35-mini-cpu"],
            "LBJLincoln26": ["gemma3-4b-cpu"],
            "TESTforge42":  ["qwen3-4b-cpu","llama32-1b-cpu","smollm3-3b","qwen25-15b"],
            "Nomos42":      [],
        },
        "nomos42_blocked": "Account saturated (islands+TFs+pixel-world+langfuse), 403 on selfhost restart",
        "gateway_routing_note": "selfhost:* prefix → LBJLincoln/* or TESTforge42/* variants, NOT Nomos42/*",
    }

# ── 04: YouTube ingestion ────────────────────────────────────
def build_04_youtube() -> dict:
    ov = _read_json(ROOT / "data" / "prompts" / "overrides.json") or {}
    out = {"ts": NOW, "per_fleet": {}}
    for fleet in ("nba","pol","itf","pqtf"):
        sec = (ov.get(fleet) or {})
        narrative = sec.get("market_narrative","")
        out["per_fleet"][fleet] = {
            "has_narrative": bool(narrative),
            "narrative_len": len(narrative),
            "narrative_ts": sec.get("market_narrative_ts"),
            "manual_videos_count": sec.get("manual_videos_count"),
            "current_version": sec.get("current_version"),
            # parse video count from narrative header if present
            "digest_video_count": (
                int(narrative.split("(")[1].split(" ")[0])
                if narrative.startswith("YouTube narrative digest (") else None
            ),
        }
    manual = _read_json(ROOT / "data" / "youtube" / "manual-ingested.json") or {}
    channels = _read_json(ROOT / "data" / "youtube" / "channel-state.json") or {}
    out["manual_videos"] = manual.get("videos", []) if isinstance(manual, dict) else []
    out["tracked_channels"] = channels.get("channels", {}) if isinstance(channels, dict) else {}
    out["n_tracked_channels"] = len(out["tracked_channels"])
    out["autofetch_cron"] = "17 */6 * * *  (every 6h) → scripts/ops/youtube_ingest_and_deploy.sh"
    return out

# ── 06: experiments ledger ───────────────────────────────────
def build_06_experiments() -> dict:
    return {
        "ts": NOW,
        "targets": {
            "nba_brier": {"target": 0.20, "current_fleet": 0.22073, "current_colab": 0.21514},
            "pol_brier": {"target": 0.25, "current_fleet": 0.24923},
            "pqtf_roi":  {"target": 10.0, "current": 1003.9, "status": "completed_scientific_validation"},
            "roi":       {"target": 0.05},
            "sharpe":    {"target": 1.5},
        },
        "shipped_recent": [
            {"id": "cat_66_market_consensus", "ts": "2026-04-20", "owner": "FRANKENSTEIN", "status": "shipped", "sha": "5e66371c4a39"},
            {"id": "venn_abers_fusion_S22",   "ts": "2026-04-19", "owner": "HAWKEYE→FRANKENSTEIN", "status": "canary_best", "brier": 0.22073},
            {"id": "prompt_mutator",          "ts": "2026-04-19", "owner": "FRANKENSTEIN", "status": "live_all_TFs"},
            {"id": "coalition_mandatory",     "ts": "2026-04-18", "owner": "FRANKENSTEIN", "status": "live_all_TFs"},
            {"id": "yt_channel_autofetch",    "ts": "2026-04-20", "owner": "FRANKENSTEIN", "status": "live_22_channels"},
            {"id": "load_prompt_override_narrative_fix", "ts": "2026-04-21", "owner": "SWITCHBOARD",
             "status": "deployed_POL_ITF_NBA_pending", "note": "market_narrative was silently dropped — patched"},
        ],
        "queued_for_frankenstein": [
            {"id": "tabpfn_2_5_wrapper",       "source": "paper 2511.08667", "benefit": "+40% vs XGBoost"},
            {"id": "isotonic_venn_abers",      "source": "daily HAWKEYE scan"},
            {"id": "polymarket_tf",            "source": "project_polymarket_tf_proposal_apr20"},
            {"id": "pol_options_overlay",     "source": "project_polymarket_tf_proposal_apr20"},
        ],
        "dead_lines": [
            {"id": "TF v4/v5 hash-simulation", "reason": "purged 2026-04-17 (4-tracks)"},
            {"id": "councils D1-D9 Spaces",    "reason": "DECOMMISSIONED 2026-04-20 — BLACKSMITH now no-op"},
            {"id": "RAG website / Factory",    "reason": "DECOMMISSIONED 2026-04-20"},
        ],
    }

# ── 08: browser + hermes ─────────────────────────────────────
def build_08_browser_hermes() -> dict:
    endpoints = {
        "browser_nba": "https://lbjlincoln-nomos-browser-nba.hf.space/api/status",
        "browser_qa":  "https://testforge42-nomos-browser-qa.hf.space/api/status",
        "hermes":      "https://lbjlincoln26-nomos-hermes-agent.hf.space/api/status",
    }
    out = {"ts": NOW, "agents": {}}
    for k, url in endpoints.items():
        s = _fetch(url, timeout=20) or {}
        out["agents"][k] = {
            "url": url,
            "reachable": "_error" not in s,
            "payload": s if "_error" not in s else {"error": s.get("_error")},
        }
    out["secrets_set"] = ["GOOGLE_API_KEY"]
    out["secrets_pending_user"] = ["ANTHROPIC_API_KEY","BROWSERUSE_API_KEY","NOUS_API_KEY","OPENROUTER_API_KEY"]
    return out

def main() -> int:
    files = {
        "01-tf-health.json":         build_01_tf_health(),
        "02-islands.json":           build_02_islands(),
        "03-selfhost-llms.json":     build_03_selfhost(),
        "04-youtube-ingestion.json": build_04_youtube(),
        "06-experiments-ledger.json":build_06_experiments(),
        "08-browser-hermes.json":    build_08_browser_hermes(),
    }
    for name, data in files.items():
        _write_json(OUT / name, data)
    # write refresh-status
    _write_json(OUT / "_refresh-status.json", {
        "ts": NOW,
        "files_written": list(files.keys()),
        "script": "scripts/ops/refresh_strategic_dashboard.py",
    })
    print(f"[refresh_strategic_dashboard] {NOW} — {len(files)} live files written to {OUT}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
