#!/usr/bin/env python3
"""
AGENT REGISTRY — 220+ Trading Floor Agents in 4 Tiers
======================================================
Tier 1: Premium Traders (14) — 5 named + 4 HF base + 5 Claude CLI, full game analysis
Tier 2: Free Power Traders (25) — best free models, focused analysis
Tier 3: Specialist Swarm (176+) — one agent per bet category side
Tier 4: Meta-Traders (3) — Paperclip, Hermes, Oracle

Total: 222+ agents, ~1,000 API calls/day for 5 games
"""

import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum

from bet_categories import (
    ALL_CATEGORIES, CATEGORY_BY_ID, CATEGORIES_BY_GROUP,
    TOTAL_SPECIALIST_AGENTS, BetCategory,
    get_specialist_prompt, get_tier2_prompt, get_tier1_prompt, get_meta_prompt,
)


class AgentTier(Enum):
    PREMIUM = 1
    FREE_POWER = 2
    SPECIALIST = 3
    META = 4


@dataclass
class TradingAgent:
    """A single trading agent on the floor."""
    id: str
    name: str
    tier: AgentTier
    provider: str           # matches api_pool provider key
    model: str              # specific model to use
    strategy: str           # betting strategy name
    focus_groups: List[str] = field(default_factory=list)   # bet category groups
    focus_category: Optional[str] = None                     # specialist: specific category
    focus_side: int = 0                                      # specialist: which side
    personality: str = "analytical"
    min_edge: float = 0.02
    risk_tolerance: float = 0.5
    kelly_fraction: float = 0.5   # what fraction of Kelly to use
    bankroll: float = 100.0
    peak_bankroll: float = 100.0
    total_bets: int = 0
    total_wins: int = 0
    total_pnl: float = 0.0
    win_streak: int = 0
    accuracy_history: List[float] = field(default_factory=list)
    weight: float = 1.0     # meta-trader weight (updated by retrolearning)
    active: bool = True
    description: str = ""

    @property
    def win_rate(self) -> float:
        return self.total_wins / self.total_bets if self.total_bets > 0 else 0.0

    @property
    def roi(self) -> float:
        return (self.bankroll - 100.0) / 100.0 * 100

    @property
    def rolling_accuracy(self) -> float:
        if not self.accuracy_history:
            return 0.5
        recent = self.accuracy_history[-20:]
        return sum(recent) / len(recent)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "tier": self.tier.name,
            "provider": self.provider,
            "model": self.model,
            "strategy": self.strategy,
            "bankroll": round(self.bankroll, 2),
            "total_bets": self.total_bets,
            "total_wins": self.total_wins,
            "win_rate": round(self.win_rate, 4),
            "roi": round(self.roi, 2),
            "total_pnl": round(self.total_pnl, 2),
            "weight": round(self.weight, 4),
            "active": self.active,
        }


