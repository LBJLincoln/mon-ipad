#!/usr/bin/env python3
"""
Nomos42 Trading Floor — 10 Real LLM Agents (CLI Runner)
========================================================
Batch runner for GH Actions. Processes N games per run, persists state.
Same agents/providers as the HF Space (hf-llm-trading-floor/app.py).

Usage:
    python3 scripts/arena/trading-floor-10agents-cli.py [--games 10] [--reset]
"""

import json, os, sys, time, requests, csv, argparse
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parent.parent.parent  # mon-ipad/
HF_DATA = Path(__file__).resolve().parent / "hf-llm-trading-floor" / "data"
STATE_FILE = ROOT / "data" / "arena" / "trading-floor-10agents-state.json"
OUTPUT_FILE = ROOT / "data" / "arena" / "trading-floor-10agents-latest.json"

# ── TEAM MAP ──────────────────────────────────────────────────────────────────
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

# ── PROVIDERS (verified 2026-04-13) ──────────────────────────────────────────
PROVIDERS = {
    "cerebras:qwen-3-235b": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "qwen-3-235b-a22b-instruct-2507", "key_env": "CEREBRAS_API_KEY",
        "max_tokens": 400, "rpm": 30,
    },
    "cerebras:llama3.1-8b": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "llama3.1-8b", "key_env": "CEREBRAS_API_KEY",
        "max_tokens": 400, "rpm": 30,
    },
    # NOTE: cerebras:zai-glm-4.7 and gpt-oss-120b return 404 — replaced with OpenRouter
    "openrouter:glm-4.5-air:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "z-ai/glm-4.5-air:free", "key_env": "OPENROUTER_KEY_BARTOLI",
        "max_tokens": 400, "rpm": 20,
    },
    "openrouter:gpt-oss-20b:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "openai/gpt-oss-20b:free", "key_env": "OPENROUTER_KEY_ORCHESTRATOR",
        "max_tokens": 400, "rpm": 20,
    },
    "google:gemini-2.5-flash": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        "model": "gemini-2.5-flash", "key_env": "GOOGLE_API_KEY",
        "max_tokens": 400, "rpm": 14,
    },
    "google:gemini-3-flash": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent",
        "model": "gemini-3-flash-preview", "key_env": "GOOGLE_API_KEY_2",
        "max_tokens": 400, "rpm": 14,
    },
    "openrouter:gemma-4-26b:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "google/gemma-4-26b-a4b-it:free", "key_env": "OPENROUTER_KEY_ORCHESTRATOR",
        "max_tokens": 400, "rpm": 20,
    },
    "openrouter:nemotron-120b:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "nvidia/nemotron-3-super-120b-a12b:free", "key_env": "OPENROUTER_KEY_BARTOLI",
        "max_tokens": 400, "rpm": 20,
    },
    "openrouter:minimax-m2.5:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "minimax/minimax-m2.5:free", "key_env": "OPENROUTER_KEY_PME",
        "max_tokens": 400, "rpm": 20,
    },
    "openrouter:qwen3-80b:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "qwen/qwen3-next-80b-a3b-instruct:free", "key_env": "OPENROUTER_KEY_ORCHESTRATOR",
        "max_tokens": 400, "rpm": 20,
    },
}

