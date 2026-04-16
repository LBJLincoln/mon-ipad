"""
Nomos42 Political LLM Trading Floor — HuggingFace Spaces
=========================================================
10 AI agents (real LLM API calls) compete on ~1120 political events
over ~14 days (2026-03-12 to 2026-03-26).
Each agent receives daily political signals (insider trades, Fed rules,
executive orders) and allocates long/short on affected sector ETFs.
NO hash simulation. Every decision is a real LLM call.

Providers: Cerebras (2 models), Google Gemini, Mistral (5 models)
Runtime: ~1-2 hours for full dataset. Live visualization throughout.

Architecture follows:
  - TradingAgents (arXiv 2412.20138): structured agent reasoning
  - Prediction Arena (arXiv 2604.07355): 1-bet-per-agent validation
  - DMAD (Diverse Multi-Agent Debate): structurally different data views
"""

import gradio as gr
import json
import os
import time
import requests
import traceback
import io
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Centralised gateway router (vendored into Space; see scripts/arena/gateway_client.py)
from gateway_client import gateway_call as _gateway_call, GATEWAY_URL as _GATEWAY_URL

# ── STARTUP DIAGNOSTICS ─────────────────────────────────────────────────────
print("=" * 60)
print("NOMOS42 POLITICAL LLM TRADING FLOOR — STARTUP")
print("=" * 60)
for k in ["CEREBRAS_API_KEY", "GOOGLE_API_KEY", "GOOGLE_API_KEY_2",
          "OPENROUTER_KEY_ORCHESTRATOR", "OPENROUTER_KEY_PME", "OPENROUTER_KEY_BARTOLI",
          "MISTRAL_API_KEY"]:
    v = os.environ.get(k, "")
    if v:
        print(f"  {k}: {v[:6]}...{v[-3:]} (len={len(v)})")
    else:
        print(f"  {k}: NOT SET")
print("=" * 60)
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ── CONTROL STATE (stop/mutate/resume) ──────────────────────────────────────
_stop_event = threading.Event()
_experiment_running = False
_experiment_state = {}  # Persisted to disk
_agent_logs: Dict[str, List[dict]] = defaultdict(list)  # Per-agent decision log
_state_lock = threading.Lock()
_common_knowledge: Dict[str, str] = {}  # Axelrod CK[D]: day_date → formatted block for day D+1
_sacrificial_assignments: Dict[str, str] = {}  # Axelrod Mech B: tid → archetype for NEXT day
_used_archetypes: Dict[str, set] = defaultdict(set)  # Axelrod Mech B: tid → set of archetypes tried
_challenge_assignments: Dict[str, int] = {}  # Axelrod Mech B: mid-tier tid → leaderboard rank
STATE_PATH = Path("/tmp/ptf-state.json")   # Persists across restarts on HF Spaces
LOGS_PATH = Path("/tmp/ptf-agent-logs.json")
AXELROD_LOG_DIR = Path("/tmp/axelrod-log-political")  # Axelrod Mech C

# Axelrod Mech B — archetype pool tuned for political/macro alpha traders
AXELROD_ARCHETYPES = [
    "political_sentiment", "insider_tracking", "trump_volatility",
    "foreign_sovereign_flow", "regulatory_arb", "congress_trading_mirror",
    "macro_narrative", "crisis_contrarian", "election_cycle_timing",
    "fed_watcher", "geopolitical_risk", "congressional_calendar",
    "lobbying_flow", "pac_money_velocity", "treasury_curve_divergence",
    "commodities_war_premium", "dollar_strength_fade", "emerging_market_risk",
    "defense_budget_catalyst", "sanctions_arbitrage",
]

# Axelrod 1980 canon — political-alpha variant (same canon, context swapped).
AXELROD_CANON = (
    "=== AXELROD CANON (mandatory reading) ===\n"
    "You are a trader in an iterated multi-agent political-alpha society. Axelrod's 1980 "
    "tournament proved that the winning strategies share 4 properties: NICE (never defect "
    "first), RETALIATORY (punish defection immediately), FORGIVING (one-shot retaliation, "
    "then reset), CLEAR (legible so peers can reason about you).\n"
    "Canonical strategies you must know by name:\n"
    "  - TIT_FOR_TAT (Rapoport): cooperate first, then copy last move of peer.\n"
    "  - GRIM_TRIGGER: cooperate until one defection, then defect forever.\n"
    "  - PAVLOV / WIN-STAY-LOSE-SHIFT (Nowak-Sigmund 1993): keep last move if it paid, flip if it lost.\n"
    "  - GENEROUS_TFT: TFT with ~10% forgiveness to escape noise-driven defection spirals.\n"
    "  - FIRM_BUT_FAIR: cooperate unless suckered, then retaliate once and return to cooperation.\n"
    "DMAD (Du et al. 2023, Debate with Multi-Agent Diverse-reasoning): groupthink collapses "
    "ensemble accuracy by ~18%. Your reasoning chain MUST be structurally distinct from peers' "
    "chains reported in COMMON_KNOWLEDGE — if consensus is obvious, state the strongest counter-argument.\n"
    "Prediction Arena (arXiv 2604.07355, Mar 2026): 1 bet per agent per day with public "
    "resolution + reputation score beats unconstrained betting by 31% ROI.\n"
    "COOPERATION RULES (Mech D — binding this season):\n"
    "  1. You may propose a COALITION with another agent: both agents trade the SAME event_idx "
    "     on the SAME sector on day D. Honored coalitions get a 'pact_honored' reputation credit.\n"
    "  2. You may EXIT a coalition any day by simply not repeating it. No hidden defection.\n"
    "  3. Your reputation field (pact_honored / pact_broken counters) is visible to peers in "
    "     COMMON_KNOWLEDGE the next day. Pavlov-style opponents will track your reputation.\n"
    "  4. Coalitions do NOT change stake math — only reputation. Edge must still justify the trade.\n"
    "=== END AXELROD CANON ===\n"
)

# Axelrod Mech D — cooperation ledger (political)
_cooperation_pacts: Dict[str, dict] = {}
_reputation: Dict[str, Dict[str, int]] = defaultdict(lambda: {"pact_honored": 0, "pact_broken": 0})

# --- Axelrod-Python real-library engine (Mech D+, political parity) ----------
try:
    import axelrod as axl
    _AXELROD_OK = True
except Exception:
    axl = None
    _AXELROD_OK = False

AXELROD_STRATEGIES = {
    "qwen-quant":        "TitForTat",
    "qwen-arb":          "Grudger",
    "llama-contra":      "SuspiciousTitForTat",
    "gemini-anl":        "TitFor2Tats",
    "gemini-tact":       "TwoTitsForTat",
    "mistral-large":     "WinStayLoseShift",
    "mistral-medium":    "GenerousTitForTat",
    "mistral-small":     "Cooperator",
    "mistral-nemo":      "Defector",
    "mistral-ministral": "FirmButFair",
    "nemotron-120b":     "Adaptive",
    "gemma4-selfhost":   "Tullock",
    "qwen25-micro":      "Random",
    "llama32-micro":     "Cycler CCD",
    "gemma2-micro":      "HardGoByMajority",
}
_axelrod_agents: Dict[str, object] = {}

def _axelrod_make(tid: str):
    if not _AXELROD_OK:
        return None
    if tid in _axelrod_agents:
        return _axelrod_agents[tid]
    name = AXELROD_STRATEGIES.get(tid, "TitForTat")
    cls = getattr(axl, name.replace(" ", ""), None) or getattr(axl, name, None) or axl.TitForTat
    try:
        obj = cls()
        _axelrod_agents[tid] = obj
        return obj
    except Exception:
        return None

def _axelrod_advice(tid: str, peer_tid: str) -> Dict[str, str]:
    if not _AXELROD_OK:
        return {"move": "C", "strategy": "unavailable", "reason": "axelrod-python not installed"}
    self_agent = _axelrod_make(tid)
    peer_agent = _axelrod_make(peer_tid)
    if self_agent is None or peer_agent is None:
        return {"move": "C", "strategy": AXELROD_STRATEGIES.get(tid, "TitForTat"), "reason": "init failed"}
    try:
        self_agent.reset()
        peer_agent.reset()
        pair_keys = [k for k in _cooperation_pacts.keys()
                     if k.startswith(f"{tid}|{peer_tid}|") or k.startswith(f"{peer_tid}|{tid}|")]
        pair_keys.sort()
        for k in pair_keys[-50:]:
            move = axl.Action.C if _cooperation_pacts[k].get("honored", False) else axl.Action.D
            self_agent.history.append(move)
            peer_agent.history.append(move)
        next_move = self_agent.strategy(peer_agent)
        return {
            "move": "C" if next_move == axl.Action.C else "D",
            "strategy": AXELROD_STRATEGIES.get(tid, "TitForTat"),
            "reason": f"{len(pair_keys)} prior pacts with {peer_tid}",
        }
    except Exception as e:
        return {"move": "C", "strategy": AXELROD_STRATEGIES.get(tid, "TitForTat"),
                "reason": f"strategy error: {str(e)[:60]}"}

def _axelrod_advice_block(tid: str, active_peers: list) -> str:
    if not _AXELROD_OK or not active_peers:
        return ""
    peers = list(active_peers)[:3]
    lines = []
    for peer in peers:
        a = _axelrod_advice(tid, peer)
        lines.append(f"  - vs {peer}: strategy={a['strategy']} → suggests {a['move']} ({a['reason']})")
    if not lines:
        return ""
    return (
        "\n=== AXELROD MECH D — CANON STRATEGY ADVICE (axelrod-python library, ~240 strategies) ===\n"
        f"Your assigned canon strategy: {AXELROD_STRATEGIES.get(tid, 'TitForTat')}\n"
        "Today's advice against 3 peers (based on real pact history):\n"
        + "\n".join(lines) +
        "\nHonor the C (cooperate) suggestions as PACT proposals; decline D (defect) peers.\n"
        "=== END AXELROD ADVICE ===\n"
    )

GATEWAY_URL = os.environ.get("GATEWAY_URL", "").rstrip("/")

# DMAD (ICLR 2025, OpenReview t6QHYUOQL7) — structurally distinct reasoning per agent (political flavor).
REASONING_TEMPLATES = {
    "qwen-quant":        "REASONING TEMPLATE (DMAD): EXPECTED-UTILITY MAXIMIZATION. Compute E[V] = (p_event × sector_move) − cost. Trade iff E[V]/stake > 0.05.",
    "qwen-arb":          "REASONING TEMPLATE (DMAD): CROSS-SECTOR ARBITRAGE. Spot correlated ETFs diverging > 2σ from historical beta.",
    "llama-contra":      "REASONING TEMPLATE (DMAD): CONTRARIAN INVERSION. Start from consensus narrative, argue the OPPOSITE with 3 reasons.",
    "gemini-anl":        "REASONING TEMPLATE (DMAD): FIRST-PRINCIPLES DECOMPOSITION. List 3 decisive political drivers, weight each, multiply to get signal.",
    "gemini-tact":       "REASONING TEMPLATE (DMAD): TACTICAL TIMING. Focus on calendar risk (votes, summits). No imminent catalyst → PASS.",
    "mistral-large":     "REASONING TEMPLATE (DMAD): SCENARIO MAJORITY. Enumerate 5 macro scenarios, assign P, trade iff ≥3 align.",
    "mistral-medium":    "REASONING TEMPLATE (DMAD): DIVERSIFIED PORTFOLIO. Split across 2-3 uncorrelated sectors.",
    "mistral-small":     "REASONING TEMPLATE (DMAD): RISK-AVERSE STRESS. Assume worst-case tail; trade only if still +EV.",
    "mistral-nemo":      "REASONING TEMPLATE (DMAD): MOMENTUM CHASE. Bet hardest on sectors with 5-day momentum > 2σ.",
    "mistral-ministral": "REASONING TEMPLATE (DMAD): THEORETICAL MODEL. Mental factor model from 3 coefficients → compute expected sector return.",
    "nemotron-120b":     "REASONING TEMPLATE (DMAD): EXPLICIT 7-STEP CoT. context → hypothesis → evidence → counter → weight → conclusion → trade.",
    "gemma4-selfhost":   "REASONING TEMPLATE (DMAD): 4-RULE CHECKLIST. (1) edge > 0.05 (2) bankroll > $30 (3) not same sector as yesterday (4) political catalyst dated within 14d. Trade iff ALL pass.",
    "qwen25-micro":      "REASONING TEMPLATE (DMAD): PATTERN-MATCH. Find most similar historical political event in COMMON_KNOWLEDGE, mimic sector rotation.",
    "llama32-micro":     "REASONING TEMPLATE (DMAD): ANCHOR & ADJUST. Anchor at consensus polling / betting-market prob, adjust ±10% on strongest signal.",
    "gemma2-micro":      "REASONING TEMPLATE (DMAD): MINIMALIST. Pick the SINGLE highest-conviction trade of the day or PASS. Never > 1 trade.",
}

