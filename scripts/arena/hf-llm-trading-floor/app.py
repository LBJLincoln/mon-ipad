"""Nomos42 Real LLM Trading Floor — HuggingFace Spaces
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

# Island oracle — bridges TF agents to the island-trained calibrated model (S18).
# Failure-open: if island is down, oracle returns {} and the prompt skips the block.
try:
    from island_oracle import (
        nba_oracle_predict as _island_nba_predict,
        nba_oracle_predict_many as _island_nba_predict_many,
        oracle_block_for_prompt as _island_oracle_block,
    )
    _ORACLE_OK = True
except Exception as _orc_err:
    print(f"[oracle] import failed: {_orc_err}")
    _ORACLE_OK = False
    def _island_nba_predict(*a, **kw): return {}
    def _island_nba_predict_many(games): return [{} for _ in (games or [])]
    def _island_oracle_block(nba_pred=None, pol_pred=None): return ""

# ── STARTUP DIAGNOSTICS ─────────────────────────────────────────────────────
print("=" * 60)
print("NOMOS42 REAL LLM TRADING FLOOR — STARTUP")
print("=" * 60)
for k in ["CEREBRAS_API_KEY", "GOOGLE_API_KEY", "GOOGLE_API_KEY_2",
          "OPENROUTER_KEY_ORCHESTRATOR", "OPENROUTER_KEY_PME", "OPENROUTER_KEY_BARTOLI",
          "COHERE_API_KEY", "HF_TOKEN", "HF_DATASET_TOKEN",
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
SEASON_YEAR   = 2026
MAX_WORKERS   = 3
CEREBRAS_RPM  = 30
CALL_DELAY    = 60 / CEREBRAS_RPM

# HF Hub dataset push
HF_DATASET_REPO  = "Nomos42/nba-trading-floor-results"
HF_AXELROD_REPO  = "Nomos42/arena-axelrod-log"
HF_DATASET_TOKEN = os.environ.get("HF_DATASET_TOKEN", "")

# ── ARCHETYPES ────────────────────────────────────────────────────────────────
ARCHETYPES = [
    "momentum_surfer", "contrarian", "value_hunter",
    "form_follower", "underdog_backer", "injury_tracker",
    "home_field_hawk", "sharp_money", "weather_watcher", "stats_quant",
]

ARCHETYPE_DESCRIPTIONS = {
    "momentum_surfer":  "Chases recent winning streaks and hot teams",
    "contrarian":       "Fades public consensus and bets against popular picks",
    "value_hunter":     "Seeks mispriced odds relative to true probability",
    "form_follower":    "Analyses last 5-10 game performance trends",
    "underdog_backer":  "Systematically backs underdogs for value",
    "injury_tracker":   "Focuses on key player injuries and lineup changes",
    "home_field_hawk":  "Overweights home-court advantage signals",
    "sharp_money":      "Follows sharp bettor line movements",
    "weather_watcher":  "Considers environmental and travel factors",
    "stats_quant":      "Deep statistical models, pace, efficiency ratings",
}

PROVIDER_MODELS = [
    ("cerebras",    "llama-3.3-70b"),
    ("cerebras",    "llama-4-scout-17b-16e-instruct"),
    ("cerebras",    "qwen-3-32b"),
    ("cerebras",    "deepseek-r1-distill-llama-70b"),
    ("cerebras",    "llama3.1-8b"),
    ("google",      "gemini-2.0-flash"),
    ("openrouter",  "mistralai/mistral-small-3.2-24b-instruct:free"),
    ("openrouter",  "microsoft/mai-ds-r1:free"),
    ("cohere",      "command-r-plus"),
    ("huggingface", "Qwen/Qwen2.5-72B-Instruct"),
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
STATE_FILE = "/tmp/trading_floor_state.json"

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

# ── NBA DATA ──────────────────────────────────────────────────────────────────
def load_nba_games():
    """Load NBA games from CSV bundled with the Space."""
    csv_path = os.path.join(os.path.dirname(__file__), "nba_games_2025_26.csv")
    games = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                games.append(row)
        print(f"[data] Loaded {len(games)} NBA games from CSV")
    except FileNotFoundError:
        print(f"[data] CSV not found at {csv_path}, using synthetic data")
        games = _synthetic_games()
    except Exception as e:
        print(f"[data] CSV load error: {e} — using synthetic")
        games = _synthetic_games()
    return games

def _synthetic_games():
    """Fallback synthetic NBA schedule."""
    teams = [
        ("Lakers", "Celtics"), ("Warriors", "Bucks"), ("Nets", "Heat"),
        ("76ers", "Suns"),     ("Clippers", "Nuggets"), ("Mavericks", "Grizzlies"),
        ("Raptors", "Jazz"),   ("Knicks", "Trail Blazers"),
    ]
    games = []
    for i, (home, away) in enumerate(teams * 5):
        games.append({
            "game_id":    f"game_{i:03d}",
            "date":       f"2026-0{(i//10)+1}-{(i%10)+1:02d}",
            "home_team":  home,
            "away_team":  away,
            "home_score": "",
            "away_score": "",
            "home_odds":  str(round(-110 + (i % 5) * 5, 0)),
            "away_odds":  str(round(+100 + (i % 5) * 5, 0)),
        })
    return games

# ── GAME GROUPING ─────────────────────────────────────────────────────────────
def group_games_by_day(games):
    from collections import defaultdict
    day_map = defaultdict(list)
    for g in games:
        day_map[g.get("date", "unknown")].append(g)
    return [day_map[d] for d in sorted(day_map)]

# ── STANDINGS TRACKER ─────────────────────────────────────────────────────────
class StandingsTracker:
    def __init__(self):
        self.wins   = {}
        self.losses = {}
        self.streak = {}   # positive = win streak, negative = loss streak

    def update(self, game):
        home, away = game["home_team"], game["away_team"]
        try:
            hs, as_ = int(game["home_score"]), int(game["away_score"])
        except (ValueError, KeyError):
            return
        winner, loser = (home, away) if hs > as_ else (away, home)
        for t in [home, away]:
            self.wins.setdefault(t, 0)
            self.losses.setdefault(t, 0)
            self.streak.setdefault(t, 0)
        self.wins[winner]   += 1
        self.losses[loser]  += 1
        prev_w = self.streak.get(winner, 0)
        self.streak[winner] = prev_w + 1 if prev_w >= 0 else 1
        prev_l = self.streak.get(loser, 0)
        self.streak[loser]  = prev_l - 1 if prev_l <= 0 else -1

    def summary(self, team):
        w = self.wins.get(team, 0)
        l = self.losses.get(team, 0)
        s = self.streak.get(team, 0)
        streak_str = f"W{s}" if s > 0 else (f"L{abs(s)}" if s < 0 else "—")
        return f"{w}W-{l}L ({streak_str})"

    def top_teams(self, n=5):
        all_teams = set(list(self.wins) + list(self.losses))
        ranked = sorted(all_teams,
                        key=lambda t: self.wins.get(t, 0) /
                        max(1, self.wins.get(t,0)+self.losses.get(t,0)),
                        reverse=True)
        return ranked[:n]

_standings = StandingsTracker()

# ── RECENT FORM ───────────────────────────────────────────────────────────────
_recent_results: dict[str, list[str]] = {}   # team → ['W','L','W',...]

def update_recent_form(game):
    home, away = game["home_team"], game["away_team"]
    try:
        hs, as_ = int(game["home_score"]), int(game["away_score"])
    except (ValueError, KeyError):
        return
    winner, loser = (home, away) if hs > as_ else (away, home)
    for team, result in [(winner, "W"), (loser, "L")]:
        _recent_results.setdefault(team, []).append(result)
        _recent_results[team] = _recent_results[team][-10:]

def get_form_string(team, n=5):
    results = _recent_results.get(team, [])[-n:]
    return "".join(results) if results else "No data"

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
            "bankroll":    10_000.0,
            "bets_won":    0,
            "bets_lost":   0,
            "bets_push":   0,
            "total_bets":  0,
            "pnl":         0.0,
            "history":     [],   # list of {game_id, bet, stake, result, pnl}
            "day_picks":   [],   # picks for current day
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
    """Sum PnL from last 7 days of history."""
    hist = agent.get("history", [])
    cutoff = max(0, len(hist) - 7)
    return sum(h.get("pnl", 0) for h in hist[cutoff:])

def build_history_block(all_bets, day_idx, window=3):
    """3-day rolling all-bets history."""
    if not all_bets:
        return "=== RECENT BETS (last 3 days) ===\n  (none yet)"
    cutoff_day = max(0, day_idx - window)
    recent = [b for b in all_bets if b.get("day_idx", 0) >= cutoff_day]
    if not recent:
        return "=== RECENT BETS (last 3 days) ===\n  (none yet)"
    lines = [f"=== RECENT BETS (last {window} days) ==="]
    for b in recent[-30:]:   # cap display at 30
        lines.append(
            f"  Day{b['day_idx']+1} {b['agent_name']} → "
            f"{b['pick']} (stake ${b['stake']:.0f}, result={b.get('result','pending')})"
        )
    return "\n".join(lines)

def build_consensus_block(day_picks):
    """CONSENSUS PICKS: how many agents picked each side."""
    if not day_picks:
        return ""
    from collections import Counter
    counts = Counter(p["pick"] for p in day_picks)
    lines = ["=== CONSENSUS PICKS (today so far) ==="]
    for pick, cnt in counts.most_common():
        lines.append(f"  {pick}: {cnt} agent(s)")
    return "\n".join(lines)

def build_peer_stances_block(day_picks, current_agent_id):
    """PEER CK STANCES: show each other agent's pick for today's game."""
    peers = [p for p in day_picks if p["agent_id"] != current_agent_id]
    if not peers:
        return ""
    lines = ["=== PEER CK STANCES (today) ==="]
    for p in peers:
        lines.append(f"  {p['agent_name']} ({p['archetype']}): {p['pick']}")
    return "\n".join(lines)

def build_archetype_perf_block(agents):
    """ARCHETYPE PERFORMANCE: avg bankroll per archetype."""
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
    """TOMORROW TIERS: show challenge/sacrifice assignments for next day."""
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
    """DMAD mandate: agent's unique structural data view."""
    archetype = agent.get("archetype", "stats_quant")
    mandates = {
        "momentum_surfer":  "Focus: team momentum, last-5 win streak, point differential trend",
        "contrarian":       "Focus: public betting percentages, reverse-line movement",
        "value_hunter":     "Focus: implied probability vs. true probability gaps",
        "form_follower":    "Focus: last-10 game efficiency ratings, home/away splits",
        "underdog_backer":  "Focus: underdog historical ATS record, upset conditions",
        "injury_tracker":   "Focus: injury reports, minutes restrictions, back-to-back fatigue",
        "home_field_hawk":  "Focus: home-court edge, travel schedule, altitude factors",
        "sharp_money":      "Focus: line movement, steam moves, CLV (closing line value)",
        "weather_watcher":  "Focus: schedule density, back-to-backs, altitude, travel miles",
        "stats_quant":      "Focus: pace-adjusted efficiency, true shooting %, net rating",
    }
    mandate = mandates.get(archetype, "Focus: general statistical analysis")
    return f"=== YOUR DMAD MANDATE ===\n  {mandate}"

