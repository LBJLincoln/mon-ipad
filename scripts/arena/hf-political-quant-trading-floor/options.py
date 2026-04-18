"""Black-Scholes options pricer with Greeks + historical-vol IV estimator.

Designed for the political-quant-trading-floor intraday/derivatives extension.
Lean, stdlib-only, deterministic. No numpy/scipy dependency.

API:
  bs_price(spot, strike, tte_years, iv, option_type, r=0.0, q=0.0) -> float
  bs_greeks(spot, strike, tte_years, iv, option_type, r=0.0, q=0.0) -> dict
  implied_vol_hist(daily_closes: list[float], lookback_days=30) -> float

Conventions:
  - tte_years: time to expiry in YEARS (e.g. 1 day = 1/252 = 0.00397)
  - iv: annualized implied vol, decimal (0.20 = 20%)
  - r: risk-free rate (default 0, simplification for short-dated)
  - q: dividend yield (default 0)
  - option_type: "call" or "put"
  - Greeks returned: delta, gamma, theta (per-day), vega (per-1vol-point), rho

References: Hull 11e; cross-checked against QuantLib for ATM 1y 20% vol.
"""
from math import exp, log, sqrt, pi, erf
from typing import List, Dict, Optional


# ── Standard normal CDF + PDF (stdlib-only) ─────────────────────────────────

def _norm_cdf(x: float) -> float:
    """Φ(x) via erf. Accurate to ~1e-15."""
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return exp(-0.5 * x * x) / sqrt(2.0 * pi)


# ── Black-Scholes price ─────────────────────────────────────────────────────

def _d1(spot: float, strike: float, tte: float, iv: float, r: float, q: float) -> float:
    return (log(spot / strike) + (r - q + 0.5 * iv * iv) * tte) / (iv * sqrt(tte))


def bs_price(spot: float, strike: float, tte_years: float, iv: float,
             option_type: str = "call", r: float = 0.0, q: float = 0.0) -> float:
    """Black-Scholes European option price.

    Degenerate cases:
      - tte_years ≤ 0 → intrinsic value (max(spot-strike, 0) for call, max(strike-spot, 0) for put)
      - iv ≤ 0 or spot ≤ 0 → intrinsic value
    """
    if tte_years <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
        intrinsic = spot - strike if option_type == "call" else strike - spot
        return max(intrinsic, 0.0)
    d1 = _d1(spot, strike, tte_years, iv, r, q)
    d2 = d1 - iv * sqrt(tte_years)
    disc_r = exp(-r * tte_years)
    disc_q = exp(-q * tte_years)
    if option_type == "call":
        return spot * disc_q * _norm_cdf(d1) - strike * disc_r * _norm_cdf(d2)
    elif option_type == "put":
        return strike * disc_r * _norm_cdf(-d2) - spot * disc_q * _norm_cdf(-d1)
    raise ValueError(f"option_type must be 'call' or 'put', got {option_type!r}")


# ── Greeks ──────────────────────────────────────────────────────────────────

