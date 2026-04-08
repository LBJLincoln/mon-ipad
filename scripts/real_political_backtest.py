#!/usr/bin/env python3
"""
Real Political Trading Backtest — Using Actual Market Prices
=============================================================
Downloads real daily close prices via yfinance and runs 8 trading strategies
on 20 ETFs from 2025-10-01 to 2026-04-03.

Each strategy starts with $100,000 virtual capital.

Output: Confrontation table sorted by Sharpe ratio.
Saves results to data/nba-agent/real-political-confrontation.json
"""

import json, os, sys, warnings
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

# ── CONFIG ──────────────────────────────────────────────────────────────────
INITIAL_CAPITAL = 100_000.0
START_DATE = "2025-10-01"
END_DATE = "2026-04-03"
RISK_FREE_RATE = 0.05  # ~5% T-bill rate

TICKERS = {
    # Indices
    "SPY": "S&P 500", "QQQ": "NASDAQ 100", "IWM": "Russell 2000", "DIA": "Dow Jones",
    # Sectors
    "XLK": "Technology", "XLF": "Financials", "XLE": "Energy", "XLV": "Healthcare",
    "XLI": "Industrials", "XLU": "Utilities", "XLRE": "Real Estate", "XLC": "Communications",
    # Safe havens
    "GLD": "Gold", "TLT": "20Y Treasuries", "SHY": "1-3Y Treasuries", "UUP": "US Dollar",
    # Crypto
    "BITO": "Bitcoin ETF",
    # International
    "EFA": "Intl Developed", "EEM": "Emerging Mkts", "FXI": "China",
}

ROOT = Path("/home/termius/mon-ipad")
OUTPUT_FILE = ROOT / "data" / "nba-agent" / "real-political-confrontation.json"

# ── DATA DOWNLOAD ───────────────────────────────────────────────────────────
def download_prices() -> pd.DataFrame:
    """Download daily close prices for all tickers."""
    print(f"Downloading prices for {len(TICKERS)} ETFs: {START_DATE} to {END_DATE}")

    tickers_str = " ".join(TICKERS.keys())
    data = yf.download(tickers_str, start=START_DATE, end=END_DATE,
                        auto_adjust=True, progress=False)

    # Extract 'Close' prices
    if isinstance(data.columns, pd.MultiIndex):
        prices = data["Close"]
    else:
        prices = data

    # Drop any tickers with no data
    prices = prices.dropna(axis=1, how="all")
    # Forward-fill gaps (weekends/holidays already excluded by yfinance)
    prices = prices.ffill()
    prices = prices.dropna()

    print(f"  Got {len(prices)} trading days, {len(prices.columns)} tickers")
    print(f"  Date range: {prices.index[0].strftime('%Y-%m-%d')} to {prices.index[-1].strftime('%Y-%m-%d')}")

    missing = set(TICKERS.keys()) - set(prices.columns)
    if missing:
        print(f"  Missing tickers: {missing}")

    return prices


# ── TECHNICAL INDICATORS ────────────────────────────────────────────────────
def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Compute RSI indicator."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_realized_vol(series: pd.Series, window: int = 20) -> pd.Series:
    """Annualized realized volatility from log returns."""
    log_ret = np.log(series / series.shift(1))
    return log_ret.rolling(window=window, min_periods=window).std() * np.sqrt(252)


def compute_zscore(series: pd.Series, window: int = 20) -> pd.Series:
    """Rolling z-score."""
    mean = series.rolling(window=window, min_periods=window).mean()
    std = series.rolling(window=window, min_periods=window).std()
    return (series - mean) / std.replace(0, np.nan)