def build_common_knowledge_block(agents, all_bets, day_idx, day_picks):
    """
    Axelrod Mech A — day-end common knowledge broadcast.
    Assembled once per day after all agents pick; stored in _state['_common_knowledge'].
    """
    parts = [
        build_leaderboard_block(agents, day_idx),
        build_history_block(all_bets, day_idx, window=3),
        build_consensus_block(day_picks),
        build_archetype_perf_block(agents),
        build_tomorrow_tiers_block(agents, day_idx),
        build_dmad_mandate_block({"archetype": "stats_quant"}),  # generic footer
    ]
    return "\n\n".join(p for p in parts if p)

# ── AXELROD MECH B — SACRIFICIAL SYSTEM ──────────────────────────────────────
def assign_sacrificial_archetypes(agents, day_idx):
    """
    Mech B: bottom-3 agents by bankroll receive a NEW archetype they haven't
    used in the last 7 days ('used_archetypes' rolling window).
    Returns updated agents list and stores assignments in _state.
    """
    used_archetypes = _gs("_used_archetypes") or {}

    sorted_agents = sorted(agents, key=lambda a: a["bankroll"])
    bottom_3 = sorted_agents[:3]

    assignments = {}
    for ag in bottom_3:
        agent_id = ag["id"]
        recent_used = used_archetypes.get(str(agent_id), [])[-7:]
        available = [a for a in ARCHETYPES if a not in recent_used]
        if not available:
            available = ARCHETYPES   # fallback: all archetypes

        # Assign the least-recently-used archetype
        new_arch = available[0]
        ag["archetype"] = new_arch
        assignments[agent_id] = {
            "tier":       "sacrifice",
            "challenger": None,
            "challenged": None,
            "new_arch":   new_arch,
        }

        # Update rolling window
        used_archetypes.setdefault(str(agent_id), []).append(new_arch)
        used_archetypes[str(agent_id)] = used_archetypes[str(agent_id)][-7:]

    _ss("_used_archetypes",      used_archetypes)
    _ss("_challenge_assignments", assignments)
    return agents

