#!/usr/bin/env python3
"""tf_analytics — per-agent / per-category / per-bet daily analyzer for all 3 TFs.

Pulls the latest day-XXX.json from each Space, emits:

  data/tf-analytics/{tf}/day-{day:03d}.json   (single day snapshot)
  data/tf-analytics/{tf}/cumulative.json      (rolling fleet history)
  data/tf-analytics/summary.json              (1-screen cross-TF digest)

Per-agent fields: bankroll curve, WR, Sharpe (day-returns), max-DD,
pact-count (when available), Jaccard-vs-fleet (today), bet count.

Per-category (NBA/POL) or per-etf+option (PQTF): WR + total_pnl + share-of-fleet.

Per-bet: full log, compact shape.

Cron: every 4h at :45, after run_audit.py at :40 runs first.
"""
import datetime
import json
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "data" / "tf-analytics"
OUT_DIR.mkdir(parents=True, exist_ok=True)

NBA_SPACE = "LBJLincoln26/nba-llm-trading-floor"
POL_SPACE = "LBJLincoln26/political-llm-trading-floor"
PQTF_SPACE = "LBJLincoln26/political-quant-trading-floor"

ITF_BASE = "https://lbjlincoln26-intraday-trading-floor.hf.space"
ITF_DECISIONS = f"{ITF_BASE}/api/decisions"
ITF_TRADES = f"{ITF_BASE}/api/trades"
ITF_STATUS = f"{ITF_BASE}/api/status"
ITF_BANKROLLS = f"{ITF_BASE}/api/bankrolls"


def hf_token():
    for k in ("HF_TOKEN_2", "HF_TOKEN_NBA", "HF_TOKEN_LLM", "HF_TOKEN_3", "HF_TOKEN"):
        v = os.environ.get(k)
        if v:
            return v
    env_local = REPO / ".env.local"
    if env_local.exists():
        vals = {}
        for line in env_local.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"): continue
            if line.startswith("export "): line = line[len("export "):]
            if "=" not in line: continue
            k, v = line.split("=", 1)
            v = v.strip()
            # Quoted value → stop at closing quote (strip trailing inline comments).
            if v.startswith('"'):
                end = v.find('"', 1)
                v = v[1:end] if end > 0 else v[1:]
            elif v.startswith("'"):
                end = v.find("'", 1)
                v = v[1:end] if end > 0 else v[1:]
            else:
                # Unquoted — stop at first whitespace-# (POSIX-style comment)
                hash_pos = v.find(" #")
                if hash_pos > 0: v = v[:hash_pos]
                v = v.strip()
            if v.startswith("$"): v = vals.get(v[1:].strip("{}"), v)
            vals[k.strip()] = v
        for k in ("HF_TOKEN_2", "HF_TOKEN_NBA", "HF_TOKEN_LLM", "HF_TOKEN_3", "HF_TOKEN"):
            if vals.get(k): return vals[k]
    return None


def fetch_day(space, n_back=0, token=None):
    """Fetch the Nth-from-latest day file (0 = latest)."""
    from huggingface_hub import HfApi, hf_hub_download
    api = HfApi(token=token)
    files = sorted(f for f in api.list_repo_files(space, repo_type="space")
                   if "data/decisions/day-" in f and f.endswith(".json"))
    if not files or n_back >= len(files):
        return None, None
    rf = files[-1 - n_back]
    p = hf_hub_download(space, rf, repo_type="space", token=token,
                        cache_dir="/tmp/nomos-tf-analytics", force_download=True)
    return rf, json.loads(open(p, encoding="utf-8").read())


def fetch_range(space, n=5, token=None):
    """Fetch the last N days. Newest last."""
    from huggingface_hub import HfApi, hf_hub_download
    api = HfApi(token=token)
    files = sorted(f for f in api.list_repo_files(space, repo_type="space")
                   if "data/decisions/day-" in f and f.endswith(".json"))
    out = []
    for rf in files[-n:]:
        p = hf_hub_download(space, rf, repo_type="space", token=token,
                            cache_dir="/tmp/nomos-tf-analytics", force_download=True)
        try:
            out.append((rf, json.loads(open(p, encoding="utf-8").read())))
        except Exception:
            continue
    return out