# ── STRATEGY BASE ───────────────────────────────────────────────────────────
class Strategy:
    """Base class for tracking strategy equity."""
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.equity = [INITIAL_CAPITAL]
        self.dates = []
        self.monthly_returns = {}

    def get_metrics(self) -> dict:
        """Compute performance metrics."""
        equity = np.array(self.equity)
        daily_returns = np.diff(equity) / equity[:-1]

        total_return = (equity[-1] / equity[0]) - 1
        n_days = len(daily_returns)
        ann_factor = 252 / max(n_days, 1)
        ann_return = (1 + total_return) ** ann_factor - 1

        # Sharpe
        if daily_returns.std() > 0:
            sharpe = (daily_returns.mean() - RISK_FREE_RATE / 252) / daily_returns.std() * np.sqrt(252)
        else:
            sharpe = 0.0

        # Sortino
        downside = daily_returns[daily_returns < 0]
        if len(downside) > 0 and downside.std() > 0:
            sortino = (daily_returns.mean() - RISK_FREE_RATE / 252) / downside.std() * np.sqrt(252)
        else:
            sortino = 0.0

        # Max drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        max_dd = drawdown.min()

        # Monthly returns
        monthly = {}
        for i, d in enumerate(self.dates):
            key = d.strftime("%Y-%m")
            if key not in monthly:
                monthly[key] = {"start_eq": self.equity[i]}
            monthly[key]["end_eq"] = self.equity[i + 1] if i + 1 < len(self.equity) else self.equity[-1]

        monthly_rets = {}
        for k, v in monthly.items():
            monthly_rets[k] = round((v["end_eq"] / v["start_eq"] - 1) * 100, 2)

        return {
            "name": self.name,
            "description": self.description,
            "final_equity": round(equity[-1], 2),
            "total_return_pct": round(total_return * 100, 2),
            "annualized_return_pct": round(ann_return * 100, 2),
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "n_trading_days": n_days,
            "monthly_returns": monthly_rets,
        }


# ── STRATEGY IMPLEMENTATIONS ───────────────────────────────────────────────

def run_momentum(prices: pd.DataFrame) -> Strategy:
    """Momentum: Buy top 3 performers over last 20 days, short bottom 3. Rebalance weekly."""
    strat = Strategy("Momentum", "Long top-3 / short bottom-3 by 20-day return, weekly rebalance")

    returns_20d = prices.pct_change(20)
    equity = INITIAL_CAPITAL
    positions = {}  # ticker -> (shares, direction)
    last_rebalance = None

    for i in range(21, len(prices)):
        date = prices.index[i]
        strat.dates.append(date)

        # Check if we should rebalance (weekly = every 5 trading days)
        should_rebalance = last_rebalance is None or (i - last_rebalance) >= 5

        if should_rebalance:
            # Close all positions first
            equity_now = equity
            for ticker, (shares, direction) in positions.items():
                if ticker in prices.columns:
                    price_now = prices[ticker].iloc[i]
                    price_entry = prices[ticker].iloc[i - 1] if i > 0 else price_now
                    # Just mark to market

            # Rank by 20-day momentum
            mom = returns_20d.iloc[i].dropna().sort_values(ascending=False)
            if len(mom) >= 6:
                top3 = mom.head(3).index.tolist()
                bottom3 = mom.tail(3).index.tolist()
            else:
                strat.equity.append(equity)
                continue

            # Allocate equally: 1/6 of equity per position
            alloc = equity / 6.0
            positions = {}
            for t in top3:
                price = prices[t].iloc[i]
                shares = alloc / price
                positions[t] = (shares, 1)  # long
            for t in bottom3:
                price = prices[t].iloc[i]
                shares = alloc / price
                positions[t] = (shares, -1)  # short

            last_rebalance = i

        # Mark to market
        pnl = 0
        for ticker, (shares, direction) in positions.items():
            if ticker in prices.columns:
                ret_1d = (prices[ticker].iloc[i] / prices[ticker].iloc[i - 1]) - 1
                pnl += shares * prices[ticker].iloc[i - 1] * ret_1d * direction

        equity += pnl
        equity = max(equity, 0)  # can't go below 0
        strat.equity.append(equity)

    return strat


