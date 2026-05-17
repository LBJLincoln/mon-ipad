"""Nomos42 Political LLM Trading Floor — HuggingFace Spaces
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

# Island oracle — bridges POL TF agents to P7's calibrated xgboost/extra_trees model.
# Fail-open: if P7 is down, oracle returns {} and prompts skip the ORACLE line.
try:
    from island_oracle import pol_oracle_predict as _island_pol_predict
    _POL_ORACLE_OK = True
except Exception as _orc_err:
    print(f"[pol-oracle] import failed: {_orc_err}")
    _POL_ORACLE_OK = False
    def _island_pol_predict(*a, **kw): return {}

# ── STARTUP DIAGNOSTICS ─────────────────────────────────────────────────────
print("=" * 60)
print("NOMOS42 POLITICAL LLM TRADING FLOOR — STARTUP")
print("=" * 60)
for k in ["CEREBRAS_API_KEY", "GOOGLE_API_KEY", "GOOGLE_API_KEY_2",
          "OPENROUTER_KEY_ORCHESTRATOR", "OPENROUTER_KEY_PME", "OPENROUTER_KEY_BARTOLI",
          "MISTRAL_API_KEY", "HF_TOKEN", "HF_DATASET_TOKEN",
          "GATEWAY_URL", "ISLAND_URL"]:
    v = os.environ.get(k, "")
    print(f"  {k}: {'SET (' + str(len(v)) + ' chars)' if v else 'MISSING'}")
print("=" * 60)

# ── GATEWAY WRAPPER ──────────────────────────────────────────────────────────
def gateway_call(provider, model, messages, temperature=0.7, max_tokens=1800,
                 timeout=90, system=None):
    return _gateway_call(provider, model, messages,
                         temperature=temperature, max_tokens=max_tokens,
                         timeout=timeout, system=system)

GATEWAY_URL = _GATEWAY_URL

# ── CONSTANTS ────────────────────────────────────────────────────────────────
MAX_WORKERS  = 3
CEREBRAS_RPM = 30
CALL_DELAY   = 60 / CEREBRAS_RPM

# HF Hub dataset push
HF_DATASET_REPO  = "Nomos42/political-trading-floor-results"
HF_AXELROD_REPO  = "Nomos42/arena-axelrod-log"
HF_DATASET_TOKEN = os.environ.get("HF_DATASET_TOKEN", "")

# ── ARCHETYPES ────────────────────────────────────────────────────────────────
ARCHETYPES = [
    "macro_hawk",       "policy_contrarian",  "sector_rotator",
    "insider_tracker",  "fed_watcher",        "geopolitical_analyst",
    "esg_screener",     "momentum_trader",    "value_allocator",
    "risk_arbitrageur",
]

ARCHETYPE_DESCRIPTIONS = {
    "macro_hawk":           "Focuses on macro indicators: inflation, rates, GDP signals",
    "policy_contrarian":    "Fades consensus policy narratives, seeks mispriced political risk",
    "sector_rotator":       "Rotates between sectors based on policy exposure",
    "insider_tracker":      "Follows congressional insider trades and Form 4 filings",
    "fed_watcher":          "Monitors Fed statements, dot-plot shifts, FOMC minutes",
    "geopolitical_analyst": "Tracks geopolitical events: tariffs, sanctions, treaty risks",
    "esg_screener":         "Screens for ESG-driven policy impacts on sector ETFs",
    "momentum_trader":      "Chases political momentum: bills gaining traction, polls",
    "value_allocator":      "Seeks undervalued sectors post policy shock",
    "risk_arbitrageur":     "Arbitrages political event risk vs. market pricing",
}

PROVIDER_MODELS = [
    ("cerebras",  "llama-3.3-70b"),
    ("cerebras",  "llama-4-scout-17b-16e-instruct"),
    ("google",    "gemini-2.0-flash"),
    ("mistral",   "mistral-large-latest"),
    ("mistral",   "mistral-small-latest"),
    ("mistral",   "open-mistral-nemo"),
    ("mistral",   "codestral-latest"),
    ("mistral",   "open-mixtral-8x22b"),
    ("openrouter","mistralai/mistral-small-3.2-24b-instruct:free"),
    ("openrouter","microsoft/mai-ds-r1:free"),
]

# ── STATE ─────────────────────────────────────────────────────────────────────
_state_lock = threading.Lock()
_state = {
    "status":       "idle",
    "day_idx":      0,
    "total_days":   0,
    "agents":       [],
    "log":          [],
    "run_id":       None,
    "running":      False,
    "stop_flag":    False,
    "day_results":  [],
    "all_bets":     [],
    # Axelrod Mech B state
    "_challenge_assignments": {},   # agent_id → {challenger, challenged, tier}
    # Axelrod Mech A: common knowledge (broadcast at day-end)
    "_common_knowledge": "",
    # Axelrod: used archetypes per agent (7-day rolling)
    "_used_archetypes": {},         # agent_id → [archetype, ...]
}

def _gs(key, default=None):
    with _state_lock:
        return _state.get(key, default)

def _ss(key, value):
    with _state_lock:
        _state[key] = value

# ── PERSISTENCE ───────────────────────────────────────────────────────────────
STATE_FILE = "/tmp/pol_trading_floor_state.json"

def save_state():
    with _state_lock:
        snap = {k: v for k, v in _state.items() if k != "stop_flag"}
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(snap, f)
    except Exception as e:
        print(f"[state] save error: {e}")

def load_state():
    global _state
    if not os.path.exists(STATE_FILE):
        return False
    try:
        with open(STATE_FILE) as f:
            saved = json.load(f)
        with _state_lock:
            for k, v in saved.items():
                _state[k] = v
            _state["stop_flag"] = False
            _state["running"]   = False
        print(f"[state] Loaded: day={_state.get('day_idx')}, "
              f"agents={len(_state.get('agents', []))}")
        return True
    except Exception as e:
        print(f"[state] load error: {e}")
        return False

# ── POLITICAL DATA ────────────────────────────────────────────────────────────
SECTOR_ETFS = {
    "XLE":  "Energy",
    "XLF":  "Financials",
    "XLV":  "Healthcare",
    "XLI":  "Industrials",
    "XLB":  "Materials",
    "XLK":  "Technology",
    "XLU":  "Utilities",
    "XLRE": "Real Estate",
    "XLY":  "Consumer Discretionary",
    "XLP":  "Consumer Staples",
}

POLITICAL_EVENTS_SYNTHETIC = [
    {
        "date": "2026-03-12",
        "events": [
            {
                "type":     "executive_order",
                "title":    "EO 14210: Strategic Energy Reserve Expansion",
                "summary":  "Administration orders 50M barrel SPR refill. Boosts XLE, pressures XLY.",
                "affected": ["XLE", "XLY"],
                "signal":   "bullish_energy",
            },
            {
                "type":     "insider_trade",
                "title":    "Sen. Johnson buys $2.1M XLF (Goldman Sachs)",
                "summary":  "Senate Finance chair discloses large financial sector buy ahead of banking deregulation vote.",
                "affected": ["XLF"],
                "signal":   "bullish_financials",
            },
        ],
    },
    {
        "date": "2026-03-13",
        "events": [
            {
                "type":     "fed_statement",
                "title":    "FOMC: Rates held at 4.25-4.50%, hawkish dot-plot shift",
                "summary":  "Fed signals 2 cuts in 2026 vs prior 3. XLU and XLRE pressured; XLF benefits.",
                "affected": ["XLU", "XLRE", "XLF"],
                "signal":   "hawkish_rates",
            },
        ],
    },
    {
        "date": "2026-03-14",
        "events": [
            {
                "type":     "tariff_announcement",
                "title":    "25% tariff on EU steel/aluminum — effective April 1",
                "summary":  "Trade war escalation. XLB and XLI at risk; domestic steel producers may benefit.",
                "affected": ["XLB", "XLI"],
                "signal":   "tariff_risk",
            },
            {
                "type":     "insider_trade",
                "title":    "Rep. Smith sells $800K XLK (Nvidia)",
                "summary":  "House Armed Services member sells tech ahead of chip export control vote.",
                "affected": ["XLK"],
                "signal":   "bearish_tech",
            },
        ],
    },
    {
        "date": "2026-03-17",
        "events": [
            {
                "type":     "legislation",
                "title":    "Inflation Reduction Act Amendment — healthcare subsidy extension",
                "summary":  "Senate passes XLV-positive amendment extending ACA subsidies 5 years.",
                "affected": ["XLV"],
                "signal":   "bullish_healthcare",
            },
        ],
    },
    {
        "date": "2026-03-18",
        "events": [
            {
                "type":     "geopolitical",
                "title":    "Taiwan Strait naval incident — PLA exercises near ADIZ",
                "summary":  "Risk-off: XLU + XLP defensives up. XLY + XLK tech suppressed on supply chain fears.",
                "affected": ["XLU", "XLP", "XLY", "XLK"],
                "signal":   "risk_off_geopolitical",
            },
        ],
    },
    {
        "date": "2026-03-19",
        "events": [
            {
                "type":     "executive_order",
                "title":    "EO 14215: Broadband Infrastructure National Emergency",
                "summary":  "Federal broadband emergency declaration accelerates XLK capex cycle.",
                "affected": ["XLK", "XLI"],
                "signal":   "bullish_tech_infra",
            },
        ],
    },
    {
        "date": "2026-03-20",
        "events": [
            {
                "type":     "fed_statement",
                "title":    "Fed Chair testimony: 'Inflation still sticky above 3%'",
                "summary":  "Rate cut timeline pushed to Q4 2026. Bonds sell off; XLF benefits from higher-for-longer.",
                "affected": ["XLF", "XLRE", "XLU"],
                "signal":   "hawkish_rates_extended",
            },
            {
                "type":     "insider_trade",
                "title":    "Multiple senators buy XLE after closed-door energy briefing",
                "summary":  "5 senators disclose XLE buys ($500K-$3M each) day before offshore drilling EO.",
                "affected": ["XLE"],
                "signal":   "insider_bullish_energy",
            },
        ],
    },
    {
        "date": "2026-03-21",
        "events": [
            {
                "type":     "executive_order",
                "title":    "EO 14218: Offshore Drilling Moratorium Lifted",
                "summary":  "Atlantic and Pacific offshore drilling reopened. XLE surges; ESG-focused funds sell.",
                "affected": ["XLE", "XLB"],
                "signal":   "bullish_energy_offshore",
            },
        ],
    },
    {
        "date": "2026-03-24",
        "events": [
            {
                "type":     "legislation",
                "title":    "Infrastructure Investment Act — $800B roads/bridges/grid",
                "summary":  "Bipartisan bill passes Senate. XLI and XLB primary beneficiaries; XLU grid capex up.",
                "affected": ["XLI", "XLB", "XLU"],
                "signal":   "bullish_infrastructure",
            },
        ],
    },
    {
        "date": "2026-03-25",
        "events": [
            {
                "type":     "tariff_announcement",
                "title":    "China retaliates: 35% tariff on US agricultural exports",
                "summary":  "Trade war escalation. XLP (agri exposure) under pressure; XLB chemicals at risk.",
                "affected": ["XLP", "XLB"],
                "signal":   "bearish_agri_trade",
            },
            {
                "type":     "insider_trade",
                "title":    "Rep. Chen buys $1.5M XLV (UnitedHealth, Moderna)",
                "summary":  "House Health subcommittee chair buys healthcare ahead of Medicare pricing rule.",
                "affected": ["XLV"],
                "signal":   "insider_bullish_healthcare",
            },
        ],
    },
    {
        "date": "2026-03-26",
        "events": [
            {
                "type":     "geopolitical",
                "title":    "Middle East escalation: Houthi strikes on Red Sea shipping",
                "summary":  "Energy disruption risk. XLE spikes; XLI shipping-exposed names drop.",
                "affected": ["XLE", "XLI"],
                "signal":   "risk_on_energy_geopolitical",
            },
        ],
    },
]

def load_political_events():
    """Load political events — try HF dataset first, fall back to synthetic."""
    hf_token = os.environ.get("HF_TOKEN", "")
    if hf_token:
        try:
            url = "https://huggingface.co/datasets/Nomos42/political-events/resolve/main/events.json"
            resp = requests.get(url, headers={"Authorization": f"Bearer {hf_token}"}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                print(f"[data] Loaded {len(data)} political event days from HF Hub")
                return data
        except Exception as e:
            print(f"[data] HF load failed: {e}")
    print("[data] Using synthetic political events")
    return POLITICAL_EVENTS_SYNTHETIC

# ── AGENT INITIALISATION ──────────────────────────────────────────────────────
def initialise_agents():
    agents = []
    for i, (provider, model) in enumerate(PROVIDER_MODELS):
        archetype = ARCHETYPES[i % len(ARCHETYPES)]
        agents.append({
            "id":          i,
            "name":        f"Agent-{i+1}",
            "provider":    provider,
            "model":       model,
            "archetype":   archetype,
            "bankroll":    100_000.0,   # political traders start with $100K
            "bets_won":    0,
            "bets_lost":   0,
            "bets_push":   0,
            "total_bets":  0,
            "pnl":         0.0,
            "history":     [],
            "day_picks":   [],
        })
    return agents

# ── PROMPT BUILDERS ───────────────────────────────────────────────────────────
def build_leaderboard_block(agents, day_idx):
    """Top-5 + bottom-3 leaderboard with 7-day Δ."""
    sorted_agents = sorted(agents, key=lambda a: a["bankroll"], reverse=True)
    lines = ["=== GLOBAL LEADERBOARD (Top-5 / Bottom-3) ==="]
    for rank, ag in enumerate(sorted_agents[:5], 1):
        delta_7d = _compute_7d_delta(ag)
        lines.append(
            f"  #{rank} {ag['name']} ({ag['archetype']}): "
            f"${ag['bankroll']:,.0f}  7dΔ={delta_7d:+,.0f}"
        )
    lines.append("  ...")
    for rank, ag in enumerate(sorted_agents[-3:],
                               len(sorted_agents) - 2):
        delta_7d = _compute_7d_delta(ag)
        lines.append(
            f"  #{rank} {ag['name']} ({ag['archetype']}): "
            f"${ag['bankroll']:,.0f}  7dΔ={delta_7d:+,.0f}"
        )
    return "\n".join(lines)

def _compute_7d_delta(agent):
    hist = agent.get("history", [])
    cutoff = max(0, len(hist) - 7)
    return sum(h.get("pnl", 0) for h in hist[cutoff:])

def build_history_block(all_bets, day_idx, window=3):
    if not all_bets:
        return "=== RECENT ALLOCATIONS (last 3 days) ===\n  (none yet)"
    cutoff_day = max(0, day_idx - window)
    recent = [b for b in all_bets if b.get("day_idx", 0) >= cutoff_day]
    if not recent:
        return "=== RECENT ALLOCATIONS (last 3 days) ===\n  (none yet)"
    lines = [f"=== RECENT ALLOCATIONS (last {window} days) ==="]
    for b in recent[-30:]:
        lines.append(
            f"  Day{b['day_idx']+1} {b['agent_name']} → "
            f"{b['pick']} {b.get('direction','LONG')} "
            f"(${b.get('stake',0):.0f}, result={b.get('result','pending')})"
        )
    return "\n".join(lines)

def build_consensus_block(day_picks):
    if not day_picks:
        return ""
    from collections import Counter
    counts = Counter(f"{p['pick']}-{p.get('direction','LONG')}" for p in day_picks)
    lines = ["=== CONSENSUS PICKS (today so far) ==="]
    for pick, cnt in counts.most_common():
        lines.append(f"  {pick}: {cnt} agent(s)")
    return "\n".join(lines)

def build_peer_stances_block(day_picks, current_agent_id):
    peers = [p for p in day_picks if p["agent_id"] != current_agent_id]
    if not peers:
        return ""
    lines = ["=== PEER CK STANCES (today) ==="]
    for p in peers:
        lines.append(
            f"  {p['agent_name']} ({p['archetype']}): "
            f"{p['pick']} {p.get('direction','LONG')}"
        )
    return "\n".join(lines)

def build_archetype_perf_block(agents):
    from collections import defaultdict
    arch_bankrolls = defaultdict(list)
    for ag in agents:
        arch_bankrolls[ag["archetype"]].append(ag["bankroll"])
    lines = ["=== ARCHETYPE PERFORMANCE (avg bankroll) ==="]
    for arch, bks in sorted(arch_bankrolls.items(),
                             key=lambda x: -sum(x[1])/len(x[1])):
        avg = sum(bks) / len(bks)
        lines.append(f"  {arch}: ${avg:,.0f} (n={len(bks)})")
    return "\n".join(lines)

def build_tomorrow_tiers_block(agents, day_idx):
    assignments = _gs("_challenge_assignments") or {}
    if not assignments:
        return ""
    lines = ["=== TOMORROW CHALLENGE TIERS ==="]
    for agent_id, info in assignments.items():
        ag_name = next((a["name"] for a in agents if a["id"] == agent_id), f"Agent-{agent_id}")
        lines.append(
            f"  {ag_name}: tier={info.get('tier','?')} "
            f"challenger={info.get('challenger','?')} "
            f"challenged={info.get('challenged','?')}"
        )
    return "\n".join(lines)

def build_dmad_mandate_block(agent):
    archetype = agent.get("archetype", "macro_hawk")
    mandates = {
        "macro_hawk":           "Focus: macro indicators — CPI, PPI, GDP, unemployment vs. market pricing",
        "policy_contrarian":    "Focus: consensus policy narrative vs. actual legislative probability",
        "sector_rotator":       "Focus: cross-sector ETF relative strength and policy-driven rotation signals",
        "insider_tracker":      "Focus: congressional Form 4 + STOCK Act disclosures and pattern clustering",
        "fed_watcher":          "Focus: FOMC dot-plot, PCE data, Fed speak — rate path vs. curve pricing",
        "geopolitical_analyst": "Focus: geopolitical event risk premium — tariffs, sanctions, conflict zones",
        "esg_screener":         "Focus: ESG policy impact — IRA, clean energy credits, fossil fuel regulations",
        "momentum_trader":      "Focus: political momentum — bill passage probability, polling trend, media volume",
        "value_allocator":      "Focus: post-shock mean-reversion in sectors with policy-driven dislocations",
        "risk_arbitrageur":     "Focus: event-driven risk arb — announced deals, regulatory approvals, court rulings",
    }
    mandate = mandates.get(archetype, "Focus: general political risk analysis")
    return f"=== YOUR DMAD MANDATE ===\n  {mandate}"

def build_common_knowledge_block(agents, all_bets, day_idx, day_picks):
    """Axelrod Mech A — day-end common knowledge broadcast."""
    parts = [
        build_leaderboard_block(agents, day_idx),
        build_history_block(all_bets, day_idx, window=3),
        build_consensus_block(day_picks),
        build_archetype_perf_block(agents),
        build_tomorrow_tiers_block(agents, day_idx),
        build_dmad_mandate_block({"archetype": "macro_hawk"}),
    ]
    return "\n\n".join(p for p in parts if p)

# ── AXELROD MECH B — SACRIFICIAL SYSTEM ──────────────────────────────────────
def assign_sacrificial_archetypes(agents, day_idx):
    used_archetypes = _gs("_used_archetypes") or {}
    sorted_agents = sorted(agents, key=lambda a: a["bankroll"])
    bottom_3 = sorted_agents[:3]

    assignments = {}
    for ag in bottom_3:
        agent_id = ag["id"]
        recent_used = used_archetypes.get(str(agent_id), [])[-7:]
        available = [a for a in ARCHETYPES if a not in recent_used]
        if not available:
            available = ARCHETYPES

        new_arch = available[0]
        ag["archetype"] = new_arch
        assignments[agent_id] = {
            "tier":       "sacrifice",
            "challenger": None,
            "challenged": None,
            "new_arch":   new_arch,
        }

        used_archetypes.setdefault(str(agent_id), []).append(new_arch)
        used_archetypes[str(agent_id)] = used_archetypes[str(agent_id)][-7:]

    _ss("_used_archetypes",      used_archetypes)
    _ss("_challenge_assignments", assignments)
    return agents

def assign_challenge_tiers(agents):
    sorted_agents = sorted(agents, key=lambda a: a["bankroll"], reverse=True)
    top_3    = sorted_agents[:3]
    bottom_3 = sorted_agents[-3:]

    assignments = _gs("_challenge_assignments") or {}
    for challenger, challenged in zip(top_3, bottom_3):
        assignments[challenger["id"]] = {
            "tier":       "challenger",
            "challenger": challenger["id"],
            "challenged": challenged["id"],
        }
        if challenged["id"] not in assignments:
            assignments[challenged["id"]] = {
                "tier":       "sacrifice",
                "challenger": challenger["id"],
                "challenged": None,
                "new_arch":   challenged.get("archetype"),
            }
        else:
            assignments[challenged["id"]]["challenger"] = challenger["id"]

    _ss("_challenge_assignments", assignments)
    return agents

def build_challenge_block(agent, agents):
    assignments = _gs("_challenge_assignments") or {}
    agent_id = agent["id"]

    if agent_id not in assignments:
        return ""

    info = assignments[agent_id]
    tier = info.get("tier", "")

    lines = ["=== AXELROD CHALLENGE SYSTEM ==="]
    if tier == "challenger":
        challenged_id = info.get("challenged")
        challenged_ag = next((a for a in agents if a["id"] == challenged_id), None)
        if challenged_ag:
            lines.append(
                f"  You are a CHALLENGER. Your target: "
                f"{challenged_ag['name']} (${challenged_ag['bankroll']:,.0f}). "
                f"Outperform them today."
            )
    elif tier == "sacrifice":
        new_arch = info.get("new_arch", agent.get("archetype"))
        challenger_id = info.get("challenger")
        challenger_ag = next((a for a in agents if a["id"] == challenger_id), None)
        lines.append(
            f"  You are in SACRIFICE position (bottom-3). "
            f"New archetype assigned: {new_arch}. "
            f"{'Challenger: ' + challenger_ag['name'] if challenger_ag else ''}"
        )
    return "\n".join(lines)

def build_sacrificial_system_suffix(agent, agents):
    challenge_block = build_challenge_block(agent, agents)
    if not challenge_block:
        return ""
    return f"\n\n{challenge_block}"

# ── AXELROD MECH C — POST-MORTEM LOG ─────────────────────────────────────────
def compute_peer_consensus_distance(agent, agents, day_picks):
    """
    D_KL(agent || peers):
    KL divergence of this agent's pick distribution vs. the society baseline
    (all OTHER agents — self excluded).

    Pick distribution: fraction of picks for each unique option.
    Returns a float ≥ 0.  Returns 0.0 if no peer picks or no agent picks.
    """
    import math

    agent_id = agent["id"]

    # Agent's picks today
    agent_picks = [p["pick"] for p in day_picks if p["agent_id"] == agent_id]
    # Society baseline: all OTHER agents' picks (self excluded)
    peer_picks  = [p["pick"] for p in day_picks if p["agent_id"] != agent_id]

    if not agent_picks or not peer_picks:
        return 0.0

    all_options = list(set(agent_picks + peer_picks))

    def dist(picks):
        total = len(picks)
        return {o: picks.count(o) / total for o in all_options}

    q = dist(agent_picks)   # agent distribution
    p = dist(peer_picks)    # peer (society) distribution — self excluded

    eps = 1e-9
    kl = sum(q.get(o, eps) * math.log((q.get(o, eps)) / (p.get(o, eps)))
             for o in all_options)
    return max(0.0, kl)

def write_axelrod_log(agent, agents, day_idx, date_str, day_picks, all_bets):
    """
    Mech C: write one row per agent per day to the Axelrod log dataset.
    Pushes to HF Hub: Nomos42/arena-axelrod-log
    Schema: 25 top-level fields.
    """
    if not HF_DATASET_TOKEN:
        print("[axelrod-log] HF_DATASET_TOKEN missing — skipping push")
        return

    agent_bets_today = [
        b for b in all_bets
        if b.get("agent_id") == agent["id"] and b.get("day_idx") == day_idx
    ]
    wins_today = sum(1 for b in agent_bets_today if b.get("result") == "win")
    decisions_summary = "; ".join(
        f"{b['pick']}-{b.get('direction','LONG')}→{b.get('result','pending')}"
        for b in agent_bets_today
    )

    # Peer consensus picks distribution (excluding self)
    peer_picks_today = [p["pick"] for p in day_picks if p["agent_id"] != agent["id"]]
    from collections import Counter
    consensus_dist = dict(Counter(peer_picks_today))

    # peer_consensus_distance: D_KL(agent || peers), self excluded
    pcd = compute_peer_consensus_distance(agent, agents, day_picks)

    # 7-day trailing PnL
    hist = agent.get("history", [])
    trailing_7d = sum(h.get("pnl", 0) for h in hist[-7:])

    # used_archetypes_7d
    used_archetypes = _gs("_used_archetypes") or {}
    used_7d = used_archetypes.get(str(agent["id"]), [])[-7:]

    # Cash held
    total_bankroll = agent["bankroll"]
    staked_today   = sum(b.get("stake", 0) for b in agent_bets_today)
    cash_held_pct  = max(0.0, (total_bankroll - staked_today) / total_bankroll) if total_bankroll else 0.0

    # Common knowledge fields
    ck_block = _gs("_common_knowledge") or ""

    # Coalition / council fields
    assignments = _gs("_challenge_assignments") or {}
    agent_assign = assignments.get(agent["id"], {})

    record = {
        "day_idx":                  day_idx,
        "date":                     date_str,
        "trader_id":                agent["id"],
        "rank":                     sorted([a["bankroll"] for a in agents], reverse=True).index(agent["bankroll"]) + 1,
        "bankroll":                 agent["bankroll"],
        "archetype_assigned":       agent.get("archetype", ""),
        "was_sacrificed":           agent_assign.get("tier") == "sacrifice",
        "was_challenged":           agent_assign.get("challenger") is not None,
        "tier":                     agent_assign.get("tier", "standard"),
        "num_decisions":            len(agent_bets_today),
        "wins_today":               wins_today,
        "decisions_summary":        decisions_summary,
        "peer_consensus_distance":  round(pcd, 6),
        "day_strategy_prefix":      agent.get("day_strategy_prefix", ""),
        "ck_consensus_stance":      agent.get("ck_consensus_stance", ""),
        "coalition_proposal":       agent.get("coalition_proposal", ""),
        "council_alignment":        agent.get("council_alignment", ""),
        "bankroll_growth_factor":   round(agent["bankroll"] / 100_000.0, 6),
        "consensus_pick_distribution": consensus_dist,
        "fleet":                    agent.get("model", ""),
        "provider":                 agent.get("provider", ""),
        "trailing_7d_delta":        round(trailing_7d, 2),
        "dmad_prefix_type":         agent.get("archetype", ""),
        "cash_held_pct":            round(cash_held_pct, 4),
        "used_archetypes_7d":       used_7d,
    }

    # Push to HF Hub
    try:
        from huggingface_hub import HfApi
        api = HfApi()
        log_path = f"logs/pol/day_{day_idx:04d}_agent_{agent['id']:02d}.json"
        api.upload_file(
            path_or_fileobj=json.dumps(record, indent=2).encode(),
            path_in_repo=log_path,
            repo_id=HF_AXELROD_REPO,
            repo_type="dataset",
            token=HF_DATASET_TOKEN,
            commit_message=f"pol axelrod log day={day_idx} agent={agent['id']}",
        )
        print(f"[axelrod-log] Pushed {log_path}")
    except Exception as e:
        print(f"[axelrod-log] push error: {e}")

# ── ORACLE BLOCK ──────────────────────────────────────────────────────────────
def get_oracle_block(events_today):
    """Call island oracle for today's political events."""
    if not _POL_ORACLE_OK:
        return ""
    try:
        pred = _island_pol_predict(events_today)
        if pred:
            return f"ORACLE MODEL: {json.dumps(pred, indent=2)}"
        return ""
    except Exception as e:
        print(f"[pol-oracle] block error: {e}")
        return ""

