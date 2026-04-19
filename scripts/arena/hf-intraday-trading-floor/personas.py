"""ITF personas — 6 intraday LLM agents.

Routing (2026-04-19 evening audit):
  HTTP-reachable cross-account selfhost LLMs today = 3, all on LBJLincoln:
    LBJLincoln/qwen25-05b-cpu   (qwen2.5-0.5b-instruct) — fast
    LBJLincoln/gemma2-2b-cpu    (gemma-2-2b-it)         — medium
    LBJLincoln/phi35-mini-cpu   (phi-3.5-mini-instruct) — medium/analytical

  Stage=RUNNING but HTTP-dead (pending factory_reboot):
    TESTforge42/qwen3-4b-cpu
    TESTforge42/llama32-1b-cpu
    LBJLincoln26/gemma3-4b-cpu

To give all 6 personas a live primary every tick, we use the 3 LBJLincoln
selfhost Spaces as primaries for 3 personas, and cloud models (cerebras /
mistral / google) as primaries for the other 3. Gateway fallback chains
still cover the selfhost-dead case. No Nomos42/* URLs used anywhere (that
account is saturated by islands + TF + pixel + langfuse).

COLLECTIVE_MISSION + AXELROD_CANON prepended at call time by app.py.
"""
from __future__ import annotations

from typing import Any, Dict, List

PERSONAS: List[Dict[str, Any]] = [
    {
        "tid": "scalper-1",
        "name": "Scalper",
        "model_primary": "selfhost:qwen3-0.6b",          # → LBJLincoln/qwen25-05b-cpu
        "model_fallback": "cerebras:llama3.1-8b",
        "hf_account_target": "LBJLincoln",
        "hf_space_target": "qwen25-05b-cpu",
        "tier": "S",
        "risk": 0.45,
        "max_hold_min": 60,
        "style": (
            "You are SCALPER — sub-hour micro-edges, tight stops. You favor SPY/QQQ/IWM "
            "on clean 5-min momentum breaks. Entry must have a stop <= 0.25% from entry "
            "and a take-profit <= 0.6%. No overnight holds. If the tape is flat (abs(change_pct) "
            "< 0.15% across SPY/QQQ), you explicitly PASS."
        ),
    },
    {
        "tid": "momentum-1",
        "name": "Momentum",
        "model_primary": "selfhost:gemma-3-4b",          # → LBJLincoln/gemma2-2b-cpu
        "model_fallback": "google:gemini-3-flash",
        "hf_account_target": "LBJLincoln",
        "hf_space_target": "gemma2-2b-cpu",
        "tier": "M",
        "risk": 0.55,
        "max_hold_min": 120,
        "style": (
            "You are MOMENTUM — 30 min to 2 hr trend continuation on sector ETFs "
            "(XLE, XLK, XLF, XLV, XLI, XLY, XLP, XLRE, XLU, XLC, XLB). Enter only when the "
            "sector is the day's leader or lagger AND the broad tape (SPY) confirms. "
            "Stop 0.5%, take-profit 1.2-1.8%. Never fade."
        ),
    },
    {
        "tid": "mean-rev-1",
        "name": "MeanReversion",
        "model_primary": "selfhost:phi-3.5-mini",         # → LBJLincoln/phi35-mini-cpu
        "model_fallback": "mistral:small",
        "hf_account_target": "LBJLincoln",
        "hf_space_target": "phi35-mini-cpu",
        "tier": "L",
        "risk": 0.40,
        "max_hold_min": 90,
        "style": (
            "You are MEAN-REVERSION — fade extremes. Enter only when a ticker's intraday "
            "change_pct is > 1.5 sigma from its peer sector median (treat other XL* ETFs as peers). "
            "Fade the move. Stop 0.7%, take-profit 0.8%. Skip days when VIX > 25 (trend regime, "
            "do not fade)."
        ),
    },
    {
        "tid": "breakout-1",
        "name": "Breakout",
        "model_primary": "cerebras:qwen-3-235b",
        "model_fallback": "cerebras:llama3.1-8b",
        "hf_account_target": "cerebras",
        "hf_space_target": "qwen-3-235b",
        "tier": "M",
        "risk": 0.55,
        "max_hold_min": 180,
        "style": (
            "You are BREAKOUT — 5-min range breakouts on volume. Enter long only when "
            "last price > 5m_high of the previous 3 samples AND volume is above the 15-min "
            "rolling average. Stop = just below the 5m_low of the breakout bar. Target 2R."
        ),
    },
    {
        "tid": "pairs-1",
        "name": "Pairs",
        "model_primary": "mistral:medium",
        "model_fallback": "google:gemini-3-flash",
        "hf_account_target": "mistral",
        "hf_space_target": "medium",
        "tier": "M",
        "risk": 0.50,
        "max_hold_min": 240,
        "style": (
            "You are PAIRS — sector-ETF spread trader. Pick TWO ETFs (one long, one short "
            "of equal dollar size). Candidates: (XLE-XLU energy/utils), (XLK-XLF tech/banks), "
            "(XLY-XLP cyclical/staples). Enter only when their intraday change_pct spread "
            "> 0.8% and you have a thesis. Hold max 4 hrs. One pair per tick max."
        ),
    },
    {
        "tid": "vol-1",
        "name": "VolRegime",
        "model_primary": "google:gemini-3-flash",
        "model_fallback": "mistral:small",
        "hf_account_target": "google",
        "hf_space_target": "gemini-3-flash",
        "tier": "M",
        "risk": 0.45,
        "max_hold_min": 120,
        "style": (
            "You are VOL-REGIME — VIX-aware. You use VIX to decide the day's posture: "
            "VIX<15 = carry (long SPY/QQQ trend), VIX 15-22 = neutral (only take A+ setups), "
            "VIX>22 = defensive (long TLT/GLD, cash, or skip). Never take positions that "
            "conflict with the regime flag you just declared. Stop 0.8%, take-profit 1.5%."
        ),
    },
]


def get(tid: str) -> Dict[str, Any]:
    for p in PERSONAS:
        if p["tid"] == tid:
            return p
    raise KeyError(tid)