def run_mean_reversion(prices: pd.DataFrame) -> Strategy:
    """Mean Reversion: Buy 3 most oversold (RSI<30), short 3 most overbought (RSI>70). Daily."""
    strat = Strategy("Mean Reversion", "Long RSI<30, short RSI>70, daily rebalance")

    # Precompute RSI for all tickers
    rsi_all = pd.DataFrame()
    for t in prices.columns:
        rsi_all[t] = compute_rsi(prices[t])

    equity = INITIAL_CAPITAL

    for i in range(15, len(prices)):
        date = prices.index[i]
        strat.dates.append(date)

        rsi_today = rsi_all.iloc[i].dropna()

        oversold = rsi_today[rsi_today < 30].nsmallest(3)
        overbought = rsi_today[rsi_today > 70].nlargest(3)

        n_positions = len(oversold) + len(overbought)
        if n_positions == 0:
            strat.equity.append(equity)
            continue

        alloc = equity / max(n_positions, 1)
        pnl = 0

        if i + 1 < len(prices):
            for t in oversold.index:
                ret = (prices[t].iloc[i + 1] / prices[t].iloc[i]) - 1 if i + 1 < len(prices) else 0
                pnl += alloc * ret  # long
            for t in overbought.index:
                ret = (prices[t].iloc[i + 1] / prices[t].iloc[i]) - 1 if i + 1 < len(prices) else 0
                pnl -= alloc * ret  # short

        equity += pnl
        equity = max(equity, 0)
        strat.equity.append(equity)

    return strat


def run_sector_rotation(prices: pd.DataFrame) -> Strategy:
    """Sector Rotation: Monthly, go 100% into best-performing sector ETF."""
    strat = Strategy("Sector Rotation", "100% into best sector ETF, monthly rebalance")

    sector_etfs = [t for t in ["XLK", "XLF", "XLE", "XLV", "XLI", "XLU", "XLRE", "XLC"]
                   if t in prices.columns]

    equity = INITIAL_CAPITAL
    current_etf = None
    shares = 0
    last_month = None

    for i in range(21, len(prices)):
        date = prices.index[i]
        strat.dates.append(date)

        current_month = date.strftime("%Y-%m")

        if current_month != last_month:
            # Sell current position
            if current_etf and current_etf in prices.columns:
                equity = shares * prices[current_etf].iloc[i]

            # Find best performing sector over last 20 days
            perfs = {}
            for t in sector_etfs:
                if i >= 20:
                    perfs[t] = prices[t].iloc[i] / prices[t].iloc[i - 20] - 1

            if perfs:
                best = max(perfs, key=perfs.get)
                current_etf = best
                shares = equity / prices[best].iloc[i]

            last_month = current_month
        else:
            # Mark to market
            if current_etf and current_etf in prices.columns:
                equity = shares * prices[current_etf].iloc[i]

        strat.equity.append(max(equity, 0))

    return strat


def run_safe_haven(prices: pd.DataFrame) -> Strategy:
    """Safe Haven: 60% GLD + 30% TLT + 10% SHY when vol>20%, else 100% SPY."""
    strat = Strategy("Safe Haven", "Risk-on SPY / risk-off GLD+TLT+SHY based on realized vol")

    spy_vol = compute_realized_vol(prices["SPY"]) if "SPY" in prices.columns else None
    if spy_vol is None:
        return strat

    equity = INITIAL_CAPITAL

    for i in range(21, len(prices)):
        date = prices.index[i]
        strat.dates.append(date)

        vol = spy_vol.iloc[i]

        if i < 1:
            strat.equity.append(equity)
            continue

        if pd.isna(vol):
            strat.equity.append(equity)
            continue

        pnl = 0
        if vol > 0.20:  # High vol = risk-off
            for ticker, weight in [("GLD", 0.60), ("TLT", 0.30), ("SHY", 0.10)]:
                if ticker in prices.columns:
                    ret = prices[ticker].iloc[i] / prices[ticker].iloc[i - 1] - 1
                    pnl += equity * weight * ret
        else:  # Low vol = risk-on
            if "SPY" in prices.columns:
                ret = prices["SPY"].iloc[i] / prices["SPY"].iloc[i - 1] - 1
                pnl += equity * ret

        equity += pnl
        equity = max(equity, 0)
        strat.equity.append(equity)

    return strat