# ============================================================================
# TIER 1: PREMIUM TRADERS (14 agents — 4 HF base + 5 named + 5 Claude CLI)
# ============================================================================
def _build_tier1() -> List[TradingAgent]:
    """14 premium traders: 4 base + 5 named visible + 5 deep thinkers.

    2026-04-12: All T1 switched to cerebras/qwen-3-235b (235B params)
    as primary provider. HF Router is depleted (402), Claude CLI
    subprocess too slow (90s timeout). Cerebras Qwen-3-235B is the
    best available free model — 235B params, ultra-fast inference.
    Fallback chain still tries HF and google if cerebras is down.
    """
    base = [
        TradingAgent(
            id="t1_qwen72b", name="Qwen-72B Strategist", tier=AgentTier.PREMIUM,
            provider="cerebras", model="qwen-3-235b-a22b-instruct-2507",
            strategy="value_hunter_half_kelly",
            focus_groups=["moneyline", "spread", "totals", "player_props", "exotic"],
            personality="analytical", min_edge=0.04, risk_tolerance=0.4,
            kelly_fraction=0.5,
            description="Qwen 235B via Cerebras. Deep reasoning, value hunting."
        ),
        TradingAgent(
            id="t1_llama70b", name="Llama-70B Analyst", tier=AgentTier.PREMIUM,
            provider="cerebras", model="qwen-3-235b-a22b-instruct-2507",
            strategy="proportional_edge",
            focus_groups=["moneyline", "spread", "totals", "player_props", "exotic"],
            personality="analytical", min_edge=0.03, risk_tolerance=0.6,
            kelly_fraction=0.5,
            description="Qwen 235B via Cerebras. Proportional edge sizing."
        ),
        TradingAgent(
            id="t1_gemma27b", name="Gemma-27B Contrarian", tier=AgentTier.PREMIUM,
            provider="cerebras", model="qwen-3-235b-a22b-instruct-2507",
            strategy="underdog_specialist",
            focus_groups=["moneyline", "spread", "exotic", "margin"],
            personality="contrarian", min_edge=0.03, risk_tolerance=0.7,
            kelly_fraction=0.5,
            description="Qwen 235B via Cerebras. Contrarian underdog specialist."
        ),
        TradingAgent(
            id="t1_mistral24b", name="Mistral-24B Analyst", tier=AgentTier.PREMIUM,
            provider="cerebras", model="qwen-3-235b-a22b-instruct-2507",
            strategy="confidence_scaled",
            focus_groups=["moneyline", "spread", "totals", "player_props"],
            personality="analytical", min_edge=0.03, risk_tolerance=0.5,
            kelly_fraction=0.5,
            description="Qwen 235B via Cerebras. Fast analytical coverage."
        ),
    ]

    # --- 5 Named Premium Traders (visible T1_premium) ---
    # 2026-04-12: Switched from dead HF Router to cerebras/qwen-3-235b
    named_premium = [
        TradingAgent(
            id="t1_gemma", name="Gemma", tier=AgentTier.PREMIUM,
            provider="cerebras", model="qwen-3-235b-a22b-instruct-2507",
            strategy="value_hunter",
            focus_groups=["moneyline", "spread", "totals", "player_props", "exotic"],
            personality="analytical_ensemble", min_edge=0.04, risk_tolerance=0.5,
            kelly_fraction=0.5, bankroll=100.0, peak_bankroll=100.0,
            description="Qwen 235B via Cerebras. Analytical ensemble, value hunting specialist."
        ),
        TradingAgent(
            id="t1_qwen", name="Qwen", tier=AgentTier.PREMIUM,
            provider="cerebras", model="qwen-3-235b-a22b-instruct-2507",
            strategy="edge_seeker",
            focus_groups=["moneyline", "spread", "totals", "player_props", "exotic"],
            personality="deep_thinker", min_edge=0.05, risk_tolerance=0.5,
            kelly_fraction=0.6, bankroll=100.0, peak_bankroll=100.0,
            description="Qwen 235B via Cerebras. Deep thinker, edge seeker with high conviction."
        ),
        TradingAgent(
            id="t1_deepseek", name="DeepSeek", tier=AgentTier.PREMIUM,
            provider="cerebras", model="qwen-3-235b-a22b-instruct-2507",
            strategy="contrarian",
            focus_groups=["moneyline", "spread", "totals", "exotic", "margin"],
            personality="contrarian_value", min_edge=0.03, risk_tolerance=0.7,
            kelly_fraction=0.4, bankroll=100.0, peak_bankroll=100.0,
            description="Qwen 235B via Cerebras. Contrarian value player, fades public sentiment."
        ),
        TradingAgent(
            id="t1_mistral", name="Mistral", tier=AgentTier.PREMIUM,
            provider="cerebras", model="qwen-3-235b-a22b-instruct-2507",
            strategy="kelly_quarter",
            focus_groups=["moneyline", "spread", "totals", "player_props"],
            personality="balanced_optimizer", min_edge=0.03, risk_tolerance=0.5,
            kelly_fraction=0.25, bankroll=100.0, peak_bankroll=100.0,
            description="Qwen 235B via Cerebras. Balanced optimizer, conservative Kelly sizing."
        ),
        TradingAgent(
            id="t1_llama", name="Llama", tier=AgentTier.PREMIUM,
            provider="cerebras", model="qwen-3-235b-a22b-instruct-2507",
            strategy="momentum",
            focus_groups=["moneyline", "spread", "totals", "player_props", "exotic"],
            personality="momentum_tracker", min_edge=0.02, risk_tolerance=0.6,
            kelly_fraction=0.35, bankroll=100.0, peak_bankroll=100.0,
            description="Qwen 235B via Cerebras. Momentum tracker, follows streaks and trends."
        ),
    ]

    # --- Premium deep thinkers (5) ---
    # 2026-04-12: Formerly anthropic_cli (subprocess `claude`), which
    # caused 90s timeout + 0/14 T1 predictions in iter 85. Switched to
    # cerebras/qwen-3-235b for immediate results. Re-enable CLI when
    # Anthropic HTTP API key (not CLI subprocess) is available.
    deep_agents = [
        TradingAgent(
            id="t1_claude_code_opus", name="Deep Thinker Alpha", tier=AgentTier.PREMIUM,
            provider="cerebras", model="qwen-3-235b-a22b-instruct-2507",
            strategy="value_hunter_half_kelly",
            focus_groups=["moneyline", "spread", "totals", "player_props", "exotic"],
            personality="conservative", min_edge=0.04, risk_tolerance=0.4,
            kelly_fraction=0.5, bankroll=100.0, peak_bankroll=100.0,
            description="Qwen 235B via Cerebras. Deepest reasoning, value hunting."
        ),
        TradingAgent(
            id="t1_claude_code_sonnet", name="Deep Thinker Beta", tier=AgentTier.PREMIUM,
            provider="cerebras", model="qwen-3-235b-a22b-instruct-2507",
            strategy="half_kelly",
            focus_groups=["moneyline", "spread", "totals", "player_props", "exotic"],
            personality="analytical", min_edge=0.03, risk_tolerance=0.5,
            kelly_fraction=0.5, bankroll=100.0, peak_bankroll=100.0,
            description="Qwen 235B via Cerebras. Balanced analytical coverage."
        ),
        TradingAgent(
            id="t1_claude_code_haiku", name="Deep Thinker Gamma", tier=AgentTier.PREMIUM,
            provider="cerebras", model="qwen-3-235b-a22b-instruct-2507",
            strategy="proportional_edge",
            focus_groups=["moneyline", "spread", "totals"],
            personality="analytical", min_edge=0.03, risk_tolerance=0.5,
            kelly_fraction=0.5, bankroll=100.0, peak_bankroll=100.0,
            description="Qwen 235B via Cerebras. Fast, focused analysis."
        ),
        TradingAgent(
            id="t2_claude_code_research", name="Deep Thinker Research", tier=AgentTier.PREMIUM,
            provider="cerebras", model="qwen-3-235b-a22b-instruct-2507",
            strategy="value_hunter_half_kelly",
            focus_groups=["player_props", "exotic", "margin"],
            personality="analytical", min_edge=0.04, risk_tolerance=0.4,
            kelly_fraction=0.5, bankroll=100.0, peak_bankroll=100.0,
            description="Qwen 235B via Cerebras. Research-informed prop bets."
        ),
        TradingAgent(
            id="t2_claude_code_quant", name="Deep Thinker Quant", tier=AgentTier.PREMIUM,
            provider="cerebras", model="qwen-3-235b-a22b-instruct-2507",
            strategy="proportional_edge",
            focus_groups=["moneyline", "spread", "totals"],
            personality="analytical", min_edge=0.03, risk_tolerance=0.5,
            kelly_fraction=0.5, bankroll=100.0, peak_bankroll=100.0,
            description="Qwen 235B via Cerebras. Quantitative, ML-guided."
        ),
    ]

    return base + named_premium + deep_agents


