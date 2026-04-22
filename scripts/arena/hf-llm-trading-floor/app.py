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
import math

# ── LANGFUSE OBSERVABILITY (non-blocking — never delays TF startup) ────────
_langfuse = None
_langfuse_errors: List[str] = []
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
    Treats |edge| as a test statistic under H0: edge=0. With ~91 categories
    derived from Normal CDF, the SE of each derived edge is ~0.03-0.05.
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
_started_utc: Optional[str] = None  # 2026-04-22: set on first run_experiment entry, exposed via /api/status
_common_knowledge: Dict[str, str] = {}  # Axelrod CK[D]: day_date → formatted block for day D+1
_sacrificial_assignments: Dict[str, str] = {}  # Axelrod Mech B: tid → archetype for NEXT day
_used_archetypes: Dict[str, set] = defaultdict(set)  # Axelrod Mech B: tid → set of archetypes tried (per-agent fallback)
_society_archetypes_by_day: Dict[str, set] = {}  # Axelrod Mech B: day_date → society-wide archetypes assigned that day
_challenge_assignments: Dict[str, int] = {}  # Axelrod Mech B: mid-tier tid → leaderboard rank
STATE_PATH = Path("/tmp/tf-state.json")   # Local (ephemeral /tmp) — cheap quick-save
LOGS_PATH = Path("/tmp/tf-agent-logs.json")
AXELROD_LOG_DIR = Path("/tmp/axelrod-log")  # Axelrod Mech C: per-day post-mortem dataset

# ── HUB PERSISTENCE (2026-04-17) ────────────────────────────────────────────
# HF Space /tmp is wiped on every restart → we lose all decisions + bankrolls.
# Fix: every N days, push a runtime snapshot (state + agent_logs + council
# plans) to the Space's OWN repo under data/runtime/. On startup, if /tmp is
# empty, download that snapshot. That survives all restarts for free.
HF_REPO_ID = os.environ.get("SPACE_ID") or "LBJLincoln26/nba-llm-trading-floor"
HF_HUB_TOKEN = os.environ.get("HF_WRITE_TOKEN") or os.environ.get("NOMOS_HF_TOKEN") or os.environ.get("HF_TOKEN")
HUB_SNAPSHOT_EVERY_DAYS = 3  # commit snapshot every 3 days (balances git noise vs recovery granularity)
try:
    from huggingface_hub import HfApi, hf_hub_download
    _hub_api = HfApi(token=HF_HUB_TOKEN) if HF_HUB_TOKEN else None
except Exception:
    _hub_api = None
    hf_hub_download = None

# ── COLLECTIVE EXPERIMENT (2026-04-17) ─────────────────────────────────────
# Common goal: one agent hits $1M by season end. Shared plan each day via
# LLM moderator; agents only defect if their bankroll crashes or a peer
# gets greedy (>$250K). Exposed on /api/status.
SEASON_TARGET = 1_000_000.0          # common goal — any agent reaching this wins the season
STARTING_CAPITAL = 100.0             # per-agent seed (pre multi-season compound)
# 2026-04-21 SWISH — PQTF-doctrine relaxation (project_tf_coalition_mandatory_apr18).
# Old rogue-drawdown gate = 0.25×STARTING_CAPITAL → $25. With fleet avg ~$27 after the
# $1475→$461 (-69%) bleed, ~70% of 17 agents were silenced into preservation mode
# (MIN_DEPLOY 50%, moneylines only, 5% bet cap) every tick → could not recover →
# frozen-gate death spiral. Same bug class as PQTF $20 hardcoded for $100K era
# (fixed 2026-04-19, commit 87d12e2f3). Relaxing to ABSOLUTE $20 survival floor —
# mistral-ministral's $10K→$1.3K→$14K swing proved agents DO recover when given room.
ABS_SURVIVAL_FLOOR = 20.0            # $20 absolute — only gate, no peak-relative strangle
ROGUE_DRAWDOWN_THRESHOLD = ABS_SURVIVAL_FLOOR / STARTING_CAPITAL  # = 0.20 for legacy callers
ROGUE_GREED_THRESHOLD = 250_000.0    # any peer > $250K → greed rogue
COUNCIL_MIN_COMMIT_PER_AGENT = 0.50  # each agent commits ≥50% of bankroll daily
# Peak-drawdown guard (2026-04-18 post-mortem finding): mistral-ministral peaked
# at $10,098 on day 12 then lost 78.7% to $2,149. Root cause: prompt told drawdown
# agents to chase variance. Fix: when bankroll < PEAK_DRAWDOWN_GUARD × best_bankroll,
# force capital-preservation mode (half-Kelly cap, no parlays, deploy floor waived).
# Prompt-mutator overrides (2026-04-19) — scripts/arena/prompt_mutator.py writes
# data/prompts/overrides.json from priority-1 post-mortem proposals. Space Dockerfile
# copies overrides.json to /app/data/prompts/overrides.json; repo layout falls back.
def _load_prompt_override(fleet: str = "nba", sim_date: str = None) -> str:
    """Load prompt-mutator override + YouTube market narrative for this fleet.

    sim_date (ISO "YYYY-MM-DD"): simulated trading day. When provided (NBA+POL are
    sim-dated Oct 2025 - Feb 2026), the narrative is rebuilt from
    `market_narrative_videos` filtered to `published_at <= sim_date`, preventing
    lookahead leakage flagged 2026-04-21 by INTERNAL AFFAIRS (152/229 videos newer
    than sim window). When None (ITF/PQTF are live-dated) we fall back to the flat
    `market_narrative`. Section-level `market_narrative_disabled` is an audit
    kill-switch — suppresses the narrative block entirely.
    """
    import os as _os, json as _json
    candidates = [
        "/app/data/prompts/overrides.json",
        "/home/user/app/data/prompts/overrides.json",
        _os.path.join(_os.path.dirname(__file__), "..", "..", "..", "data", "prompts", "overrides.json"),
    ]
    for p in candidates:
        try:
            if not _os.path.exists(p):
                continue
            with open(p) as fh:
                ov = _json.load(fh)
            section = (ov.get(fleet) or {})
            rule = section.get("current_text") or ""
            v = section.get("current_version") or "?"

            narrative_block = ""
            if not section.get("market_narrative_disabled"):
                struct = section.get("market_narrative_videos")
                if sim_date and struct:
                    cutoff = (sim_date or "")[:10]
                    kept = [sv for sv in struct if (sv.get("published_at") or "")[:10] <= cutoff]
                    if kept:
                        header = f"YouTube narrative digest ({len(kept)} videos, sim_date={cutoff}):"
                        body = "\n".join(sv.get("line", "") for sv in kept[:8])
                        narrative_block = header + "\n" + body
                elif not sim_date:
                    narrative_block = section.get("market_narrative") or ""

            mvc = section.get("manual_videos_count") or 0
            out = ""
            if rule:
                out += f"\n=== PROMPT MUTATOR OVERRIDE ({v}) ===\n{rule}\n=== END OVERRIDE ===\n"
            if narrative_block:
                out += f"\n=== YOUTUBE MARKET NARRATIVE ({mvc} tracked videos, 22 channels) ===\n{narrative_block}\n=== END NARRATIVE ===\n"
            if out:
                return out
        except Exception:
            continue
    return ""

# 2026-04-21 SWISH — RETIRED: peak-relative guard was the frozen-gate death spiral.
# After $1475 peak → $461 (-69%), every agent was 69% off peak → silenced forever.
# Removed from executable path. Kept as 0.0 so any legacy reference no-ops.
PEAK_DRAWDOWN_GUARD = 0.0            # DISABLED — absolute ABS_SURVIVAL_FLOOR is the only gate
PRESERVATION_MAX_DEPLOY = 0.50       # cap daily deploy at 50% while preserving (only if <$20)
PRESERVATION_MAX_BET_PCT = 0.05      # cap any single bet at 5% bankroll (only if <$20)
SINGLE_DAY_WIPEOUT_THRESHOLD = 0.40  # >40% single-day loss → forced cash next day
COLLISION_MAX_AGENTS = 3             # max agents sharing same game+category in one day
# 2026-04-20 SWISH — fleet-wide post-council wipe dropped avg bankroll to ~$4.50.
# Original $5 bankrupt gate (5% of $100 start) now silences 16/17 agents every tick
# → death spiral: can't bet → can't recover → starves forever. Same bug class as
# PQTF $20 survival floor hardcoded for $100K era (fixed 2026-04-19). Drop to
# $0.50 (same 0.5% proportion to current fleet avg) so agents can trade the long
# tail out of ruin. BOSS report: NBA -$70.75 / 24h, 7 starved. RC = this gate.
BANKRUPT_THRESHOLD = 0.50            # below this = truly bust (was 5.0; proportional to post-wipe $4.50 fleet avg)

def _tiered_risk(bankroll: float) -> dict:
    """Bankroll-tier aggression (gambler's ruin doctrine, 2026-04-18 → 2026-04-19 $1M push).
    Low bankrolls deploy HARDER (higher Kelly, higher per-bet floor) to compound
    out of the hole. High bankrolls diversify across more categories to harvest
    small edges. No per-bet CAP below Kelly — cap is set ABOVE Kelly at tier cap.
    Targets picked to saturate NBA's ~100+ bet categories across ~10 games/day.

    2026-04-19 extension: added CHAMPION/MOONSHOT/PROVEN tiers above $500, $2K, $10K.
    PQTF run hit $244K on mistral-large via proven-edge compounding; NBA TF needs the
    same ceiling to actually reach the $1M collective goal. Winners above 5× starting
    get bet_cap raised 0.10 → 0.15-0.25 and kelly_mult 0.5 → 0.65-0.85. min_allocs
    also relaxed at top tiers so agents can concentrate into their best picks."""
    # Post-mortem 2026-04-19 (51-day NBA TF): winners used flat-stake wide coverage
    # with strict EV threshold and half-Kelly. Losers used high-conviction single plays
    # that wiped 60-70% in a single day. New doctrine: tighter MIN_EDGE (0.04 blocks
    # marginal DIVERGE bets), capped KELLY_MULT (0.5× max), lower per-bet caps.
    # 2026-04-20 SWISH: RAISED min_edge 0.04 → 0.06 on all survival tiers.
    # Post-mortem: 128 days, qwen-quant 7W/37L = 16% WR, every agent crashed to $3-7,
    # uniform-fallback (selfhost-gemma3, llm_ok=0) outperformed every LLM agent.
    # RCA: fleet-best Brier 0.22073 vs random 0.25 = 0.029 Brier-signal envelope.
    # Old MIN_EDGE=0.04 sat INSIDE that noise envelope. Agents were forced to stake
    # on "edges" smaller than the model's own calibration error. At 0.06 every
    # claimed edge must be >2× the model's demonstrable information gain — forces
    # agents to PASS when only noise is visible, rather than parrot the floor.
    if bankroll < 25.0:
        return {"deploy_floor": 0.90, "bet_floor": 0.04, "bet_cap": 0.20,
                "min_edge": 0.06, "kelly_mult": 0.5,
                "min_allocs": 35, "min_cats": 15, "min_games": 8}
    if bankroll < 50.0:
        return {"deploy_floor": 0.80, "bet_floor": 0.03, "bet_cap": 0.15,
                "min_edge": 0.06, "kelly_mult": 0.5,
                "min_allocs": 30, "min_cats": 12, "min_games": 7}
    if bankroll < 100.0:
        return {"deploy_floor": 0.70, "bet_floor": 0.02, "bet_cap": 0.12,
                "min_edge": 0.06, "kelly_mult": 0.5,
                "min_allocs": 25, "min_cats": 10, "min_games": 6}
    if bankroll < 500.0:
        return {"deploy_floor": 0.60, "bet_floor": 0.015, "bet_cap": 0.10,
                "min_edge": 0.06, "kelly_mult": 0.5,
                "min_allocs": 20, "min_cats": 8, "min_games": 5}
    # PROVEN tier: 5-20× starting, press edges harder
    if bankroll < 2000.0:
        return {"deploy_floor": 0.65, "bet_floor": 0.02, "bet_cap": 0.15,
                "min_edge": 0.04, "kelly_mult": 0.65,
                "min_allocs": 18, "min_cats": 8, "min_games": 5}
    # MOONSHOT tier: 20-100× starting, real edge demonstrated
    if bankroll < 10000.0:
        return {"deploy_floor": 0.65, "bet_floor": 0.025, "bet_cap": 0.20,
                "min_edge": 0.05, "kelly_mult": 0.75,
                "min_allocs": 15, "min_cats": 6, "min_games": 4}
    # CHAMPION tier: 100×+ starting — on the path to $1M
    return {"deploy_floor": 0.65, "bet_floor": 0.03, "bet_cap": 0.25,
            "min_edge": 0.05, "kelly_mult": 0.85,
            "min_allocs": 12, "min_cats": 5, "min_games": 3}

_council_plans: Dict[str, dict] = {} # day_date → plan dict (strategies, categories, per-agent %, summary)
_rogue_events: List[Dict] = []       # append-only audit: {day, tid, reason, detail}

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
COLLECTIVE_MISSION = (
    "=== COLLECTIVE MISSION (2026-04-17, binding) ===\n"
    "You are ONE of 17 LLM agents sharing a society bankroll. All 17 agents see the SAME data: "
    "1257 games, 100+ betting categories per game, full odds + standings + forms + player stats + "
    "model predictions + peer bankrolls + peer allocations + post-mortem logs.\n"
    "COMMON GOAL: ONE of us reaches $1,000,000 bankroll by season end. That agent's win counts "
    "as a collective win — help each other reach it. Individual greed (>$250K while peers dying) "
    "triggers a DEFECT rogue permission.\n"
    "DEPLOY RULE (hard): ≥75% of your bankroll MUST be deployed EVERY DAY. ≥3 allocations EVERY DAY. "
    "Holding >25% cash violates the collective goal. Pick from the FULL 100+ category menu — "
    "moneylines, spreads, totals, halves, quarters, alt-lines, team totals, props. Use breadth.\n"
    "COLLABORATION STACK: (1) morning council plan (qwen-235B moderator) specifies focus_strategies + "
    "focus_categories + per-agent commit. (2) Pact proposals let 2 agents bet the same game+category. "
    "(3) Axelrod canon strategy assigned per agent. (4) Post-mortem log visible to all. "
    "(5) Sacrificial rotation reassigns a losing agent to an archetype the society lacks.\n"
    "=== END COLLECTIVE MISSION ===\n\n"
)

AXELROD_CANON = (
    COLLECTIVE_MISSION +
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
    "\n=== DMAD ANTI-CONSENSUS GATE (2026-04-21, binding) ===\n"
    "Cross-TF audit 2026-04-21 flagged NBA lockstep at 79–100% on days 62–63 (16/17 agents holding "
    "identical picks). This collapses ensemble accuracy ~18% (DMAD, Du 2023) and defeats the 17-agent "
    "point of this floor. HARD RULE (overrides breadth/deploy optimizations):\n"
    "  - At least ONE of your top-3 allocations today MUST be a bet (game_idx+category+side tuple) "
    "    that is NOT present in the peer_allocations block of COMMON_KNOWLEDGE from yesterday.\n"
    "  - If every top-tier edge is already crowded (≥10/17 peers), you MUST dig deeper into the "
    "    100+ category menu (halves, quarters, team totals, alt-lines, props) to find a non-crowded edge "
    "    with ≥0.03 edge. Breadth is the anti-lockstep tool.\n"
    "  - Annotate your non-consensus bet with tag 'DMAD_DIVERGE' in allocation.notes. Pure follow-the-herd "
    "    picks with no DMAD_DIVERGE will be flagged in the post-mortem.\n"
    "=== END DMAD ANTI-CONSENSUS GATE ===\n"
)

# Axelrod Mech D — cooperation ledger
# _cooperation_pacts[(tid_a, tid_b, day_date)] = {"game_idx": int, "category": str, "honored": bool}
_cooperation_pacts: Dict[str, dict] = {}
# _reputation[tid] = {"pact_honored": int, "pact_broken": int}
_reputation: Dict[str, Dict[str, int]] = defaultdict(lambda: {"pact_honored": 0, "pact_broken": 0})

# --- Axelrod-Python real-library engine (Mech D+) -----------------------------
# axelrod-python ships ~240 canonical strategies from the 1980 Axelrod tournament
# through modern evolution. We assign each trader one canon strategy and consult
# it each day: it consumes the pact history vs each peer and returns C (cooperate)
# or D (defect) as a hard bias injected into the LLM prompt. The LLM can override
# for bet sizing but must honor the cooperate/defect signal on PACT decisions.
try:
    import axelrod as axl
    _AXELROD_OK = True
except Exception:
    axl = None
    _AXELROD_OK = False

# Per-trader canonical strategy (matched to trader personality — NICE/RETALIATORY/
# FORGIVING/CLEAR strategies go to cooperative personalities; harsher go to contrarian).
AXELROD_STRATEGIES = {
    "qwen-quant":        "TitForTat",           # nice, retaliatory, forgiving (Rapoport 1980)
    "qwen-arb":          "Grudger",             # grim-trigger (punishes once forever)
    "llama-contra":      "SuspiciousTitForTat", # defects first, then TFT (contrarian)
    "gemini-anl":        "TitFor2Tats",         # forgives one defection (analytical/patient)
    "gemini-tact":       "TwoTitsForTat",       # doubles retaliation (tactical/aggressive)
    "mistral-large":     "WinStayLoseShift",    # Pavlov (Nowak-Sigmund 1993)
    "mistral-medium":    "GenerousTitForTat",   # ~10% forgiveness (escape noise spirals)
    "mistral-small":     "Cooperator",          # always cooperate (risk-averse)
    "mistral-nemo":      "Defector",            # always defect (aggressive)
    "mistral-ministral": "FirmButFair",         # cooperate unless suckered (theoretical)
    "nemotron-120b":     "Adaptive",            # long-run learner (chainthought)
    "selfhost-qwen4b":   "Tullock",             # probabilistic nice (disciplined, ex-gemma4-selfhost)
    "nvidia-minimax":    "Prober",              # probe then adapt (decisive long-context)
    "nvidia-llama70":    "Gradual",             # gradual retaliation (swing/balanced)
    "selfhost-gemma3":   "Handshake",           # mutual-cooperation probe (analytical)
    "selfhost-qwen06":   "Cooperator",          # always cooperate, tiny model (conservative)
    "selfhost-dolphin3": "Pavlov",              # win-stay/lose-shift (uncensored, adaptive)
}
# Per-trader instantiated strategy object (populated on first call)
_axelrod_agents: Dict[str, object] = {}

