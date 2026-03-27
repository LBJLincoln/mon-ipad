#!/usr/bin/env python3
"""
Donor Power Index — Score each donor corp by Trump proximity, donation size,
pending regulatory business, and favor delivery probability.

Inspired by: Starlizard power ratings for NBA teams.
Adapted for: Trump donor corporate universe.
"""

import json, math
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent

# Import donor universe
import sys; sys.path.insert(0, str(ROOT / "ops"))
from fetch_political_data import DONOR_UNIVERSE, DONOR_TICKERS

# ═══════════════════════════════════════════════════════════
# DONOR POWER SCORE
# ═══════════════════════════════════════════════════════════

def compute_donor_power_index(donor_info, fec_data=None, insider_data=None, polymarket_signals=None):
    """
    Compute a composite Donor Power Index (DPI) for a single ticker.
    
    Components:
      1. Donation Magnitude (0-30 pts): log-scaled donation size
      2. Channel Weight (0-20 pts): ballroom > inaugural > PAC > indirect
      3. Favor Delivery (0-25 pts): has the favor been delivered?
      4. Sector Tailwind (0-15 pts): is the sector currently favored by policy?
      5. Insider Signal (0-10 pts): are insiders buying?
    
    Total: 0-100
    """
    score = 0.0
    
    # 1. Donation Magnitude (log-scaled, max 30)
    amount = donor_info.get("donated", 0)
    if amount > 0:
        # log10(500K) ≈ 5.7, log10(290M) ≈ 8.5
        log_amount = math.log10(max(amount, 1))
        score += min(30, (log_amount - 4) * 10)  # 10K=10, 1M=20, 100M=30
    
    # 2. Channel Weight
    channel_scores = {
        "ballroom": 20,      # Most direct quid pro quo signal
        "MAGA_Inc": 18,      # Direct PAC = high commitment
        "inaugural": 15,     # Standard corporate play
        "musk_PAC": 15,      # Mega individual
        "adelson_PAC": 15,   # Mega individual
        "indirect": 5,       # Crypto ecosystem, no direct donation
    }
    channel = donor_info.get("channel", "indirect")
    score += channel_scores.get(channel, 5)
    
    # 3. Favor Delivery
    if donor_info.get("delivered", False):
        score += 25  # Favor already delivered = proven pattern
    else:
        # Pending favor = potential catalyst
        score += 10  # Still has upside catalyst
    
    # 4. Sector Tailwind (simplified — would use real policy data)
    hot_sectors = {"private_prisons": 15, "crypto": 14, "oil_gas": 13,
                   "defense": 12, "tobacco": 11, "healthcare": 10,
                   "nuclear": 10, "big_tech": 8, "fintech": 8,
                   "transport": 6, "auto_ev": 5, "gaming": 5,
                   "food": 7, "media": 5, "rail": 4}
    sector = donor_info.get("sector", "")
    score += hot_sectors.get(sector, 3)
    
    # 5. Insider Signal (from Form 4 data)
    if insider_data:
        # Count net buys in last 30 days
        recent_buys = sum(1 for t in insider_data if "Purchase" in str(t.get("form_type", "")))
        recent_sells = sum(1 for t in insider_data if "Sale" in str(t.get("form_type", "")))
        if recent_buys > recent_sells:
            score += min(10, (recent_buys - recent_sells) * 3)
        elif recent_sells > recent_buys:
            score -= min(5, (recent_sells - recent_buys) * 2)
    
    return round(min(100, max(0, score)), 1)


def compute_all_dpi(insider_data=None):
    """Compute DPI for entire donor universe."""
    dpi = {}
    for ticker, info in DONOR_UNIVERSE.items():
        insider = insider_data.get(ticker, []) if insider_data else []
        dpi[ticker] = {
            "ticker": ticker,
            "name": info["name"],
            "sector": info["sector"],
            "dpi_score": compute_donor_power_index(info, insider_data=insider),
            "donated": info["donated"],
            "channel": info["channel"],
            "favor_delivered": info["delivered"],
            "favor": info["favor"],
        }
    
    # Sort by DPI score
    ranked = sorted(dpi.values(), key=lambda x: x["dpi_score"], reverse=True)
    return {r["ticker"]: r for r in ranked}


def print_dpi_table():
    """Print formatted DPI table."""
    dpi = compute_all_dpi()
    print(f"\n{'='*80}")
    print(f"{'DONOR POWER INDEX':^80}")
    print(f"{'='*80}")
    print(f"{'Rank':>4} {'Ticker':>6} {'Name':<25} {'DPI':>5} {'Sector':<18} {'Favor':>3} {'Donated':>12}")
    print(f"{'-'*80}")
    for rank, (ticker, d) in enumerate(dpi.items(), 1):
        delivered = "✅" if d["favor_delivered"] else "⏳"
        donated_str = f"${d['donated']:>10,}"
        print(f"{rank:>4} {ticker:>6} {d['name']:<25} {d['dpi_score']:>5.1f} {d['sector']:<18} {delivered:>3} {donated_str}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    print_dpi_table()
