"""
DMAD: Diverse Multi-Agent Debate profiles
==========================================
From: "Diverse Multi-Agent Debate for Improved Prediction Accuracy" (ICLR 2025)

Standard multi-agent debate fails because agents reason identically despite
different personas. DMAD forces structurally distinct reasoning by locking
each agent to a different data source. This prevents groupthink and forces
genuine epistemic diversity.

NBA profiles: each trader locked to a different data partition.
Political profiles: each trader locked to a different signal category.

Key innovation: when >3/5 agents agree, reduce Kelly fraction by 40%.
This is the core anti-groupthink mechanism from the paper.
"""

from typing import Dict, Optional

# ── NBA DMAD PROFILES ─────────────────────────────────────────────────────────
# Each trader sees a different slice of game_context.
# Keys map to top-level fields in the build_game_context() dict.
# "excluded" fields are set to None/empty before agent sees the context.

NBA_DMAD_PROFILES: Dict[str, Dict] = {
    "gemini": {
        "name": "Stats Purist",
        "data_sources": ["home_standings", "away_standings", "models"],
        "excluded": ["home_form_L10", "away_form_L10", "odds"],
        "reasoning_label": "Only historical statistical performance. No market data.",
    },
    "openrouter": {
        "name": "Market Reader",
        "data_sources": ["odds"],
        "excluded": ["home_standings", "away_standings", "models", "home_form_L10", "away_form_L10"],
        "reasoning_label": "Only market signals. What is the money saying?",
    },
    "claude": {
        "name": "Momentum Tracker",
        "data_sources": ["home_form_L10", "away_form_L10"],
        "excluded": ["home_standings", "away_standings", "odds"],
        "reasoning_label": "Only recent form and schedule factors.",
    },
    "codex": {
        "name": "Regression Analyst",
        "data_sources": ["home_standings", "away_standings"],
        "excluded": ["home_form_L10", "away_form_L10", "odds"],
        "reasoning_label": "Only regression to mean analysis via full season standings.",
    },
    "grok": {
        "name": "Contrarian Scout",
        "data_sources": ["odds", "home_form_L10", "away_form_L10"],
        "excluded": ["home_standings", "away_standings", "models"],
        "reasoning_label": "Looks for spots where market is likely wrong on recent form.",
    },
    # ── New traders (expanded roster Apr 2026) ─────────────────────────────
    "deepseek": {
        "name": "Full-Context Quant",
        "data_sources": ["home_standings", "away_standings", "odds", "models"],
        "excluded": ["home_form_L10", "away_form_L10"],
        "reasoning_label": "Sees full season + market but ignores recent form. Long-term statistical anchor.",
    },
    "phi": {
        "name": "Model-Only Theorist",
        "data_sources": ["models"],
        "excluded": ["home_standings", "away_standings", "odds", "home_form_L10", "away_form_L10"],
        "reasoning_label": "Pure model output. No human-readable context. Trust the math.",
    },
    "cohere": {
        "name": "Form + Market Tactician",
        "data_sources": ["home_form_L10", "away_form_L10", "odds"],
        "excluded": ["home_standings", "away_standings", "models"],
        "reasoning_label": "Recent form meets market pricing. Short-term tactical view.",
    },
    "gemma": {
        "name": "Odds Arbitrageur",
        "data_sources": ["odds", "models"],
        "excluded": ["home_standings", "away_standings", "home_form_L10", "away_form_L10"],
        "reasoning_label": "Finds model-vs-market disagreement. Pure edge detection.",
    },
    "mixtral": {
        "name": "Everything Ensemble",
        "data_sources": ["home_standings", "away_standings", "home_form_L10", "away_form_L10", "odds", "models"],
        "excluded": [],
        "reasoning_label": "Sees all data. Ensemble view with no blind spots but groupthink risk.",
    },
}

# ── POLITICAL DMAD PROFILES ───────────────────────────────────────────────────
# Each political trader processes a different slice of social_signals / events.
# "event_filter" limits which event categories this agent considers.
# "signal_keys" limits which keys in social_signals this agent reads.

