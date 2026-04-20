"""ITF personas — 6 intraday LLM agents, routed at proven winners.

Winner attribution across fleets (2026-04-19 live state):
  PQTF (completed 50/50, $600→$602K):
    mistral:large        $244K  (+40,667% — 60.2% of the $1M mission alone)
    mistral:medium       $155K  (+25,783%)
    google:gemini-2.5-flash (gemini-anl) $17K
  POL TF (day 23/50):
    google:gemini-3-flash (gemini-anl)  $470.72 (+370.7%) ★
    google:gemini-3-flash (gemini-tact) $408.40 (+308.4%) ★
    mistral:nemo         $115.57
    cerebras:llama3.1-8b (llama-contra) $114.91
  NBA TF (day 128/175, harsh regime):
    selfhost:dolphin3-l32-3b $316.20 ★ (only selfhost to 3x)
    cerebras:qwen-3-235b (qwen-quant) $26.06

ITF picks cloud-winner primaries and keeps selfhost as fallback (free + cheap
when cloud rate-limits). Personas retain their trading style — only the LLM
backing changes.

Routing rule: no Nomos42/* URLs referenced anywhere (that account is saturated).
Gateway `selfhost:*` keys now route to 3 HTTP-verified LBJLincoln Spaces.

COLLECTIVE_MISSION + AXELROD_CANON prepended at call time by app.py.
"""
from __future__ import annotations

from typing import Any, Dict, List

# Appended to every persona.style at prompt build time so every agent knows it
# has a crypto lane when equities are closed. Before this clause, 04-20 logs
# showed 84% pass rate dominated by "market closed, vol=0" reasons — personas
# were ignoring the 10 crypto pairs the schema explicitly whitelisted.
CRYPTO_PIVOT_CLAUSE = (
    " OFF-HOURS RULE: when equities are closed (weekend/night), pivot your "
    "style to BTC/USD, ETH/USD, SOL/USD, AVAX/USD, LINK/USD, DOGE/USD — "
    "they trade 24/7 on Alpaca. You MUST emit a crypto trade if at least ONE "
    "of {BTC, ETH, SOL} shows |change_pct| > 0.3% in the tape. Passing every "
    "tick because 'equities closed' is cowardice — the leaderboard punishes it."
)

PERSONAS: List[Dict[str, Any]] = [
    {
        "tid": "scalper-1",
        "name": "Scalper",
        # gemini-3-flash was 100% llm_failed_both on ITF (thinking-budget bug in gateway);
        # selfhost:qwen3-0.6b fallback also unreachable. Route at mistral:medium (PQTF #2).
        "model_primary": "mistral:medium",
        "model_fallback": "cerebras:llama3.1-8b",
        "hf_account_target": "mistral",
        "hf_space_target": "medium",
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
        "model_primary": "mistral:large",                # PQTF #1: $244K winner
        "model_fallback": "mistral:medium",
        "hf_account_target": "mistral",
        "hf_space_target": "large",
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
        # 2026-04-20: user asked for nemotron + minimax to actually be used.
        # openrouter:nemotron-120b:free is FREE-tier and was the NBA T11 chainthought
        # trader; perfect fit for mean-reversion "fade the extreme" reasoning.
        # mistral:medium fallback keeps us solvent if openrouter rate-limits.
        "model_primary": "openrouter:nemotron-120b:free",
        "model_fallback": "mistral:medium",
        "hf_account_target": "openrouter",
        "hf_space_target": "nemotron-120b",
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
        # 2026-04-20: user asked minimax m2.7 be used — it's the NVIDIA NIM free
        # lane (T13 NBA "decisive" trader). Breakouts reward decisiveness, so
        # this is a fit. cerebras:qwen-3-235b fallback keeps analytical backup.
        "model_primary": "nvidia:minimax-m2.7",
        "model_fallback": "cerebras:qwen-3-235b",
        "hf_account_target": "nvidia",
        "hf_space_target": "minimax-m2.7",
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
        "model_primary": "mistral:medium",               # PQTF #2: $155K winner
        "model_fallback": "mistral:small",
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
        # dolphin3-l32-3b is NBA TF's 3× winner but its selfhost endpoint 45s-timeouts
        # on ITF. Reroute to cerebras:qwen-3-235b (NBA qwen-quant) + mistral:medium.
        "model_primary": "cerebras:qwen-3-235b",
        "model_fallback": "mistral:medium",
        "hf_account_target": "cerebras",
        "hf_space_target": "qwen-3-235b",
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
    {
        "tid": "options-1",
        "name": "GammaOptions",
        "model_primary": "mistral:large",                 # PQTF #1 winner — top derivatives brain
        "model_fallback": "mistral:medium",
        "hf_account_target": "mistral",
        "hf_space_target": "large",
        "tier": "L",
        "risk": 0.55,
        "max_hold_min": 240,
        "style": (
            "You are GAMMA-OPTIONS — you trade 0DTE/1DTE options on SPY/QQQ/IWM "
            "(occasionally XLE/XLK/XLF/NVDA/TSLA for single-name catalysts). "
            "Strategy selection rules: "
            "(a) IV rank < 30% + directional conviction → long call or long put (gamma buy). "
            "(b) IV rank > 70% + range thesis → iron_condor or vertical_credit (gamma sell). "
            "(c) Pre-catalyst / FOMC / CPI → straddle (long vol). "
            "(d) Mild directional + IV neutral → vertical_debit (defined risk). "
            "Emit action='option_trade'. Always cite IV rank, realized vol, or skew in thesis. "
            "Max stake $1500/ticket. Max loss ≤ stake_usd. Skip if VIX > 30 (whipsaw risk)."
        ),
    },
]


def get(tid: str) -> Dict[str, Any]:
    for p in PERSONAS:
        if p["tid"] == tid:
            return p
    raise KeyError(tid)


# Append the off-hours crypto pivot to every persona at import time so every
# prompt downstream gets it automatically.
for _p in PERSONAS:
    if CRYPTO_PIVOT_CLAUSE not in _p["style"]:
        _p["style"] = _p["style"] + CRYPTO_PIVOT_CLAUSE