def assign_challenge_tiers(agents):
    """
    Mech B: top-3 agents challenge bottom-3 agents.
    Updates _challenge_assignments with challenger/challenged pairs.
    """
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
    """Build the challenge context block for an agent's prompt."""
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
    """Full Mech B suffix appended to the agent's prompt."""
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

    # Agent's picks today (exclude current day if not yet picked — use history)
    agent_picks = [p["pick"] for p in day_picks if p["agent_id"] == agent_id]
    # Society baseline: all OTHER agents' picks today
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
        f"{b['pick']}→{b.get('result','pending')}" for b in agent_bets_today
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

    # Cash held (no bet today)
    total_bankroll = agent["bankroll"]
    staked_today   = sum(b.get("stake", 0) for b in agent_bets_today)
    cash_held_pct  = max(0.0, (total_bankroll - staked_today) / total_bankroll) if total_bankroll else 0.0

    # Common knowledge fields
    ck_block = _gs("_common_knowledge") or ""

    # Coalition / council fields (stub — populated when Mech B runs)
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
        "bankroll_growth_factor":   round(agent["bankroll"] / 10_000.0, 6),
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
        log_path = f"logs/day_{day_idx:04d}_agent_{agent['id']:02d}.json"
        api.upload_file(
            path_or_fileobj=json.dumps(record, indent=2).encode(),
            path_in_repo=log_path,
            repo_id=HF_AXELROD_REPO,
            repo_type="dataset",
            token=HF_DATASET_TOKEN,
            commit_message=f"axelrod log day={day_idx} agent={agent['id']}",
        )
        print(f"[axelrod-log] Pushed {log_path}")
    except Exception as e:
        print(f"[axelrod-log] push error: {e}")

