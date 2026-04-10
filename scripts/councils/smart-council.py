#!/usr/bin/env python3
"""
Smart Council — Real Executing AI Councils
==========================================
Replaces the dead monitor-only councils with councils that actually DO things.

Each council cycle:
  1. SCAN  — read current state from data files, git, HF spaces
  2. ASK   — send structured context to free LLM (Cerebras/Groq/OpenRouter)
  3. PARSE — extract a concrete JSON action from the LLM response
  4. ACT   — execute the action (HF API call, file write, script run, etc.)
  5. LOG   — append full record to data/councils/<project>-<dept>.jsonl

Usage:
    python3 smart-council.py --project nba --dept evolution
    python3 smart-council.py --project nba --dept evolution --execute
    python3 smart-council.py --project nba --dept research --dry-run
    python3 smart-council.py --list-actions
    python3 smart-council.py --run-all --execute

Safety:
    --dry-run (default) — print the action, don't execute
    --execute           — actually run the action
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import ssl
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─── Paths ───────────────────────────────────────────────────────────────────

ROOT = Path("/home/termius/mon-ipad")
DATA_DIR = ROOT / "data"
COUNCILS_DIR = DATA_DIR / "councils"
PROPOSALS_DIR = DATA_DIR / "research-proposals"
DEPARTMENTS_DIR = DATA_DIR / "departments"
AGENTS_DIR = ROOT / "scripts" / "agents"
ENV_FILE = ROOT / ".env.local"

COUNCILS_DIR.mkdir(parents=True, exist_ok=True)
PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

# ─── Load .env.local ─────────────────────────────────────────────────────────

def _load_env():
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))

_load_env()

# ─── Island definitions ───────────────────────────────────────────────────────

ISLANDS = {
    "S10": {"url": "nomos42-nba-quant",   "role": "exploitation",          "mut": 0.09, "feat": 63,  "model": None},
    "S11": {"url": "nomos42-nba-quant-2", "role": "exploration",           "mut": 0.15, "feat": 80,  "model": None},
    "S12": {"url": "nomos42-nba-evo-3",   "role": "extra_trees_specialist","mut": 0.08, "feat": 60,  "model": "extra_trees"},
    "S13": {"url": "nomos42-nba-evo-4",   "role": "catboost_specialist",   "mut": 0.10, "feat": 66,  "model": "catboost"},
    "S14": {"url": "nomos42-nba-evo-5",   "role": "lightgbm_specialist",   "mut": 0.08, "feat": 55,  "model": "lightgbm"},
    "S15": {"url": "nomos42-nba-evo-6",   "role": "wide_search",           "mut": 0.18, "feat": 80,  "model": None},
}

# ─── LLM Backend (reusing free-models-integration logic inline) ───────────────

PROVIDER_URLS = {
    "cerebras":   "https://api.cerebras.ai/v1/chat/completions",
    "groq":       "https://api.groq.com/openai/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
}

MODELS = {
    "qwen":    ("cerebras",   "qwen-3-235b-a22b-instruct-2507"),
    "qwen32b": ("cerebras",   "qwen-3-32b"),
    "llama8b": ("groq",       "llama-3.1-8b-instant"),
    "llama4":  ("groq",       "meta-llama/llama-4-scout-17b-16e-instruct"),
    "gemma3":  ("openrouter", "google/gemma-3-27b-it:free"),
    "mistral": ("openrouter", "mistralai/mistral-small-3.1-24b-instruct:free"),
    "deepseek":("openrouter", "deepseek/deepseek-r1:free"),
}

_last_call: Dict[str, float] = {}

def _get_token(provider: str) -> str:
    env_map = {
        "cerebras":   "CEREBRAS_API_KEY",
        "groq":       "GROQ_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    return os.environ.get(env_map.get(provider, ""), "").strip()

def _ssl():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def _call_llm(provider: str, model_id: str, prompt: str, max_tokens: int = 800,
               temperature: float = 0.2) -> str:
    token = _get_token(provider)
    if not token:
        return ""
    # Rate-limit per token
    now = time.time()
    wait = 2.0 - (now - _last_call.get(token, 0))
    if wait > 0:
        time.sleep(wait)
    _last_call[token] = time.time()

    url = PROVIDER_URLS[provider]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "Nomos42-SmartCouncil/2.0",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://nomos42.com"
        headers["X-Title"] = "Nomos42 Smart Council"

    payload = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }).encode()

    try:
        req = urllib.request.Request(url, data=payload, method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=60, context=_ssl()) as resp:
            result = json.loads(resp.read())
            choices = result.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        pass
    return ""

def query_llm(prompt: str, model: str = "qwen", max_tokens: int = 800) -> str:
    """Query LLM with automatic provider fallback."""
    # Try requested model first
    if model in MODELS:
        provider, model_id = MODELS[model]
        result = _call_llm(provider, model_id, prompt, max_tokens)
        if result:
            return result

    # Auto-fallback chain
    fallback_chain = ["qwen", "llama8b", "gemma3", "qwen32b", "mistral"]
    for alias in fallback_chain:
        if alias == model:
            continue
        if alias not in MODELS:
            continue
        prov, mid = MODELS[alias]
        result = _call_llm(prov, mid, prompt, max_tokens)
        if result:
            return result

    return ""

def extract_json_from_response(text: str) -> Optional[dict]:
    """Extract the first JSON object from an LLM response."""
    if not text:
        return None
    # Try direct parse first
    try:
        return json.loads(text)
    except Exception:
        pass
    # Try to find JSON block between ```json ... ```
    import re
    for pattern in [r"```json\s*([\s\S]+?)\s*```", r"```\s*([\s\S]+?)\s*```", r"(\{[\s\S]+\})"]:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
    return None

# ─── Data readers ─────────────────────────────────────────────────────────────

def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default if default is not None else {}

def read_jsonl_last(path: Path, n: int = 5) -> List[dict]:
    if not path.exists():
        return []
    lines = path.read_text().strip().splitlines()
    results = []
    for line in lines[-n:]:
        try:
            results.append(json.loads(line))
        except Exception:
            pass
    return results

def get_fleet_state() -> dict:
    health = read_json(DATA_DIR / "agent-health.json")
    return health.get("projects", {}).get("nba", {}).get("spaces", {})

def get_git_log(n: int = 10) -> str:
    try:
        result = subprocess.run(
            ["git", "log", f"--oneline", f"-{n}"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception:
        return ""

def get_disk_usage() -> dict:
    try:
        result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().splitlines()
        if len(lines) >= 2:
            parts = lines[1].split()
            return {"total": parts[1], "used": parts[2], "avail": parts[3], "pct": parts[4]}
    except Exception:
        pass
    return {}

def hf_get_status(space_url: str) -> dict:
    """Fetch /api/status from a HF space."""
    url = f"https://{space_url}.hf.space/api/status"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Nomos42-Council/2.0"})
        with urllib.request.urlopen(req, timeout=15, context=_ssl()) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}

def hf_post_config(space_url: str, params: dict) -> dict:
    url = f"https://{space_url}.hf.space/api/config"
    try:
        data = json.dumps(params).encode()
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "Nomos42-Council/2.0"}
        )
        with urllib.request.urlopen(req, timeout=15, context=_ssl()) as resp:
            return {"success": True, "result": json.loads(resp.read())}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}

def hf_post_command(space_url: str, command: str) -> dict:
    url = f"https://{space_url}.hf.space/api/command"
    try:
        data = json.dumps({"command": command}).encode()
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "Nomos42-Council/2.0"}
        )
        with urllib.request.urlopen(req, timeout=15, context=_ssl()) as resp:
            return {"success": True, "result": json.loads(resp.read())}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}

# ─── Action Executor ──────────────────────────────────────────────────────────

def execute_action(action: dict, dry_run: bool = True) -> dict:
    """
    Execute a concrete action. Returns {"success": bool, "detail": str}.

    Supported actions:
      tune_mutation_rate   → POST /api/config to a HF space
      cross_pollinate      → run scripts/agents/cross-pollinate.py
      diversify_island     → POST /api/command diversify to a space
      restart_island       → POST /api/command restart to a space
      write_proposal       → write JSON to data/research-proposals/
      flag_issue           → write warning to data/councils/issues.jsonl
      run_script           → run an arbitrary script (whitelist only)
      post_hf_config       → POST arbitrary config to a space
      write_dept_metric    → append metric to data/departments/<dept>/metrics.jsonl
      noop                 → do nothing (LLM said no action needed)
    """
    action_type = action.get("action", "noop")
    ts = datetime.now(timezone.utc).isoformat()

    if dry_run:
        return {"success": True, "dry_run": True, "detail": f"[DRY-RUN] Would execute: {json.dumps(action)}"}

    # ── tune_mutation_rate ─────────────────────────────────────────────
    if action_type == "tune_mutation_rate":
        island_id = action.get("island", "S10")
        new_rate = float(action.get("value", 0.10))
        # Cap at 0.15 per CLAUDE.md rule
        new_rate = min(new_rate, 0.15)
        island_cfg = ISLANDS.get(island_id, {})
        space_url = island_cfg.get("url", "")
        if not space_url:
            return {"success": False, "detail": f"Unknown island {island_id}"}
        result = hf_post_config(space_url, {"mutation_rate": new_rate})
        return {"success": result.get("success", False), "detail": json.dumps(result)}

    # ── cross_pollinate ────────────────────────────────────────────────
    elif action_type == "cross_pollinate":
        script = AGENTS_DIR / "cross-pollinate.py"
        if not script.exists():
            return {"success": False, "detail": f"Script not found: {script}"}
        try:
            result = subprocess.run(
                [sys.executable, str(script)],
                cwd=str(ROOT), capture_output=True, text=True, timeout=120
            )
            return {"success": result.returncode == 0, "detail": result.stdout[-500:] + result.stderr[-200:]}
        except Exception as e:
            return {"success": False, "detail": str(e)}

    # ── diversify_island ───────────────────────────────────────────────
    elif action_type == "diversify_island":
        island_id = action.get("island", "S10")
        island_cfg = ISLANDS.get(island_id, {})
        space_url = island_cfg.get("url", "")
        if not space_url:
            return {"success": False, "detail": f"Unknown island {island_id}"}
        result = hf_post_command(space_url, "diversify")
        return {"success": result.get("success", False), "detail": json.dumps(result)}

    # ── restart_island ────────────────────────────────────────────────
    elif action_type == "restart_island":
        island_id = action.get("island", "S10")
        island_cfg = ISLANDS.get(island_id, {})
        space_url = island_cfg.get("url", "")
        if not space_url:
            return {"success": False, "detail": f"Unknown island {island_id}"}
        result = hf_post_command(space_url, "restart")
        return {"success": result.get("success", False), "detail": json.dumps(result)}

    # ── post_hf_config ─────────────────────────────────────────────────
    elif action_type == "post_hf_config":
        island_id = action.get("island", "S10")
        params = action.get("params", {})
        island_cfg = ISLANDS.get(island_id, {})
        space_url = island_cfg.get("url", "")
        if not space_url:
            return {"success": False, "detail": f"Unknown island {island_id}"}
        # Safety: cap mutation_rate
        if "mutation_rate" in params:
            params["mutation_rate"] = min(float(params["mutation_rate"]), 0.15)
        result = hf_post_config(space_url, params)
        return {"success": result.get("success", False), "detail": json.dumps(result)}

    # ── write_proposal ────────────────────────────────────────────────
    elif action_type == "write_proposal":
        title = action.get("title", "Untitled Proposal")
        content = action.get("content", {})
        slug = title.lower().replace(" ", "-").replace("/", "-")[:50]
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = PROPOSALS_DIR / f"{date}-{slug}.json"
        proposal = {
            "title": title,
            "date": ts,
            "source": "smart-council",
            "dept": action.get("dept", "research"),
            "content": content,
            "reason": action.get("reason", ""),
            "priority": action.get("priority", 2),
        }
        filename.write_text(json.dumps(proposal, indent=2))
        return {"success": True, "detail": f"Written to {filename}"}

    # ── write_dept_metric ──────────────────────────────────────────────
    elif action_type == "write_dept_metric":
        dept = action.get("dept", "unknown")
        metric = action.get("metric", {})
        metric["ts"] = ts
        metrics_dir = DEPARTMENTS_DIR / dept
        metrics_dir.mkdir(parents=True, exist_ok=True)
        metrics_file = metrics_dir / "metrics.jsonl"
        with open(metrics_file, "a") as f:
            f.write(json.dumps(metric) + "\n")
        return {"success": True, "detail": f"Metric written to {metrics_file}"}

    # ── flag_issue ────────────────────────────────────────────────────
    elif action_type == "flag_issue":
        issue = {
            "ts": ts,
            "severity": action.get("severity", "WARNING"),
            "dept": action.get("dept", "unknown"),
            "message": action.get("message", ""),
            "data": action.get("data", {}),
        }
        issues_file = COUNCILS_DIR / "issues.jsonl"
        with open(issues_file, "a") as f:
            f.write(json.dumps(issue) + "\n")
        return {"success": True, "detail": f"Issue logged: {issue['message'][:100]}"}

    # ── run_script ────────────────────────────────────────────────────
    elif action_type == "run_script":
        # Whitelist only — never exec arbitrary shell
        ALLOWED_SCRIPTS = {
            "cross-pollinate": AGENTS_DIR / "cross-pollinate.py",
            "diversity-injector": AGENTS_DIR / "diversity-injector.py",
            "keepalive": ROOT / "scripts" / "keepalive-spaces.sh",
        }
        script_name = action.get("script", "")
        script_path = ALLOWED_SCRIPTS.get(script_name)
        if not script_path:
            return {"success": False, "detail": f"Script '{script_name}' not in whitelist: {list(ALLOWED_SCRIPTS.keys())}"}
        if not script_path.exists():
            return {"success": False, "detail": f"Script not found: {script_path}"}
        try:
            cmd = [sys.executable, str(script_path)] if str(script_path).endswith(".py") else ["bash", str(script_path)]
            result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=120)
            return {"success": result.returncode == 0, "detail": result.stdout[-400:] + result.stderr[-200:]}
        except Exception as e:
            return {"success": False, "detail": str(e)}

    # ── noop ──────────────────────────────────────────────────────────
    elif action_type == "noop":
        return {"success": True, "detail": f"No action needed: {action.get('reason', '')}"}

    else:
        return {"success": False, "detail": f"Unknown action type: {action_type}"}


# ─── Department Scanners ──────────────────────────────────────────────────────

def scan_nba_evolution() -> dict:
    spaces = get_fleet_state()
    best_brier = min((v.get("brier", 1.0) for v in spaces.values() if v.get("brier")), default=None)
    fleet_avg = None
    if spaces:
        briers = [v.get("brier", 1.0) for v in spaces.values() if v.get("brier")]
        fleet_avg = round(sum(briers) / len(briers), 5) if briers else None
    stagnant = {sid: v.get("stagnation_cycles", 0) for sid, v in spaces.items() if v.get("stagnation_cycles", 0) > 10}
    models = {sid: v.get("model", "?") for sid, v in spaces.items()}
    generations = {sid: v.get("generation", 0) for sid, v in spaces.items()}
    prev_output = read_json(DEPARTMENTS_DIR / "evolution" / "karpathy-output.json")
    return {
        "atr": 0.21570,  # All-time record
        "target": 0.200,
        "best_brier": best_brier,
        "fleet_avg_brier": fleet_avg,
        "spaces": spaces,
        "stagnant_islands": stagnant,
        "models": models,
        "generations": generations,
        "prev_recommendations": prev_output.get("recommendations", [])[:3],
        "diversity_score": prev_output.get("diversity_score", None),
    }

def scan_nba_research() -> dict:
    prev_output = read_json(DEPARTMENTS_DIR / "research" / "karpathy-output.json")
    prev_proposals = sorted(PROPOSALS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:3]
    recent_proposals = []
    for p in prev_proposals:
        d = read_json(p)
        if not isinstance(d, dict):
            d = {}
        recent_proposals.append({"title": d.get("title", p.name), "date": d.get("date", d.get("created_at", ""))})
    return {
        "atr": 0.21570,
        "target": 0.200,
        "sota": "Montrucchio 2026 — 0.199 via shot-chart CNN + MC dropout + RNN temporal",
        "current_gap": round(0.21570 - 0.200, 5),
        "papers_scanned": prev_output.get("papers_scanned", 0),
        "techniques_extracted": prev_output.get("techniques_extracted", 0),
        "recent_proposals": recent_proposals,
        "open_questions": [
            "TabICLv2 upgrade from TabICL — potential -0.005 Brier",
            "Venn-Abers calibration — proven ECE reduction",
            "Referee-foul signal (Cat47+) — unexploited alpha",
        ],
    }

def scan_nba_engineering() -> dict:
    eng_output = read_json(DEPARTMENTS_DIR / "engineering" / "karpathy-output.json")
    bug_fixes = read_json(DEPARTMENTS_DIR / "engineering" / "bug-fixes.json", default=[])
    spaces = get_fleet_state()
    best_brier = min((v.get("brier", 1.0) for v in spaces.values() if v.get("brier")), default=None)
    recent_git = get_git_log(5)
    return {
        "atr": 0.21570,
        "current_best_brier": best_brier,
        "feature_engine_version": "v3.1-46cat",
        "feature_count": 6253,
        "max_features": 200,
        "recent_commits": recent_git,
        "recent_bug_fixes": bug_fixes[-3:] if isinstance(bug_fixes, list) else [],
        "known_issues": eng_output.get("issues", [])[:3] if eng_output else [],
    }

def scan_nba_evaluation() -> dict:
    spaces = get_fleet_state()
    briers = {sid: v.get("brier", None) for sid, v in spaces.items()}
    calibration_file = DATA_DIR / "calibration"
    cal_files = sorted(calibration_file.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if calibration_file.exists() else []
    latest_cal = read_json(cal_files[0]) if cal_files else {}
    return {
        "atr": 0.21570,
        "target_brier": 0.200,
        "fleet_briers": briers,
        "calibration": {
            "latest_file": cal_files[0].name if cal_files else None,
            "ece": latest_cal.get("ece", None),
            "sharpness": latest_cal.get("sharpness", None),
        },
        "backtest_sharpe": None,  # From bankroll state if available
        "known_issues": [
            "Walk-forward avg 0.22447 vs fleet best 0.221 — gap suggests overfitting on HF spaces",
        ],
    }

def scan_nba_infra() -> dict:
    spaces = get_fleet_state()
    all_up = all(v.get("status") == "UP" for v in spaces.values())
    down_spaces = [sid for sid, v in spaces.items() if v.get("status") != "UP"]
    disk = get_disk_usage()
    infra_status = read_json(DATA_DIR / "infra-status.json")
    return {
        "spaces_total": len(spaces),
        "spaces_up": sum(1 for v in spaces.values() if v.get("status") == "UP"),
        "all_up": all_up,
        "down_spaces": down_spaces,
        "disk": disk,
        "vm_ram_mb": 969,
        "vm_vcpu": 1,
        "infra_status": infra_status,
        "critical_rule": "ZERO ML on VM — all training on HF Spaces",
    }

def scan_political() -> dict:
    health = read_json(DATA_DIR / "agent-health.json")
    political = health.get("projects", {}).get("political", {})
    trader_states = {}
    for t in ["political-claude-state", "political-grok-state", "political-gemini-state"]:
        f = DATA_DIR / "arena" / "traders" / f"{t}.json"
        if f.exists():
            d = read_json(f)
            trader_states[t.replace("-state", "")] = {
                "portfolio_value": d.get("portfolio_value", None),
                "cash": d.get("cash", None),
                "roi": d.get("roi_pct", None),
            }
    return {
        "feature_engine": "v3.1-22cat",
        "categories": 22,
        "features": 743,
        "kaggle_status": political.get("kaggle", {}),
        "trader_states": trader_states,
    }

def scan_cross_repo() -> dict:
    cross_health = read_json(DATA_DIR / "cross-repo-health.json")
    return {
        "repos_monitored": 5,
        "health": cross_health,
        "parity_rule": "features/engine.py must be identical across all HF spaces",
        "git_log": get_git_log(5),
    }

def scan_business() -> dict:
    return {
        "pricing_tiers": [
            {"name": "Starter", "price": 19, "target": "casual bettors"},
            {"name": "Pro", "price": 49, "target": "serious bettors"},
            {"name": "Elite", "price": 149, "target": "professional traders"},
        ],
        "current_users": 1,  # Pierre = first user
        "mrr": 0,
        "target_mrr": 1000,
        "channels": ["Telegram @Nomos42Bot", "Dashboard nomos-dashboard"],
        "conversion_levers": ["free predictions", "bankroll tracking", "value bet alerts"],
    }

def scan_finance() -> dict:
    bankroll_file = DATA_DIR / "nba-agent" / "bankroll-state.json"
    bankroll = read_json(bankroll_file) if bankroll_file.exists() else {}
    return {
        "bankroll": bankroll,
        "api_cost_estimate": {
            "cerebras": "$0/day (1M tokens free)",
            "groq": "$0/day (14400 RPD free)",
            "openrouter": "$0/day (200 RPD free)",
            "hf_spaces": "$0/month (free tier, 6 spaces)",
            "vercel": "$0/month (hobby plan)",
        },
        "monthly_burn": 0,
        "note": "Currently fully free stack — no API costs",
    }


# ─── Department Registry ──────────────────────────────────────────────────────

DEPT_REGISTRY = {
    # project → dept → {scanner, prompt_builder, valid_actions}
    "nba": {
        "evolution": {
            "scanner": scan_nba_evolution,
            "model": "qwen",
            "valid_actions": ["tune_mutation_rate", "cross_pollinate", "diversify_island",
                              "restart_island", "post_hf_config", "write_proposal", "flag_issue", "noop"],
            "prompt_template": """\
