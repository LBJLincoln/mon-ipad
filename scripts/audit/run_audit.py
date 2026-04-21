#!/usr/bin/env python3
"""nomos-audit runner — scientific integrity checks on both TFs.

Runs 5 checks on the latest 3 day-XXX.json from each TF Space:
  1. Leakage: thesis↔outcome correlation
  2. Bet source distribution (forbidden sources)
  3. Win-rate outliers (>75% warn, >85% critical)
  4. Lockstep picks (DMAD bypass)
  5. Walk-forward cutoff (POL)

Writes findings to data/audit/YYYY-MM-DDTHHMM.json and alerts to ALERT.json.
"""
import json, os, re, sys, time, datetime
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUDIT_DIR = REPO / "data" / "audit"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

NBA_SPACE = "LBJLincoln26/nba-llm-trading-floor"
POL_SPACE = "LBJLincoln26/political-llm-trading-floor"
PQTF_SPACE = "LBJLincoln26/political-quant-trading-floor"

FORBIDDEN_SOURCES = {"ml_home-synth", "SPY-long-synth", "synthetic-fallback"}
ALLOWED_SOURCES = {"direct", "fallback-edge-post", "tiered-post-filter", "post-filter-edge"}


def hf_token():
    """Resolve HF token from env.local (handles bash 'export K=$REF' chains)."""
    if os.environ.get("HF_TOKEN_2"):
        return os.environ["HF_TOKEN_2"]
    env = REPO / ".env.local"
    if env.exists():
        vals = {}
        for raw in env.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip()
            # strip inline comments outside of quotes (bash-compatible)
            if v and v[0] in ('"', "'"):
                q = v[0]
                end = v.find(q, 1)
                v = v[1:end] if end > 0 else v[1:]
            else:
                # unquoted: cut at first whitespace or '#'
                for i, ch in enumerate(v):
                    if ch in (" ", "\t", "#"):
                        v = v[:i]
                        break
            if v.startswith("$"):
                v = vals.get(v[1:].strip("{}"), v)
            vals[k.strip()] = v
        for k in ("HF_TOKEN_2", "HF_TOKEN_NBA", "HF_TOKEN", "HF_TOKEN_3"):
            if vals.get(k):
                return vals[k]
    return os.environ.get("HF_TOKEN")


def fetch_days(space: str, n: int = 3, token: str = None):
    from huggingface_hub import HfApi, hf_hub_download
    api = HfApi(token=token)
    files = sorted(
        f for f in api.list_repo_files(space, repo_type="space")
        if f.startswith("data/decisions/day-")
    )
    latest = files[-n:]
    out = []
    for rf in latest:
        p = hf_hub_download(space, rf, repo_type="space", token=token,
                            cache_dir="/tmp/nomos-audit", force_download=True)
        with open(p) as fh:
            d = json.load(fh)
        out.append((rf, d))
    return out


def check_leakage(days):
    """For each bet, parse numeric signals from thesis, compare to resolved pnl/excess_return."""
    pairs = []
    num_re = re.compile(r"[+-]?\d+\.\d{2,4}")
    for _, d in days:
        for tid, log in (d.get("agents") or {}).items():
            for a in log.get("allocations", []):
                t = a.get("thesis") or a.get("rationale") or ""
                m = num_re.findall(t)
                if not m:
                    continue
                try:
                    thesis_num = float(m[0])
                except (ValueError, TypeError):
                    continue
                outcome = a.get("excess_return") or a.get("pnl_pct") or a.get("profit")
                if outcome is None:
                    continue
                try:
                    pairs.append((thesis_num, float(outcome)))
                except (ValueError, TypeError):
                    continue
    if len(pairs) < 5:
        return "ok", {"pairs": len(pairs), "note": "insufficient-bets"}
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    n = len(pairs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in pairs) / n
    sx = (sum((x - mx) ** 2 for x in xs) / n) ** 0.5
    sy = (sum((y - my) ** 2 for y in ys) / n) ** 0.5
    if sx == 0 or sy == 0:
        return "ok", {"pairs": n, "corr": None}
    corr = cov / (sx * sy)
    # Require n>=20 for a critical flag — small samples can spuriously hit |r|>0.8 by chance.
    # Under-20 bets can still warn at |r|>0.80 but not trip CRITICAL.
    if n < 20:
        sev = "warn" if abs(corr) > 0.80 else ("warn" if abs(corr) > 0.70 else "ok")
    else:
        sev = "critical" if abs(corr) > 0.80 else ("warn" if abs(corr) > 0.60 else "ok")
    return sev, {"pairs": n, "corr": round(corr, 3), "n_gate": (n >= 20)}


