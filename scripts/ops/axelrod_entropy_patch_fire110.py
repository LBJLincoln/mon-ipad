#!/usr/bin/env python3
"""
Axelrod-2026 fire-110 patch: society entropy + lockstep alert in CK[D] broadcast.

Applies to:
  scripts/arena/hf-llm-trading-floor/app.py      (NBA)
  scripts/arena/hf-political-trading-floor/app.py (Political)

Changes (at parity in both files):
  1. build_common_knowledge_block: add entropy H=-Sp*log(p) to CONSENSUS PICKS
     header, add LOCKSTEP ALERT block when >=60% agents chose the same pick.
  2. write_axelrod_log: compute society_entropy from cpd, add to each row
     (paper primary dataset - enables time-series diversity analysis).

Run from mon-ipad root: python3 scripts/ops/axelrod_entropy_patch_fire110.py
"""
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NBA_PATH = REPO_ROOT / "scripts/arena/hf-llm-trading-floor/app.py"
POL_PATH = REPO_ROOT / "scripts/arena/hf-political-trading-floor/app.py"

# -- PATCH 1: CONSENSUS PICKS block (identical in both NBA and POL) ----------
CK_OLD = (
    '        if _pick_ctr:\n'
    '            lines.append(f"\\nCONSENSUS PICKS on {_yesterday} (Axelrod-2026: cite your diverge/agree stance):")\n'
    '            for _pk2, _cnt2 in sorted(_pick_ctr.items(), key=lambda x: -x[1])[:8]:\n'
    '                _pct2 = _cnt2 / max(_n_active, 1) * 100\n'
    '                _stk2 = _stake_ctr.get(_pk2, 0.0)\n'
    '                _pnl2 = _pnl_ctr.get(_pk2, 0.0)\n'
    '                _wr2 = _win_ctr.get(_pk2, 0) / max(_pick_ctr.get(_pk2, 1), 1) * 100\n'
    "                lines.append(f\"  {_cnt2}/{_n_active} ({_pct2:.0f}%) stake=${_stk2:.0f} pnl={_pnl2:+.1f} wr={_wr2:.0f}%: {_pk2}\")\n"
    "        # Axelrod-2026 fire-85: surface each peer's ck_consensus_stance from yesterday."
)

CK_NEW = (
    '        if _pick_ctr:\n'
    '            # Axelrod-2026 fire-110: society entropy H=-Sp*log(p) for paper diversity metric.\n'
    '            # Low entropy = concentrated picks (groupthink risk); high = well-dispersed.\n'
    '            _total_picks_all = sum(_pick_ctr.values())\n'
    '            _ck_entropy = -sum(\n'
    '                (_c / _total_picks_all) * math.log(_c / _total_picks_all + 1e-12)\n'
    '                for _c in _pick_ctr.values()\n'
    '            )\n'
    '            _lockstep_n = max(2, int(_n_active * 0.6))  # >=60% threshold (approx 10/17)\n'
    '            lines.append(f"\\nCONSENSUS PICKS on {_yesterday} (entropy={_ck_entropy:.3f} nats | Axelrod-2026: cite your diverge/agree stance):")\n'
    '            for _pk2, _cnt2 in sorted(_pick_ctr.items(), key=lambda x: -x[1])[:8]:\n'
    '                _pct2 = _cnt2 / max(_n_active, 1) * 100\n'
    '                _stk2 = _stake_ctr.get(_pk2, 0.0)\n'
    '                _pnl2 = _pnl_ctr.get(_pk2, 0.0)\n'
    '                _wr2 = _win_ctr.get(_pk2, 0) / max(_pick_ctr.get(_pk2, 1), 1) * 100\n'
    "                lines.append(f\"  {_cnt2}/{_n_active} ({_pct2:.0f}%) stake=${_stk2:.0f} pnl={_pnl2:+.1f} wr={_wr2:.0f}%: {_pk2}\")\n"
    '            _lockstep_picks = [(pk, cnt) for pk, cnt in _pick_ctr.items() if cnt >= _lockstep_n]\n'
    '            if _lockstep_picks:\n'
    '                lines.append(f"  LOCKSTEP ALERT: {len(_lockstep_picks)} pick(s) chosen by >={_lockstep_n}/{_n_active} agents (low entropy):")\n'
    '                for _lpk, _lcnt in sorted(_lockstep_picks, key=lambda x: -x[1]):\n'
    '                    lines.append(f"    {_lcnt}/{_n_active}: {_lpk}")\n'
    '                lines.append(f"  -> Mech B: bottom-3 by 7d delta received archetype rotation (diversity enforcement).")\n'
    "        # Axelrod-2026 fire-85: surface each peer's ck_consensus_stance from yesterday."
)

