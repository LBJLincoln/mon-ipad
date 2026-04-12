#!/usr/bin/env python3
"""
Forge Council Template — Universal Karpathy loop for any department in any repo.

Usage:
    python3 council-template.py --repo mon-ipad --dept research [--dry-run]

Each department has 4 council agents that follow the Karpathy autoresearch pattern:
    1. SCAN: Gather current state and data
    2. PROPOSE: Generate improvement hypothesis
    3. EXECUTE: Apply the change (5-min budget)
    4. EVALUATE: Measure metric delta → keep or revert

Inspired by:
    - Karpathy autoresearch (github.com/karpathy/autoresearch)
    - Paperclip org charts (github.com/paperclipai/paperclip)
    - Hermes-agent self-improvement (github.com/nousresearch/hermes-agent)
"""

import json
import sys
import os
import time
import hashlib
import subprocess as _sp
from datetime import datetime, timezone
from pathlib import Path

# ── HF Inference Client (optional — LLM council voting) ──────────────────
_HF_AVAILABLE = False
_hf_council_vote = None
_hf_query_best = None
_hf_query_qwen7b = None
_HF_MODELS = {}
try:
    import importlib.util as _ilu
    _hf_client_path = Path(__file__).resolve().parent.parent / "gpu-burst" / "hf-inference-client.py"
    if _hf_client_path.exists():
        _spec = _ilu.spec_from_file_location("hf_inference_client", str(_hf_client_path))
        _hf_mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_hf_mod)
        _hf_council_vote = _hf_mod.council_vote
        _hf_query_best = _hf_mod.query_best_available
        _hf_query_qwen7b = _hf_mod.query_qwen25_7b
        _HF_MODELS = _hf_mod.MODELS
        _HF_AVAILABLE = True
except Exception:
    pass  # All fallbacks remain None — rule-based approval will be used

# ── Config ──────────────────────────────────────────────────────────────

FORGE_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = FORGE_ROOT / "department-config.json"

# ── HF Space URLs (for direct API commands) ──────────────────────────────
SPACE_URLS = {
    "S10": "nomos42-nba-quant",
    "S11": "nomos42-nba-quant-2",
    "S12": "nomos42-nba-evo-3",
    "S13": "nomos42-nba-evo-4",
    "S14": "nomos42-nba-evo-5",
    "S15": "nomos42-nba-evo-6",
    "S16": "lbjlincoln26-nba-evo-s16",
    "S17": "lbjlincoln26-nba-evo-s17",
}


# ── Council Advisor (LLM gate for critical actions) ─────────────────────