def _sharpe(returns):
    if len(returns) < 2: return None
    m = statistics.mean(returns)
    s = statistics.pstdev(returns)
    if s == 0: return None
    return round(m / s * (252 ** 0.5), 3)


def _max_drawdown(bankroll_series):
    if not bankroll_series: return None
    peak = bankroll_series[0]
    dd = 0
    for b in bankroll_series:
        if b > peak: peak = b
        if peak > 0:
            cur = (peak - b) / peak
            if cur > dd: dd = cur
    return round(dd, 4)


def _jaccard(a, b):
    if not a or not b: return None
    inter = len(a & b); union = len(a | b)
    return inter / union if union else None


def analyze_nba_pol(tf, latest, history, start_cap):
    """Schema: {agents: {tid: {allocations: [{game/ticker, category/direction, stake, profit, won}], bankroll_before, bankroll_after}}}"""
    ag = latest.get("agents") or {}
    day_idx = latest.get("day_idx") or latest.get("day")
    date = latest.get("date")

    per_agent = {}
    per_category = defaultdict(lambda: {"wins": 0, "losses": 0, "stake_sum": 0.0,
                                         "profit_sum": 0.0, "agents": set()})
    per_bet = []
    # Pick sets per agent for cross-agent Jaccard
    pick_sets = {}

    for tid, log in ag.items():
        allocs = log.get("allocations") or []
        bb = log.get("bankroll_before") or start_cap
        ba = log.get("bankroll_after") or bb
        wins = sum(1 for a in allocs if a.get("won") is True)
        losses = sum(1 for a in allocs if a.get("won") is False)

        # Build per-agent picks for Jaccard
        picks = set()
        for a in allocs:
            if tf == "nba":
                k = (a.get("game"), a.get("category"))
            else:
                k = (a.get("ticker") or a.get("event_idx"), a.get("direction"))
            if k[0] is not None:
                picks.add(k)
        pick_sets[tid] = picks

        # Bankroll history from agent state if available
        hist = log.get("history") or []
        curve = list(hist) if hist else [bb, ba]
        # Day returns from curve
        day_returns = []
        for i in range(1, len(curve)):
            if curve[i-1] > 0:
                day_returns.append((curve[i] - curve[i-1]) / curve[i-1])
        per_agent[tid] = {
            "bankroll_before": round(bb, 2),
            "bankroll_after": round(ba, 2),
            "day_pnl": round(ba - bb, 2),
            "day_return_pct": round(((ba - bb) / bb * 100) if bb else 0, 3),
            "n_bets": len(allocs),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / (wins + losses), 3) if (wins + losses) else None,
            "stake_total": round(sum(a.get("stake", 0) for a in allocs), 2),
            "profit_total": round(sum(a.get("profit", 0) for a in allocs), 2),
            "deploy_pct": round(sum(a.get("stake", 0) for a in allocs) / bb, 3) if bb else 0,
            "sharpe_approx": _sharpe(day_returns),
            "max_drawdown": _max_drawdown(curve),
            "cash_held_pct": log.get("cash_held_pct"),
            "day_strategy": (log.get("day_strategy") or "")[:120],
            "coalition_proposal": log.get("coalition_proposal"),
        }

        # Per-category aggregation
        for a in allocs:
            cat = a.get("category") or a.get("event_type") or "unknown"
            if a.get("won") is True: per_category[cat]["wins"] += 1
            elif a.get("won") is False: per_category[cat]["losses"] += 1
            per_category[cat]["stake_sum"] += a.get("stake", 0)
            per_category[cat]["profit_sum"] += a.get("profit", 0)
            per_category[cat]["agents"].add(tid)
            # Per-bet log (compact)
            per_bet.append({
                "tid": tid,
                "game": a.get("game") or a.get("ticker") or a.get("event_idx"),
                "cat": cat,
                "stake": round(a.get("stake", 0), 2),
                "pnl": round(a.get("profit", 0), 2),
                "won": a.get("won"),
                "edge": a.get("edge"),
                "odds": a.get("odds"),
                "confidence": a.get("confidence"),
                "source": a.get("source", "direct"),
            })

    # Jaccard per agent vs fleet (mean pairwise)
    tids = list(pick_sets.keys())
    for tid in tids:
        js = []
        for other in tids:
            if other == tid: continue
            v = _jaccard(pick_sets[tid], pick_sets[other])
            if v is not None: js.append(v)
        per_agent[tid]["jaccard_vs_fleet_mean"] = round(sum(js) / len(js), 3) if js else None

    # Finalize per_category: sets → lists
    for cat, stats in per_category.items():
        stats["agents_covered"] = len(stats["agents"])
        stats["agents"] = sorted(stats["agents"])
        n = stats["wins"] + stats["losses"]
        stats["win_rate"] = round(stats["wins"] / n, 3) if n else None
        stats["stake_sum"] = round(stats["stake_sum"], 2)
        stats["profit_sum"] = round(stats["profit_sum"], 2)
        stats["roi"] = round(stats["profit_sum"] / stats["stake_sum"], 3) if stats["stake_sum"] else None

    # Fleet aggregate
    bankrolls = [log.get("bankroll_after") for log in ag.values() if log.get("bankroll_after") is not None]
    fleet = {
        "n_agents": len(ag),
        "fleet_total": round(sum(bankrolls), 2) if bankrolls else None,
        "fleet_avg": round(sum(bankrolls) / len(bankrolls), 2) if bankrolls else None,
        "fleet_leader": max(ag.items(), key=lambda kv: kv[1].get("bankroll_after", 0))[0] if ag else None,
        "fleet_laggard": min(ag.items(), key=lambda kv: kv[1].get("bankroll_after", 0))[0] if ag else None,
        "fleet_total_deploy_pct": round(sum(per_agent[t]["deploy_pct"] for t in per_agent) / len(per_agent), 3) if per_agent else 0,
        "day_total_bets": sum(per_agent[t]["n_bets"] for t in per_agent),
        "day_total_wins": sum(per_agent[t]["wins"] for t in per_agent),
        "day_total_losses": sum(per_agent[t]["losses"] for t in per_agent),
        "day_fleet_pnl": round(sum(per_agent[t]["day_pnl"] for t in per_agent), 2),
    }
    fleet["day_fleet_wr"] = (round(fleet["day_total_wins"] / (fleet["day_total_wins"] + fleet["day_total_losses"]), 3)
                              if (fleet["day_total_wins"] + fleet["day_total_losses"]) else None)

    # Fleet-level Jaccard (all pairs)
    all_j = []
    for i in range(len(tids)):
        for j in range(i + 1, len(tids)):
            v = _jaccard(pick_sets[tids[i]], pick_sets[tids[j]])
            if v is not None: all_j.append(v)
    fleet["jaccard_fleet_mean"] = round(sum(all_j) / len(all_j), 3) if all_j else None
    fleet["jaccard_fleet_max"] = round(max(all_j), 3) if all_j else None

    return {
        "tf": tf, "day_idx": day_idx, "date": date,
        "written_at": datetime.datetime.utcnow().isoformat() + "Z",
        "fleet": fleet,
        "per_agent": per_agent,
        "per_category": dict(per_category),
        "per_bet": per_bet,
    }


