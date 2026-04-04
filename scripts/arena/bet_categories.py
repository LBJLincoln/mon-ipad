#!/usr/bin/env python3
"""
BET CATEGORIES — 120+ NBA Bet Types for Specialist Agents
==========================================================
Each category defines:
  - id: unique short identifier
  - name: human-readable name
  - tier: which tier of agent typically handles it
  - prompt_template: what the specialist agent should analyze
  - resolution: how to determine win/loss (for retrolearning)
  - group: grouping for portfolio diversification
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable


@dataclass
class BetCategory:
    id: str
    name: str
    group: str
    prompt_hint: str
    sides: int = 2  # most bets have 2 sides (over/under, home/away)

    def agent_ids(self) -> List[str]:
        """Return specialist agent IDs for each side of this bet."""
        if self.sides == 1:
            return [f"spec_{self.id}"]
        return [f"spec_{self.id}_side{i}" for i in range(self.sides)]


# ============================================================================
# GROUP 1: MONEYLINE (10 categories)
# ============================================================================
MONEYLINE_CATS = [
    BetCategory("ml_fg", "Moneyline Full Game", "moneyline",
                "Who wins the full game? Analyze team strength, form, H/A splits."),
    BetCategory("ml_1h", "Moneyline 1st Half", "moneyline",
                "Who leads at halftime? Analyze fast starters, 1H records."),
    BetCategory("ml_2h", "Moneyline 2nd Half", "moneyline",
                "Who wins the second half? Analyze closers, fatigue, bench depth."),
    BetCategory("ml_q1", "Moneyline Q1", "moneyline",
                "Who wins Q1? Analyze opening lineups, Q1 scoring pace."),
    BetCategory("ml_q2", "Moneyline Q2", "moneyline",
                "Who wins Q2? Analyze bench rotations, Q2 trends."),
    BetCategory("ml_q3", "Moneyline Q3", "moneyline",
                "Who wins Q3? Analyze halftime adjustments, Q3 runs."),
    BetCategory("ml_q4", "Moneyline Q4", "moneyline",
                "Who wins Q4? Analyze clutch performance, closing ability."),
]

# ============================================================================
# GROUP 2: SPREAD (12 categories)
# ============================================================================
SPREAD_CATS = [
    BetCategory("sp_fg", "Spread Full Game", "spread",
                "Will home team cover the spread? Analyze ATS records, margin trends."),
    BetCategory("sp_1h", "Spread 1st Half", "spread",
                "Will home cover 1H spread? Analyze 1H ATS records."),
    BetCategory("sp_2h", "Spread 2nd Half", "spread",
                "Will home cover 2H spread? Analyze 2H ATS splits."),
    BetCategory("sp_q1", "Spread Q1", "spread",
                "Will home cover Q1 spread?"),
    BetCategory("sp_alt_p2", "Alt Spread +2", "spread",
                "Home covers at +2 points? Analyze close game frequency."),
    BetCategory("sp_alt_p5", "Alt Spread +5", "spread",
                "Home covers at +5 points? Higher probability, lower payout."),
    BetCategory("sp_alt_m2", "Alt Spread -2", "spread",
                "Home covers at -2? Analyze blowout potential."),
    BetCategory("sp_alt_m5", "Alt Spread -5", "spread",
                "Home covers at -5? Analyze dominant win likelihood."),
    BetCategory("sp_alt_m10", "Alt Spread -10", "spread",
                "Home covers at -10? Longshot blowout analysis."),
]

# ============================================================================
# GROUP 3: TOTALS (14 categories)
# ============================================================================
TOTALS_CATS = [
    BetCategory("tot_fg", "Total Full Game", "totals",
                "Over or under the total? Analyze pace, ORTG, DRTG."),
    BetCategory("tot_1h", "Total 1st Half", "totals",
                "Over/under 1H total? Analyze early scoring pace."),
    BetCategory("tot_2h", "Total 2nd Half", "totals",
                "Over/under 2H total? Analyze fatigue, garbage time."),
    BetCategory("tot_q1", "Total Q1", "totals",
                "Over/under Q1 total? Analyze Q1 pace tendencies."),
    BetCategory("tot_home_fg", "Home Team Total", "totals",
                "Will home team score over/under their team total?"),
    BetCategory("tot_away_fg", "Away Team Total", "totals",
                "Will away team score over/under their team total?"),
    BetCategory("tot_alt_p5", "Alt Total +5", "totals",
                "Over/under at total+5? High-scoring game analysis."),
    BetCategory("tot_alt_m5", "Alt Total -5", "totals",
                "Over/under at total-5? Low-scoring defensive game analysis."),
    BetCategory("tot_alt_p10", "Alt Total +10", "totals",
                "Over/under at total+10? Extreme pace analysis."),
    BetCategory("tot_combined_q1q2", "Combined Q1+Q2 Total", "totals",
                "Over/under combined first half quarters total?"),
]

# ============================================================================
# GROUP 4: PLAYER PROPS (30 categories — top 6 stats x 5 tiers)
# ============================================================================
PLAYER_PROP_STATS = ["points", "rebounds", "assists", "threes", "steals", "blocks"]
PLAYER_PROP_TIERS = ["star1", "star2", "star3", "role1", "role2"]

PLAYER_PROP_CATS = []
for stat in PLAYER_PROP_STATS:
    for tier in PLAYER_PROP_TIERS:
        cat_id = f"pp_{stat}_{tier}"
        name = f"Player {stat.title()} ({tier})"
        hint = (f"Will {tier} player go over/under their {stat} line? "
                f"Analyze matchup, minutes, usage rate, recent form.")
        PLAYER_PROP_CATS.append(BetCategory(cat_id, name, "player_props", hint))

# ============================================================================
# GROUP 5: MARGIN / EXACT (12 categories)
# ============================================================================
MARGIN_CATS = [
    BetCategory("margin_1_5", "Win Margin 1-5", "margin",
                "Will the game be decided by 1-5 points? Analyze close game tendency.", sides=1),
    BetCategory("margin_6_10", "Win Margin 6-10", "margin",
                "Will the game be decided by 6-10 points?", sides=1),
    BetCategory("margin_11_15", "Win Margin 11-15", "margin",
                "Will the game be decided by 11-15 points?", sides=1),
    BetCategory("margin_16_20", "Win Margin 16-20", "margin",
                "Will the game be decided by 16-20 points?", sides=1),
    BetCategory("margin_21p", "Win Margin 21+", "margin",
                "Will the game be a 21+ point blowout?", sides=1),
    BetCategory("margin_exact_home", "Exact Margin Home Wins", "margin",
                "Predict exact winning margin if home wins.", sides=1),
    BetCategory("margin_exact_away", "Exact Margin Away Wins", "margin",
                "Predict exact winning margin if away wins.", sides=1),
    BetCategory("odd_even", "Odd/Even Total", "margin",
                "Will the total score be odd or even?"),
]

# ============================================================================
# GROUP 6: RACE / FIRST-TO (10 categories)
# ============================================================================
RACE_CATS = [
    BetCategory("race_20", "Race to 20 Points", "race",
                "Which team reaches 20 points first? Analyze early offense."),
    BetCategory("race_30", "Race to 30 Points", "race",
                "Which team reaches 30 points first?"),
    BetCategory("race_50", "Race to 50 Points", "race",
                "Which team reaches 50 points first?"),
    BetCategory("first_basket", "First Basket", "race",
                "Which team scores first? Analyze tip-off win rate, first possession plays."),
    BetCategory("first_to_10", "First to 10", "race",
                "Which team reaches 10 points first?"),
    BetCategory("lead_after_q1", "Lead After Q1", "race",
                "Which team leads after Q1? Analyze Q1 performance splits."),
    BetCategory("lead_change_count", "Lead Changes O/U", "race",
                "Over/under on number of lead changes? Analyze competitiveness."),
]

# ============================================================================
# GROUP 7: EXOTIC / SGP (16 categories)
# ============================================================================
EXOTIC_CATS = [
    BetCategory("double_result", "Double Result (1H/FG)", "exotic",
                "Predict both halftime leader AND full game winner.", sides=4),
    BetCategory("highest_scoring_q", "Highest Scoring Quarter", "exotic",
                "Which quarter will have the most points?", sides=4),
    BetCategory("lowest_scoring_q", "Lowest Scoring Quarter", "exotic",
                "Which quarter will have the fewest points?", sides=4),
    BetCategory("both_100", "Both Teams Over 100", "exotic",
                "Will both teams score 100+ points?", sides=1),
    BetCategory("blowout_15", "Blowout by 15+", "exotic",
                "Will either team win by 15+?", sides=1),
    BetCategory("overtime", "Overtime", "exotic",
                "Will the game go to overtime? Analyze OT frequency, close game tendency.", sides=1),
    BetCategory("triple_double", "Any Triple-Double", "exotic",
                "Will any player record a triple-double? Analyze stat-stuffers.", sides=1),
    BetCategory("sgp_ml_over", "SGP: ML + Over", "exotic",
                "Same-game parlay: favorite wins AND game goes over total?", sides=1),
    BetCategory("sgp_ml_under", "SGP: ML + Under", "exotic",
                "Same-game parlay: favorite wins AND game goes under total?", sides=1),
    BetCategory("sgp_dog_over", "SGP: Dog + Over", "exotic",
                "Same-game parlay: underdog wins AND game goes over?", sides=1),
    BetCategory("sgp_spread_player", "SGP: Spread + Player Prop", "exotic",
                "Same-game parlay: spread cover AND star player hits over?", sides=1),
]

# ============================================================================
# GROUP 8: PARLAY / TEASER (6 categories)
# ============================================================================
PARLAY_CATS = [
    BetCategory("parlay_2leg_ml", "2-Leg ML Parlay", "parlay",
                "Pick 2 games to parlay on moneyline. Analyze correlation.", sides=1),
    BetCategory("parlay_3leg_ml", "3-Leg ML Parlay", "parlay",
                "Pick 3 games to parlay on moneyline.", sides=1),
    BetCategory("parlay_2leg_spread", "2-Leg Spread Parlay", "parlay",
                "Pick 2 games to parlay on spread.", sides=1),
    BetCategory("teaser_6pt", "6-Point Teaser", "parlay",
                "Pick 2+ games with 6-point teaser adjustment.", sides=1),
    BetCategory("teaser_7pt", "7-Point Teaser", "parlay",
                "Pick 2+ games with 7-point teaser adjustment.", sides=1),
    BetCategory("round_robin", "Round Robin 3-way", "parlay",
                "Create round-robin from 3 selections.", sides=1),
]

# ============================================================================
# GROUP 9: LIVE / MOMENTUM (8 categories — pre-game estimates)
# ============================================================================
LIVE_CATS = [
    BetCategory("live_q1_ml_flip", "Live Q1 ML Flip", "live",
                "Will the Q1 loser come back to win? Analyze comeback tendency.", sides=1),
    BetCategory("live_halftime_flip", "Halftime Comeback", "live",
                "Will the halftime trailer win? Analyze 2H strength.", sides=1),
    BetCategory("live_run_10_0", "10-0 Run Probability", "live",
                "Will there be a 10-0 run in the game? Analyze streakiness.", sides=1),
    BetCategory("live_largest_lead", "Largest Lead O/U", "live",
                "Over/under on largest lead in the game?"),
    BetCategory("momentum_q3", "Q3 Momentum Shift", "live",
                "Will Q3 feature a significant momentum shift?", sides=1),
]

# ============================================================================
# MASTER REGISTRY
# ============================================================================
ALL_CATEGORIES: List[BetCategory] = (
    MONEYLINE_CATS + SPREAD_CATS + TOTALS_CATS + PLAYER_PROP_CATS +
    MARGIN_CATS + RACE_CATS + EXOTIC_CATS + PARLAY_CATS + LIVE_CATS
)

# Quick lookup
CATEGORY_BY_ID: Dict[str, BetCategory] = {cat.id: cat for cat in ALL_CATEGORIES}

# Group lookup
CATEGORIES_BY_GROUP: Dict[str, List[BetCategory]] = {}
for cat in ALL_CATEGORIES:
    CATEGORIES_BY_GROUP.setdefault(cat.group, []).append(cat)

# Total specialist agent count
TOTAL_SPECIALIST_AGENTS = sum(cat.sides for cat in ALL_CATEGORIES)


def get_specialist_prompt(cat: BetCategory, game_context: dict, side: int = 0) -> str:
    """Build a focused prompt for a specialist agent on one specific bet category."""
    home = game_context.get("home_team", "HOME")
    away = game_context.get("away_team", "AWAY")
    spread = game_context.get("spread_home", "N/A")
    total = game_context.get("total", "N/A")
    odds_home = game_context.get("odds_home", "N/A")
    odds_away = game_context.get("odds_away", "N/A")

    side_label = f" (side {side})" if cat.sides > 2 else ""
    if cat.sides == 2 and side == 0:
        side_label = f" ({home} / Over / Home)"
    elif cat.sides == 2 and side == 1:
        side_label = f" ({away} / Under / Away)"

    return f"""NBA Bet Analysis — {cat.name}{side_label}

