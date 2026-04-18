"""Provider health registry + hot-swap substitution for the LLM trading floor.

Scientific principle: every agent stays a real LLM call. When the intended
provider fails N times consecutively we substitute with a tier-matched live
alternative from the emergency pool while an async worker tries to heal the
original HF Space. Substitutions are logged per-decision as
(provider_intended, provider_actual) for audit-clean replay.

This preserves:
- Multi-agent LLM principle (no Python shims, no hash sims).
- Axelrod canon / persona / strategy (system_prompt unchanged).
- Sequential-day resolution (CK broadcast intact).
- Reputation + P&L scoring (every agent participates every day).

And adds:
- No 30s dead-provider timeouts on the critical path.
- Async self-heal of dead HF Spaces (restart_space + poll /health).
- Auditable substitution trail.
"""
import time
import threading
import urllib.parse
from typing import Optional, Dict, List

import requests

# Tier-tagged emergency pool (verified alive cloud providers, 2026-04-17).
EMERGENCY_POOL = {
    "L": ["cerebras:qwen-3-235b", "openrouter:nemotron-120b", "nvidia:llama-3.3-70b", "github:gpt-4o-mini"],
    "M": ["cerebras:llama3.1-8b", "mistral:large", "mistral:medium", "nvidia:minimax-m2.7", "github:gpt-4o-mini", "github:llama-3.1-8b"],
    "S": ["mistral:small", "mistral:ministral-8b", "mistral:nemo", "openrouter:gpt-oss-120b", "github:llama-3.1-8b", "selfhost:qwen3-4b", "selfhost:dolphin3-l32-3b"],
}

PROVIDER_TIER: Dict[str, str] = {
    "cerebras:qwen-3-235b": "L",
    "openrouter:nemotron-120b": "L",
    "nvidia:llama-3.3-70b": "L",
    "nvidia:nemotron-70b": "L",
    "cerebras:llama3.1-8b": "M",
    "mistral:large": "M",
    "mistral:medium": "M",
    "google:gemini-3-flash": "M",
    "nvidia:minimax-m2.7": "M",
    "nvidia:minimax-m2.7-alt": "M",
    "mistral:small": "S",
    "mistral:ministral-8b": "S",
    "mistral:nemo": "S",
    "openrouter:gpt-oss-120b": "S",
    "openrouter:gemma-4-31b": "S",
    "selfhost:qwen3-4b": "S",
    "selfhost:gemma-3-4b": "S",
    "selfhost:qwen3-0.6b": "S",
    "selfhost:dolphin3-l32-3b": "S",
    "selfhost:cpu-gemma4": "S",
    "github:gpt-4o-mini": "M",
    "github:llama-3.1-8b": "S",
}

CIRCUIT_THRESHOLD = 3
CIRCUIT_COOLDOWN = 300
HEAL_POLL_INTERVAL = 30
HEAL_DEADLINE = 1800

_lock = threading.Lock()
_health: Dict[str, dict] = {}
_substitutions_in_use: Dict[str, int] = {}
_substitutions_log: List[dict] = []
_healing_threads: Dict[str, threading.Thread] = {}


def record_success(provider: str) -> None:
    with _lock:
        h = _health.setdefault(provider, {"consecutive_failures": 0, "skip_until": 0, "last_error": None, "last_success": 0})
        h["consecutive_failures"] = 0
        h["last_success"] = time.time()
        h["skip_until"] = 0


def record_failure(provider: str, error_class: str = "unknown") -> None:
    with _lock:
        h = _health.setdefault(provider, {"consecutive_failures": 0, "skip_until": 0, "last_error": None, "last_success": 0})
        h["consecutive_failures"] += 1
        h["last_error"] = error_class
        if h["consecutive_failures"] >= CIRCUIT_THRESHOLD:
            h["skip_until"] = time.time() + CIRCUIT_COOLDOWN


def is_dead(provider: str) -> bool:
    with _lock:
        return _health.get(provider, {}).get("skip_until", 0) > time.time()


def pick_substitute(intended: str, exclude: Optional[List[str]] = None) -> Optional[str]:
    """Pick a live substitute from the same tier, least-loaded first."""
    exclude = set(exclude or [])
    tier = PROVIDER_TIER.get(intended, "M")
    for tier_order in ([tier] + [t for t in ("M", "L", "S") if t != tier]):
        cands = [p for p in EMERGENCY_POOL.get(tier_order, [])
                 if p != intended and p not in exclude and not is_dead(p)]
        if cands:
            with _lock:
                return min(cands, key=lambda p: _substitutions_in_use.get(p, 0))
    return None


def register_substitute_use(actual: str, intended: str, trader_id: str = "?") -> None:
    with _lock:
        _substitutions_in_use[actual] = _substitutions_in_use.get(actual, 0) + 1
        _substitutions_log.append({
            "ts": time.time(),
            "trader_id": trader_id,
            "intended": intended,
            "actual": actual,
        })
        if len(_substitutions_log) > 500:
            del _substitutions_log[:len(_substitutions_log) - 500]


def classify_error(error_msg: Optional[str], status_code: Optional[int] = None) -> str:
    """Classify an LLM failure into 6 canonical classes."""
    if status_code == 429:
        return "rate_limit"
    if status_code in (500, 502, 503, 504):
        return "http_5xx"
    if status_code == 404:
        return "dead_endpoint"
    if status_code in (401, 403):
        return "auth_fail"
    msg = (error_msg or "").lower()
    if "timeout" in msg or "timed out" in msg:
        return "timeout"
    if "json" in msg and ("decode" in msg or "parse" in msg):
        return "parse_fail"
    if "empty" in msg or "finishreason" in msg:
        return "empty_response"
    return "unknown"


def _heal_worker(provider: str, url: str) -> None:
    """Poll the HF Space root until 200 OK, then clear skip_until."""
    parts = urllib.parse.urlparse(url)
    health_url = f"{parts.scheme}://{parts.netloc}/"
    deadline = time.time() + HEAL_DEADLINE
    while time.time() < deadline:
        try:
            r = requests.get(health_url, timeout=10)
            if r.status_code == 200:
                with _lock:
                    if provider in _health:
                        _health[provider]["consecutive_failures"] = 0
                        _health[provider]["skip_until"] = 0
                        _health[provider]["recovered_at"] = time.time()
                return
        except Exception:
            pass
        time.sleep(HEAL_POLL_INTERVAL)


def trigger_heal(provider: str, url: str) -> None:
    """Spawn (once) an async healing thread for a dead provider."""
    with _lock:
        t = _healing_threads.get(provider)
        if t and t.is_alive():
            return
        nt = threading.Thread(target=_heal_worker, args=(provider, url), daemon=True)
        _healing_threads[provider] = nt
        nt.start()


def get_snapshot() -> dict:
    """Health snapshot for /api/status exposure."""
    now = time.time()
    with _lock:
        return {
            "providers_dead": {p: max(0, int(h["skip_until"] - now))
                               for p, h in _health.items() if h.get("skip_until", 0) > now},
            "providers_ok": [p for p, h in _health.items()
                             if h.get("skip_until", 0) <= now and h.get("consecutive_failures", 0) == 0],
            "substitutions_in_use": dict(_substitutions_in_use),
            "recent_substitutions": _substitutions_log[-20:],
            "healing_active": [p for p, t in _healing_threads.items() if t.is_alive()],
        }