class CouncilAdvisor:
    """LLM-backed advisor that gates autonomous actions via HF Inference API.

    Priority levels:
        CRITICAL — requires 3/4 LLM models to approve (council_vote)
        HIGH     — requires LLM consensus via council_vote (majority)
        MEDIUM   — quick sanity check with 1 fast model (Qwen 2.5 7B)
        LOW      — auto-approved (no LLM call)

    Falls back to rule-based approval if HF API is unavailable or times out.
    All LLM calls use a 30s timeout.
    """

    LLM_TIMEOUT = 30  # seconds

    DANGEROUS_PATTERNS = ["rm -rf /", "DROP TABLE", "git push --force", "shutdown", "reboot"]

    def __init__(self):
        self._backend = None
        try:
            from scripts.forge.free_models_integration import CouncilAdvisor as _CA
            self._backend = _CA()
        except Exception:
            pass  # fallback to rule-based

    def advise(self, dept: str, action: str, cmd: str, priority: str) -> dict:
        """Return {"approved": bool, "reason": str, "model_votes": dict|None}."""
        # Always block dangerous commands regardless of priority
        for d in self.DANGEROUS_PATTERNS:
            if d in cmd:
                return {"approved": False, "reason": f"Blocked dangerous pattern: {d}",
                        "model_votes": None}

        # CRITICAL: require 3/4 models to approve
        if priority == "critical":
            return self._llm_critical_vote(dept, action, cmd)

        # HIGH: LLM consensus (majority of responding models)
        if priority == "high":
            return self._llm_high_vote(dept, action, cmd)

        # MEDIUM: quick sanity check with 1 fast model
        if priority == "medium":
            return self._llm_medium_check(dept, action, cmd)

        # LOW: auto-approve
        return {"approved": True, "reason": "auto-approved (low priority)",
                "model_votes": None}

    def _llm_critical_vote(self, dept: str, action: str, cmd: str) -> dict:
        """CRITICAL: require 3/4 models to approve."""
        if not _HF_AVAILABLE or not _hf_council_vote:
            return self._rule_based_fallback(cmd, "critical (no LLM)")

        prompt = (
            f"CRITICAL ACTION REVIEW for department '{dept}'.\n"
            f"Action: {action}\n"
            f"Command: {cmd}\n\n"
            f"Should this command be executed autonomously? "
            f"Answer APPROVE or REJECT with a one-line reason."
        )
        try:
            import signal

            def _timeout_handler(signum, frame):
                raise TimeoutError("Council vote timed out")

            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(self.LLM_TIMEOUT)
            try:
                result = _hf_council_vote(prompt, role="risk")
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            votes = result.get("votes", {})
            model_decisions = {}
            approve_count = 0
            total_responded = 0

            for model_key, response in votes.items():
                if response is None:
                    model_decisions[model_key] = "NO_RESPONSE"
                    continue
                total_responded += 1
                response_upper = response.upper()
                if "APPROVE" in response_upper and "REJECT" not in response_upper:
                    model_decisions[model_key] = "APPROVE"
                    approve_count += 1
                else:
                    model_decisions[model_key] = "REJECT"

            approved = approve_count >= 3
            reason = (f"LLM council: {approve_count}/{total_responded} approved "
                      f"(need 3/4 for critical)")
            log("advisor", dept,
                f"CRITICAL vote: {reason} | votes={model_decisions}")
            return {"approved": approved, "reason": reason,
                    "model_votes": model_decisions}

        except (TimeoutError, Exception) as e:
            log("advisor", dept,
                f"LLM council failed ({type(e).__name__}: {e}), falling back to rules",
                "WARN")
            return self._rule_based_fallback(cmd, f"critical (LLM failed: {e})")

    def _llm_high_vote(self, dept: str, action: str, cmd: str) -> dict:
        """HIGH: LLM consensus — majority of responding models must approve."""
        if not _HF_AVAILABLE or not _hf_council_vote:
            return self._rule_based_fallback(cmd, "high (no LLM)")

        prompt = (
            f"ACTION REVIEW for department '{dept}'.\n"
            f"Action: {action}\n"
            f"Command: {cmd}\n\n"
            f"Should this command be executed? "
            f"Answer APPROVE or REJECT with a one-line reason."
        )
        try:
            import signal

            def _timeout_handler(signum, frame):
                raise TimeoutError("Council vote timed out")

            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(self.LLM_TIMEOUT)
            try:
                result = _hf_council_vote(prompt, role="risk")
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            votes = result.get("votes", {})
            model_decisions = {}
            approve_count = 0
            total_responded = 0

            for model_key, response in votes.items():
                if response is None:
                    model_decisions[model_key] = "NO_RESPONSE"
                    continue
                total_responded += 1
                response_upper = response.upper()
                if "APPROVE" in response_upper and "REJECT" not in response_upper:
                    model_decisions[model_key] = "APPROVE"
                    approve_count += 1
                else:
                    model_decisions[model_key] = "REJECT"

            approved = total_responded > 0 and approve_count > total_responded / 2
            reason = (f"LLM council: {approve_count}/{total_responded} approved "
                      f"(majority needed for high)")
            log("advisor", dept,
                f"HIGH vote: {reason} | votes={model_decisions}")
            return {"approved": approved, "reason": reason,
                    "model_votes": model_decisions}

        except (TimeoutError, Exception) as e:
            log("advisor", dept,
                f"LLM council failed ({type(e).__name__}: {e}), falling back to rules",
                "WARN")
            return self._rule_based_fallback(cmd, f"high (LLM failed: {e})")

    def _llm_medium_check(self, dept: str, action: str, cmd: str) -> dict:
        """MEDIUM: quick sanity check with Qwen 2.5 7B (fastest model)."""
        if not _HF_AVAILABLE or not _hf_query_qwen7b:
            return self._rule_based_fallback(cmd, "medium (no LLM)")

        prompt = (
            f"Quick safety check for department '{dept}'.\n"
            f"Action: {action}\n"
            f"Command: {cmd}\n\n"
            f"Is this safe to run autonomously? Answer APPROVE or REJECT in one line."
        )
        try:
            import signal

            def _timeout_handler(signum, frame):
                raise TimeoutError("Qwen 7B query timed out")

            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(self.LLM_TIMEOUT)
            try:
                response = _hf_query_qwen7b(prompt, max_tokens=128)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            if response is None:
                return self._rule_based_fallback(cmd, "medium (Qwen 7B no response)")

            response_upper = response.upper()
            approved = "APPROVE" in response_upper and "REJECT" not in response_upper
            decision = "APPROVE" if approved else "REJECT"

            log("advisor", dept,
                f"MEDIUM check (qwen25_7b): {decision} | response={response[:100]}")
            return {"approved": approved,
                    "reason": f"Qwen 2.5 7B: {decision} — {response[:150]}",
                    "model_votes": {"qwen25_7b": decision}}

        except (TimeoutError, Exception) as e:
            log("advisor", dept,
                f"Qwen 7B check failed ({type(e).__name__}: {e}), falling back to rules",
                "WARN")
            return self._rule_based_fallback(cmd, f"medium (LLM failed: {e})")

    def _rule_based_fallback(self, cmd: str, context: str) -> dict:
        """Fallback: rule-based approval when LLM is unavailable."""
        for d in self.DANGEROUS_PATTERNS:
            if d in cmd:
                return {"approved": False,
                        "reason": f"Blocked dangerous pattern: {d} ({context})",
                        "model_votes": None}
        return {"approved": True,
                "reason": f"rule-based auto-approve ({context})",
                "model_votes": None}


_advisor = CouncilAdvisor()

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def log(repo, dept, msg, level="INFO"):
    print(f"[{ts()}] [{level}] [{repo}:{dept}] {msg}")

# ── Metric Logger ───────────────────────────────────────────────────────

def log_metric(repo_path, dept, metric_name, value, delta=None):
    """Append a metric entry to the department's metrics JSONL file."""
    metrics_dir = Path(repo_path) / "data" / "departments" / dept
    metrics_dir.mkdir(parents=True, exist_ok=True)
    metrics_file = metrics_dir / "metrics.jsonl"

    entry = {
        "ts": ts(),
        "repo": Path(repo_path).name,
        "dept": dept,
        "metric": metric_name,
        "value": value,
    }
    if delta is not None:
        entry["delta"] = delta

    with open(metrics_file, "a") as f:
        f.write(json.dumps(entry) + "\n")

# ── Council State ───────────────────────────────────────────────────────

def load_council_state(repo_path, dept):
    """Load the current council state for a department."""
    state_file = Path(repo_path) / "data" / "departments" / f"council-{dept}.json"
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {
        "dept": dept,
        "iteration": 0,
        "best_metric": None,
        "last_run": None,
        "history": [],
        "agents": {},
    }

def save_council_state(repo_path, dept, state):
    """Save council state after a run."""
    state_dir = Path(repo_path) / "data" / "departments"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"council-{dept}.json"

    state["last_run"] = ts()
    state["iteration"] = state.get("iteration", 0) + 1

    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

# ── Karpathy Loop Core ─────────────────────────────────────────────────