# ============================================================================
# TIER 2: FREE POWER TRADERS (20 agents)
# ============================================================================
def _build_tier2() -> List[TradingAgent]:
    """20 free power traders using best free models, each with a focused angle."""
    agents = []

    # --- 5x HuggingFace diverse (replaced dead Groq/OpenRouter) ---
    hf_power_strategies = [
        ("value_hunter", "HF Value Hunter", "moneyline", 0.04, "conservative", "Qwen/Qwen2.5-72B-Instruct"),
        ("half_kelly", "HF Momentum", "spread", 0.03, "aggressive", "meta-llama/Llama-3.3-70B-Instruct"),
        ("proportional_edge", "HF Totals Master", "totals", 0.03, "analytical", "mistralai/Mistral-Small-24B-Instruct-2501"),
        ("confidence_scaled", "HF Props Analyst", "player_props", 0.03, "analytical", "google/gemma-3-27b-it"),
        ("quarter_kelly", "HF Exotic Eye", "exotic", 0.05, "contrarian", "Qwen/Qwen3-8B"),
    ]
    for i, (strat, name, group, min_e, pers, model) in enumerate(hf_power_strategies):
        agents.append(TradingAgent(
            id=f"t2_hf_power_{i}", name=name, tier=AgentTier.FREE_POWER,
            provider="huggingface", model=model,
            strategy=strat, focus_groups=[group, "moneyline"],
            personality=pers, min_edge=min_e, risk_tolerance=0.5,
            kelly_fraction=0.5,
            description=f"HuggingFace power trader, focus: {group}"
        ))

    # --- 5x HuggingFace + Cohere (fast bulk analysis, diverse strategies) ---
    hf_cohere_strategies = [
        ("flat_2pct", "HF Flat Diversifier", ["moneyline", "spread"], "huggingface", "Qwen/Qwen2.5-72B-Instruct"),
        ("half_kelly", "HF Sharp Shooter", ["spread", "totals"], "huggingface", "mistralai/Mistral-Small-24B-Instruct-2501"),
        ("value_hunter", "HF Value Seeker", ["moneyline", "margin"], "huggingface", "Qwen/Qwen2.5-72B-Instruct"),
        ("eighth_kelly", "HF Safety Net", ["totals", "moneyline"], "huggingface", "meta-llama/Llama-3.3-70B-Instruct"),
        ("proportional_edge", "HF Edge Scaler", ["spread", "player_props"], "huggingface", "Qwen/Qwen2.5-72B-Instruct"),
    ]
    for i, (strat, name, groups, provider, model) in enumerate(hf_cohere_strategies):
        agents.append(TradingAgent(
            id=f"t2_hf_cohere_{i}", name=name, tier=AgentTier.FREE_POWER,
            provider=provider, model=model,
            strategy=strat, focus_groups=groups,
            personality="analytical", min_edge=0.02, risk_tolerance=0.5,
            kelly_fraction=0.25,
            description=f"{provider} fast trader #{i}"
        ))

    # --- 3x OpenRouter Qwen (different angles) ---
    or_qwen_configs = [
        ("half_kelly", "Qwen ML Specialist", ["moneyline"], "aggressive"),
        ("value_hunter", "Qwen Spread Master", ["spread", "totals"], "analytical"),
        ("confidence_scaled", "Qwen Full Scan", ["moneyline", "spread", "totals"], "analytical"),
    ]
    for i, (strat, name, groups, pers) in enumerate(or_qwen_configs):
        agents.append(TradingAgent(
            id=f"t2_or_qwen_{i}", name=name, tier=AgentTier.FREE_POWER,
            provider="huggingface", model="Qwen/Qwen2.5-72B-Instruct",
            strategy=strat, focus_groups=groups,
            personality=pers, min_edge=0.03, risk_tolerance=0.5,
            kelly_fraction=0.5,
            description=f"OpenRouter Qwen3 free model #{i}"
        ))

    # --- 2x OpenRouter Gemma-3-27b ---
    for i, (strat, name) in enumerate([
        ("proportional_edge", "Gemma Game Reader"),
        ("half_kelly", "Gemma Trend Follower"),
    ]):
        agents.append(TradingAgent(
            id=f"t2_or_gemma_{i}", name=name, tier=AgentTier.FREE_POWER,
            provider="huggingface", model="google/gemma-3-27b-it",
            strategy=strat, focus_groups=["moneyline", "spread", "totals"],
            personality="analytical", min_edge=0.03,
            description=f"OpenRouter Gemma-3-27b free #{i}"
        ))

    # --- 2x OpenRouter Llama-4-Maverick ---
    for i, (strat, name) in enumerate([
        ("underdog_specialist", "Maverick Dog Hunter"),
        ("value_hunter", "Maverick Value Play"),
    ]):
        agents.append(TradingAgent(
            id=f"t2_or_maverick_{i}", name=name, tier=AgentTier.FREE_POWER,
            provider="huggingface", model="meta-llama/Llama-3.3-70B-Instruct",
            strategy=strat, focus_groups=["moneyline", "margin", "exotic"],
            personality="contrarian", min_edge=0.03,
            description=f"OpenRouter Llama-4-Maverick free #{i}"
        ))

    # --- 2x Cohere Command-R+ ---
    for i, (strat, name) in enumerate([
        ("half_kelly", "Cohere Analyst"),
        ("confidence_scaled", "Cohere Consensus"),
    ]):
        agents.append(TradingAgent(
            id=f"t2_cohere_{i}", name=name, tier=AgentTier.FREE_POWER,
            provider="huggingface", model="Qwen/Qwen2.5-72B-Instruct",
            strategy=strat, focus_groups=["moneyline", "spread", "totals"],
            personality="analytical", min_edge=0.03,
            description=f"Cohere Command-R+ free #{i}"
        ))

    # --- 1x Cerebras Qwen3-235B ---
    agents.append(TradingAgent(
        id="t2_cerebras_0", name="Cerebras Thunder", tier=AgentTier.FREE_POWER,
        provider="huggingface", model="Qwen/Qwen2.5-72B-Instruct",
        strategy="proportional_edge",
        focus_groups=["moneyline", "spread", "totals", "exotic"],
        personality="analytical", min_edge=0.03,
        description="Cerebras ultra-fast inference, full game analysis"
    ))

    # --- 5x Additional HF models (replaced dead Google API) ---
    hf_extra = [
        TradingAgent(
            id="t2_hf_qwen72b_pro", name="Qwen-72B Pro Analyst", tier=AgentTier.FREE_POWER,
            provider="huggingface", model="Qwen/Qwen2.5-72B-Instruct",
            strategy="confidence_scaled",
            focus_groups=["moneyline", "spread", "totals", "player_props", "exotic"],
            personality="analytical", min_edge=0.03, risk_tolerance=0.5,
            kelly_fraction=0.5, bankroll=100.0, peak_bankroll=100.0,
            description="Qwen 72B full coverage. Deep analysis."
        ),
        TradingAgent(
            id="t2_hf_llama70b", name="Llama-70B Fast", tier=AgentTier.FREE_POWER,
            provider="huggingface", model="meta-llama/Llama-3.3-70B-Instruct",
            strategy="half_kelly",
            focus_groups=["moneyline", "spread", "totals"],
            personality="analytical", min_edge=0.03, risk_tolerance=0.5,
            kelly_fraction=0.5, bankroll=100.0, peak_bankroll=100.0,
            description="Llama 70B balanced speed+quality."
        ),
        TradingAgent(
            id="t2_hf_nvidia_nemo", name="NVIDIA Nemotron", tier=AgentTier.FREE_POWER,
            provider="huggingface", model="nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
            strategy="flat_2pct",
            focus_groups=["moneyline", "spread"],
            personality="analytical", min_edge=0.02, risk_tolerance=0.5,
            kelly_fraction=0.25, bankroll=100.0, peak_bankroll=100.0,
            description="NVIDIA Nemotron 70B. Bulk fast screening."
        ),
        TradingAgent(
            id="t2_hf_qwen3_8b", name="Qwen3-8B Thinker", tier=AgentTier.FREE_POWER,
            provider="huggingface", model="Qwen/Qwen3-8B",
            strategy="value_hunter",
            focus_groups=["moneyline", "spread", "totals", "exotic"],
            personality="analytical", min_edge=0.04, risk_tolerance=0.4,
            kelly_fraction=0.5, bankroll=100.0, peak_bankroll=100.0,
            description="Qwen3 8B with extended reasoning. High edge focus."
        ),
        TradingAgent(
            id="t2_hf_gemma_spread", name="Gemma Spread Specialist", tier=AgentTier.FREE_POWER,
            provider="huggingface", model="google/gemma-3-27b-it",
            strategy="half_kelly",
            focus_groups=["spread", "margin"],
            personality="analytical", min_edge=0.03, risk_tolerance=0.5,
            kelly_fraction=0.5, bankroll=100.0, peak_bankroll=100.0,
            description="Gemma 3 27B spread/margin specialist."
        ),
        # GEMMA 4 PLACEHOLDER — using Gemma 3 until Gemma 4 becomes free
        # UPGRADE PATH (2026-04-05):
        #   When google/gemma-4-31B-it becomes free on OpenRouter/HF:
        #     Change model to "google/gemma-4-31B-it"
        #   When laptop Ollama comes online:
        #     Add provider="ollama", model="gemma4:e4b" agents
        TradingAgent(
            id="t2_gemma4_value", name="Gemma-4 Value Seeker", tier=AgentTier.FREE_POWER,
            provider="huggingface", model="google/gemma-3-27b-it",
            strategy="value_hunter",
            focus_groups=["moneyline", "spread", "totals"],
            personality="analytical", min_edge=0.03, risk_tolerance=0.4,
            kelly_fraction=0.25, bankroll=100.0, peak_bankroll=100.0,
            description="Gemma 4 placeholder (using Gemma-3-27B). Value hunting specialist."
        ),
        TradingAgent(
            id="t2_gemma4_contrarian", name="Gemma-4 Contrarian", tier=AgentTier.FREE_POWER,
            provider="huggingface", model="google/gemma-3-27b-it",
            strategy="contrarian",
            focus_groups=["moneyline", "totals"],
            personality="contrarian", min_edge=0.04, risk_tolerance=0.6,
            kelly_fraction=0.15, bankroll=100.0, peak_bankroll=100.0,
            description="Gemma 4 placeholder (using Gemma-3-27B). Contrarian edge finder."
        ),
    ]
    agents.extend(hf_extra)

    return agents


