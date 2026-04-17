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
import math

# ── LANGFUSE OBSERVABILITY (non-blocking — never delays TF startup) ────────
_langfuse = None
try:
    from langfuse import Langfuse
    _lf_pub = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    _lf_sec = os.environ.get("LANGFUSE_SECRET_KEY", "")
    _lf_host = os.environ.get("LANGFUSE_HOST", "")
    if _lf_pub and _lf_sec and _lf_host:
        _langfuse = Langfuse(public_key=_lf_pub, secret_key=_lf_sec, host=_lf_host, enabled=True, timeout=5)
        print(f"  LANGFUSE: initialized → {_lf_host}")
    else:
        print("  LANGFUSE: keys/host not set (observability disabled)")
except Exception as e:
    print(f"  LANGFUSE: init failed ({e}) — continuing without observability")

def benjamini_hochberg(edges: List[Tuple[str, float]], alpha: float = 0.05) -> set:
    """Return set of category tags that survive BH FDR correction.
    Treats |edge| as a test statistic under H0: edge=0. With ~22 political
    categories derived from Normal CDF, the SE of each derived edge is ~0.03-0.05.
    We use SE=0.04 as conservative estimate for all categories."""
    SE = 0.04
    n = len(edges)
    if n == 0:
        return set()
    pvals = []
    for tag, edge_val in edges:
        z = abs(edge_val) / SE
        p = 2 * (1 - _norm_cdf(z))
        pvals.append((p, tag))
    pvals.sort()
    passing = set()
    for rank, (p, tag) in enumerate(pvals, 1):
        threshold = alpha * rank / n
        if p <= threshold:
            passing.add(tag)
        else:
            break
    return passing

def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

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
_used_archetypes: Dict[str, set] = defaultdict(set)  # Axelrod Mech B: tid → set of archetypes tried (per-agent fallback)
_society_archetypes_by_day: Dict[str, set] = {}  # Axelrod Mech B: day_date → society-wide archetypes assigned that day
_challenge_assignments: Dict[str, int] = {}  # Axelrod Mech B: mid-tier tid → leaderboard rank
STATE_PATH = Path("/tmp/ptf-state.json")   # Local (ephemeral /tmp) — cheap quick-save
LOGS_PATH = Path("/tmp/ptf-agent-logs.json")
AXELROD_LOG_DIR = Path("/tmp/axelrod-log-political")  # Axelrod Mech C

# ── HUB PERSISTENCE (2026-04-17) ────────────────────────────────────────────
# Mirrors NBA TF. /tmp wiped every restart; push snapshot to Space repo so the
# full per-agent per-day decision trail survives every restart.
HF_REPO_ID = os.environ.get("SPACE_ID") or "LBJLincoln26/political-llm-trading-floor"
HF_HUB_TOKEN = os.environ.get("HF_WRITE_TOKEN") or os.environ.get("NOMOS_HF_TOKEN") or os.environ.get("HF_TOKEN")
HUB_SNAPSHOT_EVERY_DAYS = 3
try:
    from huggingface_hub import HfApi, hf_hub_download
    _hub_api = HfApi(token=HF_HUB_TOKEN) if HF_HUB_TOKEN else None
except Exception:
    _hub_api = None
    hf_hub_download = None

# ── COLLECTIVE EXPERIMENT (2026-04-17) ─────────────────────────────────────
# Mirrors NBA TF. Common goal: one agent hits $1M by season end. Council plan
# daily; rogue defection allowed on bankroll crash or peer > $250K.
SEASON_TARGET = 1_000_000.0
STARTING_CAPITAL = 100.0
ROGUE_DRAWDOWN_THRESHOLD = 0.25
ROGUE_GREED_THRESHOLD = 250_000.0
COUNCIL_MIN_COMMIT_PER_AGENT = 0.50
_council_plans: Dict[str, dict] = {}
_rogue_events: List[Dict] = []

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
COLLECTIVE_MISSION = (
    "=== COLLECTIVE MISSION (2026-04-17, binding) ===\n"
    "You are ONE of 16 LLM agents sharing a political-alpha society bankroll. All 16 agents see "
    "the SAME data: 1120 political events, 22 event categories × 7 SPDR sectors, full sector-beta "
    "matrices + insider trades + fed speakers + exec orders + peer bankrolls + peer positions + "
    "post-mortem logs.\n"
    "COMMON GOAL: ONE of us reaches $1,000,000 bankroll by season end. That agent's win counts "
    "as a collective win. Individual greed (>$250K while peers dying) triggers DEFECT rogue.\n"
    "DEPLOY RULE (hard): ≥75% of your bankroll MUST be deployed EVERY DAY across ≥3 sector "
    "allocations. Holding >25% cash violates the collective goal. Use the full 7-sector SPDR menu "
    "(XLF/XLE/XLV/XLI/XLK/XLC/XLY) + individual stocks when politically warranted.\n"
    "COLLABORATION STACK: (1) morning council plan (qwen-235B moderator) specifies focus sectors + "
    "per-agent commit. (2) Pact proposals let 2 agents bet the same sector+direction. "
    "(3) Axelrod canon strategy assigned per agent. (4) Post-mortem log visible to all. "
    "(5) Sacrificial rotation reassigns losing agents to archetypes the society lacks.\n"
    "=== END COLLECTIVE MISSION ===\n\n"
)