def analyze_pqtf(latest):
    """Schema: {date, sessions: [{positions: [{tid, etf, option_type, strike, tte_days, qty, entry_price, iv_open}], pacts, risk}], agents_start, agents_end}"""
    sessions = latest.get("sessions") or []
    date = latest.get("date")
    start_map = latest.get("agents_start") or {}
    end_map = latest.get("agents_end") or {}

    per_agent = {}
    per_etf = defaultdict(lambda: {"n_positions": 0, "notional": 0.0, "agents": set(),
                                    "calls": 0, "puts": 0, "multi_leg": 0})
    per_bet = []  # positions
    pick_sets = defaultdict(set)

    all_tids = set(start_map.keys()) | set(end_map.keys())
    for tid in all_tids:
        per_agent[tid] = {
            "bankroll_start": round(start_map.get(tid, 0), 2),
            "bankroll_end": round(end_map.get(tid, 0), 2),
            "day_pnl": round(end_map.get(tid, 0) - start_map.get(tid, 0), 2),
            "day_return_pct": (round((end_map.get(tid, 0) - start_map.get(tid, 0)) / start_map.get(tid, 1) * 100, 3)
                              if start_map.get(tid) else None),
            "n_positions": 0, "n_calls": 0, "n_puts": 0, "n_multi_leg": 0,
            "etfs_touched": set(), "notional_gross": 0.0, "pacts": 0,
        }

    total_pacts = 0
    total_stops = 0
    all_var = []
    all_ivs = []

    for s in sessions:
        positions = s.get("positions") or []
        pacts = s.get("pacts") or []
        risk = s.get("risk") or {}
        total_pacts += len(pacts)
        if risk.get("var_95_1d") is not None: all_var.append(risk["var_95_1d"])
        total_stops += risk.get("stops_triggered", 0) or 0

        # Count pacts per agent
        for pact in pacts:
            for tid in pact.get("pair", []) or []:
                if tid in per_agent:
                    per_agent[tid]["pacts"] += 1

        for pos in positions:
            tid = pos.get("tid")
            if tid not in per_agent: continue
            etf = pos.get("etf")
            # 2026-04-20 zombie-row fix: multi-leg positions store strategy in
            # `option_type` (e.g. "vertical", "iron_condor"). Fall back through
            # explicit `strategy` field for legacy state files written before
            # the engine fix landed.
            is_multi_leg = bool(pos.get("multi_leg")) or (pos.get("strategy") in
                                                          ("vertical", "iron_condor", "straddle", "butterfly"))
            opt = pos.get("option_type")
            if is_multi_leg and (opt is None or opt in ("call", "put")):
                # Engine-side fix sets opt=strategy_kind for new rows; legacy
                # state may have opt=None or opt="call". Prefer explicit strategy.
                opt = pos.get("strategy") or opt or "multi_leg"
            strike = pos.get("strike") or 0
            qty = pos.get("qty") or 0
            px = pos.get("entry_price") or 0
            # For multi-leg positions, fall back to `cost`/qty as per-contract premium
            # so notional reflects deployed capital instead of zero.
            if is_multi_leg and not px:
                _cost = pos.get("cost") or 0
                if qty and _cost:
                    px = abs(_cost) / (qty * 100)
            notional = abs(qty * px * 100)  # options contract = 100 shares

            per_agent[tid]["n_positions"] += 1
            if opt == "call": per_agent[tid]["n_calls"] += 1
            elif opt == "put": per_agent[tid]["n_puts"] += 1
            if is_multi_leg: per_agent[tid]["n_multi_leg"] += 1
            per_agent[tid]["etfs_touched"].add(etf)
            per_agent[tid]["notional_gross"] += notional
            pick_sets[tid].add((etf, opt, round(strike, 0), pos.get("tte_days")))

            per_etf[etf]["n_positions"] += 1
            per_etf[etf]["notional"] += notional
            per_etf[etf]["agents"].add(tid)
            if opt == "call": per_etf[etf]["calls"] += 1
            elif opt == "put": per_etf[etf]["puts"] += 1
            if is_multi_leg: per_etf[etf]["multi_leg"] += 1

            if pos.get("iv_open") is not None:
                all_ivs.append(pos["iv_open"])

            per_bet.append({
                "tid": tid, "etf": etf, "type": opt,
                "strike": round(strike, 2), "qty": qty,
                "entry_price": round(px, 4),
                "tte_days": pos.get("tte_days"),
                "iv_open": pos.get("iv_open"),
                "notional": round(notional, 2),
                "session": s.get("session_id"),
            })

    # Multi-leg detection — pact-linked positions count as legs of same structure
    # Simplification: n_multi_leg = sum of sessions.risk.n_multi_leg
    for s in sessions:
        for tid in per_agent:
            # approx attribution: spread multi-leg count evenly across active agents
            pass

    # Pairwise Jaccard
    tids = list(pick_sets.keys())
    fleet_j = []
    for tid in tids:
        js = []
        for other in tids:
            if other == tid: continue
            v = _jaccard(pick_sets[tid], pick_sets[other])
            if v is not None: js.append(v)
        per_agent[tid]["jaccard_vs_fleet_mean"] = round(sum(js) / len(js), 3) if js else None
        fleet_j.extend(js)
    # Each pair counted twice above — dedupe by halving
    fleet_j = fleet_j[::2] if fleet_j else []

    # Serialize sets
    for tid, d in per_agent.items():
        d["etfs_touched"] = sorted(d["etfs_touched"])
        d["notional_gross"] = round(d["notional_gross"], 2)

    for etf, d in per_etf.items():
        d["agents_covered"] = len(d["agents"])
        d["agents"] = sorted(d["agents"])
        d["notional"] = round(d["notional"], 2)

    fleet = {
        "n_agents": len(all_tids),
        "fleet_total": round(sum(end_map.values()), 2),
        "fleet_avg": round(sum(end_map.values()) / len(end_map), 2) if end_map else None,
        "fleet_leader": max(end_map.items(), key=lambda kv: kv[1])[0] if end_map else None,
        "fleet_laggard": min(end_map.items(), key=lambda kv: kv[1])[0] if end_map else None,
        "day_fleet_pnl": round(sum(per_agent[t]["day_pnl"] for t in per_agent), 2),
        "n_sessions": len(sessions),
        "n_positions": sum(1 for _ in per_bet),
        "n_pacts": total_pacts,
        "n_stops_triggered": total_stops,
        "avg_var_95": round(sum(all_var) / len(all_var), 2) if all_var else None,
        "max_var_95": round(max(all_var), 2) if all_var else None,
        "avg_iv_open": round(sum(all_ivs) / len(all_ivs), 4) if all_ivs else None,
        "jaccard_fleet_mean": round(sum(fleet_j) / len(fleet_j), 3) if fleet_j else None,
        "jaccard_fleet_max": round(max(fleet_j), 3) if fleet_j else None,
    }

    return {
        "tf": "pqtf", "day_idx": latest.get("day_idx"), "date": date,
        "written_at": datetime.datetime.utcnow().isoformat() + "Z",
        "fleet": fleet,
        "per_agent": per_agent,
        "per_etf": dict(per_etf),
        "per_bet": per_bet,
    }


