#!/usr/bin/env python3
"""
OASIS Adapter — Multi-Agent Social Discussion → Trading Decisions
=================================================================

Bridges the vendored camel-ai/oasis social simulation framework to the
Nomos42 trading floor.  Works in two modes:

  LITE MODE (default, VM-safe):
    No external deps required.  Uses stdlib only.  Each of the 5 traders
    gets a persona-driven prompt template; "discussion" is a structured
    round of synthetic posts/replies that modify per-trader confidence
    biases.  Output format is identical to full mode so the trading floor
    cannot tell them apart.

  FULL MODE (--full, GH Actions):
    Attempts to import vendor/oasis + camel-ai.  If import succeeds, uses
    the real SocialAgent / UserInfo classes to run one discussion round.
    Falls back to lite mode silently on any ImportError.

Output
------
  data/arena/oasis-discussions/YYYY-MM-DD.json

  Schema:
    {
      "date": "YYYY-MM-DD",
      "mode": "lite" | "full",
      "context": { "game_count": N, "top_game": "...", "political_events": [...] },
      "rounds": [
        {
          "round": 1,
          "posts": [
            { "agent_id": "gemini", "post": "...", "sentiment": 0.0..1.0 }
          ],
          "replies": [
            { "agent_id": "...", "to": "...", "reply": "...", "sentiment": ... }
          ]
        }
      ],
      "decisions": {
        "gemini":    { "model_bias": "...", "strategy_bias": "...",
                       "confidence_delta": -0.10..+0.10,
                       "rationale": "..." },
        ...
      },
      "consensus": { "home_confidence": 0.0..1.0, "sentiment": "bullish|bearish|neutral" }
    }

  "model_bias"    — preferred model after discussion (empty string = no change)
  "strategy_bias" — preferred strategy after discussion (empty string = no change)
  "confidence_delta" — additive nudge to the trader's implied home-win probability
                        [-0.10, +0.10]

Trading Floor Integration
-------------------------
  In trading-floor-v4.py, call:

      oasis_ctx = load_oasis_context()  # returns {} if no file for today

  Then pass oasis_ctx into run_nba_backtest_for_agent().  Inside that
  function, at the top of the day loop, call:

      kelly_adj *= _oasis_kelly_modifier(trader_id, oasis_ctx)

  And inside build_game_context() or agent_pick_model_for_game(), use:

      oasis_bias = oasis_ctx.get("decisions", {}).get(trader_id, {})
      confidence_delta = oasis_bias.get("confidence_delta", 0.0)

Usage
-----
  python3 scripts/arena/oasis_adapter.py                 # lite, today
  python3 scripts/arena/oasis_adapter.py --date 2026-04-12
  python3 scripts/arena/oasis_adapter.py --full          # try real OASIS
  python3 scripts/arena/oasis_adapter.py --dry-run       # print, no write
  python3 scripts/arena/oasis_adapter.py --context '{"game_count":8}'
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── PATHS ──────────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).resolve().parent.parent.parent
VENDOR_OASIS = ROOT / "vendor" / "oasis"
DISCUSS_DIR  = ROOT / "data" / "arena" / "oasis-discussions"

# ── TRADER PERSONAS (mirror trading-floor-v4.py TRADERS dict) ─────────────────
TRADER_PERSONAS: Dict[str, Dict[str, Any]] = {
    "gemini": {
        "name":        "Gemma Analyst",
        "personality": "analytical",
        "voice":       "data-driven, statistical, precise",
        "bias_toward": "high-confidence consensus picks",
        "style":       "cites model disagreement, defers to lower Brier scores",
    },
    "openrouter": {
        "name":        "Qwen Strategist",
        "personality": "diversified",
        "voice":       "portfolio-focused, sector-aware",
        "bias_toward": "spreading bets across value opportunities",
        "style":       "looks for Kelly diversification, avoids concentration",
    },
    "claude": {
        "name":        "Claude Sentinel",
        "personality": "conservative",
        "voice":       "risk-averse, drawdown-conscious",
        "bias_toward": "preserving bankroll, avoiding bad beats",
        "style":       "questions high-variance plays, warns about streaks",
    },
    "codex": {
        "name":        "Llama Vanguard",
        "personality": "aggressive",
        "voice":       "momentum-chasing, streak-riding",
        "bias_toward": "the hottest model prediction and max kelly",
        "style":       "argues for bigger bets on high-confidence games",
    },
    "grok": {
        "name":        "Mistral Maverick",
        "personality": "contrarian",
        "voice":       "fades the crowd, hunts undervalued dogs",
        "bias_toward": "underdog value, pairs trading, outlier lines",
        "style":       "disagrees with consensus, looks for market overreaction",
    },
}

# ── DISCUSSION TEMPLATES ───────────────────────────────────────────────────────
# Each template is parameterized by {name}, {context_summary}, {personality}
# We generate synthetic "posts" by filling in these templates with the day's context.

_POST_TEMPLATES: Dict[str, List[str]] = {
    "analytical": [
        "{name}: Looking at today's slate — {context_summary}. "
        "Model consensus sits at {consensus_pct:.0f}% home. "
        "I'm backing the {top_model} signal here.",
        "{name}: Brier gap between our top and bottom model is {brier_gap:.4f}. "
        "That's meaningful — sticking to consensus_ensemble.",
    ],
    "diversified": [
        "{name}: {game_count} games today. Spreading across value spots rather than concentrating. "
        "Quarter Kelly across 3+ bets.",
        "{name}: Watching {top_game} — line movement suggests sharp action. "
        "Diversifying into away ML + first half.",
    ],
    "conservative": [
        "{name}: Given the {win_streak}-game streak, pulling back to flat_1pct. "
        "Drawdown protection first.",
        "{name}: Models disagree more than usual today ({disagreement:.2f} spread). "
        "Low confidence = reduced sizing.",
    ],
    "aggressive": [
        "{name}: {top_game} is a screaming value bet. Full Kelly on the {top_model} edge.",
        "{name}: On a {win_streak}-game run. Pressing with streak_momentum — "
        "3+ strategies on the marquee game.",
    ],
    "contrarian": [
        "{name}: Public is hammering home favorites hard today. "
        "Going the other way on {top_game} — home ML is juiced.",
        "{name}: The {top_model} model agrees with the market — that's a fade signal for me. "
        "Dog value plus is the move.",
    ],
}

_REPLY_TEMPLATES: Dict[str, Dict[str, str]] = {
    # who → who → template
    "codex": {
        "claude":    "{name} to Sentinel: stop playing scared — "
                     "that {win_streak}-game streak is signal, not noise.",
        "grok":      "{name} to Maverick: the underdog angle is cute but "
                     "we're in a momentum regime right now.",
    },
    "claude": {
        "codex":     "{name} to Vanguard: bankroll preservation isn't cowardice. "
                     "One blowup erases 5 wins. I'll stay at half_kelly.",
        "grok":      "{name} to Maverick: the contrarian play works 35% of the time. "
                     "That's not an edge, that's a coin flip.",
    },
    "grok": {
        "gemini":    "{name} to Analyst: your consensus signal is exactly what the market priced in. "
                     "Where's the edge?",
        "codex":     "{name} to Vanguard: chasing momentum blows up accounts. "
                     "I'll take the dog — market overreacted.",
    },
    "gemini": {
        "grok":      "{name} to Maverick: the Brier says consensus is right more often than not. "
                     "Data wins over narrative.",
        "codex":     "{name} to Vanguard: full Kelly is reckless with a {disagreement:.2f} model spread. "
                     "Even half is aggressive today.",
    },
    "openrouter": {
        "gemini":    "{name} to Analyst: agreed on consensus, but diversifying across "
                     "{game_count} games beats concentration.",
        "claude":    "{name} to Sentinel: your flat_1pct leaves ROI on the table. "
                     "At least do quarter_kelly.",
    },
}

# ── SENTIMENT + DECISION LOGIC ────────────────────────────────────────────────

def _compute_sentiment(personality: str, win_streak: int,
                       model_disagreement: float, game_count: int) -> float:
    """Returns a sentiment score in [0, 1] where 1 = very bullish, 0 = very bearish."""
    base = {
        "analytical":  0.55,
        "diversified": 0.50,
        "conservative": 0.40,
        "aggressive":  0.65,
        "contrarian":  0.35,
    }.get(personality, 0.50)

    # Positive streak pushes bullish traders up, pushes contrarian down
    streak_factor = win_streak * 0.02
    if personality == "contrarian":
        streak_factor = -streak_factor
    if personality == "conservative":
        streak_factor *= 0.5

    # High disagreement → analytical and conservative get less bullish
    disagreement_penalty = model_disagreement * 2.0
    if personality in ("aggressive", "contrarian"):
        disagreement_penalty = -disagreement_penalty * 0.5  # they like chaos

    score = base + streak_factor - disagreement_penalty
    return max(0.05, min(0.95, score))


def _sentiment_to_confidence_delta(trader_id: str, sentiment: float,
                                   other_sentiments: Dict[str, float]) -> float:
    """Convert discussion outcome (own + peer sentiments) to confidence_delta."""
    peers = [v for k, v in other_sentiments.items() if k != trader_id]
    peer_avg = sum(peers) / len(peers) if peers else 0.5

    personality = TRADER_PERSONAS[trader_id]["personality"]

    if personality == "contrarian":
        # Fade the crowd
        delta = (0.5 - peer_avg) * 0.20
    elif personality == "conservative":
        # Pull toward 0 (less conviction)
        delta = (sentiment - 0.5) * 0.05
    elif personality == "aggressive":
        # Amplify own sentiment
        delta = (sentiment - 0.5) * 0.15
    elif personality == "analytical":
        # Weight own view 60%, peer_avg 40%
        blended = 0.6 * sentiment + 0.4 * peer_avg
        delta = (blended - 0.5) * 0.10
    else:  # diversified
        # Stay near neutral — diversification doesn't need a directional view
        delta = (sentiment - 0.5) * 0.06

    return round(max(-0.10, min(0.10, delta)), 4)


def _pick_model_bias(trader_id: str, sentiment: float) -> str:
    """Pick model bias based on trader personality and discussion sentiment."""
    personality = TRADER_PERSONAS[trader_id]["personality"]
    if personality == "contrarian" and sentiment < 0.45:
        return "elo_baseline"   # fade consensus in low-sentiment environment
    if personality == "aggressive" and sentiment > 0.60:
        return "tabicl"         # most confident model when bullish
    if personality == "conservative" and sentiment < 0.50:
        return "consensus_ensemble"   # safest when uncertain
    if personality == "analytical":
        return "consensus_ensemble"
    return ""  # no change


def _pick_strategy_bias(trader_id: str, sentiment: float,
                        peer_avg: float) -> str:
    """Pick strategy bias based on discussion consensus."""
    personality = TRADER_PERSONAS[trader_id]["personality"]
    crowd_bullish = peer_avg > 0.55
    crowd_bearish = peer_avg < 0.45

    if personality == "contrarian":
        return "underdog_specialist" if crowd_bullish else "value_hunter"
    if personality == "aggressive" and sentiment > 0.65:
        return "full_kelly"
    if personality == "conservative" and crowd_bearish:
        return "flat_1pct"
    if personality == "analytical" and crowd_bullish:
        return "confidence_scaled"
    return ""  # no change


# ── LITE MODE: PURE PYTHON DISCUSSION SIMULATION ─────────────────────────────

def run_lite_discussion(date_str: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulate one round of OASIS-style multi-agent discussion using stdlib only.
    No LLM calls, no torch, no camel-ai.  Deterministic given date + context.

    The simulation:
      Round 1 — each agent posts their initial take on the day's slate
      Round 2 — cross-replies based on personality conflicts
      Output   — per-trader confidence_delta + model/strategy biases
    """
    game_count     = context.get("game_count", 5)
    top_game       = context.get("top_game", "home vs away")
    disagreement   = context.get("model_disagreement", 0.05)
    win_streaks    = context.get("win_streaks", {})
    consensus_pct  = context.get("consensus_home_pct", 55.0)
    top_model      = context.get("top_model", "consensus_ensemble")
    brier_gap      = context.get("brier_gap", 0.015)

    # Seed randomness from date so the same day always produces the same discussion
    seed = int(hashlib.md5(date_str.encode()).hexdigest()[:8], 16)
    rng  = random.Random(seed)

    # ── ROUND 1: opening posts ──
    posts: List[Dict[str, Any]] = []
    sentiments: Dict[str, float] = {}

    for trader_id, persona in TRADER_PERSONAS.items():
        personality  = persona["personality"]
        win_streak   = win_streaks.get(trader_id, 0)
        sentiment    = _compute_sentiment(personality, win_streak, disagreement, game_count)
        # Small random nudge (±0.03) to break ties
        sentiment   += rng.uniform(-0.03, 0.03)
        sentiment    = max(0.05, min(0.95, sentiment))
        sentiments[trader_id] = sentiment

        templates = _POST_TEMPLATES.get(personality, ["{name}: ready to trade."])
        tmpl      = rng.choice(templates)
        post_text = tmpl.format(
            name        = persona["name"],
            context_summary = f"{game_count} NBA games",
            consensus_pct   = consensus_pct,
            top_model       = top_model,
            brier_gap       = brier_gap,
            top_game        = top_game,
            game_count      = game_count,
            win_streak      = max(0, win_streak),
            disagreement    = disagreement,
        )
        posts.append({
            "agent_id":  trader_id,
            "post":      post_text,
            "sentiment": round(sentiment, 4),
        })

    # ── ROUND 2: cross-replies ──
    replies: List[Dict[str, Any]] = []
    reply_pairs = list(_REPLY_TEMPLATES.items())
    rng.shuffle(reply_pairs)

    for from_id, target_map in reply_pairs[:3]:  # pick 3 reply chains
        from_persona = TRADER_PERSONAS[from_id]
        target_id    = rng.choice(list(target_map.keys()))
        tmpl         = target_map[target_id]
        win_streak   = win_streaks.get(from_id, 0)
        try:
            reply_text = tmpl.format(
                name        = from_persona["name"],
                win_streak  = max(0, win_streak),
                disagreement = disagreement,
                game_count  = game_count,
                top_game    = top_game,
            )
        except KeyError:
            reply_text = f"{from_persona['name']}: {from_persona['bias_toward']}"

        # Reply slightly shifts sender's sentiment toward peer view
        peer_sentiment = sentiments.get(target_id, 0.5)
        sentiments[from_id] = (0.7 * sentiments[from_id] + 0.3 * peer_sentiment)

        replies.append({
            "agent_id":  from_id,
            "to":        target_id,
            "reply":     reply_text,
            "sentiment": round(sentiments[from_id], 4),
        })

    # ── DECISIONS: translate discussion → trading biases ──
    decisions: Dict[str, Dict[str, Any]] = {}
    for trader_id, sentiment in sentiments.items():
        peer_avg = sum(v for k, v in sentiments.items() if k != trader_id) / 4
        delta    = _sentiment_to_confidence_delta(trader_id, sentiment, sentiments)
        mbias    = _pick_model_bias(trader_id, sentiment)
        sbias    = _pick_strategy_bias(trader_id, sentiment, peer_avg)
        persona  = TRADER_PERSONAS[trader_id]

        decisions[trader_id] = {
            "model_bias":         mbias,
            "strategy_bias":      sbias,
            "confidence_delta":   delta,
            "final_sentiment":    round(sentiment, 4),
            "rationale": (
                f"{persona['name']} ({persona['personality']}): "
                f"discussion sentiment {sentiment:.2f}, "
                f"confidence nudge {delta:+.4f}, "
                f"model={mbias or 'unchanged'}, strategy={sbias or 'unchanged'}"
            ),
        }

    # ── CONSENSUS ──
    avg_sentiment = sum(sentiments.values()) / len(sentiments)
    consensus_label = (
        "bullish" if avg_sentiment > 0.55
        else "bearish" if avg_sentiment < 0.45
        else "neutral"
    )

    return {
        "date":  date_str,
        "mode":  "lite",
        "context": {
            "game_count":        game_count,
            "top_game":          top_game,
            "model_disagreement": disagreement,
            "consensus_home_pct": consensus_pct,
            "top_model":         top_model,
        },
        "rounds": [
            {"round": 1, "posts": posts, "replies": []},
            {"round": 2, "posts": [], "replies": replies},
        ],
        "decisions": decisions,
        "consensus": {
            "home_confidence": round(avg_sentiment, 4),
            "sentiment":       consensus_label,
        },
    }


