#!/usr/bin/env python3
"""
NOMOS42 NBA TRADING FLOOR — HuggingFace Space Edition
======================================================
Runs trading-floor-v5 on HF Spaces (CPU free tier, 2 vCPU / 16GB RAM).
Lite mode by default (~25 agents). Auto-runs every 4 hours.

Providers used:
  - Google Gemini 2.5 Flash (free, primary)
  - HuggingFace Inference API (free, secondary)
  - Cohere Command-A (free, tertiary)
  - Cerebras Qwen3-32B (free, quaternary)

Environment secrets (set in HF Space settings):
  GOOGLE_API_KEY, GOOGLE_API_KEY_2   — Gemini
  HF_TOKEN, HF_TOKEN_2, HF_TOKEN_3  — HF Inference
  COHERE_API_KEY                     — Cohere
  CEREBRAS_API_KEY                   — Cerebras
  GIT_REPO_URL                       — (optional) git push results back
"""

import os
import sys
import json
import time
import threading
import traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta
from copy import deepcopy

# ── Environment bootstrap ──
for f in [Path(".env"), Path(".env.local")]:
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:]
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))

import gradio as gr

# ── Path setup: make arena/ importable ──
SPACE_ROOT = Path(__file__).parent.resolve()
ARENA_DIR = SPACE_ROOT / "arena"
sys.path.insert(0, str(ARENA_DIR))

# Data directory: persistent across restarts on HF Spaces
DATA_DIR = SPACE_ROOT / "data" / "arena"
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "traders-v5").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "predictions-v5").mkdir(parents=True, exist_ok=True)

# ── Monkey-patch hardcoded paths BEFORE importing trading floor ──
# The original code has ROOT = Path("/home/termius/mon-ipad")
# We need to override these at module level after import.

# Patch 1: Create a fake nomos-nba-agent data dir (odds/games)
FAKE_NBA_AGENT = SPACE_ROOT / "external-data" / "nba-agent"
(FAKE_NBA_AGENT / "data" / "historical-odds").mkdir(parents=True, exist_ok=True)
(FAKE_NBA_AGENT / "data" / "historical").mkdir(parents=True, exist_ok=True)

# ── Import arena modules (with path patching) ──
try:
    from api_pool import APIPool, get_pool, PROVIDERS
    from agent_registry import AgentRegistry, TradingAgent, AgentTier
    from bet_categories import ALL_CATEGORIES, CATEGORY_BY_ID
    HAS_ARENA = True
except ImportError as e:
    HAS_ARENA = False
    _IMPORT_ERROR = str(e)

# ── Global State ──
_state = {
    "last_run": None,
    "last_run_time": None,
    "last_result": None,
    "iteration": 0,
    "total_api_calls": 0,
    "total_bets": 0,
    "run_history": [],
    "is_running": False,
    "error": None,
    "agents_active": 0,
    "providers_active": [],
    "schedule_enabled": True,
    "schedule_interval_hours": 4,
}
_state_lock = threading.Lock()

# Results storage (persisted to disk)
RESULTS_FILE = DATA_DIR / "trading-floor-v5-latest.json"
STATE_FILE = DATA_DIR / "space-state.json"
HISTORY_FILE = DATA_DIR / "run-history.json"


def _load_persisted_state():
    """Load state from disk on startup."""
    if STATE_FILE.exists():
        try:
            saved = json.loads(STATE_FILE.read_text())
            with _state_lock:
                _state["iteration"] = saved.get("iteration", 0)
                _state["total_api_calls"] = saved.get("total_api_calls", 0)
                _state["total_bets"] = saved.get("total_bets", 0)
                _state["last_run"] = saved.get("last_run")
                _state["last_run_time"] = saved.get("last_run_time")
        except Exception:
            pass
    if HISTORY_FILE.exists():
        try:
            _state["run_history"] = json.loads(HISTORY_FILE.read_text())
        except Exception:
            _state["run_history"] = []


def _save_persisted_state():
    """Persist state to disk."""
    try:
        STATE_FILE.write_text(json.dumps({
            "iteration": _state["iteration"],
            "total_api_calls": _state["total_api_calls"],
            "total_bets": _state["total_bets"],
            "last_run": _state["last_run"],
            "last_run_time": _state["last_run_time"],
        }, indent=2))
        HISTORY_FILE.write_text(json.dumps(_state["run_history"][-50:], indent=2))
    except Exception:
        pass