# -- PATCH 2a: write_axelrod_log cpd block — NBA (uses 'game' key) -----------
NBA_CPD_OLD = (
    '            for _d2 in (_dlog2.get("allocations", []) if _dlog2 else []):\n'
    '                _g2 = _d2.get("game", "")\n'
    '                if _g2:\n'
    '                    _cpd[_g2] = _cpd.get(_g2, 0) + 1\n'
    '        for tid, ts in state.items():\n'
    '            logs = agent_logs.get(tid, [])\n'
    '            day_log = next((l for l in reversed(logs) if l.get("date") == day_date), None)'
)

NBA_CPD_NEW = (
    '            for _d2 in (_dlog2.get("allocations", []) if _dlog2 else []):\n'
    '                _g2 = _d2.get("game", "")\n'
    '                if _g2:\n'
    '                    _cpd[_g2] = _cpd.get(_g2, 0) + 1\n'
    '        _cpd_total = sum(_cpd.values()) or 1\n'
    '        _society_entropy = round(-sum((_c/_cpd_total)*math.log(_c/_cpd_total+1e-12) for _c in _cpd.values()), 6) if _cpd else 0.0\n'
    '        for tid, ts in state.items():\n'
    '            logs = agent_logs.get(tid, [])\n'
    '            day_log = next((l for l in reversed(logs) if l.get("date") == day_date), None)'
)

# -- PATCH 2b: write_axelrod_log cpd block — POL (uses 'ticker' key) ---------
POL_CPD_OLD = (
    '            for _d2 in (_dlog2.get("allocations", []) if _dlog2 else []):\n'
    '                _t2 = _d2.get("ticker", "")\n'
    '                if _t2:\n'
    '                    _cpd[_t2] = _cpd.get(_t2, 0) + 1\n'
    '        for tid, ts in state.items():\n'
    '            logs = agent_logs.get(tid, [])'
)

POL_CPD_NEW = (
    '            for _d2 in (_dlog2.get("allocations", []) if _dlog2 else []):\n'
    '                _t2 = _d2.get("ticker", "")\n'
    '                if _t2:\n'
    '                    _cpd[_t2] = _cpd.get(_t2, 0) + 1\n'
    '        _cpd_total = sum(_cpd.values()) or 1\n'
    '        _society_entropy = round(-sum((_c/_cpd_total)*math.log(_c/_cpd_total+1e-12) for _c in _cpd.values()), 6) if _cpd else 0.0\n'
    '        for tid, ts in state.items():\n'
    '            logs = agent_logs.get(tid, [])'
)

# -- PATCH 3a: rows society_entropy field — NBA --------------------------------
NBA_ROW_OLD = (
    '                "fleet": "nba",\n'
    '                "provider": TRADERS.get(tid, {}).get("provider", "unknown"),\n'
    '                "trailing_7d_delta": round(compute_trailing_delta(tid, state, agent_logs, 7), 2),\n'
    '                "dmad_prefix_type": _parse_dmad_prefix(day_log.get("day_strategy", "") if day_log else ""),\n'
    '                "cash_held_pct": round(float((day_log.get("cash_held_pct") or 0) if day_log else 0), 4),\n'
    '            })'
)