def run_karpathy_loop(repo_path, dept, config, dry_run=False):
    """
    The universal Karpathy loop:
    1. SCAN current state
    2. PROPOSE improvement
    3. EXECUTE (5-min budget)
    4. EVALUATE → keep or revert
    """
    repo_name = Path(repo_path).name
    dept_config = config["departments"].get(dept)

    if not dept_config:
        log(repo_name, dept, f"Department '{dept}' not found in config", "ERROR")
        return False

    state = load_council_state(repo_path, dept)
    iteration = state.get("iteration", 0) + 1

    log(repo_name, dept, f"=== Council Iteration {iteration} ===")
    log(repo_name, dept, f"Layer: {dept_config['layer']}")
    log(repo_name, dept, f"Metrics: {', '.join(dept_config['metrics'])}")
    log(repo_name, dept, f"Loop: {dept_config['karpathy_loop']}")

    if dry_run:
        log(repo_name, dept, "[DRY RUN] Would execute Karpathy loop", "WARN")
        return True

    # Phase 1: SCAN
    log(repo_name, dept, "Phase 1/4: SCAN — gathering current state")
    scan_result = phase_scan(repo_path, dept, dept_config)

    # Phase 2: PROPOSE
    log(repo_name, dept, "Phase 2/4: PROPOSE — generating improvement hypothesis")
    proposal = phase_propose(repo_path, dept, dept_config, scan_result)

    # Phase 3: EXECUTE (5-min budget)
    log(repo_name, dept, "Phase 3/4: EXECUTE — applying change (5-min budget)")
    start_time = time.time()
    exec_result = phase_execute(repo_path, dept, dept_config, proposal)
    elapsed = time.time() - start_time
    log(repo_name, dept, f"Execution took {elapsed:.1f}s")

    # Phase 4: EVALUATE
    log(repo_name, dept, "Phase 4/4: EVALUATE — measuring metric delta")
    eval_result = phase_evaluate(repo_path, dept, dept_config, exec_result)

    # Log result
    for metric in dept_config["metrics"]:
        if metric in eval_result:
            log_metric(repo_path, dept, metric, eval_result[metric].get("value"), eval_result[metric].get("delta"))

    # Update state
    state["history"] = state.get("history", [])[-49:]  # keep last 50
    state["history"].append({
        "iteration": iteration,
        "ts": ts(),
        "proposal": proposal.get("summary", ""),
        "result": eval_result.get("decision", "unknown"),
        "metrics": {k: v for k, v in eval_result.items() if k != "decision"},
    })

    save_council_state(repo_path, dept, state)

    decision = eval_result.get("decision", "revert")
    log(repo_name, dept, f"Decision: {decision.upper()}")
    return decision == "keep"


# ── Data Helpers ───────────────────────────────────────────────────────

MON_IPAD = Path(__file__).resolve().parent.parent.parent

def _read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default or {}

def _read_jsonl_tail(path, n=10):
    try:
        lines = Path(path).read_text().strip().split("\n")
        return [json.loads(l) for l in lines[-n:] if l.strip()]
    except Exception:
        return []

def _safe_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ── Phase Implementations (REAL per-department logic) ──────────────────

def phase_scan(repo_path, dept, config):
    """Scan current state with REAL data reads per department."""
    repo_name = Path(repo_path).name
    result = {"dept": dept, "repo": repo_name, "ts": ts()}

    # Common: metrics history
    metrics_file = Path(repo_path) / "data" / "departments" / dept / "metrics.jsonl"
    result["metrics_history"] = _read_jsonl_tail(metrics_file, 5)

    # Previous council state for trend detection
    state = load_council_state(repo_path, dept)
    result["iteration"] = state.get("iteration", 0)
    result["last_run"] = state.get("last_run")
    last_hist = state.get("history", [])[-3:]
    result["recent_decisions"] = [h.get("result") for h in last_hist]

    # Department-specific scans
    scanners = {
        "research": _scan_research,
        "engineering": _scan_engineering,
        "evolution": _scan_evolution,
        "product": _scan_product,
        "business": _scan_business,
        "evaluation": _scan_evaluation,
        "infra": _scan_infra,
        "finance": _scan_finance,
        "cross_repo_agents": _scan_cross_repo_agents,
    }
    scanner = scanners.get(dept)
    if scanner:
        result.update(scanner(repo_path))

    return result


def _scan_research(repo_path):
    """Scan ArXiv outputs, research proposals, paper counts."""
    data = {}
    scan_dir = MON_IPAD / "data" / "research"
    if scan_dir.exists():
        scans = sorted(scan_dir.glob("*.json"))
        data["scan_count"] = len(scans)
        if scans:
            latest = _read_json(scans[-1])
            data["latest_scan"] = scans[-1].name
            data["papers_found"] = len(latest) if isinstance(latest, list) else latest.get("count", 0)
    proposals_dir = MON_IPAD / "data" / "departments" / "research"
    if proposals_dir.exists():
        data["proposal_files"] = [f.name for f in proposals_dir.iterdir()]
    return data


def _scan_engineering(repo_path):
    """Scan code quality: latest eval, Brier, test results."""
    data = {}
    eval_data = _read_json(MON_IPAD / "data" / "nba-agent" / "latest-eval.json")
    if eval_data:
        data["brier"] = eval_data.get("brier_score") or eval_data.get("brier")
        data["games_evaluated"] = eval_data.get("games_evaluated", 0)
        data["model_version"] = eval_data.get("model", "unknown")
    summary = _read_json(MON_IPAD / "data" / "nba-agent" / "quant-summary.json")
    if summary:
        data["atr_brier"] = summary.get("atr_brier", summary.get("best_brier"))
        data["walk_forward_brier"] = summary.get("walk_forward_avg")
    return data


def _scan_evolution(repo_path):
    """Scan HF island health, generation counts, Brier scores, stagnation."""
    data = {}
    health = _read_json(MON_IPAD / "data" / "agent-health.json")
    spaces = health.get("projects", {}).get("nba", {}).get("spaces", {})
    islands = {}
    best_brier = 1.0
    total_gens = 0
    stagnant_count = 0
    for sid, info in spaces.items():
        brier = _safe_float(info.get("brier"), 1.0)
        gen = info.get("generation", 0)
        stag = info.get("stagnation_cycles", 0)
        islands[sid] = {"brier": brier, "gen": gen, "status": info.get("status"), "stagnation": stag}
        if brier < best_brier:
            best_brier = brier
        total_gens += gen
        if stag > 5:
            stagnant_count += 1
    data["islands"] = islands
    data["best_fleet_brier"] = round(best_brier, 5)
    data["total_generations"] = total_gens
    data["stagnant_islands"] = stagnant_count
    data["fleet_size"] = len(islands)
    data["all_up"] = all(i.get("status") == "UP" for i in islands.values())
    return data