def fetch_itf_snapshot(timeout=10):
    """ITF is always 'today' — pull decisions + trades + status + bankrolls."""
    import urllib.request
    def _get(url):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception:
            return None
    return {
        "decisions": _get(ITF_DECISIONS),
        "trades": _get(ITF_TRADES),
        "status": _get(ITF_STATUS),
        "bankrolls": _get(ITF_BANKROLLS),
    }


def analyze_itf(snap):
    """ITF has no day-XXX.json — single live snapshot.

    Schema combines:
      - /api/decisions — {date, decisions: [{ts, agent_tid, tier, decision:{action,reason,_llm_routed_via}}]}
      - /api/trades — {count, trades: [{ts, agent_tid, ticker, side, qty, stake_usd, ...}]}
      - /api/status — {agents: {tid: {decisions, trades, passes, bankroll}}}
      - /api/bankrolls — {fleet_*, agents: {tid: {available, reserved_open, total_equity}}}
    """
    if not snap or not snap.get("status"):
        return None
    decisions = (snap.get("decisions") or {}).get("decisions") or []
    date = (snap.get("decisions") or {}).get("date")
    trades = (snap.get("trades") or {}).get("trades") or []
    status_agents = (snap.get("status") or {}).get("agents") or {}
    bankrolls_agents = (snap.get("bankrolls") or {}).get("agents") or {}

    all_tids = set(status_agents.keys()) | set(bankrolls_agents.keys())

    per_agent = {}
    for tid in all_tids:
        s = status_agents.get(tid, {}) or {}
        br = bankrolls_agents.get(tid, {}) or {}
        per_agent[tid] = {
            "bankroll": round(br.get("total_equity") or s.get("bankroll") or 0, 2),
            "bankroll_available": round(br.get("available") or 0, 2),
            "bankroll_reserved": round(br.get("reserved_open") or 0, 2),
            "n_decisions": s.get("decisions", 0),
            "n_trades": s.get("trades", 0),
            "n_passes": s.get("passes", 0),
            "pass_rate": (round(s.get("passes", 0) / s["decisions"], 3)
                          if s.get("decisions") else None),
            "tickers_touched": set(),
            "notional_gross": 0.0,
            "llm_models": defaultdict(int),
            "action_mix": defaultdict(int),
        }

    # Decisions — count action mix, LLM routing, tickers
    for d in decisions:
        tid = d.get("agent_tid")
        if tid not in per_agent:
            per_agent[tid] = {
                "bankroll": 0, "bankroll_available": 0, "bankroll_reserved": 0,
                "n_decisions": 0, "n_trades": 0, "n_passes": 0, "pass_rate": None,
                "tickers_touched": set(), "notional_gross": 0.0,
                "llm_models": defaultdict(int), "action_mix": defaultdict(int),
            }
        dec = d.get("decision") or {}
        action = dec.get("action", "unknown")
        per_agent[tid]["action_mix"][action] += 1
        routed = dec.get("_llm_routed_via") or "unknown"
        per_agent[tid]["llm_models"][routed] += 1

    # Per-ticker + per-bet aggregation from trades
    per_ticker = defaultdict(lambda: {"n_trades": 0, "notional": 0.0,
                                        "agents": set(), "longs": 0, "shorts": 0})
    per_bet = []
    pick_sets = defaultdict(set)

    for t in trades:
        tid = t.get("agent_tid")
        ticker = t.get("ticker")
        side = t.get("side")
        stake = float(t.get("stake_usd") or 0)
        if tid in per_agent:
            per_agent[tid]["tickers_touched"].add(ticker)
            per_agent[tid]["notional_gross"] += stake
            pick_sets[tid].add((ticker, side))
        per_ticker[ticker]["n_trades"] += 1
        per_ticker[ticker]["notional"] += stake
        per_ticker[ticker]["agents"].add(tid)
        if side == "long": per_ticker[ticker]["longs"] += 1
        elif side == "short": per_ticker[ticker]["shorts"] += 1
        per_bet.append({
            "ts": t.get("ts"),
            "tid": tid,
            "ticker": ticker,
            "side": side,
            "qty": t.get("qty"),
            "entry_price": t.get("entry_price"),
            "stake_usd": round(stake, 2),
            "stop_pct": t.get("stop_pct"),
            "take_profit_pct": t.get("take_profit_pct"),
            "status": t.get("status"),
            "broker_class": t.get("broker_class"),
        })

    # Pairwise Jaccard across agents that traded
    tids = list(pick_sets.keys())
    fleet_j = []
    for tid in tids:
        js = []
        for other in tids:
            if other == tid: continue
            v = _jaccard(pick_sets[tid], pick_sets[other])
            if v is not None: js.append(v)
        per_agent[tid]["jaccard_vs_fleet_mean"] = round(sum(js)/len(js), 3) if js else None
        fleet_j.extend(js)
    fleet_j = fleet_j[::2] if fleet_j else []

    # Serialize
    for tid, d in per_agent.items():
        d["tickers_touched"] = sorted(d["tickers_touched"])
        d["notional_gross"] = round(d["notional_gross"], 2)
        d["llm_models"] = dict(d["llm_models"])
        d["action_mix"] = dict(d["action_mix"])
    for ticker, d in per_ticker.items():
        d["agents_covered"] = len(d["agents"])
        d["agents"] = sorted(d["agents"])
        d["notional"] = round(d["notional"], 2)

    equities = sum(a.get("bankroll", 0) for a in per_agent.values())
    leader = max(per_agent.items(), key=lambda kv: kv[1].get("bankroll", 0))[0] if per_agent else None
    laggard = min(per_agent.items(), key=lambda kv: kv[1].get("bankroll", 0))[0] if per_agent else None

    fleet = {
        "n_agents": len(per_agent),
        "fleet_total": round(equities, 2),
        "fleet_avg": round(equities / len(per_agent), 2) if per_agent else None,
        "fleet_available": round(sum(a.get("bankroll_available", 0) for a in per_agent.values()), 2),
        "fleet_reserved": round(sum(a.get("bankroll_reserved", 0) for a in per_agent.values()), 2),
        "fleet_leader": leader,
        "fleet_laggard": laggard,
        "day_total_trades": len(trades),
        "day_total_decisions": len(decisions),
        "day_total_passes": sum(a.get("n_passes", 0) for a in per_agent.values()),
        "fleet_pass_rate": (round(sum(a.get("n_passes", 0) for a in per_agent.values()) /
                                   sum(a.get("n_decisions", 0) for a in per_agent.values()), 3)
                            if sum(a.get("n_decisions", 0) for a in per_agent.values()) else None),
        "n_unique_tickers": len(per_ticker),
        "jaccard_fleet_mean": round(sum(fleet_j)/len(fleet_j), 3) if fleet_j else None,
        "jaccard_fleet_max": round(max(fleet_j), 3) if fleet_j else None,
    }

    return {
        "tf": "itf", "day_idx": None, "date": date,
        "written_at": datetime.datetime.utcnow().isoformat() + "Z",
        "fleet": fleet,
        "per_agent": per_agent,
        "per_ticker": dict(per_ticker),
        "per_bet": per_bet,
    }


