#!/usr/bin/env python3
"""Rigorous TF validation — bootstrap CI95 + ECE + walk-forward.

For each of NBA / POL, pulls the decision archive directly from HF Hub
(bypasses local cache), computes:

  1. Bootstrap 95% CI for WR, Brier, PnL (1000 resamples).
  2. ECE (Expected Calibration Error) on 10 buckets — gold standard for
     "is the agent's confidence honest?"
  3. Reliability diagram — predicted_bucket vs actual_WR per bucket.
  4. Walk-forward Brier trajectory — Brier per rolling 20-day window
     so we can see "is the edge stable or degrading?"
  5. Per-agent rolling Brier — detect agent-level drift.
  6. Cross-TF statistical test — is POL Brier significantly lower than NBA?

Output:
  data/audit/rigorous-<ts>.json         machine-readable
  data/audit/rigorous-latest.md         human-readable report

Honest answer to "is our edge real or noise". No point estimates without CIs.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "data" / "audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SPACES = {
    "nba": "LBJLincoln26/nba-llm-trading-floor",
    "pol": "LBJLincoln26/political-llm-trading-floor",
}
HTTP_TIMEOUT = 15
WINDOW_DAYS = 30  # longer than scorecard -- for CI we need samples
BOOTSTRAP_N = 1000
ECE_BUCKETS = 10


def _hf_headers() -> dict:
    tok = os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN") or ""
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def _http_get(url: str) -> object | None:
    try:
        req = urllib.request.Request(url, headers=_hf_headers())
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return json.loads(r.read())
    except Exception:
        return None


def _recent_days(tf: str) -> list[dict]:
    repo = SPACES[tf]
    tree = _http_get(f"https://huggingface.co/api/spaces/{repo}/tree/main?recursive=true")
    if not isinstance(tree, list):
        return []
    paths = sorted(
        str(f.get("path"))
        for f in tree
        if isinstance(f, dict)
        and str(f.get("path", "")).startswith("data/decisions/day-")
        and str(f.get("path", "")).endswith(".json")
    )[-WINDOW_DAYS:]
    out = []
    for p in paths:
        d = _http_get(f"https://huggingface.co/spaces/{repo}/resolve/main/{urllib.parse.quote(p)}")
        if isinstance(d, dict):
            out.append(d)
    return out


def _extract_bets(days: list[dict]) -> list[dict]:
    """Returns flat list of bets: {day_idx, tid, conf, won, pnl}."""
    bets = []
    for d in days:
        day_idx = d.get("day_idx")
        for tid, a in (d.get("agents") or {}).items():
            for b in (a.get("allocations") or []):
                conf = b.get("confidence")
                won = b.get("won")
                pnl = b.get("profit") if b.get("profit") is not None else b.get("pnl")
                if won is None: continue
                try:
                    cv = float(conf) if conf is not None else None
                except Exception:
                    cv = None
                try:
                    pv = float(pnl) if pnl is not None else 0.0
                except Exception:
                    pv = 0.0
                bets.append({
                    "day_idx": day_idx, "tid": tid,
                    "conf": cv, "won": bool(won), "pnl": pv,
                })
    return bets


def _brier(bets: list[dict]) -> float | None:
    good = [(b["conf"], 1.0 if b["won"] else 0.0) for b in bets if b["conf"] is not None]
    if not good: return None
    return sum((c - o) ** 2 for c, o in good) / len(good)


def _wr(bets: list[dict]) -> float | None:
    if not bets: return None
    w = sum(1 for b in bets if b["won"])
    return w / len(bets)


def _pnl(bets: list[dict]) -> float:
    return sum(b["pnl"] for b in bets)


def _bootstrap_ci(bets: list[dict], stat_fn, n: int = BOOTSTRAP_N, alpha: float = 0.05) -> tuple[float | None, float | None, float | None]:
    """(lo, mid, hi) for the stat. Resample with replacement."""
    if not bets: return (None, None, None)
    import random
    rng = random.Random(42)
    sample_size = len(bets)
    vals = []
    for _ in range(n):
        resample = [bets[rng.randint(0, sample_size - 1)] for _ in range(sample_size)]
        v = stat_fn(resample)
        if v is not None: vals.append(v)
    if not vals: return (None, None, None)
    vals.sort()
    lo = vals[int(n * alpha / 2)]
    hi = vals[int(n * (1 - alpha / 2))]
    mid = stat_fn(bets)
    return (lo, mid, hi)


def _ece(bets: list[dict], n_buckets: int = ECE_BUCKETS) -> tuple[float | None, list[dict]]:
    """Expected Calibration Error + per-bucket breakdown."""
    good = [(b["conf"], 1 if b["won"] else 0) for b in bets if b["conf"] is not None and 0 <= b["conf"] <= 1]
    if not good: return (None, [])
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(n_buckets)]
    for c, o in good:
        idx = min(n_buckets - 1, int(c * n_buckets))
        buckets[idx].append((c, o))
    total = len(good)
    ece = 0.0
    table = []
    for i, bk in enumerate(buckets):
        if not bk: continue
        avg_conf = sum(c for c, _ in bk) / len(bk)
        avg_acc = sum(o for _, o in bk) / len(bk)
        weight = len(bk) / total
        ece += weight * abs(avg_conf - avg_acc)
        table.append({
            "bucket": f"{i/n_buckets:.1f}-{(i+1)/n_buckets:.1f}",
            "n": len(bk),
            "avg_predicted": round(avg_conf, 3),
            "avg_actual": round(avg_acc, 3),
            "gap": round(avg_acc - avg_conf, 3),
        })
    return (round(ece, 4), table)


def _walkforward(bets: list[dict], win: int = 20) -> list[dict]:
    """Rolling-window Brier: sort by day_idx, slide window of size `win`."""
    sorted_bets = sorted([b for b in bets if b["day_idx"] is not None and b["conf"] is not None],
                          key=lambda x: x["day_idx"])
    if len(sorted_bets) < win: return []
    out = []
    for i in range(0, len(sorted_bets) - win + 1, max(1, win // 4)):
        window = sorted_bets[i:i+win]
        b = _brier(window)
        first_day = window[0]["day_idx"]; last_day = window[-1]["day_idx"]
        out.append({"start_day": first_day, "end_day": last_day, "n": len(window), "brier": round(b, 4) if b else None})
    return out


def _two_sample_test(bets_a: list[dict], bets_b: list[dict]) -> dict:
    """Welch's t-test on per-bet (conf - outcome)^2 terms between two TFs.
    Returns {t, df, p_approx} — null hypothesis: equal Brier means."""
    def briers_arr(bs):
        return [(b["conf"] - (1 if b["won"] else 0)) ** 2 for b in bs if b["conf"] is not None]
    a, bv = briers_arr(bets_a), briers_arr(bets_b)
    if len(a) < 5 or len(bv) < 5: return {"t": None, "df": None, "p_approx": None}
    mean_a, mean_b = sum(a)/len(a), sum(bv)/len(bv)
    var_a = sum((x - mean_a)**2 for x in a) / (len(a) - 1)
    var_b = sum((x - mean_b)**2 for x in bv) / (len(bv) - 1)
    se = math.sqrt(var_a/len(a) + var_b/len(bv))
    if se == 0: return {"t": 0, "df": None, "p_approx": 1.0}
    t = (mean_a - mean_b) / se
    # Welch-Satterthwaite df
    df = (var_a/len(a) + var_b/len(bv)) ** 2 / ((var_a/len(a))**2 / (len(a)-1) + (var_b/len(bv))**2 / (len(bv)-1))
    # Rough two-sided p via normal approx for large df
    z = abs(t)
    # Abramowitz normal tail approximation
    p = 2 * 0.5 * math.erfc(z / math.sqrt(2))
    return {"t": round(t, 4), "df": round(df, 1), "p_two_sided": round(p, 5),
            "mean_brier_a": round(mean_a, 4), "mean_brier_b": round(mean_b, 4)}


def _per_agent(bets: list[dict]) -> list[dict]:
    by_tid: dict[str, list[dict]] = {}
    for b in bets: by_tid.setdefault(b["tid"], []).append(b)
    rows = []
    for tid, bs in by_tid.items():
        brier = _brier(bs)
        wr = _wr(bs)
        pnl = _pnl(bs)
        rows.append({"tid": tid, "n": len(bs), "wr": round(wr, 3) if wr else None,
                     "brier": round(brier, 4) if brier else None, "pnl": round(pnl, 2)})
    return sorted(rows, key=lambda r: -(r["pnl"] or 0))


def analyze(tf: str) -> dict:
    days = _recent_days(tf)
    if not days: return {"tf": tf, "ok": False, "reason": "no day files"}
    bets = _extract_bets(days)
    if not bets: return {"tf": tf, "ok": False, "reason": "no confident bets"}

    brier_lo, brier_mid, brier_hi = _bootstrap_ci(bets, _brier)
    wr_lo, wr_mid, wr_hi = _bootstrap_ci(bets, _wr)
    pnl_lo, pnl_mid, pnl_hi = _bootstrap_ci(bets, _pnl)
    ece, ece_table = _ece(bets)
    wf = _walkforward(bets)

    return {
        "tf": tf, "ok": True,
        "n_days": len(days), "n_bets": len(bets),
        "brier": {"lo": brier_lo, "mid": brier_mid, "hi": brier_hi},
        "wr": {"lo": wr_lo, "mid": wr_mid, "hi": wr_hi},
        "pnl": {"lo": pnl_lo, "mid": pnl_mid, "hi": pnl_hi},
        "ece": ece, "reliability": ece_table,
        "walk_forward": wf,
        "per_agent": _per_agent(bets),
        "_bets": bets,  # keep for cross-TF test
    }


def _md(results: dict) -> str:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# TF Rigorous Validation — {now}",
             "",
             "Bootstrap 95% CI (1000 resamples), ECE calibration, walk-forward Brier, per-agent breakdown.",
             ""]
    for tf, r in results["tfs"].items():
        if not r.get("ok"):
            lines.append(f"## {tf.upper()} — SKIP ({r.get('reason')})"); lines.append(""); continue
        lines.append(f"## {tf.upper()}")
        lines.append(f"- window: last {r['n_days']} days, {r['n_bets']} confident bets")
        b = r["brier"]
        lines.append(f"- **Brier**: {b['mid']:.4f}  95% CI [{b['lo']:.4f}, {b['hi']:.4f}]")
        wr = r["wr"]
        lines.append(f"- **Win rate**: {wr['mid']:.2%}  95% CI [{wr['lo']:.2%}, {wr['hi']:.2%}]")
        pnl = r["pnl"]
        lines.append(f"- **PnL**: ${pnl['mid']:+.2f}  95% CI [${pnl['lo']:+.2f}, ${pnl['hi']:+.2f}]")
        lines.append(f"- **ECE**: {r['ece']}  (0=perfectly calibrated; random ~0.25)")
        lines.append("")
        lines.append("### Reliability (predicted vs actual per bucket)")
        lines.append("| bucket | n | predicted | actual | gap |")
        lines.append("|---|---:|---:|---:|---:|")
        for row in r["reliability"]:
            lines.append(f"| {row['bucket']} | {row['n']} | {row['avg_predicted']:.3f} | {row['avg_actual']:.3f} | {row['gap']:+.3f} |")
        lines.append("")
        lines.append("### Walk-forward Brier trajectory (rolling windows)")
        lines.append("| window | n | brier |")
        lines.append("|---|---:|---:|")
        for w in r["walk_forward"]:
            lines.append(f"| d{w['start_day']}-{w['end_day']} | {w['n']} | {w['brier']} |")
        lines.append("")
        lines.append("### Per-agent (top 5 + bottom 3)")
        lines.append("| agent | bets | WR | Brier | PnL |")
        lines.append("|---|---:|---:|---:|---:|")
        agents = r["per_agent"]
        for a in agents[:5] + agents[-3:]:
            wr_s = f"{a['wr']:.2%}" if a['wr'] is not None else "-"
            br_s = f"{a['brier']}" if a['brier'] is not None else "-"
            lines.append(f"| `{a['tid']}` | {a['n']} | {wr_s} | {br_s} | ${a['pnl']:+.2f} |")
        lines.append("")
    # Cross-TF stat test
    tfa, tfb = "nba", "pol"
    if results["tfs"][tfa].get("ok") and results["tfs"][tfb].get("ok"):
        test = _two_sample_test(results["tfs"][tfa]["_bets"], results["tfs"][tfb]["_bets"])
        lines.append("## Cross-TF Brier comparison (Welch's t-test)")
        lines.append(f"- NBA mean Brier: {test.get('mean_brier_a')}")
        lines.append(f"- POL mean Brier: {test.get('mean_brier_b')}")
        lines.append(f"- t = {test.get('t')}, df ≈ {test.get('df')}, p (two-sided) ≈ {test.get('p_two_sided')}")
        if test.get("p_two_sided") is not None:
            sig = "yes (p<0.05)" if test["p_two_sided"] < 0.05 else "no (p>=0.05)"
            lines.append(f"- statistically significant at 95%: **{sig}**")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    results = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(), "tfs": {}}
    for tf in SPACES: results["tfs"][tf] = analyze(tf)

    # Strip _bets before saving (too big)
    saveable = {"ts": results["ts"], "tfs": {}}
    for tf, r in results["tfs"].items():
        rr = {k: v for k, v in r.items() if not k.startswith("_")}
        saveable["tfs"][tf] = rr

    # Attach cross-TF test result
    tfa, tfb = "nba", "pol"
    if results["tfs"][tfa].get("ok") and results["tfs"][tfb].get("ok"):
        saveable["cross_tf_test"] = _two_sample_test(
            results["tfs"][tfa]["_bets"], results["tfs"][tfb]["_bets"]
        )

    ts_str = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%MZ")
    (OUT_DIR / f"rigorous-{ts_str}.json").write_text(json.dumps(saveable, indent=2, default=str))
    (OUT_DIR / "rigorous-latest.md").write_text(_md(results))
    # Fixed-name latest JSON for the dashboard to fetch — pairs with the MD.
    (OUT_DIR / "rigorous-latest.json").write_text(json.dumps(saveable, indent=2, default=str))
    print(f"rigorous validation done: {ts_str}")
    for tf, r in results["tfs"].items():
        if r.get("ok"):
            b = r["brier"]
            print(f"  {tf.upper()}: n_bets={r['n_bets']} brier={b['mid']:.4f} CI[{b['lo']:.4f},{b['hi']:.4f}] ECE={r['ece']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