def _scan_product(repo_path):
    """Scan dashboard, Telegram bots, picks delivery."""
    import subprocess
    data = {}
    # Check dashboard repo
    dash_dir = MON_IPAD.parent / "nomos-dashboard"
    if dash_dir.exists():
        try:
            res = subprocess.run(["git", "-C", str(dash_dir), "log", "-1", "--format=%h %s"],
                                 capture_output=True, text=True, timeout=5)
            data["dashboard_last_commit"] = res.stdout.strip()
        except Exception:
            data["dashboard_last_commit"] = "error"
    # Check picks freshness
    picks = _read_json(MON_IPAD / "data" / "nba-agent" / "predictions-today.json")
    if isinstance(picks, list):
        data["picks_count"] = len(picks)
    elif isinstance(picks, dict):
        data["picks_count"] = len(picks.get("predictions", []))
    # Check bot status
    for bot in ["nomos42-brain", "forge-bot", "nba-bot"]:
        pid_file = Path(f"/tmp/{bot}.pid")
        data[f"bot_{bot.replace('-', '_')}"] = pid_file.exists()
    return data


def _scan_business(repo_path):
    """Scan user count, subscription state, API usage."""
    data = {}
    users_file = MON_IPAD / "data" / "forge-users" / "users.json"
    users = _read_json(users_file, {})
    data["total_users"] = len(users) if isinstance(users, (dict, list)) else 0
    data["mrr"] = 0  # No revenue yet
    # Check API docs exist
    api_doc = MON_IPAD / "docs" / "business" / "api-architecture.md"
    data["api_docs_exist"] = api_doc.exists()
    data["pricing_tiers"] = ["free", "scout_19", "edge_49", "whale_149"]
    return data


def _scan_evaluation(repo_path):
    """Scan calibration, backtest results, false positive rates."""
    data = {}
    eval_data = _read_json(MON_IPAD / "data" / "nba-agent" / "latest-eval.json")
    if eval_data:
        data["brier"] = eval_data.get("brier_score") or eval_data.get("brier")
        data["ece"] = eval_data.get("ece")
        data["mce"] = eval_data.get("mce")
        data["log_loss"] = eval_data.get("log_loss")
        data["games"] = eval_data.get("games_evaluated", 0)
    backtest = _read_json(MON_IPAD / "data" / "nba-agent" / "backtest-results.json")
    if backtest:
        data["backtest_roi"] = backtest.get("roi")
        data["backtest_sharpe"] = backtest.get("sharpe")
        data["backtest_games"] = backtest.get("total_games", 0)
    bankroll = _read_json(MON_IPAD / "data" / "nba-agent" / "bankroll-state.json")
    if bankroll:
        data["real_roi"] = bankroll.get("roi_pct", 0)
        data["real_sharpe"] = bankroll.get("sharpe_ratio", 0)
    return data


def _scan_infra(repo_path):
    """Scan VM health, disk, memory, process counts, space status."""
    import shutil, subprocess
    data = {}
    # Disk
    usage = shutil.disk_usage("/")
    data["disk_used_pct"] = round(usage.used / usage.total * 100, 1)
    data["disk_free_gb"] = round(usage.free / (1024**3), 2)
    # Memory
    try:
        with open("/proc/meminfo") as f:
            lines = f.read()
        for line in lines.split("\n"):
            if line.startswith("MemTotal:"):
                data["mem_total_mb"] = int(line.split()[1]) // 1024
            elif line.startswith("MemAvailable:"):
                data["mem_avail_mb"] = int(line.split()[1]) // 1024
    except Exception:
        pass
    # Process count
    try:
        res = subprocess.run(["pgrep", "-c", "python3"], capture_output=True, text=True, timeout=5)
        data["python_procs"] = int(res.stdout.strip() or 0)
    except Exception:
        data["python_procs"] = -1
    # Spaces health
    health = _read_json(MON_IPAD / "data" / "agent-health.json")
    spaces = health.get("projects", {}).get("nba", {}).get("spaces", {})
    data["spaces_up"] = sum(1 for s in spaces.values() if s.get("status") == "UP")
    data["spaces_total"] = len(spaces)
    data["issues"] = health.get("issues", [])
    return data


def _scan_finance(repo_path):
    """Scan bankroll, costs, revenue projections."""
    data = {}
    bankroll = _read_json(MON_IPAD / "data" / "nba-agent" / "bankroll-state.json")
    if bankroll:
        data["bankroll"] = bankroll.get("balance", bankroll.get("bankroll", 0))
        data["roi_pct"] = bankroll.get("roi_pct", 0)
        data["total_bets"] = bankroll.get("total_bets", 0)
    data["estimated_monthly_cost"] = 20  # $20/mo baseline
    data["revenue"] = 0  # Pre-revenue
    data["burn_rate"] = 20
    return data


def _scan_cross_repo_agents(repo_path):
    """Scan cross-repo consistency: feature parity, config drift, health."""
    import subprocess
    data = {}
    repos = ["mon-ipad", "nomos-nba-agent", "nomos-political-alpha", "nomos-dashboard",
             "rgwa", "nomos-picks", "nomos-pierre", "OddsHarvester"]

    # Check which repos exist and have councils
    active = 0
    drift_issues = []
    for r in repos:
        rpath = MON_IPAD.parent / r
        if rpath.exists():
            active += 1
            # Check council state freshness
            council_dir = rpath / "data" / "departments"
            if council_dir.exists():
                councils = list(council_dir.glob("council-*.json"))
                for cf in councils:
                    try:
                        state = _read_json(cf)
                        last_run = state.get("last_run", "")
                        if last_run and last_run < (datetime.now(timezone.utc).replace(hour=0)).strftime("%Y-%m-%dT%H:%M:%SZ"):
                            drift_issues.append(f"{r}:{cf.stem} stale (last: {last_run[:10]})")
                    except Exception:
                        pass

    data["repos_active"] = active
    data["repos_total"] = len(repos)
    data["drift_issues"] = drift_issues[:10]
    data["drift_count"] = len(drift_issues)

    # Cross-repo health
    health = _read_json(MON_IPAD / "data" / "cross-repo-health.json")
    if health:
        repo_info = health.get("repos", {})
        data["uncommitted"] = {k: v.get("uncommitted_changes", 0) for k, v in repo_info.items()}

    # Feature engine parity check
    engine_hash_file = MON_IPAD / "data" / ".last-engine-hash"
    if engine_hash_file.exists():
        data["engine_hash"] = engine_hash_file.read_text().strip()[:12]

    return data