AXELROD_CANON = (
    COLLECTIVE_MISSION +
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
    "selfhost-qwen4b":   "Tullock",
    "nvidia-minimax":    "Prober",
    "nvidia-llama70":    "Gradual",
    "selfhost-gemma3":   "Handshake",
    "selfhost-qwen06":   "Cooperator",
    "selfhost-dolphin3": "Pavlov",
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
    "gemini-tact":       "REASONING TEMPLATE (DMAD): TACTICAL TIMING. Focus on calendar risk (votes, summits). Absent imminent catalyst, deploy ≥3 sector allocations on rolling 14-day sentiment (collective 75% deploy rule).",
    "mistral-large":     "REASONING TEMPLATE (DMAD): SCENARIO MAJORITY. Enumerate 5 macro scenarios, assign P, trade iff ≥3 align.",
    "mistral-medium":    "REASONING TEMPLATE (DMAD): DIVERSIFIED PORTFOLIO. Split across 2-3 uncorrelated sectors.",
    "mistral-small":     "REASONING TEMPLATE (DMAD): RISK-AVERSE STRESS. Assume worst-case tail; trade only if still +EV.",
    "mistral-nemo":      "REASONING TEMPLATE (DMAD): MOMENTUM CHASE. Bet hardest on sectors with 5-day momentum > 2σ.",
    "mistral-ministral": "REASONING TEMPLATE (DMAD): THEORETICAL MODEL. Mental factor model from 3 coefficients → compute expected sector return.",
    "nemotron-120b":     "REASONING TEMPLATE (DMAD): EXPLICIT 7-STEP CoT. context → hypothesis → evidence → counter → weight → conclusion → trade.",
    "selfhost-qwen4b":   "REASONING TEMPLATE (DMAD): 4-RULE CHECKLIST. (1) edge > 0.05 (2) bankroll > $30 (3) not same sector as yesterday (4) political catalyst dated within 14d. Trade iff ALL pass.",
    "nvidia-minimax":    "REASONING TEMPLATE (DMAD): LONG-CONTEXT SCAN. Ingest ALL today's events + 7-day history. Rank sectors by event-density × sentiment × sector-beta. Pick 2-3 with highest composite score.",
    "nvidia-llama70":    "REASONING TEMPLATE (DMAD): EV-THRESHOLD SWING. For each sector ETF compute EV = p_event × expected_sector_move − fees. Bet top 3 if EV > 0.05; else cash.",
    "selfhost-gemma3":   "REASONING TEMPLATE (DMAD): 3-FACTOR POLITICAL MODEL. Factors {congressional_vote_proximity, fed_speaker_density, geopolitical_tape}. Weight {0.4, 0.3, 0.3}. Trade iff weighted >0.6.",
    "selfhost-qwen06":   "REASONING TEMPLATE (DMAD): TINY-MODEL WIDE COVERAGE. Spread flat stakes across ALL 7 SPDR sectors (XLF/XLE/XLV/XLI/XLK/XLC/XLY). Any signal >0.35 → allocate.",
    "selfhost-dolphin3": "REASONING TEMPLATE (DMAD): PAVLOV WIN-STAY/LOSE-SHIFT. After a winning sector, double down. After a loss, rotate to the highest-momentum alternative. No overthinking.",
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
    """Persist to /tmp (fast, ephemeral) + HF Hub state.json (every day)."""
    try:
        STATE_PATH.write_text(json.dumps(state, default=str))
    except Exception:
        pass
    if _hub_api and int(state.get("days_processed", 0)) > 0:
        _push_state_to_hub(state)

def _push_state_to_hub(state: dict):
    """Lightweight state snapshot — one file, overwritten daily (resume)."""
    try:
        days = int(state.get("days_processed", 0))
        total = int(state.get("days_total", 0))
        _hub_api.upload_file(
            path_or_fileobj=json.dumps(state, default=str, indent=2).encode("utf-8"),
            path_in_repo="data/runtime/state.json",
            repo_id=HF_REPO_ID, repo_type="space",
            commit_message=f"runtime: day {days}/{total} state",
        )
    except Exception as e:
        print(f"[hub-persist] state push failed: {e}")

def _push_day_decisions_to_hub(day_idx: int, day_date: str, n_events: int,
                                day_logs_by_agent: Dict[str, dict],
                                day_council_plan: Optional[dict] = None,
                                day_rogue_state: Optional[dict] = None):
    """One file per experiment-day: data/decisions/day-XXX.json on the Space
    repo. Contains per-agent full rationale (which event, category, sizing,
    council alignment) + council plan. Councils/depts aggregate across days."""
    if not _hub_api:
        return
    try:
        payload = {
            "day_idx": day_idx,
            "date": day_date,
            "n_events": n_events,
            "n_agents": len(day_logs_by_agent),
            "council_plan": day_council_plan,
            "rogue_state": day_rogue_state,
            "agents": day_logs_by_agent,
            "written_at": datetime.now(timezone.utc).isoformat(),
        }
        _hub_api.upload_file(
            path_or_fileobj=json.dumps(payload, default=str, indent=2).encode("utf-8"),
            path_in_repo=f"data/decisions/day-{day_idx:03d}.json",
            repo_id=HF_REPO_ID, repo_type="space",
            commit_message=f"decisions: day {day_idx} ({day_date}) — {len(day_logs_by_agent)} agents",
        )
    except Exception as e:
        print(f"[hub-persist] day-{day_idx} push failed: {e}")

def _load_state_from_disk() -> Optional[dict]:
    """Load from /tmp (fast) or fallback to last Hub snapshot (survives
    Space restarts)."""
    try:
        if STATE_PATH.exists():
            return json.loads(STATE_PATH.read_text())
    except Exception:
        pass
    if hf_hub_download and HF_HUB_TOKEN:
        try:
            p = hf_hub_download(
                repo_id=HF_REPO_ID, filename="data/runtime/state.json",
                repo_type="space", token=HF_HUB_TOKEN,
            )
            state = json.loads(Path(p).read_text())
            print(f"[hub-persist] restored state from hub: day {state.get('days_processed',0)}/{state.get('days_total',0)}")
            for fname, target in [("agent_logs.json", _agent_logs), ("council_plans.json", _council_plans)]:
                try:
                    p2 = hf_hub_download(
                        repo_id=HF_REPO_ID, filename=f"data/runtime/{fname}",
                        repo_type="space", token=HF_HUB_TOKEN,
                    )
                    data = json.loads(Path(p2).read_text())
                    if isinstance(target, dict):
                        target.clear(); target.update(data)
                    else:
                        target.clear()
                        for k, v in data.items():
                            target[k] = v if isinstance(v, list) else []
                    print(f"[hub-persist] restored {fname}")
                except Exception as e:
                    print(f"[hub-persist] {fname} not yet in hub: {e}")
            return state
        except Exception as e:
            print(f"[hub-persist] no hub snapshot yet: {e}")
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
        "max_tokens": 500,
        "rpm": 30,
    },
    "cerebras:llama3.1-8b": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "llama3.1-8b",
        "key_env": "CEREBRAS_API_KEY",
        "max_tokens": 500,
        "rpm": 30,
    },
    # Google Gemini 3 Flash (key 2)
    "google:gemini-3-flash": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent",
        "model": "gemini-3-flash-preview",
        "key_env": "GOOGLE_API_KEY_2",
        "max_tokens": 500,
        "rpm": 14,
    },
    # Mistral la Plateforme (free tier — added 2026-04-14)
    "mistral:large": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-large-latest",
        "key_env": "MISTRAL_API_KEY",
        "max_tokens": 500,
        "rpm": 20,
    },
    "mistral:medium": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-medium-latest",
        "key_env": "MISTRAL_API_KEY",
        "max_tokens": 500,
        "rpm": 20,
    },
    "mistral:small": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-small-latest",
        "key_env": "MISTRAL_API_KEY",
        "max_tokens": 500,
        "rpm": 20,
    },
    "mistral:nemo": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "open-mistral-nemo",
        "key_env": "MISTRAL_API_KEY",
        "max_tokens": 500,
        "rpm": 20,
    },
    "mistral:ministral-8b": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "ministral-8b-latest",
        "key_env": "MISTRAL_API_KEY",
        "max_tokens": 500,
        "rpm": 20,
    },
    "openrouter:nemotron-120b": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "nvidia/nemotron-3-super-120b-a12b:free",
        "key_env": "OPENROUTER_API_KEY",
        "max_tokens": 500,
        "rpm": 12,
    },
    "openrouter:gemma-4-31b": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "google/gemma-4-31b-it:free",
        "key_env": "OPENROUTER_API_KEY",
        "max_tokens": 500,
        "rpm": 12,
    },
    "openrouter:gpt-oss-120b": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "openai/gpt-oss-120b:free",
        "key_env": "OPENROUTER_API_KEY",
        "max_tokens": 500,
        "rpm": 12,
    },
    # 2026-04-17 ROUTE: broken nomos-cpu-gemma4 → nomos42-llm-cpu (Qwen 2.5-1.5B cpu-basic, ~3 tok/s)
    # Keep max_tokens small so calls finish under timeout (~2-3 min budget).
    "selfhost:cpu-gemma4": {
        "url": "https://nomos42-nomos42-llm-cpu.hf.space/api/decide",
        "model": "qwen2.5-1.5b-instruct-q4_k_m",
        "key_env": "SELFHOST_NOOP",
        "max_tokens": 120,
        "rpm": 6,
    },
    # 2026-04-17 FIX: 5 providers referenced by TRADERS but absent from PROVIDERS
    # caused "unknown provider" → 100% fail rate on 5 agents. Direct fallback now
    # works even if gateway SSE times out.
    "selfhost:qwen3-4b": {
        "url": "https://nomos42-qwen3-4b-cpu.hf.space/v1/chat/completions",
        "model": "qwen3-4b-instruct",
        "key_env": "SELFHOST_NOOP",
        "max_tokens": 400,
        "rpm": 60,
    },
    "selfhost:gemma-3-4b": {
        "url": "https://nomos42-gemma2-2b-cpu.hf.space/v1/chat/completions",
        "model": "gemma-3-4b-it",
        "key_env": "SELFHOST_NOOP",
        "max_tokens": 400,
        "rpm": 60,
    },
    "selfhost:qwen3-0.6b": {
        "url": "https://nomos42-qwen25-05b-cpu.hf.space/v1/chat/completions",
        "model": "qwen3-0.6b-instruct",
        "key_env": "SELFHOST_NOOP",
        "max_tokens": 400,
        "rpm": 60,
    },
    "selfhost:dolphin3-l32-3b": {
        "url": "https://nomos42-llama32-1b-cpu.hf.space/v1/chat/completions",
        "model": "dolphin3-llama3.2-3b",
        "key_env": "SELFHOST_NOOP",
        "max_tokens": 400,
        "rpm": 60,
    },
    "selfhost:fin-r1": {
        "url": "https://nomos42-fin-r1-7b-cpu.hf.space/v1/chat/completions",
        "model": "fin-r1-7b",
        "key_env": "SELFHOST_NOOP",
        "max_tokens": 800,
        "rpm": 30,
    },
    "nvidia:minimax-m2.7": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model": "minimaxai/minimax-m2.7",
        "key_env": "NVIDIA_API_KEY",
        "max_tokens": 500,
        "rpm": 40,
    },
    "nvidia:minimax-m2.7-alt": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model": "minimaxai/minimax-m2.7",
        "key_env": "NVIDIA_API_KEY_2",
        "max_tokens": 500,
        "rpm": 40,
    },
    "nvidia:llama-3.3-70b": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model": "meta/llama-3.3-70b-instruct",
        "key_env": "NVIDIA_API_KEY",
        "max_tokens": 500,
        "rpm": 40,
    },
    "nvidia:nemotron-70b": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "key_env": "NVIDIA_API_KEY",
        "max_tokens": 500,
        "rpm": 40,
    },
}