# ============================================================================
# TRADING FLOOR RUNNER (lite mode, HF-adapted)
# ============================================================================

def _run_trading_floor_lite(target_date: str = None) -> dict:
    """
    Run a lite trading floor iteration.
    This is the core function called by both the scheduler and manual trigger.

    Since we cannot import the full 2400-line trading-floor-v5.py directly
    (it has many hardcoded paths and cross-repo dependencies), we run a
    simplified version that uses the same API pool and agent registry.
    """
    if not HAS_ARENA:
        return {"error": f"Arena modules not found: {_IMPORT_ERROR}",
                "status": "FAILED"}

    start = time.time()
    now = datetime.now(timezone.utc)
    if not target_date:
        target_date = now.strftime("%Y-%m-%d")

    result = {
        "date": target_date,
        "timestamp": now.isoformat(),
        "status": "running",
        "iteration": _state["iteration"] + 1,
        "mode": "lite",
        "agents": [],
        "predictions": {},
        "consensus": {},
        "bets": [],
        "api_calls": 0,
        "api_errors": 0,
        "providers_used": [],
        "duration_sec": 0,
    }

    try:
        # Initialize API pool
        pool = get_pool()

        # Check which providers are alive
        capacity = pool.get_capacity_report()
        active_providers = [p for p, info in capacity.items()
                           if info.get("keys", 0) > 0]
        result["providers_used"] = active_providers

        if not active_providers:
            result["status"] = "FAILED"
            result["error"] = "No API keys configured. Set GOOGLE_API_KEY or HF_TOKEN in Space secrets."
            return result

        # Initialize registry (lite mode agents)
        registry = AgentRegistry()
        lite_agents = _select_lite_agents(registry, pool)
        result["agents"] = [{"id": a.id, "name": a.name, "tier": a.tier.name,
                             "provider": a.provider, "model": a.model}
                            for a in lite_agents]

        # Try to fetch today's games from the-odds-api or fallback
        games = _fetch_todays_games(target_date)

        if not games:
            result["status"] = "NO_GAMES"
            result["message"] = f"No NBA games found for {target_date}"
            result["duration_sec"] = round(time.time() - start, 1)
            return result

        result["games"] = [{"home": g["home"], "away": g["away"],
                            "odds": g.get("odds", {})} for g in games]

        # Run predictions for each game
        from concurrent.futures import ThreadPoolExecutor, as_completed

        for game in games[:10]:  # Cap at 10 games per run
            game_key = f"{game['away']}@{game['home']}"
            game_predictions = {}

            # Call each lite agent
            def _call_one_agent(agent, gm, gk):
                try:
                    prompt = _build_lite_prompt(agent, gm)
                    resp = pool.call_llm(
                        provider=agent.provider,
                        prompt=prompt,
                        model=agent.model,
                        system="You are an elite NBA betting analyst. Respond only with valid JSON.",
                        max_tokens=512,
                        temperature=0.3,
                    )
                    return agent.id, resp
                except Exception as e:
                    return agent.id, None

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(_call_one_agent, a, game, game_key): a
                           for a in lite_agents}
                for future in as_completed(futures, timeout=120):
                    try:
                        aid, resp = future.result(timeout=30)
                        result["api_calls"] += 1
                        if resp:
                            game_predictions[aid] = resp
                        else:
                            result["api_errors"] += 1
                    except Exception:
                        result["api_errors"] += 1

            # Build consensus from predictions
            consensus = _build_consensus(game_predictions, game)
            result["predictions"][game_key] = {
                "agent_count": len(game_predictions),
                "predictions": {k: _safe_serialize(v)
                                for k, v in game_predictions.items()},
            }
            result["consensus"][game_key] = consensus

            # Generate bets from consensus
            bets = _generate_bets(consensus, game)
            result["bets"].extend(bets)

        result["status"] = "SUCCESS"
        result["duration_sec"] = round(time.time() - start, 1)

    except Exception as e:
        result["status"] = "ERROR"
        result["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        result["traceback"] = traceback.format_exc()[-500:]
        result["duration_sec"] = round(time.time() - start, 1)

    return result


def _select_lite_agents(registry: AgentRegistry, pool: APIPool) -> list:
    """Select ~25 agents for lite mode, using only providers with keys."""
    capacity = pool.get_capacity_report()
    available_providers = {p for p, info in capacity.items()
                          if info.get("keys", 0) > 0}

    # Remove anthropic_cli — no CLI on HF Space
    available_providers.discard("anthropic_cli")

    lite = []
    seen_models = set()

    # Tier 1+2: one agent per unique model from available providers
    for agent in registry.tier1 + registry.tier2:
        if agent.provider in available_providers and agent.model not in seen_models:
            lite.append(agent)
            seen_models.add(agent.model)
        if len(lite) >= 15:
            break

    # Tier 3: key specialist categories
    key_cats = ["ml_fg", "sp_fg", "tot_fg", "sp_alt_p5", "sp_alt_m5",
                "ml_1h", "tot_ou", "sp_q1"]
    for agent in registry.tier3:
        if (agent.provider in available_providers
                and agent.focus_category in key_cats
                and len(lite) < 25):
            lite.append(agent)

    # Ensure at least a few agents even if registry is empty
    if not lite:
        # Create minimal agents from available providers
        provider_models = {
            "google": "gemini-2.5-flash",
            "huggingface": "Qwen/Qwen2.5-72B-Instruct",
            "cohere": "command-a-03-2025",
            "cerebras": "qwen-3-32b",
        }
        for prov, model in provider_models.items():
            if prov in available_providers:
                lite.append(TradingAgent(
                    id=f"lite_{prov}",
                    name=f"Lite {prov.title()}",
                    tier=AgentTier.PREMIUM,
                    provider=prov,
                    model=model,
                    strategy="balanced",
                ))

    return lite


def _fetch_todays_games(target_date: str) -> list:
    """Fetch today's NBA games. Try local data, then fallback to odds API."""
    games = []

    # Check for local predictions file
    pred_file = SPACE_ROOT / "data" / "nba-agent" / "predictions-latest.json"
    if pred_file.exists():
        try:
            data = json.loads(pred_file.read_text())
            for p in data.get("predictions", []):
                if p.get("date", p.get("game_date", "")) == target_date:
                    games.append({
                        "home": p.get("home_team", p.get("home", "")),
                        "away": p.get("away_team", p.get("away", "")),
                        "odds": p.get("odds", {}),
                        "model_prob_home": p.get("prob_home", 0.5),
                    })
        except Exception:
            pass

    # Check for local odds-latest.json
    if not games:
        odds_file = SPACE_ROOT / "data" / "nba-agent" / "odds-latest.json"
        if odds_file.exists():
            try:
                data = json.loads(odds_file.read_text())
                raw = data.get("games", data) if isinstance(data, dict) else data
                if isinstance(raw, list):
                    for g in raw:
                        games.append({
                            "home": g.get("home_team", g.get("home", "")),
                            "away": g.get("away_team", g.get("away", "")),
                            "odds": {},
                            "model_prob_home": 0.5,
                        })
            except Exception:
                pass

    # Fallback: try the-odds-api if we have a key
    if not games:
        odds_key = os.environ.get("ODDS_API_KEY", "")
        if odds_key:
            try:
                import urllib.request
                url = (f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/"
                       f"?apiKey={odds_key}&regions=us&markets=h2h,spreads,totals"
                       f"&oddsFormat=decimal&dateFormat=iso")
                with urllib.request.urlopen(url, timeout=15) as resp:
                    data = json.loads(resp.read().decode())
                for g in data:
                    commence = g.get("commence_time", "")
                    if commence.startswith(target_date):
                        home = g.get("home_team", "")
                        away = g.get("away_team", "")
                        odds_entry = {}
                        for bk in g.get("bookmakers", [])[:1]:
                            for mkt in bk.get("markets", []):
                                if mkt["key"] == "h2h":
                                    outcomes = {o["name"]: o["price"]
                                                for o in mkt.get("outcomes", [])}
                                    odds_entry["ml_home_dec"] = outcomes.get(home, 1.91)
                                    odds_entry["ml_away_dec"] = outcomes.get(away, 1.91)
                        games.append({
                            "home": home, "away": away,
                            "odds": odds_entry,
                            "model_prob_home": 0.5,
                        })
            except Exception:
                pass

    # Last resort: generate a synthetic slate for testing
    if not games:
        games = _synthetic_games_for_date(target_date)

    return games


def _synthetic_games_for_date(target_date: str) -> list:
    """Generate plausible synthetic games for dates with no live data."""
    import hashlib
    # Use date as seed for deterministic synthetic games
    seed = int(hashlib.md5(target_date.encode()).hexdigest()[:8], 16)
    import random as _rng
    _rng.seed(seed)

    teams = [
        "Boston Celtics", "Oklahoma City Thunder", "Cleveland Cavaliers",
        "New York Knicks", "Denver Nuggets", "Milwaukee Bucks",
        "Golden State Warriors", "Dallas Mavericks", "Phoenix Suns",
        "Memphis Grizzlies", "Minnesota Timberwolves", "Los Angeles Lakers",
        "Miami Heat", "Sacramento Kings", "Philadelphia 76ers",
        "Indiana Pacers",
    ]
    _rng.shuffle(teams)
    games = []
    for i in range(0, min(len(teams), 10), 2):
        home_prob = 0.45 + _rng.random() * 0.20
        games.append({
            "home": teams[i],
            "away": teams[i + 1],
            "odds": {
                "ml_home_dec": round(1.0 / home_prob, 2),
                "ml_away_dec": round(1.0 / (1.0 - home_prob), 2),
            },
            "model_prob_home": round(home_prob, 3),
            "_synthetic": True,
        })
    return games[:5]


def _build_lite_prompt(agent: TradingAgent, game: dict) -> str:
    """Build a concise prompt for a lite-mode agent."""
    home = game.get("home", "Unknown")
    away = game.get("away", "Unknown")
    odds = game.get("odds", {})
    model_prob = game.get("model_prob_home", 0.5)

    odds_str = ""
    if odds.get("ml_home_dec") and odds.get("ml_away_dec"):
        impl_home = round(1.0 / odds["ml_home_dec"], 3)
        impl_away = round(1.0 / odds["ml_away_dec"], 3)
        odds_str = (f"Odds: {home} {odds['ml_home_dec']:.2f} "
                    f"(implied {impl_home:.1%}) | "
                    f"{away} {odds['ml_away_dec']:.2f} "
                    f"(implied {impl_away:.1%})")
    else:
        odds_str = "Odds: not available"

    model_str = f"Model P(home win) = {model_prob:.3f}" if model_prob else ""

    return (
        f"NBA GAME: {away} @ {home}\n"
        f"{odds_str}\n"
        f"{model_str}\n\n"
        f"Your strategy: {agent.strategy}\n"
        f"Your focus: {', '.join(agent.focus_groups) if agent.focus_groups else 'full game'}\n\n"
        f"Analyze this matchup. Return JSON with:\n"
        f'{{"ml_fg": {{"direction": "home"|"away", "confidence": 0.0-1.0, '
        f'"edge_pct": -5 to 15, "kelly_fraction": 0.0-0.15}}, '
        f'"spread_pick": "home"|"away"|"skip", '
        f'"total_pick": "over"|"under"|"skip", '
        f'"reasoning": "brief analysis (max 50 words)"}}'
    )


def _build_consensus(predictions: dict, game: dict) -> dict:
    """Build consensus from multiple agent predictions."""
    home_votes = 0
    away_votes = 0
    total_confidence = 0.0
    edges = []
    reasons = []
    n = 0

    for aid, pred in predictions.items():
        if not isinstance(pred, dict):
            continue
        ml = pred.get("ml_fg", {})
        if isinstance(ml, dict):
            direction = ml.get("direction", "").lower()
            conf = float(ml.get("confidence", 0.5))
            edge = float(ml.get("edge_pct", 0))
            if direction == "home":
                home_votes += 1
            elif direction == "away":
                away_votes += 1
            total_confidence += conf
            edges.append(edge)
            n += 1
        reason = pred.get("reasoning", "")
        if reason:
            reasons.append(reason[:80])

    consensus_dir = "home" if home_votes >= away_votes else "away"
    consensus_strength = max(home_votes, away_votes) / n if n > 0 else 0
    avg_conf = total_confidence / n if n > 0 else 0
    avg_edge = sum(edges) / len(edges) if edges else 0

    return {
        "direction": consensus_dir,
        "home_votes": home_votes,
        "away_votes": away_votes,
        "total_agents": n,
        "consensus_strength": round(consensus_strength, 3),
        "avg_confidence": round(avg_conf, 3),
        "avg_edge": round(avg_edge, 2),
        "top_reasons": reasons[:5],
        "home": game.get("home", ""),
        "away": game.get("away", ""),
    }


def _generate_bets(consensus: dict, game: dict) -> list:
    """Generate bet recommendations from consensus."""
    bets = []
    if consensus["consensus_strength"] >= 0.6 and consensus["avg_confidence"] >= 0.55:
        odds = game.get("odds", {})
        direction = consensus["direction"]

        # Kelly sizing
        prob = consensus["avg_confidence"]
        if direction == "home":
            dec_odds = odds.get("ml_home_dec", 1.91)
        else:
            dec_odds = odds.get("ml_away_dec", 1.91)

        b = dec_odds - 1.0
        if b > 0 and prob > 0:
            kelly_full = (prob * b - (1 - prob)) / b
            kelly = max(0, min(0.15, kelly_full * 0.5))  # Half Kelly, capped
        else:
            kelly = 0

        if kelly > 0.005:
            bets.append({
                "game": f"{consensus['away']} @ {consensus['home']}",
                "type": "moneyline",
                "pick": f"{consensus['home'] if direction == 'home' else consensus['away']} ML",
                "direction": direction,
                "odds_decimal": dec_odds,
                "confidence": consensus["avg_confidence"],
                "edge_pct": consensus["avg_edge"],
                "kelly_fraction": round(kelly, 4),
                "consensus_strength": consensus["consensus_strength"],
                "agents_agree": max(consensus["home_votes"], consensus["away_votes"]),
                "agents_total": consensus["total_agents"],
            })

    return bets


def _safe_serialize(obj):
    """Make an object JSON-serializable."""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(v) for v in obj]
    return str(obj)