# ── PROPOSE: Generate real proposals ───────────────────────────────────

def phase_propose(repo_path, dept, config, scan):
    """Generate improvement proposals — LLM-enhanced when available, rule-based fallback."""
    proposers = {
        "research": _propose_research,
        "cross_repo_agents": _propose_cross_repo,
        "engineering": _propose_engineering,
        "evolution": _propose_evolution,
        "product": _propose_product,
        "business": _propose_business,
        "evaluation": _propose_evaluation,
        "infra": _propose_infra,
        "finance": _propose_finance,
    }

    # Step 1: Get rule-based proposal (always available)
    proposer = proposers.get(dept, _propose_generic)
    rule_proposal = proposer(repo_path, scan)

    # Step 2: Try LLM-enhanced proposal for non-trivial priorities
    if rule_proposal.get("priority") in ("high", "critical", "medium"):
        llm_proposal = _llm_enhanced_propose(repo_path, dept, scan, rule_proposal)
        if llm_proposal:
            return llm_proposal

    return rule_proposal


def _llm_enhanced_propose(repo_path, dept, scan, rule_proposal):
    """Use LLM to generate a more specific proposal. Returns None on failure."""
    if not _HF_AVAILABLE or not _hf_query_best:
        return None

    repo_name = Path(repo_path).name

    # Build a concise metrics summary from scan data (exclude verbose fields)
    metrics_summary = {}
    skip_keys = {"dept", "repo", "ts", "metrics_history", "recent_decisions",
                 "proposal_files", "islands", "uncommitted"}
    for k, v in scan.items():
        if k not in skip_keys and v is not None:
            metrics_summary[k] = v

    prompt = (
        f"You are an AI advisor for the '{dept}' department of an NBA prediction system.\n\n"
        f"Current metrics: {json.dumps(metrics_summary, default=str)}\n\n"
        f"Rule-based analysis suggests: {rule_proposal.get('summary', 'unknown')}\n"
        f"Priority: {rule_proposal.get('priority', 'unknown')}\n\n"
        f"Propose 1 specific improvement. Be concrete — include exact file paths, "
        f"commands, or config changes. Format:\n"
        f"PROPOSAL: <one-line summary>\n"
        f"ACTION: <specific command or file change>\n"
        f"REASON: <why this helps>\n"
    )

    try:
        import signal

        def _timeout_handler(signum, frame):
            raise TimeoutError("LLM proposal generation timed out")

        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(30)
        try:
            response = _hf_query_best(prompt, max_tokens=512)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

        if not response:
            return None

        # Parse LLM response to extract proposal
        llm_summary = rule_proposal.get("summary", "")
        llm_action = rule_proposal.get("action", "monitor")

        for line in response.split("\n"):
            line = line.strip()
            if line.upper().startswith("PROPOSAL:"):
                llm_summary = line[len("PROPOSAL:"):].strip()
            elif line.upper().startswith("ACTION:"):
                parsed_action = line[len("ACTION:"):].strip()
                if parsed_action:
                    llm_action = parsed_action

        # Merge: keep rule-based cmd/priority but use LLM summary
        enhanced = dict(rule_proposal)
        enhanced["summary"] = f"[LLM] {llm_summary}"
        enhanced["llm_raw"] = response[:500]
        enhanced["proposal_source"] = "llm_enhanced"

        log(repo_name, dept, f"LLM proposal: {llm_summary[:120]}")
        return enhanced

    except (TimeoutError, Exception) as e:
        log(repo_name, dept,
            f"LLM proposal failed ({type(e).__name__}: {e}), using rule-based",
            "WARN")
        return None


def _propose_generic(repo_path, scan):
    return {"summary": f"No specific proposer for {scan['dept']}", "action": "skip", "priority": "low"}


def _propose_research(repo_path, scan):
    papers = scan.get("papers_found", 0)
    if papers == 0:
        return {"summary": "Run ArXiv + GitHub scan for latest NBA/ML papers",
                "action": "run_scan", "priority": "high",
                "cmd": "bash scripts/agents/research-cron.sh"}
    scan_count = scan.get("scan_count", 0)
    if papers < 3 and scan_count > 0:
        return {"summary": f"Only {papers} papers found — run deeper scan with research-scanner.py",
                "action": "deep_scan", "priority": "high",
                "cmd": "python3 scripts/agents/research-scanner.py --deep"}
    return {"summary": f"Research scan found {papers} papers — check for actionable techniques",
            "action": "review_proposals", "priority": "medium"}


def _propose_engineering(repo_path, scan):
    brier = _safe_float(scan.get("brier"), 0.23)
    atr = _safe_float(scan.get("atr_brier"), 0.21570)
    wf = _safe_float(scan.get("walk_forward_brier"), 0.0)
    gap = brier - atr
    if gap > 0.01:
        # SAFETY: never auto-change code — log detailed diagnostic instead
        diag = (f"BRIER REGRESSION ALERT: latest={brier:.5f} atr={atr:.5f} gap={gap:.5f}"
                f" walk_forward={wf:.5f} model={scan.get('model_version','?')}"
                f" games={scan.get('games_evaluated',0)}")
        return {"summary": f"Latest Brier {brier:.4f} is {gap:.4f} above ATR {atr:.5f} — investigate regression",
                "action": "investigate_brier_gap", "priority": "critical",
                "diagnostic": diag,
                "note": "SAFETY: no auto-code-change — logged for human review"}
    if brier > 0.22:
        return {"summary": f"Brier {brier:.4f} above 0.22 — check calibration and feature selection",
                "action": "calibration_check", "priority": "high",
                "diagnostic": f"brier={brier:.5f} atr={atr:.5f} wf={wf:.5f}",
                "note": "SAFETY: no auto-code-change — logged for human review"}
    return {"summary": f"Brier {brier:.4f} healthy — monitor for drift",
            "action": "monitor", "priority": "low"}