# ── PROMPT BUILDER ────────────────────────────────────────────────────────────
def build_agent_prompt(agent, events_today, day_idx, agents,
                       all_bets, day_picks, common_knowledge):
    """Build the full system + user prompt for one political agent."""
    events_text = []
    for ev in events_today:
        events_text.append(
            f"[{ev['type'].upper()}] {ev['title']}\n"
            f"  Summary: {ev['summary']}\n"
            f"  Affected sectors: {', '.join(ev.get('affected', []))}\n"
            f"  Signal: {ev.get('signal', 'neutral')}"
        )

    oracle_block = get_oracle_block(events_today)

    # Common knowledge (Mech A broadcast)
    ck_block = common_knowledge or _gs("_common_knowledge") or ""

    # Peer stances (Mech A — real-time)
    peer_stances = build_peer_stances_block(day_picks, agent["id"])

    # Mech B suffix
    mech_b_suffix = build_sacrificial_system_suffix(agent, agents)

    system_prompt = (
        f"You are {agent['name']}, a political trading floor analyst.\n"
        f"Archetype: {agent['archetype']} — {ARCHETYPE_DESCRIPTIONS.get(agent['archetype'], '')}\n"
        f"Provider: {agent['provider']} | Model: {agent['model']}\n"
        f"Current portfolio value: ${agent['bankroll']:,.2f}\n"
        f"Track record: {agent['bets_won']}W / {agent['bets_lost']}L / {agent['bets_push']}P\n\n"
        f"You MUST allocate capital to exactly ONE sector ETF today based on the political signals.\n"
        f"Output:\n"
        f"PICK: <ETF ticker, e.g. XLE>\n"
        f"DIRECTION: LONG or SHORT\n"
        f"STAKE: <amount in dollars, 1000-20000>\n"
        f"REASONING: <2-3 sentences>\n\n"
        f"Valid ETFs: {', '.join(SECTOR_ETFS.keys())}\n"
        f"Be concise. Output the four lines above and nothing else."
    )

    user_parts = [
        f"Day {day_idx + 1} — Political signals:\n",
        "\n\n".join(events_text),
    ]
    if oracle_block:
        user_parts.append(f"\n{oracle_block}")
    if ck_block:
        user_parts.append(f"\n{ck_block}")
    if peer_stances:
        user_parts.append(f"\n{peer_stances}")
    user_parts.append(mech_b_suffix)

    return system_prompt, "\n".join(user_parts)