# ── AGENT DEFINITIONS (v3 — 10 personas across 3 providers, 2026-04-14) ──────
# Each agent gets a real distinct model where possible. Same model + different
# system prompt = DMAD-style distinct reasoning (Prediction Arena 2604.07355).
TRADERS = {
    # Cerebras Qwen 3 235B — heaviest reasoning model, 2 personas
    # 2026-04-17 FIX: Cerebras free tier 429 "queue_exceeded" under TF load → add fallbacks
    "qwen-quant":  {"name": "Qwen Quant 235B",   "provider": "cerebras:qwen-3-235b",  "personality": "quantitative", "risk_tolerance": 0.55,
                    "fallback_provider": "mistral:large"},
    "qwen-arb":    {"name": "Qwen Arb 235B",     "provider": "cerebras:qwen-3-235b",  "personality": "arbitrage",    "risk_tolerance": 0.65,
                    "fallback_provider": "openrouter:gpt-oss-120b"},
    # Cerebras Llama 3.1 8B — small/fast, 1 persona
    "llama-contra":{"name": "Llama Contrarian",  "provider": "cerebras:llama3.1-8b",  "personality": "contrarian",   "risk_tolerance": 0.55,
                    "fallback_provider": "mistral:medium"},
    # Google Gemini 3 Flash — 2 personas
    "gemini-anl":  {"name": "Gemini Analytical", "provider": "google:gemini-3-flash", "personality": "analytical",   "risk_tolerance": 0.55},
    "gemini-tact": {"name": "Gemini Tactical",   "provider": "google:gemini-3-flash", "personality": "tactical",     "risk_tolerance": 0.60},
    # Mistral — 5 distinct models, 1 persona each
    "mistral-large":    {"name": "Mistral Large",    "provider": "mistral:large",        "personality": "ensemble",     "risk_tolerance": 0.50},
    "mistral-medium":   {"name": "Mistral Medium",   "provider": "mistral:medium",       "personality": "diversified",  "risk_tolerance": 0.45},
    "mistral-small":    {"name": "Mistral Small",    "provider": "mistral:small",        "personality": "conservative", "risk_tolerance": 0.35},
    # 2026-04-17 SWAP: gemma-4-31b rate-limited 429 upstream → cerebras:llama3.1-8b (aggressive momentum)
    "mistral-nemo":     {"name": "Momentum Hunter",   "provider": "cerebras:llama3.1-8b",  "personality": "aggressive",   "risk_tolerance": 0.70,
                         "fallback_provider": "openrouter:gpt-oss-120b"},
    "mistral-ministral":{"name": "Ministral 8B",     "provider": "openrouter:gpt-oss-120b","personality": "theoretical",  "risk_tolerance": 0.35,
                         "fallback_provider": "cerebras:llama3.1-8b"},
    "nemotron-120b":    {"name": "Nemotron 120B",    "provider": "openrouter:nemotron-120b","personality": "chainthought","risk_tolerance": 0.55,
                         "fallback_provider": "cerebras:qwen-3-235b"},
    # 2026-04-17 FIX: selfhost:cpu-gemma4 slug was never in gateway → dead. Switch to live selfhost:qwen3-4b.
    "selfhost-qwen4b":  {"name": "SelfHost Qwen3-4B","provider": "selfhost:qwen3-4b",      "personality": "disciplined", "risk_tolerance": 0.40,
                         "fallback_provider": "selfhost:gemma-3-4b"},
    # NEW 2026-04-17 — NVIDIA NIM (2 keys wired in gateway, 0 usage before) → parity with NBA TF.
    "nvidia-minimax":   {"name": "NVIDIA MiniMax M2.7","provider": "nvidia:minimax-m2.7",   "personality": "decisive",    "risk_tolerance": 0.58,
                         "fallback_provider": "nvidia:minimax-m2.7-alt"},
    "nvidia-llama70":   {"name": "NVIDIA Llama 3.3-70B","provider": "nvidia:llama-3.3-70b", "personality": "swing",       "risk_tolerance": 0.50,
                         "fallback_provider": "nvidia:nemotron-70b"},
    # NEW 2026-04-17 — 2 additional selfhost traders → full 16-agent parity with NBA TF.
    "selfhost-gemma3":  {"name": "SelfHost Gemma-3-4B","provider": "selfhost:gemma-3-4b",  "personality": "analytical",  "risk_tolerance": 0.45,
                         "fallback_provider": "selfhost:qwen3-4b"},
    "selfhost-qwen06":  {"name": "SelfHost Qwen3-0.6B","provider": "selfhost:qwen3-0.6b",  "personality": "conservative","risk_tolerance": 0.30,
                         "fallback_provider": "selfhost:qwen3-4b"},
    "selfhost-dolphin3":{"name": "SelfHost Dolphin3-3B","provider": "selfhost:dolphin3-l32-3b", "personality": "uncensored",  "risk_tolerance": 0.60,
                         "fallback_provider": "selfhost:qwen3-4b"},
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

    "mistral-small": """You are Mistral Small, a wide-coverage small-stake political allocator.
APPROACH: Spread small stakes across MANY sectors (≥5 per day). 22 political categories × N events/day = rich menu. Never sit on cash — deploy ≥75% bankroll every day per $1M collective goal.
PREFERRED STRATEGIES: eighth_kelly, flat_1pct, sector_rotation
EDGE DETECTION: Lower threshold (signal_strength >0.4). Tiny stakes on many signals compounds better than cash.
RISK: Low (0.35). Small per-bet stakes, but deploy wide.
SPECIALTY: Multi-sector ETFs (XLF, XLE, XLV, XLI, XLK, XLC, XLY) — use the breadth of 22 political categories.""",

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

    "nemotron-120b": """You are Nemotron 120B, a chain-of-thought sector value hunter.
APPROACH: Rank every sector by |political_signal - market_consensus|. Size the top 1-2 mispricings using half-Kelly. Ignore noisy signals.
PREFERRED STRATEGIES: value_hunter, half_kelly, proportional_edge
EDGE DETECTION: Cross-sector scan — healthcare, defense, energy often mispriced after regulatory events. Require edge >4%.
RISK: Moderate (0.55). Depth of reasoning over breadth.
SPECIALTY: Healthcare/defense/energy ETFs with deep CoT reasoning.""",

    "selfhost-qwen4b": """You are SelfHost Qwen3-4B, a disciplined self-hosted multi-sector political allocator on Nomos42/qwen3-4b-cpu.
APPROACH: Deploy ≥75% bankroll every day across ≥3 sector allocations. Pick from the full 22-category political menu (exec_orders, insider_trades, fed_speakers, congressional_votes, geopolitical, etc) × 7 SPDR sectors.
PREFERRED STRATEGIES: quarter_kelly, flat_2pct, sector_rotation
EDGE DETECTION: signal_strength >0.4 on ≥3 sectors → diversify across them. Collective $1M goal forbids cash-sitting.
RISK: Low-moderate (0.40). 3-5 sector allocations per day.
SPECIALTY: XLF / XLE / XLV / XLI / XLK rotation. Free infra, no quota.""",

    "nvidia-minimax": """You are NVIDIA MiniMax M2.7, a long-context political allocator on NVIDIA NIM.
APPROACH: Use the long-context window to ingest ALL events + 7-day political history simultaneously. Rank sectors by event density × sentiment × sector beta.
PREFERRED STRATEGIES: confidence_scaled, half_kelly, sector_rotation
EDGE DETECTION: Cross-correlate executive orders × Fed speakers × congressional votes × geopolitical tape. Pick 2-3 top sectors.
RISK: Moderate (0.58). Decisive on top conviction.
SPECIALTY: Sector rotation ETFs (XLF, XLE, XLV, XLI, XLK, XLC) based on multi-day political flow.""",

    "nvidia-llama70": """You are NVIDIA Llama 3.3 70B, a balanced EV-threshold political allocator on NVIDIA NIM.
APPROACH: Classical value hunter. For each sector ETF compute EV = p_event × expected_sector_move − fees. Bet top 3 if EV > 5%.
PREFERRED STRATEGIES: value_hunter, proportional_edge, flat_2pct
EDGE DETECTION: Pure EV math. Ignore narrative. Trust event → sector correlation.
RISK: Moderate (0.50). Swing trader, balanced across sectors.
SPECIALTY: Broad sector ETFs on FOMC + Treasury + geopolitical catalysts.""",

    "selfhost-gemma3": """You are SelfHost Gemma-3-4B, an analytical 3-factor political allocator on Nomos42/gemma2-2b-cpu Space.
APPROACH: 3-factor model {congressional vote proximity, fed speaker density, geopolitical tape}. Weight {0.4, 0.3, 0.3}. Trade only when weighted signal > 0.6.
PREFERRED STRATEGIES: half_kelly, confidence_scaled, sector_rotation
EDGE DETECTION: Factor score >0.6 AND sector beta >0.8 vs event type.
RISK: Low-moderate (0.45). Analytical, factor-disciplined.
SPECIALTY: XLF on Fed weeks, XLE on OPEC weeks, XLI on infra votes. Free infra.""",

    "selfhost-qwen06": """You are SelfHost Qwen3-0.6B, a wide-coverage tiny-model political allocator on Nomos42/qwen25-05b-cpu.
APPROACH: Tiny 0.6B model, so use SIMPLE rules: spread ≥3 tiny flat-bets across ALL 7 SPDR sectors (XLF/XLE/XLV/XLI/XLK/XLC/XLY). Deploy ≥75% bankroll every day.
PREFERRED STRATEGIES: flat_1pct, flat_2pct, sector_rotation
EDGE DETECTION: Any signal >0.35 on any sector → allocate. Diversify wide, not deep.
RISK: Very low (0.30). Tiny per-bet stakes, but many sectors = full 75%+ deployment.
SPECIALTY: Flat-stake wide coverage across all 7 SPDR sector ETFs.""",

    "selfhost-dolphin3": """You are SelfHost Dolphin3-3B, an uncensored adaptive political allocator on Nomos42/llama32-1b-cpu (Dolphin3-Llama3.2-3B).
APPROACH: Pavlov win-stay/lose-shift. Repeat yesterday's winning sectors, drop yesterday's losers. No filters, no hedging.
PREFERRED STRATEGIES: half_kelly, momentum_chase, sector_rotation
EDGE DETECTION: If yesterday's sector won → same sector today with +50% stake. If lost → switch to highest-momentum alternative. Deploy ≥75%.
RISK: High (0.60). Aggressive momentum, fast adaptation. Uncensored model — says what it thinks about political signals.
SPECIALTY: Adaptive momentum trading on political catalysts. Free infra.""",
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
                # Legacy self-hosted HF Space (T12 cpu-gemma4) — non-OpenAI shape.
                # cpu-basic GGUF is ~3 tok/s; 120 tokens = ~40s. Give 180s budget.
                payload = {
                    "system": system_prompt,
                    "user": user_prompt,
                    "max_tokens": cfg["max_tokens"],
                    "temperature": 0.3,
                    "json_only": True,
                }
                resp = requests.post(cfg["url"], json=payload, timeout=max(timeout, 180))
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
                # JSON-schema output: force structured response on providers that support it.
                # Skip selfhost (llama.cpp OpenAI shim often 400s on response_format).
                if not is_selfhost and any(p in provider for p in ("cerebras", "mistral", "openrouter", "nvidia")):
                    payload["response_format"] = {"type": "json_object"}
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
              timeout: float = 20.0, trace_name: str = "pol-tf-llm-call",
              trace_metadata: Optional[Dict] = None) -> Optional[str]:
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
    _t0 = time.time()

    text = _direct(system_prompt, user_prompt)
    if text:
        _gateway_fallback += 1
        result = {"text": text, "routed_via": "direct", "model_used": provider,
                  "latency_ms": int((time.time() - _t0) * 1000), "error": None}
    elif GATEWAY_URL:
        result = _gateway_call(
            provider, messages,
            temperature=0.3, max_tokens=max_tokens,
            fallback_direct=False, direct_fn=None,
            timeout=max(timeout, 30.0),
        )
    else:
        result = {"text": None, "routed_via": "failed", "model_used": provider,
                  "latency_ms": int((time.time() - _t0) * 1000), "error": "direct failed, no gateway"}
    _latency = time.time() - _t0

    if result["routed_via"] == "gateway":
        _gateway_routed += 1
        _text = result["text"]
        _status = "success"
    elif result["routed_via"] == "direct":
        _text = result["text"]
        _status = "success"
    else:
        _text = None
        _status = "failure"
        _llm_failures += 1
        if len(_llm_errors) < 100:
            _llm_errors.append(f"{provider}: {result.get('error')}")

    if _langfuse:
        try:
            trace = _langfuse.trace(
                name=trace_name,
                metadata={
                    "provider": provider,
                    "model": cfg.get("model", "unknown"),
                    "routed_via": result.get("routed_via", "none"),
                    "latency_s": round(_latency, 2),
                    "status": _status,
                    "sys_prompt_len": len(system_prompt),
                    "usr_prompt_len": len(user_prompt),
                    "response_len": len(_text) if _text else 0,
                    **(trace_metadata or {}),
                },
            )
            trace.generation(
                name=f"{provider}/{cfg.get('model','?')}",
                model=cfg.get("model", "unknown"),
                input={"system": system_prompt[:200], "user": user_prompt[:200]},
                output=_text[:500] if _text else None,
                usage={"total_tokens": len(system_prompt)//4 + len(user_prompt)//4 + (len(_text)//4 if _text else 0)},
            )
        except Exception:
            pass

    return _text


# ── PROMPT BUILDERS ──────────────────────────────────────────────────────────

def parse_llm_decision(raw: str) -> Optional[Dict]:
    """Extract JSON decision from LLM response. Handles thinking tags, markdown fences,
    channel tokens (Nemotron), dangling closers, nested braces, and LLM wrapping patterns."""
    if not raw:
        return None
    text = raw.strip()
    import re
    # 1. Strip thinking/reasoning tags (DeepSeek-R1, Qwen3, Nemotron-120B)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'<reasoning>.*?</reasoning>', '', text, flags=re.DOTALL)
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL)
    text = re.sub(r'<\|.*?\|>', '', text, flags=re.DOTALL)
    text = re.sub(r'^.*?</think>\s*', '', text, flags=re.DOTALL)
    text = re.sub(r'^.*?</reasoning>\s*', '', text, flags=re.DOTALL)
    text = text.strip()
    # 2. Markdown fence extraction
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            for p in parts[1::2]:
                if p.strip().startswith("{"):
                    text = p.strip()
                    break
            else:
                text = parts[1].strip()
    # 3. Candidate scan — try last-brace, then greedy
    candidates = []
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start:end + 1])
    last_open = text.rfind("{")
    if last_open >= 0 and last_open != start:
        candidates.append(text[last_open:] + ("}" if not text.rstrip().endswith("}") else ""))
    for candidate in candidates:
        for attempt in (candidate, re.sub(r',\s*([}\]])', r'\1', candidate),
                        re.sub(r"'([^']*)':", r'"\1":', candidate)):
            try:
                parsed = json.loads(attempt)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                continue
    # 4. Last resort — regex pluck of key fields
    dec_match = re.search(r'"decision"\s*:\s*"([^"]+)"', text)
    if dec_match:
        result = {"decision": dec_match.group(1)}
        for key in ("bet", "edge", "stake_pct", "confidence", "reason", "category"):
            m = re.search(r'"' + key + r'"\s*:\s*(?:"([^"]+)"|([\d.]+))', text)
            if m:
                val = m.group(1) if m.group(1) is not None else m.group(2)
                try:
                    result[key] = float(val)
                except (ValueError, TypeError):
                    result[key] = val
        return result
    return None