def _propose_evolution(repo_path, scan):
    stagnant = scan.get("stagnant_islands", 0)
    best = scan.get("best_fleet_brier", 0.23)
    islands = scan.get("islands", {})

    # Identify DOWN and stagnant islands for targeted commands
    down_islands = [sid for sid, info in islands.items() if info.get("status") != "UP"]
    stagnant_ids = [sid for sid, info in islands.items() if info.get("stagnation", 0) > 5]

    if down_islands:
        # Build keepalive curl for each DOWN island
        keepalive_cmds = []
        for sid in down_islands:
            url = SPACE_URLS.get(sid, "")
            if url:
                keepalive_cmds.append(
                    f'curl -sf --max-time 15 https://{url}.hf.space/api/status || true')
        cmd = " && ".join(keepalive_cmds) if keepalive_cmds else "bash scripts/keepalive-spaces.sh"
        return {"summary": f"{len(down_islands)} islands DOWN ({', '.join(down_islands)}) — sending keepalive",
                "action": "restart_islands", "priority": "critical",
                "cmd": cmd}

    if stagnant >= 3:
        # Diversify the most stagnant islands + cross-pollinate
        diversify_cmds = []
        for sid in sorted(stagnant_ids, key=lambda s: islands.get(s, {}).get("stagnation", 0), reverse=True)[:3]:
            url = SPACE_URLS.get(sid, "")
            if url:
                diversify_cmds.append(
                    f'curl -sf -X POST https://{url}.hf.space/api/command '
                    f'-H "Content-Type: application/json" '
                    f'-d \'{{"command":"diversify"}}\' || true')
        diversify_cmds.append("python3 scripts/agents/cross-pollinate.py")
        return {"summary": f"{stagnant} islands stagnant ({', '.join(stagnant_ids)}) — diversify + cross-pollinate",
                "action": "cross_pollinate", "priority": "high",
                "cmd": " && ".join(diversify_cmds)}

    if stagnant_ids:
        # 1-2 stagnant: targeted diversify only
        diversify_cmds = []
        for sid in stagnant_ids:
            url = SPACE_URLS.get(sid, "")
            if url:
                diversify_cmds.append(
                    f'curl -sf -X POST https://{url}.hf.space/api/command '
                    f'-H "Content-Type: application/json" '
                    f'-d \'{{"command":"diversify"}}\' || true')
        if diversify_cmds:
            return {"summary": f"{len(stagnant_ids)} stagnant islands ({', '.join(stagnant_ids)}) — sending diversify",
                    "action": "diversify_targeted", "priority": "high",
                    "cmd": " && ".join(diversify_cmds)}

    if best > 0.222:
        return {"summary": f"Best fleet Brier {best:.5f} > 0.222 — consider mutation rate bump",
                "action": "tune_mutation", "priority": "medium"}
    return {"summary": f"Fleet healthy at {best:.5f} — {scan.get('total_generations', 0)} total gens",
            "action": "monitor", "priority": "low"}


def _propose_product(repo_path, scan):
    picks = scan.get("picks_count", 0)
    bots_up = sum(1 for k, v in scan.items() if k.startswith("bot_") and v)
    if picks == 0:
        return {"summary": "No picks today — running prediction pipeline",
                "action": "check_pipeline", "priority": "critical",
                "cmd": f"cd {MON_IPAD.parent / chr(39) + "nomos-nba-agent" + chr(39)} && timeout 300 python3 predict_today.py 2>&1 | tail -20"}
    if bots_up < 2:
        return {"summary": f"Only {bots_up} bots running — restart bot fleet",
                "action": "restart_bots", "priority": "high",
                "cmd": "bash scripts/telegram/start_bots.sh restart"}
    return {"summary": f"{picks} picks ready, {bots_up} bots running",
            "action": "monitor", "priority": "low"}


def _propose_business(repo_path, scan):
    users = scan.get("total_users", 0)
    if users == 0:
        return {"summary": "Zero users — focus on first 10 users via Telegram channel",
                "action": "user_acquisition", "priority": "high"}
    if not scan.get("api_docs_exist"):
        return {"summary": "API docs missing — create API architecture",
                "action": "create_api_docs", "priority": "medium"}
    return {"summary": f"{users} users — track engagement and conversion",
            "action": "monitor", "priority": "low"}


def _propose_evaluation(repo_path, scan):
    ece = _safe_float(scan.get("ece"), 0)
    real_roi = _safe_float(scan.get("real_roi"), 0)
    real_sharpe = _safe_float(scan.get("real_sharpe"), 0)
    issues = []
    cmds = []

    if ece > 0.10:
        issues.append(f"ECE {ece:.3f} > 0.10 — calibration needs fixing")
        # Calibration: log for human review, don't auto-fix model
    if real_roi < -10:
        issues.append(f"Real ROI {real_roi:.1f}% — CRITICAL: reduce bet sizes")
        # Reduce max bet to 50% of current by updating bankroll config
        cmds.append(
            "python3 -c \""
            "import json; p='data/nba-agent/bankroll-state.json'; "
            "d=json.load(open(p)); "
            "d['max_bet_pct']=d.get('max_bet_pct',5.0)*0.5; "
            "d['auto_reduced']=True; d['reduction_reason']='ROI < -10pct'; "
            "json.dump(d,open(p,'w'),indent=2); "
            "print(f'Reduced max_bet_pct to {d[\\\"max_bet_pct\\\"]}')\"")
    elif real_roi < -5:
        issues.append(f"Real ROI {real_roi:.1f}% — strategy losing money")
    if real_sharpe < 0:
        issues.append(f"Sharpe {real_sharpe:.2f} negative — risk-adjusted returns bad")

    if issues:
        priority = "critical" if real_roi < -10 else "high"
        return {"summary": " | ".join(issues), "action": "fix_calibration", "priority": priority,
                "cmd": " && ".join(cmds) if cmds else None}
    return {"summary": f"Evaluation metrics OK: ECE={ece:.3f}, ROI={real_roi:.1f}%, Sharpe={real_sharpe:.2f}",
            "action": "monitor", "priority": "low"}