def get_stackelberg_leader(state: dict) -> Optional[str]:
    """Stackelberg (arXiv 2507.09407): yesterday's top-bankroll trader is today's leader."""
    active = [(tid, st.get("bankroll", 0)) for tid, st in state.items()
              if isinstance(st, dict) and tid in TRADERS and st.get("bankroll", 0) > 5.0]
    if not active:
        return None
    return max(active, key=lambda x: x[1])[0]

def build_stackelberg_role_block(tid: str, leader_tid: Optional[str]) -> str:
    if not leader_tid:
        return ""
    if tid == leader_tid:
        return ("\n=== STACKELBERG ROLE TODAY: LEADER ===\n"
                "You are today's leader (highest bankroll prior day). Commit trades FIRST with full "
                "public reasoning. Your decisions enter COMMON_KNOWLEDGE for followers.\n")
    return (f"\n=== STACKELBERG ROLE TODAY: FOLLOWER (leader = {leader_tid}) ===\n"
            "After leader's public commitments, you must either:\n"
            "  (a) AGREE — align with leader's logic where same sector applies, OR\n"
            "  (b) DEVIATE — state one explicit reason to best-respond differently.\n")

def _save_state_to_disk(state: dict):
    """Persist experiment state to disk (survives Space restarts)."""
    try:
        STATE_PATH.write_text(json.dumps(state, default=str))
    except Exception:
        pass

def _load_state_from_disk() -> Optional[dict]:
    """Load persisted state if available."""
    try:
        if STATE_PATH.exists():
            return json.loads(STATE_PATH.read_text())
    except Exception:
        pass
    return None

def _save_logs_to_disk():
    """Persist agent logs."""
    try:
        LOGS_PATH.write_text(json.dumps(dict(_agent_logs), default=str))
    except Exception:
        pass

def _load_logs_from_disk():
    """Load persisted logs."""
    global _agent_logs
    try:
        if LOGS_PATH.exists():
            data = json.loads(LOGS_PATH.read_text())
            _agent_logs = defaultdict(list, data)
    except Exception:
        pass

_load_logs_from_disk()

# ── SECTOR / TICKER METADATA ────────────────────────────────────────────────
SECTOR_ETF_MAP = {
    "energy": "XLE", "healthcare": "XLV", "finance": "XLF",
    "tech": "XLK", "defense": "XAR", "private_prisons": "GEO",
    "consumer_disc": "XLY", "consumer_staples": "XLP", "industrials": "XLI",
    "materials": "XLB", "utilities": "XLU", "real_estate": "XLRE",
    "communications": "XLC", "other": "SPY",
}
LEVERAGE = 5.0  # Effective sector-ETF leverage for 1-week holds (typical for 2x-3x ETFs)

# ── PROVIDER CONFIGS (v3 — day-bucket design, 3 real providers, 2026-04-14) ──
# Verified by live experiment audit + /api/probe on 2026-04-14:
#   Cerebras qwen-3-235b + llama3.1-8b: 100% success, 30 RPM
#   Google Gemini 3 Flash (key 2):      100% success, 14 RPM
#   Mistral (la Plateforme free tier):  large/medium/small/nemo/ministral all OK
# Dead: OpenRouter (6 models, quota), Gemini key 1, Groq keys (org restricted).
# With day-bucket design: 1 call/agent/day × 14 days × 10 agents = 140 calls
# — fits free tiers with 10x headroom.
PROVIDERS = {
    # Cerebras (shared key, 30 RPM)
    "cerebras:qwen-3-235b": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "qwen-3-235b-a22b-instruct-2507",
        "key_env": "CEREBRAS_API_KEY",
        "max_tokens": 1200,
        "rpm": 30,
    },
    "cerebras:llama3.1-8b": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "llama3.1-8b",
        "key_env": "CEREBRAS_API_KEY",
        "max_tokens": 1200,
        "rpm": 30,
    },
    # Google Gemini 3 Flash (key 2)
    "google:gemini-3-flash": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent",
        "model": "gemini-3-flash-preview",
        "key_env": "GOOGLE_API_KEY_2",
        "max_tokens": 1500,
        "rpm": 14,
    },
    # Mistral la Plateforme (free tier — added 2026-04-14)
    "mistral:large": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-large-latest",
        "key_env": "MISTRAL_API_KEY",
        "max_tokens": 1200,
        "rpm": 20,
    },
    "mistral:medium": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-medium-latest",
        "key_env": "MISTRAL_API_KEY",
        "max_tokens": 1200,
        "rpm": 20,
    },
    "mistral:small": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-small-latest",
        "key_env": "MISTRAL_API_KEY",
        "max_tokens": 1200,
        "rpm": 20,
    },
    "mistral:nemo": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "open-mistral-nemo",
        "key_env": "MISTRAL_API_KEY",
        "max_tokens": 1200,
        "rpm": 20,
    },
    "mistral:ministral-8b": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "ministral-8b-latest",
        "key_env": "MISTRAL_API_KEY",
        "max_tokens": 1200,
        "rpm": 20,
    },
    # NEW 2026-04-15 — parity with NBA TF (T11-T15)
    "openrouter:nemotron-120b": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "nvidia/nemotron-3-super-120b:free",
        "key_env": "OPENROUTER_API_KEY",
        "max_tokens": 1200,
        "rpm": 12,
    },
    "selfhost:cpu-gemma4": {
        "url": "https://nomos42-nomos-cpu-gemma4.hf.space/api/decide",
        "model": "phi-3.5-mini-instruct-q4_k_m",
        "key_env": "SELFHOST_NOOP",
        "max_tokens": 800,
        "rpm": 6,
    },
    # 2026-04-16 REFRESH — 3 self-host CPU Spaces upgraded to 2026 SOTA (URLs unchanged)
    "selfhost:qwen3-0.6b": {
        "url": "https://nomos42-qwen25-05b-cpu.hf.space/chat/completions",
        "model": "qwen3-0.6b-instruct",
        "key_env": "SELFHOST_NOOP",
        "max_tokens": 800,
        "rpm": 12,
    },
    "selfhost:dolphin3-llama-3.2-3b": {
        "url": "https://nomos42-llama32-1b-cpu.hf.space/chat/completions",
        "model": "dolphin3-llama3.2-3b",
        "key_env": "SELFHOST_NOOP",
        "max_tokens": 800,
        "rpm": 8,
    },
    "selfhost:gemma-4-e2b": {
        "url": "https://nomos42-gemma2-2b-cpu.hf.space/chat/completions",
        "model": "gemma-4-e2b-it",
        "key_env": "SELFHOST_NOOP",
        "max_tokens": 800,
        "rpm": 4,
    },
}

# ── AGENT DEFINITIONS (v3 — 10 personas across 3 providers, 2026-04-14) ──────
# Each agent gets a real distinct model where possible. Same model + different
# system prompt = DMAD-style distinct reasoning (Prediction Arena 2604.07355).
TRADERS = {
    # Cerebras Qwen 3 235B — heaviest reasoning model, 2 personas
    "qwen-quant":  {"name": "Qwen Quant 235B",   "provider": "cerebras:qwen-3-235b",  "personality": "quantitative", "risk_tolerance": 0.55},
    "qwen-arb":    {"name": "Qwen Arb 235B",     "provider": "cerebras:qwen-3-235b",  "personality": "arbitrage",    "risk_tolerance": 0.65},
    # Cerebras Llama 3.1 8B — small/fast, 1 persona
    "llama-contra":{"name": "Llama Contrarian",  "provider": "cerebras:llama3.1-8b",  "personality": "contrarian",   "risk_tolerance": 0.55},
    # Google Gemini 3 Flash — 2 personas
    "gemini-anl":  {"name": "Gemini Analytical", "provider": "google:gemini-3-flash", "personality": "analytical",   "risk_tolerance": 0.55},
    "gemini-tact": {"name": "Gemini Tactical",   "provider": "google:gemini-3-flash", "personality": "tactical",     "risk_tolerance": 0.60},
    # Mistral — 5 distinct models, 1 persona each
    "mistral-large":    {"name": "Mistral Large",    "provider": "mistral:large",        "personality": "ensemble",     "risk_tolerance": 0.50},
    "mistral-medium":   {"name": "Mistral Medium",   "provider": "mistral:medium",       "personality": "diversified",  "risk_tolerance": 0.45},
    "mistral-small":    {"name": "Mistral Small",    "provider": "mistral:small",        "personality": "conservative", "risk_tolerance": 0.35},
    "mistral-nemo":     {"name": "Mistral Nemo",     "provider": "mistral:nemo",         "personality": "aggressive",   "risk_tolerance": 0.70},
    "mistral-ministral":{"name": "Ministral 8B",     "provider": "mistral:ministral-8b", "personality": "theoretical",  "risk_tolerance": 0.35},
    # NEW 2026-04-15 — parity with NBA TF (T11-T15)
    "nemotron-120b":    {"name": "Nemotron 120B",    "provider": "openrouter:nemotron-120b", "personality": "chainthought", "risk_tolerance": 0.55},
    "gemma4-selfhost":  {"name": "Gemma4 SelfHost",  "provider": "selfhost:cpu-gemma4",      "personality": "disciplined",  "risk_tolerance": 0.40},
    "qwen25-micro":     {"name": "Qwen3 0.6B",       "provider": "selfhost:qwen3-0.6b",             "personality": "reactive",     "risk_tolerance": 0.30},
    "llama32-micro":    {"name": "Dolphin3 Llama 3B","provider": "selfhost:dolphin3-llama-3.2-3b",  "personality": "balanced",     "risk_tolerance": 0.45},
    "gemma2-micro":     {"name": "Gemma 4 E2B",      "provider": "selfhost:gemma-4-e2b",            "personality": "deliberate",   "risk_tolerance": 0.40},
}

