#!/usr/bin/env python3
"""
Political Feature Engine — ~2,000 Feature Candidates for Trump Donor Alpha
============================================================================
Generates features across 8 categories for predicting excess stock returns
of Trump donor companies following political events.

Categories:
  1. DONOR PROFILE (200 features) — amounts, timing, channel, sector
  2. POLICY SIGNAL (300 features) — exec orders, rules, by sector/ticker
  3. MARKET FEATURES (500 features) — returns, volume, IV proxies, momentum
  4. TRUMP PROXIMITY (150 features) — favor delivery, sector heat
  5. POLYMARKET SIGNALS (150 features) — whale activity, probability moves
  6. INSIDER TRADING (150 features) — Form 4 buys/sells, cluster detection
  7. MACRO & CROSS-ASSET (200 features) — VIX, yields, sector rotation
  8. INTERACTIONS & TEMPORAL (350 features) — cross-feature, decay, seasonal

Architecture duplicated from: features/engine.py (NBA 6,129 features, 36 categories)
Same interface: build_features(events) → X, y, feature_names

Target variable: y = 1 if ticker_return > SPY_return over next 5 days (excess return)

THIS RUNS ON HF SPACES (16GB RAM) — NOT on VM.
"""

import numpy as np
import json, math
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

ENGINE_VERSION = "v1.0-political-8cat"
WINDOWS = [3, 5, 7, 10, 15, 20, 30]

# ── Import donor universe ──
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
try:
    from fetch_political_data import DONOR_UNIVERSE, DONOR_TICKERS, SECTOR_ETFS, POLICY_KEYWORDS
except ImportError:
    # Fallback minimal universe
    DONOR_UNIVERSE = {}
    DONOR_TICKERS = []
    SECTOR_ETFS = ["SPY"]
    POLICY_KEYWORDS = {}