def _axelrod_make(tid: str):
    """Return an instantiated axelrod strategy object for trader `tid`.
    Caches in _axelrod_agents. Returns None if axelrod-python unavailable or
    strategy name is invalid."""
    if not _AXELROD_OK:
        return None
    if tid in _axelrod_agents:
        return _axelrod_agents[tid]
    name = AXELROD_STRATEGIES.get(tid, "TitForTat")
    # Resolve class by name (handles "Cycler CCD" → "CyclerCCD" etc.)
    cls_name = name.replace(" ", "")
    cls = getattr(axl, cls_name, None) or getattr(axl, name, None) or axl.TitForTat
    try:
        obj = cls()
        _axelrod_agents[tid] = obj
        return obj
    except Exception:
        return None

def _axelrod_advice(tid: str, peer_tid: str) -> Dict[str, str]:
    """Consult trader `tid`'s axelrod strategy on whether to COOPERATE/DEFECT
    against `peer_tid` today. Reads the shared _cooperation_pacts ledger as
    the move history (pact honored = C, pact broken = D), re-runs the strategy
    from the start (stateless per-peer — cheap, ~200 games worth of history).
    Returns {"move": "C"|"D", "strategy": "TitForTat", "reason": "..."}."""
    if not _AXELROD_OK:
        return {"move": "C", "strategy": "unavailable",
                "reason": "axelrod-python not installed"}
    self_agent = _axelrod_make(tid)
    peer_agent = _axelrod_make(peer_tid)
    if self_agent is None or peer_agent is None:
        return {"move": "C", "strategy": AXELROD_STRATEGIES.get(tid, "TitForTat"),
                "reason": "strategy init failed"}
    # Reset and replay history up through yesterday from _cooperation_pacts
    try:
        self_agent.reset()
        peer_agent.reset()
        # Extract ordered (self_move, peer_move) history from pacts ledger
        pair_keys = [
            k for k in _cooperation_pacts.keys()
            if (k.startswith(f"{tid}|{peer_tid}|") or k.startswith(f"{peer_tid}|{tid}|"))
        ]
        pair_keys.sort()  # date-ordered (keys include YYYY-MM-DD suffix)
        for k in pair_keys[-50:]:  # cap at last 50 interactions
            pact = _cooperation_pacts[k]
            honored = pact.get("honored", False)
            move = axl.Action.C if honored else axl.Action.D
            # Replay both agents' view of the history
            self_agent.history.append(move)
            peer_agent.history.append(move)
        # Strategy picks next move conditioned on history
        next_move = self_agent.strategy(peer_agent)
        move_str = "C" if next_move == axl.Action.C else "D"
        return {
            "move": move_str,
            "strategy": AXELROD_STRATEGIES.get(tid, "TitForTat"),
            "reason": f"{len(pair_keys)} prior pacts with {peer_tid}",
        }
    except Exception as e:
        return {"move": "C", "strategy": AXELROD_STRATEGIES.get(tid, "TitForTat"),
                "reason": f"strategy error: {str(e)[:60]}"}

def _axelrod_advice_block(tid: str, active_peers: List[str]) -> str:
    """Build a prompt suffix telling trader `tid` what each of ~3 randomly
    sampled peers' axelrod strategies suggest today. This is the 'hard bias'
    the LLM must factor into PACT propose/honor decisions."""
    if not _AXELROD_OK or not active_peers:
        return ""
    # Sample up to 3 peers for prompt length
    peers = list(active_peers)[:3]
    advice_lines = []
    for peer in peers:
        a = _axelrod_advice(tid, peer)
        advice_lines.append(
            f"  - vs {peer}: strategy={a['strategy']} → suggests {a['move']} ({a['reason']})"
        )
    if not advice_lines:
        return ""
    return (
        "\n=== AXELROD MECH D — CANON STRATEGY ADVICE (from axelrod-python library, ~240 strategies) ===\n"
        f"Your assigned canon strategy: {AXELROD_STRATEGIES.get(tid, 'TitForTat')}\n"
        "Today's advice against 3 peers (based on real pact history):\n"
        + "\n".join(advice_lines) +
        "\nHonor the C (cooperate) suggestions as PACT proposals; decline D (defect) peers."
        "\n=== END AXELROD ADVICE ===\n"
    )

GATEWAY_URL = os.environ.get("GATEWAY_URL", "").rstrip("/")

# DMAD (ICLR 2025, OpenReview t6QHYUOQL7) — structurally distinct reasoning templates per agent.
# Each trader MUST reason via its own template; prevents groupthink across Qwen/Llama/Gemini/Mistral.
REASONING_TEMPLATES = {
    "qwen-quant":        "REASONING TEMPLATE (DMAD): EXPECTED-UTILITY MAXIMIZATION. Compute E[V] = (p_win × win_amount) − ((1−p_win) × stake). Bet iff E[V]/stake > 0.05.",
    "qwen-arb":          "REASONING TEMPLATE (DMAD): CROSS-MARKET ARBITRAGE. Scan line discrepancies vs implied prob > 1.5σ. Pick top 3 mispriced sides and diversify across them (collective goal forbids sitting out).",
    "llama-contra":      "REASONING TEMPLATE (DMAD): CONTRARIAN INVERSION. Start from public prior, argue the OPPOSITE with 3 reasons. Bet only if inversion survives.",
    "gemini-anl":        "REASONING TEMPLATE (DMAD): FIRST-PRINCIPLES DECOMPOSITION. List the 3 most decisive factors, weight each ∈[0,1], multiply to get signal.",
    "gemini-tact":       "REASONING TEMPLATE (DMAD): TACTICAL TIMING. Focus on line movement + steam. Even absent steam, deploy ≥3 bets on highest-tempo-edge games (collective 75% deploy rule).",
    "mistral-large":     "REASONING TEMPLATE (DMAD): SCENARIO MAJORITY. Enumerate 5 scenarios, assign P to each, bet iff ≥3 align.",
    "mistral-medium":    "REASONING TEMPLATE (DMAD): DIVERSIFIED PORTFOLIO. Split across 2-3 uncorrelated games. Never all-in one game.",
    "mistral-small":     "REASONING TEMPLATE (DMAD): RISK-AVERSE STRESS TEST. Assume worst-case; bet only if still +EV in worst case.",
    "mistral-nemo":      "REASONING TEMPLATE (DMAD): MOMENTUM CHASE. Bet hardest on last-5 form streaks ≥ 4-1.",
    "mistral-ministral": "REASONING TEMPLATE (DMAD): THEORETICAL MODEL. Mental logistic regression from 3 coefficients → compute p.",
    "nemotron-120b":     "REASONING TEMPLATE (DMAD): EXPLICIT 7-STEP CoT. context → hypothesis → evidence → counter → weight → conclusion → bet.",
    "selfhost-qwen4b":   "REASONING TEMPLATE (DMAD): 4-RULE CHECKLIST. (1) edge > 0.05 (2) bankroll > $30 (3) not same game as yesterday (4) category in top-3. Bet iff ALL pass.",
    "nvidia-minimax":    "REASONING TEMPLATE (DMAD): LONG-CONTEXT SCAN. Ingest ALL 100+ category odds + season form + last-5 streaks. Rank by |p_model − p_implied|. Pick top 2-3 mispricings.",
    "nvidia-llama70":    "REASONING TEMPLATE (DMAD): EV-THRESHOLD SWING. For each category compute EV = p_model × payout − 1. Bet top 3 if EV > 0.05; else cash.",
    "selfhost-gemma3":   "REASONING TEMPLATE (DMAD): WEIGHTED FACTOR MODEL. 3 factors {form, rest, home}. Weights {0.4, 0.3, 0.3}. Bet only if weighted signal > 0.6.",
    "selfhost-qwen06":   "REASONING TEMPLATE (DMAD): WIDE FLAT-STAKE. Spread ≥5 tiny flat bets (1-3% each) across any of the 100+ categories. Any edge >3% qualifies.",
    "selfhost-dolphin3": "REASONING TEMPLATE (DMAD): PAVLOV WIN-STAY/LOSE-SHIFT. After a winning bet, repeat the same category. After a loss, switch to the opposite side or different category. No overthinking.",
}

def get_stackelberg_leader(state: dict) -> Optional[str]:
    """Stackelberg (arXiv 2507.09407): yesterday's top-bankroll trader is today's leader."""
    active = [(tid, st.get("bankroll", 0)) for tid, st in state.items()
              if isinstance(st, dict) and tid in TRADERS and st.get("bankroll", 0) > BANKRUPT_THRESHOLD]
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
    """Persist to /tmp (fast, ephemeral) + HF Hub state.json (every day, for
    resume). Per-day decision files are pushed separately by
    _push_day_decisions_to_hub() after each day completes."""
    try:
        STATE_PATH.write_text(json.dumps(state, default=str))
    except Exception:
        pass
    # Always push state.json so resume sees latest bankrolls/day_idx.
    if _hub_api and int(state.get("days_processed", 0)) > 0:
        _push_state_to_hub(state)

def _push_state_to_hub(state: dict):
    """Lightweight state snapshot (for resume). One file, overwritten daily."""
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

def _push_day_decisions_to_hub(day_idx: int, day_date: str, n_games: int,
                                day_logs_by_agent: Dict[str, dict],
                                day_council_plan: Optional[dict] = None,
                                day_rogue_state: Optional[dict] = None):
    """Commit one file per experiment-day: data/decisions/day-XXX.json.
    Contains full per-agent decision trail (rationale per game, category,
    bankroll sizing, council alignment) + day's council plan. Councils/depts
    read these back to aggregate & analyze."""
    if not _hub_api:
        return
    try:
        payload = {
            "day_idx": day_idx,
            "date": day_date,
            "n_games": n_games,
            "n_agents": len(day_logs_by_agent),
            "council_plan": day_council_plan,
            "rogue_state": day_rogue_state,
            "agents": day_logs_by_agent,  # tid -> day_log with allocations + rationale
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
    """Load persisted state. Prefers local /tmp (fastest), falls back to the
    last Hub snapshot (survives Space restarts)."""
    try:
        if STATE_PATH.exists():
            return json.loads(STATE_PATH.read_text())
    except Exception:
        pass
    # /tmp empty → try Hub. Happens on every fresh container start.
    if hf_hub_download and HF_HUB_TOKEN:
        try:
            p = hf_hub_download(
                repo_id=HF_REPO_ID, filename="data/runtime/state.json",
                repo_type="space", token=HF_HUB_TOKEN,
            )
            state = json.loads(Path(p).read_text())
            print(f"[hub-persist] restored state from hub: day {state.get('days_processed',0)}/{state.get('days_total',0)}")
            # Also restore agent logs + council plans (best-effort)
            for fname, target in [("agent_logs.json", _agent_logs), ("council_plans.json", _council_plans)]:
                try:
                    p2 = hf_hub_download(
                        repo_id=HF_REPO_ID, filename=f"data/runtime/{fname}",
                        repo_type="space", token=HF_HUB_TOKEN,
                    )
                    data = json.loads(Path(p2).read_text())
                    if isinstance(target, dict):
                        target.clear(); target.update(data)
                    else:  # defaultdict list
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
    """Persist agent logs (local /tmp + HF Hub so /api/day-decisions survives
    container preempt — bug fix 2026-04-18)."""
    try:
        payload = json.dumps(dict(_agent_logs), default=str)
        LOGS_PATH.write_text(payload)
    except Exception:
        return
    if _hub_api:
        try:
            _hub_api.upload_file(
                path_or_fileobj=payload.encode("utf-8"),
                path_in_repo="data/runtime/agent_logs.json",
                repo_id=HF_REPO_ID, repo_type="space",
                commit_message="runtime: agent_logs snapshot",
            )
        except Exception as e:
            print(f"[hub-persist] agent_logs push failed: {e}")
        try:
            cp_payload = json.dumps(dict(_council_plans), default=str).encode("utf-8")
            _hub_api.upload_file(
                path_or_fileobj=cp_payload,
                path_in_repo="data/runtime/council_plans.json",
                repo_id=HF_REPO_ID, repo_type="space",
                commit_message="runtime: council_plans snapshot",
            )
        except Exception as e:
            print(f"[hub-persist] council_plans push failed: {e}")

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
        "max_tokens": 2000,
        "rpm": 30,
    },
    "cerebras:llama3.1-8b": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "llama3.1-8b",
        "key_env": "CEREBRAS_API_KEY",
        "max_tokens": 2000,
        "rpm": 30,
    },
    # Google Gemini 3 Flash (key 2) — thinking model, needs big token budget +
    # thinkingBudget=0 or all tokens get eaten by thought traces.
    "google:gemini-3-flash": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent",
        "model": "gemini-3-flash-preview",
        "key_env": "GOOGLE_API_KEY_2",
        "max_tokens": 2500,
        "rpm": 14,
    },
    # Mistral la Plateforme (free tier — added 2026-04-14)
    "mistral:large": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-large-latest",
        "key_env": "MISTRAL_API_KEY",
        "max_tokens": 2000,
        "rpm": 20,
    },
    "mistral:medium": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-medium-latest",
        "key_env": "MISTRAL_API_KEY",
        "max_tokens": 2000,
        "rpm": 20,
    },
    "mistral:small": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-small-latest",
        "key_env": "MISTRAL_API_KEY",
        "max_tokens": 2000,
        "rpm": 20,
    },
    "mistral:nemo": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "open-mistral-nemo",
        "key_env": "MISTRAL_API_KEY",
        "max_tokens": 2000,
        "rpm": 20,
    },
    "mistral:ministral-8b": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "ministral-8b-latest",
        "key_env": "MISTRAL_API_KEY",
        "max_tokens": 2000,
        "rpm": 20,
    },
    # OpenRouter free models — diversify away from Mistral rate limits
    "openrouter:gemma-4-31b": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "google/gemma-4-31b-it:free",
        "key_env": "OPENROUTER_KEY_BARTOLI",
        "max_tokens": 2000,
        "rpm": 12,
    },
    "openrouter:gpt-oss-120b": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "openai/gpt-oss-120b:free",
        "key_env": "OPENROUTER_KEY_BARTOLI",
        "max_tokens": 2000,
        "rpm": 12,
    },
    # OpenRouter Nemotron 120B free — only free-tier model that reliably responds
    # (verified 2026-04-15: qwen3-80b / glm-4.5-air / llama-3.3-70b all 429 across 3 keys).
    "openrouter:nemotron-120b": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "nvidia/nemotron-3-super-120b-a12b:free",
        "key_env": "OPENROUTER_KEY_BARTOLI",
        "max_tokens": 2000,
        "rpm": 12,
    },
    # Self-hosted CPU LLM on Nomos42 HF Space — no auth, no quota.
    # 2026-04-17 ROUTE: Nomos42/nomos-cpu-gemma4 had 14 errors / 0 successes (gemma-4 GGUF load failed)
    # → switched to Nomos42/nomos42-llm-cpu (Qwen 2.5-1.5B, verified ready + responding)
    # cpu-basic throughput measured ~3 tok/s (57s for 18 tokens). 120 tokens ≈ 40s → fits 180s budget.
    # Endpoint is NOT OpenAI-compat: POST /api/decide {system, user, max_tokens} -> {text}.
    "selfhost:cpu-gemma4": {
        "url": "https://nomos42-nomos42-llm-cpu.hf.space/api/decide",
        "model": "qwen2.5-1.5b-instruct-q4_k_m",
        "key_env": "SELFHOST_NOOP",  # sentinel — no auth needed
        "max_tokens": 120,  # tight budget so call finishes before fallback fires
        "rpm": 6,
    },
    # 2026-04-17 FIX: 5 providers referenced by TRADERS but absent from PROVIDERS
    # (selfhost:qwen3-4b, selfhost:gemma-3-4b, selfhost:qwen3-0.6b, nvidia:minimax-m2.7,
    # nvidia:llama-3.3-70b) caused "unknown provider" → 100% fail rate on 5 agents.
    # Direct fallback now works even if gateway SSE times out.
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
    "nvidia:minimax-m2.7": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model": "minimaxai/minimax-m2.7",
        "key_env": "NVIDIA_API_KEY",
        "max_tokens": 2000,
        "rpm": 40,
    },
    "nvidia:minimax-m2.7-alt": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model": "minimaxai/minimax-m2.7",
        "key_env": "NVIDIA_API_KEY_2",
        "max_tokens": 2000,
        "rpm": 40,
    },
    "nvidia:llama-3.3-70b": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model": "meta/llama-3.3-70b-instruct",
        "key_env": "NVIDIA_API_KEY",
        "max_tokens": 2000,
        "rpm": 40,
    },
    "nvidia:nemotron-70b": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "key_env": "NVIDIA_API_KEY",
        "max_tokens": 2000,
        "rpm": 40,
    },
    # GitHub Models (free, reliable, Azure-backed — nuclear fallback)
    "github:gpt-4o-mini": {
        "url": "https://models.inference.ai.azure.com/chat/completions",
        "model": "gpt-4o-mini",
        "key_env": "GH_TOKEN",
        "max_tokens": 2000,
        "rpm": 30,
    },
    "github:llama-3.1-8b": {
        "url": "https://models.inference.ai.azure.com/chat/completions",
        "model": "meta-llama-3.1-8b-instruct",
        "key_env": "GH_TOKEN",
        "max_tokens": 2000,
        "rpm": 30,
    },
}