def bs_greeks(spot: float, strike: float, tte_years: float, iv: float,
              option_type: str = "call", r: float = 0.0, q: float = 0.0) -> Dict[str, float]:
    """Return {delta, gamma, theta_per_day, vega_per_1pct, rho_per_1pct}.

    theta is scaled to per-calendar-day (÷365).
    vega is scaled to a 1% vol change (÷100 from analytic form).
    rho is scaled to a 1% rate change.
    """
    if tte_years <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
        # Deep degenerate: intrinsic region, all greeks zero except delta ±1/0 at boundary.
        if option_type == "call":
            delta = 1.0 if spot > strike else 0.0
        else:
            delta = -1.0 if spot < strike else 0.0
        return {"delta": delta, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
    d1 = _d1(spot, strike, tte_years, iv, r, q)
    d2 = d1 - iv * sqrt(tte_years)
    disc_r = exp(-r * tte_years)
    disc_q = exp(-q * tte_years)
    pdf_d1 = _norm_pdf(d1)
    gamma = (disc_q * pdf_d1) / (spot * iv * sqrt(tte_years))
    vega_analytic = spot * disc_q * pdf_d1 * sqrt(tte_years)  # per 1.00 vol change
    vega_per_1pct = vega_analytic / 100.0
    if option_type == "call":
        delta = disc_q * _norm_cdf(d1)
        theta_analytic = (
            -(spot * disc_q * pdf_d1 * iv) / (2.0 * sqrt(tte_years))
            + q * spot * disc_q * _norm_cdf(d1)
            - r * strike * disc_r * _norm_cdf(d2)
        )
        rho_analytic = strike * tte_years * disc_r * _norm_cdf(d2)
    else:  # put
        delta = -disc_q * _norm_cdf(-d1)
        theta_analytic = (
            -(spot * disc_q * pdf_d1 * iv) / (2.0 * sqrt(tte_years))
            - q * spot * disc_q * _norm_cdf(-d1)
            + r * strike * disc_r * _norm_cdf(-d2)
        )
        rho_analytic = -strike * tte_years * disc_r * _norm_cdf(-d2)
    return {
        "delta": delta,
        "gamma": gamma,
        "theta": theta_analytic / 365.0,
        "vega": vega_per_1pct,
        "rho": rho_analytic / 100.0,
    }


# ── Implied vol from historical realized vol ────────────────────────────────

def implied_vol_hist(daily_closes: List[float], lookback_days: int = 30,
                     iv_premium: float = 1.15, floor: float = 0.08,
                     cap: float = 1.50) -> float:
    """Estimate IV from realized close-to-close vol × iv_premium.

    Real options IV typically trades at a ~15-25% premium to realized (vol-risk
    premium). We use 1.15 × realized as a conservative anchor.

    Falls back to `floor` if < 5 points. Annualized (×√252).
    """
    closes = [c for c in daily_closes if c and c > 0]
    if len(closes) < 5:
        return floor
    closes = closes[-lookback_days - 1:] if len(closes) > lookback_days + 1 else closes
    log_rets = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0 and closes[i] > 0:
            log_rets.append(log(closes[i] / closes[i - 1]))
    if len(log_rets) < 2:
        return floor
    n = len(log_rets)
    mean_r = sum(log_rets) / n
    var = sum((r - mean_r) ** 2 for r in log_rets) / (n - 1)
    daily_vol = sqrt(var)
    ann_realized = daily_vol * sqrt(252.0)
    iv = ann_realized * iv_premium
    return max(floor, min(cap, iv))


# ── Position P&L helper ─────────────────────────────────────────────────────

def option_pnl(entry_price: float, current_price: float, qty: int,
               multiplier: int = 100, side: str = "long") -> float:
    """P&L for a single option leg.

    qty = number of contracts; multiplier = 100 (equity options), 1 (futures).
    side: "long" (debit at entry) or "short" (credit at entry).
    """
    unit_pnl = current_price - entry_price
    if side == "short":
        unit_pnl = -unit_pnl
    return unit_pnl * qty * multiplier


# ── Self-test ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Reference: S=100, K=100, T=1y, IV=20%, r=5% → BS call ≈ 10.45, put ≈ 5.57
    c = bs_price(100, 100, 1.0, 0.20, "call", r=0.05)
    p = bs_price(100, 100, 1.0, 0.20, "put", r=0.05)
    assert abs(c - 10.4506) < 0.01, f"call mismatch: {c}"
    assert abs(p - 5.5735) < 0.01, f"put mismatch: {p}"
    # Put-call parity: C - P = S*exp(-qT) - K*exp(-rT)
    assert abs((c - p) - (100 - 100 * exp(-0.05))) < 0.01
    # ATM Greeks sanity
    g = bs_greeks(100, 100, 1.0, 0.20, "call", r=0.05)
    assert 0.6 < g["delta"] < 0.7  # ATM call delta ≈ 0.64
    assert g["gamma"] > 0
    assert g["theta"] < 0  # time decay
    assert g["vega"] > 0
    # 0DTE edge case
    atm_0dte = bs_price(100, 100, 1.0 / 252, 0.20, "call")
    assert 0.1 < atm_0dte < 1.0, f"0DTE ATM call should be cheap but > 0: {atm_0dte}"
    # Intrinsic at expiry
    assert bs_price(110, 100, 0, 0.20, "call") == 10
    assert bs_price(90, 100, 0, 0.20, "put") == 10
    assert bs_price(90, 100, 0, 0.20, "call") == 0
    # IV estimator
    import random
    random.seed(42)
    closes = [100.0]
    for _ in range(60):
        closes.append(closes[-1] * exp(random.gauss(0, 0.01)))  # ~16% ann vol
    iv = implied_vol_hist(closes, lookback_days=30)
    assert 0.10 < iv < 0.25, f"IV estimate outside sanity range: {iv}"
    print("[options.py] all self-tests pass")
    print(f"  ATM 1y call (S=K=100, IV=20%, r=5%): ${c:.4f}  (expected 10.4506)")
    print(f"  ATM 1y put  (S=K=100, IV=20%, r=5%): ${p:.4f}  (expected 5.5735)")
    print(f"  ATM delta: {g['delta']:.4f}  gamma: {g['gamma']:.6f}  theta/day: {g['theta']:.4f}")
    print(f"  IV from simulated 16% realized: {iv:.4f}")