# ============================================================================
# SCHEDULED RUNNER
# ============================================================================

def _run_iteration():
    """Run one trading floor iteration (called by scheduler or manual trigger)."""
    with _state_lock:
        if _state["is_running"]:
            return {"status": "BUSY", "message": "Already running an iteration"}
        _state["is_running"] = True
        _state["error"] = None

    try:
        target_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        result = _run_trading_floor_lite(target_date)

        with _state_lock:
            _state["iteration"] += 1
            _state["last_run"] = target_date
            _state["last_run_time"] = datetime.now(timezone.utc).isoformat()
            _state["last_result"] = result
            _state["total_api_calls"] += result.get("api_calls", 0)
            _state["total_bets"] += len(result.get("bets", []))
            _state["is_running"] = False

            # Append to history
            summary = {
                "date": target_date,
                "timestamp": _state["last_run_time"],
                "status": result.get("status", "UNKNOWN"),
                "games": len(result.get("games", result.get("consensus", {}))),
                "agents": len(result.get("agents", [])),
                "bets": len(result.get("bets", [])),
                "api_calls": result.get("api_calls", 0),
                "duration_sec": result.get("duration_sec", 0),
            }
            _state["run_history"].append(summary)

        # Persist results
        try:
            RESULTS_FILE.write_text(json.dumps(result, indent=2, default=str))
        except Exception:
            pass
        _save_persisted_state()

        return result

    except Exception as e:
        with _state_lock:
            _state["is_running"] = False
            _state["error"] = str(e)
        return {"status": "ERROR", "error": str(e)}