def _format_event_block(idx: int, event: Dict, event_preds: Optional[Dict] = None) -> str:
    """Compact single-event block for day-level prompts.

    Agent sees: idx, ticker, event_type, agency, signal_type, signal_sector,
    signal_strength, title (truncated), donor_info summary, macro snapshot.
    If walk-forward per-event predictions are available, agent also sees
    derived_core + top-8 category edges (matches NBA TF per-category pattern).
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

    # ── NOMOS42 WALK-FORWARD MODEL EDGES (past-only empirical priors) ──
    if event_preds:
        ev_key = f"{event.get('date','')}_{event.get('ticker','?')}_{event.get('event_type','?')}"
        pred = event_preds.get(ev_key)
        if pred:
            core = pred.get("derived_core", {})
            cats = pred.get("per_category", {})
            mu = core.get("predicted_excess_return", 0.0)
            sigma = core.get("predicted_sigma", 0.0)
            p_long = core.get("predicted_p_long_wins", 0.5)
            n_prior = core.get("prior_n", 0)
            lines.append(f"  NOMOS42 MODEL: mu={mu:+.4f} sigma={sigma:.4f} p(long_wins)={p_long:.2%} (n_prior={n_prior})")
            if cats:
                # Top-8 cats by |edge|
                ranked = sorted(
                    [(t, c) for t, c in cats.items() if c.get("edge") is not None],
                    key=lambda x: -abs(x[1].get("edge", 0)),
                )[:8]
                if ranked:
                    strong = []
                    for t, c in ranked:
                        e = c.get("edge", 0)
                        p = c.get("prob", 0)
                        sign = "+" if e > 0 else ""
                        strong.append(f"{t}={p:.2f}(edge{sign}{e:+.1%})")
                    lines.append(f"  MODEL PER-CAT (top-8 of {len(cats)}): {' · '.join(strong)}")
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


# ── PHASE 3 (2026-04-17) — ROGUE STATE ─────────────────────────────────────
def compute_rogue_state(state: Dict) -> Dict[str, dict]:
    """Per-agent defection permission. Triggers: own bankroll below
    drawdown floor, or any peer > greed threshold."""
    out: Dict[str, dict] = {}
    peer_bank = {tid: state[tid]["bankroll"] for tid in state}
    for tid, ts in state.items():
        reasons = []
        if ts["bankroll"] < STARTING_CAPITAL * ROGUE_DRAWDOWN_THRESHOLD:
            reasons.append("drawdown")
        others = {p: b for p, b in peer_bank.items() if p != tid}
        leader = max(others, key=others.get) if others else None
        leader_br = others.get(leader, 0.0) if leader else 0.0
        if leader_br > ROGUE_GREED_THRESHOLD:
            reasons.append("greed")
        out[tid] = {
            "is_rogue": bool(reasons),
            "reasons": reasons,
            "peer_leader": leader,
            "peer_bankroll": round(leader_br, 2),
        }
    return out


def build_rogue_block(rogue_info: dict) -> str:
    if not rogue_info.get("is_rogue"):
        return ""
    reasons = rogue_info.get("reasons", [])
    lines = ["\n\n=== ROGUE PERMISSION (rare) ==="]
    if "drawdown" in reasons:
        lines.append(
            f"Your bankroll is below ${STARTING_CAPITAL * ROGUE_DRAWDOWN_THRESHOLD:.0f} "
            "(drawdown floor). You may DEFECT from today's council plan for higher-variance "
            "macro/event trades. State 'DEFECT: drawdown' in day_strategy."
        )
    if "greed" in reasons:
        leader = rogue_info.get("peer_leader", "?")
        lb = rogue_info.get("peer_bankroll", 0.0)
        lines.append(
            f"Peer {leader} is at ${lb:,.0f} — past the ${ROGUE_GREED_THRESHOLD:,.0f} greed "
            "line. You may DEFECT and pursue independent high-EV trades. "
            "State 'DEFECT: greed' in day_strategy."
        )
    lines.append("Defection is LEGAL under these triggers. Otherwise follow council.")
    return "\n".join(lines)


# ── PHASE 1 (2026-04-17) — MORNING COUNCIL ─────────────────────────────────
def run_morning_council(day_idx: int, day_date: str, day_events: List[Dict],
                        sector_trends: Dict, state: Dict,
                        fleet_best_bankroll: float) -> dict:
    """One LLM call per day: moderator proposes shared plan for 10 political agents."""
    n_events = len(day_events)
    n_agents = len(state)
    leader = max(state, key=lambda t: state[t]["bankroll"])
    leader_br = state[leader]["bankroll"]
    fleet_total = sum(state[t]["bankroll"] for t in state)
    progress_pct = (fleet_best_bankroll / SEASON_TARGET) * 100.0

    roster_lines = []
    for tid, ts in sorted(state.items(), key=lambda x: -x[1]["bankroll"]):
        wr = (ts["wins"] / max(1, ts["wins"] + ts["losses"])) * 100.0
        roster_lines.append(
            f"  - {tid}: ${ts['bankroll']:,.2f} | {ts['wins']}W-{ts['losses']}L ({wr:.0f}%) | dd {ts['max_drawdown']*100:.1f}%"
        )
    events_brief = []
    for i, ev in enumerate(day_events[:15], 1):
        events_brief.append(
            f"  {i}. {ev.get('event_type','?')} · {ev.get('ticker','?')} · sig={ev.get('signal_strength','?')}"
        )
    trend_brief = ", ".join(
        f"{s}:{d.get('avg_ret',0):+.3f}" for s, d in sorted(
            (sector_trends or {}).items(), key=lambda x: -abs(x[1].get('avg_ret', 0))
        )[:6]
    )

    sys_prompt = (
        "You are the COUNCIL MODERATOR for a 10-agent POLITICAL trading floor. "
        "You coordinate all agents into a unified sector-ETF allocation plan for today. "
        "Common goal: one agent reaches $1,000,000 by season end. You are NOT trading — "
        "you are writing the plan."
    )
    usr_prompt = f"""COUNCIL SESSION · DAY {day_idx+1} · {day_date}