def _process_nba_pol(tf, space, token):
    rf, d = fetch_day(space, token=token)
    if not d: return None
    out = analyze_nba_pol(tf, d, None, start_cap=100)
    day_str = rf.split("/")[-1].replace(".json", "") if rf else f"day-{out['day_idx']:03d}"
    out_dir = OUT_DIR / tf; out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{day_str}.json").write_text(json.dumps(out, indent=2, default=str))
    return out, day_str


def _process_pqtf(token):
    rf, d = fetch_day(PQTF_SPACE, token=token)
    if not d: return None
    out = analyze_pqtf(d)
    day_str = rf.split("/")[-1].replace(".json", "") if rf else "day-unknown"
    out_dir = OUT_DIR / "pqtf"; out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{day_str}.json").write_text(json.dumps(out, indent=2, default=str))
    return out, day_str


def backfill(token, n_back):
    """Pull the last N day-XXX.json files from each day-batched TF and analyze each.

    Writes data/tf-analytics/<tf>/day-XXX.json for every recovered day.
    ITF is skipped (it's always 'today' — nothing to backfill).
    """
    print(f"[tf_analytics] backfill last {n_back} days across NBA/POL/PQTF")
    for space, tf, analyzer in [
        (NBA_SPACE, "nba", lambda d: analyze_nba_pol("nba", d, None, start_cap=100)),
        (POL_SPACE, "pol", lambda d: analyze_nba_pol("pol", d, None, start_cap=100)),
        (PQTF_SPACE, "pqtf", analyze_pqtf),
    ]:
        out_dir = OUT_DIR / tf; out_dir.mkdir(parents=True, exist_ok=True)
        try:
            rows = fetch_range(space, n=n_back, token=token)
            for rf, d in rows:
                try:
                    out = analyzer(d)
                    day_str = rf.split("/")[-1].replace(".json", "")
                    (out_dir / f"{day_str}.json").write_text(json.dumps(out, indent=2, default=str))
                    print(f"  {tf}/{day_str}: fleet_total={out['fleet'].get('fleet_total')}")
                except Exception as e:
                    print(f"  {tf}/{rf} FAIL: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[tf_analytics] {tf} backfill aborted: {e}", file=sys.stderr)


