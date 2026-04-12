#!/usr/bin/env python3
"""
TRADINGAGENTS-STYLE BULL vs BEAR DEBATE
=========================================
Lightweight adaptation of the TauricResearch/TradingAgents LangGraph pattern
for TF v5 Stage 2. We run a multi-round debate on T1 Premium predictions:

    Round 1: Bull states thesis → Bear rebuts
    Round 2: Bull counter-rebuts → Bear counter-rebuts
    Final:   Risk Judge decides verdict + conviction [0-1]

Why here (not in LangGraph): the VM is 1vCPU/969MB. We reuse the existing
api_pool so no extra deps, and the debate is fully gated behind dry_run.

Returns None on any failure — caller must fall back to existing peer_review.
"""

import json
from typing import Optional

# 2026-04-12: HF Inference credits exhausted. Updated routing:
#   BULL: cerebras (qwen-3-235b, 1M tok/day, working)
#   BEAR: google key rotation (KEY_2 working, KEY_1 as fallback)
#   JUDGE: google key rotation (same)
# huggingface + groq: DEAD (credits/banned).
# anthropic_cli uses subprocess (call_llm_cli), not call_llm — cannot use here.
BULL_PROVIDER = "cerebras"
BEAR_PROVIDER = "google"
JUDGE_PROVIDER = "google"

# Model overrides for Cerebras (must use exact model name from /v1/models)
BULL_MODEL = "qwen-3-235b-a22b-instruct-2507"
BEAR_MODEL = None    # google: uses default (gemini-2.5-flash first key in pool)
JUDGE_MODEL = None   # google: uses default

DEFAULT_ROUNDS = 2
MAX_ARG_TOKENS = 350
MAX_JUDGE_TOKENS = 512


def _format_predictions_summary(predictions: dict, limit: int = 9) -> str:
    """Condense T1 Premium predictions into a short bullet list."""
    rows = []
    for aid, pred in list(predictions.items())[:limit]:
        tier = pred.get("_agent_tier", "?")
        if tier != "PREMIUM":
            continue
        ml = pred.get("ml_fg", {}) if isinstance(pred.get("ml_fg"), dict) else {}
        direction = ml.get("direction", "?")
        conf = ml.get("confidence", 0)
        edge = ml.get("edge_pct", 0)
        rows.append(f"  - {aid[:24]}: {direction} (conf={conf:.2f}, edge={edge}%)")
    return "\n".join(rows) if rows else "  (no T1 predictions)"


def _bull_prompt(ctx: dict, preds_summary: str, bear_previous: Optional[str]) -> str:
    away = ctx.get("away_team", ctx.get("away", "?"))
    home = ctx.get("home_team", ctx.get("home", "?"))
    base = (
        f"You are the BULL RESEARCHER on {away} @ {home}. "
        f"You argue FOR the strongest edge in the T1 Premium predictions below.\n\n"
        f"T1 PREMIUM PREDICTIONS:\n{preds_summary}\n"
    )
    if bear_previous:
        base += f"\nBEAR'S LAST ARGUMENT:\n{bear_previous}\n\nRebut the bear. "
    base += (
        "Build one concrete, data-driven bull thesis (max 4 sentences). "
        'Respond with JSON: {"argument": "<text>", "key_signal": "<str>", "confidence": <0-1>}'
    )
    return base


def _bear_prompt(ctx: dict, preds_summary: str, bull_previous: str) -> str:
    away = ctx.get("away_team", ctx.get("away", "?"))
    home = ctx.get("home_team", ctx.get("home", "?"))
    return (
        f"You are the BEAR RESEARCHER on {away} @ {home}. "
        f"You argue AGAINST the bull thesis.\n\n"
        f"T1 PREMIUM PREDICTIONS:\n{preds_summary}\n\n"
        f"BULL'S ARGUMENT:\n{bull_previous}\n\n"
        "Rebut with concrete downside risk (injuries, schedule, variance, line move). "
        "Max 4 sentences. "
        'Respond with JSON: {"argument": "<text>", "key_risk": "<str>", "confidence": <0-1>}'
    )


def _judge_prompt(ctx: dict, rounds: list) -> str:
    away = ctx.get("away_team", ctx.get("away", "?"))
    home = ctx.get("home_team", ctx.get("home", "?"))
    transcript = []
    for i, r in enumerate(rounds, start=1):
        transcript.append(f"Round {i} BULL: {r.get('bull', {}).get('argument', '')}")
        transcript.append(f"Round {i} BEAR: {r.get('bear', {}).get('argument', '')}")
    return (
        f"You are the RISK JUDGE on {away} @ {home}. Read the Bull vs Bear "
        f"debate below and issue a verdict.\n\n"
        + "\n".join(transcript)
        + "\n\nWeigh evidence quality, not rhetoric. "
        'Respond with JSON: {"verdict": "bull"|"bear"|"tie", '
        '"conviction": <0-1>, "reasoning": "<3 sentences>", '
        '"recommended_action": "bet"|"skip"|"reduce_size"}'
    )


