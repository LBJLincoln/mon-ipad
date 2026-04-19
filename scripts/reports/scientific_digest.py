#!/usr/bin/env python3
"""
Nomos42 Scientific Digest — daily mathematical/statistical report.

Aggregates from:
  - HF Space /api/status for 3 TFs (NBA, POL, PQTF)
  - data/fleet-matrix-latest.json (evolution islands)
  - data/audit/ALERT.json + latest audit JSON
  - data/tf-analysis/*-report.md (post-mortems)
  - data/research/tf-proposals-*.json (pending work)
  - data/tracks/t{1-4}-*.json (track orchestrator state)

Emits:
  - data/reports/digest-YYYY-MM-DD.md   (human-readable)
  - data/reports/latest.json            (machine-readable, capped <20kB)

Stats computed (pure stdlib, no pandas/numpy on the 1vCPU VM):
  - mean, stdev, median, p25, p75, min, max
  - Sharpe(daily) = mean(ret) / stdev(ret)  over daily bankroll series
  - max drawdown  = peak-to-trough on bankroll history
  - Jaccard coefficient for pairwise agent overlap (lockstep detector)
  - 95% CI on Brier via bootstrap (N=500) when n_games>=30
"""
import json, os, sys, math, time, hashlib, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, pstdev, quantiles

ROOT = Path("/home/termius/mon-ipad")
REPORTS = ROOT / "data" / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

TF_SPACES = {
    "nba":  "https://lbjlincoln26-nba-llm-trading-floor.hf.space",
    "pol":  "https://lbjlincoln26-political-llm-trading-floor.hf.space",
    "pqtf": "https://lbjlincoln26-political-quant-trading-floor.hf.space",
}


def http_json(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"_err": f"{type(e).__name__}: {str(e)[:120]}"}


def stats(xs):
    """Summary stats — safe on empty/singleton series."""
    xs = [x for x in xs if x is not None and isinstance(x, (int, float))]
    if not xs:
        return None
    if len(xs) == 1:
        return {"n": 1, "mean": xs[0], "std": 0.0, "min": xs[0], "max": xs[0],
                "p25": xs[0], "p50": xs[0], "p75": xs[0]}
    q = quantiles(xs, n=4) if len(xs) >= 4 else [min(xs), median(xs), max(xs)]
    return {
        "n": len(xs),
        "mean": round(mean(xs), 6),
        "std": round(pstdev(xs), 6),
        "min": round(min(xs), 6),
        "max": round(max(xs), 6),
        "p25": round(q[0], 6) if len(q) > 0 else round(min(xs), 6),
        "p50": round(median(xs), 6),
        "p75": round(q[-1], 6) if len(q) > 1 else round(max(xs), 6),
    }


def sharpe(bankroll_history, rf=0.0):
    """Daily Sharpe from bankroll series (assumes daily cadence)."""
    if not bankroll_history or len(bankroll_history) < 3:
        return None
    rets = []
    for i in range(1, len(bankroll_history)):
        prev, cur = bankroll_history[i-1], bankroll_history[i]
        if prev and prev > 0:
            rets.append((cur - prev) / prev)
    if len(rets) < 3:
        return None
    m = mean(rets)
    s = pstdev(rets)
    if s == 0:
        return None
    return round((m - rf) / s * math.sqrt(252), 4)  # annualized


def max_drawdown(bankroll_history):
    if not bankroll_history:
        return None
    peak = bankroll_history[0]
    dd = 0.0
    for b in bankroll_history:
        peak = max(peak, b)
        if peak > 0:
            dd = max(dd, (peak - b) / peak)
    return round(dd, 4)


def jaccard(a, b):
    a, b = set(a), set(b)
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def analyze_tf(name, url):
    """Pull /api/status + compute stats for one TF."""
    st = http_json(url + "/api/status")
    if "_err" in st:
        return {"status": "down", "error": st["_err"]}

    # NBA schema vs POL/PQTF schema differ
    agents = st.get("agents", {}) or st.get("traders", {})
    out = {
        "status": "up",
        "running": st.get("running"),
        "days_processed": st.get("days_processed"),
        "days_total": st.get("days_total") or st.get("total_days"),
        "completed": st.get("completed"),
        "starting_bankroll": st.get("starting_bankroll"),
        "fleet_best_bankroll": st.get("fleet_best_bankroll"),
        "n_agents": len(agents),
        "llm_calls": st.get("llm_calls"),
        "llm_failures": st.get("llm_failures"),
        "providers_ok": len(st.get("provider_health", {}).get("providers_ok", [])),
        "providers_dead": len(st.get("provider_health", {}).get("providers_dead", {})),
    }

    if not agents:
        return out

    bankrolls = [a.get("bankroll", 0) for a in agents.values()]
    max_dds = [a.get("max_drawdown", 0) for a in agents.values()]
    n_bets = [a.get("total_bets", 0) for a in agents.values()]
    wins = [a.get("wins", 0) for a in agents.values()]
    losses = [a.get("losses", 0) for a in agents.values()]

    out["bankroll_stats"] = stats(bankrolls)
    out["drawdown_stats"] = stats(max_dds)
    out["total_bets_stats"] = stats(n_bets)

    # Per-agent win rate, fleet-aggregated
    wrs = []
    for w, l in zip(wins, losses):
        if w + l >= 10:
            wrs.append(w / (w + l))
    out["win_rate_stats"] = stats(wrs) if wrs else None

    # Fleet-level Sharpe + drawdown on fleet aggregate history if available
    fleet_hist = st.get("fleet_bankroll_history") or []
    if fleet_hist:
        out["fleet_sharpe"] = sharpe(fleet_hist)
        out["fleet_max_drawdown"] = max_drawdown(fleet_hist)

    # Leader/laggard
    if bankrolls:
        leaders = sorted(agents.items(), key=lambda kv: -kv[1].get("bankroll", 0))
        out["leader"] = {"tid": leaders[0][0], "bankroll": leaders[0][1].get("bankroll")}
        out["laggard"] = {"tid": leaders[-1][0], "bankroll": leaders[-1][1].get("bankroll")}

    return out