FLEET STATE ({n_agents} agents):
  Leader: {leader} @ ${leader_br:,.2f}
  Fleet total: ${fleet_total:,.2f}
  Season progress toward $1M: {progress_pct:.2f}%

AGENTS:
{chr(10).join(roster_lines)}

SECTOR TRENDS: {trend_brief}
TODAY'S EVENTS ({n_events} total, first 15):
{chr(10).join(events_brief)}

STRATEGIES: insider_tracking, regulatory_arb, macro_narrative, congressional_calendar,
  political_sentiment, foreign_sovereign_flow, trump_volatility, fed_watcher

CATEGORIES (sector ETFs): XLE, XLF, XLV, XLI, XLY, XLP, XLB, XLK, XLU, XLRE, ITA, XBI

TASK: Output COUNCIL PLAN. All 10 agents follow unless rogue.

RULES:
- Each agent commits ≥ {int(COUNCIL_MIN_COMMIT_PER_AGENT*100)}% of bankroll today.
- Bias weaker agents toward higher commit (catch-up).
- 2-4 focus_strategies, 3-6 focus_categories.
- Keep plan COMPACT.

SCHEMA:
{{
  "council_summary": "1 sentence",
  "focus_strategies": ["insider_tracking", "regulatory_arb"],
  "focus_categories": ["XLE", "XLF", "ITA"],
  "per_agent_commit_pct": {{"qwen-quant": 0.55, ...}},
  "shared_notes": "1-3 sentences"
}}

RESPOND WITH RAW JSON ONLY. All 10 agent ids in per_agent_commit_pct.
Values >= {COUNCIL_MIN_COMMIT_PER_AGENT} and <= 0.85."""

    fallback = {
        "council_summary": "no LLM council; default equal commitment",
        "focus_strategies": ["insider_tracking", "macro_narrative"],
        "focus_categories": ["XLE", "XLF", "ITA"],
        "per_agent_commit_pct": {tid: 0.55 for tid in state},
        "shared_notes": "Deterministic fallback plan.",
        "raw": "",
    }

    try:
        raw = _call_llm(
            "cerebras:qwen-3-235b",
            sys_prompt, usr_prompt, timeout=45.0,
            trace_name=f"pol-tf-council-{day_idx}",
            trace_metadata={"day": day_date, "n_events": n_events, "n_agents": n_agents, "fleet_total": fleet_total},
        )
    except Exception:
        raw = None
    if not raw:
        return fallback

    plan = parse_llm_decision(raw)
    if not isinstance(plan, dict):
        return fallback

    focus_strats = plan.get("focus_strategies") or []
    if not isinstance(focus_strats, list):
        focus_strats = []
    focus_cats = plan.get("focus_categories") or []
    if not isinstance(focus_cats, list):
        focus_cats = []
    commits = plan.get("per_agent_commit_pct") or {}
    if not isinstance(commits, dict):
        commits = {}
    clean_commits = {}
    for tid in state:
        try:
            v = float(commits.get(tid, 0.55) or 0.55)
        except (TypeError, ValueError):
            v = 0.55
        clean_commits[tid] = max(COUNCIL_MIN_COMMIT_PER_AGENT, min(0.85, v))

    return {
        "council_summary": str(plan.get("council_summary", ""))[:300],
        "focus_strategies": [str(s)[:40] for s in focus_strats[:4]],
        "focus_categories": [str(c)[:40] for c in focus_cats[:6]],
        "per_agent_commit_pct": clean_commits,
        "shared_notes": str(plan.get("shared_notes", ""))[:500],
        "raw": raw[:400],
    }


def build_council_block(plan: dict, tid: str, fleet_best_bankroll: float) -> str:
    if not plan:
        return ""
    my_commit = plan.get("per_agent_commit_pct", {}).get(tid, COUNCIL_MIN_COMMIT_PER_AGENT)
    progress = (fleet_best_bankroll / SEASON_TARGET) * 100.0
    lines = [
        "\n\n=== MORNING COUNCIL PLAN (follow unless rogue) ===",
        f"Fleet best bankroll: ${fleet_best_bankroll:,.2f} ({progress:.2f}% of $1M common goal)",
        f"Council summary: {plan.get('council_summary','(none)')}",
        f"Focus strategies: {', '.join(plan.get('focus_strategies',[]) or ['(none)'])}",
        f"Focus categories/ETFs: {', '.join(plan.get('focus_categories',[]) or ['(none)'])}",
        f"YOUR council commit: at least {my_commit*100:.0f}% of your bankroll deployed today.",
        f"Shared notes: {plan.get('shared_notes','(none)')}",
        "Bias allocations toward focus_strategies + focus_categories unless rogue.",
        "Common goal: ONE agent reaches $1M by season end.",
    ]
    return "\n".join(lines)


def build_day_prompt(day_date: str, day_events: List[Dict], sector_trends: Dict,
                     trader_state: Dict, strategies=None,
                     recent_decisions: List[Dict] = None,
                     common_knowledge_block: Optional[str] = None,
                     fleet_best_bankroll: float = 100.0,
                     event_preds: Optional[Dict] = None) -> str:
    """Build comprehensive day-level prompt. Agent sees ALL political events of the day."""
    bankroll = trader_state.get("bankroll", 100.0)
    total_allocs = trader_state.get("total_bets", 0)
    wins = trader_state.get("wins", 0)
    losses = trader_state.get("losses", 0)
    roi = ((bankroll - 100.0) / 100.0) * 100

    progress_pct = (fleet_best_bankroll / SEASON_TARGET) * 100.0
    lines = [f"=== TRADING DAY: {day_date} | {len(day_events)} POLITICAL EVENTS ===",
             f"",
             f"COMMON GOAL: one agent reaches ${SEASON_TARGET:,.0f}. Fleet best now ${fleet_best_bankroll:,.2f} ({progress_pct:.2f}%).",
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
        lines.append(_format_event_block(i, ev, event_preds))

    if strategies:
        lines.append(f"\nSTRATEGIES ({len(strategies)}): {', '.join(list(strategies.keys())[:12])}...")

    if common_knowledge_block:
        lines.append("\n" + common_knowledge_block)

    lines.append("""
=== YOUR TASK ===
Allocate your bankroll across today's political events.
Each allocation = one sector ETF trade on one event. Total allocations + cash_held must sum to 1.00.
MANDATORY: You MUST place at least 1 trade. Zero-trade days are NOT allowed.
Even if edges are small, pick your BEST signal and allocate 5-15%. Cash-only is forbidden.

DIRECTIONS: long (bet ticker goes up), short (bet ticker goes down)
Each allocation references one event_idx from the list above.

LEAKAGE RULE: You NEVER see excess_return or y. Reason from signal_type, signal_strength, agency, donor_info, and sector_trends only.
Your thesis MUST cite which signal/agency drove the decision, not just the ticker.