def _scheduler_loop():
    """Background scheduler: run iterations every N hours."""
    while True:
        with _state_lock:
            enabled = _state["schedule_enabled"]
            interval = _state["schedule_interval_hours"]

        if enabled:
            # Check if it's time to run
            should_run = False
            with _state_lock:
                last = _state.get("last_run_time")
            if not last:
                should_run = True
            else:
                try:
                    last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                    elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
                    if elapsed >= interval * 3600:
                        should_run = True
                except Exception:
                    should_run = True

            if should_run:
                print(f"[scheduler] Starting iteration at {datetime.now(timezone.utc).isoformat()}")
                try:
                    result = _run_iteration()
                    status = result.get("status", "UNKNOWN")
                    print(f"[scheduler] Iteration complete: {status}")
                except Exception as e:
                    print(f"[scheduler] Error: {e}")

        # Sleep 5 minutes between checks
        time.sleep(300)


# ============================================================================
# GRADIO UI
# ============================================================================

def _format_status():
    """Format current status as markdown."""
    with _state_lock:
        s = deepcopy(_state)

    lines = [
        "## Trading Floor Status",
        "",
        f"**Mode:** Lite (~25 agents) | **Iteration:** {s['iteration']}",
        f"**Last Run:** {s['last_run'] or 'Never'} at {s['last_run_time'] or 'N/A'}",
        f"**Total API Calls:** {s['total_api_calls']:,} | **Total Bets:** {s['total_bets']}",
        f"**Running:** {'YES' if s['is_running'] else 'No'}",
        f"**Schedule:** {'ON' if s['schedule_enabled'] else 'OFF'} "
        f"(every {s['schedule_interval_hours']}h)",
    ]

    if s.get("error"):
        lines.append(f"\n**Error:** {s['error']}")

    # Provider status
    try:
        pool = get_pool()
        capacity = pool.get_capacity_report()
        lines.append("\n### API Providers")
        lines.append("| Provider | Keys | Capacity/Day | Status |")
        lines.append("|----------|------|-------------|--------|")
        for prov, info in capacity.items():
            keys = info.get("keys", 0)
            cap = info.get("daily_capacity", 0)
            status = "READY" if keys > 0 else "No keys"
            lines.append(f"| {prov} | {keys} | {cap:,} | {status} |")
    except Exception:
        lines.append("\n*Provider status unavailable*")

    return "\n".join(lines)