Game: {away} @ {home}
Spread: {home} {spread} | Total: {total}
Moneyline: {home} {odds_home} / {away} {odds_away}

Your ONLY job: Analyze category "{cat.name}" for this game.
{cat.prompt_hint}

Respond with EXACTLY this JSON (no other text):
{{"confidence": 0.0-1.0, "direction": "home"/"away"/"over"/"under"/"yes"/"no", "edge_pct": -10.0 to 10.0, "reasoning": "one sentence"}}"""


def get_tier2_prompt(game_context: dict, focus_groups: List[str]) -> str:
    """Build a broader prompt for Tier 2 (free power) agents."""
    home = game_context.get("home_team", "HOME")
    away = game_context.get("away_team", "AWAY")
    spread = game_context.get("spread_home", "N/A")
    total = game_context.get("total", "N/A")

    groups_str = ", ".join(focus_groups)
    return f"""NBA Betting Analysis — {away} @ {home}

Spread: {home} {spread} | Total: {total}
Focus areas: {groups_str}

Analyze this game across the focus areas. For each relevant bet type, provide your assessment.

Respond with EXACTLY this JSON (no other text):
{{"bets": [{{"category": "ml_fg", "confidence": 0.0-1.0, "direction": "home"/"away", "edge_pct": -10 to 10, "reasoning": "brief"}}, ...]}}"""


def get_tier1_prompt(game_context: dict, other_predictions: List[dict] = None) -> str:
    """Build a comprehensive prompt for Tier 1 (premium) agents."""
    home = game_context.get("home_team", "HOME")
    away = game_context.get("away_team", "AWAY")
    spread = game_context.get("spread_home", "N/A")
    total = game_context.get("total", "N/A")
    form_home = game_context.get("home_form", "N/A")
    form_away = game_context.get("away_form", "N/A")
    injuries = game_context.get("injuries", "None reported")

    peers_section = ""
    if other_predictions:
        peers_section = "\n\nANONYMIZED PEER PREDICTIONS (for your review):\n"
        for i, pred in enumerate(other_predictions):
            peers_section += f"  Analyst #{i+1}: ML={pred.get('ml_pick','?')}, Spread={pred.get('spread_pick','?')}, Total={pred.get('total_pick','?')}, Confidence={pred.get('confidence','?')}\n"
        peers_section += "\nIncorporate peer consensus into your final assessment.\n"

    return f"""COMPREHENSIVE NBA GAME ANALYSIS — {away} @ {home}