# ── 10 AGENTS ─────────────────────────────────────────────────────────────────
TRADERS = {
    "gemini":   {"name": "Gemini Flash",   "provider": "google:gemini-2.5-flash",       "personality": "analytical",   "risk": 0.60},
    "gemini3":  {"name": "Gemini 3 Flash",  "provider": "google:gemini-3-flash",         "personality": "diversified",  "risk": 0.50},
    "qwen":     {"name": "Qwen 3 235B",     "provider": "cerebras:qwen-3-235b",          "personality": "quantitative", "risk": 0.55},
    "llama":    {"name": "Llama 3.1 8B",    "provider": "cerebras:llama3.1-8b",           "personality": "contrarian",   "risk": 0.65},
    "glm":      {"name": "GLM 4.5 Air",      "provider": "openrouter:glm-4.5-air:free",   "personality": "conservative", "risk": 0.40},
    "gptoss":   {"name": "GPT-OSS 20B",     "provider": "openrouter:gpt-oss-20b:free",   "personality": "aggressive",   "risk": 0.70},
    "gemma4":   {"name": "Gemma 4 26B",     "provider": "openrouter:gemma-4-26b:free",   "personality": "arbitrage",    "risk": 0.75},
    "nemotron": {"name": "Nemotron 120B",   "provider": "openrouter:nemotron-120b:free",  "personality": "tactical",     "risk": 0.60},
    "minimax":  {"name": "MiniMax M2.5",    "provider": "openrouter:minimax-m2.5:free",   "personality": "theoretical",  "risk": 0.35},
    "qwen3":    {"name": "Qwen3 80B",       "provider": "openrouter:qwen3-80b:free",      "personality": "ensemble",     "risk": 0.50},
}

SYSTEM_PROMPTS = {
    "gemini":   "You are Gemini Flash, analytical NBA betting agent. Trust numbers over narratives. Cross-reference model predictions with market odds. half_kelly, confidence_scaled. Risk: 0.60.",
    "gemini3":  "You are Gemini 3 Flash, diversified strategy rotation agent. Rotate strategies based on performance. quarter_kelly, value_hunter. Risk: 0.50.",
    "qwen":     "You are Qwen 3 235B, pure quant agent. Calculate implied probabilities, compute Kelly fractions. half_kelly, ev_threshold. Risk: 0.55.",
    "llama":    "You are Llama 3.1 8B, contrarian agent. Fade the public. When public money >70% on one side, find value on the other. underdog_specialist. Risk: 0.65.",
    "glm":      "You are GLM 4.5 Air, conservative capital-preservation agent. Only bet when multiple signals align. eighth_kelly. Risk: 0.40.",
    "gptoss":   "You are GPT-OSS 20B, aggressive high-conviction agent. Go big or go home. full_kelly, streak_momentum. Risk: 0.70.",
    "gemma4":   "You are Gemma 4 26B, arbitrage-hunting agent. Hunt pricing inefficiencies between categories. confidence_scaled. Risk: 0.75.",
    "nemotron": "You are Nemotron 120B, tactical agent. Military precision. Analyze form, rest, travel. half_kelly, schedule-based. Risk: 0.60.",
    "minimax":  "You are MiniMax M2.5, theoretical/academic agent. Game theory + information theory. eighth_kelly. Risk: 0.35.",
    "qwen3":    "You are Qwen3 80B, ensemble/meta-learning agent. Aggregate signals: model 40%, market 30%, own 30%. confidence_scaled. Risk: 0.50.",
}

# ── RATE LIMITER ──────────────────────────────────────────────────────────────
_last_call: Dict[str, float] = {}
_llm_calls = 0
_llm_fails = 0

# Gateway mode: if GATEWAY_URL is set, route all LLM calls through the proxy
GATEWAY_URL = os.environ.get("GATEWAY_URL", "").rstrip("/")  # e.g. https://lbjlincoln26-llm-gateway.hf.space

def rate_limit(provider: str):
    cfg = PROVIDERS.get(provider, {})
    rpm = cfg.get("rpm", 15)
    key = provider.split(":")[0]
    now = time.time()
    wait = (60.0 / rpm) - (now - _last_call.get(key, 0))
    if wait > 0:
        time.sleep(wait)
    _last_call[key] = time.time()


