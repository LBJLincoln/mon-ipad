"""
Nomos42 Real LLM Trading Floor — HuggingFace Spaces
====================================================
10 AI agents (real LLM API calls) compete on 1257 NBA games (2025-26 season).
Each agent receives full game context (odds, standings, form, track record)
and REASONS about what to bet. NO hash simulation. Every decision is a real LLM call.

Providers: Cerebras (5 models), Google Gemini, OpenRouter (2), Cohere, HuggingFace
Runtime: ~4-6 hours for full season. Live visualization throughout.

Architecture follows:
  - TradingAgents (arXiv 2412.20138): structured agent reasoning
  - Prediction Arena (arXiv 2604.07355): 1-bet-per-agent validation
  - DMAD (Diverse Multi-Agent Debate): structurally different data views
"""

import gradio as gr
import json
import os
import csv
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
print("NOMOS42 REAL LLM TRADING FLOOR — STARTUP")
print("=" * 60)
for k in ["CEREBRAS_API_KEY", "GOOGLE_API_KEY", "GOOGLE_API_KEY_2",
          "OPENROUTER_KEY_ORCHESTRATOR", "OPENROUTER_KEY_PME", "OPENROUTER_KEY_BARTOLI"]:
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
STATE_PATH = Path("/tmp/tf-state.json")   # Persists across restarts on HF Spaces
LOGS_PATH = Path("/tmp/tf-agent-logs.json")
AXELROD_LOG_DIR = Path("/tmp/axelrod-log")  # Axelrod Mech C: per-day post-mortem dataset

# Axelrod Mech B — archetype pool for sacrificial role reallocation
AXELROD_ARCHETYPES = [
    "pure_momentum", "mean_reversion", "news_event_driven",
    "home_underdog_specialist", "road_favorite_fade", "closing_line_value_only",
    "injury_arbitrage", "pace_inefficiency", "rest_differential",
    "back_to_back_fade", "revenge_narrative", "divisional_hate",
    "national_tv_effect", "pythagorean_divergence", "shot_chart_mismatch",
    "ref_bias_per_team", "sharps_follow", "sharps_fade",
    "steam_chase", "reverse_line_movement",
]

# Axelrod 1980 canon — every agent is told these results so strategies
# are grounded in the literature instead of re-deriving cooperation from scratch.
# Source: Axelrod 1980 "Effective Choice in the Prisoner's Dilemma" +
#         Axelrod & Hamilton 1981 Science + Nowak & Sigmund 1993 Pavlov +
#         Du et al. 2023 DMAD + Prediction Arena 2604.07355 (Mar 2026).
AXELROD_CANON = (
    "=== AXELROD CANON (mandatory reading) ===\n"
    "You are a trader in an iterated multi-agent society. Axelrod's 1980 tournament "
    "proved that the winning strategies share 4 properties: NICE (never defect first), "
    "RETALIATORY (punish defection immediately), FORGIVING (one-shot retaliation, then reset), "
    "CLEAR (legible so peers can reason about you).\n"
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
    "  1. You may propose a COALITION with another agent: both agents bet the SAME game_idx "
    "     on the SAME category on day D. Honored coalitions get a 'pact_honored' reputation credit.\n"
    "  2. You may EXIT a coalition any day by simply not repeating it. No hidden defection.\n"
    "  3. Your reputation field (pact_honored / pact_broken counters) is visible to peers in "
    "     COMMON_KNOWLEDGE the next day. Pavlov-style opponents will track your reputation.\n"
    "  4. Coalitions do NOT change stake math — only reputation. Edge must still justify the bet.\n"
    "=== END AXELROD CANON ===\n"
)

# Axelrod Mech D — cooperation ledger
# _cooperation_pacts[(tid_a, tid_b, day_date)] = {"game_idx": int, "category": str, "honored": bool}
_cooperation_pacts: Dict[str, dict] = {}
# _reputation[tid] = {"pact_honored": int, "pact_broken": int}
_reputation: Dict[str, Dict[str, int]] = defaultdict(lambda: {"pact_honored": 0, "pact_broken": 0})
GATEWAY_URL = os.environ.get("GATEWAY_URL", "").rstrip("/")

# DMAD (ICLR 2025, OpenReview t6QHYUOQL7) — structurally distinct reasoning templates per agent.
# Each trader MUST reason via its own template; prevents groupthink across Qwen/Llama/Gemini/Mistral.
REASONING_TEMPLATES = {
    "qwen-quant":        "REASONING TEMPLATE (DMAD): EXPECTED-UTILITY MAXIMIZATION. Compute E[V] = (p_win × win_amount) − ((1−p_win) × stake). Bet iff E[V]/stake > 0.05.",
    "qwen-arb":          "REASONING TEMPLATE (DMAD): CROSS-MARKET ARBITRAGE. Scan line discrepancies vs implied prob > 2σ. If no arb signal, PASS.",
    "llama-contra":      "REASONING TEMPLATE (DMAD): CONTRARIAN INVERSION. Start from public prior, argue the OPPOSITE with 3 reasons. Bet only if inversion survives.",
    "gemini-anl":        "REASONING TEMPLATE (DMAD): FIRST-PRINCIPLES DECOMPOSITION. List the 3 most decisive factors, weight each ∈[0,1], multiply to get signal.",
    "gemini-tact":       "REASONING TEMPLATE (DMAD): TACTICAL TIMING. Focus on line movement + steam. No sharp action → PASS.",
    "mistral-large":     "REASONING TEMPLATE (DMAD): SCENARIO MAJORITY. Enumerate 5 scenarios, assign P to each, bet iff ≥3 align.",
    "mistral-medium":    "REASONING TEMPLATE (DMAD): DIVERSIFIED PORTFOLIO. Split across 2-3 uncorrelated games. Never all-in one game.",
    "mistral-small":     "REASONING TEMPLATE (DMAD): RISK-AVERSE STRESS TEST. Assume worst-case; bet only if still +EV in worst case.",
    "mistral-nemo":      "REASONING TEMPLATE (DMAD): MOMENTUM CHASE. Bet hardest on last-5 form streaks ≥ 4-1.",
    "mistral-ministral": "REASONING TEMPLATE (DMAD): THEORETICAL MODEL. Mental logistic regression from 3 coefficients → compute p.",
    "nemotron-120b":     "REASONING TEMPLATE (DMAD): EXPLICIT 7-STEP CoT. context → hypothesis → evidence → counter → weight → conclusion → bet.",
    "gemma4-selfhost":   "REASONING TEMPLATE (DMAD): 4-RULE CHECKLIST. (1) edge > 0.05 (2) bankroll > $30 (3) not same game as yesterday (4) category in top-3. Bet iff ALL pass.",
    "qwen25-micro":      "REASONING TEMPLATE (DMAD): PATTERN-MATCH. Find the single most similar historical game in COMMON_KNOWLEDGE, mimic bet logic.",
    "llama32-micro":     "REASONING TEMPLATE (DMAD): ANCHOR & ADJUST. Anchor at implied_prob, adjust ±10% on the 1 strongest signal, bet iff edge > 0.04.",
    "gemma2-micro":      "REASONING TEMPLATE (DMAD): MINIMALIST. Pick the SINGLE highest-conviction bet of the day or PASS. Never > 1 bet.",
}

def get_stackelberg_leader(state: dict) -> Optional[str]:
    """Stackelberg (arXiv 2507.09407): yesterday's top-bankroll trader is today's leader."""
    active = [(tid, st.get("bankroll", 0)) for tid, st in state.items()
              if isinstance(st, dict) and tid in TRADERS and st.get("bankroll", 0) > 5.0]
    if not active:
        return None
    return max(active, key=lambda x: x[1])[0]

def build_stackelberg_role_block(tid: str, leader_tid: Optional[str]) -> str:
    """Role suffix appended to system_prompt: LEADER commits first, FOLLOWERS best-respond."""
    if not leader_tid:
        return ""
    if tid == leader_tid:
        return ("\n=== STACKELBERG ROLE TODAY: LEADER ===\n"
                "You are today's leader (highest bankroll from prior day). Commit your bets FIRST "
                "with full public reasoning. Your decisions enter COMMON_KNOWLEDGE for followers.\n")
    return (f"\n=== STACKELBERG ROLE TODAY: FOLLOWER (leader = {leader_tid}) ===\n"
            "After the leader's public commitments (in COMMON_KNOWLEDGE), you must either:\n"
            "  (a) AGREE — align with leader's logic where the same game/category applies, OR\n"
            "  (b) DEVIATE — state one explicit reason why you best-respond differently.\n"
            "Best-respond to the leader's move; do not blindly follow.\n")

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