# ── LLM CALL ──────────────────────────────────────────────────────────────────
def call_agent(agent, events_today, day_idx, agents,
               all_bets, day_picks, common_knowledge):
    system_prompt, user_prompt = build_agent_prompt(
        agent, events_today, day_idx, agents,
        all_bets, day_picks, common_knowledge,
    )
    try:
        response = gateway_call(
            provider=agent["provider"],
            model=agent["model"],
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt,
            temperature=0.7,
            max_tokens=400,
        )
        return parse_agent_response(agent, response, day_idx)
    except Exception as e:
        print(f"[{agent['name']}] LLM error: {e}")
        return {
            "agent_id":   agent["id"],
            "agent_name": agent["name"],
            "archetype":  agent["archetype"],
            "pick":       "XLF",
            "direction":  "LONG",
            "stake":      0,
            "reasoning":  f"Error: {e}",
            "day_idx":    day_idx,
        }

def parse_agent_response(agent, response, day_idx):
    pick      = "XLF"
    direction = "LONG"
    stake     = 5000
    reasoning = ""

    for line in response.splitlines():
        line = line.strip()
        if line.upper().startswith("PICK:"):
            raw_pick = line.split(":", 1)[1].strip().upper()
            if raw_pick in SECTOR_ETFS:
                pick = raw_pick
        elif line.upper().startswith("DIRECTION:"):
            raw_dir = line.split(":", 1)[1].strip().upper()
            if raw_dir in ("LONG", "SHORT"):
                direction = raw_dir
        elif line.upper().startswith("STAKE:"):
            raw = line.split(":", 1)[1].strip().replace("$", "").replace(",", "")
            try:
                stake = max(1000, min(20000, int(float(raw))))
            except ValueError:
                stake = 5000
        elif line.upper().startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()

    return {
        "agent_id":   agent["id"],
        "agent_name": agent["name"],
        "archetype":  agent["archetype"],
        "pick":       pick,
        "direction":  direction,
        "stake":      stake,
        "reasoning":  reasoning,
        "day_idx":    day_idx,
    }