You are the Evolution Council for Nomos42, an NBA prediction AI system.
Your job: analyze the current evolution fleet state and return ONE concrete action.

CONTEXT:
{context}

AVAILABLE ACTIONS (return exactly ONE as JSON):
  {{"action": "tune_mutation_rate", "island": "S10", "value": 0.12, "reason": "..."}}
  {{"action": "cross_pollinate", "reason": "..."}}
  {{"action": "diversify_island", "island": "S12", "reason": "..."}}
  {{"action": "post_hf_config", "island": "S15", "params": {{"mutation_rate": 0.12, "n_features": 80}}, "reason": "..."}}
  {{"action": "write_proposal", "title": "Try XYZ technique", "content": {{"technique": "...", "expected_brier_delta": -0.003}}, "reason": "..."}}
  {{"action": "flag_issue", "severity": "WARNING", "message": "...", "reason": "..."}}
  {{"action": "noop", "reason": "Fleet is healthy, no action needed"}}

RULES:
- mutation_rate cap = 0.15 (hard limit per CLAUDE.md)
- MAX_FEATURES = 200 (never exceed)
- ZERO ML on VM — all config changes go to HF spaces via API
- Lower Brier = better (target < 0.200, ATR = 0.21570)

Return ONLY valid JSON. No markdown, no explanation outside the JSON.
""",
        },
        "research": {
            "scanner": scan_nba_research,
            "model": "qwen",
            "valid_actions": ["write_proposal", "flag_issue", "noop"],
            "prompt_template": """\