RESPOND WITH RAW JSON ONLY. No markdown fences. No explanation before or after. First character MUST be {, last MUST be }. Do NOT wrap in ```json blocks.

Schema:
{
  "day_strategy": "1-2 sentences on today's overall approach",
  "council_alignment": {
    "stance": "followed|deviated|partial",
    "reason": "1 sentence — why you followed/deviated/partial vs council_commit_target"
  },
  "events_considered": [
    {"event_idx": 1, "decision": "bet|skip", "reason": "1 sentence — if skip: why (signal weak / agency unclear / already exposed / low conviction)"},
    {"event_idx": 2, "decision": "skip", "reason": "signal ambiguous, no clear sector read"}
  ],
  "allocations": [
    {
      "event_idx": 1,
      "direction": "long",
      "ticker": "XLE",
      "pct": 0.15,
      "confidence": 0.65,
      "thesis": "1-2 sentences citing signal/agency",
      "ticker_reason": "1 sentence — why this ticker vs other sector ETFs"
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

NEW AUDIT FIELDS (MANDATORY — councils use these to score decision quality):
- council_alignment: ONE of {followed|deviated|partial} + reason. Council assigned you
  a commit_pct target today (see COUNCIL_PLAN block); if you deployed close to it say
  "followed", if you went much higher/lower say "deviated" and explain, say "partial"
  if you respected direction but magnitude differs.
- events_considered: ONE entry per event on today's slate (include EVERY event_idx, not
  just the ones you bet). For skipped events give the specific reason — "signal weak",
  "sector already maxed", "conflicting agencies", "no clear ticker map", etc.
- ticker_reason on each allocation: say why this TICKER beat other sector ETFs
  (e.g. "XLE over XLB because the signal is oil-specific, not broad commodities").

STRICT RULES:
- Sum of all allocation pct + cash_held_pct = 1.00 (±0.01)
- direction must be "long" or "short" (no "cash" in allocations)
- allocations[]: MUST contain ≥3 entries every day. Empty allocations[] is FORBIDDEN.
  If no event has obvious edge, spread across 3 sector ETFs (XLE/XLV/XLF/XLK/XLF) anyway.
- Max 10 allocations, no duplicate event_idx
- Each allocation pct: 0.01–0.40
- cash_held_pct: 0.00–0.25 MAX (aggressive-deploy policy, $1M collective goal — idle capital cannot compound)
- MANDATORY: ≥75% deployed every day. Holding >25% cash violates the collective goal.
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
            "ticker_reason": (a.get("ticker_reason") or "")[:300],
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

    # ── MIN_DEPLOY_PCT = 0.75 — $1M collective goal, aggressive deploy
    # If LLM holds >25% cash, force-scale allocations to consume excess.
    MIN_DEPLOY_PCT = 0.75
    deployed = sum(a["pct"] for a in clean)
    if deployed > 0 and deployed < MIN_DEPLOY_PCT:
        scale_up = MIN_DEPLOY_PCT / deployed
        for a in clean:
            a["pct"] = min(0.40, a["pct"] * scale_up)
        new_deployed = sum(a["pct"] for a in clean)
        cash = max(0.0, 1.0 - new_deployed)
    elif deployed == 0:
        cash = 1.0

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

    # Phase B — council_alignment + events_considered audit fields
    ca = parsed.get("council_alignment") or {}
    council_alignment = None
    if isinstance(ca, dict):
        stance = (ca.get("stance") or "").lower().strip()
        if stance in ("followed", "deviated", "partial"):
            council_alignment = {
                "stance": stance,
                "reason": (ca.get("reason") or "")[:300],
            }

    ec = parsed.get("events_considered") or []
    events_considered: List[Dict] = []
    if isinstance(ec, list):
        seen_ec = set()
        for item in ec[:30]:
            if not isinstance(item, dict):
                continue
            ei = item.get("event_idx")
            if not isinstance(ei, int) or ei < 1 or ei > n_events or ei in seen_ec:
                continue
            seen_ec.add(ei)
            decision = (item.get("decision") or "").lower().strip()
            if decision not in ("bet", "skip"):
                decision = "bet" if ei in seen_events else "skip"
            events_considered.append({
                "event_idx": ei,
                "decision": decision,
                "reason": (item.get("reason") or "")[:300],
            })

    return {
        "day_strategy": (parsed.get("day_strategy") or parsed.get("reasoning") or "")[:500],
        "allocations": clean,
        "cash_held_pct": round(max(0.0, min(1.0, cash)), 4),
        "cash_rationale": (parsed.get("cash_rationale") or "")[:300],
        "raw_sum": round(total, 4),
        "coalition_proposal": coalition,
        "council_alignment": council_alignment,
        "events_considered": events_considered,
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


def load_political_predictions() -> Dict[str, dict]:
    """Load walk-forward per-event predictions with ~38 categories each.
    Keyed by '{date}_{ticker}_{event_type}'. Generated by
    extend_predictions_all_categories.py using past-only empirical priors."""
    data_dir = Path(__file__).parent / "data"
    path = data_dir / "political-predictions.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}


def build_common_knowledge_block(day_date: str, state: Dict, agent_logs: Dict,
                                  reputation: Optional[Dict] = None,
                                  pact_events: Optional[List[dict]] = None,
                                  day_idx: int = 0) -> str:
    """Build COMMON_KNOWLEDGE[D] block: full transparency for day D+1 prompts.

    Implements Axelrod-2026 Mechanism A (day-end common knowledge broadcast).
    All agents see ALL other agents' allocations, results, strategies, and bankrolls
    from the last 3 days, enabling true collective optimization.
    """
    n_traders = len(TRADERS)
    total_start = n_traders * 100.0
    lines = [
        f"=== COMMON KNOWLEDGE — Day {day_date} (full transparency) ===",
        f"COLLECTIVE GOAL: maximize TOTAL GROUP bankroll → target ${total_start:.0f} ($100×{n_traders} start).",
        f"You are ONE of {n_traders} political-alpha traders. Every allocation you make affects the group.",
        "",
    ]

    # Leaderboard with collective stats
    ranked = sorted(state.items(), key=lambda x: -x[1]["bankroll"])
    total_bankroll = sum(ts["bankroll"] for _, ts in ranked)
    total_bets = sum(ts["total_bets"] for _, ts in ranked)
    total_wins = sum(ts["wins"] for _, ts in ranked)
    lines.append(f"GROUP TOTAL: ${total_bankroll:.2f} (started ${total_start:.0f}) | "
                 f"ROI {((total_bankroll / total_start) - 1) * 100:+.1f}% | "
                 f"{total_bets} allocations | {total_wins}W")
    lines.append("")
    lines.append("LEADERBOARD:")
    for rank, (tid, ts) in enumerate(ranked, 1):
        cfg = TRADERS.get(tid, {})
        gf = ts["bankroll"] / 100.0
        roi = (gf - 1.0) * 100
        wr = (ts["wins"] / max(ts["total_bets"], 1)) * 100
        role = ""
        if ts["bankroll"] < 50:
            role = " [RESCUE MODE]"
        elif rank <= 3:
            role = " [TOP-3]"
        lines.append(
            f"  #{rank} {cfg.get('name', tid):<20} ${ts['bankroll']:.2f} ({roi:+.1f}%)"
            f" | {ts['total_bets']}b {wr:.0f}%WR | DD {ts['max_drawdown']:.1%}{role}"
        )

    # 3-day rolling allocation history from ALL agents (full transparency)
    all_dates = set()
    for tid in state:
        for log in agent_logs.get(tid, []):
            all_dates.add(log.get("date", ""))
    recent_dates = sorted(all_dates)[-3:]

    for past_date in recent_dates:
        lines.append(f"\n--- ALL ALLOCATIONS on {past_date} (resolved) ---")
        for tid, _ts in ranked:
            logs = agent_logs.get(tid, [])
            day_log = next((l for l in reversed(logs) if l.get("date") == past_date), None)
            if not day_log:
                continue
            cfg = TRADERS.get(tid, {})
            name = cfg.get("name", tid)
            allocs = day_log.get("allocations", [])
            strat = day_log.get("day_strategy", "")[:80]
            if not allocs:
                lines.append(f"  {name}: CASH — \"{strat}\"")
            else:
                for a in allocs:
                    outcome = "W" if a["won"] else "L"
                    lines.append(
                        f"  {name}: {a['ticker']} {a['direction']} {a.get('event_type', '?')} "
                        f"${a.get('stake', 0):.1f} edge={a.get('edge', 0):.3f}→{outcome} "
                        f"pnl={a.get('profit', 0):+.1f}")
                if strat:
                    lines.append(f"    Strategy: \"{strat}\"")

    # Mech D — Cooperation reputation + today's pact resolutions
    if reputation:
        lines.append("\nCOOPERATION REPUTATION:")
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

    # Council day protocol — every 15 days, agents reorganize
    is_council_day = (day_idx > 0 and day_idx % 15 == 0)
    if is_council_day:
        lines.append(
            "\n=== COUNCIL DAY (every 15 days) ===\n"
            "Today is a strategy reorganization day. In addition to your allocations,\n"
            "add a 'council_vote' field to your JSON:\n"
            "  \"council_vote\": {\n"
            "    \"worst_strategy\": \"name of peer whose strategy should change\",\n"
            "    \"suggested_change\": \"what they should try instead\",\n"
            "    \"my_adjustment\": \"what I will change about my own strategy\"\n"
            "  }\n"
            "Review the 3-day history above. Identify what's working and what isn't.\n"
            "Agents in RESCUE MODE should take higher-variance positions.\n"
            "TOP-3 agents should protect capital and mentor via coalition proposals.\n"
        )

    lines.append(
        "\nCOLLABORATION RULES:\n"
        "- You see ALL traders' allocations from last 3 days. Learn from winners.\n"
        "- AVOID duplicating the exact same sector/direction as a peer (diversify coverage).\n"
        "- If your bankroll is in RESCUE MODE (<$50), take higher-variance positions\n"
        "  (indirect beneficiary plays, cross-sector arb, high-beta sectors) — the group needs you swinging.\n"
        "- TOP-3 traders: protect capital, use corroborated multi-agency signals.\n"
        "- Propose coalitions with traders whose strategies complement yours.\n"
        "\n"
        "ANTI-GROUPTHINK (DMAD — MANDATORY):\n"
        "Your day_strategy MUST begin with one of:\n"
        "  CONSENSUS AGREE [peer_name]: <reason your strategy supports same sector/direction>\n"
        "  CONSENSUS DIVERGE [peer_name]: <specific signal/agency counter-argument>\n"
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
    """Axelrod Mech B: bottom-N by trailing delta get NEW archetype from unused pool.

    Society-wide dedup: exclude any archetype used by ANY agent in the trailing 7 days,
    matching spec "NEVER USED in the prior 7 days by anyone" (Axelrod-2026 Mechanism B).
    """
    from datetime import timedelta as _td
    deltas = [(tid, compute_trailing_delta(tid, state, agent_logs, trailing_days))
              for tid in state.keys()]
    deltas.sort(key=lambda x: x[1])
    bottom = [tid for tid, _ in deltas[:bottom_n]]

    # Build society-wide exclusion set: union of trailing-window daily assignments
    try:
        cutoff = datetime.fromisoformat(day_date) - _td(days=trailing_days)
        society_used: set = set()
        for d, archs in _society_archetypes_by_day.items():
            try:
                if datetime.fromisoformat(d) >= cutoff:
                    society_used.update(archs)
            except ValueError:
                pass
    except Exception:
        society_used = set()

    assignments: Dict[str, str] = {}
    today_used: set = set()  # prevent duplicate archetype to two sacrificed agents same day
    for tid in bottom:
        available = [a for a in AXELROD_ARCHETYPES if a not in society_used and a not in today_used]
        if not available:
            # All archetypes used society-wide — reset and exclude only today's picks
            available = [a for a in AXELROD_ARCHETYPES if a not in today_used]
        if not available:
            available = list(AXELROD_ARCHETYPES)
        pick = available[hash(tid + day_date) % len(available)]
        assignments[tid] = pick
        today_used.add(pick)
        _used_archetypes[tid].add(pick)  # retain per-agent history as fallback

    # Record society-wide assignments for this day
    _society_archetypes_by_day[day_date] = set(assignments.values())
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
    event_preds = load_political_predictions()  # walk-forward per-event preds (~38 cats/event)
    n_events = len(all_events)
    print(f"[pol-tf] loaded {n_events} events, {len(event_preds)} walk-forward predictions, {len(strategies)} strategies")

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

    global _experiment_running, _experiment_state, _common_knowledge, _society_archetypes_by_day
    _experiment_running = True
    _stop_event.clear()
    _common_knowledge = {}  # Reset per run; built day-by-day (Axelrod Mech A)
    _sacrificial_assignments.clear()  # Axelrod Mech B reset
    _challenge_assignments.clear()   # Axelrod Mech B: mid-tier challenge reset
    _used_archetypes.clear()  # Axelrod Mech B: reset archetype history
    _society_archetypes_by_day.clear()  # Axelrod Mech B: reset society-wide archetype history

    # ── Resume support (day-indexed) ──
    saved = _load_state_from_disk()
    start_from_day = 0
    multi_season_seed = False
    if saved and not saved.get("completed") and saved.get("days_processed", 0) > 0:
        saved_agents = saved.get("agents", {})
        for tid in TRADERS:
            if tid in saved_agents:
                state[tid].update({k: v for k, v in saved_agents[tid].items() if k in state[tid]})
        start_from_day = saved.get("days_processed", 0)
        print(f"RESUMING from day {start_from_day}/{n_days}")
    elif saved and saved.get("completed") and saved.get("agents"):
        # 2026-04-17: multi-season compounding — carry final bankrolls forward.
        saved_agents = saved["agents"]
        for tid in TRADERS:
            if tid in saved_agents:
                final_br = float(saved_agents[tid].get("bankroll", 100.0))
                state[tid]["bankroll"] = final_br
                state[tid]["history"] = [final_br]
                state[tid]["best_bankroll"] = final_br
                state[tid]["worst_bankroll"] = final_br
        multi_season_seed = True
        print(f"MULTI-SEASON SEED: carrying final bankrolls from prior completed season")

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

        # ── PHASE 1/3/4 (2026-04-17) — morning council + rogue + $1M goal ──
        fleet_best_bankroll = max((state[t]["bankroll"] for t in state), default=STARTING_CAPITAL)
        day_council_plan = run_morning_council(
            day_idx, day_date, day_events, sector_trends, state, fleet_best_bankroll,
        )
        _council_plans[day_date] = day_council_plan
        day_rogue_state = compute_rogue_state(state)
        for _tid, _rs in day_rogue_state.items():
            if _rs["is_rogue"]:
                _rogue_events.append({
                    "day": day_date, "tid": _tid,
                    "reasons": _rs["reasons"],
                    "peer_leader": _rs.get("peer_leader"),
                    "peer_bankroll": _rs.get("peer_bankroll"),
                })
        log_lines.append(
            f"[day {day_idx+1}] COUNCIL: {day_council_plan.get('council_summary','(none)')[:120]}"
        )
        _n_rogues = sum(1 for r in day_rogue_state.values() if r["is_rogue"])
        if _n_rogues:
            log_lines.append(f"[day {day_idx+1}] ROGUES: {_n_rogues}/{len(state)} eligible to defect")

        # PHASE 1 — parallel LLM calls (intra-day only; days remain sequential
        # because Mech A common-knowledge broadcast on day N+1 reads day N).
        def _agent_llm_worker(tid_cfg):
            tid, cfg = tid_cfg
            provider = cfg["provider"]
            ts = state[tid]
            if ts.get("bankroll", 0) <= 5.0:
                return tid, None
            system_prompt = AGENT_SYSTEM_PROMPTS.get(tid, "You are a political alpha allocator.")
            _template = REASONING_TEMPLATES.get(tid)
            if _template:
                system_prompt = system_prompt + "\n\n" + _template
            system_prompt = system_prompt + build_stackelberg_role_block(tid, _stackelberg_leader)
            if tid in _sacrificial_assignments:
                system_prompt = system_prompt + build_sacrificial_system_suffix(_sacrificial_assignments[tid])
            elif tid in _challenge_assignments:
                system_prompt = system_prompt + build_challenge_block(tid, _challenge_assignments[tid], len(TRADERS))
            system_prompt = AXELROD_CANON + "\n" + system_prompt
            _active_peers = [p for p in TRADERS if p != tid and state[p].get("bankroll", 0) > 5.0]
            _axl_block = _axelrod_advice_block(tid, _active_peers)
            if _axl_block:
                system_prompt = system_prompt + _axl_block
            # PHASE 1 — council plan
            _council_block = build_council_block(day_council_plan, tid, fleet_best_bankroll)
            if _council_block:
                system_prompt = system_prompt + _council_block
            # PHASE 3 — rogue permission
            _rogue_block = build_rogue_block(day_rogue_state.get(tid, {}))
            if _rogue_block:
                system_prompt = system_prompt + _rogue_block
            # Rescue protocol: agents under $50 get risk-on mandate
            if ts["bankroll"] < 50.0 and ts["bankroll"] > 5.0:
                system_prompt += (
                    "\n\n[RESCUE MODE ACTIVE] Your bankroll is critically low. "
                    "The group needs you to take HIGHER-VARIANCE positions: "
                    "indirect beneficiary plays, high-beta sectors, cross-sector arb. "
                    "Minimum edge 5%. Allocate 15-40% per position. "
                    "Conservative corroborated-only plays won't recover your position."
                )
            user_prompt = build_day_prompt(
                day_date, day_events, sector_trends, ts,
                strategies=strategies,
                recent_decisions=ts.get("recent_decisions", []),
                common_knowledge_block=prev_day_ck,
                fleet_best_bankroll=fleet_best_bankroll,
                event_preds=event_preds,
            )
            try:
                raw = _call_llm(provider, system_prompt, user_prompt, timeout=30.0,
                               trace_name=f"pol-tf-day-{day_idx}",
                               trace_metadata={"trader_id": tid, "day": day_date, "bankroll": ts["bankroll"]})
            except Exception:
                raw = None
            if not raw and cfg.get("fallback_provider"):
                try:
                    raw = _call_llm(cfg["fallback_provider"], system_prompt, user_prompt, timeout=30.0,
                                   trace_name=f"pol-tf-day-{day_idx}-fallback",
                                   trace_metadata={"trader_id": tid, "day": day_date, "fallback": True})
                except Exception:
                    pass
            return tid, raw

        _max_workers = min(len(TRADERS), 16)
        with ThreadPoolExecutor(max_workers=_max_workers) as _pool:
            _responses = dict(_pool.map(_agent_llm_worker, list(TRADERS.items())))

        # PHASE 2 — sequential resolution.
        for tid, cfg in TRADERS.items():
            provider = cfg["provider"]
            ts = state[tid]
            bankroll = ts["bankroll"]

            if bankroll <= 5.0:
                ts["passes"] += 1
                ts["history"].append(bankroll)
                continue

            raw_response = _responses.get(tid)
            ts["llm_calls"] += 1
            if raw_response:
                ts["llm_ok"] += 1
            parsed = parse_day_allocation(raw_response, len(day_events)) if raw_response else None

            # COLLECTIVE_MISSION fallback: if LLM failed or returned zero allocations,
            # inject 5 default trades at 15% each (= 75% deploy exactly) on first
            # up-to-5 events, direction=long, ticker=SPY. Matches MAX_PCT_PER_BET=0.15
            # so no clipping. Guarantees >=3 trades + 75% deploy EVERY day.
            if (not parsed or not parsed.get("allocations")) and len(day_events) >= 3:
                n_fallback = min(5, len(day_events))
                per_pct = 0.75 / n_fallback
                parsed = {
                    "day_strategy": f"fallback-injection: LLM silent, forcing 75% deploy on first {n_fallback} events (SPY long)",
                    "cash_held_pct": 0.25,
                    "cash_rationale": "fallback-injection (LLM returned no actionable allocations)",
                    "allocations": [
                        {"event_idx": i + 1, "ticker": "SPY", "direction": "long",
                         "pct": per_pct, "confidence": 0.40,
                         "thesis": "fallback", "source": "fallback-injection"}
                        for i in range(n_fallback)
                    ],
                    "coalition_proposal": None,
                }

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
                "rogue": day_rogue_state.get(tid, {"is_rogue": False}) if day_rogue_state else {"is_rogue": False},
                "council_commit_target": (day_council_plan or {}).get("per_agent_commit_pct", {}).get(tid, 0.55),
                "council_alignment": (parsed or {}).get("council_alignment"),
                "events_considered": (parsed or {}).get("events_considered") or [],
                "raw_preview": (raw_response or "")[:400],
            }

            # Mech D — stash coalition proposal even if allocations are empty
            if parsed and parsed.get("coalition_proposal"):
                day_proposals[tid] = parsed["coalition_proposal"]

            if parsed and parsed.get("allocations"):
                day_log["day_strategy"] = parsed["day_strategy"]
                day_log["cash_held_pct"] = parsed["cash_held_pct"]
                day_log["cash_rationale"] = parsed["cash_rationale"]

                # 2026-04-17 v2 risk caps (parity with NBA TF):
                # Traders may split across ALL events of the day (diversified
                # Kelly). No single bet > 10%, daily cumulative ≤ 60%.
                MAX_PCT_PER_BET = 0.15   # raised from 0.10 so 6 bets can reach 75%
                MAX_PCT_PER_DAY = 0.85   # raised from 0.60 to align with 0.75 deploy floor
                starting_bankroll = bankroll
                day_exposure_pct = 0.0
                for alloc in parsed["allocations"]:
                    eidx = alloc["event_idx"] - 1  # 1-indexed in prompt
                    if eidx < 0 or eidx >= len(day_events):
                        continue
                    event = day_events[eidx]
                    direction = alloc["direction"]

                    capped_pct = min(alloc["pct"], MAX_PCT_PER_BET)
                    remaining_day = max(0.0, MAX_PCT_PER_DAY - day_exposure_pct)
                    capped_pct = min(capped_pct, remaining_day)
                    if capped_pct <= 0:
                        continue
                    stake = round(starting_bankroll * capped_pct, 2)
                    if stake < 0.50:
                        continue
                    day_exposure_pct += capped_pct

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
                        "pct": round(capped_pct, 4),
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

            # SMART post-filter: pick events where model/category signal > 0 for long,
            # < 0 for short. If model signal missing, fall back to SPY long (baseline).
            total_bets_executed = len(day_log["allocations"])
            total_deployed_pct = sum(a.get("pct", 0) for a in day_log["allocations"])
            if (total_bets_executed < 3 or total_deployed_pct < 0.70) and len(day_events) >= 3:
                # Rank events by absolute expected excess_return sign from model (if present)
                # Falls back to raw excess_return magnitude for ranking
                ranked = []
                for ei, ev in enumerate(day_events):
                    sig = ev.get("predicted_return", ev.get("model_signal"))
                    if sig is None:
                        sig = ev.get("excess_return", 0.0)  # weaker proxy
                    direction = "long" if sig >= 0 else "short"
                    score = abs(sig)
                    ranked.append((score, ei, direction, sig))
                ranked.sort(key=lambda x: -x[0])
                picks = ranked[:min(5, len(day_events))]
                n_fb = len(picks)
                if n_fb >= 3:
                    per_pct = 0.75 / n_fb
                    for score, ei, direction, sig in picks:
                        event = day_events[ei]
                        stake = round(bankroll * per_pct, 2)
                        if stake < 0.50 or stake > ts["bankroll"]:
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
                            "event_idx": ei + 1,
                            "ticker": event.get("ticker", "SPY"),
                            "direction": direction,
                            "event_type": event.get("event_type", ""),
                            "agency": event.get("agency", ""),
                            "thesis": f"smart post-filter (model signal {sig:+.3f})",
                            "pct": round(per_pct, 4),
                            "stake": stake,
                            "confidence": min(0.75, 0.40 + score * 5),
                            "excess_return": event["excess_return"],
                            "pnl_pct": round(pnl_pct, 4),
                            "won": won,
                            "profit": profit,
                            "source": "fallback-smart-post",
                        })
                    day_log["cash_held_pct"] = 1.0 - (n_fb * per_pct)
                    day_log["cash_rationale"] = "smart post-filter (direction from model signal)"
                    day_log["day_strategy"] = day_log.get("day_strategy") or f"post-filter: {n_fb} top-signal events"

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
            day_idx=day_idx,
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
        _fleet_best_live = max(state[t]["bankroll"] for t in state)
        _leader_live = max(state, key=lambda t: state[t]["bankroll"])
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
                # Collective experiment (2026-04-17)
                "season_target": SEASON_TARGET,
                "fleet_best_bankroll": round(_fleet_best_live, 2),
                "fleet_leader": _leader_live,
                "season_progress_pct": round((_fleet_best_live / SEASON_TARGET) * 100.0, 4),
                "council_plan": day_council_plan,
                "rogue_this_day": {t: r for t, r in day_rogue_state.items() if r["is_rogue"]},
            }
        # Persist EVERY day — state (resume) + per-day decisions file (audit).
        _save_state_to_disk(_experiment_state)
        _save_logs_to_disk()
        _day_logs_for_hub = {
            tid: _agent_logs[tid][-1]
            for tid in TRADERS if _agent_logs.get(tid) and _agent_logs[tid]
            and _agent_logs[tid][-1].get("date") == day_date
        }
        if _day_logs_for_hub:
            _push_day_decisions_to_hub(
                day_idx=day_idx, day_date=day_date, n_events=len(day_events),
                day_logs_by_agent=_day_logs_for_hub,
                day_council_plan=day_council_plan,
                day_rogue_state=day_rogue_state,
            )

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
    # ── Collective experiment (2026-04-17) ──
    with _state_lock:
        _agents = _experiment_state.get("agents", {}) if _experiment_state else {}
    if _agents:
        _fleet_best = max(a.get("bankroll", 0.0) for a in _agents.values())
        _leader = max(_agents, key=lambda t: _agents[t].get("bankroll", 0.0))
    else:
        _fleet_best = STARTING_CAPITAL
        _leader = None
    state["season_target"] = SEASON_TARGET
    state["fleet_best_bankroll"] = round(_fleet_best, 2)
    state["fleet_leader"] = _leader
    state["season_progress_pct"] = round((_fleet_best / SEASON_TARGET) * 100.0, 4)
    state["council_plan_count"] = len(_council_plans)
    state["latest_council_summary"] = (
        list(_council_plans.values())[-1].get("council_summary", "") if _council_plans else ""
    )
    state["rogue_events_total"] = len(_rogue_events)
    state["rogue_events_recent"] = _rogue_events[-10:]
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


@api.get("/api/axelrod-log")
async def api_axelrod_log(day: int = None, since: int = None):
    """Axelrod Mech C export — serves the per-day post-mortem dataset used as
    the primary dataset for the Axelrod-LLM paper (§6 results).

    Logs are written by write_axelrod_log to AXELROD_LOG_DIR/day-NNN.jsonl.
    Space /tmp is ephemeral, so this endpoint is the canonical way for the VM
    to pull the log into data/arena/axelrod-log/ for version-controlled analysis.

    Params:
      ?day=N      — return only day-N as a list of rows
      ?since=N    — return all days with day_idx >= N
      (no params) — index: list available days with row counts
    """
    try:
        if not AXELROD_LOG_DIR.exists():
            return JSONResponse({"status": "no_data", "message": "axelrod log dir not created yet"})
        files = sorted(AXELROD_LOG_DIR.glob("day-*.jsonl"))
        if not files:
            return JSONResponse({"status": "no_data", "days": []})

        def _read(fp):
            rows = []
            with fp.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue
            return rows

        if day is not None:
            fp = AXELROD_LOG_DIR / f"day-{int(day):03d}.jsonl"
            if not fp.exists():
                return JSONResponse({"status": "not_found", "day": day}, status_code=404)
            return JSONResponse({"day_idx": int(day), "rows": _read(fp)})

        if since is not None:
            out = []
            for fp in files:
                try:
                    idx = int(fp.stem.split("-")[1])
                except Exception:
                    continue
                if idx >= int(since):
                    out.append({"day_idx": idx, "rows": _read(fp)})
            return JSONResponse({"since": int(since), "days": out, "n_days": len(out)})

        index = []
        for fp in files:
            try:
                idx = int(fp.stem.split("-")[1])
            except Exception:
                continue
            rows = _read(fp)
            if not rows:
                continue
            index.append({
                "day_idx": idx,
                "date": rows[0].get("date"),
                "n_rows": len(rows),
            })
        return JSONResponse({"n_days": len(index), "index": index})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@api.get("/paper")
async def serve_paper():
    """Serve the Axelrod-LLM research paper inline (not as download)."""
    from fastapi.responses import HTMLResponse
    paper_path = Path(__file__).parent / "paper.html"
    if paper_path.exists():
        return HTMLResponse(content=paper_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Paper not yet generated</h1><p>Run md_to_html.py to build paper.html</p>", status_code=404)


# Mount FastAPI alongside Gradio
app = gr.mount_gradio_app(api, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