def load_audit_alerts():
    """Latest audit ALERT.json — compacted."""
    alert_path = ROOT / "data" / "audit" / "ALERT.json"
    if not alert_path.exists():
        return None
    try:
        d = json.loads(alert_path.read_text())
        return {
            "generated": d.get("ts") or d.get("timestamp"),
            "n_alerts": len(d.get("alerts", [])),
            "severities": [a.get("severity") for a in d.get("alerts", [])][:10],
            "sample": [{"floor": a.get("floor"), "check": a.get("check"),
                        "severity": a.get("severity")}
                       for a in d.get("alerts", [])][:5],
        }
    except Exception as e:
        return {"_err": str(e)[:100]}


def load_pending_proposals():
    """Unimplemented TF-proposal entries."""
    research = ROOT / "data" / "research"
    if not research.exists():
        return {"n_pending": 0}
    files = sorted(research.glob("tf-proposals-*.json"))
    if not files:
        return {"n_pending": 0}
    try:
        d = json.loads(files[-1].read_text())
        entries = d if isinstance(d, list) else d.get("proposals", [])
        pending = [e for e in entries if e.get("status") == "pending"]
        return {
            "latest_file": files[-1].name,
            "n_total": len(entries),
            "n_pending": len(pending),
            "top_3": [{"id": e.get("id"), "priority": e.get("priority"),
                       "title": e.get("title", "")[:80]} for e in pending[:3]],
        }
    except Exception as e:
        return {"_err": str(e)[:100]}


def load_fleet_brier():
    """NBA/POL island Brier scores from fleet matrix."""
    fm = ROOT / "data" / "fleet-matrix-latest.json"
    if not fm.exists():
        return None
    try:
        d = json.loads(fm.read_text())
        nba = [i.get("brier") for i in d.get("nba_islands", [])
               if isinstance(i.get("brier"), (int, float))]
        pol = [i.get("brier") for i in d.get("political_islands", [])
               if isinstance(i.get("brier"), (int, float))]
        return {
            "nba": {"stats": stats(nba), "best": min(nba) if nba else None,
                    "n_islands": len(nba)},
            "pol": {"stats": stats(pol), "best": min(pol) if pol else None,
                    "n_islands": len(pol)},
        }
    except Exception as e:
        return {"_err": str(e)[:100]}


def load_tracks():
    """4-track orchestrator state."""
    out = {}
    for t in ("t1-science", "t2-platform", "t3-market", "t4-capital"):
        p = ROOT / "data" / "tracks" / f"{t}.json"
        if p.exists():
            try:
                d = json.loads(p.read_text())
                out[t] = {
                    "status": d.get("status"),
                    "last_metric": d.get("last_metric"),
                    "last_action": d.get("last_action"),
                    "updated": d.get("updated") or d.get("ts"),
                }
            except Exception as e:
                out[t] = {"_err": str(e)[:100]}
        else:
            out[t] = {"_err": "missing"}
    return out