You are the Research Council for Nomos42, an NBA prediction AI system.
Your job: identify the SINGLE highest-value research action to close the gap from 0.21570 to <0.20 Brier.

CONTEXT:
{context}

AVAILABLE ACTIONS (return exactly ONE as JSON):
  {{"action": "write_proposal", "title": "...", "dept": "research", "priority": 1,
    "content": {{"technique": "...", "paper": "...", "expected_brier_delta": -0.003,
    "implementation_steps": ["step1", "step2"]}}, "reason": "..."}}
  {{"action": "flag_issue", "severity": "INFO", "message": "...", "data": {{}}, "reason": "..."}}
  {{"action": "noop", "reason": "No new research action needed right now"}}

FOCUS ON:
- Concrete techniques that can be tested on HF Spaces (CPU, tree-based, no neural nets on spaces)
- GPU techniques for Kaggle/Colab loops
- Calibration improvements (ECE, Venn-Abers)
- Feature engineering from play-by-play, referee, shot chart data

Return ONLY valid JSON. No markdown, no explanation outside the JSON.
""",
        },
        "engineering": {
            "scanner": scan_nba_engineering,
            "model": "qwen",
            "valid_actions": ["write_proposal", "flag_issue", "noop"],
            "prompt_template": """\
You are the Engineering Council for Nomos42, an NBA prediction AI.
Your job: identify the highest-priority engineering improvement.

