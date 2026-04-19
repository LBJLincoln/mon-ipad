"""ITF personas — 6 intraday LLM agents, ALL self-hosted.

Directive (2026-04-19): intraday agents MUST run on self-hosted Spaces only.
ITF runs every 15 min during market hours × 6 agents = ~168 calls/day; only
selfhost can sustain that without starving NBA TF / POL TF cloud quota.

Audit (2026-04-18 gateway probe):
  HEALTHY  selfhost:qwen3-4b       (Nomos42/qwen3-4b-cpu)
  HEALTHY  selfhost:gemma-3-4b     (Nomos42/gemma2-2b-cpu)
  HEALTHY  selfhost:qwen3-0.6b     (Nomos42/qwen25-05b-cpu)
  HEALTHY  selfhost:dolphin3-l32-3b(Nomos42/llama32-1b-cpu)
  BROKEN   selfhost:phi-4-mini     (Nomos42/nomos42-llm-cpu — RUNTIME_ERROR, segfault)
  BROKEN   selfhost:smollm3-3b     (llama-cpp-python 0.3.9 cannot load GGUF)

Concretely we have 4 healthy self-hosted models today. To get to 6 we MUST
provision 2 new selfhost Spaces on LBJLincoln + TESTforge42 (see
docs/INTRADAY-ROUTING-MATRIX.md). Until then, scalper+momentum share
qwen3-0.6b / gemma-3-4b with distinct system prompts and distinct fallbacks.

Account distribution target (from routing matrix):
  scalper-1   Nomos42/qwen25-05b-cpu
  momentum-1  LBJLincoln/gemma2-2b-cpu-lbj       ← TO PROVISION
  mean-rev-1  LBJLincoln26/qwen3-4b-cpu-lbj26    ← TO PROVISION
  breakout-1  TESTforge42/llama32-1b-cpu-tf42    ← TO PROVISION
  pairs-1     Nomos42/qwen3-4b-cpu (reuse, longest ctx of healthy set)
  vol-1       TESTforge42/gemma2-2b-cpu-tf42     ← TO PROVISION

COLLECTIVE_MISSION + AXELROD_CANON prepended at call time by app.py.
"""
from __future__ import annotations

from typing import Any, Dict, List

PERSONAS: List[Dict[str, Any]] = [
    {
        "tid": "scalper-1",
        "name": "Scalper",
        "model_primary": "selfhost:qwen3-0.6b",
        "model_fallback": "selfhost:gemma-3-4b",
        "hf_account_target": "Nomos42",
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
        "model_primary": "selfhost:gemma-3-4b",
        "model_fallback": "selfhost:qwen3-4b",
        "hf_account_target": "LBJLincoln",
        "hf_space_target": "gemma2-2b-cpu-lbj",
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
        "model_primary": "selfhost:qwen3-4b",
        "model_fallback": "selfhost:gemma-3-4b",
        "hf_account_target": "LBJLincoln26",
        "hf_space_target": "qwen3-4b-cpu-lbj26",
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
        "model_primary": "selfhost:dolphin3-l32-3b",
        "model_fallback": "selfhost:qwen3-4b",
        "hf_account_target": "TESTforge42",
        "hf_space_target": "llama32-1b-cpu-tf42",
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
        "model_primary": "selfhost:qwen3-4b",
        "model_fallback": "selfhost:dolphin3-l32-3b",
        "hf_account_target": "Nomos42",
        "hf_space_target": "qwen3-4b-cpu",
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
        "model_primary": "selfhost:gemma-3-4b",
        "model_fallback": "selfhost:qwen3-0.6b",
        "hf_account_target": "TESTforge42",
        "hf_space_target": "gemma2-2b-cpu-tf42",
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