def _call_via_gateway(provider: str, system: str, user: str) -> Optional[str]:
    """Route LLM call through the centralized gateway (automatic failover).
    Uses Gradio 5.x two-step API: POST event → GET result."""
    try:
        # Step 1: Create event
        resp = requests.post(
            f"{GATEWAY_URL}/gradio_api/call/call_model",
            json={"data": [provider, system, user, 400]},
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        event_id = resp.json().get("event_id")
        if not event_id:
            return None

        # Step 2: Get result (SSE stream)
        resp2 = requests.get(
            f"{GATEWAY_URL}/gradio_api/call/call_model/{event_id}",
            timeout=60,
            stream=True,
        )
        for line in resp2.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                data = json.loads(line[6:])
                if isinstance(data, list) and data:
                    result = json.loads(data[0])
                    return result.get("content")
    except Exception as e:
        print(f"  [gateway] {provider} failed: {e}", file=sys.stderr)
    return None


def call_llm(provider: str, system: str, user: str) -> Optional[str]:
    global _llm_calls, _llm_fails
    _llm_calls += 1

    # Route through gateway if available
    if GATEWAY_URL:
        result = _call_via_gateway(provider, system, user)
        if result:
            return result
        _llm_fails += 1
        return None

    # Direct API calls (original path)
    cfg = PROVIDERS.get(provider)
    if not cfg:
        _llm_fails += 1
        return None
    api_key = os.environ.get(cfg["key_env"], "")
    if not api_key:
        _llm_fails += 1
        return None

    rate_limit(provider)

    for attempt in range(2):
        try:
            if "google" in provider:
                url = f"{cfg['url']}?key={api_key}"
                payload = {
                    "contents": [{"parts": [{"text": f"{system}\n\n{user}"}]}],
                    "generationConfig": {"maxOutputTokens": cfg["max_tokens"], "temperature": 0.3},
                }
                resp = requests.post(url, json=payload, timeout=20)
                if resp.status_code == 200:
                    return resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            else:
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                if "openrouter" in provider:
                    headers["HTTP-Referer"] = "https://nomos42.ai"
                    headers["X-Title"] = "Nomos42 Trading Floor"
                payload = {
                    "model": cfg["model"],
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "max_tokens": cfg["max_tokens"], "temperature": 0.3,
                }
                resp = requests.post(cfg["url"], json=payload, headers=headers, timeout=20)
                if resp.status_code == 200:
                    return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            if resp.status_code == 429 and attempt == 0:
                time.sleep(5)
                continue
            break
        except Exception:
            if attempt == 0:
                time.sleep(2)
                continue
            break

    _llm_fails += 1
    return None


def parse_decision(raw: str) -> Optional[Dict]:
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


def resolve_bet(cat: str, odds: Dict, hs: int, as_: int, home_won: bool) -> bool:
    cat = cat.lower().strip()
    total_pts = hs + as_
    spread = odds.get("spread_home", 0) or 0
    total_line = odds.get("total", 0) or 0
    margin = hs - as_

    if cat == "ml_home": return home_won
    if cat == "ml_away": return not home_won
    if cat == "spread_home": return (hs + spread) > as_
    if cat == "spread_away": return (as_ - spread) > hs
    if cat == "total_over": return total_pts > total_line if total_line else False
    if cat == "total_under": return total_pts < total_line if total_line else False
    if cat.startswith("h1_") or cat.startswith("h2_"):
        if "ml_home" in cat: return home_won
        if "ml_away" in cat: return not home_won
        if "total_over" in cat: return total_pts > total_line if total_line else False
        if "total_under" in cat: return total_pts < total_line if total_line else False
    if cat == "team_total_home_over":
        return hs > (total_line - spread) / 2 if total_line else False
    if cat == "team_total_away_over":
        return as_ > (total_line + spread) / 2 if total_line else False
    return False


def get_odds_dec(cat: str, odds: Dict) -> float:
    cat = cat.lower().strip()
    if cat == "ml_home": return odds.get("ml_home_dec", 1.91)
    if cat == "ml_away": return odds.get("ml_away_dec", 1.91)
    return 1.91


# ── DATA LOADING ──────────────────────────────────────────────────────────────
def load_games() -> List[Dict]:
    fp = HF_DATA / "games-2025-26.json"
    if not fp.exists():
        print(f"ERROR: {fp} not found")
        return []
    raw = json.loads(fp.read_text())
    games_list = raw.get("games", raw if isinstance(raw, list) else [])
    enriched = []
    for g in games_list:
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
            "date": g.get("game_date", ""), "home": home, "away": away,
            "home_score": int(hs), "away_score": int(as_), "home_won": int(hs) > int(as_),
        })
    enriched.sort(key=lambda g: g["date"])
    return enriched