CONTEXT:
{context}

AVAILABLE ACTIONS (return exactly ONE as JSON):
  {{"action": "write_proposal", "title": "...", "dept": "engineering", "priority": 1,
    "content": {{"change": "...", "file": "...", "expected_impact": "..."}}, "reason": "..."}}
  {{"action": "flag_issue", "severity": "ERROR|WARNING|INFO", "message": "...", "data": {{}}, "reason": "..."}}
  {{"action": "noop", "reason": "Engineering is in good shape"}}

RULES:
- ZERO ML on VM (1 vCPU / 969 MB RAM)
- Feature engine parity: features/engine.py must match across all HF spaces
- All training on HF Spaces or Kaggle/Colab

Return ONLY valid JSON.
""",
        },
        "evaluation": {
            "scanner": scan_nba_evaluation,
            "model": "llama4",
            "valid_actions": ["flag_issue", "write_proposal", "noop"],
            "prompt_template": """\
You are the Evaluation Council for Nomos42. Your job: audit prediction quality and flag regressions.

CONTEXT:
{context}

AVAILABLE ACTIONS (return exactly ONE as JSON):
  {{"action": "flag_issue", "severity": "ERROR|WARNING|INFO", "message": "...",
    "dept": "evaluation", "data": {{}}, "reason": "..."}}
  {{"action": "write_proposal", "title": "...", "dept": "evaluation", "priority": 1,
    "content": {{"issue": "...", "fix": "..."}}, "reason": "..."}}
  {{"action": "noop", "reason": "Metrics look healthy"}}

