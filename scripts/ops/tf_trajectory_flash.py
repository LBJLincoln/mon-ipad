#!/usr/bin/env python3
"""Quick trajectory read — is Brier IMPROVING or DEGRADING over time?

Compares first 3 walk-forward windows against last 3 (recency-weighted).
Writes data/audit/trajectory-latest.md with verdict per TF.
"""
import datetime as dt
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUDIT = REPO / "data" / "audit"


def main() -> int:
    latest = None
    for f in sorted(AUDIT.glob("rigorous-*.json"), reverse=True):
        latest = f; break
    if not latest:
        print("no rigorous data"); return 1
    d = json.loads(latest.read_text())
    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    out = [f"# TF Trajectory Flash — {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
           f"Source: {latest.name}", ""]
    payload: dict = {"ts": now_iso, "source": latest.name, "tfs": {}}
    for tf, r in (d.get("tfs") or {}).items():
        if not r.get("ok"):
            payload["tfs"][tf] = {"ok": False, "reason": r.get("reason")}
            continue
        wf = r.get("walk_forward") or []
        briers = [w["brier"] for w in wf if w.get("brier") is not None]
        if len(briers) < 6:
            out.append(f"## {tf.upper()}  _(need >=6 walk-forward windows, have {len(briers)})_"); out.append("")
            payload["tfs"][tf] = {"ok": False,
                                  "reason": f"need >=6 wf windows, have {len(briers)}",
                                  "brier_series": wf}
            continue
        old_mean = sum(briers[:3]) / 3
        new_mean = sum(briers[-3:]) / 3
        delta = new_mean - old_mean
        # stderr-aware threshold replaces the fixed 0.01 (per PLUMBER 2026-05-01)
        n = len(briers)
        mean_b = sum(briers) / n
        var_b = sum((b - mean_b) ** 2 for b in briers) / max(1, n - 1)
        stderr = (var_b / 3) ** 0.5  # 3 windows averaged in each side
        threshold = max(0.005, 1.96 * stderr)
        verdict = "IMPROVING" if delta < -threshold else ("DEGRADING" if delta > threshold else "FLAT")
        headline_brier = r.get("brier", {}).get("mid")
        # least-squares slope per window
        xs = list(range(n))
        x_mean = sum(xs) / n
        slope_num = sum((x - x_mean) * (b - mean_b) for x, b in zip(xs, briers))
        slope_den = sum((x - x_mean) ** 2 for x in xs) or 1.0
        slope = slope_num / slope_den
        out.append(f"## {tf.upper()}")
        out.append(f"- 30-day aggregate Brier: **{headline_brier:.4f}** (lagging indicator)")
        out.append(f"- First 3 walk-forward windows (oldest): {old_mean:.4f}")
        out.append(f"- Last 3 walk-forward windows (newest): **{new_mean:.4f}**")
        out.append(f"- Δ (recent − old) = **{delta:+.4f}** vs ±{threshold:.4f} threshold → **{verdict}**")
        out.append(f"- Single most recent window Brier: **{briers[-1]:.4f}**")
        out.append(f"- All-time best window Brier: **{min(briers):.4f}**")
        out.append(f"- Linear slope (Brier per window): **{slope:+.5f}**")
        out.append("")
        payload["tfs"][tf] = {
            "ok": True,
            "verdict": verdict,
            "old_mean": round(old_mean, 5),
            "new_mean": round(new_mean, 5),
            "delta": round(delta, 5),
            "threshold": round(threshold, 5),
            "slope_per_window": round(slope, 5),
            "headline_brier": headline_brier,
            "best_brier": round(min(briers), 5),
            "latest_brier": round(briers[-1], 5),
            "brier_series": wf,  # full series for the dashboard chart
        }
    (AUDIT / "trajectory-latest.md").write_text("\n".join(out))
    # Pair the markdown with JSON for <TrajectoryRibbon> on the dashboard.
    (AUDIT / "trajectory-latest.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"trajectory written: {AUDIT/'trajectory-latest.md'} + .json")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