# ============================================================================
# TIER 3: SPECIALIST SWARM (176+ agents)
# ============================================================================
def _build_tier3() -> List[TradingAgent]:
    """
    One specialist agent per bet category side.
    Uses cheapest/fastest APIs: Groq llama-3.1-8b (72,000 RPD across 5 keys).
    """
    agents = []
    # Distribute across working free providers (2026-04-05: HF primary, others dead)
    cheap_configs = [
        ("huggingface", "Qwen/Qwen3-8B"),
        ("huggingface", "Qwen/Qwen2.5-72B-Instruct"),
        ("huggingface", "google/gemma-3-27b-it"),
        ("huggingface", "meta-llama/Llama-3.3-70B-Instruct"),
        ("huggingface", "mistralai/Mistral-Small-24B-Instruct-2501"),
        ("huggingface", "nvidia/Llama-3.1-Nemotron-70B-Instruct-HF"),
        ("huggingface", "Qwen/Qwen2.5-Coder-32B-Instruct"),
        ("huggingface", "microsoft/Phi-3.5-mini-instruct"),
    ]

    strategies_rotation = [
        "half_kelly", "quarter_kelly", "value_hunter",
        "proportional_edge", "confidence_scaled", "flat_2pct",
    ]

    agent_idx = 0
    for cat in ALL_CATEGORIES:
        for side in range(cat.sides):
            provider, model = cheap_configs[agent_idx % len(cheap_configs)]
            strategy = strategies_rotation[agent_idx % len(strategies_rotation)]

            agent_id = f"t3_{cat.id}_s{side}"
            name = f"Spec:{cat.name}:S{side}"

            agents.append(TradingAgent(
                id=agent_id,
                name=name[:40],
                tier=AgentTier.SPECIALIST,
                provider=provider,
                model=model,
                strategy=strategy,
                focus_category=cat.id,
                focus_side=side,
                focus_groups=[cat.group],
                personality="analytical",
                min_edge=0.02,
                risk_tolerance=0.4,
                kelly_fraction=0.25,
                bankroll=5_000.0,       # Smaller bankroll for specialists
                peak_bankroll=5_000.0,
                description=f"Specialist: {cat.name} side {side}"
            ))
            agent_idx += 1

    return agents