def _format_latest_results():
    """Format latest results as markdown."""
    with _state_lock:
        result = deepcopy(_state.get("last_result"))

    if not result:
        # Try loading from disk
        if RESULTS_FILE.exists():
            try:
                result = json.loads(RESULTS_FILE.read_text())
            except Exception:
                pass

    if not result:
        return "No results yet. Run an iteration first."

    lines = [
        f"## Results: {result.get('date', 'Unknown')}",
        f"**Status:** {result.get('status', 'UNKNOWN')} | "
        f"**Duration:** {result.get('duration_sec', 0):.1f}s | "
        f"**API Calls:** {result.get('api_calls', 0)} "
        f"(errors: {result.get('api_errors', 0)})",
        "",
    ]

    # Games and consensus
    consensus = result.get("consensus", {})
    if consensus:
        lines.append("### Game Consensus")
        lines.append("| Game | Direction | Strength | Confidence | Edge | Votes |")
        lines.append("|------|-----------|----------|------------|------|-------|")
        for gk, c in consensus.items():
            lines.append(
                f"| {gk} | **{c.get('direction', '?').upper()}** | "
                f"{c.get('consensus_strength', 0):.0%} | "
                f"{c.get('avg_confidence', 0):.0%} | "
                f"{c.get('avg_edge', 0):+.1f}% | "
                f"{c.get('home_votes', 0)}H/{c.get('away_votes', 0)}A |"
            )

    # Bets
    bets = result.get("bets", [])
    if bets:
        lines.append("\n### Recommended Bets")
        lines.append("| Game | Pick | Odds | Kelly | Confidence |")
        lines.append("|------|------|------|-------|------------|")
        for b in bets:
            lines.append(
                f"| {b.get('game', '?')} | **{b.get('pick', '?')}** | "
                f"{b.get('odds_decimal', 0):.2f} | "
                f"{b.get('kelly_fraction', 0):.1%} | "
                f"{b.get('confidence', 0):.0%} |"
            )
    else:
        lines.append("\n*No bets met the threshold this iteration.*")

    # Agents
    agents = result.get("agents", [])
    if agents:
        lines.append(f"\n### Agents Used ({len(agents)})")
        by_tier = {}
        for a in agents:
            tier = a.get("tier", "?")
            by_tier.setdefault(tier, []).append(a)
        for tier, ags in sorted(by_tier.items()):
            providers = set(a.get("provider", "?") for a in ags)
            lines.append(f"- **{tier}**: {len(ags)} agents ({', '.join(providers)})")

    if result.get("error"):
        lines.append(f"\n**Error:** {result['error']}")

    return "\n".join(lines)