WATCH FOR:
- Brier regression vs ATR 0.21570
- Walk-forward validation degradation
- Calibration drift (ECE increasing)
- Systematic over/under-confidence

Return ONLY valid JSON.
""",
        },
        "infra": {
            "scanner": scan_nba_infra,
            "model": "llama8b",
            "valid_actions": ["restart_island", "flag_issue", "run_script", "noop"],
            "prompt_template": """\
You are the Infra Council for Nomos42. Your job: keep 6 HF Spaces running 24/7.

CONTEXT:
{context}

AVAILABLE ACTIONS (return exactly ONE as JSON):
  {{"action": "restart_island", "island": "S10", "reason": "..."}}
  {{"action": "flag_issue", "severity": "ERROR|WARNING|INFO", "message": "...", "reason": "..."}}
  {{"action": "run_script", "script": "keepalive", "reason": "..."}}
  {{"action": "noop", "reason": "All 6 spaces are UP, infra healthy"}}

PRIORITY: Keep all 6 spaces UP. If any are down, restart immediately.
VM has only 1 vCPU / 969 MB RAM — never recommend ML on VM.

Return ONLY valid JSON.
""",
        },
    },
    "political": {
        "political": {
            "scanner": scan_political,
            "model": "qwen",
            "valid_actions": ["write_proposal", "flag_issue", "noop"],
            "prompt_template": """\