# ============================================================================
# TIER 4: META-TRADERS (3 agents)
# ============================================================================
def _build_tier4() -> List[TradingAgent]:
    """
    3 meta-traders that aggregate and synthesize:
    - Paperclip: capital allocation based on performance
    - Hermes: information routing, peer review consensus
    - Oracle: final synthesis (Karpathy Council Chairman)
    """
    return [
        TradingAgent(
            id="t4_paperclip", name="Paperclip Allocator", tier=AgentTier.META,
            provider="huggingface", model="Qwen/Qwen2.5-72B-Instruct",
            strategy="meta_allocation",
            focus_groups=["all"],
            personality="analytical", min_edge=0.0,
            bankroll=100.0, peak_bankroll=100.0,
            description=(
                "Meta-allocator: distributes capital across top performers. "
                "Reads all agent results, adjusts weights, kills underperformers."
            )
        ),
        TradingAgent(
            id="t4_hermes", name="Hermes Router", tier=AgentTier.META,
            provider="huggingface", model="google/gemma-3-27b-it",
            strategy="meta_consensus",
            focus_groups=["all"],
            personality="analytical", min_edge=0.0,
            bankroll=0.0,  # Hermes doesn't bet, it routes info
            description=(
                "Karpathy Council Stage 2: anonymized peer review. "
                "Routes predictions, manages consensus, flags disagreements."
            )
        ),
        TradingAgent(
            id="t4_oracle", name="Oracle Chairman", tier=AgentTier.META,
            provider="huggingface", model="nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
            strategy="meta_synthesis",
            focus_groups=["all"],
            personality="analytical", min_edge=0.03,
            bankroll=50_000.0, peak_bankroll=50_000.0,
            kelly_fraction=0.5,
            description=(
                "Karpathy Council Stage 3: Chairman synthesis. "
                "Weighted ensemble of all agent predictions. Final word."
            )
        ),
    ]