# ── ORACLE BLOCK ──────────────────────────────────────────────────────────────
def get_oracle_block(games_today):
    """Call island oracle for all games in today's slate."""
    if not _ORACLE_OK:
        return ""
    try:
        preds = _island_nba_predict_many(games_today)
        return _island_oracle_block(nba_pred=preds[0] if preds else None)
    except Exception as e:
        print(f"[oracle] block error: {e}")
        return ""

# ── PROMPT BUILDER ────────────────────────────────────────────────────────────
def build_agent_prompt(agent, games_today, day_idx, standings, agents,
                       all_bets, day_picks, common_knowledge):
    """Build the full system + user prompt for one agent."""
    games_text = []
    for g in games_today:
        home_form = get_form_string(g["home_team"])
        away_form = get_form_string(g["away_team"])
        home_rec  = standings.summary(g["home_team"])
        away_rec  = standings.summary(g["away_team"])
        oracle_pred = ""
        if _ORACLE_OK:
            try:
                pred = _island_nba_predict(g)
                oracle_pred = _island_oracle_block(nba_pred=pred) if pred else ""
            except Exception:
                oracle_pred = ""
        games_text.append(
            f"Game: {g['home_team']} vs {g['away_team']}\n"
            f"  Home record: {home_rec} | Form: {home_form}\n"
            f"  Away record: {away_rec} | Form: {away_form}\n"
            f"  Odds — Home: {g.get('home_odds','N/A')} | Away: {g.get('away_odds','N/A')}\n"
            + (f"  {oracle_pred}\n" if oracle_pred else "")
        )

    # Common knowledge (Mech A broadcast)
    ck_block = common_knowledge or _gs("_common_knowledge") or ""

    # Peer stances (Mech A — real-time)
    peer_stances = build_peer_stances_block(day_picks, agent["id"])

    # Mech B suffix
    mech_b_suffix = build_sacrificial_system_suffix(agent, agents)

    system_prompt = (
        f"You are {agent['name']}, a professional NBA betting analyst.\n"
        f"Archetype: {agent['archetype']} — {ARCHETYPE_DESCRIPTIONS.get(agent['archetype'], '')}\n"
        f"Provider: {agent['provider']} | Model: {agent['model']}\n"
        f"Current bankroll: ${agent['bankroll']:,.2f}\n"
        f"Season record: {agent['bets_won']}W / {agent['bets_lost']}L / {agent['bets_push']}P\n\n"
        f"You MUST pick exactly ONE game to bet on today and output:\n"
        f"PICK: <Home Team> or <Away Team>\n"
        f"STAKE: <amount in dollars, 100-2000>\n"
        f"REASONING: <2-3 sentences>\n\n"
        f"Be concise. Output the three lines above and nothing else."
    )

    user_parts = [
        f"Day {day_idx + 1} — {len(games_today)} games on the slate:\n",
        "\n".join(games_text),
    ]
    if ck_block:
        user_parts.append(f"\n{ck_block}")
    if peer_stances:
        user_parts.append(f"\n{peer_stances}")
    user_parts.append(mech_b_suffix)

    return system_prompt, "\n".join(user_parts)