=== GAME INFO ===
Spread: {home} {spread} | Total: {total}
Home Form: {form_home} | Away Form: {form_away}
Injuries: {injuries}
{peers_section}
Analyze ALL major bet categories for this game:
1. Moneyline (full game + halves + quarters)
2. Spread (full game + alt lines)
3. Totals (full game + team totals)
4. Key player props
5. Exotic (margin, race-to, SGPs)

For each bet, assess: probability, edge vs market, confidence level.

Respond with EXACTLY this JSON (no other text):
{{
  "ml_fg": {{"direction": "home"/"away", "confidence": 0.0-1.0, "edge_pct": float}},
  "spread_fg": {{"direction": "home"/"away", "confidence": 0.0-1.0, "edge_pct": float}},
  "total_fg": {{"direction": "over"/"under", "confidence": 0.0-1.0, "edge_pct": float}},
  "best_bet": {{"category": "str", "direction": "str", "confidence": float, "edge_pct": float}},
  "avoid": {{"category": "str", "reason": "str"}},
  "overall_lean": "home"/"away"/"skip",
  "game_narrative": "one paragraph analysis"
}}"""


def get_meta_prompt(all_predictions: Dict[str, dict], game_context: dict) -> str:
    """Build the Chairman/Oracle synthesis prompt from all agent predictions."""
    home = game_context.get("home_team", "HOME")
    away = game_context.get("away_team", "AWAY")

    preds_text = ""
    for agent_id, pred in all_predictions.items():
        preds_text += f"\n  {agent_id}: {json.dumps(pred, default=str)[:300]}"

    import json
    return f"""CHAIRMAN SYNTHESIS — {away} @ {home}