POLITICAL_DMAD_PROFILES: Dict[str, Dict] = {
    "gemini": {
        "name": "Tech Sector Analyst",
        "event_filter": ["exec_order", "CONTRACT_AWARD", "SECTOR_LONG"],
        "signal_keys": ["technology", "defense"],
        "excluded_signals": ["energy", "commodity", "bonds"],
        "reasoning_label": "Tech and defense sector orders only.",
    },
    "openrouter": {
        "name": "Macro Flow Reader",
        "event_filter": ["fed_rule", "TARIFF_ESCALATE", "ENFORCEMENT_DROP"],
        "signal_keys": ["broad", "financials", "small_cap"],
        "excluded_signals": ["defense", "healthcare"],
        "reasoning_label": "Fed policy and macro flow signals only.",
    },
    "claude": {
        "name": "Insider Track Monitor",
        "event_filter": ["insider_trade", "INSIDER_BUY", "INSIDER_SELL", "CONGRESS_TRADE"],
        "signal_keys": ["healthcare", "bonds", "commodity"],
        "excluded_signals": ["technology", "energy"],
        "reasoning_label": "Congressional and insider transaction data only.",
    },
    "codex": {
        "name": "Event Catalyst Hunter",
        "event_filter": ["EXECUTIVE_ORDER", "polymarket", "EVENT_BINARY", "POLY_STOCK_ARB"],
        "signal_keys": ["technology", "energy", "defense"],
        "excluded_signals": ["bonds", "commodity"],
        "reasoning_label": "Binary event catalysts and prediction market arb only.",
    },
    "grok": {
        "name": "Energy Contrarian",
        "event_filter": ["ENERGY_LONG", "TARIFF_ESCALATE", "CEO_PERSONAL"],
        "signal_keys": ["energy", "commodity", "small_cap"],
        "excluded_signals": ["technology", "financials"],
        "reasoning_label": "Energy and commodity contrarian signals only.",
    },
    # ── New traders (expanded roster Apr 2026) ─────────────────────────────
    "deepseek": {
        "name": "Macro Quant",
        "event_filter": ["fed_rule", "TARIFF_ESCALATE", "ENFORCEMENT_DROP", "exec_order"],
        "signal_keys": ["broad", "financials", "small_cap", "technology"],
        "excluded_signals": ["commodity"],
        "reasoning_label": "Macro policy signals: Fed, tariffs, executive orders. Broad market view.",
    },
    "phi": {
        "name": "Safe Haven Theorist",
        "event_filter": ["fed_rule", "INSIDER_SELL", "ENFORCEMENT_DROP"],
        "signal_keys": ["bonds", "commodity", "healthcare"],
        "excluded_signals": ["technology", "energy", "defense"],
        "reasoning_label": "Risk-off signals only: rate moves, insider selling, enforcement drops.",
    },
    "cohere": {
        "name": "Tech Policy Tracker",
        "event_filter": ["exec_order", "CONTRACT_AWARD", "polymarket", "SECTOR_LONG"],
        "signal_keys": ["technology", "industrials", "broad"],
        "excluded_signals": ["commodity", "bonds"],
        "reasoning_label": "Government tech spending, contracts, and sector-specific policy.",
    },
    "gemma": {
        "name": "Volatility Hunter",
        "event_filter": ["EXECUTIVE_ORDER", "TARIFF_ESCALATE", "CEO_PERSONAL", "EVENT_BINARY"],
        "signal_keys": ["energy", "technology", "small_cap"],
        "excluded_signals": ["bonds", "healthcare"],
        "reasoning_label": "High-volatility catalysts: tariffs, exec orders, CEO events.",
    },
    "mixtral": {
        "name": "Cross-Sector Rotator",
        "event_filter": ["fed_rule", "exec_order", "insider_trade", "SECTOR_LONG", "ENERGY_LONG"],
        "signal_keys": ["broad", "financials", "energy", "bonds"],
        "excluded_signals": ["defense"],
        "reasoning_label": "Broad cross-sector rotation signals. Sees most event types.",
    },
}

# ── ANTI-GROUPTHINK CONSTANTS ─────────────────────────────────────────────────
CONSENSUS_THRESHOLD = 5       # out of 10 agents must agree to trigger damping (was 3/5)
CONSENSUS_DAMPING   = 0.60    # multiply Kelly by this when consensus fires (40% reduction)


# ── NBA CONTEXT FILTER ────────────────────────────────────────────────────────

def filter_nba_context(full_context: Dict, trader_id: str) -> Dict:
    """
    Return a copy of game_context with only the data sources allowed by this
    trader's DMAD profile. Excluded fields are replaced with empty dicts/None
    so downstream code doesn't crash on missing keys.

    The private _result key is always preserved — it's needed for outcome
    resolution and is not visible to the decision logic anyway (it's only
    read after bets are placed).
    """
    profile = NBA_DMAD_PROFILES.get(trader_id)
    if profile is None:
        # Unknown trader — return context unchanged
        return full_context

    filtered: Dict = {}
    for key, value in full_context.items():
        if key.startswith("_") or key in ("date", "home", "away", "oasis"):
            # Always pass through meta-keys and identity fields
            filtered[key] = value
        elif key in profile["excluded"]:
            # Replace with empty sentinel to preserve key existence
            if isinstance(value, dict):
                filtered[key] = {}
            elif isinstance(value, list):
                filtered[key] = []
            else:
                filtered[key] = None
        else:
            filtered[key] = value

    # Attach DMAD metadata to context so it appears in reasoning logs
    filtered["_dmad"] = {
        "trader_id": trader_id,
        "role": profile["name"],
        "reasoning_label": profile["reasoning_label"],
        "excluded": profile["excluded"],
    }
    return filtered


# ── POLITICAL SIGNAL FILTER ───────────────────────────────────────────────────