# ── LLM CALL ──────────────────────────────────────────────────────────────────
def call_agent(agent, games_today, day_idx, standings, agents,
               all_bets, day_picks, common_knowledge):
    """Call one agent's LLM and parse the response."""
    system_prompt, user_prompt = build_agent_prompt(
        agent, games_today, day_idx, standings, agents,
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
        return parse_agent_response(agent, response, games_today, day_idx)
    except Exception as e:
        print(f"[{agent['name']}] LLM error: {e}")
        return {
            "agent_id":   agent["id"],
            "agent_name": agent["name"],
            "archetype":  agent["archetype"],
            "pick":       "NO_PICK",
            "stake":      0,
            "reasoning":  f"Error: {e}",
            "day_idx":    day_idx,
        }

def parse_agent_response(agent, response, games_today, day_idx):
    """Parse LLM output into structured bet dict."""
    pick      = "NO_PICK"
    stake     = 500
    reasoning = ""

    for line in response.splitlines():
        line = line.strip()
        if line.upper().startswith("PICK:"):
            pick = line.split(":", 1)[1].strip()
        elif line.upper().startswith("STAKE:"):
            raw = line.split(":", 1)[1].strip().replace("$", "").replace(",", "")
            try:
                stake = max(100, min(2000, int(float(raw))))
            except ValueError:
                stake = 500
        elif line.upper().startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()

    return {
        "agent_id":   agent["id"],
        "agent_name": agent["name"],
        "archetype":  agent["archetype"],
        "pick":       pick,
        "stake":      stake,
        "reasoning":  reasoning,
        "day_idx":    day_idx,
    }

# ── BET RESOLUTION ────────────────────────────────────────────────────────────
def resolve_bet(bet, games_today):
    """Resolve a bet against actual game results."""
    for g in games_today:
        home, away = g["home_team"], g["away_team"]
        try:
            hs, as_ = int(g["home_score"]), int(g["away_score"])
        except (ValueError, KeyError):
            continue
        pick = bet.get("pick", "")
        if pick in (home, away):
            winner = home if hs > as_ else away
            return "win" if pick == winner else "loss"
    return "pending"

def apply_bet_result(agent, bet, result):
    """Update agent bankroll and stats from a resolved bet."""
    stake = bet.get("stake", 0)
    if result == "win":
        pnl = stake * 0.909   # approx -110 odds payout
        agent["bankroll"]  += pnl
        agent["bets_won"]  += 1
        agent["pnl"]       += pnl
    elif result == "loss":
        pnl = -stake
        agent["bankroll"]  += pnl
        agent["bets_lost"] += 1
        agent["pnl"]       += pnl
    else:
        pnl = 0
        agent["bets_push"] += 1
    agent["total_bets"] += 1
    agent["history"].append({
        "day_idx": bet["day_idx"],
        "pick":    bet["pick"],
        "stake":   stake,
        "result":  result,
        "pnl":     pnl,
    })
    return pnl

# ── DAY RUNNER ────────────────────────────────────────────────────────────────
def run_day(day_idx, games_today, agents, all_bets):
    """Run one full trading day: pick → resolve → update."""
    date_str = games_today[0].get("date", f"Day-{day_idx+1}") if games_today else f"Day-{day_idx+1}"
    day_picks = []

    # Mech B: assign sacrificial archetypes for bottom-3
    agents = assign_sacrificial_archetypes(agents, day_idx)
    agents = assign_challenge_tiers(agents)

    # Get common knowledge from previous day (Mech A)
    common_knowledge = _gs("_common_knowledge") or ""

    # Update oracle predictions for today's slate
    oracle_block = get_oracle_block(games_today)

    # Sequential agent calls (rate-limit friendly)
    for agent in agents:
        if _gs("stop_flag"):
            break
        bet = call_agent(
            agent, games_today, day_idx, _standings, agents,
            all_bets, day_picks, common_knowledge,
        )
        day_picks.append(bet)
        time.sleep(CALL_DELAY)

    # Resolve all bets
    day_pnl = []
    for bet in day_picks:
        result = resolve_bet(bet, games_today)
        bet["result"] = result
        agent = next((a for a in agents if a["id"] == bet["agent_id"]), None)
        if agent:
            pnl = apply_bet_result(agent, bet, result)
            bet["pnl"] = pnl
            day_pnl.append(pnl)
        all_bets.append(bet)

    # Update standings and form
    for g in games_today:
        _standings.update(g)
        update_recent_form(g)

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
    """Main entry point — loads state, runs days sequentially."""
    # Try to resume from saved state
    resumed = load_state()
    if not resumed or not _gs("agents"):
        all_games = load_nba_games()
        day_groups = group_games_by_day(all_games)
        agents = initialise_agents()
        _ss("agents",      agents)
        _ss("total_days",  len(day_groups))
        _ss("day_idx",     0)
        _ss("all_bets",    [])
        _ss("day_results", [])
        _ss("run_id",      f"run_{int(time.time())}")
        _ss("running",     True)
        _ss("stop_flag",   False)
    else:
        all_games  = load_nba_games()
        day_groups = group_games_by_day(all_games)
        _ss("running",   True)
        _ss("stop_flag", False)

    agents   = _gs("agents")
    all_bets = _gs("all_bets") or []
    start    = _gs("day_idx") or 0

    for day_idx in range(start, len(day_groups)):
        if _gs("stop_flag"):
            print("[sim] Stop flag set — exiting")
            break

        _ss("day_idx", day_idx)
        games_today = day_groups[day_idx]
        print(f"\n[sim] === Day {day_idx+1}/{len(day_groups)} — "
              f"{games_today[0].get('date','?')} — {len(games_today)} games ===")

        day_picks, agents, all_bets = run_day(day_idx, games_today, agents, all_bets)

        _ss("agents",   agents)
        _ss("all_bets", all_bets)
        save_state()

        day_summary = {
            "day_idx":  day_idx,
            "date":     games_today[0].get("date", ""),
            "n_games":  len(games_today),
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
    """Push final results JSON to HF Hub dataset."""
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
            commit_message=f"Trading floor results: {_gs('run_id')}",
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
    with gr.Blocks(title="NBA LLM Trading Floor") as demo:
        gr.Markdown("# 🏀 NBA LLM Trading Floor\n10 AI agents bet real money on NBA games.")

        with gr.Row():
            start_btn  = gr.Button("▶ Start Simulation", variant="primary")
            stop_btn   = gr.Button("⏹ Stop")
            status_txt = gr.Textbox(label="Status", interactive=False)

        leaderboard = gr.Dataframe(
            headers=["Agent", "Bankroll", "PnL", "W", "L", "Archetype"],
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