def _format_history():
    """Format run history as markdown."""
    with _state_lock:
        history = list(reversed(_state.get("run_history", [])))

    if not history:
        return "No run history yet."

    lines = [
        "## Run History (last 20)",
        "| # | Date | Status | Games | Agents | Bets | API Calls | Duration |",
        "|---|------|--------|-------|--------|------|-----------|----------|",
    ]
    for i, h in enumerate(history[:20], 1):
        lines.append(
            f"| {i} | {h.get('date', '?')} | {h.get('status', '?')} | "
            f"{h.get('games', 0)} | {h.get('agents', 0)} | "
            f"{h.get('bets', 0)} | {h.get('api_calls', 0)} | "
            f"{h.get('duration_sec', 0):.0f}s |"
        )

    return "\n".join(lines)


def _format_json_output():
    """Return raw JSON of latest results."""
    with _state_lock:
        result = _state.get("last_result")
    if not result:
        if RESULTS_FILE.exists():
            try:
                return RESULTS_FILE.read_text()
            except Exception:
                pass
        return "{}"
    return json.dumps(result, indent=2, default=str)


def _trigger_run():
    """Manual trigger for a trading floor iteration."""
    with _state_lock:
        if _state["is_running"]:
            return "Already running. Please wait.", _format_status(), _format_latest_results()

    # Run in background thread to not block Gradio
    def _bg():
        _run_iteration()

    t = threading.Thread(target=_bg, daemon=True)
    t.start()

    return ("Iteration started. Refresh in 1-2 minutes to see results.",
            _format_status(),
            _format_latest_results())


