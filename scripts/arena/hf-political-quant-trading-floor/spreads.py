"""Multi-leg option strategies + portfolio risk.

Strategies:
  - Vertical spread   (bull call, bear put, etc.)    — defined risk, defined reward
  - Iron condor       (short OTM call + put spreads) — bet on low vol / range-bound
  - Calendar spread   (short near, long far, same K) — bet on vol term structure
  - Butterfly         (long ITM + 2 short ATM + long OTM) — bet on pinning
  - Straddle / strangle                              — bet on vol expansion

Risk utilities:
  - Stop-loss: close at -2σ of entry-to-target move
  - Portfolio VaR (parametric, 95%)
  - Margin for defined-risk vs undefined-risk positions
  - Greeks aggregation (net delta, gamma, vega, theta)

All priced from options.bs_price. Stdlib only.
"""
from math import sqrt, log
from typing import List, Dict, Tuple, Optional
from options import bs_price, bs_greeks


# ── Strategy constructors ──────────────────────────────────────────────────

def vertical_spread(spot: float, strike_low: float, strike_high: float,
                    tte_years: float, iv: float, option_type: str = "call",
                    r: float = 0.045, q: float = 0.0) -> Dict:
    """Bull call (buy low K, sell high K) or bear put (buy high K, sell low K).

    Cost = long_premium - short_premium
    Max profit = (high - low) - cost (for bull call)
    Max loss = cost
    Break-even = low + cost  (bull call)
    """
    assert strike_low < strike_high, "strike_low must be < strike_high"
    long_price = bs_price(spot, strike_low if option_type == "call" else strike_high,
                          tte_years, iv, option_type, r, q)
    short_price = bs_price(spot, strike_high if option_type == "call" else strike_low,
                           tte_years, iv, option_type, r, q)
    width = strike_high - strike_low
    if option_type == "call":
        cost = long_price - short_price
        max_profit = width - cost
        max_loss = cost
        breakeven = strike_low + cost
    else:  # bear put
        cost = long_price - short_price
        max_profit = width - cost
        max_loss = cost
        breakeven = strike_high - cost
    return {
        "type": f"{option_type}_vertical",
        "direction": "bull" if option_type == "call" else "bear",
        "legs": [
            {"side": "long", "strike": strike_low if option_type == "call" else strike_high,
             "option_type": option_type, "qty": 1, "entry_price": long_price},
            {"side": "short", "strike": strike_high if option_type == "call" else strike_low,
             "option_type": option_type, "qty": 1, "entry_price": short_price},
        ],
        "cost": round(cost, 4), "max_profit": round(max_profit, 4),
        "max_loss": round(max_loss, 4), "breakeven": round(breakeven, 4),
        "width": round(width, 4), "risk_reward": round(max_profit / max(0.01, max_loss), 2),
    }


def iron_condor(spot: float, put_short: float, put_long: float,
                call_short: float, call_long: float,
                tte_years: float, iv: float, r: float = 0.045) -> Dict:
    """Iron condor: short call spread + short put spread. Net credit strategy.

    Profit if spot stays between put_short and call_short at expiry.
    Max loss = wing_width - net_credit.
    """
    assert put_long < put_short < call_short < call_long, "ordering: put_long<put_short<call_short<call_long"
    pl_long = bs_price(spot, put_long, tte_years, iv, "put", r)
    pl_short = bs_price(spot, put_short, tte_years, iv, "put", r)
    cl_short = bs_price(spot, call_short, tte_years, iv, "call", r)
    cl_long = bs_price(spot, call_long, tte_years, iv, "call", r)
    # Sell inner, buy outer → net credit
    put_credit = pl_short - pl_long
    call_credit = cl_short - cl_long
    net_credit = put_credit + call_credit
    wing = max(put_short - put_long, call_long - call_short)
    max_loss = wing - net_credit
    return {
        "type": "iron_condor",
        "legs": [
            {"side": "long",  "strike": put_long,  "option_type": "put",  "entry_price": pl_long},
            {"side": "short", "strike": put_short, "option_type": "put",  "entry_price": pl_short},
            {"side": "short", "strike": call_short, "option_type": "call", "entry_price": cl_short},
            {"side": "long",  "strike": call_long, "option_type": "call", "entry_price": cl_long},
        ],
        "net_credit": round(net_credit, 4), "max_profit": round(net_credit, 4),
        "max_loss": round(max_loss, 4),
        "breakeven_low": round(put_short - net_credit, 4),
        "breakeven_high": round(call_short + net_credit, 4),
        "risk_reward": round(net_credit / max(0.01, max_loss), 2),
    }


