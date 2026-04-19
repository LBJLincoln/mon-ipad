"""Real historical ETF OHLC + VIX-backed IV, drop-in for intraday_paths.

Replaces the GBM+jump simulator with cached yfinance data when available.
Falls back to the simulator transparently if yfinance fails or a date is
missing — so the engine stays resilient without a network dependency at runtime.

Cache:
  data/real_paths_cache.json  — {date: {ticker: {o, h, l, c, v}}} + {vix: {date: close}}
  Refresh weekly via scripts/gpu/refresh_pqtf_cache.py (safe to call manually).

Keeps the SAME public API as intraday_paths so engine.py swaps via env flag:
  USE_REAL_PATHS=1  → real_paths.gbm_path / jump_path
  default           → intraday_paths (pure GBM)
"""
from __future__ import annotations

import json
import os
from math import sqrt, log, exp
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import intraday_paths as _sim

CACHE_PATH = Path(__file__).parent / "data" / "real_paths_cache.json"

_cache: Optional[dict] = None


def _load_cache() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if CACHE_PATH.exists():
        try:
            _cache = json.loads(CACHE_PATH.read_text())
        except Exception:
            _cache = {"ohlc": {}, "vix": {}}
    else:
        _cache = {"ohlc": {}, "vix": {}}
    return _cache


def _ohlc_for(date: str, ticker: str) -> Optional[dict]:
    c = _load_cache()
    d = c.get("ohlc", {}).get(date, {})
    return d.get(ticker)


def _vix_for(date: str) -> Optional[float]:
    c = _load_cache()
    return c.get("vix", {}).get(date)


def real_iv_for(date: str, ticker: str, iv_base: float = 0.18) -> float:
    """Scale VIX to a per-ETF IV proxy.

    VIX is SPY 30-day implied vol (annualized). Sector ETFs have historical
    vol ratio vs SPY — we hardcode a ratio table because we only need rough
    accuracy for an options pricer (options.py uses BS, not path-dependent).
    """
    vix = _vix_for(date)
    if vix is None or vix <= 0:
        return iv_base
    base_spy = 0.18
    spy_vix = vix / 100.0  # VIX is quoted as %
    spy_ratio = spy_vix / base_spy
    sector_ratios = {
        "SPY": 1.0, "XLF": 1.15, "XLK": 1.25, "XLE": 1.45,
        "XLV": 0.85, "XLP": 0.75, "XLY": 1.20, "XLC": 1.10,
        "XLI": 1.05, "XLB": 1.20, "XLRE": 1.00, "XLU": 0.80,
    }
    mult = sector_ratios.get(ticker, 1.0)
    return max(0.05, min(2.5, iv_base * spy_ratio * mult))


def gbm_path(spot0: float, iv_ann: float, minutes: int,
             steps: Optional[int] = None, seed: Optional[int] = None,
             date: Optional[str] = None, ticker: Optional[str] = None) -> List[float]:
    """Real-OHLC-backed intraday path with simulator fallback.

    Strategy when OHLC is available:
      - start = spot0 (caller passes session open; continuity preserved)
      - scale OHLC to realized intraday shape: build a piecewise-linear
        path from open→high→low→close proportional to real daily high/low
        and apply GBM noise around that trend at minute resolution.
      - preserves determinism when seed is set.
    Fallback when no OHLC: pure GBM (original behavior).
    """
    if not date or not ticker:
        return _sim.gbm_path(spot0, iv_ann, minutes, steps=steps, seed=seed)
    ohlc = _ohlc_for(date, ticker)
    if not ohlc:
        return _sim.gbm_path(spot0, iv_ann, minutes, steps=steps, seed=seed)
    o, h, l, c = ohlc.get("o", spot0), ohlc.get("h", spot0), ohlc.get("l", spot0), ohlc.get("c", spot0)
    if not (o > 0 and h > 0 and l > 0 and c > 0 and l <= min(o, c) and h >= max(o, c)):
        return _sim.gbm_path(spot0, iv_ann, minutes, steps=steps, seed=seed)

    day_range = (h - l) / o if o > 0 else 0.0
    daily_iv = max(0.05, day_range * sqrt(252.0))
    blended_iv = 0.5 * iv_ann + 0.5 * daily_iv
    ret_day = c / o - 1.0 if o > 0 else 0.0

    noise_path = _sim.gbm_path(spot0, blended_iv, minutes, steps=steps, seed=seed)
    n = len(noise_path)
    if n < 2:
        return noise_path
    out = [spot0]
    for i in range(1, n):
        frac = i / (n - 1)
        trend = spot0 * (1.0 + ret_day * frac)
        noise_ret = (noise_path[i] / noise_path[i - 1]) - 1.0
        out.append(out[-1] * (1.0 + 0.3 * noise_ret) * (trend / out[-1]) ** 0.7)
    return out


def jump_path(spot0: float, iv_ann: float, minutes: int,
              jumps: List[Tuple[int, float]],
              seed: Optional[int] = None,
              date: Optional[str] = None, ticker: Optional[str] = None) -> List[float]:
    """Real-backed jump path. Uses real OHLC as baseline then overlays jumps."""
    path = gbm_path(spot0, iv_ann, minutes, seed=seed, date=date, ticker=ticker)
    for minute_offset, pct in sorted(jumps, key=lambda j: j[0]):
        idx = max(0, min(minute_offset, len(path) - 1))
        factor = 1.0 + pct
        for i in range(idx, len(path)):
            path[i] *= factor
    return path


scale_iv_for_event = _sim.scale_iv_for_event
EVENT_IV_SCALE = _sim.EVENT_IV_SCALE


if __name__ == "__main__":
    cache = _load_cache()
    print(f"cache ohlc dates={len(cache.get('ohlc', {}))} vix dates={len(cache.get('vix', {}))}")
    if cache.get("ohlc"):
        sample_date = next(iter(cache["ohlc"]))
        print(f"sample {sample_date}: {list(cache['ohlc'][sample_date].keys())[:5]}")
    p = gbm_path(100.0, 0.20, 150, seed=1)
    assert len(p) == 151, f"expected 151, got {len(p)}"
    p_real = gbm_path(100.0, 0.20, 150, seed=1, date="2025-10-10", ticker="SPY")
    print(f"sim terminal={p[-1]:.2f}  real terminal (if cache)={p_real[-1]:.2f}")
