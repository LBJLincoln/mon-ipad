"""GBM intraday path generator with event-timed jumps.

Simulates 4-session intraday price paths for sector ETFs, with optional jumps
at specific minute-offsets inside a session (e.g. Fed statement at 14:00,
CPI release at 08:30 → premarket spillover, election-call at 23:00 → overnight gap).

Stdlib-only (uses random.gauss for normal draws). Deterministic with seed.

Sessions (ET):
  1. 09:30 – 12:00  (150 min)   — open / morning drift
  2. 12:00 – 14:30  (150 min)   — midday chop
  3. 14:30 – 16:00  (90 min)    — afternoon / close
  4. 16:00 – 20:00  (240 min)   — after-hours / political event window

For derivatives pricing, we care about:
  - terminal spot at each session boundary (for position marks)
  - intrasession high/low (for stops, barrier options)
  - jump magnitudes at event timestamps (for event-vol scaling)

API:
  gbm_path(spot0, iv_ann, minutes, steps=None, seed=None) -> list[float]
  jump_path(spot0, iv_ann, minutes, jumps, seed=None) -> list[float]
      jumps: list[(minute_offset, pct_jump)]  e.g. [(90, 0.02), (120, -0.015)]
  session_marks(path) -> {open, high, low, close}
  scale_iv_for_event(iv_base, event_type) -> iv_scaled
"""
from math import exp, log, sqrt
import random
from typing import List, Tuple, Dict, Optional


# Event-type IV scalers (multiplicative on base IV)
EVENT_IV_SCALE = {
    "FOMC": 1.60,          # Fed decision — big vol
    "CPI": 1.45,           # inflation print
    "NFP": 1.40,           # jobs report
    "ELECTION": 1.80,      # election night
    "DEBATE": 1.25,
    "SCOTUS": 1.55,        # major ruling
    "EARNINGS": 1.35,
    "GDP": 1.20,
    "GEOPOLITICAL": 1.70,  # war, sanctions, coups
    "DEFAULT": 1.00,
}


def gbm_path(spot0: float, iv_ann: float, minutes: int,
             steps: Optional[int] = None, seed: Optional[int] = None) -> List[float]:
    """Simulate GBM path at 1-minute resolution over `minutes` intraday minutes.

    dS/S = μ dt + σ dW,  we assume μ=0 intraday (drift dominated by events, not trend).
    Annualized iv_ann is scaled to per-minute:
        σ_min = iv_ann / sqrt(252 * 390)   (390 trading minutes per day)
    """
    if spot0 <= 0 or iv_ann <= 0 or minutes <= 0:
        return [spot0] * max(1, minutes + 1)
    if seed is not None:
        rng = random.Random(seed)
    else:
        rng = random
    n = steps if steps else minutes
    sigma_min = iv_ann / sqrt(252.0 * 390.0)
    dt = minutes / n
    # log-GBM increment per step
    path = [spot0]
    for _ in range(n):
        z = rng.gauss(0.0, 1.0)
        log_ret = -0.5 * sigma_min * sigma_min * dt + sigma_min * sqrt(dt) * z
        path.append(path[-1] * exp(log_ret))
    return path


def jump_path(spot0: float, iv_ann: float, minutes: int,
              jumps: List[Tuple[int, float]],
              seed: Optional[int] = None) -> List[float]:
    """GBM with deterministic jumps at specific minute offsets.

    jumps: list of (minute_offset, pct_jump). e.g. [(90, 0.02)] = +2% at t=90min.
    Jumps are applied AFTER the GBM step at that minute, clamping to valid range.
    """
    path = gbm_path(spot0, iv_ann, minutes, seed=seed)
    jumps_sorted = sorted(jumps, key=lambda j: j[0])
    for minute_offset, pct in jumps_sorted:
        idx = max(0, min(minute_offset, len(path) - 1))
        # Apply jump to this index and propagate forward (jump shifts entire future path)
        factor = 1.0 + pct
        for i in range(idx, len(path)):
            path[i] *= factor
    return path