# ── BET RESOLUTION ────────────────────────────────────────────────────────────
def resolve_political_bet(bet, events_today):
    """
    Resolve a political allocation based on event signals.
    'win' if agent's direction aligns with event signal; 'loss' otherwise.
    """
    pick      = bet.get("pick", "XLF")
    direction = bet.get("direction", "LONG")

    for ev in events_today:
        if pick in ev.get("affected", []):
            signal = ev.get("signal", "neutral")
            bullish_signals = {
                "bullish_energy", "bullish_financials", "bullish_healthcare",
                "bullish_tech_infra", "bullish_infrastructure",
                "insider_bullish_energy", "insider_bullish_healthcare",
                "risk_on_energy_geopolitical",
            }
            bearish_signals = {
                "hawkish_rates", "hawkish_rates_extended",
                "tariff_risk", "bearish_tech", "bearish_agri_trade",
                "risk_off_geopolitical",
            }
            if signal in bullish_signals:
                return "win" if direction == "LONG" else "loss"
            elif signal in bearish_signals:
                return "win" if direction == "SHORT" else "loss"
    return "push"   # no matching signal → push

def apply_bet_result(agent, bet, result):
    stake = bet.get("stake", 0)
    if result == "win":
        pnl = stake * 0.15    # 15% gain on political allocation
        agent["bankroll"]  += pnl
        agent["bets_won"]  += 1
        agent["pnl"]       += pnl
    elif result == "loss":
        pnl = -stake * 0.10   # 10% loss (stop-loss)
        agent["bankroll"]  += pnl
        agent["bets_lost"] += 1
        agent["pnl"]       += pnl
    else:
        pnl = 0
        agent["bets_push"] += 1
    agent["total_bets"] += 1
    agent["history"].append({
        "day_idx":   bet["day_idx"],
        "pick":      bet["pick"],
        "direction": bet.get("direction", "LONG"),
        "stake":     stake,
        "result":    result,
        "pnl":       pnl,
    })
    return pnl