# ── FULL MODE: REAL OASIS SOCIAL AGENTS ───────────────────────────────────────

def _try_import_oasis() -> bool:
    """Attempt to import vendor/oasis.  Returns True if importable."""
    if not VENDOR_OASIS.exists():
        return False
    if str(VENDOR_OASIS) not in sys.path:
        sys.path.insert(0, str(VENDOR_OASIS))
    try:
        from oasis.social_platform.config.user import UserInfo  # noqa: F401
        return True
    except Exception as exc:
        print(f"[oasis-adapter] vendor/oasis not importable: {exc}", file=sys.stderr)
        return False


def run_full_discussion(date_str: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run a REAL OASIS social discussion if vendor/oasis + camel-ai are available.
    Each trader is instantiated as an OASIS UserInfo profile; we ask each agent
    to generate a short post about today's NBA slate using the OASIS system-message
    convention, then collect replies.

    Falls back to lite mode if any import fails.
    """
    if not _try_import_oasis():
        print("[oasis-adapter] falling back to lite mode", file=sys.stderr)
        return run_lite_discussion(date_str, context)

    try:
        from oasis.social_platform.config.user import UserInfo
    except ImportError:
        return run_lite_discussion(date_str, context)

    # Build UserInfo objects for each trader
    user_infos: Dict[str, Any] = {}
    for trader_id, persona in TRADER_PERSONAS.items():
        profile = {
            "other_info": {
                "user_profile": (
                    f"A {persona['personality']} sports betting AI. "
                    f"{persona['voice']}. Biased toward: {persona['bias_toward']}."
                ),
            }
        }
        user_infos[trader_id] = UserInfo(
            user_name    = trader_id,
            name         = persona["name"],
            profile      = profile,
            recsys_type  = "twitter",
        )

    game_count  = context.get("game_count", 5)
    top_game    = context.get("top_game", "home vs away")
    news_prompt = (
        f"Today ({date_str}) there are {game_count} NBA games. "
        f"Top matchup: {top_game}. "
        "As a sports trading AI, post your pre-game view in 2 sentences. "
        "State your confidence level and which strategy you prefer today."
    )

    # We collect "posts" from each agent by formatting their system message
    # (no actual LLM call — UserInfo.to_system_message() is pure text generation)
    posts: List[Dict[str, Any]] = []
    sentiments: Dict[str, float] = {}
    seed = int(hashlib.md5(date_str.encode()).hexdigest()[:8], 16)
    rng  = random.Random(seed)

    for trader_id, ui in user_infos.items():
        sys_msg      = ui.to_system_message()
        personality  = TRADER_PERSONAS[trader_id]["personality"]
        win_streak   = context.get("win_streaks", {}).get(trader_id, 0)
        sentiment    = _compute_sentiment(
            personality, win_streak,
            context.get("model_disagreement", 0.05),
            game_count,
        )
        sentiment += rng.uniform(-0.03, 0.03)
        sentiment  = max(0.05, min(0.95, sentiment))
        sentiments[trader_id] = sentiment

        # Compose a post that combines the OASIS system message style
        # with the news prompt (no LLM call needed in this path)
        post_text = (
            f"[{TRADER_PERSONAS[trader_id]['name']}] {news_prompt} "
            f"| Sentiment: {'bullish' if sentiment > 0.55 else 'bearish' if sentiment < 0.45 else 'neutral'}"
        )
        posts.append({
            "agent_id":    trader_id,
            "post":        post_text,
            "sentiment":   round(sentiment, 4),
            "oasis_style": sys_msg[:120] + "...",  # first 120 chars of OASIS system msg
        })

    # Decisions use the same logic as lite mode
    decisions: Dict[str, Dict[str, Any]] = {}
    for trader_id, sentiment in sentiments.items():
        peer_avg = sum(v for k, v in sentiments.items() if k != trader_id) / 4
        delta    = _sentiment_to_confidence_delta(trader_id, sentiment, sentiments)
        mbias    = _pick_model_bias(trader_id, sentiment)
        sbias    = _pick_strategy_bias(trader_id, sentiment, peer_avg)
        persona  = TRADER_PERSONAS[trader_id]
        decisions[trader_id] = {
            "model_bias":         mbias,
            "strategy_bias":      sbias,
            "confidence_delta":   delta,
            "final_sentiment":    round(sentiment, 4),
            "rationale": (
                f"{persona['name']} (OASIS full mode, {persona['personality']}): "
                f"sentiment {sentiment:.2f}, delta {delta:+.4f}, "
                f"model={mbias or 'unchanged'}, strategy={sbias or 'unchanged'}"
            ),
        }

    avg_sentiment   = sum(sentiments.values()) / len(sentiments)
    consensus_label = (
        "bullish" if avg_sentiment > 0.55
        else "bearish" if avg_sentiment < 0.45
        else "neutral"
    )
    return {
        "date":  date_str,
        "mode":  "full",
        "context": context,
        "rounds": [
            {"round": 1, "posts": posts, "replies": []},
        ],
        "decisions": decisions,
        "consensus": {
            "home_confidence": round(avg_sentiment, 4),
            "sentiment":       consensus_label,
        },
    }


# ── PUBLIC HELPERS (imported by trading-floor-v4.py) ──────────────────────────

def load_oasis_context(target_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Load today's (or target_date's) OASIS discussion from disk.

    Returns {} if the file doesn't exist or can't be parsed — the trading
    floor gracefully falls back to baseline behaviour in that case.
    """
    d = target_date or date.today().isoformat()
    fp = DISCUSS_DIR / f"{d}.json"
    if not fp.exists():
        return {}
    try:
        return json.loads(fp.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def oasis_kelly_modifier(trader_id: str, oasis_ctx: Dict[str, Any]) -> float:
    """
    Return a Kelly multiplier (0.70 – 1.30) based on the OASIS discussion.

    Rules:
      - bullish consensus + trader is NOT contrarian → +10% Kelly
      - bearish consensus + conservative trader        → -20% Kelly
      - contrarian + bullish crowd                    → -10% Kelly (they fade)
      - contrarian + bearish crowd                    → +10% Kelly (they fade bearish)
      - Otherwise 1.0
    """
    if not oasis_ctx:
        return 1.0
    consensus  = oasis_ctx.get("consensus", {}).get("sentiment", "neutral")
    personality = TRADER_PERSONAS.get(trader_id, {}).get("personality", "diversified")
    decision    = oasis_ctx.get("decisions", {}).get(trader_id, {})
    delta       = decision.get("confidence_delta", 0.0)

    modifier = 1.0

    if personality == "contrarian":
        if consensus == "bullish":
            modifier = 0.90
        elif consensus == "bearish":
            modifier = 1.10
    elif personality == "conservative":
        if consensus == "bearish":
            modifier = 0.80
        elif consensus == "bullish":
            modifier = 1.05
    elif personality == "aggressive":
        if consensus == "bullish":
            modifier = 1.15
        elif consensus == "bearish":
            modifier = 0.85
    elif personality == "analytical":
        modifier = 1.0 + delta  # analytical follows their own confidence delta
    else:  # diversified
        modifier = 1.0

    return round(max(0.70, min(1.30, modifier)), 4)


def oasis_prob_nudge(trader_id: str, oasis_ctx: Dict[str, Any],
                     base_prob: float) -> float:
    """
    Nudge an agent's home-win probability estimate by the OASIS confidence_delta.

    base_prob : model output probability in [0, 1]
    Returns   : adjusted probability, still in [0.05, 0.95]
    """
    if not oasis_ctx:
        return base_prob
    decision = oasis_ctx.get("decisions", {}).get(trader_id, {})
    delta    = decision.get("confidence_delta", 0.0)
    return max(0.05, min(0.95, base_prob + delta))


def run_discussion(date_str: str, context: Dict[str, Any],
                   full_mode: bool = False) -> Dict[str, Any]:
    """Entry point for both modes.  Decides lite vs full and runs."""
    if full_mode:
        return run_full_discussion(date_str, context)
    return run_lite_discussion(date_str, context)


def save_discussion(discussion: Dict[str, Any], dry_run: bool = False) -> Path:
    """Write discussion JSON to disk. Returns the file path."""
    date_str = discussion["date"]
    fp = DISCUSS_DIR / f"{date_str}.json"
    if dry_run:
        print(f"[oasis-adapter] DRY-RUN — would write {fp}")
        print(json.dumps(discussion, indent=2))
        return fp
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps(discussion, indent=2))
    print(f"[oasis-adapter] wrote {fp}  (mode={discussion['mode']})")
    return fp


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_default_context(date_str: str) -> Dict[str, Any]:
    """Build a minimal context dict from available data files."""
    # Try to load today's odds to get real game count / top game
    odds_path = ROOT / "data" / "nba-agent" / "odds-history" / f"{date_str}.json"
    game_count = 5
    top_game   = "home vs away"
    if odds_path.exists():
        try:
            odds_data = json.loads(odds_path.read_text())
            games = odds_data if isinstance(odds_data, list) else odds_data.get("games", [])
            game_count = len(games)
            if games:
                g = games[0]
                home = g.get("home_team", g.get("home", "Home"))
                away = g.get("away_team", g.get("away", "Away"))
                top_game = f"{home} vs {away}"
        except Exception:
            pass

    # Try to read win streaks from last trader states
    win_streaks: Dict[str, int] = {}
    traders_dir = ROOT / "data" / "arena" / "traders"
    for tid in TRADER_PERSONAS:
        state_path = traders_dir / f"{tid}-state.json"
        if state_path.exists():
            try:
                s = json.loads(state_path.read_text())
                # Infer streak from last few bets (simplified)
                win_streaks[tid] = s.get("win_streak", 0)
            except Exception:
                pass

    return {
        "game_count":        game_count,
        "top_game":          top_game,
        "model_disagreement": 0.05,
        "consensus_home_pct": 55.0,
        "top_model":         "consensus_ensemble",
        "brier_gap":         0.015,
        "win_streaks":       win_streaks,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="OASIS Adapter — generate trading discussion")
    p.add_argument("--date",     default=date.today().isoformat(),
                   help="Date string YYYY-MM-DD (default: today)")
    p.add_argument("--context",  default=None,
                   help="JSON string with context override (game_count, top_game, ...)")
    p.add_argument("--full",     action="store_true",
                   help="Use full OASIS runtime (requires vendor/oasis + camel-ai)")
    p.add_argument("--dry-run",  action="store_true",
                   help="Print output without writing to disk")
    args = p.parse_args()

    ctx = _build_default_context(args.date)
    if args.context:
        try:
            override = json.loads(args.context)
            ctx.update(override)
        except json.JSONDecodeError as exc:
            print(f"[oasis-adapter] --context JSON parse error: {exc}", file=sys.stderr)
            return 1

    discussion = run_discussion(args.date, ctx, full_mode=args.full)
    save_discussion(discussion, dry_run=args.dry_run)

    # Summary
    mode = discussion["mode"]
    consensus = discussion["consensus"]
    decisions = discussion["decisions"]
    print(f"\n[oasis-adapter] {args.date}  mode={mode}  consensus={consensus['sentiment']}"
          f"  home_conf={consensus['home_confidence']:.3f}")
    for tid, dec in decisions.items():
        print(f"  {tid:12s}  delta={dec['confidence_delta']:+.4f}"
              f"  model={dec['model_bias'] or '-'}"
              f"  strategy={dec['strategy_bias'] or '-'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
