"""Market-maker signal bus — what dealers are telling us about regime.

Intraday tick-level view of dealer positioning. ITF agents read this each tick
and reason about the MM-implied view instead of only their own edge.

Signals produced (best-effort; each failure returns None, never raises):
  - VIX term structure (^VIX vs ^VIX3M vs ^VIX9D) → contango/backwardation
  - SKEW index (^SKEW) → tail-risk demand
  - Put/Call ratio on SPY (from 0-14DTE options chain)
  - IV rank proxy (current VIX vs 30d percentile from cached history)
  - Unusual options activity (top-volume contracts on top 10 tickers)
  - Gamma exposure proxy — signed dealer-gamma on SPY 0-14DTE

Cached at module scope (10 min TTL) — dealers don't rebalance every 5 seconds.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[3]
CACHE_DIR = REPO / "data" / "mm"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
VIX_HISTORY = CACHE_DIR / "vix_history.json"   # 30d VIX close series for IV-rank

_CACHE: Dict[str, Any] = {"ts": 0, "bundle": None}
_TTL_S = 600  # 10 min — MM positioning doesn't revalue faster


def _try_yf(symbol: str) -> Optional[float]:
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        info = t.fast_info
        p = info.get("last_price") if isinstance(info, dict) else getattr(info, "last_price", None)
        if p is None:
            hist = t.history(period="1d", interval="1m")
            if not hist.empty:
                p = float(hist["Close"].iloc[-1])
        return float(p) if p is not None else None
    except Exception:
        return None


def vix_term_structure() -> Dict[str, Any]:
    """^VIX9D / ^VIX / ^VIX3M — dealer vol regime."""
    v9 = _try_yf("^VIX9D")
    v30 = _try_yf("^VIX")
    v3m = _try_yf("^VIX3M")
    out: Dict[str, Any] = {"vix9d": v9, "vix": v30, "vix3m": v3m}
    if v30 and v3m:
        out["contango"] = round(v3m - v30, 2)
        out["regime"] = (
            "backwardation_stress" if v30 > v3m + 0.5
            else "steep_contango_calm" if v3m - v30 > 2.0
            else "neutral"
        )
    return out


def skew_index() -> Optional[float]:
    """CBOE SKEW — 100=normal, >140=tail demand."""
    s = _try_yf("^SKEW")
    return round(s, 2) if s else None


def _update_vix_history(vix_now: Optional[float]) -> List[float]:
    if vix_now is None:
        return []
    try:
        body = json.loads(VIX_HISTORY.read_text()) if VIX_HISTORY.exists() else []
    except Exception:
        body = []
    body.append({"ts": int(time.time()), "vix": vix_now})
    body = body[-720:]  # keep ~5d of 10-min points
    try:
        VIX_HISTORY.write_text(json.dumps(body))
    except Exception:
        pass
    return [row["vix"] for row in body if isinstance(row, dict) and "vix" in row]


def iv_rank_proxy(vix_now: Optional[float]) -> Optional[float]:
    """0-100 percentile of current VIX in trailing window. MM supply tightens at high IV-rank."""
    series = _update_vix_history(vix_now)
    if not series or vix_now is None or len(series) < 10:
        return None
    below = sum(1 for v in series if v <= vix_now)
    return round(100.0 * below / len(series), 1)


def spy_pcr_and_gex() -> Dict[str, Any]:
    """Put/Call ratio + rough gamma-exposure sign on SPY 0-14DTE.

    GEX sign: sum over chain of (gamma * OI * 100 * spot^2 * 0.01), with
    calls positive, puts negative from dealer perspective. This is a PROXY,
    not a SpotGamma-grade number — good enough to flag pins vs acceleration.
    """
    try:
        import yfinance as yf
        from datetime import datetime, timezone, timedelta
        spy = yf.Ticker("SPY")
        spot_info = spy.fast_info
        spot = spot_info.get("last_price") if isinstance(spot_info, dict) else getattr(spot_info, "last_price", None)
        if spot is None:
            return {}
        today = datetime.now(timezone.utc).date()
        expiries = [e for e in (spy.options or []) if e]
        near = []
        for e in expiries[:6]:
            try:
                d = datetime.strptime(e, "%Y-%m-%d").date()
                if 0 <= (d - today).days <= 14:
                    near.append(e)
            except Exception:
                continue
        if not near:
            return {"spot": round(float(spot), 2)}
        put_vol = 0.0
        call_vol = 0.0
        gex_sum = 0.0
        for exp in near[:3]:
            try:
                chain = spy.option_chain(exp)
                calls = chain.calls
                puts = chain.puts
                call_vol += float(calls["volume"].fillna(0).sum())
                put_vol += float(puts["volume"].fillna(0).sum())
                # crude gamma proxy: 1/|strike - spot+0.01|
                for _, row in calls.iterrows():
                    k = float(row.get("strike") or spot)
                    oi = float(row.get("openInterest") or 0)
                    gex_sum += oi * 100.0 * (spot ** 2) * 0.0001 / max(abs(k - spot) + 1.0, 1.0)
                for _, row in puts.iterrows():
                    k = float(row.get("strike") or spot)
                    oi = float(row.get("openInterest") or 0)
                    gex_sum -= oi * 100.0 * (spot ** 2) * 0.0001 / max(abs(k - spot) + 1.0, 1.0)
            except Exception:
                continue
        pcr = round(put_vol / max(call_vol, 1.0), 3)
        return {
            "spot": round(float(spot), 2),
            "spy_pcr": pcr,
            "pcr_regime": "hedging_heavy" if pcr > 1.3 else "complacent" if pcr < 0.7 else "balanced",
            "spy_gex_proxy_mm": round(gex_sum / 1e6, 1),
            "gex_sign": "positive_pin" if gex_sum > 0 else "negative_accel",
        }
    except Exception:
        return {}


def unusual_options_activity(tickers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Top-volume contracts on ETF/mega-cap chains. Volume/OI > 2 = unusual."""
    tickers = tickers or ["QQQ", "IWM", "TLT", "GLD", "NVDA", "TSLA", "AAPL", "MSFT"]
    try:
        import yfinance as yf
    except Exception:
        return []
    flags: List[Dict[str, Any]] = []
    for tk in tickers[:8]:
        try:
            t = yf.Ticker(tk)
            exps = (t.options or [])[:1]
            if not exps:
                continue
            chain = t.option_chain(exps[0])
            for side, df in (("C", chain.calls), ("P", chain.puts)):
                top = df.assign(
                    vol_oi=lambda d: d["volume"].fillna(0) / d["openInterest"].replace(0, 1).fillna(1)
                ).sort_values("vol_oi", ascending=False).head(1)
                for _, row in top.iterrows():
                    voi = float(row.get("vol_oi") or 0)
                    vol = float(row.get("volume") or 0)
                    if voi > 2.0 and vol > 500:
                        flags.append({
                            "t": tk,
                            "side": side,
                            "strike": float(row.get("strike") or 0),
                            "exp": exps[0],
                            "vol": int(vol),
                            "oi": int(row.get("openInterest") or 0),
                            "vol_oi": round(voi, 2),
                        })
        except Exception:
            continue
    flags.sort(key=lambda r: -r["vol_oi"])
    return flags[:6]