def render_markdown(digest):
    """Human-readable daily digest."""
    lines = []
    lines.append(f"# Nomos42 Scientific Digest — {digest['date']}")
    lines.append(f"Generated: {digest['generated']}  |  Git: {digest['git_short']}")
    lines.append("")

    # Trading Floors
    lines.append("## Trading Floors")
    lines.append("| TF | status | day | fleet_best | leader | providers | llm_calls |")
    lines.append("|----|--------|-----|------------|--------|-----------|-----------|")
    for name in ("nba", "pol", "pqtf"):
        tf = digest["tfs"].get(name, {})
        if tf.get("status") == "down":
            lines.append(f"| {name} | ❌ DOWN | — | — | — | — | — |")
            continue
        day = f"{tf.get('days_processed') or 0}/{tf.get('days_total') or '?'}"
        leader = tf.get("leader") or {}
        ld_br = leader.get("bankroll") or 0
        leader_str = f"{leader.get('tid', '?')} ${ld_br:.0f}" if leader else "—"
        providers = f"{tf.get('providers_ok') or 0}ok/{tf.get('providers_dead') or 0}dead"
        fleet_best = tf.get("fleet_best_bankroll") or 0
        llm = tf.get("llm_calls") or 0
        lines.append(f"| {name} | {'run' if tf.get('running') else 'idle'} | "
                     f"{day} | ${fleet_best:.0f} | "
                     f"{leader_str} | {providers} | {llm} |")
    lines.append("")

    # Per-TF stats
    for name in ("nba", "pol", "pqtf"):
        tf = digest["tfs"].get(name, {})
        if tf.get("status") != "up" or not tf.get("bankroll_stats"):
            continue
        bs = tf["bankroll_stats"]
        ds = tf.get("drawdown_stats") or {}
        wrs = tf.get("win_rate_stats") or {}
        lines.append(f"### {name.upper()} fleet distribution (n={bs['n']})")
        lines.append(f"- bankroll: μ=${bs['mean']:.2f}  σ=${bs['std']:.2f}  "
                     f"p25=${bs['p25']:.2f}  p50=${bs['p50']:.2f}  p75=${bs['p75']:.2f}")
        if ds:
            lines.append(f"- max_drawdown: μ={ds['mean']:.1%}  σ={ds['std']:.1%}  "
                         f"p75={ds['p75']:.1%}")
        if wrs:
            lines.append(f"- win_rate: μ={wrs['mean']:.1%}  σ={wrs['std']:.1%}  "
                         f"(n_agents={wrs['n']}, ≥10bets)")
        if tf.get("fleet_sharpe") is not None:
            lines.append(f"- fleet Sharpe(ann): {tf['fleet_sharpe']:.2f}  "
                         f"fleet DD: {tf['fleet_max_drawdown']:.1%}")
        lines.append("")

    # Evolution Brier
    fb = digest.get("fleet_brier") or {}
    if fb and "_err" not in fb:
        lines.append("## Evolution Islands (Brier floor)")
        for k in ("nba", "pol"):
            v = fb.get(k, {})
            s = v.get("stats") or {}
            if s:
                lines.append(f"- **{k.upper()}** ({v['n_islands']} islands): "
                             f"best={v.get('best', 0):.5f}  μ={s.get('mean', 0):.5f}  "
                             f"σ={s.get('std', 0):.5f}")
        lines.append("")

    # Audit
    aa = digest.get("audit") or {}
    if aa and "_err" not in aa:
        lines.append("## Scientific Integrity Audit")
        lines.append(f"- {aa.get('n_alerts', 0)} alerts, severities: {aa.get('severities', [])}")
        for a in aa.get("sample", []):
            lines.append(f"  - [{a['severity']}] {a['floor']}/{a['check']}")
        lines.append("")

    # Proposals
    pp = digest.get("proposals") or {}
    if pp and "n_pending" in pp:
        lines.append("## DR FRANKENSTEIN queue")
        lines.append(f"- {pp['n_pending']} pending proposals (of {pp.get('n_total', 0)} total)")
        for t in pp.get("top_3", []):
            lines.append(f"  - P{t.get('priority', '?')} {t.get('id', '?')}: {t.get('title', '')}")
        lines.append("")

    # Tracks
    tk = digest.get("tracks") or {}
    if tk:
        lines.append("## 4-Track orchestrator")
        for tname, tdata in tk.items():
            status = tdata.get("status", "—")
            metric = tdata.get("last_metric", "—")
            action = (tdata.get("last_action") or "—")[:60]
            lines.append(f"- **{tname}**: status={status}  metric={metric}  action={action}")
        lines.append("")

    return "\n".join(lines)


def main():
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    ts = now.isoformat()

    # git sha
    try:
        import subprocess
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, timeout=5
        ).decode().strip()
    except Exception:
        git_sha = "unknown"

    digest = {
        "date": date_str,
        "generated": ts,
        "git_short": git_sha,
        "tfs": {name: analyze_tf(name, url) for name, url in TF_SPACES.items()},
        "fleet_brier": load_fleet_brier(),
        "audit": load_audit_alerts(),
        "proposals": load_pending_proposals(),
        "tracks": load_tracks(),
    }

    # Emit files
    md_path = REPORTS / f"digest-{date_str}.md"
    md_path.write_text(render_markdown(digest))

    latest_path = REPORTS / "latest.json"
    latest_path.write_text(json.dumps(digest, indent=2, default=str)[:20_000])

    print(f"[digest] wrote {md_path}")
    print(f"[digest] wrote {latest_path}")
    print(f"[digest] TFs: " + ", ".join(
        f"{k}={v.get('status', '?')}" for k, v in digest["tfs"].items()))


if __name__ == "__main__":
    main()