# ── DAY RUNNER ────────────────────────────────────────────────────────────────
def run_day(day_idx, events_today, agents, all_bets):
    """Run one full political trading day: pick → resolve → update."""
    date_str  = events_today[0].get("date", f"Day-{day_idx+1}") if events_today else f"Day-{day_idx+1}"
    day_picks = []

    # Flatten events
    all_events = []
    if isinstance(events_today, dict):
        all_events = events_today.get("events", [])
    elif isinstance(events_today, list):
        # Could be a list of day-dicts or a list of events
        if events_today and isinstance(events_today[0], dict) and "events" in events_today[0]:
            all_events = events_today[0].get("events", [])
        else:
            all_events = events_today

    # Mech B: assign sacrificial archetypes for bottom-3
    agents = assign_sacrificial_archetypes(agents, day_idx)
    agents = assign_challenge_tiers(agents)

    # Get common knowledge from previous day (Mech A)
    common_knowledge = _gs("_common_knowledge") or ""

    # Sequential agent calls
    for agent in agents:
        if _gs("stop_flag"):
            break
        bet = call_agent(
            agent, all_events, day_idx, agents,
            all_bets, day_picks, common_knowledge,
        )
        day_picks.append(bet)
        time.sleep(CALL_DELAY)

    # Resolve all bets
    for bet in day_picks:
        result = resolve_political_bet(bet, all_events)
        bet["result"] = result
        agent = next((a for a in agents if a["id"] == bet["agent_id"]), None)
        if agent:
            pnl = apply_bet_result(agent, bet, result)
            bet["pnl"] = pnl
        all_bets.append(bet)

    # Mech A: broadcast common knowledge for next day
    new_ck = build_common_knowledge_block(agents, all_bets, day_idx, day_picks)
    _ss("_common_knowledge", new_ck)

    # Mech C: write Axelrod log for each agent
    for agent in agents:
        try:
            write_axelrod_log(agent, agents, day_idx, date_str, day_picks, all_bets)
        except Exception as e:
            print(f"[axelrod-log] agent {agent['id']} error: {e}")

    return day_picks, agents, all_bets