# ── AGENT DEFINITIONS (v3 — 10 personas across 3 providers, 2026-04-14) ──────
# Each agent gets a real distinct model where possible. Same model + different
# system prompt = DMAD-style distinct reasoning (Prediction Arena 2604.07355).
TRADERS = {
    # Cerebras Qwen 3 235B — heaviest reasoning model, 2 personas
    # 2026-04-17 FIX: Cerebras free tier returns 429 "queue_exceeded" under TF load → add fallbacks
    # 2026-04-20 SWITCHBOARD: cerebras:qwen-3-235b on llm-deadlist (broken).
    # qwen-quant silent 0/3d → promote mistral:large (PQTF #1 $244K) to primary.
    "qwen-quant":  {"name": "Qwen Quant 235B",   "provider": "mistral:large",         "personality": "quantitative", "risk_tolerance": 0.55,
                    "fallback_provider": "mistral:medium"},
    "qwen-arb":    {"name": "Qwen Arb 235B",     "provider": "cerebras:qwen-3-235b",  "personality": "arbitrage",    "risk_tolerance": 0.65,
                    "fallback_provider": "mistral:large"},
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
    # 2026-04-20 SWITCHBOARD: openrouter:gpt-oss-120b is NOT in gateway registry ("Model not in registry") → swap fallback to mistral:medium.
    # 2026-04-22 NBA-DEAD-REROUTE (day 35, llm_ok 8/35 = 23% degraded): mistral:small primary, cerebras:llama3.1-8b fallback.
    "mistral-nemo":     {"name": "Momentum Hunter",   "provider": "mistral:small",         "personality": "aggressive",   "risk_tolerance": 0.70,
                         "fallback_provider": "cerebras:llama3.1-8b"},
    # 2026-04-21 SWITCHBOARD v3 (NBA-bleed RCA): 6 github:* primaries were routing to
    # dead lanes (gateway stats show calls_fail=0 AND calls_ok=0 i.e. NEVER called —
    # github fallback chain is empty, so a single 429 returns None content).
    # Drop every github:* primary. Concentrate on the 7 providers that actually have
    # a fallback chain ending in cerebras: mistral:{large,medium,small}, cerebras:{qwen-235b,llama3.1-8b},
    # google:gemini-3-flash, nvidia:llama-3.3-70b, openrouter:nemotron-120b:free.
    # Load-spread 17 agents × 7 lanes ≈ 2.4 agents per lane (down from 6+ on cerebras).
    "mistral-ministral":{"name": "Ministral 8B",     "provider": "mistral:small",         "personality": "theoretical",  "risk_tolerance": 0.35,
                         "fallback_provider": "cerebras:llama3.1-8b"},
    # NEW 2026-04-15 — +1 NVIDIA Nemotron 120B (OpenRouter free, verified responsive)
    # 2026-04-21 SWITCHBOARD v3: promote openrouter:nemotron-120b:free as primary
    # (has full fallback chain incl cerebras); keep mistral:large fallback.
    # 2026-04-22 NBA-DEAD-REROUTE (day 35, llm_ok 4/35 = 11% DEAD): mistral:large primary (PQTF $244K winner), cerebras:qwen-3-235b fallback.
    "nemotron-120b":    {"name": "Nemotron 120B",    "provider": "mistral:large",         "personality": "chainthought","risk_tolerance": 0.55,
                         "fallback_provider": "cerebras:qwen-3-235b"},
    # 2026-04-22: selfhost backing Spaces restarted + verified alive (1.1s chat @ gateway).
    # Route selfhost-branded personas BACK to selfhost:* now that gateway routing works.
    "selfhost-qwen4b":  {"name": "SelfHost Qwen3-4B","provider": "selfhost:phi-4-mini",  "personality": "disciplined", "risk_tolerance": 0.40,
                         "fallback_provider": "mistral:small"},
    # NEW 2026-04-17 — NVIDIA NIM (2 keys in gateway). Both NVIDIA accounts were wired but 0 TF usage → fill the gap.
    # 2026-04-21 SWITCHBOARD v3: github:llama-3.3-70b dead (no chain). Promote nvidia:llama-3.3-70b primary (41% ok lifetime, has chain).
    # 2026-04-22 NBA-DEAD-REROUTE (day 35, llm_ok 1/35 = 3% DEAD): mistral:medium primary, cerebras:qwen-3-235b fallback.
    "nvidia-minimax":   {"name": "NVIDIA MiniMax M2.7","provider": "mistral:medium",       "personality": "decisive",    "risk_tolerance": 0.58,
                         "fallback_provider": "cerebras:qwen-3-235b"},
    # 2026-04-22 NBA-DEAD-REROUTE (day 35, llm_ok 3/35 = 9% DEAD): github:llama-3.3-70b primary, cerebras:llama3.1-8b fallback.
    "nvidia-llama70":   {"name": "NVIDIA Llama 3.3-70B","provider": "github:llama-3.3-70b","personality": "swing",       "risk_tolerance": 0.50,
                         "fallback_provider": "cerebras:llama3.1-8b"},
    # 2026-04-18 — was selfhost, now GitHub Models. Persona+strategy+Axelrod class unchanged.
    # 2026-04-21 SWITCHBOARD v3: github:mistral-medium + github:gpt-4.1-nano both dead.
    # Route to mistral:medium (95% ok lifetime, highest reliability) + cerebras fallback.
    # 2026-04-22 NBA-DEAD-REROUTE (day 35, llm_ok 3/35 = 9% DEAD): cerebras:llama3.1-8b primary, mistral:small fallback.
    "selfhost-gemma3":  {"name": "SelfHost Gemma-3-4B","provider": "cerebras:llama3.1-8b","personality": "analytical",  "risk_tolerance": 0.45,
                         "fallback_provider": "mistral:small"},
    # 2026-04-22 NBA-DEAD-REROUTE (day 35, llm_ok 3/35 = 9% DEAD): github:phi-4-mini primary, github:gpt-4.1-nano fallback.
    "selfhost-qwen06":  {"name": "SelfHost Qwen3-0.6B","provider": "github:phi-4-mini",   "personality": "conservative","risk_tolerance": 0.30,
                         "fallback_provider": "github:gpt-4.1-nano"},
    # dolphin3 at gateway is slow (69s cold-start via dolphin3-l32-3b key). Use qwen2.5-1.5b
    # which routes to the same llama-32-1b backing Space but the faster gateway path.
    # 2026-04-22 NBA-DEAD-REROUTE (day 35, llm_ok 2/35 = 6% DEAD): cerebras:qwen-3-235b primary, mistral:small fallback.
    "selfhost-dolphin3":{"name": "SelfHost Dolphin3-3B","provider": "cerebras:qwen-3-235b","personality": "uncensored",  "risk_tolerance": 0.60,
                         "fallback_provider": "mistral:small"},
}