NBA_ROW_NEW = (
    '                "fleet": "nba",\n'
    '                "provider": TRADERS.get(tid, {}).get("provider", "unknown"),\n'
    '                "trailing_7d_delta": round(compute_trailing_delta(tid, state, agent_logs, 7), 2),\n'
    '                "dmad_prefix_type": _parse_dmad_prefix(day_log.get("day_strategy", "") if day_log else ""),\n'
    '                "cash_held_pct": round(float((day_log.get("cash_held_pct") or 0) if day_log else 0), 4),\n'
    '                "society_entropy": _society_entropy,\n'
    '            })'
)

# -- PATCH 3b: rows society_entropy field — POL --------------------------------
POL_ROW_OLD = (
    '                "fleet": "political",\n'
    '                "provider": TRADERS.get(tid, {}).get("provider", "unknown"),\n'
    '                "trailing_7d_delta": round(compute_trailing_delta(tid, state, agent_logs, 7), 2),\n'
    '                "dmad_prefix_type": _parse_dmad_prefix(day_log.get("day_strategy", "") if day_log else ""),\n'
    '                "cash_held_pct": round(float((day_log.get("cash_held_pct") or 0) if day_log else 0), 4),\n'
    '            })'
)

POL_ROW_NEW = (
    '                "fleet": "political",\n'
    '                "provider": TRADERS.get(tid, {}).get("provider", "unknown"),\n'
    '                "trailing_7d_delta": round(compute_trailing_delta(tid, state, agent_logs, 7), 2),\n'
    '                "dmad_prefix_type": _parse_dmad_prefix(day_log.get("day_strategy", "") if day_log else ""),\n'
    '                "cash_held_pct": round(float((day_log.get("cash_held_pct") or 0) if day_log else 0), 4),\n'
    '                "society_entropy": _society_entropy,\n'
    '            })'
)


def apply_patch(path: Path, patches: list, label: str) -> bool:
    text = path.read_text()
    original_lines = text.count('\n')
    for old, new in patches:
        if old not in text:
            print(f"[{label}] PATCH MISS: {repr(old[:60])}...")
            return False
        if text.count(old) > 1:
            print(f"[{label}] AMBIGUOUS: pattern appears {text.count(old)} times")
            return False
        text = text.replace(old, new, 1)
    new_lines = text.count('\n')
    path.write_text(text)
    print(f"[{label}] OK: {original_lines} -> {new_lines} lines (+{new_lines - original_lines})")
    return True


def verify(path: Path, label: str) -> bool:
    r = subprocess.run([sys.executable, "-m", "py_compile", str(path)],
                       capture_output=True, text=True)
    if r.returncode == 0:
        print(f"[{label}] py_compile OK")
        return True
    print(f"[{label}] py_compile FAIL: {r.stderr}")
    return False


if __name__ == "__main__":
    ok = True
    ok &= apply_patch(NBA_PATH, [(CK_OLD, CK_NEW), (NBA_CPD_OLD, NBA_CPD_NEW), (NBA_ROW_OLD, NBA_ROW_NEW)], "NBA")
    ok &= apply_patch(POL_PATH, [(CK_OLD, CK_NEW), (POL_CPD_OLD, POL_CPD_NEW), (POL_ROW_OLD, POL_ROW_NEW)], "POL")
    if ok:
        ok &= verify(NBA_PATH, "NBA")
        ok &= verify(POL_PATH, "POL")
    if ok:
        print("\nAll patches applied. Now run:")
        print('  bash scripts/lib/safe_commit.sh AXELROD-2026 \\')
        print('    "feat(tf): Axelrod-2026 fire-110 - Mech A tune: society entropy + lockstep alert (NBA+POL parity)" \\')
        print('    scripts/arena/hf-llm-trading-floor/app.py \\')
        print('    scripts/arena/hf-political-trading-floor/app.py')
    else:
        print("\nPATCH FAILED - no files modified")
        sys.exit(1)