# ── MAIN SIMULATION LOOP ──────────────────────────────────────────────────────
def simulation_loop():
    resumed = load_state()
    if not resumed or not _gs("agents"):
        event_days = load_political_events()
        agents = initialise_agents()
        _ss("agents",      agents)
        _ss("total_days",  len(event_days))
        _ss("day_idx",     0)
        _ss("all_bets",    [])
        _ss("day_results", [])
        _ss("run_id",      f"pol_run_{int(time.time())}")
        _ss("running",     True)
        _ss("stop_flag",   False)
    else:
        event_days = load_political_events()
        _ss("running",   True)
        _ss("stop_flag", False)

    agents   = _gs("agents")
    all_bets = _gs("all_bets") or []
    start    = _gs("day_idx") or 0

    for day_idx in range(start, len(event_days)):
        if _gs("stop_flag"):
            print("[sim] Stop flag set — exiting")
            break

        _ss("day_idx", day_idx)
        day_data    = event_days[day_idx]
        date_str    = day_data.get("date", f"Day-{day_idx+1}")
        events_list = day_data.get("events", [])

        print(f"\n[sim] === Day {day_idx+1}/{len(event_days)} — "
              f"{date_str} — {len(events_list)} events ===")

        day_picks, agents, all_bets = run_day(
            day_idx, events_list, agents, all_bets
        )

        _ss("agents",   agents)
        _ss("all_bets", all_bets)
        save_state()

        day_summary = {
            "day_idx":  day_idx,
            "date":     date_str,
            "n_events": len(events_list),
            "n_bets":   len(day_picks),
            "picks":    day_picks,
        }
        with _state_lock:
            _state["day_results"].append(day_summary)

    _ss("running", False)
    _ss("status",  "complete")
    print("[sim] Simulation complete")