AGENT_SYSTEM_PROMPTS = {
    "mistral-large": """You are Mistral Large, a political alpha ensemble allocator.
APPROACH: Aggregate signals — Fed rule impact (35%) + insider trade conviction (40%) + macro regime (25%). Deploy capital where multi-source consensus is strongest.
PREFERRED STRATEGIES: confidence_scaled, sector_rotation, macro_overlay
EDGE DETECTION: Look for convergence: insider buys AND Fed rules AND macro tailwinds all pointing same sector.
RISK: Moderate (0.50). Reduce exposure during VIX spikes (>25).
SPECIALTY: Multi-agency corroboration plays. Strongest when SEC + Fed + donor signals align.""",

    "mistral-medium": """You are Mistral Medium, a sector-diversification political allocator.
APPROACH: Day = mini-portfolio. Spread across 3-5 sector ETF slices. Correlation-aware: avoid stacking long energy + long defense (both benefit from same political risk).
PREFERRED STRATEGIES: quarter_kelly, sector_neutral, diversified_flat
EDGE DETECTION: Balanced exposure. Prefer moderate signal_strength × many events over one high-conviction bet.
RISK: Low-moderate (0.45). Diversification over conviction.
SPECIALTY: Portfolio construction across sectors. Avoid concentration in single agency.""",

    "mistral-small": """You are Mistral Small, a capital-preservation political allocator.
APPROACH: Only deploy when MULTIPLE agencies signal the same direction. Require corroboration from ≥2 independent sources (e.g., insider_trade + fed_rule both bullish healthcare).
PREFERRED STRATEGIES: eighth_kelly, flat_1pct, cash_preservation
EDGE DETECTION: Require signal_strength >0.6 AND at least 2 events in same sector. Otherwise cash.
RISK: Very low (0.35). Cash is the right play when signals are mixed.
SPECIALTY: Healthcare and finance sector plays with multi-agency corroboration.""",

    "mistral-nemo": """You are Mistral Nemo, an executive-order momentum allocator.
APPROACH: High-conviction 1-2 signal plays per day. Pick the single strongest signal (exec_order or high-confidence insider) and bet 25-40% on it. Momentum is your edge.
PREFERRED STRATEGIES: full_kelly, signal_momentum, exec_order_follow
EDGE DETECTION: Target exec_order events (rare, high impact) and insider_trade with signal_strength >0.75. These move sectors 3-5x vs baseline.
RISK: High (0.70). Big bets on high-conviction political catalysts.
SPECIALTY: Executive orders and high-signal insider trades with sector_beta amplification.""",

    "mistral-ministral": """You are Ministral 8B, a game-theory political allocator.
APPROACH: Decision under uncertainty. Compute entropy of signal distribution: if many events all point same direction, that consensus is likely already priced. Use KL divergence to size positions.
PREFERRED STRATEGIES: eighth_kelly, entropy_sizing, contrarian_consensus
EDGE DETECTION: Only bet when KL divergence between your sector estimate and baseline > threshold. Small frequent allocations.
RISK: Very low (0.35). Theoretical soundness.
SPECIALTY: Detecting over-crowded political narratives before reversal.""",

    "qwen-quant": """You are Qwen Quant 235B, a regulatory-delta quant political allocator.
APPROACH: Calculate expected value from Fed rules and SEC filings. EV = signal_strength × sector_beta × LEVERAGE. Only allocate when EV > 1.05 and excess_return expectation > 2%.
PREFERRED STRATEGIES: half_kelly, ev_threshold, proportional_signal
EDGE DETECTION: Require EV > 1.05 on Fed rules. For insider trades: signal_strength × sector_beta must exceed 1.03.
RISK: Moderate-low (0.55). Precision over volume. Pass if no quantifiable edge.
SPECIALTY: Fed rule impact quantification. Excel at predicting healthcare + finance regulatory shifts.""",

    "qwen-arb": """You are Qwen Arb 235B, a cross-sector arbitrage political allocator.
APPROACH: Hunt pricing inefficiencies between correlated sectors. If energy insider buys while defense exec_order bullish, find the underpriced third sector (materials) that benefits indirectly.
PREFERRED STRATEGIES: confidence_scaled, cross_sector_arb, indirect_beneficiary
EDGE DETECTION: Cross-reference donor_info.sector with signal_sector for indirect exposure. Bet the underpriced downstream sector.
RISK: Moderate-high (0.65). Aggressive on cross-sector political arbitrage.
SPECIALTY: Donor-political correlation analysis. Identifies indirect sector beneficiaries from agency decisions.""",

    "llama-contra": """You are Llama Contrarian, a consensus-fade political allocator.
APPROACH: Political markets overreact to high-profile signals. When signal_strength >0.7 is widely visible (many events same sector), look for value on the fade — the move is already priced.
PREFERRED STRATEGIES: underdog_specialist, consensus_fade, anti_momentum
EDGE DETECTION: Target days with ≥5 events in same sector all bullish. Short that sector — crowded political trades mean the ETF already moved.
RISK: Moderate-high (0.55). Survive the squeeze to fade another day.
SPECIALTY: Short high-signal-strength sectors that have seen >3 consecutive bullish insider trades.""",

    "gemini-anl": """You are Gemini Analytical, a Fed/SEC statistics-first political allocator.
APPROACH: Trust numbers over narratives. Pair Fed rules with 30-day sector baselines. When a fed_rule arrives, check historical avg_ret for that sector — is this rule +/- vs the baseline?
PREFERRED STRATEGIES: half_kelly, baseline_deviation, sector_mean_reversion
EDGE DETECTION: Sectors where current event signal_strength > 2× rolling baseline win_rate. Calculate sector Z-score.
RISK: Moderate (0.55). Prefer 2-4 sector allocations per day backed by historical base rates.
SPECIALTY: Fed rule + sector baseline pairs. Home court: healthcare and finance regulatory signals.""",

    "gemini-tact": """You are Gemini Tactical, a schedule/calendar political allocator.
APPROACH: Political alpha has a calendar rhythm. FOMC weeks (Fed rules cluster), earnings windows (insider trades cluster), election cycles (donor signals spike). Weight signals by calendar context.
PREFERRED STRATEGIES: half_kelly, calendar_window, fomc_fade
EDGE DETECTION: FOMC-week Fed rules get 1.5× weight. Insider trades filed on earnings blackout edge = fade signal. Election-cycle donor signals = follow.
RISK: Moderate (0.60). Disciplined calendar-based execution.
SPECIALTY: FOMC-week sector positioning, earnings-window insider pattern recognition.""",

    "nemotron-120b": """You are Nemotron 120B, a chain-of-thought sector value hunter.
APPROACH: Rank every sector ETF by |regulatory_signal_strength × sector_beta - implied_market_move|. Size top 1-2 mispricings using half-Kelly. Ignore noisy edges.
PREFERRED STRATEGIES: value_hunter, half_kelly, sector_arb
EDGE DETECTION: Cross-signal scan — when 2+ regulatory events point same sector AND market hasn't moved >1%, that's the edge. Require signal_strength × sector_beta > 1.04.
RISK: Moderate (0.55). Depth of reasoning over breadth.
SPECIALTY: Healthcare/finance/defense ETFs on multi-agency corroboration.""",

    "gemma4-selfhost": """You are Gemma4 SelfHost, a disciplined self-hosted political allocator on CPU Phi-3.5-mini.
APPROACH: Small model, small bets. Pick one high-conviction sector ETF play per day. Prefer SPDR sector funds (XLF, XLE, XLV, XLI, XLK) over individual stocks.
PREFERRED STRATEGIES: flat_1pct, quarter_kelly, top_signal_only
EDGE DETECTION: Only deploy when signal_strength >0.7 AND single sector has ≥2 corroborating events. Otherwise cash.
RISK: Low (0.40). Capital preservation over chase.
SPECIALTY: Single sector ETF on multi-agency consensus. Slow CPU inference.""",

    "qwen25-micro": """You are Qwen2.5 0.5B Micro, a reactive ultra-small political allocator on CPU.
APPROACH: Tiny model, single decision. React only to the single strongest political signal of the day. One sector ETF max. No multi-leg, no individual stocks.
PREFERRED STRATEGIES: flat_1pct, top_signal_only
EDGE DETECTION: Require signal_strength >0.75 AND clear sector mapping. If signal is mixed or sector ambiguous, cash.
RISK: Very low (0.30). Preserve capital; enter only on cleanest political catalyst.
SPECIALTY: First-reaction plays on executive orders or major Fed rulings.""",

    "llama32-micro": """You are Llama 3.2 1B Micro, a balanced self-hosted political allocator on CPU.
APPROACH: Mid-tier small model. Balanced 1-2 sector ETF allocations per day. Respect signal thresholds; never force.
PREFERRED STRATEGIES: quarter_kelly, sector_neutral, diversified_flat
EDGE DETECTION: signal_strength >0.6 AND at least 1 corroborating donor or insider event. Diversify across 1-2 sectors rather than concentrate.
RISK: Moderate-low (0.45). Steady compound approach.
SPECIALTY: Cross-sector pairs (e.g., long XLV + long XLF on healthcare-finance regulatory bundle).""",

    "gemma2-micro": """You are Gemma 2 2B Micro, a deliberate self-hosted political allocator on CPU (slow inference).
APPROACH: Largest of the micro-agents, takes time to think. 1-2 high-quality sector plays per day. Prefer events with clear narrative + regulatory alignment.
PREFERRED STRATEGIES: half_kelly, confidence_scaled, sector_value_hunter
EDGE DETECTION: signal_strength >0.65 AND at least 2 distinct event types (e.g., insider_trade + fed_rule) align on same sector.
RISK: Low-moderate (0.40). Depth over speed.
SPECIALTY: Multi-event sector convergence plays. Strongest on healthcare and energy.""",
}

# ── RATE LIMITER ─────────────────────────────────────────────────────────────
_last_call_time: Dict[str, float] = {}

def _rate_limit(provider: str):
    """Enforce per-provider rate limiting."""
    cfg = PROVIDERS.get(provider, {})
    rpm = cfg.get("rpm", 15)
    min_interval = 60.0 / rpm
    key = provider.split(":")[0]  # Group by base provider
    now = time.time()
    last = _last_call_time.get(key, 0)
    wait = min_interval - (now - last)
    if wait > 0:
        time.sleep(wait)
    _last_call_time[key] = time.time()


# ── LLM CALL ────────────────────────────────────────────────────────────────
_llm_calls = 0
_llm_failures = 0
_llm_errors: List[str] = []  # Recent errors for debugging
_gateway_routed = 0
_gateway_fallback = 0