def check_source(days):
    c = Counter()
    for _, d in days:
        for log in (d.get("agents") or {}).values():
            for a in log.get("allocations", []):
                c[a.get("source", "direct")] += 1
    total = sum(c.values())
    forbidden_hits = sum(c[s] for s in c if s in FORBIDDEN_SOURCES)
    direct_ratio = c.get("direct", 0) / total if total else 0
    if forbidden_hits > 0:
        return "critical", {"counts": dict(c), "forbidden": forbidden_hits}
    if total and direct_ratio < 0.10:
        return "warn", {"counts": dict(c), "direct_ratio": round(direct_ratio, 3),
                        "note": "LLMs mostly silent, post-filter doing most work"}
    return "ok", {"counts": dict(c), "direct_ratio": round(direct_ratio, 3)}


def check_wr(days):
    """Per-agent rolling WR across last 20 bets in these days."""
    agent_bets = defaultdict(list)
    for _, d in days:
        for tid, log in (d.get("agents") or {}).items():
            for a in log.get("allocations", []):
                agent_bets[tid].append(1 if a.get("won") else 0)
    flags = []
    sev = "ok"
    for tid, bets in agent_bets.items():
        recent = bets[-20:]
        if len(recent) < 10:
            continue
        wr = sum(recent) / len(recent)
        if wr > 0.85:
            sev = "critical"; flags.append({"tid": tid, "wr": round(wr, 3), "n": len(recent)})
        elif wr > 0.75:
            if sev == "ok": sev = "warn"
            flags.append({"tid": tid, "wr": round(wr, 3), "n": len(recent)})
    return sev, {"flags": flags}


def check_lockstep(days, idx_key="game_idx", dir_key="category"):
    worst = 0
    per_day = []
    for rf, d in days:
        agents = d.get("agents") or {}
        if not agents:
            continue
        picks = {}
        for tid, log in agents.items():
            picks[tid] = [(a.get(idx_key), a.get(dir_key)) for a in log.get("allocations", [])]
        kc = Counter()
        total_bets = 0
        for pp in picks.values():
            total_bets += len(pp)
            for k in pp:
                kc[k] += 1
        n_agents = len(agents)
        shared_10 = sum(c for k, c in kc.items() if c >= 10)
        shared_all = sum(c for k, c in kc.items() if c >= n_agents)
        share_pct = shared_10 / total_bets if total_bets else 0
        per_day.append({"day": rf, "share_10": shared_10, "share_all": shared_all,
                        "total": total_bets, "share_pct": round(share_pct, 3)})
        worst = max(worst, share_pct)
    sev = "critical" if worst > 0.95 else ("warn" if worst > 0.80 else "ok")
    return sev, {"worst_share": round(worst, 3), "per_day": per_day}


def check_walkforward_pol(days, preds_path):
    """For POL, verify prior_key_used != fallback on sampled bets — lenient check."""
    if not preds_path.exists():
        return "warn", {"note": "no preds file", "path": str(preds_path)}
    try:
        with open(preds_path) as fh:
            preds = json.load(fh)
    except Exception as e:
        return "warn", {"note": f"preds load error: {e}"}
    if not isinstance(preds, dict):
        return "ok", {"note": "not keyed preds"}
    fallback_keys = sum(1 for v in preds.values()
                        if isinstance(v, dict) and v.get("prior_key_used") == "fallback")
    total = len(preds)
    if total == 0:
        return "warn", {"note": "empty preds"}
    ratio = fallback_keys / total
    sev = "critical" if ratio > 0.95 else ("warn" if ratio > 0.60 else "ok")
    return sev, {"fallback_ratio": round(ratio, 3), "total_preds": total,
                 "fallback_keys": fallback_keys}