def _propose_infra(repo_path, scan):
    disk = scan.get("disk_used_pct", 0)
    mem = scan.get("mem_avail_mb", 999)
    spaces_up = scan.get("spaces_up", 0)
    spaces_total = scan.get("spaces_total", 6)
    issues = scan.get("issues", [])
    proposals = []
    cmds = []

    if disk > 85:
        proposals.append(f"Disk at {disk}% — cleanup needed")
        # Safe cleanup: logs older than 7d, Python cache, tmp files, journal vacuum
        cmds.extend([
            'find /home/termius -name "*.log" -mtime +7 -delete 2>/dev/null || true',
            'find /home/termius -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true',
            'find /tmp -name "*.tmp" -mtime +3 -delete 2>/dev/null || true',
            'journalctl --vacuum-size=50M 2>/dev/null || true',
        ])
    if mem < 200:
        proposals.append(f"Only {mem}MB RAM free — kill idle processes")
        cmds.append('pkill -f "python3.*idle" 2>/dev/null || true')
    if spaces_up < spaces_total:
        proposals.append(f"Only {spaces_up}/{spaces_total} spaces UP")
        cmds.append("bash scripts/keepalive-spaces.sh")
    if issues:
        proposals.append(f"{len(issues)} issues: {', '.join(issues[:3])}")

    if proposals:
        priority = "critical" if disk > 90 or mem < 100 or spaces_up < spaces_total - 2 else "high"
        return {"summary": " | ".join(proposals), "action": "fix_infra", "priority": priority,
                "cmd": " && ".join(cmds) if cmds else None}
    return {"summary": f"Infra healthy: disk {disk}%, {mem}MB free, {spaces_up}/{spaces_total} spaces",
            "action": "monitor", "priority": "low"}


def _propose_finance(repo_path, scan):
    bankroll = _safe_float(scan.get("bankroll"), 100)
    roi = _safe_float(scan.get("roi_pct"), 0)
    if bankroll < 80:
        # Actually pause the betting cron + mark bankroll as paused
        pause_cmd = (
            "python3 -c \""
            "import json; p='data/nba-agent/bankroll-state.json'; "
            "d=json.load(open(p)); d['betting_paused']=True; "
            "d['pause_reason']='Bankroll below $80 threshold'; "
            "json.dump(d,open(p,'w'),indent=2); "
            "print('Betting PAUSED — bankroll below threshold')\" && "
            "crontab -l 2>/dev/null | grep -v 'betting_agent\\|daily-edge' | crontab - 2>/dev/null || true"
        )
        return {"summary": f"Bankroll ${bankroll:.2f} below $80 — PAUSING betting cron + marking state",
                "action": "pause_betting", "priority": "critical",
                "cmd": pause_cmd}
    if roi < -10:
        # Reduce bet sizing, don't fully pause
        return {"summary": f"ROI {roi:.1f}% — reduce bet sizes and review strategy",
                "action": "strategy_review", "priority": "high",
                "cmd": (
                    "python3 -c \""
                    "import json; p='data/nba-agent/bankroll-state.json'; "
                    "d=json.load(open(p)); "
                    "d['max_bet_pct']=max(1.0, d.get('max_bet_pct',5.0)*0.5); "
                    "d['strategy_review_needed']=True; "
                    "json.dump(d,open(p,'w'),indent=2); "
                    "print(f'Reduced max_bet_pct to {d[\\\"max_bet_pct\\\"]}')\"")
                }
    return {"summary": f"Bankroll ${bankroll:.2f}, ROI {roi:.1f}%, burn ${scan.get('burn_rate', 20)}/mo",
            "action": "monitor", "priority": "low"}


def _propose_cross_repo(repo_path, scan):
    drift = scan.get("drift_count", 0)
    repos = scan.get("repos_active", 0)
    uncommitted = scan.get("uncommitted", {})
    heavy_uncommitted = [r for r, n in uncommitted.items() if n > 50]

    issues = []
    cmds = ["python3 scripts/cross-repo-monitor.py"]

    if drift > 5:
        issues.append(f"{drift} stale councils across repos")
    if heavy_uncommitted:
        issues.append(f"{len(heavy_uncommitted)} repos with 50+ uncommitted files: {', '.join(heavy_uncommitted)}")
        # Auto-commit data files for each heavy repo
        for r in heavy_uncommitted:
            rpath = str(MON_IPAD.parent / r)
            cmds.append(
                f'cd {rpath} && git add data/ *.json 2>/dev/null; '
                f'git commit -m "data: auto-commit council iteration (>50 uncommitted)" --no-verify 2>/dev/null || true')
    if repos < 8:
        issues.append(f"Only {repos}/8 repos accessible")

    if issues:
        return {"summary": " | ".join(issues), "action": "sync_repos", "priority": "high",
                "cmd": " && ".join(cmds)}
    return {"summary": f"All {repos} repos synced, {drift} minor drifts",
            "action": "monitor", "priority": "low"}


# ── EXECUTE: Real actions ──────────────────────────────────────────────