def load_odds() -> Dict:
    fp = HF_DATA / "nba_2025-26_odds.csv"
    if not fp.exists():
        return {}
    odds = {}
    with open(fp) as f:
        for row in csv.DictReader(f):
            home = TEAM_MAP.get(row.get("home_team", ""), row.get("home_team", ""))
            away = TEAM_MAP.get(row.get("away_team", ""), row.get("away_team", ""))
            try:
                ml_h = row.get("moneyline_home", "").strip()
                ml_a = row.get("moneyline_away", "").strip()
                if not ml_h or not ml_a:
                    continue
                def to_dec(s):
                    v = float(s)
                    if 1.0 < v < 15.0 and "." in s: return v
                    v = int(float(s))
                    return (v / 100.0 + 1) if v > 0 else (100.0 / abs(v) + 1)
                sp = row.get("spread_home", "").strip()
                tot = row.get("total", "").strip()
                odds[(row.get("date", ""), home, away)] = {
                    "ml_home_dec": to_dec(ml_h), "ml_away_dec": to_dec(ml_a),
                    "spread_home": float(sp) if sp else None,
                    "total": float(tot) if tot else None,
                }
            except (ValueError, TypeError):
                continue
    return odds


def compute_standings(games: List[Dict], up_to: str) -> Dict:
    st = defaultdict(lambda: {"w": 0, "l": 0})
    for g in games:
        if g["date"] >= up_to:
            break
        if g["home_won"]:
            st[g["home"]]["w"] += 1; st[g["away"]]["l"] += 1
        else:
            st[g["away"]]["w"] += 1; st[g["home"]]["l"] += 1
    for s in st.values():
        total = s["w"] + s["l"]
        s["win_pct"] = round(s["w"] / total, 3) if total else 0
    return dict(st)


# ── STATE MANAGEMENT ──────────────────────────────────────────────────────────
def load_state() -> Dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return init_state()


def init_state() -> Dict:
    agents = {}
    for tid in TRADERS:
        agents[tid] = {
            "bankroll": 100.0, "total_bets": 0, "wins": 0, "losses": 0,
            "passes": 0, "llm_calls": 0, "llm_ok": 0,
            "best_bankroll": 100.0, "max_drawdown": 0.0,
        }
    return {
        "version": "10agents-v1",
        "created": datetime.now(timezone.utc).isoformat(),
        "games_processed": 0,
        "total_iterations": 0,
        "agents": agents,
    }