You are the Political Alpha Council for Nomos42. Monitor the political AI traders and signal quality.

CONTEXT:
{context}

AVAILABLE ACTIONS (return exactly ONE as JSON):
  {{"action": "write_proposal", "title": "...", "dept": "political", "priority": 1,
    "content": {{"signal": "...", "category": "...", "expected_alpha": "..."}}, "reason": "..."}}
  {{"action": "flag_issue", "severity": "WARNING|INFO", "message": "...", "reason": "..."}}
  {{"action": "noop", "reason": "Political alpha system is running normally"}}

Return ONLY valid JSON.
""",
        },
    },
    "cross_repo": {
        "cross_repo": {
            "scanner": scan_cross_repo,
            "model": "qwen",
            "valid_actions": ["flag_issue", "write_proposal", "noop"],
            "prompt_template": """\
You are the Cross-Repo Audit Council for Nomos42. Monitor consistency across all 5 repos.

CONTEXT:
{context}

AVAILABLE ACTIONS (return exactly ONE as JSON):
  {{"action": "flag_issue", "severity": "ERROR|WARNING|INFO", "message": "...",
    "dept": "cross_repo", "data": {{}}, "reason": "..."}}
  {{"action": "write_proposal", "title": "...", "dept": "cross_repo",
    "content": {{"repo": "...", "issue": "...", "fix": "..."}}, "reason": "..."}}
  {{"action": "noop", "reason": "All repos in sync"}}

CRITICAL CHECKS:
- features/engine.py parity across all HF spaces
- CLAUDE.md version consistency
- Config drift in department-config.json

Return ONLY valid JSON.
""",
        },
    },
    "business": {
        "business": {
            "scanner": scan_business,
            "model": "gemma3",
            "valid_actions": ["write_proposal", "flag_issue", "noop"],
            "prompt_template": """\
You are the Business Council for Nomos42. Focus on user acquisition and MRR growth.