# ── PUSH RESULTS TO HF HUB ───────────────────────────────────────────────────
def push_results_to_hub():
    if not HF_DATASET_TOKEN:
        return "No HF_DATASET_TOKEN — skipping push"
    try:
        from huggingface_hub import HfApi
        api  = HfApi()
        data = {
            "run_id":       _gs("run_id"),
            "agents":       _gs("agents"),
            "all_bets":     _gs("all_bets"),
            "day_results":  _gs("day_results"),
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        buf = io.BytesIO(json.dumps(data, indent=2).encode())
        api.upload_file(
            path_or_fileobj=buf,
            path_in_repo=f"results/{_gs('run_id')}.json",
            repo_id=HF_DATASET_REPO,
            repo_type="dataset",
            token=HF_DATASET_TOKEN,
            commit_message=f"Political TF results: {_gs('run_id')}",
        )
        return f"Pushed to {HF_DATASET_REPO}"
    except Exception as e:
        return f"Push error: {e}"

# ── FASTAPI ENDPOINTS ─────────────────────────────────────────────────────────
app = FastAPI()

@app.get("/api/status")
async def api_status():
    with _state_lock:
        agents = _state.get("agents", [])
        return {
            "status":      _state.get("status", "idle"),
            "day_idx":     _state.get("day_idx", 0),
            "total_days":  _state.get("total_days", 0),
            "running":     _state.get("running", False),
            "n_agents":    len(agents),
            "leaderboard": sorted(
                [{"name": a["name"], "bankroll": a["bankroll"],
                  "pnl": a["pnl"], "archetype": a["archetype"]}
                 for a in agents],
                key=lambda x: -x["bankroll"]
            ),
        }

@app.post("/api/start")
async def api_start(request: Request):
    if _gs("running"):
        return JSONResponse({"error": "Already running"}, status_code=400)
    _ss("status", "running")
    thread = threading.Thread(target=simulation_loop, daemon=True)
    thread.start()
    return {"started": True}

@app.post("/api/stop")
async def api_stop():
    _ss("stop_flag", True)
    return {"stopping": True}

@app.get("/api/results")
async def api_results():
    return {
        "run_id":      _gs("run_id"),
        "day_results": _gs("day_results"),
        "all_bets":    _gs("all_bets"),
    }

@app.post("/api/push")
async def api_push():
    msg = push_results_to_hub()
    return {"message": msg}

# ── GRADIO UI ─────────────────────────────────────────────────────────────────
def make_gradio_ui():
    with gr.Blocks(title="Political LLM Trading Floor") as demo:
        gr.Markdown("# Political LLM Trading Floor\n10 AI agents allocate capital on political sector ETFs.")

        with gr.Row():
            start_btn  = gr.Button("Start Simulation", variant="primary")
            stop_btn   = gr.Button("Stop")
            status_txt = gr.Textbox(label="Status", interactive=False)

        leaderboard = gr.Dataframe(
            headers=["Agent", "Portfolio", "PnL", "W", "L", "Archetype"],
            label="Live Leaderboard",
        )
        log_box = gr.Textbox(label="Activity Log", lines=20, interactive=False)

        def get_status():
            s      = _gs("status") or "idle"
            day    = _gs("day_idx") or 0
            total  = _gs("total_days") or 0
            agents = _gs("agents") or []
            status = f"{s.upper()} | Day {day}/{total}"
            rows   = [
                [a["name"], f"${a['bankroll']:,.0f}", f"${a['pnl']:+,.0f}",
                 a["bets_won"], a["bets_lost"], a["archetype"]]
                for a in sorted(agents, key=lambda x: -x["bankroll"])
            ]
            log_lines = _gs("log") or []
            return status, rows, "\n".join(log_lines[-50:])

        def start_sim():
            if _gs("running"):
                return "Already running"
            _ss("status", "running")
            t = threading.Thread(target=simulation_loop, daemon=True)
            t.start()
            return "Started"

        def stop_sim():
            _ss("stop_flag", True)
            return "Stopping..."

        start_btn.click(start_sim, outputs=status_txt)
        stop_btn.click(stop_sim,  outputs=status_txt)

        demo.load(get_status, outputs=[status_txt, leaderboard, log_box], every=10)

    return demo

# ── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    gradio_app = make_gradio_ui()
    gradio_app.launch(server_name="0.0.0.0", server_port=7860, share=False)