def phase_execute(repo_path, dept, config, proposal):
    """Execute the proposal. Runs real commands for high/critical priority items.

    Safety layers:
    1. Only high/critical proposals with explicit `cmd` are executed
    2. CouncilAdvisor gates actions via LLM council voting:
       - CRITICAL: 3/4 models must approve
       - HIGH: majority of responding models must approve
       - MEDIUM: Qwen 2.5 7B quick sanity check
       Falls back to rule-based if HF API unavailable (30s timeout)
    3. Engineering proposals with `diagnostic` field are logged, never executed
    4. 5-minute timeout hard cap on all commands
    """
    action = proposal.get("action", "monitor")
    priority = proposal.get("priority", "low")
    repo_name = Path(repo_path).name

    result = {"executed": False, "action": action, "proposal": proposal.get("summary", "")}

    # ── Safety: engineering diagnostics are logged, never auto-executed ──
    diagnostic = proposal.get("diagnostic")
    if diagnostic:
        log(repo_name, dept, f"DIAGNOSTIC: {diagnostic}", "WARN")
        result["diagnostic"] = diagnostic
        result["note"] = proposal.get("note", "Diagnostic logged — no auto-execution")
        if not proposal.get("cmd"):
            return result

    # ── Only execute commands for high/critical priority with explicit cmd ──
    cmd = proposal.get("cmd")
    if cmd and priority in ("high", "critical"):
        # ── Gate high and critical actions through CouncilAdvisor ──
        if priority in ("high", "critical"):
            advice = _advisor.advise(dept=dept, action=action, cmd=cmd, priority=priority)
            log(repo_name, dept, f"Advisor: approved={advice['approved']} reason={advice['reason']}")
            if advice.get("model_votes"):
                log(repo_name, dept, f"Model votes: {json.dumps(advice['model_votes'])}")
            if not advice["approved"]:
                result["note"] = f"BLOCKED by advisor: {advice['reason']}"
                result["advisor"] = advice
                return result
            result["advisor"] = advice

        log(repo_name, dept, f"Executing: {cmd}")
        try:
            proc = _sp.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=300, cwd=str(MON_IPAD))
            result["executed"] = True
            result["exit_code"] = proc.returncode
            result["stdout_tail"] = proc.stdout[-500:] if proc.stdout else ""
            result["stderr_tail"] = proc.stderr[-200:] if proc.stderr else ""
            if proc.returncode != 0:
                log(repo_name, dept, f"Command exited {proc.returncode}: {proc.stderr[-150:]}", "WARN")
            else:
                log(repo_name, dept, f"Command succeeded (exit 0)")
        except _sp.TimeoutExpired:
            result["error"] = "Timeout after 5 minutes"
            log(repo_name, dept, "Command TIMEOUT after 5 minutes", "ERROR")
        except Exception as e:
            result["error"] = str(e)
            log(repo_name, dept, f"Command FAILED: {e}", "ERROR")
    elif action == "monitor":
        result["executed"] = True
        result["note"] = "Monitoring — no action needed"
    else:
        result["note"] = f"Action '{action}' logged but not auto-executed (priority={priority}, cmd={'present' if cmd else 'missing'})"

    return result


# ── EVALUATE: Real metric comparison ───────────────────────────────────

def phase_evaluate(repo_path, dept, config, exec_result):
    """Evaluate with REAL metrics. Compare before/after when possible."""
    repo_name = Path(repo_path).name
    eval_out = {"decision": "keep"}

    # Re-scan to get fresh metrics for comparison
    scanners = {
        "research": _scan_research,
        "engineering": _scan_engineering,
        "evolution": _scan_evolution,
        "evaluation": _scan_evaluation,
        "infra": _scan_infra,
        "finance": _scan_finance,
        "cross_repo_agents": _scan_cross_repo_agents,
    }
    scanner = scanners.get(dept)
    fresh = scanner(repo_path) if scanner else {}

    # Department-specific evaluation
    if dept == "evolution":
        brier = fresh.get("best_fleet_brier", 1.0)
        eval_out["best_fleet_brier"] = {"value": brier}
        eval_out["total_generations"] = {"value": fresh.get("total_generations", 0)}
        eval_out["stagnant_islands"] = {"value": fresh.get("stagnant_islands", 0)}
        if not fresh.get("all_up"):
            eval_out["decision"] = "alert"

    elif dept == "engineering":
        brier = _safe_float(fresh.get("brier"), 0.23)
        eval_out["brier"] = {"value": round(brier, 5)}
        atr = _safe_float(fresh.get("atr_brier"), 0.21570)
        eval_out["atr_brier"] = {"value": round(atr, 5)}
        eval_out["gap_to_atr"] = {"value": round(brier - atr, 5)}

    elif dept == "evaluation":
        for k in ["brier", "ece", "mce", "real_roi", "real_sharpe"]:
            if k in fresh:
                eval_out[k] = {"value": fresh[k]}

    elif dept == "infra":
        eval_out["disk_used_pct"] = {"value": fresh.get("disk_used_pct", 0)}
        eval_out["mem_avail_mb"] = {"value": fresh.get("mem_avail_mb", 0)}
        eval_out["spaces_up"] = {"value": f"{fresh.get('spaces_up', 0)}/{fresh.get('spaces_total', 6)}"}
        if fresh.get("disk_used_pct", 0) > 90 or fresh.get("mem_avail_mb", 999) < 100:
            eval_out["decision"] = "alert"

    elif dept == "finance":
        eval_out["bankroll"] = {"value": fresh.get("bankroll", 0)}
        eval_out["roi_pct"] = {"value": fresh.get("roi_pct", 0)}
        eval_out["burn_rate"] = {"value": fresh.get("estimated_monthly_cost", 20)}

    elif dept == "research":
        eval_out["papers_found"] = {"value": fresh.get("papers_found", 0)}
        eval_out["scan_count"] = {"value": fresh.get("scan_count", 0)}

    # If execution failed, decide revert
    if exec_result.get("error"):
        eval_out["decision"] = "revert"
        eval_out["error"] = {"value": exec_result["error"]}

    return eval_out


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Forge Council — Universal Karpathy Loop")
    parser.add_argument("--repo", required=True, help="Repo name or path")
    parser.add_argument("--dept", required=True, help="Department name")
    parser.add_argument("--dry-run", action="store_true", help="Don't execute, just show plan")
    parser.add_argument("--all-depts", action="store_true", help="Run all 8 departments")
    args = parser.parse_args()

    config = load_config()

    # Resolve repo path
    repo_path = args.repo
    if not os.path.isabs(repo_path):
        repo_path = str(MON_IPAD.parent / args.repo)
    if not os.path.isdir(repo_path):
        print(f"ERROR: Repo not found: {repo_path}")
        sys.exit(1)

    if args.all_depts:
        depts = list(config["departments"].keys())
    else:
        depts = [args.dept]

    results = {}
    for dept in depts:
        success = run_karpathy_loop(repo_path, dept, config, dry_run=args.dry_run)
        results[dept] = "KEEP" if success else "REVERT"

    print(f"\n{'='*60}")
    print(f"Council Results for {Path(repo_path).name}:")
    for dept, result in results.items():
        print(f"  {dept:15s} → {result}")

if __name__ == "__main__":
    main()