CONTEXT:
{context}

AVAILABLE ACTIONS (return exactly ONE as JSON):
  {{"action": "write_proposal", "title": "...", "dept": "business", "priority": 1,
    "content": {{"tactic": "...", "channel": "...", "expected_impact": "..."}}, "reason": "..."}}
  {{"action": "flag_issue", "severity": "WARNING|INFO", "message": "...", "reason": "..."}}
  {{"action": "noop", "reason": "Business development on track"}}

TARGET: First 10 paying users, $500 MRR.
CHANNELS: Telegram @Nomos42 channel, direct outreach to sports bettors.

Return ONLY valid JSON.
""",
        },
    },
    "finance": {
        "finance": {
            "scanner": scan_finance,
            "model": "llama8b",
            "valid_actions": ["flag_issue", "write_proposal", "noop"],
            "prompt_template": """\
You are the Finance Council for Nomos42. Track API costs, compute costs, and bankroll P&L.

CONTEXT:
{context}

AVAILABLE ACTIONS (return exactly ONE as JSON):
  {{"action": "flag_issue", "severity": "WARNING|INFO", "message": "...", "reason": "..."}}
  {{"action": "write_proposal", "title": "...", "dept": "finance",
    "content": {{"optimization": "...", "monthly_saving": "..."}}, "reason": "..."}}
  {{"action": "noop", "reason": "Costs are within budget"}}