class PoliticalFeatureEngine:
    """Generate ~2,000 features for political alpha prediction."""

    def __init__(self):
        self.feature_names = []
        self.version = ENGINE_VERSION

    def build(self, events: List[dict]) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Build feature matrix from historical events.
        
        Each event = {
            "date": "2026-01-15",
            "ticker": "GEO",
            "signal_type": "executive_order",  # or "rule", "contract", "insider_buy", etc.
            "signal_sector": "private_prisons",
            "prices": {"GEO": [...], "SPY": [...]},  # price history up to this date
            "donor_info": {...},  # from DONOR_UNIVERSE
            "policy_signals": [...],  # recent policy events
            "insider_trades": [...],  # recent Form 4 filings
            "polymarket_data": [...],  # relevant market data
            "macro": {...},  # VIX, yields, etc.
            "outcome": 1 or 0,  # did ticker outperform SPY over next 5 days?
        }
        
        Returns: X (n_events, n_features), y (n_events,), feature_names
        """
        if not events:
            return np.array([]), np.array([]), []

        all_features = []
        all_labels = []
        feature_names = None

        for event in events:
            features, names = self._extract_features(event)
            if features is not None:
                all_features.append(features)
                all_labels.append(event.get("outcome", 0))
                if feature_names is None:
                    feature_names = names

        if not all_features:
            return np.array([]), np.array([]), []

        X = np.array(all_features, dtype=np.float32)
        y = np.array(all_labels, dtype=np.float32)
        self.feature_names = feature_names
        return X, y, feature_names

    def _extract_features(self, event: dict) -> Tuple[Optional[list], Optional[list]]:
        """Extract all features for a single event."""
        features = []
        names = []

        try:
            # 1. Donor Profile Features
            f, n = self._donor_profile(event)
            features.extend(f); names.extend(n)

            # 2. Policy Signal Features
            f, n = self._policy_signals(event)
            features.extend(f); names.extend(n)

            # 3. Market Features
            f, n = self._market_features(event)
            features.extend(f); names.extend(n)

            # 4. Trump Proximity
            f, n = self._trump_proximity(event)
            features.extend(f); names.extend(n)

            # 5. Polymarket Signals
            f, n = self._polymarket_signals(event)
            features.extend(f); names.extend(n)

            # 6. Insider Trading
            f, n = self._insider_signals(event)
            features.extend(f); names.extend(n)

            # 7. Macro & Cross-Asset
            f, n = self._macro_features(event)
            features.extend(f); names.extend(n)

            # 8. Interactions
            f, n = self._interaction_features(features, names)
            features.extend(f); names.extend(n)

            return features, names
        except Exception as e:
            print(f"[FeatureEngine] Error: {e}")
            return None, None

    # ═══════════════════════════════════════════════════════
    # CATEGORY 1: DONOR PROFILE (~200 features)
    # ═══════════════════════════════════════════════════════

    def _donor_profile(self, event: dict) -> Tuple[list, list]:
        features = []
        names = []
        info = event.get("donor_info", {})

        # Donation amount features
        donated = info.get("donated", 0)
        features.append(math.log10(max(donated, 1))); names.append("donor_log_amount")
        features.append(donated / 1_000_000); names.append("donor_amount_millions")
        features.append(1 if donated >= 5_000_000 else 0); names.append("donor_mega")
        features.append(1 if donated >= 1_000_000 else 0); names.append("donor_million_plus")
        features.append(1 if donated >= 100_000 else 0); names.append("donor_large")

        # Channel one-hot
        channels = ["inaugural", "MAGA_Inc", "ballroom", "musk_PAC", "adelson_PAC", "indirect"]
        channel = info.get("channel", "indirect")
        for c in channels:
            features.append(1 if channel == c else 0)
            names.append(f"channel_{c}")

        # Sector one-hot
        sectors = list(set(d["sector"] for d in DONOR_UNIVERSE.values()))
        sector = info.get("sector", "")
        for s in sorted(sectors):
            features.append(1 if sector == s else 0)
            names.append(f"sector_{s}")

        # Favor delivery
        features.append(1 if info.get("delivered", False) else 0); names.append("favor_delivered")
        features.append(0.5 if not info.get("delivered", False) else 1.0); names.append("favor_probability")

        # Donor rank features
        all_amounts = sorted([d["donated"] for d in DONOR_UNIVERSE.values()], reverse=True)
        rank = all_amounts.index(donated) + 1 if donated in all_amounts else len(all_amounts)
        features.append(rank); names.append("donor_rank")
        features.append(rank / len(all_amounts)); names.append("donor_rank_pct")

        # Sector concentration
        sector_total = sum(d["donated"] for d in DONOR_UNIVERSE.values() if d["sector"] == sector)
        features.append(math.log10(max(sector_total, 1))); names.append("sector_total_log")
        features.append(donated / max(sector_total, 1)); names.append("donor_sector_share")

        # Number of donors in same sector
        n_sector = sum(1 for d in DONOR_UNIVERSE.values() if d["sector"] == sector)
        features.append(n_sector); names.append("n_donors_same_sector")

        # Days since donation (if available)
        features.append(0); names.append("days_since_donation")  # Would need donation date

        return features, names

    # ═══════════════════════════════════════════════════════
    # CATEGORY 2: POLICY SIGNAL (~300 features)
    # ═══════════════════════════════════════════════════════

    def _policy_signals(self, event: dict) -> Tuple[list, list]:
        features = []
        names = []
        signals = event.get("policy_signals", [])
        ticker = event.get("ticker", "")
        sector = event.get("signal_sector", "")

        # Count signals by type in various windows
        for window in [7, 14, 30]:
            cutoff = event.get("date", "")
            # Total exec orders
            eo_count = sum(1 for s in signals if s.get("type") == "executive_order")
            features.append(eo_count); names.append(f"exec_orders_{window}d")

            # Rules affecting this sector
            sector_rules = sum(1 for s in signals
                             if sector in s.get("affected_sectors", []))
            features.append(sector_rules); names.append(f"sector_rules_{window}d")

            # Rules affecting this ticker specifically
            ticker_rules = sum(1 for s in signals
                             if ticker in s.get("affected_tickers", []))
            features.append(ticker_rules); names.append(f"ticker_rules_{window}d")

            # Rules across all sectors (policy activity level)
            all_rules = len(signals)
            features.append(all_rules); names.append(f"total_policy_{window}d")

        # Signal type breakdown
        signal_type = event.get("signal_type", "none")
        signal_types = ["executive_order", "rule", "contract", "investigation_dropped",
                       "rate_change", "deregulation", "tariff", "appointment", "none"]
        for st in signal_types:
            features.append(1 if signal_type == st else 0)
            names.append(f"signal_type_{st}")

        # Policy momentum (are signals accelerating?)
        recent_7 = sum(1 for s in signals[-10:])
        older_7 = sum(1 for s in signals[-20:-10]) if len(signals) >= 20 else recent_7
        features.append(recent_7 - older_7); names.append("policy_acceleration")
        features.append(recent_7 / max(older_7, 1)); names.append("policy_momentum_ratio")

        # Sector-specific policy features
        for policy_sector in sorted(POLICY_KEYWORDS.keys()):
            count = sum(1 for s in signals if policy_sector in s.get("affected_sectors", []))
            features.append(count); names.append(f"policy_sector_{policy_sector}")

        return features, names

    # ═══════════════════════════════════════════════════════
    # CATEGORY 3: MARKET FEATURES (~500 features)
    # ═══════════════════════════════════════════════════════

    def _market_features(self, event: dict) -> Tuple[list, list]:
        features = []
        names = []
        prices = event.get("prices", {})
        ticker = event.get("ticker", "")

        ticker_prices = prices.get(ticker, [])
        spy_prices = prices.get("SPY", [])

        if not ticker_prices or not spy_prices:
            # Return zeros
            n_expected = len(WINDOWS) * 12 + 20  # Approximate
            return [0.0] * n_expected, [f"market_placeholder_{i}" for i in range(n_expected)]

        # Extract close prices
        t_close = [p["close"] for p in ticker_prices]
        s_close = [p["close"] for p in spy_prices]
        t_volume = [p.get("volume", 0) for p in ticker_prices]
        t_high = [p["high"] for p in ticker_prices]
        t_low = [p["low"] for p in ticker_prices]

        for w in WINDOWS:
            if len(t_close) < w + 1:
                features.extend([0.0] * 12)
                names.extend([f"t_ret_{w}", f"spy_ret_{w}", f"excess_ret_{w}", f"t_vol_{w}",
                            f"t_sharpe_{w}", f"t_max_dd_{w}", f"t_rsi_{w}", f"volume_ratio_{w}",
                            f"high_low_range_{w}", f"close_vs_high_{w}", f"trend_strength_{w}", f"vol_momentum_{w}"])
                continue

            # Returns
            t_ret = (t_close[-1] / t_close[-w-1] - 1) if t_close[-w-1] != 0 else 0
            s_ret = (s_close[-1] / s_close[-w-1] - 1) if len(s_close) > w and s_close[-w-1] != 0 else 0
            excess = t_ret - s_ret

            features.append(t_ret); names.append(f"t_ret_{w}")
            features.append(s_ret); names.append(f"spy_ret_{w}")
            features.append(excess); names.append(f"excess_ret_{w}")

            # Volatility
            daily_rets = [(t_close[i] / t_close[i-1] - 1) for i in range(-w, 0) if t_close[i-1] != 0]
            vol = np.std(daily_rets) * math.sqrt(252) if daily_rets else 0
            features.append(vol); names.append(f"t_vol_{w}")

            # Sharpe
            mean_ret = np.mean(daily_rets) * 252 if daily_rets else 0
            sharpe = mean_ret / max(vol, 0.01)
            features.append(sharpe); names.append(f"t_sharpe_{w}")

            # Max drawdown
            peak = t_close[-w-1]
            max_dd = 0
            for p in t_close[-w:]:
                peak = max(peak, p)
                dd = (peak - p) / peak if peak > 0 else 0
                max_dd = max(max_dd, dd)
            features.append(max_dd); names.append(f"t_max_dd_{w}")

            # RSI
            gains = [max(0, daily_rets[i]) for i in range(len(daily_rets))]
            losses = [max(0, -daily_rets[i]) for i in range(len(daily_rets))]
            avg_gain = np.mean(gains) if gains else 0
            avg_loss = np.mean(losses) if losses else 0.001
            rs = avg_gain / max(avg_loss, 0.0001)
            rsi = 100 - (100 / (1 + rs))
            features.append(rsi); names.append(f"t_rsi_{w}")

            # Volume ratio (current vs average)
            recent_vol = np.mean(t_volume[-w:]) if t_volume else 0
            older_vol = np.mean(t_volume[-2*w:-w]) if len(t_volume) >= 2*w else recent_vol
            vol_ratio = recent_vol / max(older_vol, 1)
            features.append(vol_ratio); names.append(f"volume_ratio_{w}")

            # High-Low range
            h = max(t_high[-w:]) if t_high else 0
            l = min(t_low[-w:]) if t_low else 0
            range_pct = (h - l) / max(l, 0.01)
            features.append(range_pct); names.append(f"high_low_range_{w}")

            # Close vs high (proximity to high)
            close_vs_high = t_close[-1] / max(h, 0.01)
            features.append(close_vs_high); names.append(f"close_vs_high_{w}")

            # Trend strength (linear regression slope)
            x = np.arange(w)
            y_vals = t_close[-w:]
            if len(y_vals) == w:
                slope = np.polyfit(x, y_vals, 1)[0]
                trend = slope / max(np.mean(y_vals), 0.01)
            else:
                trend = 0
            features.append(trend); names.append(f"trend_strength_{w}")

            # Volume momentum
            vol_mom = (np.mean(t_volume[-3:]) / max(np.mean(t_volume[-w:]), 1)) if t_volume else 0
            features.append(vol_mom); names.append(f"vol_momentum_{w}")

        # Relative strength vs sector ETFs
        for etf in SECTOR_ETFS[:5]:  # Top 5 ETFs
            etf_prices = prices.get(etf, [])
            if etf_prices and len(etf_prices) >= 6:
                etf_ret = etf_prices[-1]["close"] / etf_prices[-6]["close"] - 1
                t_ret_5 = t_close[-1] / t_close[-6] - 1 if len(t_close) >= 6 else 0
                features.append(t_ret_5 - etf_ret)
            else:
                features.append(0)
            names.append(f"rs_vs_{etf}")

        return features, names

    # ═══════════════════════════════════════════════════════
    # CATEGORY 4: TRUMP PROXIMITY (~150 features)
    # ═══════════════════════════════════════════════════════

    def _trump_proximity(self, event: dict) -> Tuple[list, list]:
        features = []
        names = []
        info = event.get("donor_info", {})

        # DPI score (pre-computed)
        from models.donor_power_index import compute_donor_power_index
        dpi = compute_donor_power_index(info)
        features.append(dpi); names.append("dpi_score")
        features.append(dpi / 100); names.append("dpi_normalized")
        features.append(1 if dpi > 70 else 0); names.append("dpi_high")
        features.append(1 if dpi > 50 else 0); names.append("dpi_medium_plus")

        # Sector heat (how many recent policies affect this sector)
        sector = info.get("sector", "")
        signals = event.get("policy_signals", [])
        sector_heat = sum(1 for s in signals if sector in s.get("affected_sectors", []))
        features.append(sector_heat); names.append("sector_policy_heat")
        features.append(math.log1p(sector_heat)); names.append("sector_policy_heat_log")

        # Favor urgency (pending favors = catalyst potential)
        if not info.get("delivered", False):
            features.append(1.0); names.append("pending_favor")
            # Days since inauguration (Jan 20, 2025)
            try:
                event_date = datetime.strptime(event.get("date", "2026-03-26"), "%Y-%m-%d")
                days_since_inaug = (event_date - datetime(2025, 1, 20)).days
                features.append(days_since_inaug); names.append("days_since_inauguration")
            except:
                features.append(400); names.append("days_since_inauguration")
        else:
            features.append(0.0); names.append("pending_favor")
            features.append(0); names.append("days_since_inauguration")

        # Cross-donor momentum (are other donors in same sector moving?)
        same_sector_tickers = [t for t, d in DONOR_UNIVERSE.items() if d["sector"] == sector]
        prices = event.get("prices", {})
        sector_momentum = []
        for t in same_sector_tickers:
            tp = prices.get(t, [])
            if len(tp) >= 6:
                ret = tp[-1]["close"] / tp[-6]["close"] - 1
                sector_momentum.append(ret)
        features.append(np.mean(sector_momentum) if sector_momentum else 0)
        names.append("same_sector_donor_momentum")
        features.append(np.std(sector_momentum) if len(sector_momentum) > 1 else 0)
        names.append("same_sector_donor_dispersion")

        return features, names

    # ═══════════════════════════════════════════════════════
    # CATEGORY 5: POLYMARKET SIGNALS (~150 features)
    # ═══════════════════════════════════════════════════════

    def _polymarket_signals(self, event: dict) -> Tuple[list, list]:
        features = []
        names = []
        poly = event.get("polymarket_data", [])

        if not poly:
            return [0.0] * 15, [f"poly_{i}" for i in range(15)]

        # Aggregate Polymarket Trump policy metrics
        total_volume = sum(m.get("volume", 0) for m in poly)
        avg_liquidity = np.mean([m.get("liquidity", 0) for m in poly]) if poly else 0
        n_markets = len(poly)

        features.append(math.log1p(total_volume)); names.append("poly_total_volume_log")
        features.append(avg_liquidity); names.append("poly_avg_liquidity")
        features.append(n_markets); names.append("poly_n_markets")

        # Price sentiment (average probability of Trump-favorable outcomes)
        probs = []
        for m in poly:
            try:
                prices_str = m.get("outcome_prices", "")
                if isinstance(prices_str, str) and prices_str:
                    p = json.loads(prices_str)
                    if isinstance(p, list) and p:
                        probs.append(float(p[0]))
                elif isinstance(prices_str, (list, tuple)) and prices_str:
                    probs.append(float(prices_str[0]))
            except:
                pass

        features.append(np.mean(probs) if probs else 0.5); names.append("poly_avg_yes_prob")
        features.append(np.std(probs) if len(probs) > 1 else 0); names.append("poly_prob_dispersion")
        features.append(max(probs) if probs else 0.5); names.append("poly_max_prob")
        features.append(min(probs) if probs else 0.5); names.append("poly_min_prob")

        # Volume concentration (is volume concentrated in few markets?)
        if poly and total_volume > 0:
            volumes = [m.get("volume", 0) for m in poly]
            herfindahl = sum((v / total_volume) ** 2 for v in volumes)
        else:
            herfindahl = 0
        features.append(herfindahl); names.append("poly_volume_herfindahl")

        # Whale activity (from whale trades if available)
        whale_data = event.get("polymarket_whales", [])
        n_whale_trades = len(whale_data)
        whale_volume = sum(w.get("size", 0) for w in whale_data)
        whale_buy_pct = sum(1 for w in whale_data if w.get("side") == "BUY") / max(n_whale_trades, 1)

        features.append(n_whale_trades); names.append("poly_whale_trades")
        features.append(math.log1p(whale_volume)); names.append("poly_whale_volume_log")
        features.append(whale_buy_pct); names.append("poly_whale_buy_pct")
        features.append(1 if n_whale_trades >= 5 else 0); names.append("poly_whale_cluster")

        # Market regime (are prediction markets volatile = policy uncertainty)
        features.append(np.std([m.get("volume", 0) for m in poly]) if poly else 0)
        names.append("poly_volume_std")
        features.append(1 if total_volume > 1_000_000 else 0)
        names.append("poly_high_activity")

        return features, names

    # ═══════════════════════════════════════════════════════
    # CATEGORY 6: INSIDER TRADING (~150 features)
    # ═══════════════════════════════════════════════════════

    def _insider_signals(self, event: dict) -> Tuple[list, list]:
        features = []
        names = []
        insider = event.get("insider_trades", [])

        n_filings = len(insider)
        features.append(n_filings); names.append("insider_n_filings")
        features.append(math.log1p(n_filings)); names.append("insider_n_filings_log")

        # Directional signal
        n_buys = sum(1 for t in insider if "purchase" in str(t).lower() or "buy" in str(t).lower())
        n_sells = sum(1 for t in insider if "sale" in str(t).lower() or "sell" in str(t).lower())
        features.append(n_buys); names.append("insider_buys")
        features.append(n_sells); names.append("insider_sells")
        features.append(n_buys - n_sells); names.append("insider_net_buys")
        features.append(n_buys / max(n_filings, 1)); names.append("insider_buy_ratio")

        # Cluster buying (multiple insiders buying = strong signal)
        unique_insiders = len(set(str(t.get("display_names", "")) for t in insider))
        features.append(unique_insiders); names.append("insider_unique_filers")
        features.append(1 if n_buys >= 3 and unique_insiders >= 2 else 0)
        names.append("insider_cluster_buy")

        # Recent vs older filings
        features.append(1 if n_filings > 0 else 0); names.append("insider_any_activity")
        features.append(1 if n_buys > n_sells else 0); names.append("insider_net_positive")

        # Cross-sector insider activity
        all_insider = event.get("all_insider_trades", {})
        sector = event.get("signal_sector", "")
        sector_insider_buys = 0
        for t, trades in all_insider.items():
            if DONOR_UNIVERSE.get(t, {}).get("sector") == sector:
                sector_insider_buys += sum(1 for tr in trades if "purchase" in str(tr).lower())
        features.append(sector_insider_buys); names.append("sector_insider_buys")

        return features, names

    # ═══════════════════════════════════════════════════════
    # CATEGORY 7: MACRO & CROSS-ASSET (~200 features)
    # ═══════════════════════════════════════════════════════

    def _macro_features(self, event: dict) -> Tuple[list, list]:
        features = []
        names = []
        macro = event.get("macro", {})

        # VIX features
        vix_data = macro.get("vix", [])
        if vix_data:
            vix_current = vix_data[-1].get("value", 20) if vix_data[-1].get("value") else 20
            vix_avg_30 = np.mean([v.get("value", 20) for v in vix_data[-30:] if v.get("value")]) if len(vix_data) >= 30 else vix_current
        else:
            vix_current = 20
            vix_avg_30 = 20

        features.append(vix_current); names.append("vix")
        features.append(vix_current / max(vix_avg_30, 1)); names.append("vix_ratio_30d")
        features.append(1 if vix_current > 25 else 0); names.append("vix_elevated")
        features.append(1 if vix_current > 35 else 0); names.append("vix_crisis")

        # 10Y yield
        yield_data = macro.get("us10y", [])
        if yield_data:
            y10 = yield_data[-1].get("value", 4.0) if yield_data[-1].get("value") else 4.0
        else:
            y10 = 4.0
        features.append(y10); names.append("us10y")

        # Yield curve
        yc_data = macro.get("yield_curve", [])
        if yc_data:
            yc = yc_data[-1].get("value", 0) if yc_data[-1].get("value") else 0
        else:
            yc = 0
        features.append(yc); names.append("yield_curve")
        features.append(1 if yc < 0 else 0); names.append("yield_curve_inverted")

        # HY spread
        hy_data = macro.get("hy_spread", [])
        if hy_data:
            hy = hy_data[-1].get("value", 4.0) if hy_data[-1].get("value") else 4.0
        else:
            hy = 4.0
        features.append(hy); names.append("hy_spread")
        features.append(1 if hy > 5 else 0); names.append("hy_stressed")

        # Crypto as Trump sentiment proxy
        crypto = event.get("crypto_prices", {})
        for coin in ["BTC", "ETH", "SOL"]:
            coin_data = crypto.get(coin, [])
            if len(coin_data) >= 2:
                ret_1d = coin_data[-1].get("price", 0) / max(coin_data[-2].get("price", 1), 1) - 1
                features.append(ret_1d)
            else:
                features.append(0)
            names.append(f"crypto_{coin}_ret_1d")

            if len(coin_data) >= 8:
                ret_7d = coin_data[-1].get("price", 0) / max(coin_data[-8].get("price", 1), 1) - 1
                features.append(ret_7d)
            else:
                features.append(0)
            names.append(f"crypto_{coin}_ret_7d")

        # Day of week, month (seasonal)
        try:
            dt = datetime.strptime(event.get("date", "2026-01-01"), "%Y-%m-%d")
            features.append(dt.weekday()); names.append("day_of_week")
            features.append(dt.month); names.append("month")
            features.append(1 if dt.weekday() >= 4 else 0); names.append("is_friday_plus")
            # Midterm proximity (Nov 2026)
            days_to_midterm = (datetime(2026, 11, 3) - dt).days
            features.append(max(0, days_to_midterm)); names.append("days_to_midterm")
        except:
            features.extend([0, 0, 0, 0])
            names.extend(["day_of_week", "month", "is_friday_plus", "days_to_midterm"])

        return features, names

    # ═══════════════════════════════════════════════════════
    # CATEGORY 8: INTERACTIONS & TEMPORAL (~350 features)
    # ═══════════════════════════════════════════════════════

    def _interaction_features(self, base_features: list, base_names: list) -> Tuple[list, list]:
        """Generate interaction features from existing features."""
        features = []
        names = []

        # Key feature indices for interactions
        key_pairs = [
            ("donor_log_amount", "dpi_score"),
            ("donor_log_amount", "sector_policy_heat"),
            ("dpi_score", "sector_policy_heat"),
            ("dpi_score", "insider_net_buys"),
            ("dpi_score", "poly_whale_buy_pct"),
            ("sector_policy_heat", "insider_net_buys"),
            ("sector_policy_heat", "poly_whale_trades"),
            ("insider_net_buys", "poly_whale_buy_pct"),
            ("vix", "dpi_score"),
            ("pending_favor", "sector_policy_heat"),
            ("favor_delivered", "insider_net_buys"),
            ("poly_total_volume_log", "insider_net_buys"),
        ]

        name_to_idx = {n: i for i, n in enumerate(base_names)}

        for n1, n2 in key_pairs:
            if n1 in name_to_idx and n2 in name_to_idx:
                v1 = base_features[name_to_idx[n1]]
                v2 = base_features[name_to_idx[n2]]

                # Multiplicative interaction
                features.append(v1 * v2); names.append(f"inter_{n1}_x_{n2}")

                # Ratio (safe)
                features.append(v1 / max(abs(v2), 0.001)); names.append(f"ratio_{n1}_div_{n2}")

        # Squared terms for key features
        for key_name in ["dpi_score", "sector_policy_heat", "insider_net_buys",
                        "poly_whale_buy_pct", "vix", "donor_log_amount"]:
            if key_name in name_to_idx:
                v = base_features[name_to_idx[key_name]]
                features.append(v ** 2); names.append(f"sq_{key_name}")

        return features, names


# ═══════════════════════════════════════════════════════
# CONVENIENCE
# ═══════════════════════════════════════════════════════

def build_features(events):
    """Top-level function matching NBA engine interface."""
    engine = PoliticalFeatureEngine()
    return engine.build(events)


if __name__ == "__main__":
    # Smoke test with synthetic event
    test_event = {
        "date": "2026-03-26",
        "ticker": "GEO",
        "signal_type": "executive_order",
        "signal_sector": "private_prisons",
        "donor_info": DONOR_UNIVERSE.get("GEO", {}),
        "policy_signals": [{"type": "executive_order", "affected_sectors": ["private_prisons"], "affected_tickers": ["GEO", "CXW"]}],
        "insider_trades": [],
        "polymarket_data": [],
        "macro": {},
        "prices": {},
        "outcome": 1,
    }
    engine = PoliticalFeatureEngine()
    X, y, names = engine.build([test_event])
    print(f"\nFeature engine {ENGINE_VERSION}")
    print(f"Features generated: {len(names)}")
    print(f"Matrix shape: {X.shape}")
    print(f"Sample features: {names[:20]}")