def filter_political_signals(
    social_signals: Dict,
    day_events: list,
    trader_id: str,
) -> tuple:
    """
    Return (filtered_signals, filtered_events) for this trader's DMAD profile.

    social_signals: top-level dict where keys are sector names or signal categories.
    day_events: list of event dicts, each has an "event_type" field.

    Excluded signal keys are removed entirely.
    Only events whose event_type is in the profile's event_filter are kept.
    """
    profile = POLITICAL_DMAD_PROFILES.get(trader_id)
    if profile is None:
        return social_signals, day_events

    # Filter social signal keys
    excluded_sigs = set(profile.get("excluded_signals", []))
    filtered_signals: Dict = {
        k: v for k, v in social_signals.items()
        if k not in excluded_sigs
    }

    # Filter events to only allowed types
    allowed_events = set(profile.get("event_filter", []))
    filtered_events = [
        ev for ev in day_events
        if ev.get("event_type", "") in allowed_events
    ] if allowed_events else day_events

    return filtered_signals, filtered_events


# ── CONSENSUS DETECTION & DAMPING ────────────────────────────────────────────

def check_nba_consensus(
    all_agent_decisions: Dict[str, Dict],
    game_key: str,
) -> Dict:
    """
    Examine all agents' bet records for a specific game and detect consensus.

    all_agent_decisions: {trader_id: list_of_bets_for_this_game}
    game_key: e.g. "ml_home" — the category to check consensus on.

    Returns:
      {
        "consensus": bool,
        "direction": "home" | "away" | None,
        "agreeing_agents": [...],
        "damping_factor": float  (1.0 if no consensus, CONSENSUS_DAMPING if consensus)
      }
    """
    home_votes = []
    away_votes = []

    for trader_id, bets in all_agent_decisions.items():
        for bet in bets:
            if bet.get("category") == game_key:
                if "home" in bet["category"]:
                    home_votes.append(trader_id)
                else:
                    away_votes.append(trader_id)
                break  # one vote per agent per category

    if len(home_votes) >= CONSENSUS_THRESHOLD:
        return {
            "consensus": True,
            "direction": "home",
            "agreeing_agents": home_votes,
            "damping_factor": CONSENSUS_DAMPING,
        }
    if len(away_votes) >= CONSENSUS_THRESHOLD:
        return {
            "consensus": True,
            "direction": "away",
            "agreeing_agents": away_votes,
            "damping_factor": CONSENSUS_DAMPING,
        }
    return {
        "consensus": False,
        "direction": None,
        "agreeing_agents": [],
        "damping_factor": 1.0,
    }


def check_political_consensus(
    all_agent_positions: Dict[str, list],
    ticker: str,
) -> Dict:
    """
    Examine all agents' positions for a specific ticker and detect consensus.

    Returns damping dict same structure as check_nba_consensus.
    """
    long_votes = []
    short_votes = []

    for trader_id, positions in all_agent_positions.items():
        for pos in positions:
            if pos.get("ticker") == ticker:
                if pos.get("direction") == "long":
                    long_votes.append(trader_id)
                else:
                    short_votes.append(trader_id)
                break

    if len(long_votes) >= CONSENSUS_THRESHOLD:
        return {
            "consensus": True,
            "direction": "long",
            "agreeing_agents": long_votes,
            "damping_factor": CONSENSUS_DAMPING,
        }
    if len(short_votes) >= CONSENSUS_THRESHOLD:
        return {
            "consensus": True,
            "direction": "short",
            "agreeing_agents": short_votes,
            "damping_factor": CONSENSUS_DAMPING,
        }
    return {
        "consensus": False,
        "direction": None,
        "agreeing_agents": [],
        "damping_factor": 1.0,
    }


def compute_dmad_divergence(all_agent_decisions: Dict[str, list]) -> Dict:
    """
    Compute divergence metrics across all agents for a given round of decisions.
    Returns a summary dict logged with each iteration.

    Divergence = 1 - (max agreement fraction across all categories).
    High divergence (>0.5) = healthy debate. Low divergence (<0.3) = groupthink.
    """
    if not all_agent_decisions:
        return {"divergence": 0.0, "consensus_events": 0, "healthy": True}

    n_agents = len(all_agent_decisions)
    all_cats: Dict[str, Dict[str, int]] = {}  # cat -> {direction: count}

    for trader_id, decisions in all_agent_decisions.items():
        for item in decisions:
            cat = item.get("category") or item.get("ticker", "unknown")
            direction = item.get("direction") or (
                "home" if "home" in cat else "away"
            )
            if cat not in all_cats:
                all_cats[cat] = {}
            all_cats[cat][direction] = all_cats[cat].get(direction, 0) + 1

    if not all_cats:
        return {"divergence": 0.0, "consensus_events": 0, "healthy": True}

    consensus_events = 0
    total_agreement = 0.0

    for cat, votes in all_cats.items():
        max_votes = max(votes.values())
        agreement_frac = max_votes / n_agents
        total_agreement += agreement_frac
        if max_votes >= CONSENSUS_THRESHOLD:
            consensus_events += 1

    avg_agreement = total_agreement / len(all_cats)
    divergence = round(1.0 - avg_agreement, 4)
    healthy = divergence >= 0.30  # Below 0.30 signals dangerous groupthink

    return {
        "divergence": divergence,
        "consensus_events": consensus_events,
        "avg_agreement": round(avg_agreement, 4),
        "healthy": healthy,
        "warning": "GROUPTHINK RISK" if not healthy else None,
    }