def straddle(spot: float, strike: float, tte_years: float, iv: float,
             r: float = 0.045, side: str = "long") -> Dict:
    """Long straddle: buy ATM call + put. Profits if |move| > total_premium.

    side: "long" (debit) or "short" (credit, capped risk if margin).
    """
    c = bs_price(spot, strike, tte_years, iv, "call", r)
    p = bs_price(spot, strike, tte_years, iv, "put", r)
    cost = c + p
    return {
        "type": f"{side}_straddle",
        "legs": [
            {"side": side, "strike": strike, "option_type": "call", "entry_price": c},
            {"side": side, "strike": strike, "option_type": "put",  "entry_price": p},
        ],
        "cost": round(cost, 4) if side == "long" else -round(cost, 4),
        "breakeven_low":  round(strike - cost, 4),
        "breakeven_high": round(strike + cost, 4),
        "max_profit": "unbounded" if side == "long" else round(cost, 4),
        "max_loss": round(cost, 4) if side == "long" else "unbounded",
    }


def butterfly(spot: float, strike_low: float, strike_mid: float, strike_high: float,
              tte_years: float, iv: float, option_type: str = "call",
              r: float = 0.045) -> Dict:
    """Long butterfly: buy 1 low K, sell 2 mid K, buy 1 high K. Bets on pinning at mid K.

    Cost = low_premium - 2*mid_premium + high_premium.
    Max profit at expiry if spot = strike_mid.
    """
    assert strike_low < strike_mid < strike_high
    lo = bs_price(spot, strike_low,  tte_years, iv, option_type, r)
    md = bs_price(spot, strike_mid,  tte_years, iv, option_type, r)
    hi = bs_price(spot, strike_high, tte_years, iv, option_type, r)
    cost = lo - 2 * md + hi
    wing = min(strike_mid - strike_low, strike_high - strike_mid)
    max_profit = wing - cost
    return {
        "type": f"{option_type}_butterfly",
        "legs": [
            {"side": "long",  "strike": strike_low,  "option_type": option_type, "qty": 1, "entry_price": lo},
            {"side": "short", "strike": strike_mid,  "option_type": option_type, "qty": 2, "entry_price": md},
            {"side": "long",  "strike": strike_high, "option_type": option_type, "qty": 1, "entry_price": hi},
        ],
        "cost": round(cost, 4), "max_profit": round(max_profit, 4),
        "max_loss": round(cost, 4),
        "pin_strike": strike_mid,
    }


# ── Multi-leg mark-to-market ───────────────────────────────────────────────

def mark_position(strategy: Dict, spot_now: float, tte_years_now: float,
                  iv_now: float, r: float = 0.045, multiplier: int = 100) -> Dict:
    """Mark a multi-leg strategy to current spot/tte/IV. Returns {mark, pnl, greeks}."""
    leg_marks = []
    net_mark = 0.0
    net_greeks = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
    for leg in strategy["legs"]:
        qty = leg.get("qty", 1)
        side_sign = 1 if leg["side"] == "long" else -1
        mark_price = bs_price(spot_now, leg["strike"], tte_years_now, iv_now,
                              leg["option_type"], r)
        greeks = bs_greeks(spot_now, leg["strike"], tte_years_now, iv_now,
                           leg["option_type"], r)
        leg_pnl = (mark_price - leg["entry_price"]) * side_sign * qty * multiplier
        leg_marks.append({**leg, "mark": round(mark_price, 4), "pnl": round(leg_pnl, 2)})
        net_mark += mark_price * side_sign * qty
        for g in net_greeks:
            net_greeks[g] += greeks[g] * side_sign * qty
    strategy_cost = strategy.get("cost") or -strategy.get("net_credit", 0.0)
    try:
        strategy_cost = float(strategy_cost)
    except (TypeError, ValueError):
        strategy_cost = 0.0
    total_pnl = sum(l["pnl"] for l in leg_marks)
    return {
        "mark_per_share": round(net_mark, 4),
        "mark_total": round(net_mark * multiplier, 2),
        "pnl": round(total_pnl, 2),
        "leg_marks": leg_marks,
        "net_greeks": {k: round(v, 4) for k, v in net_greeks.items()},
    }


# ── Portfolio risk ─────────────────────────────────────────────────────────

def portfolio_var(positions: List[Dict], confidence: float = 0.95) -> float:
    """Parametric VaR from position deltas + implied vol assumption.

    positions: list of dicts with {mark_total, net_greeks: {delta, vega}, spot, iv}
    Uses 1-day horizon: σ_1d = spot × iv / sqrt(252) × delta_abs.
    Conservative — does not correlate across underlyings (assumes independence).
    """
    from math import sqrt
    total_var = 0.0
    # z-score for 95% one-sided
    z = 1.645 if confidence == 0.95 else 2.326 if confidence == 0.99 else 1.28
    for p in positions:
        spot = p.get("spot", 0)
        iv = p.get("iv", 0.20)
        delta = p.get("net_greeks", {}).get("delta", 0)
        daily_move = spot * iv / sqrt(252.0)
        position_var = abs(delta) * daily_move * z
        total_var += position_var ** 2
    return sqrt(total_var)