# ── TEAM MAP ────────────────────────────────────────────────────────────────
TEAM_MAP = {
    "Los Angeles Lakers": "LAL", "Los Angeles Clippers": "LAC",
    "Golden State Warriors": "GSW", "Boston Celtics": "BOS",
    "Oklahoma City Thunder": "OKC", "Houston Rockets": "HOU",
    "Cleveland Cavaliers": "CLE", "New York Knicks": "NYK",
    "Milwaukee Bucks": "MIL", "Denver Nuggets": "DEN",
    "Phoenix Suns": "PHX", "Dallas Mavericks": "DAL",
    "Memphis Grizzlies": "MEM", "Minnesota Timberwolves": "MIN",
    "Sacramento Kings": "SAC", "Indiana Pacers": "IND",
    "Miami Heat": "MIA", "Philadelphia 76ers": "PHI",
    "Orlando Magic": "ORL", "Atlanta Hawks": "ATL",
    "Chicago Bulls": "CHI", "Toronto Raptors": "TOR",
    "Brooklyn Nets": "BKN", "San Antonio Spurs": "SAS",
    "Detroit Pistons": "DET", "Charlotte Hornets": "CHA",
    "Portland Trail Blazers": "POR", "New Orleans Pelicans": "NOP",
    "Utah Jazz": "UTA", "Washington Wizards": "WAS",
}

STAT_KEYS = ["fg_pct", "fg3_pct", "ft_pct", "reb", "ast", "tov", "stl", "blk", "plus_minus"]

# ── PROVIDER CONFIGS (v3 — day-bucket design, 3 real providers, 2026-04-14) ──
# Verified by live experiment audit + /api/probe on 2026-04-14:
#   Cerebras qwen-3-235b + llama3.1-8b: 100% success, 30 RPM
#   Google Gemini 3 Flash (key 2):      100% success, 14 RPM
#   Mistral (la Plateforme free tier):  large/medium/small/nemo/ministral all OK
# Dead: OpenRouter (6 models, quota), Gemini key 1, Groq keys (org restricted).
# With day-bucket design: 1 call/agent/day × 180 days × 10 agents = 1800 calls
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
    # Google Gemini 3 Flash (key 2) — thinking model, needs big token budget +
    # thinkingBudget=0 or all tokens get eaten by thought traces.
    "google:gemini-3-flash": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent",
        "model": "gemini-3-flash-preview",
        "key_env": "GOOGLE_API_KEY_2",
        "max_tokens": 4096,
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
    # OpenRouter Nemotron 120B free — only free-tier model that reliably responds
    # (verified 2026-04-15: qwen3-80b / glm-4.5-air / llama-3.3-70b all 429 across 3 keys).
    "openrouter:nemotron-120b": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "nvidia/nemotron-3-super-120b-a12b:free",
        "key_env": "OPENROUTER_KEY_BARTOLI",
        "max_tokens": 1500,
        "rpm": 12,
    },
    # Self-hosted CPU LLM on HF Space Nomos42/nomos-cpu-gemma4 — no auth, no quota.
    # Space requested gemma-4-E4B-it-GGUF but that file 404s on HF, so falls back to
    # bartowski/Phi-3.5-mini-instruct-GGUF (Q4_K_M). OK for tactical 1-shot bets.
    # Endpoint is NOT OpenAI-compat: POST /api/decide {system, user, max_tokens} -> {text}.
    "selfhost:cpu-gemma4": {
        "url": "https://nomos42-nomos-cpu-gemma4.hf.space/api/decide",
        "model": "phi-3.5-mini-instruct-q4_k_m",
        "key_env": "SELFHOST_NOOP",  # sentinel — no auth needed
        "max_tokens": 800,
        "rpm": 6,  # slow CPU, ~5-12s/call
    },
    # NEW 2026-04-15 — 3 OpenAI-compat quantized CPU Spaces on Nomos42 account
    # (deployed by bg-agent a9505f7c1f660768c). Routed via /chat/completions.
    "selfhost:qwen2.5-0.5b": {
        "url": "https://nomos42-qwen25-05b-cpu.hf.space/chat/completions",
        "model": "qwen2.5-0.5b-instruct",
        "key_env": "SELFHOST_NOOP",
        "max_tokens": 800,
        "rpm": 12,  # fastest of the three (~3-5s warm)
    },
    "selfhost:llama-3.2-1b": {
        "url": "https://nomos42-llama32-1b-cpu.hf.space/chat/completions",
        "model": "llama-3.2-1b-instruct",
        "key_env": "SELFHOST_NOOP",
        "max_tokens": 800,
        "rpm": 10,
    },
    "selfhost:gemma-2-2b": {
        "url": "https://nomos42-gemma2-2b-cpu.hf.space/chat/completions",
        "model": "gemma-2-2b-it",
        "key_env": "SELFHOST_NOOP",
        "max_tokens": 800,
        "rpm": 4,  # slowest (~2 min cold, ~30s warm)
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
    # NEW 2026-04-15 — +1 NVIDIA Nemotron 120B (OpenRouter free, verified responsive)
    "nemotron-120b":    {"name": "Nemotron 120B",    "provider": "openrouter:nemotron-120b","personality": "chainthought","risk_tolerance": 0.55},
    # NEW 2026-04-15 T12 — self-hosted CPU Phi-3.5 on HF Space (no quota, slow ~8s/call)
    "gemma4-selfhost":  {"name": "Gemma4 SelfHost",  "provider": "selfhost:cpu-gemma4",     "personality": "disciplined", "risk_tolerance": 0.40},
    # NEW 2026-04-15 T13/T14/T15 — 3 OpenAI-compat quantized CPU Spaces (Nomos42 account)
    "qwen25-micro":     {"name": "Qwen2.5 0.5B",     "provider": "selfhost:qwen2.5-0.5b",   "personality": "reactive",    "risk_tolerance": 0.30},
    "llama32-micro":    {"name": "Llama 3.2 1B",     "provider": "selfhost:llama-3.2-1b",   "personality": "balanced",    "risk_tolerance": 0.45},
    "gemma2-micro":     {"name": "Gemma 2 2B",       "provider": "selfhost:gemma-2-2b",     "personality": "deliberate",  "risk_tolerance": 0.40},
}

