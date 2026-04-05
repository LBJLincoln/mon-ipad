#!/usr/bin/env python3
"""
AGENT REGISTRY — 200+ Trading Floor Agents in 4 Tiers
======================================================
Tier 1: Premium Traders (4) — paid APIs, full game analysis
Tier 2: Free Power Traders (20) — best free models, focused analysis
Tier 3: Specialist Swarm (176+) — one agent per bet category side
Tier 4: Meta-Traders (3) — Paperclip, Hermes, Oracle

Total: 203+ agents, ~1,000 API calls/day for 5 games
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
    bankroll: float = 10_000.0
    peak_bankroll: float = 10_000.0
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
        return (self.bankroll - 10_000.0) / 10_000.0 * 100

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
# TIER 1: PREMIUM TRADERS (9 agents — 4 original + 5 Claude Code CLI)
# ============================================================================
def _build_tier1() -> List[TradingAgent]:
    """9 premium traders: existing paid-API agents + 5 new Claude Code CLI agents."""
    base = [
        TradingAgent(
            id="t1_claude", name="Claude Prime", tier=AgentTier.PREMIUM,
            provider="openai",  # GPT-4o proxy (backward compat)
            model="gpt-4o",
            strategy="value_hunter_half_kelly",
            focus_groups=["moneyline", "spread", "totals", "player_props", "exotic"],
            personality="conservative", min_edge=0.04, risk_tolerance=0.4,
            kelly_fraction=0.5,
            description="Premium Claude via GPT-4o proxy. Conservative value hunter."
        ),
        TradingAgent(
            id="t1_gpt4o", name="GPT-4o Strategist", tier=AgentTier.PREMIUM,
            provider="openai", model="gpt-4o",
            strategy="proportional_edge",
            focus_groups=["moneyline", "spread", "totals", "player_props", "exotic"],
            personality="analytical", min_edge=0.03, risk_tolerance=0.6,
            kelly_fraction=0.5,
            description="GPT-4o with proportional edge sizing. Analytical precision."
        ),
        TradingAgent(
            id="t1_grok", name="Grok Contrarian", tier=AgentTier.PREMIUM,
            provider="xai", model="grok-3-mini",
            strategy="underdog_specialist",
            focus_groups=["moneyline", "spread", "exotic", "margin"],
            personality="contrarian", min_edge=0.03, risk_tolerance=0.7,
            kelly_fraction=0.5,
            description="Grok hunting underdog value. Contrarian streak finder."
        ),
        TradingAgent(
            id="t1_gemini", name="Gemini Analyst", tier=AgentTier.PREMIUM,
            provider="google", model="gemini-2.0-flash",
            strategy="confidence_scaled",
            focus_groups=["moneyline", "spread", "totals", "player_props"],
            personality="analytical", min_edge=0.03, risk_tolerance=0.5,
            kelly_fraction=0.5,
            description="Gemini Flash for rapid analytical coverage."
        ),
    ]

    # --- Claude Code CLI agents (5 new) ---
    # provider="anthropic_cli" routes to subprocess `claude` command
    cli_agents = [
        TradingAgent(
            id="t1_claude_code_opus", name="Claude Opus CLI", tier=AgentTier.PREMIUM,
            provider="anthropic_cli", model="claude-opus-4-6",
            strategy="value_hunter_half_kelly",
            focus_groups=["moneyline", "spread", "totals", "player_props", "exotic"],
            personality="conservative", min_edge=0.04, risk_tolerance=0.4,
            kelly_fraction=0.5, bankroll=10_000.0, peak_bankroll=10_000.0,
            description="Claude Opus 4.6 via CLI. Deepest reasoning, highest quality."
        ),
        TradingAgent(
            id="t1_claude_code_sonnet", name="Claude Sonnet CLI", tier=AgentTier.PREMIUM,
            provider="anthropic_cli", model="claude-sonnet-4-6",
            strategy="half_kelly",
            focus_groups=["moneyline", "spread", "totals", "player_props", "exotic"],
            personality="analytical", min_edge=0.03, risk_tolerance=0.5,
            kelly_fraction=0.5, bankroll=10_000.0, peak_bankroll=10_000.0,
            description="Claude Sonnet 4.6 via CLI. Balanced speed and quality."
        ),
        TradingAgent(
            id="t1_claude_code_haiku", name="Claude Haiku CLI", tier=AgentTier.PREMIUM,
            provider="anthropic_cli", model="claude-haiku-4-5-20251001",
            strategy="proportional_edge",
            focus_groups=["moneyline", "spread", "totals"],
            personality="analytical", min_edge=0.03, risk_tolerance=0.5,
            kelly_fraction=0.5, bankroll=10_000.0, peak_bankroll=10_000.0,
            description="Claude Haiku 4.5 via CLI. Fast, focused analysis."
        ),
        TradingAgent(
            id="t2_claude_code_research", name="Claude Research CLI", tier=AgentTier.PREMIUM,
            provider="anthropic_cli", model="claude-sonnet-4-6",
            strategy="value_hunter_half_kelly",
            focus_groups=["player_props", "exotic", "margin"],
            personality="analytical", min_edge=0.04, risk_tolerance=0.4,
            kelly_fraction=0.5, bankroll=10_000.0, peak_bankroll=10_000.0,
            description="Claude Sonnet via CLI. Specialist: research-informed bets."
        ),
        TradingAgent(
            id="t2_claude_code_quant", name="Claude Quant CLI", tier=AgentTier.PREMIUM,
            provider="anthropic_cli", model="claude-sonnet-4-6",
            strategy="proportional_edge",
            focus_groups=["moneyline", "spread", "totals"],
            personality="analytical", min_edge=0.03, risk_tolerance=0.5,
            kelly_fraction=0.5, bankroll=10_000.0, peak_bankroll=10_000.0,
            description="Claude Sonnet via CLI. Quantitative analysis, ML-guided."
        ),
    ]

    return base + cli_agents


# ============================================================================
# TIER 2: FREE POWER TRADERS (20 agents)
# ============================================================================
def _build_tier2() -> List[TradingAgent]:
    """20 free power traders using best free models, each with a focused angle."""
    agents = []

    # --- 5x Groq Llama-4-Scout (different strategies) ---
    groq_scout_strategies = [
        ("value_hunter", "Scout Value Hunter", "moneyline", 0.04, "conservative"),
        ("half_kelly", "Scout Momentum", "spread", 0.03, "aggressive"),
        ("proportional_edge", "Scout Totals Master", "totals", 0.03, "analytical"),
        ("confidence_scaled", "Scout Props Analyst", "player_props", 0.03, "analytical"),
        ("quarter_kelly", "Scout Exotic Eye", "exotic", 0.05, "contrarian"),
    ]
    for i, (strat, name, group, min_e, pers) in enumerate(groq_scout_strategies):
        agents.append(TradingAgent(
            id=f"t2_groq_scout_{i}", name=name, tier=AgentTier.FREE_POWER,
            provider="groq", model="llama-4-scout-17b-16e-instruct",
            strategy=strat, focus_groups=[group, "moneyline"],
            personality=pers, min_edge=min_e, risk_tolerance=0.5,
            kelly_fraction=0.5,
            description=f"Groq Llama-4-Scout key rotation, focus: {group}"
        ))

    # --- 5x Groq Llama-3.1-8b (fast bulk analysis, diverse strategies) ---
    groq_llama_strategies = [
        ("flat_2pct", "Llama Flat Diversifier", ["moneyline", "spread"]),
        ("half_kelly", "Llama Sharp Shooter", ["spread", "totals"]),
        ("value_hunter", "Llama Value Seeker", ["moneyline", "margin"]),
        ("eighth_kelly", "Llama Safety Net", ["totals", "moneyline"]),
        ("proportional_edge", "Llama Edge Scaler", ["spread", "player_props"]),
    ]
    for i, (strat, name, groups) in enumerate(groq_llama_strategies):
        agents.append(TradingAgent(
            id=f"t2_groq_llama_{i}", name=name, tier=AgentTier.FREE_POWER,
            provider="groq", model="llama-3.1-8b-instant",
            strategy=strat, focus_groups=groups,
            personality="analytical", min_edge=0.02, risk_tolerance=0.5,
            kelly_fraction=0.25,
            description=f"Groq Llama-3.1-8b fast trader #{i}"
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
            provider="openrouter", model="qwen/qwen3-30b-a3b:free",
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
            provider="openrouter", model="google/gemma-3-27b-it:free",
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
            provider="openrouter", model="meta-llama/llama-4-maverick:free",
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
            provider="cohere", model="command-r-plus",
            strategy=strat, focus_groups=["moneyline", "spread", "totals"],
            personality="analytical", min_edge=0.03,
            description=f"Cohere Command-R+ free #{i}"
        ))

    # --- 1x Cerebras Qwen3-235B ---
    agents.append(TradingAgent(
        id="t2_cerebras_0", name="Cerebras Thunder", tier=AgentTier.FREE_POWER,
        provider="cerebras", model="qwen-3-32b",
        strategy="proportional_edge",
        focus_groups=["moneyline", "spread", "totals", "exotic"],
        personality="analytical", min_edge=0.03,
        description="Cerebras ultra-fast inference, full game analysis"
    ))

    # --- 5x Gemini (additional coverage with Google API) ---
    gemini_agents = [
        TradingAgent(
            id="t1_gemini_pro", name="Gemini 2.5 Pro", tier=AgentTier.FREE_POWER,
            provider="google", model="gemini-2.5-pro",
            strategy="confidence_scaled",
            focus_groups=["moneyline", "spread", "totals", "player_props", "exotic"],
            personality="analytical", min_edge=0.03, risk_tolerance=0.5,
            kelly_fraction=0.5, bankroll=10_000.0, peak_bankroll=10_000.0,
            description="Gemini 2.5 Pro. Deepest Gemini model, premium tier."
        ),
        TradingAgent(
            id="t2_gemini_flash", name="Gemini 2.5 Flash", tier=AgentTier.FREE_POWER,
            provider="google", model="gemini-2.5-flash",
            strategy="half_kelly",
            focus_groups=["moneyline", "spread", "totals"],
            personality="analytical", min_edge=0.03, risk_tolerance=0.5,
            kelly_fraction=0.5, bankroll=10_000.0, peak_bankroll=10_000.0,
            description="Gemini 2.5 Flash. Fast, capable, free tier."
        ),
        TradingAgent(
            id="t2_gemini_flash_lite", name="Gemini 2.0 Flash Lite", tier=AgentTier.FREE_POWER,
            provider="google", model="gemini-2.0-flash-lite",
            strategy="flat_2pct",
            focus_groups=["moneyline", "spread"],
            personality="analytical", min_edge=0.02, risk_tolerance=0.5,
            kelly_fraction=0.25, bankroll=10_000.0, peak_bankroll=10_000.0,
            description="Gemini 2.0 Flash Lite. Bulk fast screening."
        ),
        TradingAgent(
            id="t2_gemini_thinking", name="Gemini Flash Thinking", tier=AgentTier.FREE_POWER,
            provider="google", model="gemini-2.5-flash-thinking",
            strategy="value_hunter",
            focus_groups=["moneyline", "spread", "totals", "exotic"],
            personality="analytical", min_edge=0.04, risk_tolerance=0.4,
            kelly_fraction=0.5, bankroll=10_000.0, peak_bankroll=10_000.0,
            description="Gemini 2.5 Flash Thinking. Extended reasoning, high edge."
        ),
        TradingAgent(
            id="t2_gemini_spread", name="Gemini Spread Specialist", tier=AgentTier.FREE_POWER,
            provider="google", model="gemini-2.5-flash",
            strategy="half_kelly",
            focus_groups=["spread", "margin"],
            personality="analytical", min_edge=0.03, risk_tolerance=0.5,
            kelly_fraction=0.5, bankroll=10_000.0, peak_bankroll=10_000.0,
            description="Gemini Flash spread/margin specialist."
        ),
    ]
    agents.extend(gemini_agents)

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
    # Distribute across Groq models for load balancing
    cheap_configs = [
        ("groq", "llama-3.1-8b-instant"),
        ("groq", "gemma2-9b-it"),
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
            provider="groq", model="llama-3.3-70b-versatile",
            strategy="meta_allocation",
            focus_groups=["all"],
            personality="analytical", min_edge=0.0,
            bankroll=100_000.0, peak_bankroll=100_000.0,
            description=(
                "Meta-allocator: distributes capital across top performers. "
                "Reads all agent results, adjusts weights, kills underperformers."
            )
        ),
        TradingAgent(
            id="t4_hermes", name="Hermes Router", tier=AgentTier.META,
            provider="groq", model="llama-3.3-70b-versatile",
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
            provider="google", model="gemini-2.0-flash",
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