def save_state(state: Dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def save_output(state: Dict, games_total: int):
    leaderboard = []
    for tid, ts in sorted(state["agents"].items(), key=lambda x: -x[1]["bankroll"]):
        cfg = TRADERS[tid]
        roi = ((ts["bankroll"] - 100) / 100) * 100
        wr = ts["wins"] / max(1, ts["total_bets"]) * 100
        leaderboard.append({
            "rank": len(leaderboard) + 1,
            "trader_id": tid, "name": cfg["name"],
            "provider": cfg["provider"], "personality": cfg["personality"],
            "bankroll": round(ts["bankroll"], 2),
            "roi_pct": round(roi, 2),
            "total_bets": ts["total_bets"], "wins": ts["wins"], "losses": ts["losses"],
            "win_rate": round(wr, 1),
            "max_drawdown": round(ts["max_drawdown"], 4),
            "llm_calls": ts["llm_calls"], "llm_ok": ts["llm_ok"],
        })

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "10agents-real-llm",
        "games_processed": state["games_processed"],
        "games_total": games_total,
        "progress_pct": round(state["games_processed"] / max(1, games_total) * 100, 1),
        "total_iterations": state["total_iterations"],
        "llm_calls_total": _llm_calls,
        "llm_fails_total": _llm_fails,
        "leaderboard": leaderboard,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    return output


# ── MAIN LOOP ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="10-agent real LLM trading floor CLI")
    parser.add_argument("--games", type=int, default=100, help="Games to process this run")
    parser.add_argument("--reset", action="store_true", help="Reset state and start fresh")
    args = parser.parse_args()

    print("=" * 60)
    print("NOMOS42 REAL LLM TRADING FLOOR — CLI RUNNER")
    print("=" * 60)

    # Check API keys
    keys_found = []
    for env in ["CEREBRAS_API_KEY", "GOOGLE_API_KEY", "GOOGLE_API_KEY_2",
                "OPENROUTER_KEY_ORCHESTRATOR", "OPENROUTER_KEY_PME", "OPENROUTER_KEY_BARTOLI"]:
        if os.environ.get(env):
            keys_found.append(env)
    print(f"API keys: {', '.join(keys_found) or 'NONE'}")

    if not keys_found:
        print("ERROR: No API keys found. Set at least CEREBRAS_API_KEY.")
        sys.exit(1)

    # Load data
    all_games = load_games()
    odds_dict = load_odds()
    print(f"Games: {len(all_games)} | Odds: {len(odds_dict)}")

    if not all_games:
        print("ERROR: No game data")
        sys.exit(1)

    # Load or init state
    if args.reset or not STATE_FILE.exists():
        state = init_state()
        print("State: FRESH")
    else:
        state = load_state()
        print(f"State: loaded ({state['games_processed']} games done, iter {state['total_iterations']})")

    start_idx = state["games_processed"]
    end_idx = min(start_idx + args.games, len(all_games))

    if start_idx >= len(all_games):
        print(f"All {len(all_games)} games already processed! Use --reset to restart.")
        save_output(state, len(all_games))
        return

    print(f"Processing games {start_idx + 1} to {end_idx} of {len(all_games)}")
    print("-" * 60)

    start_time = time.time()

    for game_idx in range(start_idx, end_idx):
        game = all_games[game_idx]
        home, away = game["home"], game["away"]
        hs, as_ = game["home_score"], game["away_score"]
        home_won = game["home_won"]
        game_date = game["date"]

        standings = compute_standings(all_games, game_date)
        h_st = standings.get(home, {})
        a_st = standings.get(away, {})

        # Get odds
        odds_key = (game_date, home, away)
        odds = odds_dict.get(odds_key)
        if not odds:
            odds_key_rev = (game_date, away, home)
            raw = odds_dict.get(odds_key_rev)
            if raw:
                odds = {
                    "ml_home_dec": raw.get("ml_away_dec", 2.0),
                    "ml_away_dec": raw.get("ml_home_dec", 2.0),
                    "spread_home": -(raw.get("spread_home", 0) or 0),
                    "total": raw.get("total"),
                }
            else:
                hp = h_st.get("win_pct", 0.5)
                home_prob = max(0.15, min(0.85, hp * 0.6 + 0.5 * 0.4 + 0.035))
                odds = {"ml_home_dec": round(1 / home_prob, 3),
                        "ml_away_dec": round(1 / (1 - home_prob), 3),
                        "spread_home": round((0.5 - home_prob) * 20, 1), "total": 220.0}

        ml_h = odds.get("ml_home_dec", 2.0)
        ml_a = odds.get("ml_away_dec", 2.0)
        impl_h = round(1 / ml_h, 3) if ml_h > 1 else 0.5

        game_bets = []

        # ── PARALLEL: Call all 10 agents simultaneously ──
        def _agent_call(tid):
            cfg = TRADERS[tid]
            ts = state["agents"][tid]
            if ts["bankroll"] <= 1.0:
                return tid, None, True  # pass
            roi = ((ts["bankroll"] - 100) / 100) * 100
            prompt = (
                f"GAME: {away} @ {home} | {game_date}\n"
                f"STANDINGS: {home} {h_st.get('w',0)}-{h_st.get('l',0)} ({h_st.get('win_pct',0):.3f}) | "
                f"{away} {a_st.get('w',0)}-{a_st.get('l',0)} ({a_st.get('win_pct',0):.3f})\n"
                f"ODDS: ML {home} {ml_h:.3f} (impl {impl_h:.1%}) | {away} {ml_a:.3f}\n"
                f"Spread: {home} {odds.get('spread_home', 'N/A')} | Total: {odds.get('total', 'N/A')}\n"
                f"YOUR STATE: ${ts['bankroll']:.2f} | {ts['total_bets']} bets | {ts['wins']}W-{ts['losses']}L | ROI {roi:+.1f}%\n\n"
                f"Respond ONLY JSON: {{\"reasoning\": \"1-2 sentences\", \"bets\": [{{\"category\": \"ml_home\", \"confidence\": 0.65, \"edge\": 0.05, \"bet_pct\": 0.02}}], \"pass\": false}}\n"
                f"Categories: ml_home, ml_away, spread_home, spread_away, total_over, total_under\n"
                f"Rules: max 2 bets, bet_pct 0.005-0.08, pass if no edge."
            )
            raw = call_llm(cfg["provider"], SYSTEM_PROMPTS[tid], prompt)
            return tid, raw, False

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(_agent_call, tid): tid for tid in TRADERS}
            for future in as_completed(futures):
                tid, raw, was_pass = future.result()
                cfg = TRADERS[tid]
                ts = state["agents"][tid]

                if was_pass:
                    ts["passes"] += 1
                    continue

                ts["llm_calls"] += 1
                if raw:
                    ts["llm_ok"] += 1
                    decision = parse_decision(raw)
                else:
                    decision = None

                if decision and isinstance(decision.get("bets"), list) and not decision.get("pass", True):
                    for bet in decision["bets"][:2]:
                        cat = bet.get("category", "").lower()
                        edge = float(bet.get("edge", 0))
                        bet_pct = min(float(bet.get("bet_pct", 0.01)), 0.08)
                        if not cat or edge <= 0 or bet_pct <= 0:
                            continue
                        amount = round(ts["bankroll"] * bet_pct, 2)
                        amount = min(amount, ts["bankroll"] * 0.1)
                        if amount < 0.10:
                            continue

                        won = resolve_bet(cat, odds, hs, as_, home_won)
                        odds_dec = get_odds_dec(cat, odds)

                        if won:
                            ts["bankroll"] += round(amount * (odds_dec - 1), 2)
                            ts["wins"] += 1
                        else:
                            ts["bankroll"] -= amount
                            ts["losses"] += 1
                        ts["bankroll"] = round(ts["bankroll"], 2)
                        ts["total_bets"] += 1
                        game_bets.append(f"{cfg['name'][:8]}:{cat}({'W' if won else 'L'})")
                else:
                    ts["passes"] += 1

                ts["best_bankroll"] = max(ts["best_bankroll"], ts["bankroll"])
                dd = (ts["best_bankroll"] - ts["bankroll"]) / ts["best_bankroll"] if ts["best_bankroll"] > 0 else 0
                ts["max_drawdown"] = max(ts["max_drawdown"], dd)

        state["games_processed"] = game_idx + 1
        bets_str = " | ".join(game_bets[:5]) if game_bets else "all passed"
        result_str = f"{'W' if home_won else 'L'} {hs}-{as_}"
        print(f"  [{game_idx+1}/{len(all_games)}] {game_date} {away}@{home} {result_str} → {bets_str}")

    state["total_iterations"] += 1
    elapsed = time.time() - start_time

    # Save
    save_state(state)
    output = save_output(state, len(all_games))

    print("\n" + "=" * 60)
    print(f"DONE: {end_idx - start_idx} games in {elapsed:.0f}s | LLM: {_llm_calls} calls ({_llm_fails} fails)")
    print(f"Progress: {state['games_processed']}/{len(all_games)} ({output['progress_pct']}%)")
    print(f"\nLEADERBOARD:")
    for a in output["leaderboard"][:10]:
        print(f"  #{a['rank']} {a['name']:20s} ${a['bankroll']:>8.2f}  ROI={a['roi_pct']:>+7.1f}%  bets={a['total_bets']:>4}  W%={a['win_rate']:.0f}%  LLM={a['llm_ok']}/{a['llm_calls']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
