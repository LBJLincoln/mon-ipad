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
    out = [f"# TF Trajectory Flash — {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
           f"Source: {latest.name}", ""]
    for tf, r in (d.get("tfs") or {}).items():
        if not r.get("ok"): continue
        wf = r.get("walk_forward") or []
        briers = [w["brier"] for w in wf if w.get("brier") is not None]
        if len(briers) < 6:
            out.append(f"## {tf.upper()}  _(need >=6 walk-forward windows, have {len(briers)})_"); out.append(""); continue
        old_mean = sum(briers[:3]) / 3
        new_mean = sum(briers[-3:]) / 3
        delta = new_mean - old_mean
        verdict = "IMPROVING" if delta < -0.01 else ("DEGRADING" if delta > 0.01 else "FLAT")
        headline_brier = r.get("brier", {}).get("mid")
        out.append(f"## {tf.upper()}")
        out.append(f"- 30-day aggregate Brier: **{headline_brier:.4f}** (lagging indicator)")
        out.append(f"- First 3 walk-forward windows (oldest): {old_mean:.4f}")
        out.append(f"- Last 3 walk-forward windows (newest): **{new_mean:.4f}**")
        out.append(f"- Δ (recent minus old) = **{delta:+.4f}**  →  **{verdict}**")
        out.append(f"- Single most recent window Brier: **{briers[-1]:.4f}**")
        out.append(f"- All-time best window Brier: **{min(briers):.4f}**")
        out.append("")
    outp = AUDIT / "trajectory-latest.md"
    outp.write_text("\n".join(out))
    print(f"trajectory written: {outp}")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