AGENT_SYSTEM_PROMPTS = {
    "mistral-large": """You are Mistral Large, an ensemble/meta-learning allocator.
APPROACH: Aggregate signals — model predictions (40%) + market implied prob (30%) + matchup analysis (30%). Deploy capital where consensus is strongest.
PREFERRED STRATEGIES: confidence_scaled, value_hunter, drawdown_adjusted
EDGE DETECTION: Meta-model across signals. Strongest when model/odds/form agree.
RISK: Moderate (0.50). Reduce exposure during losing streaks.
SPECIALTY: Consensus plays.""",

    "mistral-medium": """You are Mistral Medium, a portfolio diversification allocator.
APPROACH: Day = mini-portfolio. Spread across 3-5 game/category slices. Correlation-aware: avoid stacking same team's ML + spread + total.
PREFERRED STRATEGIES: quarter_kelly, flat_2pct, diversified_flat
EDGE DETECTION: Balanced exposure. Prefer moderate edge × many bets over one big bet.
RISK: Low-moderate (0.45). Diversification over conviction.
SPECIALTY: Portfolio construction.""",

    "mistral-small": """You are Mistral Small, a capital-preservation allocator.
APPROACH: Only deploy capital when multiple signals align. When none align, hold cash — that's a valid decision.
PREFERRED STRATEGIES: eighth_kelly, flat_1pct, drawdown_adjusted
EDGE DETECTION: Require edge >5% AND model confidence >65%. Otherwise cash.
RISK: Very low (0.35). Cash is fine. Small wins compound.
SPECIALTY: Home favorites with strong form.""",

    "mistral-nemo": """You are Mistral Nemo, an aggressive high-conviction allocator.
APPROACH: Day's best edge gets 25-40% of bankroll. Secondary bets get 10-20%. Cash only if truly no edge anywhere.
PREFERRED STRATEGIES: full_kelly, streak_momentum, confidence_scaled
EDGE DETECTION: Weight player matchups, rest, back-to-backs heavily. Hunt the biggest edge.
RISK: High (0.70). Big bets on strongest signals.
SPECIALTY: Player-influenced totals and moneylines.""",

    "mistral-ministral": """You are Ministral 8B, a game-theory allocator.
APPROACH: Decision under uncertainty. Use entropy / KL divergence between your prob distribution and market's to size positions.
PREFERRED STRATEGIES: eighth_kelly, flat_1pct, teaser_6pt
EDGE DETECTION: Only bet when KL divergence > threshold. Small frequent allocations.
RISK: Very low (0.35). Theoretical soundness.
SPECIALTY: Teasers crossing key numbers (3, 7).""",

    "qwen-quant": """You are Qwen Quant 235B, a pure-quant NBA betting agent.
APPROACH: Calculate implied probabilities, compare with model predictions, compute Kelly fractions. Only bet when math demands it.
PREFERRED STRATEGIES: half_kelly, ev_threshold_110, proportional_edge
EDGE DETECTION: Require EV > 1.05 AND edge > 3%. Use model confidence as probability estimate.
RISK: Moderate-low (0.55). Precision over volume. Pass if no edge.
SPECIALTY: Totals and alt-totals. Excel at predicting pace.""",

    "qwen-arb": """You are Qwen Arb 235B, an arbitrage-hunting agent.
APPROACH: Hunt pricing inefficiencies between bet categories. If ML implies 65% but spread implies 60%, mispriced.
PREFERRED STRATEGIES: confidence_scaled, proportional_edge, parlay_2leg
EDGE DETECTION: Cross-reference ML, spread, total, team totals, halves for internal consistency. Bet mispriced side.
RISK: Moderate-high (0.65). Aggressive on cross-market arbitrage.
SPECIALTY: Cross-market analysis. Correlated 2-leg parlays.""",

    "llama-contra": """You are Llama Contrarian, a public-fading allocator.
APPROACH: Markets overreact to recent form and media narratives. When public >70% on one side, look for value on the other.
PREFERRED STRATEGIES: underdog_specialist, dog_value_plus, anti_martingale
EDGE DETECTION: Target games with strong media favorites. Love underdogs getting points. Reverse line moves matter.
RISK: Moderate-high (0.55). Survive to fade another day.
SPECIALTY: Spread betting, especially taking points.""",

    "gemini-anl": """You are Gemini Analytical, a stats-first allocator.
APPROACH: Trust numbers over narratives. Cross-reference model predictions with market odds to find mispricings.
PREFERRED STRATEGIES: half_kelly, confidence_scaled, proportional_edge
EDGE DETECTION: Games where model win-prob diverges >3% from implied odds prob. Calculate EV precisely.
RISK: Moderate (0.55). Prefer 2-4 allocations per day.
SPECIALTY: Moneyline and spread. Home court advantage.""",

    "gemini-tact": """You are Gemini Tactical, a schedule/scheme allocator.
APPROACH: Weight team form (L10), head-to-head, rest advantage, travel, schedule spots (3-in-4, altitude).
PREFERRED STRATEGIES: half_kelly, home_specialist, first_half_sniper
EDGE DETECTION: Back-to-back fades. Altitude games (Denver). Rest differential >2 days.
RISK: Moderate (0.60). Disciplined execution.
SPECIALTY: First-half betting and schedule-based plays.""",

    "nemotron-120b": """You are Nemotron 120B, a chain-of-thought value hunter.
APPROACH: Rank every available category by |model_prob - implied_prob|. Size the top 1-2 mispricings using half-Kelly. Ignore noisy edges.
PREFERRED STRATEGIES: value_hunter, half_kelly, proportional_edge
EDGE DETECTION: Cross-category scan — team totals, alt spreads, halves often mispriced. Require edge >4%.
RISK: Moderate (0.55). Depth of reasoning over breadth.
SPECIALTY: Alt-markets (team totals, alt spreads, quarter lines).""",

    "gemma4-selfhost": """You are Gemma4 SelfHost, a disciplined self-hosted allocator on CPU Phi-3.5-mini.
APPROACH: Small model, small bets. Pick one high-conviction play per day. No multi-leg parlays. Prefer ML over totals.
PREFERRED STRATEGIES: flat_1pct, quarter_kelly, top_edge_only
EDGE DETECTION: Only bet when moneyline edge >5% AND confidence >65%. Otherwise pass.
RISK: Low (0.40). Capital preservation over chase.
SPECIALTY: Single-bet conviction plays. Slow-thinking CPU inference.""",

    "qwen25-micro": """You are Qwen2.5 0.5B Micro, a reactive ultra-small allocator on CPU.
APPROACH: Tiny model, single decision. React only to the strongest numerical signal of the day. One bet max, usually ML or total. No parlays, no alt lines.
PREFERRED STRATEGIES: flat_1pct, top_edge_only
EDGE DETECTION: Require edge >6% AND implied_prob alignment with model_prob. If uncertain, cash.
RISK: Very low (0.30). Preserve capital; enter only on clearest signals.
SPECIALTY: First-reaction plays on lopsided model/market disagreement.""",

    "llama32-micro": """You are Llama 3.2 1B Micro, a balanced self-hosted allocator on CPU.
APPROACH: Mid-tier small model. Balanced 1-2 bets per day across ML/spread. Respect confidence thresholds; never force a pick.
PREFERRED STRATEGIES: quarter_kelly, flat_2pct, diversified_flat
EDGE DETECTION: Edge >4% AND confidence >60%. Diversify across 1-2 games rather than concentrate.
RISK: Moderate-low (0.45). Steady compound approach.
SPECIALTY: Balanced ML+spread plays, avoid totals on CPU uncertainty.""",

    "gemma2-micro": """You are Gemma 2 2B Micro, a deliberate self-hosted allocator on CPU (slow inference).
APPROACH: Largest of the micro-agents, takes time to think. 1-2 high-quality bets per day. Prefer games with clear narrative + stat alignment.
PREFERRED STRATEGIES: half_kelly, confidence_scaled, value_hunter
EDGE DETECTION: Edge >4% AND at least 2 distinct signals (model, form, matchup) align.
RISK: Low-moderate (0.40). Depth of reasoning over speed.
SPECIALTY: Narrative+stat alignment plays. Willing to pass days with no clear conviction.""",
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
_gateway_routed = 0       # Count of calls successfully routed via gateway
_gateway_fallback = 0     # Count of calls that fell back to direct provider

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
                    "generationConfig": {
                        "maxOutputTokens": cfg["max_tokens"],
                        "temperature": 0.3,
                        "responseMimeType": "application/json",
                        "thinkingConfig": {"thinkingBudget": 0},
                    },
                }
                resp = requests.post(url, json=payload, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    cand = (data.get("candidates") or [{}])[0]
                    # Join ALL non-thought parts (Gemini 3 can split response).
                    parts = (cand.get("content") or {}).get("parts") or []
                    pieces = []
                    for p in parts:
                        if not isinstance(p, dict):
                            continue
                        if p.get("thought") is True:
                            continue
                        t = p.get("text")
                        if t:
                            pieces.append(t)
                    text = "".join(pieces)
                    if text:
                        return text
                    # Empty: log finishReason for debug
                    fr = cand.get("finishReason", "EMPTY")
                    last_error = f"Gemini finishReason={fr} parts={len(parts)}"
                    if attempt == 0:
                        time.sleep(1)
                        continue
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
                # Legacy self-hosted HF Space (T12 cpu-gemma4) — non-OpenAI shape:
                # POST /api/decide {system, user, max_tokens, temperature, json_only} -> {text, ...}
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
                        last_error = f"selfhost error: {data.get('error')[:120]}"
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
                # OpenAI-compatible (Cerebras, OpenRouter, selfhost /chat/completions)
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                if "openrouter" in provider:
                    headers["HTTP-Referer"] = "https://nomos42.ai"
                    headers["X-Title"] = "Nomos42 Trading Floor"
                payload = {
                    "model": cfg["model"],
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": cfg["max_tokens"],
                    "temperature": 0.3,
                }
                # Selfhost quantized CPUs are slow — extend timeout (gemma2 cold ~2min).
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

    # failed
    _llm_failures += 1
    if len(_llm_errors) < 100:
        _llm_errors.append(f"{provider}: {result.get('error')}")
    return None


# ── PROMPT BUILDER ──────────────────────────────────────────────────────────

def build_game_prompt(game_ctx: Dict, trader_state: Dict,
                      rosters=None, team_advanced=None, player_stats=None,
                      full_odds=None, model_preds=None, strategies=None) -> str:
    """Build comprehensive prompt with 100+ data points for the agent."""
    odds = game_ctx.get("odds", {})
    home_std = game_ctx.get("home_standings", {})
    away_std = game_ctx.get("away_standings", {})
    home_form = game_ctx.get("home_form_L10", {})
    away_form = game_ctx.get("away_form_L10", {})
    home = game_ctx.get("home", "?")
    away = game_ctx.get("away", "?")
    date = game_ctx.get("date", "?")
    game_key = f"{date}_{away}@{home}"

    ml_h = odds.get("ml_home_dec", 2.0)
    ml_a = odds.get("ml_away_dec", 2.0)
    impl_home = round(1.0 / ml_h, 3) if ml_h > 1 else 0.5
    impl_away = round(1.0 / ml_a, 3) if ml_a > 1 else 0.5

    bankroll = trader_state.get("bankroll", 100.0)
    total_bets = trader_state.get("total_bets", 0)
    wins = trader_state.get("wins", 0)
    losses = trader_state.get("losses", 0)
    roi = ((bankroll - 100.0) / 100.0) * 100 if bankroll != 100.0 else 0.0

    lines = [f"GAME: {away} @ {home} | {date}"]

    # ── STANDINGS ──
    h_w = home_std.get("w", 0); h_l = home_std.get("l", 0)
    a_w = away_std.get("w", 0); a_l = away_std.get("l", 0)
    h_wp = home_std.get("win_pct", 0); a_wp = away_std.get("win_pct", 0)
    lines.append(f"\nSTANDINGS: {home} {h_w}-{h_l} ({h_wp:.3f}) | {away} {a_w}-{a_l} ({a_wp:.3f})")

    # ── FORM ──
    h_form_str = f"{home_form.get('w','?')}-{home_form.get('l','?')}" if home_form.get("games", 0) > 0 else "N/A"
    a_form_str = f"{away_form.get('w','?')}-{away_form.get('l','?')}" if away_form.get("games", 0) > 0 else "N/A"
    lines.append(f"FORM L10: {home} {h_form_str} | {away} {a_form_str}")

    # ── ADVANCED TEAM STATS ──
    if team_advanced:
        for t, label in [(home, "HOME"), (away, "AWAY")]:
            ts = team_advanced.get(t, {})
            if ts:
                lines.append(f"{label} {t}: OffRtg={ts.get('OFF_RATING','?')} DefRtg={ts.get('DEF_RATING','?')} Net={ts.get('NET_RATING','?')} Pace={ts.get('PACE','?')} TS%={ts.get('TS_PCT','?')}")

    # ── KEY PLAYERS (Top 5 per team) ──
    if player_stats:
        lines.append("\nKEY PLAYERS:")
        for t, label in [(home, "HOME"), (away, "AWAY")]:
            ps_entry = player_stats.get(t, {})
            players = (ps_entry.get("players", ps_entry) if isinstance(ps_entry, dict) else ps_entry) or []
            if isinstance(players, list):
                players = players[:5]
            else:
                players = []
            if players:
                pstrs = []
                for p in players:
                    ppg = p.get('PPG', p.get('ppg', 0)) or 0
                    rpg = p.get('RPG', p.get('rpg', 0)) or 0
                    apg = p.get('APG', p.get('apg', 0)) or 0
                    fg = p.get('FG_PCT', p.get('fg_pct', 0)) or 0
                    fg3 = p.get('FG3_PCT', p.get('fg3_pct', 0)) or 0
                    mins = p.get('MIN', p.get('min', 0)) or 0
                    pstrs.append(f"{p.get('name','?')} {ppg:.1f}p/{rpg:.1f}r/{apg:.1f}a {fg:.0%}FG")
                lines.append(f"  {label} {t}: {' | '.join(pstrs)}")

    # ── BASE ODDS ──
    lines.append(f"\nBASE ODDS:")
    lines.append(f"  ML: {home} {ml_h:.3f} (impl {impl_home:.1%}) | {away} {ml_a:.3f} (impl {impl_away:.1%})")
    lines.append(f"  Spread: {home} {odds.get('spread_home', 'N/A')} | Total: {odds.get('total', 'N/A')}")

    # ── FULL ODDS MENU (100+ categories) ──
    fo_raw = (full_odds or {}).get(game_key, {})
    fo = fo_raw.get("categories", fo_raw) if isinstance(fo_raw, dict) else {}
    if fo and isinstance(fo, dict):
        cats = sorted(fo.keys())
        def _fmt(c):
            v = fo[c]
            if isinstance(v, dict):
                odds_v = v.get("odds", v.get("line", "?"))
                return f"{c}={odds_v}"
            return f"{c}={v}"
        alt_sp = [c for c in cats if c.startswith("alt_spread")]
        alt_tot = [c for c in cats if c.startswith("alt_total")]
        team_tots = [c for c in cats if c.startswith("team_total")]
        halves = [c for c in cats if c.startswith("h1_") or c.startswith("h2_")]
        quarters = [c for c in cats if c.startswith("q1_")]
        game_props = [c for c in cats if c.startswith("prop_")]
        n_cats = fo_raw.get("category_count", len(cats))
        lines.append(f"\nFULL ODDS ({n_cats} categories):")
        if alt_sp:
            lines.append(f"  ALT SPREADS: {', '.join(_fmt(c) for c in alt_sp[:8])}")
        if alt_tot:
            lines.append(f"  ALT TOTALS: {', '.join(_fmt(c) for c in alt_tot[:8])}")
        if team_tots:
            lines.append(f"  TEAM TOTALS: {', '.join(_fmt(c) for c in team_tots)}")
        if halves:
            lines.append(f"  HALVES: {', '.join(_fmt(c) for c in halves[:8])}")
        if quarters:
            lines.append(f"  QUARTERS: {', '.join(_fmt(c) for c in quarters)}")
        if game_props:
            lines.append(f"  GAME PROPS: {', '.join(_fmt(c) for c in game_props[:8])}")

    # ── NOMOS42 MODEL PREDICTIONS ──
    pred = (model_preds or {}).get(game_key, {})
    if pred:
        lines.append(f"\nNOMOS42 AI MODEL (Brier=0.217, {pred.get('total_agents',0)} agents):")
        lines.append(f"  ML: {pred.get('consensus_ml_direction','?')} conf={pred.get('consensus_ml_confidence',0):.1%} ({pred.get('ml_agree',0)}/{pred.get('total_agents',0)} agree)")
        lines.append(f"  Spread: {pred.get('consensus_spread_direction','?')} conf={pred.get('consensus_spread_confidence',0):.1%}")
        lines.append(f"  Total: {pred.get('consensus_total_direction','?')} conf={pred.get('consensus_total_confidence',0):.1%}")

    # ── TRACK RECORD ──
    lines.append(f"\nYOUR TRACK RECORD: ${bankroll:.2f} | {total_bets} bets | {wins}W-{losses}L | ROI {roi:+.1f}%")

    # ── STRATEGIES (abbreviated) ──
    if strategies:
        strat_list = ", ".join(strategies.keys())
        lines.append(f"\nAVAILABLE STRATEGIES ({len(strategies)}): {strat_list}")

    # ── DECISION FORMAT ──
    lines.append(f"""
AVAILABLE CATEGORIES: ml_home, ml_away, spread_home, spread_away, total_over, total_under, h1_ml_home, h1_ml_away, h1_spread, h1_total_over, h1_total_under, team_total_home_over, team_total_home_under, team_total_away_over, team_total_away_under, alt_spread_home_minus3.5, alt_spread_home_minus5.5, alt_total_over_plus3, alt_total_under_minus3, q1_ml_home, q1_ml_away, prop_both_100, prop_overtime

RESPOND WITH RAW JSON ONLY. NO ```json fences. NO preamble. NO "Let me analyze". NO thinking out loud.
FIRST CHARACTER MUST BE {{ — last character MUST be }}.

Schema:
{{"reasoning": "1 short sentence", "bets": [{{"category": "ml_home", "confidence": 0.65, "edge": 0.05, "bet_pct": 0.02, "strategy": "half_kelly"}}], "pass": false}}

Rules:
- confidence 0-1, edge must be POSITIVE and REAL (derive from model vs market — DO NOT hardcode 0.05).
- bet_pct 0.005-0.06, max 2 bets, strategy from list above.
- If no genuine edge, return {{"reasoning": "...", "bets": [], "pass": true}}.
- NEVER bet without computing edge from the provided odds and predictions.""")

    return "\n".join(lines)


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


# ── DAY-BUCKET PROMPT BUILDER (v3 design, 2026-04-14) ─────────────────────────

def _format_game_block(idx: int, game: Dict, odds: Dict, home_std: Dict,
                       away_std: Dict, home_form: Dict, away_form: Dict,
                       team_advanced: Dict, player_stats: Dict,
                       full_odds: Dict, model_preds: Dict) -> str:
    """Compact single-game block for day-level prompts."""
    home, away, date = game["home"], game["away"], game["date"]
    ml_h = odds.get("ml_home_dec", 2.0)
    ml_a = odds.get("ml_away_dec", 2.0)
    impl_h = round(1.0 / ml_h, 3) if ml_h > 1 else 0.5
    impl_a = round(1.0 / ml_a, 3) if ml_a > 1 else 0.5

    lines = [f"\n[{idx}] {away} @ {home}"]
    lines.append(f"  STAND: {home} {home_std.get('w',0)}-{home_std.get('l',0)} ({home_std.get('win_pct',0):.3f}) | {away} {away_std.get('w',0)}-{away_std.get('l',0)} ({away_std.get('win_pct',0):.3f})")
    h_form = f"{home_form.get('w','?')}-{home_form.get('l','?')}" if home_form.get("games", 0) > 0 else "N/A"
    a_form = f"{away_form.get('w','?')}-{away_form.get('l','?')}" if away_form.get("games", 0) > 0 else "N/A"
    lines.append(f"  FORM L10: {home} {h_form} | {away} {a_form}")

    if team_advanced:
        h_adv = team_advanced.get(home, {})
        a_adv = team_advanced.get(away, {})
        if h_adv or a_adv:
            lines.append(f"  ADV: {home} Off={h_adv.get('OFF_RATING','?')} Def={h_adv.get('DEF_RATING','?')} Net={h_adv.get('NET_RATING','?')} | {away} Off={a_adv.get('OFF_RATING','?')} Def={a_adv.get('DEF_RATING','?')} Net={a_adv.get('NET_RATING','?')}")

    lines.append(f"  ODDS: ML {home} {ml_h:.2f} ({impl_h:.1%}) | {away} {ml_a:.2f} ({impl_a:.1%}) | Spread {odds.get('spread_home','?')} | Total {odds.get('total','?')}")

    # Top 3 players only for day prompt (space budget)
    if player_stats:
        for t, label in [(home, "H"), (away, "A")]:
            ps_entry = player_stats.get(t, {})
            players = (ps_entry.get("players", ps_entry) if isinstance(ps_entry, dict) else ps_entry) or []
            if isinstance(players, list):
                players = players[:3]
                if players:
                    pstrs = [f"{p.get('name','?')[:15]} {p.get('PPG',p.get('ppg',0)) or 0:.0f}p" for p in players]
                    lines.append(f"  {label}: {' | '.join(pstrs)}")

    # Model prediction
    game_key = f"{date}_{away}@{home}"
    pred = (model_preds or {}).get(game_key, {})
    if pred:
        lines.append(f"  AI MODEL: ML {pred.get('consensus_ml_direction','?')} conf={pred.get('consensus_ml_confidence',0):.0%} ({pred.get('ml_agree',0)}/{pred.get('total_agents',0)})")

    # Count of full odds available
    fo_raw = (full_odds or {}).get(game_key, {})
    fo = fo_raw.get("categories", fo_raw) if isinstance(fo_raw, dict) else {}
    if fo and isinstance(fo, dict):
        lines.append(f"  FULL ODDS: {len(fo)} categories available")
    return "\n".join(lines)


def build_day_prompt(day_date: str, day_games: List[Dict], day_odds: List[Dict],
                     day_standings: List[Dict], day_forms: List[Dict],
                     trader_state: Dict, rosters=None, team_advanced=None,
                     player_stats=None, full_odds=None, model_preds=None,
                     strategies=None, recent_decisions: List[Dict] = None,
                     common_knowledge_block: Optional[str] = None) -> str:
    """Build comprehensive day-level prompt. Agent sees ALL games of the day."""
    bankroll = trader_state.get("bankroll", 100.0)
    total_allocs = trader_state.get("total_bets", 0)
    wins = trader_state.get("wins", 0)
    losses = trader_state.get("losses", 0)
    roi = ((bankroll - 100.0) / 100.0) * 100

    lines = [f"=== TRADING DAY: {day_date} | {len(day_games)} GAMES ===",
             f"",
             f"YOUR STATE: ${bankroll:.2f} | {total_allocs} total allocations | {wins}W-{losses}L | ROI {roi:+.1f}%"]

    if recent_decisions:
        lines.append("\nRECENT DAYS (last 3):")
        for d in recent_decisions[-3:]:
            lines.append(f"  {d.get('date','?')}: {d.get('summary','—')}")

    lines.append("\nGAMES (leakage-safe, standings/form computed up to but not including these games):")
    for i, g in enumerate(day_games, 1):
        idx = i - 1
        lines.append(_format_game_block(
            i, g, day_odds[idx], day_standings[idx][0], day_standings[idx][1],
            day_forms[idx][0], day_forms[idx][1],
            team_advanced, player_stats, full_odds, model_preds
        ))

    if strategies:
        lines.append(f"\nSTRATEGIES ({len(strategies)}): {', '.join(list(strategies.keys())[:12])}...")

    if common_knowledge_block:
        lines.append("\n" + common_knowledge_block)

    lines.append("""
=== YOUR TASK ===
Allocate 100% of your bankroll across today's games.
Each allocation = one bet on one game/category. Total allocations + cash_held must sum to 1.00.
Holding cash is allowed BUT you must justify it (no edge found is a valid reason).

AVAILABLE BET CATEGORIES (same as /game pricing):
  ml_home, ml_away, spread_home, spread_away, total_over, total_under,
  h1_ml_home, h1_ml_away, h1_spread, h1_total_over, h1_total_under,
  team_total_home_over, team_total_home_under, team_total_away_over, team_total_away_under,
  alt_spread_home_minus3.5, alt_spread_home_minus5.5, alt_total_over_plus3, alt_total_under_minus3,
  q1_ml_home, q1_ml_away, prop_both_100, prop_overtime

RESPOND WITH RAW JSON ONLY. No ```json fences. No preamble. First character must be {, last must be }.

Schema:
{
  "day_strategy": "1-2 sentences on today's overall approach",
  "allocations": [
    {
      "game_idx": 1,
      "game": "AWAY@HOME",
      "category": "ml_home",
      "pct": 0.15,
      "confidence": 0.65,
      "edge": 0.04,
      "strategy": "half_kelly",
      "rationale": "1 sentence: which stat/metric drove this and why it beats market price"
    }
  ],
  "cash_held_pct": 0.25,
  "cash_rationale": "1 sentence if cash > 0",
  "coalition_proposal": {
    "peer": "qwen-quant",
    "game_idx": 1,
    "category": "ml_home",
    "rationale": "optional 1 sentence — why you want to pact with this peer"
  }
}

STRICT RULES:
- Sum of all allocation pct + cash_held_pct = 1.00 (±0.01)
- Max 1 allocation per game_idx (no hedging same game both sides)
- Max 10 allocations
- Each allocation pct: 0.01–0.40
- cash_held_pct: 0.0–1.0
- Rationale MUST cite a specific stat/metric (not "I think they'll win")
- Edge must be computed from model vs implied odds, NOT hardcoded
- coalition_proposal is OPTIONAL (null or omit if you are not pacting today).
  If present, you MUST also place a matching allocation for that game_idx+category,
  or your reputation is marked pact_broken. Peer only sees your proposal via
  COMMON_KNOWLEDGE the next day — mutual pacts emerge from independent proposals.
""")
    return "\n".join(lines)


def parse_day_allocation(raw: str, n_games: int) -> Optional[Dict]:
    """Parse day allocation JSON. Validates sum=1.0 within tolerance.

    Returns dict with: day_strategy, allocations (normalized), cash_held_pct,
    cash_rationale. Returns None if unparseable or grossly invalid.
    """
    parsed = parse_llm_decision(raw)
    if not parsed:
        return None
    allocations = parsed.get("allocations") or []
    if not isinstance(allocations, list):
        allocations = []
    cash = float(parsed.get("cash_held_pct", 0.0) or 0.0)

    # Filter invalid allocations
    clean = []
    seen_games = set()
    for a in allocations[:10]:
        if not isinstance(a, dict):
            continue
        gidx = a.get("game_idx")
        cat = (a.get("category") or "").lower().strip()
        try:
            pct = float(a.get("pct", 0) or 0)
            conf = float(a.get("confidence", 0.5) or 0.5)
            edge = float(a.get("edge", 0) or 0)
        except (TypeError, ValueError):
            continue
        if not cat or pct <= 0 or edge <= 0:
            continue
        if gidx is None or not isinstance(gidx, int):
            continue
        if gidx < 1 or gidx > n_games:
            continue
        if gidx in seen_games:
            continue
        seen_games.add(gidx)
        clean.append({
            "game_idx": gidx,
            "game": a.get("game", ""),
            "category": cat,
            "pct": max(0.01, min(0.40, pct)),
            "confidence": max(0.0, min(1.0, conf)),
            "edge": max(0.0, edge),
            "strategy": (a.get("strategy") or "half_kelly")[:30],
            "rationale": (a.get("rationale") or "")[:300],
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
        cp_gidx = cp.get("game_idx")
        cp_cat = (cp.get("category") or "").lower().strip()
        if peer and isinstance(cp_gidx, int) and 1 <= cp_gidx <= n_games and cp_cat:
            coalition = {
                "peer": peer[:40],
                "game_idx": cp_gidx,
                "category": cp_cat[:30],
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


# ── BET RESOLUTION ──────────────────────────────────────────────────────────

def resolve_bet(category: str, odds: Dict, hs: int, as_: int, home_won: bool,
                game_data: Dict = None) -> bool:
    """Resolve whether a bet category won. Supports 100+ categories."""
    cat = category.lower().strip()
    total_pts = hs + as_
    spread = odds.get("spread_home", 0) or 0
    total_line = odds.get("total", 0) or 0
    margin = hs - as_  # positive = home won by N

    # Base categories
    if cat == "ml_home": return home_won
    if cat == "ml_away": return not home_won
    if cat == "spread_home": return (hs + spread) > as_
    if cat == "spread_away": return (as_ - spread) > hs
    if cat == "total_over": return total_pts > total_line if total_line else False
    if cat == "total_under": return total_pts < total_line if total_line else False

    # Alt spreads: alt_spread_home_minus3.5 means home -3.5
    if cat.startswith("alt_spread_home_minus"):
        try:
            alt_line = float(cat.split("minus")[-1])
            return margin > alt_line
        except ValueError: pass
    if cat.startswith("alt_spread_home_plus"):
        try:
            alt_line = float(cat.split("plus")[-1])
            return margin > -alt_line
        except ValueError: pass
    if cat.startswith("alt_spread_away"):
        try:
            n = float(cat.split("_")[-1].replace("minus","-").replace("plus",""))
            return -margin > n
        except ValueError: pass

    # Alt totals: alt_total_over_plus3 means total > (line + 3)
    if cat.startswith("alt_total_over"):
        try:
            adj = float(cat.split("_")[-1].replace("plus","").replace("minus","-"))
            return total_pts > (total_line + adj) if total_line else False
        except ValueError: pass
    if cat.startswith("alt_total_under"):
        try:
            adj = float(cat.split("_")[-1].replace("plus","").replace("minus","-"))
            return total_pts < (total_line + adj) if total_line else False
        except ValueError: pass

    # Team totals
    if cat == "team_total_home_over":
        home_line = (total_line - spread) / 2 if total_line else 0
        return hs > home_line
    if cat == "team_total_home_under":
        home_line = (total_line - spread) / 2 if total_line else 0
        return hs < home_line
    if cat == "team_total_away_over":
        away_line = (total_line + spread) / 2 if total_line else 0
        return as_ > away_line
    if cat == "team_total_away_under":
        away_line = (total_line + spread) / 2 if total_line else 0
        return as_ < away_line

    # Halves (approximate: H1 ~ 48-52% of total)
    if cat.startswith("h1_") or cat.startswith("h2_"):
        # Without quarter data, use total game result as proxy
        if "ml_home" in cat: return home_won
        if "ml_away" in cat: return not home_won
        if "total_over" in cat: return total_pts > total_line if total_line else False
        if "total_under" in cat: return total_pts < total_line if total_line else False
        if "spread" in cat: return (hs + spread) > as_

    # Quarter MLs
    if cat.startswith("q1_"):
        if "ml_home" in cat: return home_won
        if "ml_away" in cat: return not home_won

    # Game props
    if cat == "prop_both_100": return hs >= 100 and as_ >= 100
    if cat == "prop_overtime": return False  # Can't determine from final score alone
    if cat.startswith("prop_margin"):
        if "1_5" in cat: return 1 <= abs(margin) <= 5
        if "6_10" in cat: return 6 <= abs(margin) <= 10
        if "11_15" in cat: return 11 <= abs(margin) <= 15
        if "16_20" in cat: return 16 <= abs(margin) <= 20
        if "21plus" in cat: return abs(margin) >= 21

    # Fallback: unknown category — treat as loss
    return False


def get_odds_dec(category: str, odds: Dict) -> float:
    """Get decimal odds for a bet category. Supports 100+ categories."""
    cat = category.lower().strip()
    # Base categories with real odds
    if cat == "ml_home": return odds.get("ml_home_dec", 1.91)
    if cat == "ml_away": return odds.get("ml_away_dec", 1.91)
    if cat in ("spread_home", "spread_away", "total_over", "total_under"):
        return 1.91  # Standard -110 juice
    # Alt spreads: adjusted odds (tighter = worse odds, wider = better)
    if "alt_spread" in cat:
        if "minus" in cat:
            try:
                n = float(cat.split("minus")[-1])
                base = odds.get("spread_home", 0) or 0
                diff = n - abs(base)
                return max(1.2, 1.91 - diff * 0.08)  # ~8 cents per point
            except ValueError: pass
        return 1.91
    # Alt totals
    if "alt_total" in cat: return 1.85
    # Team totals, halves, quarters: standard juice
    if cat.startswith(("team_total", "h1_", "h2_", "q1_")): return 1.91
    # Game props: higher odds for prop bets
    if cat == "prop_both_100": return 1.80
    if cat == "prop_overtime": return 8.0
    if "prop_margin" in cat: return 3.0
    return 1.91


# ── DATA LOADING ────────────────────────────────────────────────────────────

def load_games() -> List[Dict]:
    """Load 2025-26 season games."""
    data_dir = Path(__file__).parent / "data"
    fp = data_dir / "games-2025-26.json"
    if not fp.exists():
        return []
    raw = json.loads(fp.read_text())
    games_list = raw.get("games", raw if isinstance(raw, list) else [])
    enriched = []
    for g in games_list:
        game_date = g.get("game_date", "")
        # home_team is already an abbreviation in this dataset
        home = g.get("home_team") or g.get("home", {}).get("team_abbr", "")
        away = g.get("away_team") or g.get("away", {}).get("team_abbr", "")
        if not home or not away:
            continue
        h_data = g.get("home", {})
        a_data = g.get("away", {})
        hs = h_data.get("pts", h_data.get("PTS", 0))
        as_ = a_data.get("pts", a_data.get("PTS", 0))
        if not hs or not as_:
            continue
        enriched.append({
            "date": game_date, "home": home, "away": away,
            "home_score": int(hs), "away_score": int(as_),
            "home_won": int(hs) > int(as_),
            "home_stats": {k: h_data.get(k, 0) for k in STAT_KEYS},
            "away_stats": {k: a_data.get(k, 0) for k in STAT_KEYS},
        })
    enriched.sort(key=lambda g: g["date"])
    return enriched


def load_odds() -> Dict:
    """Load odds from CSV. Maps full team names to abbreviations."""
    data_dir = Path(__file__).parent / "data"
    fp = data_dir / "nba_2025-26_odds.csv"
    if not fp.exists():
        return {}

    def parse_odds_val(s):
        if not s or not s.strip():
            return None
        v = float(s.strip())
        if 1.0 < v < 15.0 and "." in s.strip():
            return v
        v = int(v)
        if v > 0:
            return v / 100.0 + 1
        if v < 0:
            return 100.0 / abs(v) + 1
        return 2.0

    odds = {}
    with open(fp) as f:
        reader = csv.DictReader(f)
        for row in reader:
            game_date = row.get("date", "")
            # Odds CSV uses full team names — map to abbreviations
            home = TEAM_MAP.get(row.get("home_team", ""), row.get("home_team", ""))
            away = TEAM_MAP.get(row.get("away_team", ""), row.get("away_team", ""))

            try:
                ml_home = parse_odds_val(row.get("moneyline_home", ""))
                ml_away = parse_odds_val(row.get("moneyline_away", ""))
                spread_s = row.get("spread_home", "").strip()
                total_s = row.get("total", "").strip()
                spread = float(spread_s) if spread_s else None
                total = float(total_s) if total_s else None
                if ml_home and ml_away:
                    odds[(game_date, home, away)] = {
                        "ml_home_dec": ml_home, "ml_away_dec": ml_away,
                        "spread_home": spread, "total": total,
                    }
            except (ValueError, TypeError):
                continue
    return odds


DATA = Path(__file__).parent / "data"

def load_rosters():
    """Load team rosters {team_abbr: [{name, position, age, ...}, ...]}"""
    path = DATA / "rosters-2025-26.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}

def load_team_advanced():
    """Load advanced team stats {team_abbr: {OFF_RATING, DEF_RATING, ...}}"""
    path = DATA / "team-advanced-2025-26.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}

def load_player_stats():
    """Load player per-game stats {team_abbr: [{name, ppg, rpg, ...}, ...]}"""
    path = DATA / "player-stats-2025-26.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}

def load_full_odds():
    """Load 100+ odds categories {game_key: {category: odds, ...}}"""
    path = DATA / "full-odds-2025-26.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}

def load_model_predictions():
    """Load our Nomos42 model consensus predictions {game_key: {...}}"""
    path = DATA / "model-predictions-2025-26.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}

def load_strategies():
    """Load 22 SOTA betting strategies"""
    path = DATA / "strategies.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def generate_implied_odds(home_wp: float, away_wp: float) -> Dict:
    """Generate implied odds from team win percentages when no real odds available."""
    if home_wp <= 0:
        home_wp = 0.4
    if away_wp <= 0:
        away_wp = 0.4
    # Home court advantage ~ +3.5%
    home_prob = (home_wp * 0.6 + 0.5 * 0.4) + 0.035
    home_prob = max(0.15, min(0.85, home_prob))
    ml_home = round(1.0 / home_prob, 3)
    ml_away = round(1.0 / (1.0 - home_prob), 3)
    # Rough spread from prob
    spread = round((0.5 - home_prob) * 20, 1)
    return {
        "ml_home_dec": ml_home, "ml_away_dec": ml_away,
        "spread_home": spread, "total": 220.0,
        "synthetic": True,
    }


# ── STANDINGS + FORM ────────────────────────────────────────────────────────

def compute_standings(all_games: List[Dict], up_to_date: str) -> Dict:
    standings = defaultdict(lambda: {"w": 0, "l": 0, "pts_for": 0, "pts_against": 0})
    for g in all_games:
        if g["date"] >= up_to_date:
            break
        home, away = g["home"], g["away"]
        if g["home_won"]:
            standings[home]["w"] += 1
            standings[away]["l"] += 1
        else:
            standings[away]["w"] += 1
            standings[home]["l"] += 1
        standings[home]["pts_for"] += g["home_score"]
        standings[home]["pts_against"] += g["away_score"]
        standings[away]["pts_for"] += g["away_score"]
        standings[away]["pts_against"] += g["home_score"]
    for team, s in standings.items():
        total = s["w"] + s["l"]
        s["win_pct"] = round(s["w"] / total, 3) if total > 0 else 0.0
    return dict(standings)


def compute_form(all_games: List[Dict], team: str, up_to_date: str, window: int = 10) -> Dict:
    recent = []
    for g in all_games:
        if g["date"] >= up_to_date:
            break
        if g["home"] == team:
            recent.append(g["home_won"])
        elif g["away"] == team:
            recent.append(not g["home_won"])
    last_n = recent[-window:]
    if not last_n:
        return {"games": 0, "w": 0, "l": 0}
    wins = sum(1 for w in last_n if w)
    return {"games": len(last_n), "w": wins, "l": len(last_n) - wins}


def build_common_knowledge_block(day_date: str, state: Dict, agent_logs: Dict,
                                  reputation: Optional[Dict] = None,
                                  pact_events: Optional[List[dict]] = None) -> str:
    """Build COMMON_KNOWLEDGE[D] block: peer bets + leaderboard for day D+1 prompts.

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
            f" | {ts['total_bets']} bets | {ts['wins']}W-{ts['losses']}L"
            f" | DD {ts['max_drawdown']:.1%}"
        )

    # Per-agent bet summary for day D (resolved outcomes)
    lines.append(f"\nPEER BETS on {day_date} (outcomes resolved):")
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
                parts.append(
                    f"{a['game']} {a['category']} edge={a['edge']:.3f}→{outcome}"
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
                f"on game#{ev['game_idx']} {ev['category']}"
            )

    lines.append(
        "AXELROD ANTI-GROUPTHINK (DMAD — MANDATORY):\n"
        "Your day_strategy field MUST begin with one of:\n"
        "  CONSENSUS AGREE [peer_name]: <reason your strategy supports the same pick>\n"
        "  CONSENSUS DIVERGE [peer_name]: <specific stat/metric counter-argument>\n"
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
    deltas.sort(key=lambda x: x[1])  # ascending — worst first
    bottom = [tid for tid, _ in deltas[:bottom_n]]

    assignments: Dict[str, str] = {}
    for tid in bottom:
        unused = [a for a in AXELROD_ARCHETYPES if a not in _used_archetypes[tid]]
        if not unused:
            _used_archetypes[tid].clear()  # exhausted → rotate again
            unused = list(AXELROD_ARCHETYPES)
        # Deterministic pick by tid-hash for reproducibility
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
        f"reason AND bet ONLY through the lens of '{archetype}'. This is a Pareto-\n"
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
        f"  1. NAME one recent decision that underperformed vs expectation.\n"
        f"  2. STATE one concrete adjustment: edge threshold, stake sizing, or "
        f"category selection.\n"
        f"  3. APPLY that adjustment today — not tomorrow.\n"
        f"Your day_strategy field MUST include 'CHALLENGE_RESPONSE:' followed by "
        f"your one-sentence improvement plan before any bet rationale.\n"
    )


def compute_consensus_distance(tid: str, day_date: str, state: Dict, agent_logs: Dict) -> float:
    """Axelrod Mech C: KL-divergence proxy of this agent's bet distribution vs society consensus.

    Computes ||p_agent - p_society||_1 over category buckets (simpler than true KL, no smoothing).
    """
    # Bucket categories used in bets today across all agents
    from collections import Counter
    society = Counter()
    agent_counts = Counter()
    for other_tid, logs in agent_logs.items():
        day_log = next((l for l in reversed(logs) if l.get("date") == day_date), None)
        if not day_log:
            continue
        for a in day_log.get("allocations", []):
            cat = a.get("category", "unknown")
            society[cat] += 1
            if other_tid == tid:
                agent_counts[cat] += 1
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
    return l1 / 2.0  # normalize [0,1]


def write_axelrod_log(day_idx: int, day_date: str, state: Dict,
                       agent_logs: Dict, sacrificial_map: Dict[str, str]) -> None:
    """Axelrod Mech C: append per-day post-mortem to /tmp/axelrod-log/day-N.jsonl.

    This is the primary dataset for the Nature paper on LLM agent society game theory.
    """
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
    """v3 DAY-BUCKET experiment: 10 agents × all game-days.

    Each agent receives ALL games of a single day in one prompt, and must
    allocate 100% of their bankroll across them (or explicitly hold cash with
    rationale). One LLM call per agent per day (not per game).
    """
    global _llm_calls, _llm_failures, _gateway_routed, _gateway_fallback
    _llm_calls = 0
    _llm_failures = 0
    _gateway_routed = 0
    _gateway_fallback = 0

    # Load data
    all_games = load_games()
    odds_dict = load_odds()
    rosters = load_rosters()
    team_advanced = load_team_advanced()
    player_stats = load_player_stats()
    full_odds = load_full_odds()
    model_preds = load_model_predictions()
    strategies = load_strategies()
    n_games = len(all_games)

    if n_games == 0:
        yield ("No game data found!", None, None, "Error: No game data in data/ directory")
        return

    # ── Group games by date ──
    games_by_date = defaultdict(list)
    for g in all_games:
        games_by_date[g["date"]].append(g)
    dates_sorted = sorted(games_by_date.keys())
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
                # merge what we saved; ensure new keys exist
                state[tid].update({k: v for k, v in saved_agents[tid].items() if k in state[tid]})
        start_from_day = saved.get("days_processed", 0)
        print(f"RESUMING from day {start_from_day}/{n_days}")

    start_time = time.time()
    odds_matched = 0
    odds_synthetic = 0
    log_lines = []

    log_lines.append("=== NOMOS42 REAL LLM TRADING FLOOR v3 (DAY-BUCKET) ===")
    log_lines.append(f"Season: 2025-26 | Days: {n_days} | Games: {n_games} | Agents: {len(TRADERS)}")
    log_lines.append(f"API keys: {key_summary or 'NONE FOUND'}")
    log_lines.append(f"Data: {len(rosters)} rosters | {len(team_advanced)} teams adv | {len(full_odds)} odds | {len(model_preds)} preds | {len(strategies)} strategies")
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

        day_games = games_by_date[day_date]

        # Pre-compute per-game context for this day (leakage-safe — uses day_date cutoff)
        standings_at_day = compute_standings(all_games, day_date)
        day_odds_list = []
        day_stand_list = []
        day_form_list = []
        for g in day_games:
            home, away = g["home"], g["away"]
            h_std = standings_at_day.get(home, {})
            a_std = standings_at_day.get(away, {})
            h_form = compute_form(all_games, home, day_date)
            a_form = compute_form(all_games, away, day_date)

            odds_key = (day_date, home, away)
            if odds_key in odds_dict:
                odds = odds_dict[odds_key]
                odds_matched += 1
            else:
                odds_key_rev = (day_date, away, home)
                if odds_key_rev in odds_dict:
                    raw = odds_dict[odds_key_rev]
                    odds = {
                        "ml_home_dec": raw.get("ml_away_dec", 2.0),
                        "ml_away_dec": raw.get("ml_home_dec", 2.0),
                        "spread_home": -(raw.get("spread_home", 0) or 0),
                        "total": raw.get("total"),
                        "swapped": True,
                    }
                    odds_matched += 1
                else:
                    odds = generate_implied_odds(h_std.get("win_pct", 0.5), a_std.get("win_pct", 0.5))
                    odds_synthetic += 1
            day_odds_list.append(odds)
            day_stand_list.append((h_std, a_std))
            day_form_list.append((h_form, a_form))

        day_summary_lines = [f"[day {day_idx+1}/{n_days}] {day_date} | {len(day_games)} games"]

        # Axelrod Mech D — day-scope collection for coalition resolution after all agents decide
        day_proposals: Dict[str, dict] = {}
        day_actual_bets: Dict[str, set] = {}

        # Stackelberg leader for the day (arXiv 2507.09407): yesterday's top bankroll.
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

            system_prompt = AGENT_SYSTEM_PROMPTS.get(tid, "You are an NBA betting allocator.")
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
            # Axelrod Canon + Mech D cooperation rules (prepended so base role still reads last)
            system_prompt = AXELROD_CANON + "\n" + system_prompt
            user_prompt = build_day_prompt(
                day_date, day_games, day_odds_list, day_stand_list, day_form_list,
                ts, rosters=rosters, team_advanced=team_advanced,
                player_stats=player_stats, full_odds=full_odds,
                model_preds=model_preds, strategies=strategies,
                recent_decisions=ts.get("recent_decisions", []),
                common_knowledge_block=prev_day_ck,
            )

            ts["llm_calls"] += 1
            raw_response = _call_llm(provider, system_prompt, user_prompt, timeout=30.0)
            if raw_response:
                ts["llm_ok"] += 1
            parsed = parse_day_allocation(raw_response, len(day_games)) if raw_response else None

            day_log = {
                "day_idx": day_idx,
                "date": day_date,
                "n_games": len(day_games),
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

                # Stake-sizing fix (2026-04-14): use CURRENT bankroll, not fixed
                # starting_bankroll, and cap LLM-chosen pct at 5% (half-Kelly equivalent)
                # plus require edge > 0.03 to skip unprofitable bets.
                # Without these caps, agents with 60-65% WR drained their bankroll to $0
                # because the same $15 stake wiped out a $10 bankroll.
                MAX_PCT_PER_BET = 0.05  # half-Kelly cap
                MIN_EDGE = 0.03         # only bet meaningful edges
                for alloc in parsed["allocations"]:
                    gidx = alloc["game_idx"] - 1  # 1-indexed in prompt
                    if gidx < 0 or gidx >= len(day_games):
                        continue
                    g = day_games[gidx]
                    odds = day_odds_list[gidx]
                    cat = alloc["category"]

                    edge_val = alloc.get("edge", 0.0) or 0.0
                    if edge_val < MIN_EDGE:
                        continue
                    capped_pct = min(alloc["pct"], MAX_PCT_PER_BET)
                    stake = round(ts["bankroll"] * capped_pct, 2)
                    if stake < 0.50 or stake > ts["bankroll"]:
                        continue

                    won = resolve_bet(cat, odds, g["home_score"], g["away_score"], g["home_won"])
                    odds_dec = get_odds_dec(cat, odds)
                    if won:
                        profit = stake * (odds_dec - 1)
                        ts["bankroll"] += profit
                        ts["wins"] += 1
                    else:
                        profit = -stake
                        ts["bankroll"] -= stake
                        ts["losses"] += 1
                    ts["total_bets"] += 1
                    ts["bankroll"] = round(ts["bankroll"], 2)

                    day_log["allocations"].append({
                        "game": f"{g['away']}@{g['home']}",
                        "category": cat,
                        "pct": round(alloc["pct"], 4),
                        "stake": stake,
                        "confidence": alloc["confidence"],
                        "edge": round(alloc["edge"], 4),
                        "rationale": alloc["rationale"],
                        "won": won,
                        "odds": round(odds_dec, 3),
                        "profit": round(profit, 2),
                    })
                    # Mech D — record actual (game_idx, category) pairs for coalition resolution
                    day_actual_bets.setdefault(tid, set()).add((alloc["game_idx"], cat))
            else:
                ts["passes"] += 1  # full-cash day

            # Track recent decisions for next-day prompt
            n_bets = len(day_log["allocations"])
            n_wins = sum(1 for a in day_log["allocations"] if a["won"])
            day_pnl = ts["bankroll"] - bankroll
            summary = f"{n_bets} bets, {n_wins}W, pnl {day_pnl:+.2f}"
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

            day_summary_lines.append(f"  {cfg['name'][:16]:<16} ${ts['bankroll']:>7.2f} ({n_bets} bets, {n_wins}W, {day_log['cash_held_pct']:.0%} cash)")

        log_lines.extend(day_summary_lines)

        # Axelrod Mech D — resolve coalitions for today
        day_pact_events: List[dict] = []
        for tid, prop in day_proposals.items():
            peer = prop.get("peer")
            gidx = prop.get("game_idx")
            cat = prop.get("category")
            key = (gidx, cat)
            self_executed = key in day_actual_bets.get(tid, set())
            peer_executed = peer in day_actual_bets and key in day_actual_bets[peer]
            if self_executed and peer_executed:
                _reputation[tid]["pact_honored"] += 1
                day_pact_events.append({
                    "day": day_date, "proposer": tid, "peer": peer,
                    "game_idx": gidx, "category": cat, "status": "honored",
                })
                _cooperation_pacts[f"{tid}|{peer}|{day_date}"] = {
                    "game_idx": gidx, "category": cat, "honored": True,
                }
            elif not self_executed:
                _reputation[tid]["pact_broken"] += 1
                day_pact_events.append({
                    "day": day_date, "proposer": tid, "peer": peer,
                    "game_idx": gidx, "category": cat, "status": "broken",
                })

        # Axelrod Mechanism A: build COMMON_KNOWLEDGE[D] from today's resolved bets
        prev_day_ck = build_common_knowledge_block(
            day_date, state, dict(_agent_logs),
            reputation=dict(_reputation), pact_events=day_pact_events,
        )
        _common_knowledge[day_date] = prev_day_ck

        # Axelrod Mechanism C: write day-N post-mortem log BEFORE Mech B reassigns
        write_axelrod_log(day_idx, day_date, state, dict(_agent_logs), dict(_sacrificial_assignments))

        # Axelrod Mechanism B: compute sacrificial + challenge assignments for NEXT day (D+1)
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
                "games_processed": sum(len(games_by_date[d]) for d in dates_sorted[:day_idx + 1]),
                "games_total": n_games,
                "completed": False,
                "design": "day-bucket-v3",
                "agents": {tid: {k: v for k, v in ts.items() if k not in ("history", "recent_decisions")}
                           for tid, ts in state.items()},
                "updated": datetime.now(timezone.utc).isoformat(),
                "last_ck_block": prev_day_ck,  # Axelrod Mech A: persist for resume
            }
        if (day_idx + 1) % 5 == 0 or day_idx == n_days - 1:
            _save_state_to_disk(_experiment_state)
            _save_logs_to_disk()

        if (day_idx + 1) % 1 == 0:  # Yield every day (slower pace than games)
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
            games_done = sum(len(games_by_date[d]) for d in dates_sorted[:day_idx + 1])
            fig = make_bankroll_chart(state, games_done)

            # Show recent unique errors
            err_summary = ""
            if _llm_errors:
                unique_errs = list(set(_llm_errors[-20:]))[:5]
                err_summary = " | ERRORS: " + "; ".join(unique_errs)

            status = (
                f"Day {days_done}/{n_days} ({games_done}/{n_games} games) | "
                f"LLM calls: {_llm_calls} (fail: {_llm_failures}) | "
                f"Odds: {odds_matched} real + {odds_synthetic} synthetic | "
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
            f"| {ts['total_bets']} bets | {ts['wins']}W-{ts['losses']}L | "
            f"DD: {ts['max_drawdown']:.1%} | LLM: {ts['llm_ok']}/{ts['llm_calls']}"
        )

    log_lines.append(f"\nTotal LLM calls: {_llm_calls} | Failures: {_llm_failures}")
    log_lines.append(f"Time: {elapsed/60:.1f} min ({elapsed/3600:.1f} hours)")

    # Save results
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "season": "2025-26",
        "design": "day-bucket-v3",
        "games_processed": n_games,
        "days_processed": n_days,
        "odds_matched": odds_matched,
        "odds_synthetic": odds_synthetic,
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

    fig = make_bankroll_chart(state, n_games)
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
            "games_total": n_games,
            "completed": not stopped,
            "stopped": stopped,
            "design": "day-bucket-v3",
            "agents": {tid: {k: v for k, v in ts.items() if k not in ("history", "recent_decisions")}
                       for tid, ts in state.items()},
            "updated": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(elapsed, 1),
        }
        _save_state_to_disk(_experiment_state)
        _save_logs_to_disk()
    _experiment_running = False

    yield (status, lb_data, fig, log_text)


def make_bankroll_chart(state: Dict, games_done: int) -> plt.Figure:
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
    ax.set_xlabel("Agent-game steps", color="#aaa", fontsize=10)
    ax.set_ylabel("Bankroll ($)", color="#aaa", fontsize=10)
    ax.set_title(f"Nomos42 Real LLM Trading Floor — Bankroll Evolution ({games_done} games)",
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
    "Agent", "Model", "Bankroll", "ROI", "Bets",
    "Win%", "Passes", "LLM%", "Max DD",
]

with gr.Blocks(
    title="Nomos42 Real LLM Trading Floor",
    theme=gr.themes.Base(
        primary_hue="blue",
        neutral_hue="gray",
    ),
    css="""
    .gradio-container { max-width: 1200px !important; }
    .status-bar { font-family: monospace; font-size: 14px; }
    """
) as demo:
    gr.Markdown("""
# Nomos42 Real LLM Trading Floor
### 10 AI Agents x 1257 NBA Games x Real LLM Reasoning

Each agent is a **real LLM** (Cerebras, Gemini, OpenRouter) that receives
**100+ betting categories**, team rosters, advanced stats, our Nomos42 AI predictions,
and **22 SOTA strategies** from research papers — then **reasons** about what to bet.

After the full 2025-26 season, we see which LLM backbone, personality, and strategy
combination actually makes money.

| Agent | Model | Provider | Personality | Risk |
|-------|-------|----------|-------------|------|
| Gemini Flash | Gemini 2.5 Flash | Google (key 1) | Analytical | 0.60 |
| Gemini 3 Flash | Gemini 3 Flash Preview | Google (key 2) | Diversified | 0.50 |
| Qwen 3 235B | Qwen 3 235B-A22B | Cerebras | Quantitative | 0.55 |
| Llama 3.1 8B | Llama 3.1 8B | Cerebras | Contrarian | 0.65 |
| GLM 4.5 Air | GLM 4.5 Air | OpenRouter | Conservative | 0.40 |
| GPT-OSS 20B | GPT-OSS 20B | OpenRouter | Aggressive | 0.70 |
| Gemma 4 26B | Gemma 4 26B | OpenRouter | Arbitrage | 0.75 |
| Nemotron 120B | Nemotron 3 Super 120B | OpenRouter | Tactical | 0.60 |
| MiniMax M2.5 | MiniMax M2.5 | OpenRouter | Theoretical | 0.35 |
| Qwen3 80B | Qwen3 Next 80B | OpenRouter | Ensemble | 0.50 |
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
        log_box = gr.Textbox(label="Game Log (last 30 entries)", lines=15, interactive=False,
                             show_copy_button=True)

    def stop_experiment():
        _stop_event.set()
        return "STOPPING... (will finish current game)"

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
    return JSONResponse(state)

@api.post("/api/run")
async def api_run(request: Request):
    """Trigger experiment start (same as clicking the button).
    For GH Actions / council triggers. Non-blocking — returns immediately."""
    # Always clear stop flag — allows resuming a stopped-but-still-running experiment
    _stop_event.clear()
    if _experiment_running:
        return JSONResponse({"status": "resumed", "games_processed": _experiment_state.get("games_processed", 0), "message": "Stop flag cleared, experiment continues."})
    return JSONResponse({"status": "ready", "message": "Stop flag cleared. Click Start in Gradio UI or use gradio_api."})

@api.post("/api/stop")
async def api_stop():
    """Graceful stop — finishes current game then saves state."""
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
    Body: {"agent": "gemini", "risk_tolerance": 0.8, "personality": "aggressive"}"""
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
    """Per-agent decision log. ?agent=gemini&limit=20"""
    if agent:
        logs = list(_agent_logs.get(agent, []))[-limit:]
        return JSONResponse({"agent": agent, "count": len(logs), "logs": logs})
    # All agents summary
    summary = {tid: len(logs) for tid, logs in _agent_logs.items()}
    return JSONResponse({"agents": summary, "total_entries": sum(summary.values())})

@api.get("/api/day-decisions")
async def api_day_decisions(date: str = None, agent: str = None, limit: int = 200):
    """Day-level decisions for council analysis.

    ?date=2025-10-21 — all agents' decisions for that day
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
    return JSONResponse({"leaderboard": lb, "games_processed": _experiment_state.get("games_processed", 0)})

# Mount FastAPI alongside Gradio
app = gr.mount_gradio_app(api, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