def run_bull_bear_debate(pool, ctx: dict, predictions: dict,
                         rounds: int = DEFAULT_ROUNDS,
                         dry_run: bool = False) -> Optional[dict]:
    """
    Run a multi-round Bull vs Bear debate on T1 Premium predictions.

    Args:
        pool: api_pool.APIPool instance with call_llm(provider, prompt, ...)
        ctx: game context dict (home_team, away_team, ...)
        predictions: dict of agent_id -> prediction dict
        rounds: number of bull/bear exchanges
        dry_run: if True, skip LLM calls and return a synthetic debate

    Returns:
        dict with {rounds, verdict, conviction, reasoning,
                   recommended_action, source} or None on failure.
    """
    # Only debate if we have at least 3 T1 Premium predictions
    premium_preds = {
        aid: p for aid, p in predictions.items()
        if p.get("_agent_tier") == "PREMIUM"
    }
    if len(premium_preds) < 3:
        return None

    if dry_run:
        return {
            "rounds": [],
            "verdict": "tie",
            "conviction": 0.5,
            "reasoning": "dry-run — debate skipped",
            "recommended_action": "skip",
            "premium_count": len(premium_preds),
            "source": "dry_run_stub",
        }

    preds_summary = _format_predictions_summary(premium_preds)
    debate_rounds = []
    bear_previous: Optional[str] = None

    for round_idx in range(rounds):
        # BULL — cerebras primary, google fallback
        bull_result = pool.call_llm(
            provider=BULL_PROVIDER,
            prompt=_bull_prompt(ctx, preds_summary, bear_previous),
            model=BULL_MODEL,
            max_tokens=MAX_ARG_TOKENS,
            temperature=0.4,
        )
        if not bull_result or not isinstance(bull_result, dict):
            # Fallback: try google
            bull_result = pool.call_llm(
                provider="google",
                prompt=_bull_prompt(ctx, preds_summary, bear_previous),
                model=BEAR_MODEL,
                max_tokens=MAX_ARG_TOKENS,
                temperature=0.4,
            )
        if not bull_result or not isinstance(bull_result, dict):
            return None
        bull_text = bull_result.get("argument", "") or ""
        if not bull_text:
            return None

        # BEAR — google primary, cerebras fallback
        bear_result = pool.call_llm(
            provider=BEAR_PROVIDER,
            prompt=_bear_prompt(ctx, preds_summary, bull_text),
            model=BEAR_MODEL,
            max_tokens=MAX_ARG_TOKENS,
            temperature=0.4,
        )
        if not bear_result or not isinstance(bear_result, dict):
            # Fallback: try cerebras
            bear_result = pool.call_llm(
                provider="cerebras",
                prompt=_bear_prompt(ctx, preds_summary, bull_text),
                model=BULL_MODEL,
                max_tokens=MAX_ARG_TOKENS,
                temperature=0.4,
            )
        if not bear_result or not isinstance(bear_result, dict):
            return None
        bear_text = bear_result.get("argument", "") or ""
        if not bear_text:
            return None

        debate_rounds.append({"bull": bull_result, "bear": bear_result})
        bear_previous = bear_text

    # JUDGE — google primary, cerebras fallback
    verdict = pool.call_llm(
        provider=JUDGE_PROVIDER,
        prompt=_judge_prompt(ctx, debate_rounds),
        model=JUDGE_MODEL,
        max_tokens=MAX_JUDGE_TOKENS,
        temperature=0.2,
    )
    if not verdict or not isinstance(verdict, dict):
        verdict = pool.call_llm(
            provider="cerebras",
            prompt=_judge_prompt(ctx, debate_rounds),
            model=BULL_MODEL,
            max_tokens=MAX_JUDGE_TOKENS,
            temperature=0.2,
        )
    if not verdict or not isinstance(verdict, dict):
        return None

    conviction = verdict.get("conviction", 0.5)
    try:
        conviction = float(conviction)
    except (TypeError, ValueError):
        conviction = 0.5

    return {
        "rounds": debate_rounds,
        "verdict": verdict.get("verdict", "tie"),
        "conviction": round(max(0.0, min(1.0, conviction)), 3),
        "reasoning": verdict.get("reasoning", "")[:500],
        "recommended_action": verdict.get("recommended_action", "skip"),
        "premium_count": len(premium_preds),
        "source": "llm_debate",
    }


if __name__ == "__main__":
    # Smoke test: dry_run only (no LLM calls)
    fake_preds = {
        f"t1_prem_{i}": {
            "_agent_tier": "PREMIUM",
            "ml_fg": {"direction": "home", "confidence": 0.7, "edge_pct": 4.0},
        }
        for i in range(4)
    }
    result = run_bull_bear_debate(
        pool=None,
        ctx={"home_team": "LAL", "away_team": "BOS"},
        predictions=fake_preds,
        dry_run=True,
    )
    print(json.dumps(result, indent=2))