def session_marks(path: List[float]) -> Dict[str, float]:
    """Return {open, high, low, close, ret_pct} from a single session's path."""
    if not path:
        return {"open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0, "ret_pct": 0.0}
    o, c = path[0], path[-1]
    hi = max(path)
    lo = min(path)
    ret = (c / o - 1.0) if o > 0 else 0.0
    return {"open": o, "high": hi, "low": lo, "close": c, "ret_pct": ret}


def scale_iv_for_event(iv_base: float, event_type: str) -> float:
    """Scale base IV by event-type multiplier (cap at 2.5 to avoid insanity)."""
    mult = EVENT_IV_SCALE.get(event_type.upper(), EVENT_IV_SCALE["DEFAULT"])
    return min(2.5, iv_base * mult)


def four_session_paths(spot0: float, iv_ann: float,
                       session_minutes: Tuple[int, int, int, int] = (150, 150, 90, 240),
                       jumps_by_session: Optional[Dict[int, List[Tuple[int, float]]]] = None,
                       seed: Optional[int] = None) -> Dict[str, Dict]:
    """Generate 4 consecutive sessions (morning/midday/afternoon/afterhours).

    Returns {s1: marks, s2: marks, s3: marks, s4: marks, final_close: float}.
    jumps_by_session: {1: [...], 2: [...], ...} — optional event jumps per session.
    """
    jumps_by_session = jumps_by_session or {}
    out = {}
    current_spot = spot0
    for i, mins in enumerate(session_minutes, start=1):
        session_seed = None if seed is None else seed + i
        jumps = jumps_by_session.get(i, [])
        if jumps:
            path = jump_path(current_spot, iv_ann, mins, jumps, seed=session_seed)
        else:
            path = gbm_path(current_spot, iv_ann, mins, seed=session_seed)
        marks = session_marks(path)
        out[f"s{i}"] = marks
        current_spot = marks["close"]
    out["final_close"] = current_spot
    out["total_ret_pct"] = (current_spot / spot0 - 1.0) if spot0 > 0 else 0.0
    return out


# ── Self-test ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    random.seed(42)
    # Basic GBM path
    p = gbm_path(100.0, 0.20, 390, seed=1)
    assert len(p) == 391, f"expected 391 points, got {len(p)}"
    assert p[0] == 100.0
    assert 80 < p[-1] < 125, f"terminal unreasonable: {p[-1]}"
    m = session_marks(p)
    assert m["low"] <= m["open"] <= m["high"]
    assert m["low"] <= m["close"] <= m["high"]

    # Jump path — +5% at minute 120 should show clear discontinuity
    pj = jump_path(100.0, 0.20, 390, jumps=[(120, 0.05)], seed=1)
    ret_no_jump = p[-1] / 100.0 - 1
    ret_with_jump = pj[-1] / 100.0 - 1
    assert ret_with_jump > ret_no_jump + 0.04, f"jump didn't register: {ret_with_jump - ret_no_jump}"

    # Event IV scaling
    iv_fomc = scale_iv_for_event(0.15, "FOMC")
    iv_default = scale_iv_for_event(0.15, "RANDOM_EVENT")
    assert iv_fomc == 0.15 * 1.60
    assert iv_default == 0.15
    assert scale_iv_for_event(2.0, "ELECTION") == 2.5  # capped

    # Four-session with election-night jump in s4
    s = four_session_paths(100.0, 0.25, jumps_by_session={4: [(120, -0.03)]}, seed=7)
    assert {"s1", "s2", "s3", "s4", "final_close", "total_ret_pct"} <= set(s.keys())
    assert s["s1"]["close"] == s["s2"]["open"]  # continuity
    assert s["s3"]["close"] == s["s4"]["open"]

    # Zero-iv degenerate
    pz = gbm_path(100.0, 0.0, 60, seed=1)
    assert all(x == 100.0 for x in pz), "zero-iv should be flat"

    # Determinism
    a = gbm_path(100.0, 0.20, 100, seed=42)
    b = gbm_path(100.0, 0.20, 100, seed=42)
    assert a == b, "same seed should produce same path"

    print("[intraday_paths.py] all self-tests pass")
    print(f"  GBM 1-day 20% IV, terminal spot: {p[-1]:.4f}")
    print(f"  With +5% jump @ t=120: terminal {pj[-1]:.4f}  (Δ{(ret_with_jump - ret_no_jump)*100:+.2f}pp)")
    print(f"  4-session election day: {s['total_ret_pct']*100:+.2f}% (s4 has -3% jump)")
    print(f"    s1 close: {s['s1']['close']:.2f}  s2 close: {s['s2']['close']:.2f}  "
          f"s3 close: {s['s3']['close']:.2f}  s4 close: {s['s4']['close']:.2f}")
    print(f"  Event IV scaling: FOMC 0.15→{iv_fomc:.3f}, ELECTION cap 2.0→{scale_iv_for_event(2.0, 'ELECTION'):.3f}")