def true_deploy_stats(days):
    deploys = []
    for _, d in days:
        for log in (d.get("agents") or {}).values():
            bb = log.get("bankroll_before", 100)
            stakes = sum(a.get("stake", 0) for a in log.get("allocations", []))
            if bb > 0:
                deploys.append(stakes / bb)
    if not deploys:
        return None
    deploys.sort()
    return {"avg": round(sum(deploys) / len(deploys), 3),
            "min": round(deploys[0], 3),
            "p50": round(deploys[len(deploys) // 2], 3),
            "max": round(deploys[-1], 3),
            "n": len(deploys)}


# ── PQTF-specific checks (schema: sessions[].positions[] w/ etf+option_type+strike)

def check_pqtf_lockstep(days):
    """Jaccard on (etf, option_type, round(strike,0), tte_days) across agents.

    Target: <0.50. >0.70 warn, >0.85 critical. PQTF agents trade single-leg +
    multi-leg option structures; positions on the same ETF/strike/type/tte are
    effectively the same bet."""
    all_jaccs = []
    per_day = []
    for rf, d in days:
        picks_by_agent = defaultdict(set)
        for s in d.get("sessions") or []:
            for pos in s.get("positions") or []:
                tid = pos.get("tid")
                if not tid: continue
                key = (pos.get("etf"), pos.get("option_type"),
                       round((pos.get("strike") or 0), 0), pos.get("tte_days"))
                picks_by_agent[tid].add(key)
        keys = list(picks_by_agent.keys())
        js = []
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a, b = picks_by_agent[keys[i]], picks_by_agent[keys[j]]
                if not a or not b: continue
                inter = len(a & b); union = len(a | b)
                if union: js.append(inter / union)
        if js:
            per_day.append({"day": rf, "n_agents": len(keys),
                            "mean": round(sum(js) / len(js), 3),
                            "max": round(max(js), 3)})
            all_jaccs.extend(js)
    if not all_jaccs:
        return "ok", {"note": "no-positions"}
    mean = sum(all_jaccs) / len(all_jaccs)
    mx = max(all_jaccs)
    sev = "critical" if mean > 0.85 else ("warn" if mean > 0.70 else "ok")
    return sev, {"mean": round(mean, 3), "max": round(mx, 3), "per_day": per_day}


def check_pqtf_risk(days):
    """VaR utilization + multi-leg ratio + stops-triggered rate."""
    vars_95 = []
    n_multi = 0
    n_single = 0
    n_stops = 0
    for _, d in days:
        for s in d.get("sessions") or []:
            r = s.get("risk") or {}
            if r.get("var_95_1d") is not None:
                vars_95.append(r["var_95_1d"])
            n_multi += r.get("n_multi_leg", 0) or 0
            n_single += r.get("n_single_leg", 0) or 0
            n_stops += r.get("stops_triggered", 0) or 0
    total = n_multi + n_single
    multi_ratio = n_multi / total if total else 0
    detail = {"sessions": sum(len(d.get("sessions") or []) for _, d in days),
              "avg_var_95": round(sum(vars_95) / len(vars_95), 2) if vars_95 else None,
              "max_var_95": round(max(vars_95), 2) if vars_95 else None,
              "multi_leg_ratio": round(multi_ratio, 3),
              "stops_triggered": n_stops}
    # PQTF with 0 multi-leg is broken (Phase 2 shipped spreads)
    if total > 0 and multi_ratio < 0.05:
        return "warn", {**detail, "note": "multi-leg spreads barely used — Phase 2 regression"}
    return "ok", detail


def run_audit():
    token = hf_token()
    if not token:
        print("[audit] NO HF_TOKEN_2 available", file=sys.stderr)
        sys.exit(1)
    now = datetime.datetime.utcnow()
    result = {"ts": now.isoformat() + "Z", "nba": {}, "pol": {}, "pqtf": {}, "alerts": []}

    for key, space, idx_key, dir_key in [
        ("nba", NBA_SPACE, "game", "category"),   # NBA uses "game" not "game_idx"
        ("pol", POL_SPACE, "event_idx", "direction"),
    ]:
        try:
            days = fetch_days(space, n=3, token=token)
        except Exception as e:
            result[key] = {"error": str(e)}
            continue
        checks = {}
        checks["leakage"], lk_d = check_leakage(days)
        checks["source"], src_d = check_source(days)
        checks["wr"], wr_d = check_wr(days)
        checks["lockstep"], ls_d = check_lockstep(days, idx_key, dir_key)
        if key == "pol":
            preds_path = REPO / "scripts" / "arena" / "hf-political-trading-floor" / "data" / "political-predictions.json"
            checks["walkforward"], wf_d = check_walkforward_pol(days, preds_path)
        else:
            wf_d = {"note": "nba-walkforward-check-not-implemented"}
            checks["walkforward"] = "ok"

        # collect bets, fleet
        n_bets = sum(len(log.get("allocations", [])) for _, d in days
                     for log in (d.get("agents") or {}).values())
        last = days[-1][1] if days else {}
        agents_last = last.get("agents") or {}
        banks = sorted(log.get("bankroll_after", 100) for log in agents_last.values())

        result[key] = {
            "space": space,
            "days_checked": [rf.split("/")[-1].replace(".json", "") for rf, _ in days],
            "bets": n_bets,
            "deploy": true_deploy_stats(days),
            "fleet_range": [banks[0], banks[-1]] if banks else None,
            "checks": checks,
            "details": {
                "leakage": lk_d, "source": src_d, "wr": wr_d,
                "lockstep": ls_d, "walkforward": wf_d,
            },
        }
        for chk, sev in checks.items():
            if sev in ("warn", "critical"):
                result["alerts"].append({"severity": sev, "floor": key, "check": chk,
                                         "detail": result[key]["details"].get(chk)})

    # ── PQTF audit (session-based schema, different shape from NBA/POL) ─────
    try:
        pq_days = fetch_days(PQTF_SPACE, n=3, token=token)
    except Exception as e:
        result["pqtf"] = {"error": str(e)}
    else:
        pq_checks = {}
        pq_checks["lockstep"], pq_ls = check_pqtf_lockstep(pq_days)
        pq_checks["risk"], pq_rk = check_pqtf_risk(pq_days)
        # fleet_range = agents_end map
        ends = {}
        for _, d in pq_days:
            ends.update(d.get("agents_end") or {})
        banks = sorted(ends.values()) if ends else []
        result["pqtf"] = {
            "space": PQTF_SPACE,
            "days_checked": [rf.split("/")[-1].replace(".json", "") for rf, _ in pq_days],
            "fleet_range": [banks[0], banks[-1]] if banks else None,
            "checks": pq_checks,
            "details": {"lockstep": pq_ls, "risk": pq_rk},
        }
        for chk, sev in pq_checks.items():
            if sev in ("warn", "critical"):
                result["alerts"].append({"severity": sev, "floor": "pqtf", "check": chk,
                                         "detail": result["pqtf"]["details"].get(chk)})

    stamp = now.strftime("%Y-%m-%dT%H%M")
    out_path = AUDIT_DIR / f"{stamp}.json"
    out_path.write_text(json.dumps(result, indent=2))

    if result["alerts"]:
        alert_path = AUDIT_DIR / "ALERT.json"
        current = []
        if alert_path.exists():
            try:
                current = json.loads(alert_path.read_text())
            except Exception:
                current = []
        for a in result["alerts"]:
            a["at"] = result["ts"]
        current.extend(result["alerts"])
        current = current[-100:]  # keep last 100
        alert_path.write_text(json.dumps(current, indent=2))

    print(f"[audit] wrote {out_path.name}  alerts={len(result['alerts'])}")
    for a in result["alerts"]:
        print(f"  {a['severity'].upper():8} {a['floor']}.{a['check']}: {a['detail']}")
    return result


if __name__ == "__main__":
    run_audit()