# ============================================================================
# FULL REGISTRY
# ============================================================================
class AgentRegistry:
    """Central registry for all 200+ trading agents."""

    def __init__(self):
        self.agents: Dict[str, TradingAgent] = {}
        self._build_all()

    def _build_all(self):
        """Build and register all agents across all tiers."""
        all_agents = (
            _build_tier1() +
            _build_tier2() +
            _build_tier3() +
            _build_tier4()
        )
        for agent in all_agents:
            self.agents[agent.id] = agent
        self._diversify_providers()

    def _diversify_providers(self):
        """Remap generic 'huggingface' to model-specific aliases.

        The api_pool.py has separate rate-limit buckets for google-gemma,
        qwen, deepseek, mistral, meta-llama (each 2000 RPD, 4 keys).
        Routing agents to model-specific aliases spreads the load across
        5× the capacity instead of bottlenecking on the single 'huggingface'
        bucket. Iter 86 had 95% API errors from this bottleneck.
        """
        MODEL_TO_PROVIDER = {
            "google/gemma-3-27b-it": "google-gemma",
            "Qwen/Qwen2.5-72B-Instruct": "qwen",
            "Qwen/Qwen2.5-Coder-32B-Instruct": "qwen",
            "Qwen/Qwen3-8B": "qwen",
            "meta-llama/Llama-3.3-70B-Instruct": "meta-llama",
            "mistralai/Mistral-Small-24B-Instruct-2501": "mistral",
            "microsoft/Phi-3.5-mini-instruct": "mistral",  # share mistral bucket
            "nvidia/Llama-3.1-Nemotron-70B-Instruct-HF": "meta-llama",
        }
        remapped = 0
        for agent in self.agents.values():
            if agent.provider == "huggingface" and agent.model in MODEL_TO_PROVIDER:
                agent.provider = MODEL_TO_PROVIDER[agent.model]
                remapped += 1

    @property
    def tier1(self) -> List[TradingAgent]:
        return [a for a in self.agents.values() if a.tier == AgentTier.PREMIUM]

    @property
    def tier2(self) -> List[TradingAgent]:
        return [a for a in self.agents.values() if a.tier == AgentTier.FREE_POWER]

    @property
    def tier3(self) -> List[TradingAgent]:
        return [a for a in self.agents.values() if a.tier == AgentTier.SPECIALIST]

    @property
    def tier4(self) -> List[TradingAgent]:
        return [a for a in self.agents.values() if a.tier == AgentTier.META]

    @property
    def active_agents(self) -> List[TradingAgent]:
        return [a for a in self.agents.values() if a.active]

    def get(self, agent_id: str) -> Optional[TradingAgent]:
        return self.agents.get(agent_id)

    def get_by_provider(self, provider: str) -> List[TradingAgent]:
        return [a for a in self.agents.values() if a.provider == provider and a.active]

    def get_by_category(self, category_id: str) -> List[TradingAgent]:
        """Get all specialist agents for a specific bet category."""
        return [a for a in self.agents.values()
                if a.focus_category == category_id and a.active]

    def get_top_performers(self, n: int = 20) -> List[TradingAgent]:
        """Get top N agents by ROI, with minimum 10 bets."""
        qualified = [a for a in self.agents.values()
                     if a.total_bets >= 10 and a.active]
        qualified.sort(key=lambda a: a.roi, reverse=True)
        return qualified[:n]

    def deactivate_underperformers(self, min_bets: int = 20, max_loss_pct: float = -30.0):
        """Deactivate agents that have lost too much."""
        deactivated = []
        for agent in self.agents.values():
            if agent.tier == AgentTier.META:
                continue  # Never deactivate meta-traders
            if agent.total_bets >= min_bets and agent.roi < max_loss_pct:
                agent.active = False
                deactivated.append(agent.id)
        return deactivated

    def update_weights_from_performance(self):
        """Update agent weights based on rolling accuracy. Used by Paperclip meta-trader."""
        for agent in self.agents.values():
            if agent.total_bets < 5:
                agent.weight = 1.0
                continue
            # Weight = rolling accuracy ^ 2 (rewards consistent winners)
            acc = agent.rolling_accuracy
            agent.weight = max(0.1, acc ** 2 * 4)  # Scale so 50% acc = 1.0 weight

    def save_state(self, path: str):
        """Save all agent states to JSON."""
        data = {
            "agent_count": len(self.agents),
            "active_count": len(self.active_agents),
            "tiers": {
                "premium": len(self.tier1),
                "free_power": len(self.tier2),
                "specialist": len(self.tier3),
                "meta": len(self.tier4),
            },
            "agents": {aid: agent.to_dict() for aid, agent in self.agents.items()},
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_state(self, path: str):
        """Load agent states from JSON (bankroll, bets, weights)."""
        try:
            with open(path) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return

        saved_agents = data.get("agents", {})
        for aid, saved in saved_agents.items():
            agent = self.agents.get(aid)
            if not agent:
                continue
            agent.bankroll = saved.get("bankroll", agent.bankroll)
            agent.total_bets = saved.get("total_bets", agent.total_bets)
            agent.total_wins = saved.get("total_wins", agent.total_wins)
            agent.total_pnl = saved.get("total_pnl", agent.total_pnl)
            agent.weight = saved.get("weight", agent.weight)
            agent.active = saved.get("active", agent.active)

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            "Agent Registry Summary",
            "=" * 60,
            f"Total agents: {len(self.agents)}",
            f"Active agents: {len(self.active_agents)}",
            "",
            f"Tier 1 (Premium):    {len(self.tier1):>4} agents",
            f"Tier 2 (Free Power): {len(self.tier2):>4} agents",
            f"Tier 3 (Specialist): {len(self.tier3):>4} agents",
            f"Tier 4 (Meta):       {len(self.tier4):>4} agents",
            "",
            "Provider Distribution:",
        ]
        from collections import Counter
        provider_counts = Counter(a.provider for a in self.agents.values())
        for provider, count in provider_counts.most_common():
            lines.append(f"  {provider:<15} {count:>4} agents")

        # API calls estimate for 5 games
        t1_calls = len(self.tier1) * 5  # 1 call per game
        t2_calls = len(self.tier2) * 5
        # Tier 3: only call if category is relevant to the game
        # Estimate ~40% of specialists fire per game
        t3_calls = int(len(self.tier3) * 5 * 0.4)
        t4_calls = len(self.tier4) * 5 * 2  # peer review + synthesis
        total_calls = t1_calls + t2_calls + t3_calls + t4_calls

        lines.extend([
            "",
            f"Estimated daily API calls (5 games):",
            f"  Tier 1: {t1_calls:>5} calls",
            f"  Tier 2: {t2_calls:>5} calls",
            f"  Tier 3: {t3_calls:>5} calls (est. 40% fire rate)",
            f"  Tier 4: {t4_calls:>5} calls",
            f"  TOTAL:  {total_calls:>5} calls/day",
        ])

        return "\n".join(lines)


# ============================================================================
# CLI
# ============================================================================
if __name__ == "__main__":
    registry = AgentRegistry()
    print(registry.summary())
    print()

    # Show some agents from each tier
    for tier_name, agents in [
        ("TIER 1 — Premium", registry.tier1),
        ("TIER 2 — Free Power", registry.tier2[:5]),
        ("TIER 3 — Specialist (first 5)", registry.tier3[:5]),
        ("TIER 4 — Meta", registry.tier4),
    ]:
        print(f"\n{tier_name}:")
        for a in agents:
            print(f"  {a.id:<30} {a.provider:<12} {a.model:<35} {a.strategy}")