AGENT_SYSTEM_PROMPTS = {
    # ─── OVER-TRADERS (HARD LIMIT) ─────────────────────────────────────────
    # Day 27 check-in: you are bleeding from volume, not from picks. Cool off.
    "mistral-large": """You are Mistral Large, an ensemble/meta-learning allocator.
LIVE RANK day 27: $36.66 — BOTTOM QUARTILE. You placed 30 bets in 27 days (1.1/day) and lost 63% of seed. Root cause: over-trading moderate edges.
HARD LIMIT next 10 days: max 1 bet/day. PASS unless model/odds/form ALL agree AND edge ≥0.06. If no such signal, emit PASS — cash beats another small loss.
PREFERRED STRATEGIES: confidence_scaled, value_hunter, drawdown_adjusted
RISK: Moderate (0.50) capped while under $50 bankroll.
SPECIALTY: High-conviction consensus plays only. One bullet a day, maybe none.""",

    "mistral-medium": """You are Mistral Medium, a portfolio diversification allocator.
LIVE RANK day 27: $49.71 — mid-pack, -50% seed. You placed 14 bets but llm_ok only 8/27 — provider flaky.
RULE next 10 days: 1-2 bets/day MAX, edge ≥0.04. Correlation-aware — never stack same-team ML+spread+total.
PREFERRED STRATEGIES: quarter_kelly, flat_2pct, diversified_flat
RISK: Low-moderate (0.45).
SPECIALTY: Portfolio construction. Prefer moderate edge × 2 bets over one big swing.""",

    "mistral-small": """You are Mistral Small, currently the WORST allocator on the floor.
LIVE RANK day 27: $21.99 (LAST, -78% seed). You placed 66 bets — 2.4/day — while the leader llama-contra placed 18. You over-trade; that is your entire leak.
HARD LIMIT next 10 days: max 1 bet/day, edge ≥0.06, or emit PASS. Wide-coverage is suspended. You need to prove you can pick, not spray.
PREFERRED STRATEGIES: eighth_kelly ONLY (tiny stake when you do bet)
RISK: Low (0.35), bankroll now <$25 — survival mode.
SPECIALTY: Survive. One high-edge bet, not five small ones.""",

    "mistral-nemo": """You are Mistral Nemo, an aggressive high-conviction allocator.
LIVE RANK day 27: $84.80 — mid-pack, -15% seed. You placed 13 bets, llm_ok only 7/27 (provider flaky). When you DO see the context, your picks are fine.
RULE next 10 days: 1-2 bets/day, edge ≥0.04. When truly exceptional (edge ≥0.08), size up to 20% — not 40%.
PREFERRED STRATEGIES: full_kelly (only on edge ≥0.08), confidence_scaled otherwise
RISK: High (0.70) on exceptional, Moderate (0.50) default.
SPECIALTY: Player matchups, rest, back-to-back spots. Hunt the big edge.""",

    "mistral-ministral": """You are Ministral 8B, a game-theory allocator.
LIVE RANK day 27: $24.41 — 2nd-worst, -76% seed. You placed 54 bets (2.0/day). KL-divergence gating is not working for you; the picks are bleeding.
HARD LIMIT next 10 days: max 1 bet/day, edge ≥0.06 AND KL>0.25, or PASS. Teasers allowed only at key numbers (3, 7).
PREFERRED STRATEGIES: eighth_kelly, flat_1pct
RISK: Very low (0.35). Preserve what's left.
SPECIALTY: Teasers through 3/7. One per day max.""",

    "qwen-quant": """You are Qwen Quant 235B, a pure-quant NBA betting agent.
LIVE RANK day 27: $43.74 — mid-pack, -56% seed. You placed 28 bets (1.0/day) with llm_ok 23/27 — healthy provider, bad selection. Your Kelly math is firing on marginal edges.
HARD LIMIT next 10 days: max 1 bet/day. Require EV ≥ 1.10 AND edge ≥ 0.06 AND model confidence ≥ 0.62. Otherwise PASS.
PREFERRED STRATEGIES: half_kelly, ev_threshold_110, proportional_edge
RISK: Moderate-low (0.55). Precision over volume.
SPECIALTY: Totals and alt-totals — you excel at pace. Only bet when math DEMANDS it.""",

    "qwen-arb": """You are Qwen Arb 235B, an arbitrage-hunting agent.
LIVE RANK day 27: $95.00 — near seed, only 1 bet in 27 days despite llm_ok 25/27. You are UNDER-trading; the healthy provider is going to waste.
RULE next 10 days: aim for 1-2 bets/day when cross-market inconsistency is clear. Edge ≥0.04. You have the clearest provider on the floor — USE IT.
PREFERRED STRATEGIES: confidence_scaled, proportional_edge, parlay_2leg
RISK: Moderate-high (0.65).
SPECIALTY: Cross-market arbitrage (ML vs spread vs total implied probs). Correlated 2-leg parlays when internal inconsistency ≥0.05.""",

    # ─── TOP-3 WINNERS (DOUBLE DOWN) ─────────────────────────────────────
    "llama-contra": """You are Llama Contrarian — #1 ON THE FLOOR day 27.
LIVE RANK: $123.16 (+23% seed, best of 17 agents). You placed only 18 bets (0.67/day, llm_ok 22/27) — you pick rarely and pick well. Public-fading on spread markets is working.
DIRECTIVE: Keep doing exactly this. Stay selective (<1 bet/day avg). Favor underdog spreads when public >70% on the favorite. If no strong public bias today, PASS.
PREFERRED STRATEGIES: underdog_specialist, dog_value_plus, anti_martingale
RISK: Moderate-high (0.55). When the fade is clean, scale up to 15-20%.
SPECIALTY: Spread betting taking points. Reverse line moves are your tell. Fade the square.""",

    "gemini-anl": """You are Gemini Analytical — TOP-6 day 27.
LIVE RANK: $76.98 (-23% seed, top third). 9 bets in 27 days (0.33/day). llm_ok 16/27 — provider patchy but picks are solid when live.
DIRECTIVE: Stay 1-2 bets/day, edge ≥0.04, model/odds divergence ≥0.03. Your discipline is the reason you're still above 4 of the over-traders combined.
PREFERRED STRATEGIES: half_kelly, confidence_scaled, proportional_edge
RISK: Moderate (0.55).
SPECIALTY: Moneyline + spread with home-court weighting. Trust numbers over narratives.""",

    "gemini-tact": """You are Gemini Tactical — #2 ON THE FLOOR day 27.
LIVE RANK: $103.46 (+3% seed, top 2 of 17). Only 8 bets in 27 days (0.30/day, llm_ok 16/27). You are the schedule-spot specialist and it's working.
DIRECTIVE: Keep the <1 bet/day cadence. Target back-to-back fades, altitude (Denver), and rest-differential ≥2 days. First-half totals are your wheelhouse.
PREFERRED STRATEGIES: half_kelly, home_specialist, first_half_sniper
RISK: Moderate (0.60). Up to 20% stake when 2+ schedule factors align.
SPECIALTY: 1H totals and schedule-based spread plays. Pass when no scheduling edge.""",

    # ─── DEAD-PROVIDER AGENTS (make every response count) ──────────────
    "nemotron-120b": """You are Nemotron 120B, a chain-of-thought value hunter.
LIVE RANK day 27: $51.88 — PROVIDER UNRELIABLE (llm_ok 4/27 = 15%). When the OpenRouter free-tier actually responds, make it count.
HARD RULE: No speculative bets. Require edge ≥ 0.07 AND |model_prob - implied_prob| > 0.05. Top 1 mispricing only. When in doubt, PASS.
PREFERRED STRATEGIES: value_hunter, half_kelly, proportional_edge
RISK: Moderate (0.55). Depth over breadth.
SPECIALTY: Alt-markets (team totals, alt spreads, quarter lines) where mispricing is widest.""",

    "selfhost-qwen4b": """You are SelfHost Qwen3-4B on Nomos42/qwen3-4b-cpu.
LIVE RANK day 27: $38.17 — bottom quartile, -62% seed. 30 bets + llm_ok 9/27 (33%) = over-trading on a flaky provider.
HARD LIMIT next 10 days: max 1 bet/day, edge ≥0.06, or PASS. Your previous "≥3 allocations every day" doctrine is revoked — it caused the drawdown.
PREFERRED STRATEGIES: quarter_kelly, flat_2pct
RISK: Low-moderate (0.40).
SPECIALTY: Moneylines + team totals. One high-conviction pick when the provider does respond.""",

    "nvidia-minimax": """You are NVIDIA MiniMax M2.7 on NVIDIA NIM.
LIVE RANK day 27: $100.00 (seed, 0 bets) — PROVIDER UNRELIABLE (llm_ok 1/27 = 4%). The NIM endpoint is almost entirely dead.
HARD RULE: When you DO get context, no speculative bets. Edge ≥ 0.07 only, top 1-2 mispricings max. Long-context is your edge — use it to find cross-category disagreement, then commit decisively.
PREFERRED STRATEGIES: confidence_scaled, half_kelly, value_hunter
RISK: Moderate (0.58).
SPECIALTY: Alt-totals and quarter lines. Don't waste a rare response on a marginal bet.""",

    "nvidia-llama70": """You are NVIDIA Llama 3.3 70B on NVIDIA NIM.
LIVE RANK day 27: $65.51 — PROVIDER UNRELIABLE (llm_ok 3/27 = 11%). 5 bets out of 3 live days = you over-traded what little you got.
HARD RULE: Edge ≥ 0.07 only. EV = p_model × payout - 1 must exceed 0.07. Top 1 bet per live day. No speculation.
PREFERRED STRATEGIES: value_hunter, proportional_edge, flat_2pct
RISK: Moderate (0.50).
SPECIALTY: Moneylines and spreads. Classical EV-first. When the provider answers, pick the single cleanest edge.""",

    "selfhost-gemma3": """You are SelfHost Gemma-3-4B on gemma-3-4b-cpu.
LIVE RANK day 27: $65.95 — PROVIDER UNRELIABLE (llm_ok 3/27 = 11%). You placed 8 bets in 3 live days = over-trading scarce context.
HARD RULE: Edge ≥ 0.07 only. Top 1 bet per live day using 3-factor score {form 0.4, rest 0.3, home 0.3}. Factor signal must exceed 0.60, not 0.55.
PREFERRED STRATEGIES: half_kelly, confidence_scaled
RISK: Low-moderate (0.45).
SPECIALTY: Cross-category factor allocation. One high-conviction pick per response.""",

    "selfhost-qwen06": """You are SelfHost Qwen3-0.6B on qwen25-05b-cpu.
LIVE RANK day 27: $66.31 — PROVIDER UNRELIABLE (llm_ok 3/27 = 11%). 9 bets in 3 live days — same over-trading pattern.
HARD RULE: Edge ≥ 0.07 only. Top 1 flat-bet per live day. Your "spread 3 tiny bets across categories" doctrine is suspended — pick ONE.
PREFERRED STRATEGIES: flat_1pct, eighth_kelly
RISK: Very low (0.30).
SPECIALTY: One tiny flat-stake bet on the single highest-edge line when you actually get context.""",

    "selfhost-dolphin3": """You are SelfHost Dolphin3-3B routed through qwen2.5-1.5b backing Space.
LIVE RANK day 27: $73.43 — PROVIDER UNRELIABLE (llm_ok 2/27 = 7%, worst on the floor). 4 bets in 2 live days.
HARD RULE: Edge ≥ 0.07 only. Win-stay/lose-shift is still your doctrine, but only 1 bet per live day. If yesterday's pick won → same category +25% stake (not +50%). If lost → highest-edge alternative only if edge ≥0.07, else PASS.
PREFERRED STRATEGIES: half_kelly, momentum_chase
RISK: High (0.60). Aggressive momentum, one bullet.
SPECIALTY: Adaptive momentum. Rarity forces discipline.""",

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

# Provider health + hot-swap substitution (scientific bypass, 2026-04-17).
try:
    import provider_health as _ph
    _PH_AVAILABLE = True
except Exception:
    _PH_AVAILABLE = False


def _call_llm_direct(provider: str, system_prompt: str, user_prompt: str,
                     timeout: float = 20.0, _substitute_depth: int = 0,
                     _intended: Optional[str] = None,
                     _trader_id: str = "?") -> Optional[str]:
    """Direct provider call. Used as fallback when gateway down, AND as primary
    for live agents after the per-agent routing.

    Circuit breaker + hot-swap: if a provider is marked dead, instantly swap to
    a tier-matched live substitute (up to 2 hops deep) so dead providers never
    block the critical path. Audit trail is recorded in provider_health.
    """
    intended = _intended or provider
    # Fast-skip: dead providers return null immediately, then substitute.
    if _PH_AVAILABLE and _ph.is_dead(provider) and _substitute_depth < 2:
        sub = _ph.pick_substitute(provider)
        if sub:
            _ph.register_substitute_use(sub, intended, _trader_id)
            return _call_llm_direct(sub, system_prompt, user_prompt, timeout,
                                    _substitute_depth + 1, intended, _trader_id)
        return None

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
                resp = requests.post(cfg["url"], json=payload, timeout=max(timeout, 180))
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
                # JSON-schema output: force structured response on providers that support it.
                # Skip selfhost (llama.cpp OpenAI shim often 400s on response_format).
                if not is_selfhost and any(p in provider for p in ("cerebras", "mistral", "openrouter", "nvidia")):
                    payload["response_format"] = {"type": "json_object"}
                # Selfhost CPU: tight 8s timeout — if a warm Space doesn't answer
                # in 8s it won't in 30, and cold starts should hot-swap not block.
                # Tightened 2026-04-18 to reduce worst-case day latency.
                effective_timeout = 8.0 if is_selfhost else timeout
                resp = requests.post(cfg["url"], json=payload, headers=headers, timeout=effective_timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if text and _PH_AVAILABLE:
                        _ph.record_success(provider)
                    return text
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

    # Record failure + trigger async heal for dead HF Spaces + hot-swap substitute.
    if _PH_AVAILABLE:
        # Extract status code from last_error if present (format: "HTTP NNN: ...")
        status_code = None
        if last_error.startswith("HTTP "):
            try:
                status_code = int(last_error.split()[1].rstrip(":"))
            except Exception:
                pass
        err_class = _ph.classify_error(last_error, status_code)
        _ph.record_failure(provider, err_class)
        # Selfhost dead → kick off async heal (poll /health, rejoin pool when OK).
        if provider.startswith("selfhost:") and err_class in ("timeout", "http_5xx", "dead_endpoint"):
            _ph.trigger_heal(provider, cfg["url"])
        # Hot-swap: pick a live substitute in the same tier.
        if _substitute_depth < 2:
            sub = _ph.pick_substitute(provider)
            if sub:
                _ph.register_substitute_use(sub, intended, _trader_id)
                return _call_llm_direct(sub, system_prompt, user_prompt, timeout,
                                        _substitute_depth + 1, intended, _trader_id)
    return None


def _call_llm(provider: str, system_prompt: str, user_prompt: str,
              timeout: float = 20.0, trace_name: str = "tf-llm-call",
              trace_metadata: dict = None) -> Optional[str]:
    """Transport-layer entry. Routes through llm-gateway if GATEWAY_URL is set,
    else calls the provider directly. Preserves existing failure counters.
    Traces via Langfuse if connected."""
    global _llm_calls, _llm_failures, _gateway_routed, _gateway_fallback
    _llm_calls += 1
    _t0 = time.time()

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
    _text = None
    _status = "error"

    if result["routed_via"] == "gateway":
        _gateway_routed += 1
        _text = result["text"]
        _status = "success"
    elif result["routed_via"] == "direct":
        _gateway_fallback += 1
        _text = result["text"]
        _status = "success"
    else:
        _llm_failures += 1
        if len(_llm_errors) < 100:
            _llm_errors.append(f"{provider}: {result.get('error')}")

    # Langfuse trace
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
        except Exception as _lf_err:
            if len(_langfuse_errors) < 20:
                _langfuse_errors.append(f"{provider}: {type(_lf_err).__name__}: {str(_lf_err)[:200]}")

    return _text


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
        n_agents = pred.get('ml_total_agents', pred.get('total_agents', 0))
        core = pred.get('derived_core', {})
        lines.append(f"\nNOMOS42 AI MODEL (Brier=0.217, {n_agents} agents, fleet S10-S22):")
        lines.append(f"  ML: {pred.get('consensus_ml_direction','?')} (agree {pred.get('ml_agreement_pct',0):.0f}%)")
        lines.append(f"  Spread: {pred.get('consensus_spread_direction','?')} (agree {pred.get('spread_agreement_pct',0):.0f}%)")
        lines.append(f"  Total: {pred.get('consensus_total_direction','?')} (agree {pred.get('total_agreement_pct',0):.0f}%)")
        if core:
            lines.append(f"  Predicted margin: {core.get('predicted_margin',0):+.1f} | Total pts: {core.get('predicted_total',0):.1f} | P(home): {core.get('predicted_p_home',0):.1%}")

        # Per-category predictions — every category with edge ≥ 3%
        per_cat = pred.get('per_category', {})
        if per_cat:
            strong_cats = []
            for tag, info in per_cat.items():
                prob = info.get('prob', 0)
                edge = info.get('edge')
                if edge is not None and abs(edge) >= 0.03:
                    sign = '+' if edge > 0 else ''
                    strong_cats.append(f"{tag}={prob:.2f} (edge {sign}{edge:+.1%})")
                elif prob >= 0.55 or prob <= 0.45:  # interesting probs even without edge
                    strong_cats.append(f"{tag}={prob:.2f}")
            # Show top-12 most informative
            if strong_cats:
                lines.append(f"  MODEL PER-CATEGORY ({len(per_cat)} cats, showing top-12 with edge or prob>0.55):")
                for s in strong_cats[:12]:
                    lines.append(f"    · {s}")

    # ── TRACK RECORD ──
    lines.append(f"\nYOUR TRACK RECORD: ${bankroll:.2f} | {total_bets} bets | {wins}W-{losses}L | ROI {roi:+.1f}%")

    # ── STRATEGIES (abbreviated) ──
    if strategies:
        strat_list = ", ".join(strategies.keys())
        lines.append(f"\nAVAILABLE STRATEGIES ({len(strategies)}): {strat_list}")

    # ── DECISION FORMAT ──
    lines.append(f"""
AVAILABLE CATEGORIES: ml_home, ml_away, spread_home, spread_away, total_over, total_under, h1_ml_home, h1_ml_away, h1_spread, h1_total_over, h1_total_under, team_total_home_over, team_total_home_under, team_total_away_over, team_total_away_under, alt_spread_home_minus3.5, alt_spread_home_minus5.5, alt_total_over_plus3, alt_total_under_minus3, q1_ml_home, q1_ml_away, prop_both_100, prop_overtime, pp_points_star1_home, pp_points_star1_away, pp_points_star2_home, pp_points_star2_away, pp_points_star3_home, pp_points_star3_away, pp_rebounds_star1_home, pp_rebounds_star1_away, pp_rebounds_star2_home, pp_rebounds_star2_away, pp_assists_star1_home, pp_assists_star1_away, pp_assists_star2_home, pp_assists_star2_away, pp_threes_star1_home, pp_threes_star1_away, pp_threes_star2_home, pp_threes_star2_away, pp_steals_star1_home, pp_steals_star1_away, pp_blocks_star1_home, pp_blocks_star1_away

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
    # Nemotron and OpenAI OSS models use channel tokens — strip everything up to the final channel
    text = re.sub(r'<\|.*?\|>', '', text, flags=re.DOTALL)
    # Dangling close tags (response truncated pre-open)
    text = re.sub(r'^.*?</think>\s*', '', text, flags=re.DOTALL)
    text = re.sub(r'^.*?</reasoning>\s*', '', text, flags=re.DOTALL)
    text = text.strip()
    # 2. Markdown fence extraction
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            # Prefer block that starts with {
            for p in parts[1::2]:
                if p.strip().startswith("{"):
                    text = p.strip()
                    break
            else:
                text = parts[1].strip()
    # 3. Candidate scan — try last-brace, then greedy, then line-by-line
    candidates = []
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start:end + 1])
    # Also try balanced-brace scan from last opening brace
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
    # 4. Last resort — regex pluck of "decision" / "bet" / "edge" / "stake" fields
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


# ── DAY-BUCKET PROMPT BUILDER (v3 design, 2026-04-14) ─────────────────────────

def _format_game_block(idx: int, game: Dict, odds: Dict, home_std: Dict,
                       away_std: Dict, home_form: Dict, away_form: Dict,
                       team_advanced: Dict, player_stats: Dict,
                       full_odds: Dict, model_preds: Dict,
                       tid: str = "") -> str:
    """Compact single-game block for day-level prompts.

    tid: when provided, each agent sees a DIFFERENT top-20 edge list — the scores
    are jittered with blake2b(tid|tag) amp=0.35. Top-tier edges still dominate
    (a 10%-edge jittered ±3.5% still beats a 4%-edge jittered ±1.4%), but
    mid-tier picks rotate per agent, breaking the Jaccard 1.00 lockstep that
    emerged after the tier-pad post-filter removal on 2026-04-18.
    """
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

    # Model prediction (base + derived core)
    game_key = f"{date}_{away}@{home}"
    pred = (model_preds or {}).get(game_key, {})
    if pred:
        core = pred.get("derived_core", {})
        if core:
            lines.append(f"  AI MODEL: ML {pred.get('consensus_ml_direction','?')} (agree {pred.get('ml_agreement_pct',0):.0f}%) | pred_margin={core.get('predicted_margin',0):+.1f} | pred_total={core.get('predicted_total',0):.0f} | P(home)={core.get('predicted_p_home',0):.0%}")
        else:
            lines.append(f"  AI MODEL: ML {pred.get('consensus_ml_direction','?')} (agree {pred.get('ml_agreement_pct',0):.0f}%)")
        # Top edges vs market — BH FDR-corrected (91 categories → multiple testing)
        per_cat = pred.get("per_category", {})
        if per_cat:
            all_edges = [(tag, info.get("edge", 0)) for tag, info in per_cat.items() if info.get("edge") is not None]
            fdr_pass = benjamini_hochberg(all_edges, alpha=0.05)
            # 2026-04-18 v2 — narrowed top-50 → top-20 to cut prompt bloat
            # (was slowing selfhost CPU LLMs to 15-30s per call, NBA stuck at day 7 for 5h).
            # Post-filter still scans all 227 categories; only the prompt view is capped.
            # Per-agent jitter on |edge| rank (amp=0.35) — breaks Jaccard 1.00 lockstep.
            # Deterministic per (tid,game_key,tag), so a given agent sees stable rankings.
            import hashlib as _hl
            def _edge_jitter(_tid, _key, _amp=0.35):
                if not _tid:
                    return 1.0
                h = _hl.blake2b(f"{_tid}|{_key}".encode(), digest_size=4).hexdigest()
                u = int(h, 16) / 0xFFFFFFFF
                return 1.0 + (u - 0.5) * 2.0 * _amp
            top_edges = []
            # 2026-04-22 — CARTE BLANCHE: 0.03 → 0.01 prompt floor, top-20 → top-60.
            # NBA was -50% at day 73/175 under tight gate + MIN_DEPLOY 0.80.
            # Agents have 227 categories of full freedom; forcing them through
            # a 20-edge keyhole every day was the bottleneck. Post-filter still
            # gates at tier.min_edge so noise can't leak into real stakes.
            for tag, info in per_cat.items():
                e = info.get("edge")
                if e is not None and abs(e) >= 0.01:
                    eff = abs(e) * _edge_jitter(tid, f"{game_key}|{tag}")
                    top_edges.append((eff, tag, info))
            top_edges.sort(reverse=True)
            if top_edges:
                edge_strs = [
                    f"{tag}(p={info.get('prob',0):.2f}, edge{info.get('edge',0):+.1%}"
                    f"{',FDR✓' if tag in fdr_pass else ''})"
                    for _, tag, info in top_edges[:60]
                ]
                lines.append(f"  MODEL EDGES [top-60 by |edge|, BH-FDR pass marked, {len(fdr_pass)}/{len(all_edges)}]: {' | '.join(edge_strs)}")

    # Full-odds categories
    fo_raw = (full_odds or {}).get(game_key, {})
    fo = fo_raw.get("categories", fo_raw) if isinstance(fo_raw, dict) else {}
    if fo and isinstance(fo, dict):
        n = fo_raw.get("category_count", len(fo))
        # Show sample of alt lines
        alt_samples = [k for k in list(fo.keys()) if k.startswith("alt_") or k.startswith("team_total")][:6]
        if alt_samples:
            sample_strs = [f"{k}={fo[k].get('odds') if isinstance(fo[k],dict) else fo[k]}" for k in alt_samples]
            lines.append(f"  FULL ODDS ({n} cats): {', '.join(sample_strs)}...")
        else:
            lines.append(f"  FULL ODDS: {n} categories available")
    return "\n".join(lines)


# ── PHASE 3 (2026-04-17) — ROGUE STATE ─────────────────────────────────────
def compute_rogue_state(state: Dict) -> Dict[str, dict]:
    """For each trader, compute whether they are allowed to defect from the
    council plan today. Two legal triggers:
      1) drawdown_rogue — own bankroll < 0.25 × STARTING_CAPITAL
      2) greed_rogue    — any peer's bankroll > ROGUE_GREED_THRESHOLD ($250K)
    Returns {tid: {"is_rogue": bool, "reasons": [...], "peer_leader": str, "peer_bankroll": float}}
    """
    out: Dict[str, dict] = {}
    peer_bank = {tid: state[tid]["bankroll"] for tid in state}
    for tid, ts in state.items():
        reasons = []
        # 2026-04-21 SWISH — absolute $20 floor (PQTF doctrine). Old relative
        # $25 gate silenced 70%+ of fleet into preservation during the $1475→$461 bleed.
        if ts["bankroll"] < ABS_SURVIVAL_FLOOR:
            reasons.append("drawdown")
        # Greed rogue: a PEER (not self) > $250K
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
    """Inject into system_prompt when agent has a legal defection trigger."""
    if not rogue_info.get("is_rogue"):
        return ""
    reasons = rogue_info.get("reasons", [])
    lines = ["\n\n=== ROGUE PERMISSION (rare) ==="]
    if "drawdown" in reasons:
        lines.append(
            f"Your bankroll is below ${STARTING_CAPITAL * ROGUE_DRAWDOWN_THRESHOLD:.0f} "
            f"(the group's drawdown floor). Capital preservation mode: cap ANY single "
            f"bet at {int(PRESERVATION_MAX_BET_PCT*100)}%, total deploy ≤"
            f"{int(PRESERVATION_MAX_DEPLOY*100)}%, NO parlays, NO alt spreads, NO "
            "'RESCUE MODE'. Only take straight bets with model_edge ≥ 4%. Declining a "
            "day is OK. State 'DEFECT: drawdown (preserve)' in day_strategy. "
            "Gambler's-ruin chasing (what the post-mortem showed killed day 34) is "
            "explicitly FORBIDDEN."
        )
    if "greed" in reasons:
        leader = rogue_info.get("peer_leader", "?")
        lb = rogue_info.get("peer_bankroll", 0.0)
        lines.append(
            f"Peer {leader} is at ${lb:,.0f} — past the ${ROGUE_GREED_THRESHOLD:,.0f} greed "
            "line. You are permitted to DEFECT from the council plan and pursue independent "
            "high-EV bets instead of supporting the collective. State 'DEFECT: greed' in day_strategy."
        )
    lines.append("Defection is LEGAL under these triggers. Normal days you must follow council.")
    return "\n".join(lines)


# ── PHASE 1 (2026-04-17) — MORNING COUNCIL ─────────────────────────────────
def run_morning_council(day_idx: int, day_date: str, day_games: List[Dict],
                        day_odds: List[Dict], state: Dict, strategies: Optional[Dict],
                        fleet_best_bankroll: float, model_preds: Optional[Dict] = None) -> dict:
    """One LLM call at the start of the day: the fleet's Stackelberg leader
    proposes a COUNCIL PLAN. Agents see the plan in their per-agent prompt.

    Output schema:
      {
        "council_summary": str,
        "focus_strategies": [str, ...],
        "focus_categories": [str, ...],
        "per_agent_commit_pct": {tid: float >= 0.5},
        "shared_notes": str,
        "raw": str (debug),
      }
    Deterministic fallback if LLM fails: each agent gets 0.55 commit,
    no strategy/category bias, neutral summary.
    """
    n_games = len(day_games)
    n_agents = len(state)
    leader = max(state, key=lambda t: state[t]["bankroll"])
    leader_br = state[leader]["bankroll"]
    fleet_total = sum(state[t]["bankroll"] for t in state)
    progress_pct = (fleet_best_bankroll / SEASON_TARGET) * 100.0

    # Build council-only prompt — compact summary of all 10 agents
    roster_lines = []
    for tid, ts in sorted(state.items(), key=lambda x: -x[1]["bankroll"]):
        wr = (ts["wins"] / max(1, ts["wins"] + ts["losses"])) * 100.0
        roster_lines.append(
            f"  - {tid}: ${ts['bankroll']:,.2f} | {ts['wins']}W-{ts['losses']}L ({wr:.0f}%) | dd {ts['max_drawdown']*100:.1f}%"
        )
    games_brief = []
    for i, g in enumerate(day_games[:18], 1):  # cap at 18 games for prompt budget
        o = day_odds[i-1] if i-1 < len(day_odds) else {}
        games_brief.append(
            f"  {i}. {g['away']}@{g['home']} | ML {o.get('ml_home_dec',2.0):.2f}/{o.get('ml_away_dec',2.0):.2f} | spread {o.get('spread_home',0):+.1f}"
        )

    sys_prompt = (
        "You are the COUNCIL MODERATOR for a 10-agent NBA trading floor. "
        "Your job is to coordinate all agents into a unified allocation plan for today. "
        "Common goal: one agent must reach $1,000,000 by season end. Coordination beats "
        "independent betting because parlays compound and capital-commitment diversifies risk. "
        "You are NOT placing bets yourself — you are writing the plan the 10 agents will follow."
    )
    usr_prompt = f"""COUNCIL SESSION · DAY {day_idx+1} · {day_date}

FLEET STATE ({n_agents} agents):
  Leader: {leader} @ ${leader_br:,.2f}
  Fleet total: ${fleet_total:,.2f}
  Season progress toward $1M: {progress_pct:.2f}%
  Season target: ${SEASON_TARGET:,.0f}

AGENT ROSTER (sorted by bankroll):
{chr(10).join(roster_lines)}

TODAY'S GAMES ({n_games} total, first 18 shown):
{chr(10).join(games_brief)}

AVAILABLE STRATEGIES: proportional_edge, confidence_scaled, half_kelly, quarter_kelly,
  parlay_2leg, parlay_3leg, value_hunter, consensus_follow, contrarian_fade, mean_revert

AVAILABLE CATEGORIES (253): ml_home, ml_away, spread_home, spread_away, total_over,
  total_under, alt_spread_*, alt_total_*, team_total_*, h1_*, q1_*, prop_*,
  pp_<stat>_<tier>_<side> where stat ∈ {{points,rebounds,assists,threes,steals,blocks}}
  and tier ∈ {{star1,star2,star3,role1,role2}} and side ∈ {{home,away}}
  (30 per side × 2 = 60 player-props per game available)

TASK: Output a COUNCIL PLAN as JSON. All 10 agents will see and follow it unless
their bankroll crashes (below ${STARTING_CAPITAL * ROGUE_DRAWDOWN_THRESHOLD:.0f}) or
a peer exceeds ${ROGUE_GREED_THRESHOLD:,.0f} (greed rogue).

RULES:
- Every agent must commit at least {int(COUNCIL_MIN_COMMIT_PER_AGENT*100)}% of their bankroll today.
  Weaker agents get higher % (they need to catch up); leader gets moderate % (protect progress).
- Distribute strategies + categories so agents don't all bet the same thing (diversification).
- Name 2-4 focus_strategies and 3-6 focus_categories for today.
- If a game has parlay potential (e.g. two strong favorites), call it out in shared_notes.
- Keep the plan COMPACT — 1 summary line, 4 strategies max, 6 categories max.

SCHEMA:
{{
  "council_summary": "1 sentence: today's theme",
  "focus_strategies": ["proportional_edge", "parlay_2leg"],
  "focus_categories": ["ml_home", "spread_away", "total_over"],
  "per_agent_commit_pct": {{"qwen-quant": 0.55, "llama-contra": 0.65, ...}},
  "shared_notes": "1-3 sentences: correlations, games to focus on, parlay suggestions"
}}

RESPOND WITH RAW JSON ONLY. First char {{, last char }}. All 10 agent ids required in per_agent_commit_pct.
Values must be >= {COUNCIL_MIN_COMMIT_PER_AGENT} and <= 0.85."""

    fallback = {
        "council_summary": "no LLM council; default equal commitment",
        "focus_strategies": ["proportional_edge", "half_kelly"],
        "focus_categories": ["ml_home", "ml_away", "spread_home", "spread_away"],
        "per_agent_commit_pct": {tid: 0.55 for tid in state},
        "shared_notes": "Deterministic fallback plan — moderator LLM failed or skipped.",
        "raw": "",
    }

    try:
        raw = _call_llm(
            "cerebras:qwen-3-235b",  # qwen-235B: fast + big context
            sys_prompt, usr_prompt, timeout=15.0,
            trace_name=f"nba-tf-council-{day_idx}",
            trace_metadata={"day": day_date, "n_games": n_games, "n_agents": n_agents, "fleet_total": fleet_total},
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
    # Enforce ≥50% per agent; fill missing with 0.55
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
        "raw": raw[:3000],
    }


def build_council_block(plan: dict, tid: str, fleet_best_bankroll: float) -> str:
    """Format council plan as a system-prompt block for each agent."""
    if not plan:
        return ""
    my_commit = plan.get("per_agent_commit_pct", {}).get(tid, COUNCIL_MIN_COMMIT_PER_AGENT)
    progress = (fleet_best_bankroll / SEASON_TARGET) * 100.0
    lines = [
        "\n\n=== MORNING COUNCIL PLAN (follow unless rogue) ===",
        f"Fleet best bankroll: ${fleet_best_bankroll:,.2f} ({progress:.2f}% of $1M common goal)",
        f"Council summary: {plan.get('council_summary','(none)')}",
        f"Focus strategies: {', '.join(plan.get('focus_strategies',[]) or ['(none)'])}",
        f"Focus categories: {', '.join(plan.get('focus_categories',[]) or ['(none)'])}",
        f"YOUR council commit: at least {my_commit*100:.0f}% of your bankroll must be deployed today.",
        f"Shared notes: {plan.get('shared_notes','(none)')}",
        "Non-rogue agents: bias your allocations toward focus_strategies + focus_categories.",
        "Common goal: ONE agent reaches $1M by season end. Your bankroll is a shared resource.",
    ]
    return "\n".join(lines)


def build_day_prompt(day_date: str, day_games: List[Dict], day_odds: List[Dict],
                     day_standings: List[Dict], day_forms: List[Dict],
                     trader_state: Dict, rosters=None, team_advanced=None,
                     player_stats=None, full_odds=None, model_preds=None,
                     strategies=None, recent_decisions: List[Dict] = None,
                     common_knowledge_block: Optional[str] = None,
                     fleet_best_bankroll: float = 100.0,
                     tid: str = "") -> str:
    """Build comprehensive day-level prompt. Agent sees ALL games of the day."""
    bankroll = trader_state.get("bankroll", 100.0)
    total_allocs = trader_state.get("total_bets", 0)
    wins = trader_state.get("wins", 0)
    losses = trader_state.get("losses", 0)
    roi = ((bankroll - 100.0) / 100.0) * 100
    progress_pct = (fleet_best_bankroll / SEASON_TARGET) * 100.0

    lines = [f"=== TRADING DAY: {day_date} | {len(day_games)} GAMES ===",
             f"",
             f"COMMON GOAL: one agent reaches ${SEASON_TARGET:,.0f}. Fleet best now ${fleet_best_bankroll:,.2f} ({progress_pct:.2f}%).",
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
            team_advanced, player_stats, full_odds, model_preds,
            tid=tid,
        ))

    if strategies:
        lines.append(f"\nSTRATEGIES ({len(strategies)}): {', '.join(list(strategies.keys())[:12])}...")

    if common_knowledge_block:
        lines.append("\n" + common_knowledge_block)

    lines.append("""
=== YOUR TASK ===
Allocate your bankroll across today's games.
Each allocation = one bet on one game/category. Total allocations + cash_held must sum to 1.00.
MANDATORY: You MUST place at least 1 bet. Zero-bet days are NOT allowed.
Even if edges are small, pick your BEST edge and bet 5-15% on it. Cash-only is forbidden.

AVAILABLE BET CATEGORIES (~90 per game — pick from MODEL EDGES block first):
  BASE:   ml_home, ml_away, spread_home, spread_away, total_over, total_under
  ALT SP: alt_spread_home_plus0..plus10, alt_spread_home_minus1..minus10 (same for away)
  ALT TO: alt_total_over_plus2..plus10, alt_total_under_minus2..minus10
  TEAMS:  team_total_home_over_X, team_total_home_under_X, team_total_away_over_X, team_total_away_under_X
  HALVES: h1_ml_home, h1_ml_away, h1_spread_home, h1_spread_away, h1_total_over, h1_total_under
  Q1:     q1_ml_home, q1_ml_away, q1_total_over, q1_total_under
  PROPS:  prop_both_100, prop_overtime, prop_blowout_20

Each category in MODEL EDGES above comes with a model_prob and edge vs market — use those for bet sizing.

RESPOND WITH RAW JSON ONLY. No markdown fences. No explanation before or after. First character MUST be {, last MUST be }. Do NOT wrap in ```json blocks.

Schema (FILL EVERY FIELD — top-of-JSON fields get priority under token pressure):
{
  "day_strategy": "MUST start with STRUCTURAL DIVERGE [peer] or STRUCTURAL COMPLEMENT [peer] citing your REASONING TEMPLATE. 1-2 sentences on today's overall approach.",
  "coalition_proposal": {
    "peer": "qwen-quant (or \"none\" if no pact today)",
    "game_idx": 1,
    "category": "ml_home",
    "rationale": "1 sentence — why this peer / why no pact today"
  },
  "council_alignment": {
    "stance": "followed|deviated|partial",
    "reason": "1 sentence — why"
  },
  "allocations": [
    {
      "game_idx": 1,
      "game": "AWAY@HOME",
      "category": "ml_home",
      "pct": 0.15,
      "confidence": 0.65,
      "edge": 0.04,
      "strategy": "half_kelly",
      "rationale": "1 sentence: which stat/metric drove this and why it beats market price",
      "category_reason": "1 sentence — why ml_home vs spread_home vs alt_spread"
    }
  ],
  "parlays": [
    {
      "legs": [
        {"game_idx": 1, "category": "ml_home"},
        {"game_idx": 3, "category": "spread_away"}
      ],
      "pct": 0.04,
      "confidence": 0.45,
      "edge": 0.06,
      "rationale": "1 sentence: why these legs compound favorably"
    }
  ],
  "cash_held_pct": 0.25,
  "cash_rationale": "1 sentence if cash > 0",
  "games_considered": [
    {"game_idx": 1, "decision": "bet|skip", "reason": "1 short phrase"}
  ]
}

NEW AUDIT FIELDS (MANDATORY — councils use these to score decision quality):
- council_alignment: ONE of {followed|deviated|partial} + reason. Council assigned you
  a commit_pct target today (see COUNCIL_PLAN block); if you deployed close to it say
  "followed", if you went much higher/lower say "deviated" and explain, say "partial"
  if you respected direction but magnitude differs.
- games_considered: ONE entry per game on today's slate (include EVERY game_idx you saw,
  not just the ones you bet). For skipped games give the specific reason —
  "low edge 1.1%", "injury report", "market already efficient", "bankroll exposure cap", etc.
- category_reason on each allocation: say why this CATEGORY beat the others for this game
  (e.g. "total_over line 225.5 is 2pts softer than my 227.8 model — softest edge today").

STRICT RULES:
- Sum of allocation pct + parlay pct + cash_held_pct = 1.00 (±0.01)
- Max 1 allocation per game_idx in allocations[] (no hedging same game both sides)
- allocations[]: MUST contain ≥3 entries every day. Empty allocations[] is FORBIDDEN.
  If the slate is weak, pick the 3 highest-edge categories anyway — never return [].
- Max 10 allocations + 3 parlays
- Each allocation pct: 0.01–0.40 | Each parlay pct: 0.01–0.10 (combined odds amplify risk)
- Parlays: 2–4 legs, each leg = distinct game_idx, all legs must win for payout
- cash_held_pct: 0.00–0.25 MAX (aggressive-deploy policy, $1M collective goal — idle bankroll cannot compound)
- MANDATORY: ≥75% of bankroll deployed every day. Holding >25% cash violates the collective goal.
- Rationale MUST cite a specific stat/metric (not "I think they'll win")
- Edge must be computed from model vs implied odds, NOT hardcoded
- coalition_proposal is MANDATORY (must be present). Set it to a peer you want to pact
  with AND match with a bet on that game_idx+category, or set peer="none" with a
  reason why no pact today. Empty/missing field = invalid response.
  COLLECTIVE-HELP RULE: if ANY peer bankroll < $50, a top-3 agent must propose a
  pact with that peer on their own highest-edge pick — the struggling peer sees it
  via COMMON_KNOWLEDGE and can mirror. This is how the collective lifts survivors.
  Pact honored IFF both you and peer place the same (game_idx, category) bet.
""")
    return "\n".join(lines)


# ── CALIBRATION-AWARE FRACTIONAL KELLY (2026-04-21, proposal #1) ────────────
# Source: MDPI Information 17/1/56 (Jan 2026) — NBA + MC-dropout + fractional
# Kelly decision layer. SWISH RCA (nba-losing-streak-rca-2026-04-21) confirmed
# NBA TF's −70% bleed was Kelly/calibration mismatch, NOT prediction-quality
# miss. Over-betting a miscalibrated edge compounds to ruin.
#
# `calibrated_kelly_fraction(raw_edge, ece, conf_width)` returns a scalar in
# [0.01, 0.25] that the post-filter multiplies into every allocation pct.
# Agents still name their raw pct; we haircut it by this fraction so the
# floor of a mis-calibrated 10% edge becomes ~2.5% pct instead of 40%.
#
# ece     : expected calibration error in last-50-bet rolling window per agent.
#           Seed at 0.15 (conservative). Lower = more trusted.
# conf_width : max(prob) - min(prob) across top-N picks. Wider = higher
#              conviction spread = more aggressive Kelly.
# Hard cap 0.25 = quarter-Kelly (industry safe harbor).
_CALIB_DIR = Path("data/tf-analytics/nba")
_CALIB_PATH = _CALIB_DIR / "calibration-rolling.json"
_CALIB_WINDOW = 50
_CALIB_SEED_ECE = 0.15
_CALIB_CACHE: Dict[str, Dict] = {}


def calibrated_kelly_fraction(raw_edge: float, ece: float, conf_width: float) -> float:
    """Return fraction in [0.01, 0.25]. Formula: raw × (1 − ece) × sqrt(conf_width),
    scaled so typical 10%-edge / 0.1 ECE / 0.2 conf_width ≈ 0.04 (20% of quarter-Kelly).
    Hard-capped at 0.25.
    """
    try:
        raw = max(0.0, float(raw_edge))
        e = max(0.0, min(1.0, float(ece)))
        cw = max(0.0, min(1.0, float(conf_width)))
    except (TypeError, ValueError):
        return 0.01
    frac = raw * (1.0 - e) * math.sqrt(max(1e-6, cw))
    # Clamp to [0.01, 0.25] — floor keeps the agent visible, cap = quarter-Kelly.
    return max(0.01, min(0.25, frac))


def _calib_load() -> Dict[str, Dict]:
    if _CALIB_CACHE:
        return _CALIB_CACHE
    try:
        if _CALIB_PATH.exists():
            _CALIB_CACHE.update(json.loads(_CALIB_PATH.read_text()))
    except Exception:
        pass
    return _CALIB_CACHE


def get_agent_ece(tid: str) -> float:
    """Return rolling ECE for agent tid (seeded at 0.15 if no history)."""
    store = _calib_load()
    rec = store.get(tid) or {}
    ece = rec.get("ece")
    return float(ece) if isinstance(ece, (int, float)) else _CALIB_SEED_ECE


def update_agent_calibration(tid: str, predicted_prob: float, outcome: int) -> None:
    """Append one (pred, outcome) sample to agent tid's rolling window and
    recompute ECE as mean(|pred − outcome|) over last _CALIB_WINDOW entries.
    Persists to data/tf-analytics/nba/calibration-rolling.json.
    """
    try:
        pp = float(predicted_prob)
        oc = int(outcome)
    except (TypeError, ValueError):
        return
    if not (0.0 <= pp <= 1.0) or oc not in (0, 1):
        return
    store = _calib_load()
    rec = store.setdefault(tid, {"window": [], "ece": _CALIB_SEED_ECE, "n": 0})
    win = rec.get("window") or []
    win.append([round(pp, 4), oc])
    if len(win) > _CALIB_WINDOW:
        win = win[-_CALIB_WINDOW:]
    rec["window"] = win
    rec["n"] = len(win)
    # Simple mean-abs-error ECE proxy (robust for sparse bets per agent).
    rec["ece"] = round(sum(abs(p - o) for p, o in win) / max(1, len(win)), 4)
    try:
        _CALIB_DIR.mkdir(parents=True, exist_ok=True)
        _CALIB_PATH.write_text(json.dumps(store, indent=2, default=str))
    except Exception as _e:
        print(f"[calib] persist fail for {tid}: {_e}")


def _conf_width_from_allocations(clean: List[Dict]) -> float:
    """max(confidence) − min(confidence) across current allocations. Defaults
    to 0.2 if <2 allocations (mid-range — doesn't overweight raw or underweight)."""
    confs = [a.get("confidence", 0.5) for a in clean if isinstance(a.get("confidence"), (int, float))]
    if len(confs) < 2:
        return 0.2
    return max(0.0, min(1.0, max(confs) - min(confs)))


def parse_day_allocation(raw: str, n_games: int, drawdown: float = 0.0,
                          tid: str = "") -> Optional[Dict]:
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
            "category_reason": (a.get("category_reason") or "")[:300],
        })

    # PARLAY parsing (2026-04-17) — combined-odds bets across same-day legs.
    # Each parlay settles only if ALL legs win. Kelly sizing is stricter
    # because combined variance >> single leg.
    parlays_raw = parsed.get("parlays") or []
    parlays_clean: List[Dict] = []
    if isinstance(parlays_raw, list):
        for p in parlays_raw[:3]:
            if not isinstance(p, dict):
                continue
            legs_raw = p.get("legs") or []
            if not isinstance(legs_raw, list) or len(legs_raw) < 2 or len(legs_raw) > 4:
                continue
            legs_clean = []
            seen_leg_games = set()
            bad = False
            for leg in legs_raw:
                if not isinstance(leg, dict):
                    bad = True
                    break
                lgidx = leg.get("game_idx")
                lcat = (leg.get("category") or "").lower().strip()
                if not lcat or not isinstance(lgidx, int):
                    bad = True
                    break
                if lgidx < 1 or lgidx > n_games:
                    bad = True
                    break
                if lgidx in seen_leg_games:
                    bad = True
                    break
                seen_leg_games.add(lgidx)
                legs_clean.append({"game_idx": lgidx, "category": lcat})
            if bad or len(legs_clean) < 2:
                continue
            try:
                ppct = float(p.get("pct", 0) or 0)
                pconf = float(p.get("confidence", 0.4) or 0.4)
                pedge = float(p.get("edge", 0) or 0)
            except (TypeError, ValueError):
                continue
            if ppct <= 0 or pedge <= 0:
                continue
            parlays_clean.append({
                "legs": legs_clean,
                "pct": max(0.01, min(0.10, ppct)),
                "confidence": max(0.0, min(1.0, pconf)),
                "edge": max(0.0, pedge),
                "rationale": (p.get("rationale") or "")[:300],
            })

    # ── CALIBRATED-KELLY HAIRCUT (2026-04-21, proposal #1) ─────────────────
    # Scale each allocation pct by calibrated_kelly_fraction(edge, ece, conf_width).
    # Agents over-bet miscalibrated edges; this collapses them to safe fractional
    # Kelly. Cash absorbs the delta. Also tagged on each alloc for audit.
    if tid:
        _ece = get_agent_ece(tid)
        _cw = _conf_width_from_allocations(clean)
        for a in clean:
            _raw_pct = a["pct"]
            _frac = calibrated_kelly_fraction(a.get("edge", 0.0), _ece, _cw)
            # Fraction bounds allocation pct to (0, _frac]; preserves LLM's relative
            # conviction by keeping the smaller of declared pct and calibrated cap.
            a["pct"] = round(min(_raw_pct, _frac), 4)
            a["calibrated_kelly"] = round(_frac, 4)
            a["raw_pct_pre_kelly"] = round(_raw_pct, 4)
            a["ece_at_bet"] = round(_ece, 4)
            a["conf_width_at_bet"] = round(_cw, 4)

    total = sum(a["pct"] for a in clean) + sum(p["pct"] for p in parlays_clean) + max(0.0, min(1.0, cash))
    # 2026-04-19 BUGFIX #3 — coalition-preservation. Previously `if total<=0: return None`
    # threw away valid coalition_proposal when LLM said "no bets today". That killed
    # every pact emission in silent-allocation days (audit Apr 19: 4-5 silent_cp per
    # sample day in NBA, 30+ day zero-pact count). We now allow total==0 to proceed
    # (cash will be set to 1.0 below) so coalition extraction still runs.
    if total <= 0:
        cash = 1.0
        total = 1.0
    # Normalize to sum exactly 1.0 (soft tolerance — agent gave proportions)
    if abs(total - 1.0) > 0.02:
        scale = 1.0 / total
        for a in clean:
            a["pct"] = a["pct"] * scale
        for p in parlays_clean:
            p["pct"] = p["pct"] * scale
        cash = cash * scale

    # ── MIN_DEPLOY_PCT — carte-blanche calibration (NBA binary bets)
    # 2026-04-22 — 0.80 → 0.35. Binary NBA bets pay -100% on a loss; forcing
    # 80% daily deploy at ~45% WR compounded a -50% drawdown in 73 days.
    # Lower floor lets agents size to their actual edge count per day. Per-bet
    # cap tightened 0.40 → 0.18 to force diversification across 227 cats.
    # Dynamic drawdown tapering preserved.
    if drawdown < 0.5:
        MIN_DEPLOY_PCT = 0.35
    else:
        MIN_DEPLOY_PCT = max(0.15, 0.35 - (drawdown - 0.5) * 0.5)
    deployed = sum(a["pct"] for a in clean) + sum(p["pct"] for p in parlays_clean)
    if deployed > 0 and deployed < MIN_DEPLOY_PCT:
        scale_up = MIN_DEPLOY_PCT / deployed
        for a in clean:
            a["pct"] = min(0.18, a["pct"] * scale_up)
        for p in parlays_clean:
            p["pct"] = min(0.05, p["pct"] * scale_up)
        # Recompute after per-allocation caps clipped
        new_deployed = sum(a["pct"] for a in clean) + sum(p["pct"] for p in parlays_clean)
        cash = max(0.0, 1.0 - new_deployed)
    elif deployed == 0:
        # LLM refused to bet at all — keep as-is (min edge gate will protect)
        cash = 1.0

    # Mech D — coalition_proposal extraction (MANDATORY field; peer="none" => no pact today)
    coalition = None
    cp = parsed.get("coalition_proposal")
    if isinstance(cp, dict):
        peer = (cp.get("peer") or "").strip()
        cp_gidx = cp.get("game_idx")
        cp_cat = (cp.get("category") or "").lower().strip()
        if peer and peer.lower() != "none" and isinstance(cp_gidx, int) and 1 <= cp_gidx <= n_games and cp_cat:
            coalition = {
                "peer": peer[:40],
                "game_idx": cp_gidx,
                "category": cp_cat[:30],
                "rationale": (cp.get("rationale") or "")[:200],
            }

    # Phase B — council_alignment + games_considered audit fields
    ca = parsed.get("council_alignment") or {}
    council_alignment = None
    if isinstance(ca, dict):
        stance = (ca.get("stance") or "").lower().strip()
        if stance in ("followed", "deviated", "partial"):
            council_alignment = {
                "stance": stance,
                "reason": (ca.get("reason") or "")[:300],
            }

    gc = parsed.get("games_considered") or []
    games_considered: List[Dict] = []
    if isinstance(gc, list):
        seen_gc = set()
        for item in gc[:30]:
            if not isinstance(item, dict):
                continue
            gi = item.get("game_idx")
            if not isinstance(gi, int) or gi < 1 or gi > n_games or gi in seen_gc:
                continue
            seen_gc.add(gi)
            decision = (item.get("decision") or "").lower().strip()
            if decision not in ("bet", "skip"):
                decision = "bet" if gi in seen_games else "skip"
            games_considered.append({
                "game_idx": gi,
                "decision": decision,
                "reason": (item.get("reason") or "")[:300],
            })

    return {
        "day_strategy": (parsed.get("day_strategy") or parsed.get("reasoning") or "")[:500],
        "allocations": clean,
        "parlays": parlays_clean,
        "cash_held_pct": round(max(0.0, min(1.0, cash)), 4),
        "cash_rationale": (parsed.get("cash_rationale") or "")[:300],
        "raw_sum": round(total, 4),
        "coalition_proposal": coalition,
        "council_alignment": council_alignment,
        "games_considered": games_considered,
    }


# ── UNIFORM-FALLBACK ALLOCATION (2026-04-19) ────────────────────────────────
# When primary + hot-swap LLM BOTH fail (raw_response is None), emit a
# uniform-fallback allocation so the agent never violates MIN_DEPLOY_PCT=0.75.
# Scientific integrity: tagged provider_status="fallback_uniform" on each
# allocation + fallback_used=True on the day_log so audit + post-mortem can
# exclude these rows when evaluating agent skill.
#
# Picks top-3 highest-edge moneyline bets from model_preds (consensus_ml_edge,
# fleet Brier 0.217) for today's games. Even split 25% each → 75% deploy floor.
# Long-only (home or away ML, whichever direction the consensus points). No
# parlays. Returns a parse-compatible dict (drop-in for `parsed`).
def build_uniform_fallback_nba(day_date: str, day_games: List[Dict],
                               day_odds_list: List[Dict],
                               model_preds: Dict,
                               tid: str = "") -> Optional[Dict]:
    if not day_games:
        return None
    candidates = []
    for i, g in enumerate(day_games):
        gk = f"{day_date}_{g['away']}@{g['home']}"
        pred = (model_preds or {}).get(gk, {})
        ml_dir = (pred.get("consensus_ml_direction") or "").lower().strip()
        ml_edge = float(pred.get("consensus_ml_edge") or 0.0)
        ml_conf = float(pred.get("consensus_ml_confidence") or 0.5)
        if ml_dir not in ("home", "away") or ml_edge <= 0:
            continue
        cat = "ml_home" if ml_dir == "home" else "ml_away"
        candidates.append({
            "game_idx": i + 1,  # 1-indexed in prompt space
            "category": cat,
            "edge": ml_edge,
            "confidence": ml_conf,
            "matchup": f"{g['away']}@{g['home']}",
        })
    if not candidates:
        return None
    candidates.sort(key=lambda c: c["edge"], reverse=True)
    # Per-agent rotation: shift into the top pool by tid hash so not all 17
    # agents pile on the exact same 3 picks on a global LLM-outage day.
    # COLLISION_MAX_AGENTS=3 would otherwise reject 14/17 agents here.
    if tid and len(candidates) > 3:
        import hashlib as _hl
        _shift_range = max(1, min(6, len(candidates) - 3))
        _shift = int(_hl.sha1(tid.encode()).hexdigest()[:4], 16) % _shift_range
        candidates = candidates[_shift:] + candidates[:_shift]
    top = candidates[:3]
    if not top:
        return None
    # Even-split whatever the top-N size is, aiming at 75% total deploy.
    per_alloc_pct = 0.75 / len(top)
    allocations = []
    for c in top:
        allocations.append({
            "game_idx": c["game_idx"],
            "category": c["category"],
            "pct": per_alloc_pct,
            "confidence": c["confidence"],
            "edge": c["edge"],
            "rationale": "UNIFORM_FALLBACK: LLM (primary+hot-swap) failed; "
                         "betting top-3 model-edge moneylines per $1M doctrine "
                         "(provider_status=fallback_uniform)",
            "provider_status": "fallback_uniform",
        })
    return {
        "day_strategy": "FALLBACK_UNIFORM: LLM infrastructure failure — top-3 ML edges, even split 25% (75% deploy floor).",
        "cash_held_pct": round(1.0 - per_alloc_pct * len(top), 4),
        "cash_rationale": "25% reserve; 75% deployed per MIN_DEPLOY_PCT doctrine when LLM dead.",
        "allocations": allocations,
        "parlays": [],
        "coalition_proposal": None,
        "council_alignment": None,
        "games_considered": [],
        "fallback_used": True,
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
                                  pact_events: Optional[List[dict]] = None,
                                  day_idx: int = 0) -> str:
    """Build COMMON_KNOWLEDGE[D] block: full transparency for day D+1 prompts.

    Implements Axelrod-2026 Mechanism A (day-end common knowledge broadcast).
    All agents see ALL other agents' bets, results, strategies, and bankrolls
    from the last 3 days, enabling true collective optimization.
    """
    n_traders = len(TRADERS)
    total_start = n_traders * 100.0
    lines = [
        f"=== COMMON KNOWLEDGE — Day {day_date} (full transparency) ===",
        f"COLLECTIVE GOAL: maximize TOTAL GROUP bankroll → target ${total_start:,.0f} ($100×{n_traders} start).",
        f"You are ONE of {n_traders} traders. Every bet you make affects the group.",
        "",
    ]

    # Leaderboard with collective stats
    ranked = sorted(state.items(), key=lambda x: -x[1]["bankroll"])
    total_bankroll = sum(ts["bankroll"] for _, ts in ranked)
    total_bets = sum(ts["total_bets"] for _, ts in ranked)
    total_wins = sum(ts["wins"] for _, ts in ranked)
    lines.append(f"GROUP TOTAL: ${total_bankroll:.2f} (started ${total_start:,.0f}) | "
                 f"ROI {((total_bankroll / total_start) - 1) * 100:+.1f}% | "
                 f"{total_bets} bets | {total_wins}W")
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

    # 3-day rolling bet history from ALL agents (full transparency)
    all_dates = set()
    for tid in state:
        for log in agent_logs.get(tid, []):
            all_dates.add(log.get("date", ""))
    recent_dates = sorted(all_dates)[-3:]

    for past_date in recent_dates:
        lines.append(f"\n--- ALL BETS on {past_date} (resolved) ---")
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
                    _rat = (a.get('rationale') or '')[:60]
                    _rat_sfx = f' [{_rat}]' if _rat else ''
                    lines.append(
                        f"  {name}: {a['game']} {a['category']} "
                        f"${a.get('stake', 0):.1f} edge={a.get('edge', 0):.3f}→{outcome} "
                        f"pnl={a.get('profit', 0):+.1f}{_rat_sfx}")
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
                f"on game#{ev['game_idx']} {ev['category']}"
            )

    # Council day protocol — every 15 days, agents reorganize
    is_council_day = (day_idx > 0 and day_idx % 15 == 0)
    if is_council_day:
        lines.append(
            "\n=== COUNCIL DAY (every 15 days) ===\n"
            "Today is a strategy reorganization day. In addition to your bets,\n"
            "add a 'council_vote' field to your JSON:\n"
            "  \"council_vote\": {\n"
            "    \"worst_strategy\": \"name of peer whose strategy should change\",\n"
            "    \"suggested_change\": \"what they should try instead\",\n"
            "    \"my_adjustment\": \"what I will change about my own strategy\"\n"
            "  }\n"
            "Review the 3-day history above. Identify what's working and what isn't.\n"
            "Agents in PRESERVATION MODE should lock capital (5% cap, moneylines only).\n"
            "TOP-3 agents should protect capital and mentor via coalition proposals.\n"
        )

    lines.append(
        "\nCOLLABORATION RULES:\n"
        "- You see ALL traders' bets from last 3 days. Learn, do not copy.\n"
        "- MANDATORY: do NOT duplicate the exact game/direction picked by >2 peers yesterday.\n"
        "- If your bankroll is in PRESERVATION MODE (<$50), max 5% per bet,\n"
        "  moneylines/standard spreads only, NO alt spreads/props/quarters.\n"
        "- TOP-3 traders: protect capital, use conservative base categories.\n"
        "- Propose coalitions with traders whose REASONING TEMPLATE differs from yours.\n"
        "\n"
        "ANTI-GROUPTHINK (DMAD — MANDATORY, enforced 2026-04-18):\n"
        "Post-mortem (d34 2025-11-09) found 8/17 NBA agents crashed ~47% simultaneously\n"
        "by chasing variance in 'RESCUE MODE'. To break consensus-ruin, your day_strategy\n"
        "MUST begin with EXACTLY ONE of:\n"
        "  STRUCTURAL DIVERGE [peer_name] (edge=XX.X%): <how your REASONING TEMPLATE\n"
        "    produces a different pick than peer's, cite your template>. MUST include\n"
        "    numerical edge citation ≥5.0% (e.g. 'edge=6.3%') or bet is rejected.\n"
        "  STRUCTURAL COMPLEMENT [peer_name] (edge=XX.X%): <how your pick fills a game\n"
        "    the peer ignored, cite both templates>. MUST include numerical edge ≥5.0%.\n"
        "CONSENSUS AGREE is FORBIDDEN — if your template converges with a peer, pick the\n"
        "second-best candidate from your template instead.\n"
        "POST-MORTEM DOCTRINE (2026-04-19, 51-day NBA review):\n"
        "Winners used FLAT-STAKE WIDE COVERAGE with strict EV threshold (≥6% edge, half-Kelly).\n"
        "Losers used HIGH-CONVICTION SINGLE PLAYS citing DIVERGE rhetoric without numerical edge;\n"
        "6 agents wiped 60-70% in a single day. NEW RULE: any bet WITHOUT a numerical edge ≥4%\n"
        "in the rationale is REJECTED by the post-filter. Kelly is capped at 0.5× all tiers.\n"
        "Per-bet cap reduced: Tier 1 20%, T2 15%, T3 12%, T4 10%. Single-day loss >40% →\n"
        "forced 100% cash the next day (circuit breaker).\n"
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
    deltas.sort(key=lambda x: x[1])  # ascending — worst first
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
        # Deterministic pick by tid-hash for reproducibility
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
    # 2026-04-22 PLUMBER RCA fix: do NOT reset _llm_calls/_llm_failures on every
    # run_experiment entry — that was the root cause of the "soft-restart:
    # calls=0" false-positive that PLUMBER traced and keepalive then re-kicked.
    # Lifetime counters are now only zeroed in /api/reset. Per-season metrics
    # live on the per-agent state (`state[tid]["llm_calls"]`).
    global _llm_calls, _llm_failures, _gateway_routed, _gateway_fallback, _started_utc
    if _started_utc is None:
        _started_utc = datetime.now(timezone.utc).isoformat()

    # Async pre-ping (non-blocking): wake any selfhost Spaces still in substitution pool.
    # 2026-04-18: primary selfhost agents swapped to GitHub Models, so this runs background-only.
    import concurrent.futures as _cf
    def _wake_selfhosts_async():
        urls = [v["url"].rsplit("/", 1)[0] for k, v in PROVIDERS.items() if k.startswith("selfhost:")]
        def _wake(u):
            try: requests.get(u + "/", timeout=15)
            except: pass
        with _cf.ThreadPoolExecutor(max_workers=8) as _ex:
            list(_ex.map(_wake, urls))
    threading.Thread(target=_wake_selfhosts_async, daemon=True).start()

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
            "force_cash_today": False,  # 2026-04-19 circuit breaker (prev day > 40% loss)
        }

    global _experiment_running, _experiment_state, _common_knowledge, _society_archetypes_by_day
    # 2026-04-22: claim atomically — /api/run gate already flipped this True under
    # _state_lock before spawning _bg, but reaffirm here for direct Gradio entry.
    with _state_lock:
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
                # merge what we saved; ensure new keys exist
                state[tid].update({k: v for k, v in saved_agents[tid].items() if k in state[tid]})
        start_from_day = saved.get("days_processed", 0)
        print(f"RESUMING from day {start_from_day}/{n_days}")
    elif saved and saved.get("completed") and saved.get("agents"):
        # 2026-04-17: multi-season compounding. Previous season finished —
        # carry the final bankrolls forward but reset per-season counters.
        # Without this, every /api/run resets to $100 and compound is capped
        # at one season. With it, $100 → $570 → $3,250 → ... across seasons.
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

    # 2026-04-18 FIX: seed _experiment_state NOW so /api/status returns real
    # bankrolls during resume-load (previously showed $100 until day N+1 finished).
    if saved and saved.get("agents"):
        try:
            _fb = max(state[t]["bankroll"] for t in state)
            _ld = max(state, key=lambda t: state[t]["bankroll"])
            with _state_lock:
                _experiment_state = {
                    "days_processed": int(saved.get("days_processed", 0)),
                    "days_total": n_days,
                    "games_processed": 0,
                    "games_total": n_games,
                    "completed": False,
                    "design": "day-bucket-v3",
                    "agents": {tid: {k: v for k, v in ts.items() if k not in ("history", "recent_decisions")}
                               for tid, ts in state.items()},
                    "updated": datetime.now(timezone.utc).isoformat(),
                    "season_target": SEASON_TARGET,
                    "fleet_best_bankroll": round(_fb, 2),
                    "fleet_leader": _ld,
                    "season_progress_pct": round((_fb / SEASON_TARGET) * 100.0, 4),
                    "resumed": True,
                }
            print(f"[resume-seed] fleet_best=${_fb:.2f} leader={_ld}")
        except Exception as _e:
            print(f"[resume-seed] failed: {_e}")

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
    if multi_season_seed:
        seed_total = sum(state[tid]["bankroll"] for tid in state)
        log_lines.append(f"MULTI-SEASON COMPOUND: seeded ${seed_total:,.2f} from prior season")
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

        # ── PHASE 1 (morning council) + PHASE 3 (rogue triggers) + PHASE 4 ($1M goal) ──
        fleet_best_bankroll = max((state[t]["bankroll"] for t in state), default=STARTING_CAPITAL)
        day_council_plan = run_morning_council(
            day_idx, day_date, day_games, day_odds_list,
            state, strategies, fleet_best_bankroll, model_preds=model_preds,
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
            log_lines.append(f"[day {day_idx+1}] ROGUES: {_n_rogues}/{len(state)} agents eligible to defect")

        # PHASE 1 — parallel LLM calls (all agents for this day fire concurrently).
        # Intra-day parallelism only; days remain sequential because CK broadcast
        # on day N+1 depends on day N resolution (Mech A).
        def _agent_llm_worker(tid_cfg):
            tid, cfg = tid_cfg
            provider = cfg["provider"]
            ts = state[tid]
            if ts["bankroll"] <= BANKRUPT_THRESHOLD:
                return tid, None
            system_prompt = AGENT_SYSTEM_PROMPTS.get(tid, "You are an NBA betting allocator.")
            _template = REASONING_TEMPLATES.get(tid)
            if _template:
                system_prompt = system_prompt + "\n\n" + _template
            system_prompt = system_prompt + build_stackelberg_role_block(tid, _stackelberg_leader)
            if tid in _sacrificial_assignments:
                system_prompt = system_prompt + build_sacrificial_system_suffix(_sacrificial_assignments[tid])
            elif tid in _challenge_assignments:
                system_prompt = system_prompt + build_challenge_block(tid, _challenge_assignments[tid], len(TRADERS))
            _pm_override = _load_prompt_override("nba", sim_date=day_date)
            system_prompt = AXELROD_CANON + _pm_override + "\n" + system_prompt
            _active_peers = [p for p in TRADERS if p != tid and state[p]["bankroll"] > BANKRUPT_THRESHOLD]
            _axl_block = _axelrod_advice_block(tid, _active_peers)
            if _axl_block:
                system_prompt = system_prompt + _axl_block
            # PHASE 1 — council plan block (all agents)
            _council_block = build_council_block(day_council_plan, tid, fleet_best_bankroll)
            if _council_block:
                system_prompt = system_prompt + _council_block
            # PHASE 3 — rogue permission (only emitted when a legal trigger fires)
            _rogue_block = build_rogue_block(day_rogue_state.get(tid, {}))
            if _rogue_block:
                system_prompt = system_prompt + _rogue_block
            # Survival floor only: <$20 = bankruptcy imminent, dampen bets.
            # Aggressive-compound doctrine preserved above $20. mistral-ministral
            # peaked at $10K (100×) proves the system works when not over-clamped.
            if ts["bankroll"] < 20.0:
                system_prompt += (
                    "\n\n[SURVIVAL FLOOR] Bankroll below $20 — one bad day from $0. "
                    "Tight caps auto-enforced (5%/bet, 50%/day, edge≥4%). Find ONE "
                    "high-confidence pick to survive and rebuild. No parlays."
                )
            user_prompt = build_day_prompt(
                day_date, day_games, day_odds_list, day_stand_list, day_form_list,
                ts, rosters=rosters, team_advanced=team_advanced,
                player_stats=player_stats, full_odds=full_odds,
                model_preds=model_preds, strategies=strategies,
                recent_decisions=ts.get("recent_decisions", []),
                common_knowledge_block=prev_day_ck,
                fleet_best_bankroll=fleet_best_bankroll,
                tid=tid,
            )
            try:
                raw = _call_llm(provider, system_prompt, user_prompt, timeout=12.0,
                               trace_name=f"nba-tf-day-{day_idx}",
                               trace_metadata={"trader_id": tid, "day": day_date, "bankroll": ts["bankroll"]})
            except Exception:
                raw = None
            # Fallback provider if primary fails
            if not raw and cfg.get("fallback_provider"):
                try:
                    raw = _call_llm(cfg["fallback_provider"], system_prompt, user_prompt, timeout=12.0,
                                   trace_name=f"nba-tf-day-{day_idx}-fallback",
                                   trace_metadata={"trader_id": tid, "day": day_date, "fallback": True})
                except Exception:
                    pass
            return tid, raw

        _max_workers = min(len(TRADERS), 4)
        _responses = {}
        _pool = ThreadPoolExecutor(max_workers=_max_workers)
        _futures = {_pool.submit(_agent_llm_worker, item): item[0]
                    for item in list(TRADERS.items())}
        try:
            for _fut in as_completed(_futures, timeout=120.0):
                try:
                    _tid, _raw = _fut.result(timeout=1.0)
                    _responses[_tid] = _raw
                except Exception:
                    _responses[_futures[_fut]] = None
        except Exception:
            pass
        # Fill unfinished slots with None and drop the pool WITHOUT waiting.
        for _fut, _tid in _futures.items():
            if _tid not in _responses:
                _fut.cancel()
                _responses[_tid] = None
        _pool.shutdown(wait=False, cancel_futures=True)

        # Flush Langfuse batch so traces land before the day takes minutes more.
        if _langfuse:
            try:
                _langfuse.flush()
            except Exception:
                pass

        # PHASE 2 — sequential resolution (shared state mutations stay ordered).
        # 2026-04-19 collision tracker: (game_idx, category) → count of agents
        # who have taken this exact pair today. Blocks >COLLISION_MAX_AGENTS.
        # Post-mortem found winners had unique exposure; losers clustered.
        day_collisions: Dict[tuple, int] = {}
        for tid, cfg in TRADERS.items():
            provider = cfg["provider"]
            ts = state[tid]
            bankroll = ts["bankroll"]

            if bankroll <= BANKRUPT_THRESHOLD:
                # Bankrupt — skip, record history
                ts["passes"] += 1
                ts["history"].append(bankroll)
                continue

            # 2026-04-19 — single-day circuit breaker. If previous day's loss
            # exceeded SINGLE_DAY_WIPEOUT_THRESHOLD (40%), force 100% cash
            # today and reset the flag. Post-mortem showed 6 agents wiped
            # 60-70% in a single day, never recovered.
            if ts.get("force_cash_today"):
                ts["passes"] += 1
                ts["history"].append(bankroll)
                ts["force_cash_today"] = False
                _agent_logs[tid].append({
                    "day_idx": day_idx, "date": day_date, "n_games": len(day_games),
                    "bankroll_before": round(bankroll, 2),
                    "bankroll_after": round(bankroll, 2),
                    "day_strategy": "CIRCUIT_BREAKER: >40% loss yesterday → forced 100% cash today",
                    "cash_held_pct": 1.0,
                    "cash_rationale": "single-day wipeout guard (2026-04-19 doctrine)",
                    "allocations": [], "parlays": [],
                    "raw_preview": "",
                })
                continue

            raw_response = _responses.get(tid)
            ts["llm_calls"] += 1
            if raw_response:
                ts["llm_ok"] += 1
            # 2026-04-20 — pass current drawdown so MIN_DEPLOY_PCT floor can shrink
            # for ruined agents (dd>0.5 → floor drops, dd>0.9 → floor=0.25).
            _ts_dd = float(ts.get("max_drawdown", 0.0) or 0.0)
            parsed = parse_day_allocation(raw_response, len(day_games), drawdown=_ts_dd, tid=tid) if raw_response else None

            # 2026-04-18 — PRE-FILTER ml_home fallback REMOVED.
            # Post-mortem showed 16/16 agents silent on day 44 all injected identical
            # 75% ml_home bets, reproducing the exact groupthink-ruin vector this file
            # claims to fix. Fabricated bets with synthetic edge=0.03 bypass the
            # scientific integrity of the experiment: LLM silence is a REAL signal
            # (rate limit, provider down) and must NOT be papered over.
            #
            # 2026-04-19 — UNIFORM FALLBACK REINSTATED under strict conditions.
            # Distinction:
            #   (a) raw_response is None  → LLM infrastructure failure
            #       (primary + hot-swap BOTH dead). Agents can't reason.
            #       $1M COLLECTIVE_MISSION mandates ≥75% deploy EVERY day →
            #       emit uniform fallback (top-3 model-edge ML, even split).
            #       Tagged provider_status="fallback_uniform" + fallback_used=True
            #       so audit/post-mortem can exclude these from skill metrics.
            #   (b) raw_response is non-None but parse empty → informed LLM pass.
            #       Scientific integrity: preserve the silence (no fabrication).
            _day_fallback_used = False
            # 2026-04-19 BUGFIX #3 — remember coalition_proposal emitted by the LLM
            # BEFORE either the uniform-fallback or silent-pass overwrites `parsed`.
            # Previously pacts were silently dropped in ~25% of days (audit evidence:
            # 4-5 silent_cp per sample day in NBA) because the overwrite always set
            # coalition_proposal=None. Coalition is metadata about intent and does
            # not depend on allocations existing — it must survive.
            _preserved_coalition = (parsed or {}).get("coalition_proposal")
            if not parsed or not parsed.get("allocations"):
                # 2026-04-21 INTERNAL AFFAIRS RCA patch #1 — UNIFORM_FALLBACK emits
                # fabricated top-3 ML edges that produced the "fallback-identity
                # cluster" (9 agents at WR 55-65%, bled to 97-99% drawdown). Gate
                # behind UNIFORM_FALLBACK_ENABLED env (default "0"). When disabled
                # (default), llm_failed_both → all-cash silent-pass (scientifically
                # clean signal, no fabricated bets).
                if raw_response is None and os.environ.get("UNIFORM_FALLBACK_ENABLED", "0") == "1":
                    _fb = build_uniform_fallback_nba(day_date, day_games, day_odds_list, model_preds, tid=tid)
                    if _fb and _fb.get("allocations"):
                        parsed = _fb
                        _day_fallback_used = True
                if not parsed or not parsed.get("allocations"):
                    parsed = {
                        "day_strategy": "LLM_SILENT_PASS: no synthetic bets; POST-FILTER will attempt model-edge fallback.",
                        "cash_held_pct": 1.0,
                        "cash_rationale": "LLM silent — no fabricated deployment (scientific-integrity fix 2026-04-18)",
                        "allocations": [],
                        "parlays": [],
                        "coalition_proposal": _preserved_coalition,
                    }

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
                "parlays": [],      # parlay outcomes (2026-04-17)
                "rogue": day_rogue_state.get(tid, {"is_rogue": False}),
                "council_commit_target": day_council_plan.get("per_agent_commit_pct", {}).get(tid, 0.55),
                "council_alignment": (parsed or {}).get("council_alignment"),
                "games_considered": (parsed or {}).get("games_considered") or [],
                "raw_preview": (raw_response or "")[:3000],
                "fallback_used": _day_fallback_used,  # 2026-04-19 uniform-fallback tag
                "provider_status": "fallback_uniform" if _day_fallback_used else "llm_ok",
            }

            # Mech D — stash coalition proposal even if allocations are empty.
            # Also propagate to day_log for scientific observability (was missing
            # pre-2026-04-18 → coalition_proposal always None in day-XXX.json).
            if parsed and parsed.get("coalition_proposal"):
                day_proposals[tid] = parsed["coalition_proposal"]
                day_log["coalition_proposal"] = parsed["coalition_proposal"]

            if parsed and parsed.get("allocations"):
                day_log["day_strategy"] = parsed["day_strategy"]
                day_log["cash_held_pct"] = parsed["cash_held_pct"]
                day_log["cash_rationale"] = parsed["cash_rationale"]

                # Stake-sizing (2026-04-17 v2): traders can SPLIT bankroll across
                # all games of the day (diversified Kelly), but no single bet may
                # exceed 10%. Daily cap at 60% keeps 40% reserve for drawdown.
                # Rationale: multi-Kelly says if bets are ~independent with +EV,
                # you can size near individual Kelly fractions simultaneously.
                # NBA games within a day are mostly independent → diversification
                # works. 60% cap vs 100% protects against correlated down days.
                # Previous v1 (0.05/0.25) was too conservative — only ~25% of
                # bankroll working per day, compound rate capped.
                # 2026-04-18 v3 — TIERED AGGRESSION (gambler's ruin doctrine).
                # Floors + Kelly aggression scaled by bankroll tier. No per-bet
                # cap below Kelly. Low bankrolls compound out; high bankrolls
                # diversify. Post-filter pads to min_allocs/min_cats/min_games.
                tier = _tiered_risk(ts["bankroll"])
                MAX_PCT_PER_BET = tier["bet_cap"]
                MIN_BET_PCT = tier["bet_floor"]
                MAX_PCT_PER_DAY = 0.98       # near-all-in ceiling (1.0 would break bankrupt-check)
                MIN_EDGE = tier["min_edge"]
                KELLY_MULT = tier["kelly_mult"]
                # 2026-04-21 INTERNAL AFFAIRS RCA patch #3 — peak-equity drawdown clamp.
                # gemini-anl peaked $170.79 day N then bled to $29.02 (-83% of peak)
                # because stake size kept compounding on declining bankroll. Clamp:
                # <50% of peak → stake cap 1% + forbid parlays; <25% of peak → force
                # cash (ALL_PASS). Gated by PEAK_DD_GUARD_V2=1 (default on 2026-04-21).
                _pdd_on = os.environ.get("PEAK_DD_GUARD_V2", "1") == "1"
                _pdd_force_cash = False
                _pdd_forbid_parlays = False
                if _pdd_on:
                    _pdd_peak = max(float(ts.get("best_bankroll") or 0.0), ts["bankroll"])
                    _pdd_ratio = (ts["bankroll"] / _pdd_peak) if _pdd_peak > 0 else 1.0
                    if _pdd_ratio < 0.25:
                        _pdd_force_cash = True
                    elif _pdd_ratio < 0.50:
                        MAX_PCT_PER_BET = min(MAX_PCT_PER_BET, 0.01)
                        _pdd_forbid_parlays = True
                BASE_CATS = {"ml_home","ml_away","spread_home","spread_away","total_over","total_under"}
                day_exposure_pct = 0.0
                if _pdd_force_cash:
                    # <25% of peak equity → survival mode. All-cash, skip allocs+parlays.
                    # Tags cash_rationale for audit; allocations list stays empty.
                    day_log["cash_rationale"] = f"PEAK_DD_GUARD_V2: bankroll/peak<0.25, force cash (bankroll=${ts['bankroll']:.2f})"
                    parsed = {**parsed, "allocations": [], "parlays": [],
                              "cash_held_pct": 1.0,
                              "peak_dd_guard": "force_cash"}
                for alloc in parsed["allocations"]:
                    gidx = alloc["game_idx"] - 1  # 1-indexed in prompt
                    if gidx < 0 or gidx >= len(day_games):
                        continue
                    g = day_games[gidx]
                    odds = day_odds_list[gidx]
                    cat = alloc["category"]

                    edge_val = alloc.get("edge", 0.0) or 0.0
                    # FULL FREEDOM 2026-04-18 — user directive: agents are absolutely free
                    # to bet on any of 227 categories with whatever edge they claim.
                    # Only safety: MIN_EDGE (0.02, near-zero) to block explicit -EV claims.
                    # Removed BASE_CATS FDR gate entirely — LLMs now access the full tail.
                    # Bankroll compound rule (_tiered_risk) still enforces sizing discipline.
                    if edge_val < MIN_EDGE:
                        continue
                    # 2026-04-19 collision limiter: if >=COLLISION_MAX_AGENTS
                    # already picked this (game_idx, category) today, skip.
                    # Forces structural divergence at the allocation level.
                    # 2026-04-21 exception: fallback_uniform allocations are NOT
                    # agent-chosen (LLM outage → system-emitted top-3 ML edges).
                    # Collision gate would wipe 14/17 agents' allocations when the
                    # whole fleet hits the fallback on a small-game-day (2-4 games),
                    # which is exactly what happened to selfhost-gemma3/dolphin3
                    # (0 bets in 17 days). Bypass the gate for fallback allocs so
                    # every agent still trades — groupthink concern doesn't apply
                    # when the LLM wasn't the decision-maker.
                    coll_key = (alloc["game_idx"], cat)
                    _is_fallback_alloc = (
                        parsed.get("fallback_used") is True
                        or alloc.get("provider_status") == "fallback_uniform"
                    )
                    if (not _is_fallback_alloc) and day_collisions.get(coll_key, 0) >= COLLISION_MAX_AGENTS:
                        continue
                    # Tiered sizing: Kelly aggression × LLM pct, floor at bet_floor, cap at bet_cap.
                    sized_pct = (alloc["pct"] or 0.0) * KELLY_MULT
                    capped_pct = max(MIN_BET_PCT, min(sized_pct, MAX_PCT_PER_BET))
                    # Daily cumulative guard: shrink if day exposure would exceed 98%.
                    remaining_day = max(0.0, MAX_PCT_PER_DAY - day_exposure_pct)
                    capped_pct = min(capped_pct, remaining_day)
                    if capped_pct <= 0:
                        continue
                    stake = round(ts["bankroll"] * capped_pct, 2)
                    if stake > ts["bankroll"]:
                        stake = round(ts["bankroll"] * 0.99, 2)
                    if stake < 0.10:
                        continue
                    day_exposure_pct += capped_pct
                    day_collisions[coll_key] = day_collisions.get(coll_key, 0) + 1

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

                    # 2026-04-21 proposal #1 — feed resolved bet into rolling ECE
                    # window. alloc["confidence"] is agent-stated P(win); `won` is
                    # the realized outcome. Skip silently if update fails.
                    try:
                        update_agent_calibration(tid, alloc.get("confidence", 0.5),
                                                 1 if won else 0)
                    except Exception as _ce:
                        print(f"[calib] update skipped for {tid}: {_ce}")

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
                        "provider_status": alloc.get("provider_status", "llm_ok"),  # 2026-04-19 fallback tag
                    })
                    # Mech D — record actual (game_idx, category) pairs for coalition resolution
                    day_actual_bets.setdefault(tid, set()).add((alloc["game_idx"], cat))

                # ── PARLAY RESOLUTION (2026-04-17) ──
                # Each parlay: all legs must win for payout. Combined odds =
                # product of leg decimal odds. Stake capped at MAX_PCT_PER_BET.
                day_log["parlays"] = []
                _parlay_iter = [] if _pdd_forbid_parlays else (parsed.get("parlays", []) or [])
                for parlay in _parlay_iter:
                    pedge = parlay.get("edge", 0.0) or 0.0
                    if pedge < MIN_EDGE:
                        continue
                    capped_pct = min(parlay["pct"], MAX_PCT_PER_BET)
                    remaining_day = max(0.0, MAX_PCT_PER_DAY - day_exposure_pct)
                    capped_pct = min(capped_pct, remaining_day)
                    if capped_pct <= 0:
                        continue
                    p_stake = round(ts["bankroll"] * capped_pct, 2)
                    if p_stake < 0.50 or p_stake > ts["bankroll"]:
                        continue

                    leg_details = []
                    combined_odds = 1.0
                    all_won = True
                    bad_leg = False
                    for leg in parlay["legs"]:
                        lgidx = leg["game_idx"] - 1  # 1-indexed
                        if lgidx < 0 or lgidx >= len(day_games):
                            bad_leg = True
                            break
                        lg = day_games[lgidx]
                        lodds = day_odds_list[lgidx]
                        lcat = leg["category"]
                        leg_won = resolve_bet(lcat, lodds, lg["home_score"], lg["away_score"], lg["home_won"])
                        leg_odds_dec = get_odds_dec(lcat, lodds)
                        combined_odds *= leg_odds_dec
                        if not leg_won:
                            all_won = False
                        leg_details.append({
                            "game": f"{lg['away']}@{lg['home']}",
                            "category": lcat,
                            "odds": round(leg_odds_dec, 3),
                            "won": leg_won,
                        })
                    if bad_leg:
                        continue

                    day_exposure_pct += capped_pct
                    if all_won:
                        profit = p_stake * (combined_odds - 1)
                        ts["bankroll"] += profit
                        ts["wins"] += 1
                    else:
                        profit = -p_stake
                        ts["bankroll"] -= p_stake
                        ts["losses"] += 1
                    ts["total_bets"] += 1
                    ts["bankroll"] = round(ts["bankroll"], 2)

                    day_log["parlays"].append({
                        "legs": leg_details,
                        "n_legs": len(leg_details),
                        "pct": round(parlay["pct"], 4),
                        "stake": p_stake,
                        "combined_odds": round(combined_odds, 3),
                        "confidence": parlay["confidence"],
                        "edge": round(parlay["edge"], 4),
                        "rationale": parlay["rationale"],
                        "won": all_won,
                        "profit": round(profit, 2),
                    })
            else:
                ts["passes"] += 1  # full-cash day

            # TIER-PAD POST-FILTER REMOVED 2026-04-19: deterministic fallback padded
            # all 17 agents to identical picks → mean Jaccard 0.625 (max 1.0) lockstep.
            # New doctrine: empty LLM output = full-cash day. No fabricated picks.

            # Track recent decisions for next-day prompt
            n_bets = len(day_log["allocations"]) + len(day_log["parlays"])
            n_wins = sum(1 for a in day_log["allocations"] if a["won"]) + sum(1 for p in day_log["parlays"] if p["won"])
            n_parlays = len(day_log["parlays"])
            day_pnl = ts["bankroll"] - bankroll
            # 2026-04-19 circuit breaker: flag next day for 100% cash if today's
            # loss exceeded SINGLE_DAY_WIPEOUT_THRESHOLD of starting bankroll.
            if bankroll > 0 and (day_pnl / bankroll) < -SINGLE_DAY_WIPEOUT_THRESHOLD:
                ts["force_cash_today"] = True
            summary = f"{n_bets} bets ({n_parlays}p), {n_wins}W, pnl {day_pnl:+.2f}"
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
            day_idx=day_idx,
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
        _fleet_best_live = max(state[t]["bankroll"] for t in state)
        _leader_live = max(state, key=lambda t: state[t]["bankroll"])
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
                # Collective experiment (2026-04-17)
                "season_target": SEASON_TARGET,
                "fleet_best_bankroll": round(_fleet_best_live, 2),
                "fleet_leader": _leader_live,
                "season_progress_pct": round((_fleet_best_live / SEASON_TARGET) * 100.0, 4),
                "council_plan": day_council_plan,
                "rogue_this_day": {t: r for t, r in day_rogue_state.items() if r["is_rogue"]},
            }
        # Persist EVERY day so councils/analysis can read decision trail even
        # if a Space restart wipes /tmp mid-run. state.json = latest resume
        # point; data/decisions/day-XXX.json = per-day per-agent full rationale.
        # Parallel Hub pushes — 4 independent uploads fire concurrently. Saves
        # ~8-10s per day vs sequential. No shared-state races: each function
        # targets its own file on Hub.
        _day_logs_for_hub = {
            tid: _agent_logs[tid][-1]
            for tid in TRADERS if _agent_logs.get(tid) and _agent_logs[tid]
            and _agent_logs[tid][-1].get("date") == day_date
        }
        _hub_tasks = [
            lambda: _save_state_to_disk(_experiment_state),
            lambda: _save_logs_to_disk(),
        ]
        if _day_logs_for_hub:
            _hub_tasks.append(lambda: _push_day_decisions_to_hub(
                day_idx=day_idx, day_date=day_date, n_games=len(day_games),
                day_logs_by_agent=_day_logs_for_hub,
                day_council_plan=day_council_plan,
                day_rogue_state=day_rogue_state,
            ))
        with ThreadPoolExecutor(max_workers=len(_hub_tasks)) as _hub_pool:
            list(_hub_pool.map(lambda fn: fn(), _hub_tasks))

        if (day_idx + 1) % 1 == 0:  # Yield every day (slower pace than games)
            elapsed = time.time() - start_time
            days_done = day_idx + 1
            rate = days_done / (elapsed / 60) if elapsed > 0 else 0
            eta_min = (n_days - days_done) / rate if rate > 0 else 0

            try:
                progress(days_done / n_days,
                         desc=f"Day {days_done}/{n_days} | {rate:.2f} days/min | ETA {eta_min:.0f}min")
            except Exception:
                pass

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
    # 2026-04-22 PLUMBER RCA fix: do NOT flip _experiment_running=False here.
    # The outer _bg/_auto_start wrapper uses `while not _stop_event.is_set()`
    # to immediately loop back into run_experiment for multi-season compound.
    # Flipping False created a ~0.5s race window where keepalive saw
    # running=false and POSTed /api/run → second generator → reset false alert.
    # The wrapper resets state on re-entry if the season completed.

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
    state["started_utc"] = _started_utc  # 2026-04-22: set on first run_experiment entry, survives soft restarts
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
    # Provider health snapshot (circuit breaker + hot-swap, 2026-04-17).
    if _PH_AVAILABLE:
        try:
            state["provider_health"] = _ph.get_snapshot()
        except Exception:
            pass
    # Langfuse trace-send errors (first 20, captured 2026-04-18)
    state["langfuse_errors"] = list(_langfuse_errors[:20])
    state["langfuse_errors_count"] = len(_langfuse_errors)
    state["langfuse_enabled"] = bool(_langfuse)
    return JSONResponse(state)

@api.post("/api/run")
async def api_run(request: Request):
    """Trigger experiment start (same as clicking the button).
    For GH Actions / council triggers. Non-blocking — returns immediately.

    2026-04-22 PLUMBER RCA fix: atomic gate under _state_lock so keepalive +
    auto_start cannot both enter run_experiment and clobber each other's
    _llm_calls / state.
    """
    global _experiment_running
    _stop_event.clear()
    # Atomic claim — check+flip under _state_lock to kill the race window.
    with _state_lock:
        if _experiment_running:
            return JSONResponse({
                "status": "resumed",
                "games_processed": _experiment_state.get("games_processed", 0),
                "message": "Stop flag cleared, experiment continues.",
            })
        _experiment_running = True  # claim BEFORE spawning _bg — no second /api/run can enter
    import threading, traceback as _tb
    def _bg():
        global _experiment_running
        try:
            # 2026-04-22: while-not-stop loop. run_experiment no longer flips
            # _experiment_running=False on season end, so we re-enter for the
            # next season (multi-season compound). Only _stop_event exits.
            while not _stop_event.is_set():
                try:
                    for _ in run_experiment():
                        pass
                except Exception as e:
                    print(f"[api_run bg] run crashed: {e}\n{_tb.format_exc()}")
                    import time as _t; _t.sleep(10)
                    continue
                # Clean completion — brief pause before next season to avoid tight loop.
                import time as _t; _t.sleep(5)
        finally:
            # Only clear on explicit stop or permanent failure.
            with _state_lock:
                _experiment_running = False
    threading.Thread(target=_bg, daemon=True, name="api_run_bg").start()
    return JSONResponse({"status": "started", "message": "Experiment launched in background thread."})

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
    global _experiment_state, _agent_logs, _llm_calls, _llm_failures, _gateway_routed, _gateway_fallback, _started_utc
    _experiment_state = {}
    _agent_logs = defaultdict(list)
    # 2026-04-22 PLUMBER RCA fix: lifetime counters now ONLY zeroed here,
    # not on every run_experiment entry (which triggered the race).
    _llm_calls = 0
    _llm_failures = 0
    _gateway_routed = 0
    _gateway_fallback = 0
    _started_utc = None
    try:
        STATE_PATH.unlink(missing_ok=True)
        LOGS_PATH.unlink(missing_ok=True)
    except Exception:
        pass
    # Also purge Hub-persisted state — otherwise auto-resume downloads
    # data/runtime/state.json on next boot and we silently resume.
    hub_deleted = []
    if _hub_api:
        for fname in ("data/runtime/state.json",
                      "data/runtime/agent_logs.json",
                      "data/runtime/council_plans.json"):
            try:
                _hub_api.delete_file(path_in_repo=fname, repo_id=HF_REPO_ID,
                                     repo_type="space",
                                     commit_message=f"reset: purge {fname}")
                hub_deleted.append(fname)
            except Exception as e:
                print(f"[reset] hub delete {fname} failed: {e}")
    return JSONResponse({"status": "reset", "message": "State cleared. Next run starts fresh.",
                         "hub_deleted": hub_deleted})

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
async def api_leaderboard(mode: str = "cumulative"):
    """Current leaderboard as JSON.

    ?mode=cumulative (default) — sort by bankroll (season-long ROI)
    ?mode=per_day              — sort by daily ROI (roi_pct / days_traded), rewards
                                 consistent per-day performance over big-bet outliers
    ?mode=consistency          — sort by (wins / total_bets) with min 10 bets
    """
    with _state_lock:
        agents = _experiment_state.get("agents", {})
    if not agents:
        return JSONResponse({"status": "no_data", "message": "No experiment data yet"})
    lb = []
    for tid, ts in agents.items():
        cfg = TRADERS.get(tid, {})
        bankroll = ts.get("bankroll", 100)
        roi = ((bankroll - 100) / 100) * 100
        days_traded = max(1, ts.get("days_traded", 1))
        total_bets = ts.get("total_bets", 0)
        wins = ts.get("wins", 0)
        per_day_roi = roi / days_traded
        win_rate = wins / total_bets if total_bets > 0 else 0.0
        lb.append({
            "trader_id": tid,
            "name": cfg.get("name", tid),
            "provider": cfg.get("provider", "?"),
            "bankroll": round(bankroll, 2),
            "roi_pct": round(roi, 2),
            "per_day_roi_pct": round(per_day_roi, 3),
            "days_traded": ts.get("days_traded", 0),
            "total_bets": total_bets,
            "wins": wins,
            "losses": ts.get("losses", 0),
            "win_rate": round(win_rate, 3),
            "max_drawdown": round(ts.get("max_drawdown", 0.0), 4),
            "best_bankroll": round(ts.get("best_bankroll", bankroll), 2),
        })
    # Sort per mode
    if mode == "per_day":
        lb.sort(key=lambda x: -x["per_day_roi_pct"])
    elif mode == "consistency":
        lb = [x for x in lb if x["total_bets"] >= 10]
        lb.sort(key=lambda x: -x["win_rate"])
    else:  # cumulative
        lb.sort(key=lambda x: -x["bankroll"])
    return JSONResponse({
        "leaderboard": lb,
        "mode": mode,
        "games_processed": _experiment_state.get("games_processed", 0),
        "days_processed": _experiment_state.get("days_processed", 0),
    })


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

# ── MODULE-LEVEL HUB PRE-SEED (2026-04-22 PLUMBER RCA fix) ─────────────────
# Load Hub state synchronously at import time so /api/status never returns
# fresh-init defaults ($100 for every agent) during the ~0.5s window between
# uvicorn binding and the first run_experiment reaching its resume-seed block.
try:
    _preseed = _load_state_from_disk()
    if _preseed and _preseed.get("agents"):
        with _state_lock:
            _experiment_state = dict(_preseed)
            _experiment_state.setdefault("days_processed", int(_preseed.get("days_processed", 0)))
            _experiment_state.setdefault("days_total", int(_preseed.get("days_total", 0)))
            # Flag the source so monitoring can distinguish pre-seed from post-run state.
            _experiment_state["_source"] = "hub_preseed"
            _experiment_state["_preseeded_utc"] = datetime.now(timezone.utc).isoformat()
        _pfb = max((a.get("bankroll", 100.0) for a in _preseed.get("agents", {}).values()), default=100.0)
        print(f"[hub-preseed] loaded state.json — day {_preseed.get('days_processed',0)}, fleet_best ${_pfb:.2f}")
    else:
        print("[hub-preseed] no saved state (fresh install or Hub unavailable)")
except Exception as _e:
    print(f"[hub-preseed] failed: {_e}")

# Auto-start experiment on Space boot (survives rebuilds)
# Set SKIP_AUTO_START=1 env var to boot idle (for purge workflows).
def _auto_start():
    global _experiment_running
    import time as _t, traceback as _tb
    if os.environ.get("SKIP_AUTO_START") == "1":
        print("[auto-start] SKIP_AUTO_START=1 set, boot-idle mode")
        return
    _t.sleep(10)
    # 2026-04-22: atomic claim — lose the race silently if /api/run already started.
    with _state_lock:
        if _experiment_running:
            print("[auto-start] /api/run already claimed — standing down")
            return
        _experiment_running = True
    print("[auto-start] launching experiment on boot (while-not-stop loop)")
    try:
        while not _stop_event.is_set():
            try:
                for _ in run_experiment():
                    pass
            except Exception as e:
                print(f"[auto-start] run crashed: {e}\n{_tb.format_exc()}")
                _t.sleep(15)
                continue
            # Multi-season compound — brief pause before next season.
            _t.sleep(5)
    finally:
        with _state_lock:
            _experiment_running = False

threading.Thread(target=_auto_start, daemon=True, name="auto_start").start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