def run_pairs_trading(prices: pd.DataFrame) -> Strategy:
    """Pairs Trading: Trade SPY-QQQ spread when z-score > 2 or < -2."""
    strat = Strategy("Pairs Trading", "SPY-QQQ spread, z-score entry at +/-2")

    if "SPY" not in prices.columns or "QQQ" not in prices.columns:
        return strat

    # Compute log price ratio
    spread = np.log(prices["SPY"] / prices["QQQ"])
    zscore = compute_zscore(spread, window=20)

    equity = INITIAL_CAPITAL
    position = 0  # +1 = long spread, -1 = short spread, 0 = flat

    for i in range(21, len(prices)):
        date = prices.index[i]
        strat.dates.append(date)

        z = zscore.iloc[i]

        if pd.isna(z):
            strat.equity.append(equity)
            continue

        # Entry signals
        if position == 0:
            if z > 2:
                position = -1  # Short spread (short SPY, long QQQ)
            elif z < -2:
                position = 1   # Long spread (long SPY, short QQQ)
        elif position == 1 and z > 0:
            position = 0  # Mean reversion complete
        elif position == -1 and z < 0:
            position = 0

        if position != 0:
            spy_ret = prices["SPY"].iloc[i] / prices["SPY"].iloc[i - 1] - 1
            qqq_ret = prices["QQQ"].iloc[i] / prices["QQQ"].iloc[i - 1] - 1

            # Half equity each side
            half = equity * 0.5
            if position == 1:  # Long SPY, short QQQ
                pnl = half * spy_ret - half * qqq_ret
            else:  # Short SPY, long QQQ
                pnl = -half * spy_ret + half * qqq_ret

            equity += pnl
            equity = max(equity, 0)

        strat.equity.append(equity)

    return strat


def run_vol_scaled(prices: pd.DataFrame) -> Strategy:
    """Vol Scaled: Kelly-size positions inversely proportional to 20-day realized volatility."""
    strat = Strategy("Vol Scaled", "Position size inversely proportional to realized vol, target 15%")

    TARGET_VOL = 0.15  # Target 15% annualized vol

    # Use a diversified basket
    basket = [t for t in ["SPY", "QQQ", "XLK", "XLF", "GLD"] if t in prices.columns]

    if not basket:
        return strat

    vols = {}
    for t in basket:
        vols[t] = compute_realized_vol(prices[t])

    equity = INITIAL_CAPITAL

    for i in range(21, len(prices)):
        date = prices.index[i]
        strat.dates.append(date)

        pnl = 0
        n_valid = 0

        for t in basket:
            vol = vols[t].iloc[i]
            if pd.isna(vol) or vol <= 0:
                continue

            # Scale position: target_vol / realized_vol, capped at 2x
            scale = min(TARGET_VOL / vol, 2.0)
            weight = scale / len(basket)

            ret = prices[t].iloc[i] / prices[t].iloc[i - 1] - 1
            pnl += equity * weight * ret
            n_valid += 1

        equity += pnl
        equity = max(equity, 0)
        strat.equity.append(equity)

    return strat


def run_buy_hold_spy(prices: pd.DataFrame) -> Strategy:
    """Buy & Hold SPY: Baseline benchmark."""
    strat = Strategy("Buy & Hold SPY", "100% SPY from day 1 — baseline benchmark")

    if "SPY" not in prices.columns:
        return strat

    # Start from day 21 to align with other strategies
    start_price = prices["SPY"].iloc[21]

    for i in range(21, len(prices)):
        date = prices.index[i]
        strat.dates.append(date)
        equity = INITIAL_CAPITAL * (prices["SPY"].iloc[i] / start_price)
        strat.equity.append(equity)

    return strat


def run_equal_weight(prices: pd.DataFrame) -> Strategy:
    """Equal Weight: Equal allocation across all ETFs, monthly rebalance."""
    strat = Strategy("Equal Weight", "Equal allocation across all 20 ETFs, monthly rebalance")

    tickers = list(prices.columns)
    n = len(tickers)

    equity = INITIAL_CAPITAL
    holdings = {}  # ticker -> shares
    last_month = None

    for i in range(21, len(prices)):
        date = prices.index[i]
        strat.dates.append(date)

        current_month = date.strftime("%Y-%m")

        if current_month != last_month:
            # Rebalance: mark to market first
            if holdings:
                equity = sum(holdings.get(t, 0) * prices[t].iloc[i]
                            for t in tickers if t in holdings)

            # Equal weight allocation
            alloc = equity / n
            holdings = {}
            for t in tickers:
                holdings[t] = alloc / prices[t].iloc[i]

            last_month = current_month

        # Mark to market
        equity = sum(holdings.get(t, 0) * prices[t].iloc[i] for t in tickers if t in holdings)
        strat.equity.append(max(equity, 0))

    return strat