def run():
    token = hf_token()
    if not token:
        print("[tf_analytics] NO HF_TOKEN — abort", file=sys.stderr)
        sys.exit(1)

    # --backfill=N runs a bulk backfill then exits (does not touch summary.json).
    for arg in sys.argv[1:]:
        if arg.startswith("--backfill="):
            n = int(arg.split("=", 1)[1])
            backfill(token, n)
            return
        if arg == "--backfill":
            backfill(token, 50)
            return

    summary = {"ts": datetime.datetime.utcnow().isoformat() + "Z", "tfs": {}}

    # NBA
    try:
        res = _process_nba_pol("nba", NBA_SPACE, token)
        if res:
            out, day_str = res
            summary["tfs"]["nba"] = {
                "day": out["day_idx"], "date": out["date"],
                "fleet": out["fleet"], "source_file": day_str,
            }
            print(f"[tf_analytics] NBA {day_str}: fleet={out['fleet']['fleet_total']:.0f} "
                  f"WR={out['fleet']['day_fleet_wr']} Jaccard={out['fleet']['jaccard_fleet_mean']}")
    except Exception as e:
        summary["tfs"]["nba"] = {"error": str(e)}
        print(f"[tf_analytics] NBA error: {e}", file=sys.stderr)

    # POL
    try:
        res = _process_nba_pol("pol", POL_SPACE, token)
        if res:
            out, day_str = res
            summary["tfs"]["pol"] = {
                "day": out["day_idx"], "date": out["date"],
                "fleet": out["fleet"], "source_file": day_str,
            }
            print(f"[tf_analytics] POL {day_str}: fleet={out['fleet']['fleet_total']:.0f} "
                  f"WR={out['fleet']['day_fleet_wr']} Jaccard={out['fleet']['jaccard_fleet_mean']}")
    except Exception as e:
        summary["tfs"]["pol"] = {"error": str(e)}
        print(f"[tf_analytics] POL error: {e}", file=sys.stderr)

    # PQTF
    try:
        res = _process_pqtf(token)
        if res:
            out, day_str = res
            summary["tfs"]["pqtf"] = {
                "day": out["day_idx"], "date": out["date"],
                "fleet": out["fleet"], "source_file": day_str,
            }
            print(f"[tf_analytics] PQTF {day_str}: fleet=${out['fleet']['fleet_total']:.0f} "
                  f"VaR95={out['fleet']['avg_var_95']} Jaccard={out['fleet']['jaccard_fleet_mean']}")
    except Exception as e:
        summary["tfs"]["pqtf"] = {"error": str(e)}
        print(f"[tf_analytics] PQTF error: {e}", file=sys.stderr)

    # ITF (no day-XXX.json — live HF endpoints)
    try:
        snap = fetch_itf_snapshot()
        out = analyze_itf(snap)
        if out:
            day_str = f"day-{out['date']}" if out.get("date") else "day-unknown"
            itf_dir = OUT_DIR / "itf"; itf_dir.mkdir(parents=True, exist_ok=True)
            (itf_dir / f"{day_str}.json").write_text(json.dumps(out, indent=2, default=str))
            summary["tfs"]["itf"] = {
                "day": out["day_idx"], "date": out["date"],
                "fleet": out["fleet"], "source_file": day_str,
            }
            print(f"[tf_analytics] ITF {day_str}: fleet=${out['fleet']['fleet_total']:.0f} "
                  f"trades={out['fleet']['day_total_trades']} "
                  f"tickers={out['fleet']['n_unique_tickers']} "
                  f"Jaccard={out['fleet']['jaccard_fleet_mean']}")
    except Exception as e:
        summary["tfs"]["itf"] = {"error": str(e)}
        print(f"[tf_analytics] ITF error: {e}", file=sys.stderr)

    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"[tf_analytics] summary written to {OUT_DIR}/summary.json")


if __name__ == "__main__":
    run()