def build_mm_signals() -> Dict[str, Any]:
    """Bundle every MM read into one dict. Cached 10 min."""
    now = time.time()
    if _CACHE["bundle"] and (now - _CACHE["ts"] < _TTL_S):
        return _CACHE["bundle"]

    term = vix_term_structure()
    skew = skew_index()
    iv_rank = iv_rank_proxy(term.get("vix"))
    pcr_gex = spy_pcr_and_gex()
    unusual = unusual_options_activity()

    bundle = {
        "ts": int(now),
        "vix_term": term,
        "skew": skew,
        "iv_rank_5d_pct": iv_rank,
        "spy": pcr_gex,
        "unusual_options": unusual,
        "summary": _build_summary(term, skew, iv_rank, pcr_gex, unusual),
    }
    _CACHE["ts"] = now
    _CACHE["bundle"] = bundle
    return bundle


def _build_summary(term: Dict[str, Any], skew: Optional[float],
                   iv_rank: Optional[float], pcr_gex: Dict[str, Any],
                   unusual: List[Dict[str, Any]]) -> str:
    bits: List[str] = []
    if term.get("vix") is not None:
        bits.append(f"VIX {term['vix']:.1f}")
    if term.get("regime"):
        bits.append(term["regime"])
    if skew is not None:
        bits.append(f"SKEW {skew:.0f}" + (" (tail-bid)" if skew > 140 else ""))
    if iv_rank is not None:
        bits.append(f"IVr {iv_rank:.0f}")
    if pcr_gex.get("spy_pcr") is not None:
        bits.append(f"SPY PCR {pcr_gex['spy_pcr']} {pcr_gex.get('pcr_regime','')}")
    if pcr_gex.get("gex_sign"):
        bits.append(pcr_gex["gex_sign"])
    if unusual:
        bits.append(f"{len(unusual)} unusual chains")
    return " · ".join(bits) if bits else "MM signals unavailable"


if __name__ == "__main__":
    bundle = build_mm_signals()
    print(json.dumps(bundle, indent=2, default=str))