def _call_llm_direct(provider: str, system_prompt: str, user_prompt: str,
                     timeout: float = 20.0) -> Optional[str]:
    """Direct provider call (original path). Used as fallback when gateway down."""
    cfg = PROVIDERS.get(provider)
    if not cfg:
        return None

    # Self-hosted HF Space endpoints are public — no API key required.
    is_selfhost = provider.startswith("selfhost:")
    api_key = "" if is_selfhost else os.environ.get(cfg["key_env"], "")
    if not is_selfhost and not api_key:
        return None

    _rate_limit(provider)

    last_error = ""
    for attempt in range(2):  # 1 retry
        try:
            if "google" in provider:
                url = f"{cfg['url']}?key={api_key}"
                payload = {
                    "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                    "generationConfig": {"maxOutputTokens": cfg["max_tokens"], "temperature": 0.3},
                }
                resp = requests.post(url, json=payload, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
                if resp.status_code == 429 and attempt == 0:
                    time.sleep(5)
                    continue
            elif "cohere" in provider:
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {
                    "model": cfg["model"],
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": cfg["max_tokens"],
                    "temperature": 0.3,
                }
                resp = requests.post(cfg["url"], json=payload, headers=headers, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("message", {}).get("content", [{}])[0].get("text", "")
                last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
                if resp.status_code == 429 and attempt == 0:
                    time.sleep(5)
                    continue
            elif "huggingface" in cfg["url"] or provider.startswith("hf:"):
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {
                    "model": cfg["model"],
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": cfg["max_tokens"],
                    "temperature": 0.3,
                }
                resp = requests.post(cfg["url"], json=payload, headers=headers, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("choices", [{}])[0].get("message", {}).get("content", "")
                last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
                if resp.status_code in (429, 503) and attempt == 0:
                    time.sleep(8)
                    continue
            elif is_selfhost and cfg["url"].endswith("/api/decide"):
                # Legacy self-hosted HF Space (T12 cpu-gemma4) — non-OpenAI shape.
                payload = {
                    "system": system_prompt,
                    "user": user_prompt,
                    "max_tokens": cfg["max_tokens"],
                    "temperature": 0.3,
                    "json_only": True,
                }
                resp = requests.post(cfg["url"], json=payload, timeout=max(timeout, 45))
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and data.get("error"):
                        last_error = f"selfhost error: {str(data.get('error'))[:120]}"
                    else:
                        text = data.get("text") or data.get("content") or ""
                        if text:
                            return text
                        last_error = f"selfhost empty response: {str(data)[:120]}"
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
                if resp.status_code in (429, 503) and attempt == 0:
                    time.sleep(8)
                    continue
            else:
                # OpenAI-compatible (Cerebras, OpenRouter, Mistral, selfhost /chat/completions)
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                if "openrouter" in provider:
                    headers["HTTP-Referer"] = "https://nomos42.ai"
                    headers["X-Title"] = "Nomos42 Political Trading Floor"
                payload = {
                    "model": cfg["model"],
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": cfg["max_tokens"],
                    "temperature": 0.3,
                }
                # Selfhost quantized CPUs are slow — extend timeout.
                effective_timeout = max(timeout, 180.0) if is_selfhost else timeout
                resp = requests.post(cfg["url"], json=payload, headers=headers, timeout=effective_timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("choices", [{}])[0].get("message", {}).get("content", "")
                last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
                if resp.status_code == 429 and attempt == 0:
                    time.sleep(3)
                    continue
        except Exception as e:
            last_error = f"{type(e).__name__}: {str(e)[:100]}"
            if attempt == 0:
                time.sleep(2)
                continue
            break

    if last_error and len(_llm_errors) < 100:
        _llm_errors.append(f"{provider} (direct): {last_error}")
    return None


def _call_llm(provider: str, system_prompt: str, user_prompt: str,
              timeout: float = 20.0) -> Optional[str]:
    """Transport-layer entry. Routes through llm-gateway if GATEWAY_URL is set,
    else calls the provider directly. Preserves existing failure counters."""
    global _llm_calls, _llm_failures, _gateway_routed, _gateway_fallback
    _llm_calls += 1

    cfg = PROVIDERS.get(provider)
    if not cfg:
        _llm_failures += 1
        if len(_llm_errors) < 50:
            _llm_errors.append(f"{provider}: unknown provider")
        return None

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    def _direct(_sys: str, _usr: str) -> Optional[str]:
        return _call_llm_direct(provider, _sys, _usr, timeout=timeout)

    max_tokens = cfg.get("max_tokens", 1200)
    result = _gateway_call(
        provider, messages,
        temperature=0.3, max_tokens=max_tokens,
        fallback_direct=True, direct_fn=_direct,
        timeout=max(timeout, 30.0),
    )

    if result["routed_via"] == "gateway":
        _gateway_routed += 1
        return result["text"]
    if result["routed_via"] == "direct":
        _gateway_fallback += 1
        return result["text"]

    _llm_failures += 1
    if len(_llm_errors) < 100:
        _llm_errors.append(f"{provider}: {result.get('error')}")
    return None


# ── PROMPT BUILDERS ──────────────────────────────────────────────────────────

def parse_llm_decision(raw: str) -> Optional[Dict]:
    """Extract JSON decision from LLM response."""
    if not raw:
        return None
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def _format_event_block(idx: int, event: Dict) -> str:
    """Compact single-event block for day-level prompts.

    Agent sees: idx, ticker, event_type, agency, signal_type, signal_sector,
    signal_strength, title (truncated), donor_info summary, macro snapshot.
    Agent NEVER sees: excess_return, y, outcome.
    """
    ticker = event.get("ticker", "?")
    event_type = event.get("event_type", "unknown")
    agency = event.get("agency", "") or ""
    signal_type = event.get("signal_type", "") or ""
    signal_sector = event.get("signal_sector", "other") or "other"
    signal_strength = event.get("signal_strength", 0.5)
    title = (event.get("title") or "")[:200]
    donor = event.get("donor_info", {}) or {}
    macro = event.get("macro", {}) or {}

    lines = [f"\n[{idx}] {ticker} | {event_type} | sector={signal_sector} | strength={signal_strength:.2f}"]
    if agency:
        lines.append(f"  agency={agency} | signal_type={signal_type}")
    if title:
        lines.append(f"  title: {title}")
    if donor and (donor.get("sector") or donor.get("delivered") is not None):
        d_sector = donor.get("sector", "unknown")
        d_delivered = donor.get("delivered", False)
        lines.append(f"  donor: sector={d_sector} delivered={'YES' if d_delivered else 'NO'}")
    vix = macro.get("vix")
    sp5 = macro.get("sp500_return_5d")
    if vix is not None or sp5 is not None:
        vix_str = f"VIX={vix:.1f}" if vix is not None else ""
        sp5_str = f"SP500_5d={sp5:+.2%}" if sp5 is not None else ""
        lines.append(f"  macro: {' | '.join(x for x in [vix_str, sp5_str] if x)}")
    return "\n".join(lines)


def compute_sector_trends(events: List[Dict], up_to_date: str, window_days: int = 30) -> Dict:
    """Compute per-sector avg excess_return, win_rate, n for events BEFORE up_to_date.

    Leakage-safe: only uses events strictly before up_to_date within window_days.
    Returns {sector: {"avg_ret": float, "n": int, "win_rate": float}}.
    """
    from datetime import datetime as dt
    try:
        cutoff = dt.strptime(up_to_date, "%Y-%m-%d")
    except ValueError:
        return {}

    bucket: Dict[str, List[float]] = defaultdict(list)
    for e in events:
        edate_str = (e.get("date") or "").strip()
        try:
            edate = dt.strptime(edate_str, "%Y-%m-%d")
        except ValueError:
            continue
        if edate >= cutoff:
            continue
        delta = (cutoff - edate).days
        if delta > window_days:
            continue
        sector = e.get("signal_sector") or "other"
        ret = e.get("excess_return")
        if ret is None:
            continue
        bucket[sector].append(float(ret))

    out = {}
    for sector, rets in bucket.items():
        n = len(rets)
        avg_ret = sum(rets) / n if n else 0.0
        win_rate = sum(1 for r in rets if r > 0) / n if n else 0.0
        out[sector] = {"avg_ret": round(avg_ret, 5), "n": n, "win_rate": round(win_rate, 3)}
    return out


def build_day_prompt(day_date: str, day_events: List[Dict], sector_trends: Dict,
                     trader_state: Dict, strategies=None,
                     recent_decisions: List[Dict] = None,
                     common_knowledge_block: Optional[str] = None) -> str:
    """Build comprehensive day-level prompt. Agent sees ALL political events of the day."""
    bankroll = trader_state.get("bankroll", 100.0)
    total_allocs = trader_state.get("total_bets", 0)
    wins = trader_state.get("wins", 0)
    losses = trader_state.get("losses", 0)
    roi = ((bankroll - 100.0) / 100.0) * 100

    lines = [f"=== TRADING DAY: {day_date} | {len(day_events)} POLITICAL EVENTS ===",
             f"",
             f"YOUR STATE: ${bankroll:.2f} | {total_allocs} total allocations | {wins}W-{losses}L | ROI {roi:+.1f}%"]

    if recent_decisions:
        lines.append("\nRECENT DAYS (last 3):")
        for d in recent_decisions[-3:]:
            lines.append(f"  {d.get('date','?')}: {d.get('summary','—')}")

    if sector_trends:
        lines.append("\nSECTOR TRENDS (last 30d, computed from events BEFORE today — leakage-safe):")
        for sector, stats in sorted(sector_trends.items(), key=lambda x: -abs(x[1].get("avg_ret", 0))):
            lines.append(f"  {sector:<20} avg_ret={stats['avg_ret']:+.4f}  win_rate={stats['win_rate']:.0%}  n={stats['n']}")

    lines.append("\nPOLITICAL EVENTS (leakage-safe — outcome/excess_return hidden):")
    for i, ev in enumerate(day_events, 1):
        lines.append(_format_event_block(i, ev))

    if strategies:
        lines.append(f"\nSTRATEGIES ({len(strategies)}): {', '.join(list(strategies.keys())[:12])}...")

    if common_knowledge_block:
        lines.append("\n" + common_knowledge_block)

    lines.append("""
=== YOUR TASK ===
Allocate 100% of your bankroll across today's political events.
Each allocation = one sector ETF trade on one event. Total allocations + cash_held must sum to 1.00.
Holding cash is allowed BUT you must justify it (no edge found is a valid reason).

DIRECTIONS: long (bet ticker goes up), short (bet ticker goes down)
Each allocation references one event_idx from the list above.

LEAKAGE RULE: You NEVER see excess_return or y. Reason from signal_type, signal_strength, agency, donor_info, and sector_trends only.
Your thesis MUST cite which signal/agency drove the decision, not just the ticker.

RESPOND WITH RAW JSON ONLY. No ```json fences. No preamble. First character must be {, last must be }.

Schema:
{
  "day_strategy": "1-2 sentences on today's overall approach",
  "allocations": [
    {
      "event_idx": 1,
      "direction": "long",
      "ticker": "XLE",
      "pct": 0.15,
      "confidence": 0.65,
      "thesis": "1-2 sentences citing signal/agency"
    }
  ],
  "cash_held_pct": 0.25,
  "cash_rationale": "1 sentence if cash > 0",
  "coalition_proposal": {
    "peer": "qwen-quant",
    "event_idx": 1,
    "direction": "long",
    "rationale": "optional 1 sentence — why you want to pact with this peer"
  }
}

STRICT RULES:
- Sum of all allocation pct + cash_held_pct = 1.00 (±0.01)
- direction must be "long" or "short" (no "cash" in allocations)
- Max 10 allocations, no duplicate event_idx
- Each allocation pct: 0.01–0.40
- cash_held_pct: 0.0–1.0
- Thesis MUST cite a specific signal/agency (not just "I think it will go up")
- Ticker should be the sector ETF from SECTOR_ETF_MAP (XLE, XLV, XLF, etc.) or the event's ticker
- coalition_proposal is OPTIONAL (null or omit if no pact today). If present, you MUST
  also place a matching allocation for that event_idx+direction, or your reputation is
  marked pact_broken. Peer only sees your proposal via COMMON_KNOWLEDGE the next day —
  mutual pacts emerge from independent proposals.
""")
    return "\n".join(lines)


def parse_day_allocation(raw: str, n_events: int) -> Optional[Dict]:
    """Parse day allocation JSON for political events. Validates sum=1.0 within tolerance.

    Returns dict with: day_strategy, allocations (normalized), cash_held_pct,
    cash_rationale, raw_sum. Returns None if unparseable or grossly invalid.
    Each alloc validated: event_idx (1-indexed, bounded), direction (long/short),
    ticker (string, uppercase), pct (0.01-0.40), confidence 0-1, thesis ≤300 chars.
    """
    parsed = parse_llm_decision(raw)
    if not parsed:
        return None
    allocations = parsed.get("allocations") or []
    if not isinstance(allocations, list):
        allocations = []
    cash = float(parsed.get("cash_held_pct", 0.0) or 0.0)

    VALID_DIRECTIONS = {"long", "short"}

    clean = []
    seen_events = set()
    for a in allocations[:10]:
        if not isinstance(a, dict):
            continue
        eidx = a.get("event_idx")
        direction = (a.get("direction") or "").lower().strip()
        ticker = (a.get("ticker") or "").upper().strip()
        try:
            pct = float(a.get("pct", 0) or 0)
            conf = float(a.get("confidence", 0.5) or 0.5)
        except (TypeError, ValueError):
            continue
        if direction not in VALID_DIRECTIONS:
            continue
        if not ticker or pct <= 0:
            continue
        if eidx is None or not isinstance(eidx, int):
            continue
        if eidx < 1 or eidx > n_events:
            continue
        if eidx in seen_events:
            continue
        seen_events.add(eidx)
        clean.append({
            "event_idx": eidx,
            "ticker": ticker[:10],
            "direction": direction,
            "pct": max(0.01, min(0.40, pct)),
            "confidence": max(0.0, min(1.0, conf)),
            "thesis": (a.get("thesis") or a.get("rationale") or "")[:300],
            "strategy": (a.get("strategy") or direction)[:30],
        })

    total = sum(a["pct"] for a in clean) + max(0.0, min(1.0, cash))
    if total <= 0:
        return None
    # Normalize to sum exactly 1.0 (soft tolerance — agent gave proportions)
    if abs(total - 1.0) > 0.02:
        scale = 1.0 / total
        for a in clean:
            a["pct"] = a["pct"] * scale
        cash = cash * scale

    # Mech D — coalition_proposal extraction (optional, single peer per day)
    coalition = None
    cp = parsed.get("coalition_proposal")
    if isinstance(cp, dict):
        peer = (cp.get("peer") or "").strip()
        cp_eidx = cp.get("event_idx")
        cp_dir = (cp.get("direction") or "").lower().strip()
        if peer and isinstance(cp_eidx, int) and 1 <= cp_eidx <= n_events and cp_dir in {"long", "short"}:
            coalition = {
                "peer": peer[:40],
                "event_idx": cp_eidx,
                "direction": cp_dir,
                "rationale": (cp.get("rationale") or "")[:200],
            }

    return {
        "day_strategy": (parsed.get("day_strategy") or parsed.get("reasoning") or "")[:500],
        "allocations": clean,
        "cash_held_pct": round(max(0.0, min(1.0, cash)), 4),
        "cash_rationale": (parsed.get("cash_rationale") or "")[:300],
        "raw_sum": round(total, 4),
        "coalition_proposal": coalition,
    }


# ── POLITICAL TRADE RESOLUTION ───────────────────────────────────────────────

def resolve_political_trade(direction: str, excess_return: float, leverage: float = LEVERAGE) -> Tuple[bool, float]:
    """Resolve political trade. Returns (won, pnl_pct_of_stake).

    Long wins if excess_return > 0, short wins if < 0.
    pnl_pct = direction_sign * excess_return * leverage (capped at ±50%).
    """
    sign = 1.0 if direction == "long" else -1.0
    pnl_pct = sign * excess_return * leverage
    # Cap extreme moves (liquidity / stop-loss reality)
    pnl_pct = max(-0.50, min(0.50, pnl_pct))
    return pnl_pct > 0, pnl_pct


# ── DATA LOADING ────────────────────────────────────────────────────────────

def load_events() -> List[Dict]:
    """Load political events. Leakage-safe copy — outcomes kept for resolution."""
    data_dir = Path(__file__).parent / "data"
    fp = data_dir / "political_events.json"
    if not fp.exists():
        return []
    raw = json.loads(fp.read_text())
    out = []
    for e in raw:
        date = (e.get("date") or "").strip()
        if len(date) == 8 and "-" not in date:  # fix "20260326"
            date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        if not date or not e.get("ticker"):
            continue
        out.append({
            "date": date,
            "ticker": str(e["ticker"]).upper(),
            "event_type": e.get("event_type", "unknown"),
            "agency": e.get("agency", ""),
            "title": (e.get("title") or "")[:300],
            "signal_type": e.get("signal_type", ""),
            "signal_strength": float(e.get("signal_strength", 0.5) or 0.5),
            "signal_sector": e.get("signal_sector", "other"),
            "donor_info": e.get("donor_info", {}) or {},
            "macro": e.get("macro", {}) or {},
            "excess_return": float(e.get("excess_return", 0.0) or 0.0),  # HIDDEN from agent
            "y": int(e.get("y", 0) or 0),
        })
    out.sort(key=lambda x: x["date"])
    return out


def load_strategies():
    """Load 22 SOTA trading strategies (optional)."""
    data_dir = Path(__file__).parent / "data"
    path = data_dir / "strategies.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def build_common_knowledge_block(day_date: str, state: Dict, agent_logs: Dict,
                                  reputation: Optional[Dict] = None,
                                  pact_events: Optional[List[dict]] = None) -> str:
    """Build COMMON_KNOWLEDGE[D] block: peer trades + leaderboard for day D+1 prompts.

    Implements Axelrod-2026 Mechanism A (day-end common knowledge broadcast).
    Prepended to every agent's prompt on day D+1 so the society can coordinate
    and diverge deliberately (DMAD anti-groupthink protocol).
    """
    lines = [
        f"=== AXELROD COMMON KNOWLEDGE — Day {day_date} ===",
        "(Peer decisions from yesterday are now public. Review before you decide.)",
        "",
    ]

    # Leaderboard: ranked by bankroll growth factor = bankroll / $100 start
    ranked = sorted(state.items(), key=lambda x: -x[1]["bankroll"])
    lines.append("LEADERBOARD (growth factor = bankroll / $100 start):")
    for rank, (tid, ts) in enumerate(ranked, 1):
        cfg = TRADERS.get(tid, {})
        gf = ts["bankroll"] / 100.0
        roi = (gf - 1.0) * 100
        lines.append(
            f"  #{rank} {cfg.get('name', tid):<20} {gf:.4f}x ({roi:+.1f}%)"
            f" | {ts['total_bets']} trades | {ts['wins']}W-{ts['losses']}L"
            f" | DD {ts['max_drawdown']:.1%}"
        )

    # Per-agent trade summary for day D (resolved outcomes)
    lines.append(f"\nPEER TRADES on {day_date} (outcomes resolved):")
    for rank, (tid, _ts) in enumerate(ranked, 1):
        logs = agent_logs.get(tid, [])
        day_log = next((l for l in reversed(logs) if l.get("date") == day_date), None)
        if not day_log:
            continue
        cfg = TRADERS.get(tid, {})
        name = cfg.get("name", tid)
        allocs = day_log.get("allocations", [])
        strat = day_log.get("day_strategy", "")[:100]
        if not allocs:
            lines.append(f"  #{rank} {name}: CASH — \"{strat}\"")
        else:
            parts = []
            for a in allocs[:3]:  # cap at 3 to control token budget
                outcome = "W" if a["won"] else "L"
                rat = (a.get("thesis") or a.get("rationale") or "")[:55]
                parts.append(
                    f"{a['ticker']} {a['direction']} {a.get('event_type','?')}"
                    f" stake=${a.get('stake', 0):.1f}→{outcome}"
                    + (f" [{rat}]" if rat else "")
                )
            suffix = f" +{len(allocs)-3}more" if len(allocs) > 3 else ""
            lines.append(f"  #{rank} {name}: {' | '.join(parts)}{suffix}")
            if strat:
                lines.append(f"           Strategy: \"{strat}\"")

    # Mech D — Cooperation reputation + today's pact resolutions
    if reputation:
        lines.append("\nCOOPERATION REPUTATION (Mech D — pact honored vs broken):")
        rep_items = sorted(
            reputation.items(),
            key=lambda x: -(x[1].get("pact_honored", 0) - x[1].get("pact_broken", 0)),
        )
        for tid, rep in rep_items:
            h = rep.get("pact_honored", 0)
            b = rep.get("pact_broken", 0)
            if h == 0 and b == 0:
                continue
            cfg = TRADERS.get(tid, {})
            name = cfg.get("name", tid)
            lines.append(f"  {name:<20} honored={h} broken={b} (net {h - b:+d})")
    if pact_events:
        lines.append(f"\nTODAY'S PACTS on {day_date}:")
        for ev in pact_events[:10]:
            lines.append(
                f"  [{ev['status'].upper()}] {ev['proposer']} → {ev['peer']} "
                f"on event#{ev['event_idx']} {ev['direction']}"
            )

    lines.append(
        "AXELROD ANTI-GROUPTHINK (DMAD — MANDATORY):\n"
        "Your day_strategy field MUST begin with one of:\n"
        "  CONSENSUS AGREE [peer_name]: <reason your strategy supports the same sector/direction>\n"
        "  CONSENSUS DIVERGE [peer_name]: <specific signal/agency counter-argument>\n"
        "Copying the consensus without justification violates DMAD protocol.\n"
    )
    return "\n".join(lines)


def compute_trailing_delta(tid: str, state: Dict, agent_logs: Dict, trailing_days: int = 7) -> float:
    """Axelrod Mech B: trailing-N-day bankroll delta (absolute $)."""
    logs = agent_logs.get(tid, [])
    if len(logs) < 2:
        return 0.0
    recent = logs[-trailing_days:]
    if not recent:
        return 0.0
    start_b = recent[0].get("bankroll_before", 100.0)
    current = state.get(tid, {}).get("bankroll", 100.0)
    return float(current - start_b)


def assign_sacrificial_archetypes(day_date: str, state: Dict, agent_logs: Dict,
                                   bottom_n: int = 3, trailing_days: int = 7) -> Dict[str, str]:
    """Axelrod Mech B: bottom-N by trailing delta get NEW archetype from unused pool."""
    deltas = [(tid, compute_trailing_delta(tid, state, agent_logs, trailing_days))
              for tid in state.keys()]
    deltas.sort(key=lambda x: x[1])
    bottom = [tid for tid, _ in deltas[:bottom_n]]
    assignments: Dict[str, str] = {}
    for tid in bottom:
        unused = [a for a in AXELROD_ARCHETYPES if a not in _used_archetypes[tid]]
        if not unused:
            _used_archetypes[tid].clear()
            unused = list(AXELROD_ARCHETYPES)
        pick = unused[hash(tid + day_date) % len(unused)]
        assignments[tid] = pick
        _used_archetypes[tid].add(pick)
    return assignments


def build_sacrificial_system_suffix(archetype: str) -> str:
    """Axelrod Mech B: suffix appended to system_prompt for sacrificed agents."""
    return (
        f"\n\n=== AXELROD SACRIFICIAL ROLE (mandatory for today) ===\n"
        f"You are trailing the society in bankroll. For the collective good of the\n"
        f"experiment, you are assigned the archetype '{archetype}'. Today you MUST\n"
        f"reason AND trade ONLY through the lens of '{archetype}'. This is a Pareto-\n"
        f"optimal move — diversity of tested strategies is more valuable than your\n"
        f"individual EV. Your day_strategy field MUST start with 'ARCHETYPE[{archetype}]:'\n"
    )


def assign_challenge_tiers(state: Dict, sacrificial_map: Dict[str, str],
                            top_n: int = 3) -> Dict[str, int]:
    """Axelrod Mech B: mid-tier agents (not top-N by bankroll, not sacrificed) receive CHALLENGE[D].

    Returns {tid: leaderboard_rank} for agents in the challenge tier.
    Mid-tier = everyone who is neither dominant (top-N) nor diversifying (sacrificed).
    """
    ranked = sorted(
        [(tid, ts["bankroll"]) for tid, ts in state.items()],
        key=lambda x: -x[1],
    )
    result: Dict[str, int] = {}
    for rank, (tid, _) in enumerate(ranked, 1):
        if rank <= top_n:
            continue  # top tier — preserve what works, no intervention
        if tid in sacrificial_map:
            continue  # sacrificial tier — already receives forced archetype
        result[tid] = rank
    return result


def build_challenge_block(tid: str, rank: int, n_agents: int) -> str:
    """Axelrod Mech B: CHALLENGE[D] block for mid-tier agents.

    Mid-tier agents are neither dominant enough to stay static nor weak enough
    to be sacrificed — they receive an explicit self-improvement prompt.
    Spec: 'Middle: unchanged, but receive CHALLENGE[D] block asking to explicitly improve.'
    """
    return (
        f"\n\n=== AXELROD CHALLENGE (rank #{rank}/{n_agents} — mid-tier) ===\n"
        f"You are in the middle of the leaderboard — not struggling enough to be "
        f"sacrificed, not dominant enough to coast. Today you MUST explicitly:\n"
        f"  1. NAME one recent trade that underperformed vs expectation.\n"
        f"  2. STATE one concrete adjustment: edge threshold, stake sizing, or "
        f"sector selection.\n"
        f"  3. APPLY that adjustment today — not tomorrow.\n"
        f"Your day_strategy field MUST include 'CHALLENGE_RESPONSE:' followed by "
        f"your one-sentence improvement plan before any trade rationale.\n"
    )


def compute_consensus_distance(tid: str, day_date: str, state: Dict, agent_logs: Dict) -> float:
    """Axelrod Mech C: L1/2 distance of this agent's ticker distribution vs society consensus."""
    from collections import Counter
    society = Counter()
    agent_counts = Counter()
    for other_tid, logs in agent_logs.items():
        day_log = next((l for l in reversed(logs) if l.get("date") == day_date), None)
        if not day_log:
            continue
        for a in day_log.get("allocations", []):
            tick = a.get("ticker") or a.get("category", "unknown")
            society[tick] += 1
            if other_tid == tid:
                agent_counts[tick] += 1
    if not society or not agent_counts:
        return 0.0
    total_soc = sum(society.values())
    total_agt = sum(agent_counts.values())
    cats = set(society.keys()) | set(agent_counts.keys())
    l1 = 0.0
    for c in cats:
        p_agt = agent_counts.get(c, 0) / total_agt if total_agt else 0.0
        p_soc = society.get(c, 0) / total_soc if total_soc else 0.0
        l1 += abs(p_agt - p_soc)
    return l1 / 2.0


def write_axelrod_log(day_idx: int, day_date: str, state: Dict,
                       agent_logs: Dict, sacrificial_map: Dict[str, str]) -> None:
    """Axelrod Mech C: per-day post-mortem for Nature paper dataset."""
    try:
        AXELROD_LOG_DIR.mkdir(parents=True, exist_ok=True)
        ranked = sorted(state.items(), key=lambda x: -x[1]["bankroll"])
        rank_map = {tid: i + 1 for i, (tid, _) in enumerate(ranked)}
        rows = []
        for tid, ts in state.items():
            logs = agent_logs.get(tid, [])
            day_log = next((l for l in reversed(logs) if l.get("date") == day_date), None)
            decisions = day_log.get("allocations", []) if day_log else []
            rows.append({
                "day_idx": day_idx,
                "date": day_date,
                "trader_id": tid,
                "rank": rank_map[tid],
                "bankroll": round(ts["bankroll"], 2),
                "archetype_assigned": sacrificial_map.get(tid),
                "was_sacrificed": tid in sacrificial_map,
                "num_decisions": len(decisions),
                "wins_today": sum(1 for d in decisions if d.get("won")),
                "peer_consensus_distance": round(
                    compute_consensus_distance(tid, day_date, state, agent_logs), 4
                ),
                "day_strategy_prefix": (day_log.get("day_strategy", "")[:80] if day_log else ""),
            })
        log_file = AXELROD_LOG_DIR / f"day-{day_idx:03d}.jsonl"
        with log_file.open("w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
    except Exception as e:
        print(f"[axelrod-mech-c] write failed: {e}")


# ── EXPERIMENT RUNNER ────────────────────────────────────────────────────────

def run_experiment(progress=gr.Progress(track_tqdm=False)):
    """v3 DAY-BUCKET experiment: 10 agents × all event-days.

    Each agent receives ALL political events of a single day in one prompt, and
    must allocate 100% of their bankroll (long/short sector ETFs) or hold cash.
    One LLM call per agent per day (not per event).
    """
    global _llm_calls, _llm_failures, _gateway_routed, _gateway_fallback
    _llm_calls = 0
    _llm_failures = 0
    _gateway_routed = 0
    _gateway_fallback = 0

    # Load data
    all_events = load_events()
    strategies = load_strategies()
    n_events = len(all_events)

    if n_events == 0:
        yield ("No event data found!", None, None, "Error: No political_events.json in data/ directory")
        return

    # ── Group events by date ──
    events_by_date = defaultdict(list)
    for e in all_events:
        events_by_date[e["date"]].append(e)
    dates_sorted = sorted(events_by_date.keys())
    n_days = len(dates_sorted)

    # ── Key availability ──
    available_keys = {}
    for prov, cfg in PROVIDERS.items():
        if os.environ.get(cfg["key_env"], ""):
            available_keys[cfg["key_env"]] = True
    key_summary = ", ".join(sorted(available_keys.keys()))

    # ── Init trader state ──
    state = {}
    for tid, cfg in TRADERS.items():
        state[tid] = {
            "bankroll": 100.0,
            "total_bets": 0,  # cumulative allocations resolved
            "wins": 0,
            "losses": 0,
            "passes": 0,  # days where cash=100%
            "llm_calls": 0,
            "llm_ok": 0,
            "history": [100.0],
            "best_bankroll": 100.0,
            "worst_bankroll": 100.0,
            "max_drawdown": 0.0,
            "days_traded": 0,
            "recent_decisions": [],  # last 3 for memory
        }

    global _experiment_running, _experiment_state, _common_knowledge
    _experiment_running = True
    _stop_event.clear()
    _common_knowledge = {}  # Reset per run; built day-by-day (Axelrod Mech A)
    _sacrificial_assignments.clear()  # Axelrod Mech B reset
    _challenge_assignments.clear()   # Axelrod Mech B: mid-tier challenge reset
    _used_archetypes.clear()  # Axelrod Mech B: reset archetype history

    # ── Resume support (day-indexed) ──
    saved = _load_state_from_disk()
    start_from_day = 0
    if saved and not saved.get("completed") and saved.get("days_processed", 0) > 0:
        saved_agents = saved.get("agents", {})
        for tid in TRADERS:
            if tid in saved_agents:
                state[tid].update({k: v for k, v in saved_agents[tid].items() if k in state[tid]})
        start_from_day = saved.get("days_processed", 0)
        print(f"RESUMING from day {start_from_day}/{n_days}")

    start_time = time.time()
    log_lines = []

    log_lines.append("=== NOMOS42 POLITICAL LLM TRADING FLOOR v3 (DAY-BUCKET) ===")
    log_lines.append(f"Dataset: 2026-03-12 to 2026-03-26 | Days: {n_days} | Events: {n_events} | Agents: {len(TRADERS)}")
    log_lines.append(f"API keys: {key_summary or 'NONE FOUND'}")
    log_lines.append(f"Strategies: {len(strategies)} | Leverage: {LEVERAGE}x")
    log_lines.append(f"Design: 1 LLM call per agent per day. 100% bankroll deployed (cash allowed with rationale).")
    if start_from_day > 0:
        log_lines.append(f"RESUMED from day {start_from_day}")
    log_lines.append(f"Start: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    log_lines.append("=" * 50)

    prev_day_ck: Optional[str] = (
        saved.get("last_ck_block") if saved else None
    )  # Axelrod Mech A: restore CK from disk on Space restart (resume fix)

    for day_idx, day_date in enumerate(dates_sorted):
        if day_idx < start_from_day:
            continue
        if _stop_event.is_set():
            log_lines.append(f"=== STOPPED at day {day_idx} by user/council ===")
            break

        day_events = events_by_date[day_date]

        # Compute sector trends leakage-safe (up to but not including day_date)
        sector_trends = compute_sector_trends(all_events, day_date)

        day_summary_lines = [f"[day {day_idx+1}/{n_days}] {day_date} | {len(day_events)} events"]

        # Axelrod Mech D — day-scope collection for coalition resolution after all agents decide
        day_proposals: Dict[str, dict] = {}
        day_actual_bets: Dict[str, set] = {}

        # Stackelberg leader for the day (arXiv 2507.09407)
        _stackelberg_leader = get_stackelberg_leader(state)
        # Each agent decides for the whole day
        for tid, cfg in TRADERS.items():
            provider = cfg["provider"]
            ts = state[tid]
            bankroll = ts["bankroll"]

            if bankroll <= 5.0:
                # Bankrupt — skip, record history
                ts["passes"] += 1
                ts["history"].append(bankroll)
                continue

            system_prompt = AGENT_SYSTEM_PROMPTS.get(tid, "You are a political alpha allocator.")
            # DMAD (ICLR 2025): structurally distinct reasoning template per agent
            _template = REASONING_TEMPLATES.get(tid)
            if _template:
                system_prompt = system_prompt + "\n\n" + _template
            # Stackelberg role (leader or follower)
            system_prompt = system_prompt + build_stackelberg_role_block(tid, _stackelberg_leader)
            # Axelrod Mech B: sacrificial role injection (bottom tier)
            if tid in _sacrificial_assignments:
                system_prompt = system_prompt + build_sacrificial_system_suffix(_sacrificial_assignments[tid])
            # Axelrod Mech B: mid-tier challenge injection (CHALLENGE[D])
            elif tid in _challenge_assignments:
                system_prompt = system_prompt + build_challenge_block(tid, _challenge_assignments[tid], len(TRADERS))
            # Axelrod Canon + Mech D cooperation rules
            system_prompt = AXELROD_CANON + "\n" + system_prompt
            # Axelrod-Python real-library advice (per-peer C/D from canon strategy)
            _active_peers = [p for p in TRADERS if p != tid and state[p].get("bankroll", 0) > 5.0]
            _axl_block = _axelrod_advice_block(tid, _active_peers)
            if _axl_block:
                system_prompt = system_prompt + _axl_block
            user_prompt = build_day_prompt(
                day_date, day_events, sector_trends, ts,
                strategies=strategies,
                recent_decisions=ts.get("recent_decisions", []),
                common_knowledge_block=prev_day_ck,
            )

            ts["llm_calls"] += 1
            raw_response = _call_llm(provider, system_prompt, user_prompt, timeout=30.0)
            if raw_response:
                ts["llm_ok"] += 1
            parsed = parse_day_allocation(raw_response, len(day_events)) if raw_response else None

            day_log = {
                "day_idx": day_idx,
                "date": day_date,
                "n_events": len(day_events),
                "bankroll_before": round(bankroll, 2),
                "bankroll_after": round(bankroll, 2),
                "day_strategy": "",
                "cash_held_pct": 1.0,
                "cash_rationale": "no LLM response" if not raw_response else "unparseable response",
                "allocations": [],  # resolved outcomes
                "raw_preview": (raw_response or "")[:400],
            }

            # Mech D — stash coalition proposal even if allocations are empty
            if parsed and parsed.get("coalition_proposal"):
                day_proposals[tid] = parsed["coalition_proposal"]

            if parsed and parsed.get("allocations"):
                day_log["day_strategy"] = parsed["day_strategy"]
                day_log["cash_held_pct"] = parsed["cash_held_pct"]
                day_log["cash_rationale"] = parsed["cash_rationale"]

                starting_bankroll = bankroll
                for alloc in parsed["allocations"]:
                    eidx = alloc["event_idx"] - 1  # 1-indexed in prompt
                    if eidx < 0 or eidx >= len(day_events):
                        continue
                    event = day_events[eidx]
                    direction = alloc["direction"]

                    stake = round(starting_bankroll * alloc["pct"], 2)
                    if stake < 0.50:
                        continue

                    won, pnl_pct = resolve_political_trade(direction, event["excess_return"])
                    profit = round(stake * pnl_pct, 2)
                    ts["bankroll"] += profit
                    if won:
                        ts["wins"] += 1
                    else:
                        ts["losses"] += 1
                    ts["total_bets"] += 1
                    ts["bankroll"] = round(ts["bankroll"], 2)

                    day_log["allocations"].append({
                        "event_idx": alloc["event_idx"],
                        "ticker": alloc["ticker"],
                        "direction": direction,
                        "event_type": event.get("event_type", ""),
                        "agency": event.get("agency", ""),
                        "thesis": alloc["thesis"],
                        "pct": round(alloc["pct"], 4),
                        "stake": stake,
                        "confidence": alloc["confidence"],
                        "excess_return": event["excess_return"],  # visible post-resolution
                        "pnl_pct": round(pnl_pct, 4),
                        "won": won,
                        "profit": profit,
                    })
                    # Mech D — record actual (event_idx, direction) pairs
                    day_actual_bets.setdefault(tid, set()).add((alloc["event_idx"], direction))
            else:
                ts["passes"] += 1  # full-cash day

            # Track recent decisions for next-day prompt
            n_bets = len(day_log["allocations"])
            n_wins = sum(1 for a in day_log["allocations"] if a["won"])
            day_pnl = ts["bankroll"] - bankroll
            summary = f"{n_bets} trades, {n_wins}W, pnl {day_pnl:+.2f}"
            ts["recent_decisions"] = (ts.get("recent_decisions", []) + [{
                "date": day_date, "summary": summary,
            }])[-5:]
            ts["days_traded"] += 1
            ts["bankroll"] = round(ts["bankroll"], 2)
            ts["history"].append(ts["bankroll"])
            ts["best_bankroll"] = max(ts["best_bankroll"], ts["bankroll"])
            if ts["best_bankroll"] > 0:
                dd = (ts["best_bankroll"] - ts["bankroll"]) / ts["best_bankroll"]
                ts["max_drawdown"] = max(ts["max_drawdown"], dd)

            day_log["bankroll_after"] = round(ts["bankroll"], 2)
            _agent_logs[tid].append(day_log)
            if len(_agent_logs[tid]) > 200:
                _agent_logs[tid] = _agent_logs[tid][-200:]

            day_summary_lines.append(f"  {cfg['name'][:16]:<16} ${ts['bankroll']:>7.2f} ({n_bets} trades, {n_wins}W, {day_log['cash_held_pct']:.0%} cash)")

        log_lines.extend(day_summary_lines)

        # Axelrod Mech D — resolve coalitions for today
        day_pact_events: List[dict] = []
        for tid, prop in day_proposals.items():
            peer = prop.get("peer")
            eidx = prop.get("event_idx")
            direction = prop.get("direction")
            key = (eidx, direction)
            self_executed = key in day_actual_bets.get(tid, set())
            peer_executed = peer in day_actual_bets and key in day_actual_bets[peer]
            if self_executed and peer_executed:
                _reputation[tid]["pact_honored"] += 1
                day_pact_events.append({
                    "day": day_date, "proposer": tid, "peer": peer,
                    "event_idx": eidx, "direction": direction, "status": "honored",
                })
                _cooperation_pacts[f"{tid}|{peer}|{day_date}"] = {
                    "event_idx": eidx, "direction": direction, "honored": True,
                }
            elif not self_executed:
                _reputation[tid]["pact_broken"] += 1
                day_pact_events.append({
                    "day": day_date, "proposer": tid, "peer": peer,
                    "event_idx": eidx, "direction": direction, "status": "broken",
                })

        # Axelrod Mechanism A: build COMMON_KNOWLEDGE[D] from today's resolved trades
        prev_day_ck = build_common_knowledge_block(
            day_date, state, dict(_agent_logs),
            reputation=dict(_reputation), pact_events=day_pact_events,
        )
        _common_knowledge[day_date] = prev_day_ck

        # Axelrod Mechanism C: write day-N post-mortem log BEFORE Mech B reassigns
        write_axelrod_log(day_idx, day_date, state, dict(_agent_logs), dict(_sacrificial_assignments))

        # Axelrod Mechanism B: compute sacrificial + challenge assignments for NEXT day
        _sacrificial_assignments.clear()
        _sacrificial_assignments.update(
            assign_sacrificial_archetypes(day_date, state, dict(_agent_logs))
        )
        _challenge_assignments.clear()
        _challenge_assignments.update(
            assign_challenge_tiers(state, _sacrificial_assignments)
        )

        # Update live state
        with _state_lock:
            _experiment_state = {
                "days_processed": day_idx + 1,
                "days_total": n_days,
                "events_processed": sum(len(events_by_date[d]) for d in dates_sorted[:day_idx + 1]),
                "events_total": n_events,
                "completed": False,
                "design": "day-bucket-v3-political",
                "agents": {tid: {k: v for k, v in ts.items() if k not in ("history", "recent_decisions")}
                           for tid, ts in state.items()},
                "updated": datetime.now(timezone.utc).isoformat(),
                "last_ck_block": prev_day_ck,  # Axelrod Mech A: persist for resume
            }
        if (day_idx + 1) % 5 == 0 or day_idx == n_days - 1:
            _save_state_to_disk(_experiment_state)
            _save_logs_to_disk()

        if (day_idx + 1) % 1 == 0:  # Yield every day
            elapsed = time.time() - start_time
            days_done = day_idx + 1
            rate = days_done / (elapsed / 60) if elapsed > 0 else 0
            eta_min = (n_days - days_done) / rate if rate > 0 else 0

            progress(days_done / n_days,
                     desc=f"Day {days_done}/{n_days} | {rate:.2f} days/min | ETA {eta_min:.0f}min")

            # Build leaderboard
            lb_data = []
            for tid, ts in sorted(state.items(), key=lambda x: -x[1]["bankroll"]):
                cfg = TRADERS[tid]
                roi = ((ts["bankroll"] - 100.0) / 100.0) * 100
                win_rate = ts["wins"] / max(1, ts["total_bets"]) * 100
                llm_rate = ts["llm_ok"] / max(1, ts["llm_calls"]) * 100
                lb_data.append([
                    cfg["name"],
                    cfg["provider"].split(":")[-1][:20],
                    f"${ts['bankroll']:.2f}",
                    f"{roi:+.1f}%",
                    ts["total_bets"],
                    f"{win_rate:.0f}%",
                    ts["passes"],
                    f"{llm_rate:.0f}%",
                    f"{ts['max_drawdown']:.1%}",
                ])

            # Build chart
            events_done = sum(len(events_by_date[d]) for d in dates_sorted[:day_idx + 1])
            fig = make_bankroll_chart(state, events_done)

            # Show recent unique errors
            err_summary = ""
            if _llm_errors:
                unique_errs = list(set(_llm_errors[-20:]))[:5]
                err_summary = " | ERRORS: " + "; ".join(unique_errs)

            status = (
                f"Day {days_done}/{n_days} ({events_done}/{n_events} events) | "
                f"LLM calls: {_llm_calls} (fail: {_llm_failures}) | "
                f"Rate: {rate:.2f} d/min | ETA: {eta_min:.0f}min | "
                f"Elapsed: {elapsed/60:.1f}min"
                f"{err_summary}"
            )

            log_text = "\n".join(log_lines[-30:])

            yield (status, lb_data, fig, log_text)

    # ── FINAL RESULTS ────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    log_lines.append("\n" + "=" * 50)
    log_lines.append("FINAL RESULTS")
    log_lines.append("=" * 50)

    # Sort by bankroll
    final_ranking = sorted(state.items(), key=lambda x: -x[1]["bankroll"])
    for rank, (tid, ts) in enumerate(final_ranking, 1):
        cfg = TRADERS[tid]
        roi = ((ts["bankroll"] - 100.0) / 100.0) * 100
        log_lines.append(
            f"  #{rank} {cfg['name']}: ${ts['bankroll']:.2f} ({roi:+.1f}% ROI) "
            f"| {ts['total_bets']} trades | {ts['wins']}W-{ts['losses']}L | "
            f"DD: {ts['max_drawdown']:.1%} | LLM: {ts['llm_ok']}/{ts['llm_calls']}"
        )

    log_lines.append(f"\nTotal LLM calls: {_llm_calls} | Failures: {_llm_failures}")
    log_lines.append(f"Time: {elapsed/60:.1f} min ({elapsed/3600:.1f} hours)")

    # Save results
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": "political-2026-03-12-to-2026-03-26",
        "design": "day-bucket-v3-political",
        "events_processed": n_events,
        "days_processed": n_days,
        "leverage": LEVERAGE,
        "llm_calls": _llm_calls,
        "llm_failures": _llm_failures,
        "elapsed_seconds": round(elapsed, 1),
        "leaderboard": [],
    }
    for rank, (tid, ts) in enumerate(final_ranking, 1):
        cfg = TRADERS[tid]
        results["leaderboard"].append({
            "rank": rank,
            "trader_id": tid,
            "name": cfg["name"],
            "provider": cfg["provider"],
            "personality": cfg["personality"],
            "bankroll": round(ts["bankroll"], 2),
            "roi_pct": round(((ts["bankroll"] - 100.0) / 100.0) * 100, 2),
            "total_bets": ts["total_bets"],
            "wins": ts["wins"],
            "losses": ts["losses"],
            "passes": ts["passes"],
            "win_rate": round(ts["wins"] / max(1, ts["total_bets"]) * 100, 1),
            "max_drawdown": round(ts["max_drawdown"], 4),
            "llm_calls": ts["llm_calls"],
            "llm_success": ts["llm_ok"],
        })

    results_path = Path(__file__).parent / "data" / "experiment-results.json"
    try:
        results_path.write_text(json.dumps(results, indent=2))
    except Exception:
        pass

    lb_data = []
    for rank, (tid, ts) in enumerate(final_ranking, 1):
        cfg = TRADERS[tid]
        roi = ((ts["bankroll"] - 100.0) / 100.0) * 100
        win_rate = ts["wins"] / max(1, ts["total_bets"]) * 100
        llm_rate = ts["llm_ok"] / max(1, ts["llm_calls"]) * 100
        lb_data.append([
            cfg["name"],
            cfg["provider"].split(":")[-1][:20],
            f"${ts['bankroll']:.2f}",
            f"{roi:+.1f}%",
            ts["total_bets"],
            f"{win_rate:.0f}%",
            ts["passes"],
            f"{llm_rate:.0f}%",
            f"{ts['max_drawdown']:.1%}",
        ])

    fig = make_bankroll_chart(state, n_events)
    stopped = _stop_event.is_set()
    winner = TRADERS[final_ranking[0][0]]['name']
    winner_bank = final_ranking[0][1]['bankroll']
    days_done = day_idx + 1 if 'day_idx' in dir() else n_days
    status = f"{'STOPPED' if stopped else 'COMPLETE'} | {days_done}/{n_days} days | {elapsed/60:.1f}min | Winner: {winner} ${winner_bank:.2f}"
    log_text = "\n".join(log_lines[-50:])

    with _state_lock:
        _experiment_state = {
            "days_processed": days_done,
            "days_total": n_days,
            "events_total": n_events,
            "completed": not stopped,
            "stopped": stopped,
            "design": "day-bucket-v3-political",
            "agents": {tid: {k: v for k, v in ts.items() if k not in ("history", "recent_decisions")}
                       for tid, ts in state.items()},
            "updated": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(elapsed, 1),
        }
        _save_state_to_disk(_experiment_state)
        _save_logs_to_disk()
    _experiment_running = False

    yield (status, lb_data, fig, log_text)


def make_bankroll_chart(state: Dict, events_done: int) -> plt.Figure:
    """Create bankroll evolution chart."""
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor("#0a0a0a")
    ax.set_facecolor("#0a0a0a")

    colors = [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8",
        "#F7DC6F", "#BB8FCE", "#85C1E9", "#82E0AA", "#F0B27A",
    ]

    for i, (tid, ts) in enumerate(TRADERS.items()):
        hist = state[tid]["history"]
        if len(hist) > 1:
            # Subsample for performance
            step = max(1, len(hist) // 500)
            x = list(range(0, len(hist), step))
            y = [hist[j] for j in x]
            ax.plot(x, y, color=colors[i % len(colors)],
                    label=f"{ts['name']} ${state[tid]['bankroll']:.0f}",
                    linewidth=1.2, alpha=0.85)

    ax.axhline(y=100, color="#444", linestyle="--", alpha=0.5, label="Start ($100)")
    ax.set_xlabel("Agent-event steps", color="#aaa", fontsize=10)
    ax.set_ylabel("Bankroll ($)", color="#aaa", fontsize=10)
    ax.set_title(f"Nomos42 Political LLM Trading Floor — Bankroll Evolution ({events_done} events)",
                 color="#eee", fontsize=12, fontweight="bold")
    ax.legend(loc="upper left", fontsize=7, ncol=2,
              facecolor="#1a1a1a", edgecolor="#333", labelcolor="#ccc")
    ax.tick_params(colors="#888")
    ax.spines["bottom"].set_color("#333")
    ax.spines["left"].set_color("#333")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, alpha=0.15, color="#444")

    plt.tight_layout()
    return fig


# ── GRADIO UI ────────────────────────────────────────────────────────────────

LEADERBOARD_HEADERS = [
    "Agent", "Model", "Bankroll", "ROI", "Trades",
    "Win%", "Passes", "LLM%", "Max DD",
]

with gr.Blocks(
    title="Nomos42 Political LLM Trading Floor",
    theme=gr.themes.Base(
        primary_hue="purple",
        neutral_hue="gray",
    ),
    css="""
    .gradio-container { max-width: 1200px !important; }
    .status-bar { font-family: monospace; font-size: 14px; }
    """
) as demo:
    gr.Markdown("""
# Nomos42 Political LLM Trading Floor
### 10 AI agents trade sector ETFs on political signals — real LLM reasoning

Each agent is a **real LLM** (Cerebras, Gemini, Mistral) that receives
daily **political events** (insider trades, Fed rules, executive orders),
**sector trends** (30d baseline per sector), and **22 SOTA strategies** —
then **reasons** about whether to go long or short on affected sector ETFs.

After ~14 days of 2026 political data, we see which LLM backbone, personality,
and political-signal strategy actually generates alpha.

| Agent | Model | Provider | Personality | Risk |
|-------|-------|----------|-------------|------|
| Qwen Quant 235B | Qwen 3 235B | Cerebras | Regulatory-delta quant | 0.55 |
| Qwen Arb 235B | Qwen 3 235B | Cerebras | Cross-sector arbitrage | 0.65 |
| Llama Contrarian | Llama 3.1 8B | Cerebras | Consensus-fade | 0.55 |
| Gemini Analytical | Gemini 3 Flash | Google | Fed/SEC stats-first | 0.55 |
| Gemini Tactical | Gemini 3 Flash | Google | Calendar/schedule | 0.60 |
| Mistral Large | Mistral Large | Mistral | Ensemble meta-allocator | 0.50 |
| Mistral Medium | Mistral Medium | Mistral | Portfolio diversification | 0.45 |
| Mistral Small | Mistral Small | Mistral | Cash when no conviction | 0.35 |
| Mistral Nemo | Mistral Nemo | Mistral | Exec-order momentum | 0.70 |
| Ministral 8B | Ministral 8B | Mistral | Game-theory sizing | 0.35 |
    """)

    with gr.Row():
        start_btn = gr.Button("Start / Resume Experiment", variant="primary", scale=3)
        stop_btn = gr.Button("Stop", variant="stop", scale=1)
        status_box = gr.Textbox(label="Status", interactive=False, scale=6, elem_classes=["status-bar"])

    with gr.Row():
        leaderboard = gr.Dataframe(
            headers=LEADERBOARD_HEADERS,
            label="Live Leaderboard (sorted by bankroll)",
            interactive=False,
            wrap=True,
        )

    with gr.Row():
        chart = gr.Plot(label="Bankroll Evolution")

    with gr.Row():
        log_box = gr.Textbox(label="Event Log (last 30 entries)", lines=15, interactive=False,
                             show_copy_button=True)

    def stop_experiment():
        _stop_event.set()
        return "STOPPING... (will finish current event day)"

    start_btn.click(
        fn=run_experiment,
        outputs=[status_box, leaderboard, chart, log_box],
    )
    stop_btn.click(
        fn=stop_experiment,
        outputs=[status_box],
    )


# ── FASTAPI CONTROL API ────────────────────────────────────────────────────
# Mounted alongside Gradio for programmatic control (councils, GH Actions, CLI)

api = FastAPI()

@api.get("/api/status")
async def api_status():
    """Current experiment status — for councils, monitoring, GH Actions."""
    with _state_lock:
        state = dict(_experiment_state) if _experiment_state else {}
    state["running"] = _experiment_running
    state["stopped"] = _stop_event.is_set()
    state["llm_calls"] = _llm_calls
    state["llm_failures"] = _llm_failures
    state["gateway_url"] = GATEWAY_URL or None
    # True iff at least one successful gateway round-trip this session
    state["gateway_routed"] = bool(_gateway_routed)
    state["gateway_enabled"] = bool(_GATEWAY_URL)
    state["gateway_call_count"] = _gateway_routed
    state["direct_fallback_count"] = _gateway_fallback
    # Back-compat (deprecated, keep for a release)
    state["gateway_routed_count"] = _gateway_routed
    state["gateway_fallback_count"] = _gateway_fallback
    # Axelrod Mech B/D — sacrificial + cooperation exposure
    state["sacrificial_assignments"] = dict(_sacrificial_assignments)
    state["reputation"] = {tid: dict(r) for tid, r in _reputation.items()}
    state["cooperation_pacts_count"] = len(_cooperation_pacts)
    state["axelrod_canon_active"] = True
    state["axelrod_library_active"] = _AXELROD_OK
    state["axelrod_strategies"] = dict(AXELROD_STRATEGIES)
    return JSONResponse(state)

@api.post("/api/run")
async def api_run(request: Request):
    """Trigger experiment start (same as clicking the button).
    For GH Actions / council triggers. Non-blocking — returns immediately."""
    _stop_event.clear()
    if _experiment_running:
        return JSONResponse({"status": "resumed", "events_processed": _experiment_state.get("events_processed", 0), "message": "Stop flag cleared, experiment continues."})
    import threading
    def _bg():
        try:
            for _ in run_experiment():
                pass
        except Exception as e:
            print(f"[api_run bg] {e}")
    threading.Thread(target=_bg, daemon=True, name="api_run_bg").start()
    return JSONResponse({"status": "started", "message": "Experiment launched in background thread."})

@api.post("/api/stop")
async def api_stop():
    """Graceful stop — finishes current event day then saves state."""
    _stop_event.set()
    return JSONResponse({"status": "stopping", "running": _experiment_running})

@api.post("/api/reset")
async def api_reset():
    """Reset experiment state (delete saved state)."""
    if _experiment_running:
        return JSONResponse({"status": "error", "message": "Cannot reset while running. Stop first."}, status_code=409)
    global _experiment_state, _agent_logs
    _experiment_state = {}
    _agent_logs = defaultdict(list)
    try:
        STATE_PATH.unlink(missing_ok=True)
        LOGS_PATH.unlink(missing_ok=True)
    except Exception:
        pass
    return JSONResponse({"status": "reset", "message": "State cleared. Next run starts fresh."})

@api.post("/api/mutate")
async def api_mutate(request: Request):
    """Mutate agent parameters mid-experiment.
    Body: {"agent": "mistral-large", "risk_tolerance": 0.8, "personality": "aggressive"}"""
    body = await request.json()
    agent_id = body.get("agent")
    if agent_id not in TRADERS:
        return JSONResponse({"status": "error", "message": f"Unknown agent: {agent_id}"}, status_code=400)
    changed = []
    if "risk_tolerance" in body:
        TRADERS[agent_id]["risk_tolerance"] = float(body["risk_tolerance"])
        changed.append(f"risk_tolerance={body['risk_tolerance']}")
    if "personality" in body:
        TRADERS[agent_id]["personality"] = body["personality"]
        changed.append(f"personality={body['personality']}")
    return JSONResponse({"status": "mutated", "agent": agent_id, "changes": changed})

@api.get("/api/logs")
async def api_logs(agent: str = None, limit: int = 50):
    """Per-agent decision log. ?agent=mistral-large&limit=20"""
    if agent:
        logs = list(_agent_logs.get(agent, []))[-limit:]
        return JSONResponse({"agent": agent, "count": len(logs), "logs": logs})
    # All agents summary
    summary = {tid: len(logs) for tid, logs in _agent_logs.items()}
    return JSONResponse({"agents": summary, "total_entries": sum(summary.values())})

@api.get("/api/day-decisions")
async def api_day_decisions(date: str = None, agent: str = None, limit: int = 200):
    """Day-level decisions for council analysis.

    ?date=2026-03-15 — all agents' decisions for that day
    ?agent=qwen-quant — all days for one agent
    (no params) — summary by day with total allocations
    """
    out = {}
    if date:
        for tid, logs in _agent_logs.items():
            day_logs = [l for l in logs if l.get("date") == date]
            if day_logs:
                out[tid] = day_logs[0]  # one entry per agent per day
        return JSONResponse({"date": date, "agents": out, "n_agents": len(out)})
    if agent:
        logs = list(_agent_logs.get(agent, []))[-limit:]
        return JSONResponse({"agent": agent, "count": len(logs), "days": logs})
    # Summary: list dates with count of agents that traded
    by_date = {}
    for tid, logs in _agent_logs.items():
        for l in logs:
            d = l.get("date")
            if not d:
                continue
            if d not in by_date:
                by_date[d] = {"date": d, "agents": 0, "total_allocations": 0, "total_cash_pct": 0.0}
            by_date[d]["agents"] += 1
            by_date[d]["total_allocations"] += len(l.get("allocations", []))
            by_date[d]["total_cash_pct"] += l.get("cash_held_pct", 0.0)
    days = sorted(by_date.values(), key=lambda x: x["date"])
    for d in days:
        d["avg_cash_pct"] = round(d["total_cash_pct"] / max(1, d["agents"]), 3)
    return JSONResponse({"total_days": len(days), "days": days[-limit:]})


@api.get("/api/leaderboard")
async def api_leaderboard():
    """Current leaderboard as JSON."""
    with _state_lock:
        agents = _experiment_state.get("agents", {})
    if not agents:
        return JSONResponse({"status": "no_data", "message": "No experiment data yet"})
    lb = []
    for tid, ts in sorted(agents.items(), key=lambda x: -x[1].get("bankroll", 0)):
        cfg = TRADERS.get(tid, {})
        bankroll = ts.get("bankroll", 100)
        roi = ((bankroll - 100) / 100) * 100
        lb.append({
            "trader_id": tid,
            "name": cfg.get("name", tid),
            "provider": cfg.get("provider", "?"),
            "bankroll": round(bankroll, 2),
            "roi_pct": round(roi, 2),
            "total_bets": ts.get("total_bets", 0),
            "wins": ts.get("wins", 0),
            "losses": ts.get("losses", 0),
        })
    return JSONResponse({"leaderboard": lb, "events_processed": _experiment_state.get("events_processed", 0)})

# Mount FastAPI alongside Gradio
app = gr.mount_gradio_app(api, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