# ── MAIN ────────────────────────────────────────────────────────────────────
def main():
    print("=" * 80)
    print("  REAL POLITICAL TRADING BACKTEST")
    print("  Using actual ETF/Index prices from yfinance")
    print("=" * 80)
    print()

    # Download data
    prices = download_prices()
    print()

    # Show price summary
    first_prices = prices.iloc[0]
    last_prices = prices.iloc[-1]
    print("Market Performance (period total return):")
    perf = ((last_prices / first_prices) - 1) * 100
    perf_sorted = perf.sort_values(ascending=False)
    for t in perf_sorted.index:
        print(f"  {t:5s} ({TICKERS.get(t, ''):18s}): {perf_sorted[t]:+7.2f}%")
    print()

    # Run all strategies
    print("Running 8 trading strategies...")
    strategies = [
        run_momentum(prices),
        run_mean_reversion(prices),
        run_sector_rotation(prices),
        run_safe_haven(prices),
        run_pairs_trading(prices),
        run_vol_scaled(prices),
        run_buy_hold_spy(prices),
        run_equal_weight(prices),
    ]

    # Compute metrics
    results = []
    for s in strategies:
        if len(s.equity) > 1:
            metrics = s.get_metrics()
            results.append(metrics)
            print(f"  {s.name:20s}: ${metrics['final_equity']:>12,.2f} | Return: {metrics['total_return_pct']:+7.2f}%")

    # Sort by Sharpe ratio
    results.sort(key=lambda x: x["sharpe_ratio"], reverse=True)

    print()
    print("=" * 100)
    print("  CONFRONTATION TABLE — Sorted by Sharpe Ratio")
    print("=" * 100)
    print(f"  {'#':>2s}  {'Strategy':20s}  {'Final Equity':>14s}  {'Return':>8s}  {'Ann.Ret':>8s}  "
          f"{'Sharpe':>7s}  {'Sortino':>8s}  {'MaxDD':>7s}")
    print("-" * 100)

    for rank, r in enumerate(results, 1):
        medal = ""
        if rank == 1: medal = " [CHAMPION]"
        elif rank == 2: medal = " [2nd]"
        elif rank == 3: medal = " [3rd]"

        print(f"  {rank:2d}  {r['name']:20s}  ${r['final_equity']:>12,.2f}  "
              f"{r['total_return_pct']:>+7.2f}%  {r['annualized_return_pct']:>+7.2f}%  "
              f"{r['sharpe_ratio']:>7.3f}  {r['sortino_ratio']:>8.3f}  "
              f"{r['max_drawdown_pct']:>6.2f}%{medal}")

    print("-" * 100)
    print()

    # Monthly returns breakdown for champion
    champion = results[0]
    print(f"CHAMPION: {champion['name']}")
    print(f"  Description: {champion['description']}")
    print(f"  Monthly Returns:")
    for month, ret in sorted(champion["monthly_returns"].items()):
        bar = "+" * int(abs(ret)) if ret > 0 else "-" * int(abs(ret))
        print(f"    {month}: {ret:+6.2f}%  {bar}")
    print()

    # Compare to SPY benchmark
    spy_result = next((r for r in results if r["name"] == "Buy & Hold SPY"), None)
    if spy_result:
        print(f"SPY BENCHMARK: {spy_result['total_return_pct']:+.2f}% total return, "
              f"Sharpe {spy_result['sharpe_ratio']:.3f}")
        print()
        print("Strategies beating SPY benchmark:")
        for r in results:
            if r["name"] != "Buy & Hold SPY" and r["total_return_pct"] > spy_result["total_return_pct"]:
                alpha = r["total_return_pct"] - spy_result["total_return_pct"]
                print(f"  {r['name']:20s}: {r['total_return_pct']:+.2f}% (alpha: +{alpha:.2f}%)")

    # Save results
    output = {
        "backtest": {
            "start_date": START_DATE,
            "end_date": END_DATE,
            "initial_capital": INITIAL_CAPITAL,
            "n_tickers": len(prices.columns),
            "n_trading_days": len(prices),
            "tickers": list(prices.columns),
            "data_source": "yfinance (real prices)",
        },
        "market_performance": {t: round(float(perf[t]), 2) for t in perf.index},
        "strategies": results,
        "champion": champion["name"],
        "generated_at": datetime.now().isoformat(),
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"\nResults saved to: {OUTPUT_FILE}")
    print("=" * 80)


if __name__ == "__main__":
    main()