def check_stop_loss(strategy_cost: float, current_pnl: float, pct_threshold: float = -0.5) -> bool:
    """Return True if position should be stopped out.

    Default: close if unrealized loss ≥ 50% of entry cost.
    """
    if strategy_cost <= 0:
        return False
    loss_pct = current_pnl / (strategy_cost * 100)  # mult 100 for contract
    return loss_pct <= pct_threshold


def margin_requirement(strategy: Dict, multiplier: int = 100) -> float:
    """Compute margin for a multi-leg strategy (Reg T).

    Defined-risk (long options, verticals, condors, butterflies) → cost of debit or max loss.
    Undefined-risk (naked short, short straddle) → ~20% of underlying × multiplier.
    """
    stype = strategy.get("type", "")
    if "vertical" in stype or "condor" in stype or "butterfly" in stype:
        return float(strategy.get("max_loss", 0)) * multiplier
    if "long_straddle" in stype or "long_strangle" in stype:
        return abs(float(strategy.get("cost", 0))) * multiplier
    if "short_straddle" in stype or "short_strangle" in stype:
        # naked — approximate 20% margin
        legs = strategy.get("legs", [])
        if legs:
            return abs(legs[0].get("strike", 100)) * 0.20 * multiplier
    return float(strategy.get("cost", 0)) * multiplier


# ── Self-test ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Bull call spread: XLF at 50, buy 50 call / sell 52 call, 1-week
    bull = vertical_spread(50.0, 50.0, 52.0, 7/252, 0.20, "call")
    assert bull["cost"] > 0
    assert bull["max_profit"] > 0
    assert bull["max_loss"] == bull["cost"]
    assert bull["breakeven"] > 50.0
    assert bull["width"] == 2.0
    print(f"[bull call] cost=${bull['cost']:.3f} max_profit=${bull['max_profit']:.3f} "
          f"BE=${bull['breakeven']:.3f} R:R={bull['risk_reward']}")

    # Iron condor on SPY at 520
    ic = iron_condor(520, 505, 495, 535, 545, 14/252, 0.18)
    assert ic["net_credit"] > 0
    assert ic["max_loss"] > 0
    print(f"[iron condor] credit=${ic['net_credit']:.3f} max_loss=${ic['max_loss']:.3f} "
          f"BE [{ic['breakeven_low']:.2f}, {ic['breakeven_high']:.2f}]")

    # Long straddle at 100, 30d 25% IV
    st = straddle(100, 100, 30/252, 0.25, side="long")
    assert st["cost"] > 0
    assert st["breakeven_low"] < 100 < st["breakeven_high"]
    print(f"[straddle] cost=${st['cost']:.3f} BE [{st['breakeven_low']:.2f}, {st['breakeven_high']:.2f}]")

    # Butterfly
    bf = butterfly(100, 95, 100, 105, 21/252, 0.20, "call")
    assert bf["cost"] > 0
    assert bf["max_profit"] > 0
    print(f"[butterfly] cost=${bf['cost']:.3f} max_profit=${bf['max_profit']:.3f} pin={bf['pin_strike']}")

    # Mark-to-market: bull call, spot moves from 50 → 51 (favorable)
    mk = mark_position(bull, 51.0, 5/252, 0.20)
    print(f"[mark] bull@51 (2d later): mark=${mk['mark_per_share']:.3f} pnl=${mk['pnl']:+,.2f} "
          f"delta={mk['net_greeks']['delta']:.3f}")
    assert mk["pnl"] > 0, "bull call should profit when spot rises"

    # Portfolio VaR
    positions = [
        {"spot": 50, "iv": 0.20, "mark_total": 150, "net_greeks": {"delta": 0.3}},
        {"spot": 520, "iv": 0.18, "mark_total": -250, "net_greeks": {"delta": -0.1}},
    ]
    var95 = portfolio_var(positions, 0.95)
    print(f"[VaR-1d-95%] portfolio: ${var95:.2f}")
    assert var95 > 0

    # Stop-loss trigger
    assert check_stop_loss(0.50, -25, -0.5)     # $25 loss on $50 cost → stop
    assert not check_stop_loss(0.50, -10, -0.5)  # $10 loss on $50 cost → hold
    print("[stop_loss] trigger logic OK")

    # Margin
    m_bull = margin_requirement(bull)
    m_strad = margin_requirement(st)
    print(f"[margin] bull_call=${m_bull:.2f}  long_straddle=${m_strad:.2f}")

    print("[spreads.py] all self-tests pass")