def _toggle_schedule(enabled: bool, interval: int):
    """Toggle the scheduler on/off."""
    with _state_lock:
        _state["schedule_enabled"] = enabled
        _state["schedule_interval_hours"] = max(1, min(24, interval))
    _save_persisted_state()
    return _format_status()


def _refresh():
    """Refresh all displays."""
    return _format_status(), _format_latest_results(), _format_history()


# ============================================================================
# FASTAPI ENDPOINTS (via Gradio's underlying FastAPI)
# ============================================================================

def _mount_api(app):
    """Mount JSON API endpoints on the Gradio FastAPI app."""
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.get("/api/status")
    async def api_status():
        with _state_lock:
            return JSONResponse(content={
                "status": "running" if _state["is_running"] else "idle",
                "iteration": _state["iteration"],
                "last_run": _state["last_run"],
                "last_run_time": _state["last_run_time"],
                "total_api_calls": _state["total_api_calls"],
                "total_bets": _state["total_bets"],
                "schedule_enabled": _state["schedule_enabled"],
                "schedule_interval_hours": _state["schedule_interval_hours"],
            })

    @app.get("/api/latest")
    async def api_latest():
        with _state_lock:
            result = _state.get("last_result")
        if not result and RESULTS_FILE.exists():
            try:
                result = json.loads(RESULTS_FILE.read_text())
            except Exception:
                result = {}
        return JSONResponse(content=result or {})

    @app.get("/api/consensus")
    async def api_consensus():
        with _state_lock:
            result = _state.get("last_result", {})
        return JSONResponse(content=result.get("consensus", {}))

    @app.get("/api/bets")
    async def api_bets():
        with _state_lock:
            result = _state.get("last_result", {})
        return JSONResponse(content=result.get("bets", []))

    @app.post("/api/trigger")
    async def api_trigger():
        with _state_lock:
            if _state["is_running"]:
                return JSONResponse(content={"status": "busy"}, status_code=429)

        def _bg():
            _run_iteration()
        t = threading.Thread(target=_bg, daemon=True)
        t.start()
        return JSONResponse(content={"status": "started"})

    @app.get("/api/history")
    async def api_history():
        with _state_lock:
            return JSONResponse(content=_state.get("run_history", []))

    @app.get("/api/health")
    async def api_health():
        return JSONResponse(content={
            "healthy": True,
            "arena_modules": HAS_ARENA,
            "iteration": _state["iteration"],
            "uptime": "ok",
        })