Return ONLY valid JSON.
""",
        },
    },
}

# ─── Council Run ──────────────────────────────────────────────────────────────

def run_council(project: str, dept: str, dry_run: bool = True, model_override: str = None,
                verbose: bool = True) -> dict:
    """
    Run one council cycle: scan → ask LLM → parse action → execute → log.
    Returns the full council record.
    """
    ts = datetime.now(timezone.utc).isoformat()
    print(f"\n{'='*60}")
    print(f"[{ts[:19]}] COUNCIL: project={project} dept={dept} dry_run={dry_run}")
    print(f"{'='*60}")

    # Look up department config
    project_depts = DEPT_REGISTRY.get(project)
    if not project_depts:
        print(f"  ERROR: Unknown project '{project}'. Available: {list(DEPT_REGISTRY.keys())}")
        return {"error": f"Unknown project: {project}"}

    dept_cfg = project_depts.get(dept)
    if not dept_cfg:
        print(f"  ERROR: Unknown dept '{dept}' for project '{project}'. Available: {list(project_depts.keys())}")
        return {"error": f"Unknown dept: {dept}"}

    # 1. SCAN
    print(f"  [1/5] SCAN — gathering current state...")
    scanner = dept_cfg["scanner"]
    try:
        context = scanner()
    except Exception as e:
        print(f"  ERROR in scanner: {e}")
        context = {"scan_error": str(e)}

    if verbose:
        print(f"  Context keys: {list(context.keys())}")

    # 2. BUILD PROMPT
    print(f"  [2/5] BUILD PROMPT...")
    template = dept_cfg["prompt_template"]
    context_str = json.dumps(context, indent=None, separators=(", ", ": "))
    # Truncate if too long
    if len(context_str) > 3000:
        context_str = context_str[:3000] + "... (truncated)"
    prompt = template.replace("{context}", context_str)

    # 3. ASK LLM
    model = model_override or dept_cfg.get("model", "qwen")
    print(f"  [3/5] ASK LLM (model={model})...")
    raw_response = query_llm(prompt, model=model, max_tokens=600)

    if not raw_response:
        print(f"  WARNING: No LLM response. Falling back to noop.")
        raw_response = '{"action": "noop", "reason": "LLM unavailable — no API keys or rate limited"}'

    if verbose:
        print(f"  LLM raw response ({len(raw_response)} chars):")
        preview = raw_response[:400]
        for line in preview.splitlines():
            print(f"    {line}")
        if len(raw_response) > 400:
            print(f"    ... [{len(raw_response)-400} more chars]")

    # 4. PARSE ACTION
    print(f"  [4/5] PARSE ACTION...")
    action = extract_json_from_response(raw_response)

    if not action:
        print(f"  WARNING: Could not parse JSON action from response. Using noop.")
        action = {"action": "noop", "reason": "Could not parse LLM response as JSON"}

    action_type = action.get("action", "noop")
    print(f"  ACTION: {action_type} — {action.get('reason', '')[:100]}")

    # Validate action is in the allowed list
    if action_type not in dept_cfg.get("valid_actions", []) and action_type != "noop":
        print(f"  WARNING: Action '{action_type}' not in valid_actions for this dept. Converting to flag_issue.")
        action = {
            "action": "flag_issue",
            "severity": "WARNING",
            "dept": dept,
            "message": f"LLM proposed invalid action '{action_type}'",
            "data": {"original_action": action},
            "reason": "Action not in allowed list for this department",
        }

    # 5. EXECUTE
    print(f"  [5/5] EXECUTE (dry_run={dry_run})...")
    exec_result = execute_action(action, dry_run=dry_run)
    print(f"  Result: success={exec_result.get('success')} — {exec_result.get('detail', '')[:100]}")

    # 6. LOG
    record = {
        "ts": ts,
        "project": project,
        "dept": dept,
        "model": model,
        "dry_run": dry_run,
        "context_keys": list(context.keys()),
        "action": action,
        "exec_result": exec_result,
        "raw_response_len": len(raw_response),
        "raw_response_preview": raw_response[:200],
    }

    log_file = COUNCILS_DIR / f"{project}-{dept}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(record) + "\n")
    print(f"  Logged to: {log_file}")

    return record


def run_all_councils(dry_run: bool = True, projects: Optional[List[str]] = None) -> List[dict]:
    """Run all configured councils for all (or specified) projects."""
    results = []
    to_run = []

    for project, depts in DEPT_REGISTRY.items():
        if projects and project not in projects:
            continue
        for dept in depts:
            to_run.append((project, dept))

    print(f"\nRunning {len(to_run)} councils (dry_run={dry_run})...")
    for project, dept in to_run:
        try:
            record = run_council(project, dept, dry_run=dry_run)
            results.append(record)
            # Small delay to respect rate limits
            time.sleep(3)
        except Exception as e:
            print(f"  ERROR in council {project}/{dept}: {e}")
            results.append({"project": project, "dept": dept, "error": str(e)})

    return results


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Smart Council — Real Executing AI Councils",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run the evolution council (default — no changes made)
  python3 smart-council.py --project nba --dept evolution

  # Actually execute the action
  python3 smart-council.py --project nba --dept evolution --execute

  # Run all councils for the nba project
  python3 smart-council.py --project nba --run-all --execute

  # Run all councils for all projects
  python3 smart-council.py --run-all --execute

  # List all configured councils
  python3 smart-council.py --list

  # Override LLM model
  python3 smart-council.py --project nba --dept infra --model llama8b --execute
        """
    )
    parser.add_argument("--project", help="Project to run council for")
    parser.add_argument("--dept", help="Department to run council for")
    parser.add_argument("--execute", action="store_true", default=False,
                        help="Execute the action (default: dry-run only)")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Explicit dry-run (default behavior)")
    parser.add_argument("--run-all", action="store_true", default=False,
                        help="Run all councils (for --project or all projects)")
    parser.add_argument("--model", default=None,
                        help=f"Override LLM model. Available: {list(MODELS.keys())}")
    parser.add_argument("--quiet", action="store_true", default=False,
                        help="Suppress verbose output")
    parser.add_argument("--list", "--list-actions", action="store_true", default=False,
                        help="List all configured councils and their actions")
    parser.add_argument("--show-log", action="store_true", default=False,
                        help="Show last 3 log entries for the specified project/dept")

    args = parser.parse_args()

    # ── --list ──
    if args.list:
        print("\nConfigured Councils:")
        print(f"  {'project':15s}  {'dept':20s}  {'model':10s}  valid_actions")
        print(f"  {'-'*15}  {'-'*20}  {'-'*10}  {'-'*50}")
        for project, depts in DEPT_REGISTRY.items():
            for dept, cfg in depts.items():
                actions = ", ".join(cfg.get("valid_actions", []))
                print(f"  {project:15s}  {dept:20s}  {cfg.get('model','qwen'):10s}  {actions}")
        print(f"\nAvailable LLM models: {', '.join(MODELS.keys())}")
        return

    # ── --show-log ──
    if args.show_log:
        if not args.project or not args.dept:
            print("ERROR: --show-log requires --project and --dept")
            sys.exit(1)
        log_file = COUNCILS_DIR / f"{args.project}-{args.dept}.jsonl"
        entries = read_jsonl_last(log_file, 3)
        if not entries:
            print(f"No log entries found in {log_file}")
            return
        for e in entries:
            print(json.dumps(e, indent=2))
        return

    dry_run = not args.execute

    # ── --run-all ──
    if args.run_all:
        projects = [args.project] if args.project else None
        results = run_all_councils(dry_run=dry_run, projects=projects)
        print(f"\n{'='*60}")
        print(f"SUMMARY: {len(results)} councils run")
        success_count = sum(1 for r in results if r.get("exec_result", {}).get("success"))
        error_count = sum(1 for r in results if "error" in r)
        print(f"  Executed: {success_count} | Errors: {error_count}")
        action_summary = {}
        for r in results:
            a = r.get("action", {}).get("action", "unknown")
            action_summary[a] = action_summary.get(a, 0) + 1
        print(f"  Actions: {json.dumps(action_summary)}")
        return

    # ── Single council run ──
    if not args.project or not args.dept:
        parser.print_help()
        print("\nERROR: --project and --dept are required (or use --run-all)")
        sys.exit(1)

    record = run_council(
        project=args.project,
        dept=args.dept,
        dry_run=dry_run,
        model_override=args.model,
        verbose=not args.quiet,
    )

    if "error" in record:
        sys.exit(1)


if __name__ == "__main__":
    main()