You are the Oracle. Below are predictions from {len(all_predictions)} AI agents.
Your job: synthesize into final consensus, weight by historical accuracy, identify agreements and disagreements.

=== ALL AGENT PREDICTIONS ==={preds_text}

Synthesize into final recommendations. Weight agents by past accuracy if known.
Flag any strong consensus (>80% agreement) or strong disagreement.

Respond with EXACTLY this JSON:
{{
  "consensus_ml": {{"direction": "home"/"away", "confidence": 0.0-1.0, "agreement_pct": float}},
  "consensus_spread": {{"direction": "home"/"away", "confidence": 0.0-1.0, "agreement_pct": float}},
  "consensus_total": {{"direction": "over"/"under", "confidence": 0.0-1.0, "agreement_pct": float}},
  "top_3_bets": [{{"category": "str", "direction": "str", "confidence": float, "edge_pct": float}}, ...],
  "avoid_bets": ["category_ids"],
  "agent_quality_scores": {{"agent_id": 0.0-1.0, ...}},
  "narrative": "synthesis paragraph"
}}"""


# ============================================================================
# SUMMARY
# ============================================================================
if __name__ == "__main__":
    print(f"Bet Categories Registry")
    print(f"=======================")
    print(f"Total categories: {len(ALL_CATEGORIES)}")
    print(f"Total specialist agent slots: {TOTAL_SPECIALIST_AGENTS}")
    print()
    for group, cats in CATEGORIES_BY_GROUP.items():
        agent_count = sum(c.sides for c in cats)
        print(f"  {group:<20} {len(cats):>3} categories, {agent_count:>3} agent slots")
    print()
    print(f"Groups: {list(CATEGORIES_BY_GROUP.keys())}")