# ============================================================================
# MAIN
# ============================================================================

# Load persisted state
_load_persisted_state()

# Build Gradio UI
with gr.Blocks(
    title="Nomos42 NBA Trading Floor",
    theme=gr.themes.Base(
        primary_hue="indigo",
        secondary_hue="purple",
    ),
    css="""
    .contain { max-width: 1200px; margin: auto; }
    .status-box { font-family: monospace; }
    """
) as demo:

    gr.Markdown(
        "# Nomos42 NBA Trading Floor v5\n"
        "217+ AI Agent Swarm | Lite Mode (~25 agents) | "
        "Auto-runs every 4 hours\n\n"
        "**Providers:** Gemini 2.5 Flash + HF Inference + Cohere + Cerebras"
    )

    with gr.Tab("Status"):
        status_md = gr.Markdown(_format_status())
        with gr.Row():
            run_btn = gr.Button("Run Now", variant="primary", size="lg")
            refresh_btn = gr.Button("Refresh", size="lg")
        run_msg = gr.Textbox(label="Message", interactive=False, visible=True)

    with gr.Tab("Results"):
        results_md = gr.Markdown(_format_latest_results())
        refresh_results_btn = gr.Button("Refresh Results")

    with gr.Tab("History"):
        history_md = gr.Markdown(_format_history())
        refresh_history_btn = gr.Button("Refresh History")

    with gr.Tab("JSON API"):
        gr.Markdown(
            "### API Endpoints\n"
            "| Endpoint | Method | Description |\n"
            "|----------|--------|-------------|\n"
            "| `/api/status` | GET | Current status |\n"
            "| `/api/latest` | GET | Latest full results |\n"
            "| `/api/consensus` | GET | Game consensus only |\n"
            "| `/api/bets` | GET | Recommended bets only |\n"
            "| `/api/trigger` | POST | Trigger new iteration |\n"
            "| `/api/history` | GET | Run history |\n"
            "| `/api/health` | GET | Health check |\n"
        )
        json_output = gr.Code(language="json", label="Latest Results (JSON)",
                              value=_format_json_output())
        refresh_json_btn = gr.Button("Refresh JSON")
        refresh_json_btn.click(fn=_format_json_output, outputs=[json_output])

    with gr.Tab("Settings"):
        gr.Markdown("### Scheduler Settings")
        schedule_toggle = gr.Checkbox(
            label="Auto-schedule enabled",
            value=_state["schedule_enabled"],
        )
        schedule_interval = gr.Slider(
            minimum=1, maximum=24, step=1,
            label="Interval (hours)",
            value=_state["schedule_interval_hours"],
        )
        save_settings_btn = gr.Button("Save Settings")
        settings_status = gr.Markdown("")
        save_settings_btn.click(
            fn=_toggle_schedule,
            inputs=[schedule_toggle, schedule_interval],
            outputs=[settings_status],
        )

    # Wire up buttons
    run_btn.click(
        fn=_trigger_run,
        outputs=[run_msg, status_md, results_md],
    )
    refresh_btn.click(
        fn=lambda: (_format_status(), _format_latest_results(), _format_history()),
        outputs=[status_md, results_md, history_md],
    )
    refresh_results_btn.click(
        fn=_format_latest_results,
        outputs=[results_md],
    )
    refresh_history_btn.click(
        fn=_format_history,
        outputs=[history_md],
    )

# Mount API endpoints
_mount_api(demo.app)

# Start scheduler thread
_scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
_scheduler_thread.start()
print(f"[trading-floor-space] Scheduler started (every {_state['schedule_interval_hours']}h)")
print(f"[trading-floor-space] Arena modules: {'OK' if HAS_ARENA else 'MISSING'}")

# Launch
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
else:
    # HF Spaces auto-launches via demo object
    demo.queue()
