#!/usr/bin/env python3
"""
Nomos42 LLM Gateway — HuggingFace Spaces
==========================================
Centralized LLM proxy with automatic failover, rate limit handling,
and health monitoring. All API keys stored as HF Space secrets.

Providers: Cerebras (4 models), Google Gemini (2 keys), OpenRouter (27+ free models)
Features:
  - Automatic failover chain per model
  - Rate limit tracking (RPM per provider)
  - Health dashboard (which models are up/down)
  - Gradio API endpoints for programmatic access

Usage:
  - Direct: call via Gradio API client
  - CLI: python app.py --test
"""

import gradio as gr
import json
import os
import time
import requests
import traceback
from collections import defaultdict
from threading import Lock
from datetime import datetime, timezone

# ── MODEL REGISTRY ──────────────────────────────────────────────────────────
# Every model we can route to, organized by provider
MODELS = {
    # ── SELF-HOST (T12 Phi-3.5, CPU GGUF, no quota — R10 primary for low-stakes) ──
    "selfhost:phi-3.5": {
        "url": "https://nomos42-nomos42-llm-cpu.hf.space/chat/completions",
        "model": "phi-3.5-mini",
        "key_env": "NOMOS_HF_TOKEN",
        "provider": "selfhost",
        "max_tokens": 400,
        "rpm": 60,
        "tier": "fast",
    },
    # ── SELF-HOST (Qwen2.5-0.5B / Llama-3.2-1B / Gemma-2-2B — new CPU GGUF fleet) ──
    "selfhost:qwen2.5-0.5b": {
        "url": "https://nomos42-qwen25-05b-cpu.hf.space/chat/completions",
        "model": "qwen2.5-0.5b-instruct",
        "key_env": "NOMOS_HF_TOKEN",
        "provider": "selfhost",
        "max_tokens": 400,
        "rpm": 60,
        "tier": "fast",
    },
    "selfhost:llama-3.2-1b": {
        "url": "https://nomos42-llama32-1b-cpu.hf.space/chat/completions",
        "model": "llama-3.2-1b-instruct",
        "key_env": "NOMOS_HF_TOKEN",
        "provider": "selfhost",
        "max_tokens": 400,
        "rpm": 60,
        "tier": "fast",
    },
    "selfhost:gemma-2-2b": {
        "url": "https://nomos42-gemma2-2b-cpu.hf.space/chat/completions",
        "model": "gemma-2-2b-it",
        "key_env": "NOMOS_HF_TOKEN",
        "provider": "selfhost",
        "max_tokens": 400,
        "rpm": 60,
        "tier": "fast",
    },
    # ── CEREBRAS (free, ultra-fast ~2000 tok/s, 30 RPM) ──
    "cerebras:qwen-3-235b": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "qwen-3-235b-a22b-instruct-2507",
        "key_env": "CEREBRAS_API_KEY",
        "provider": "cerebras",
        "max_tokens": 400,
        "rpm": 30,
        "tier": "large",
    },
    "cerebras:llama3.1-8b": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "llama3.1-8b",
        "key_env": "CEREBRAS_API_KEY",
        "provider": "cerebras",
        "max_tokens": 400,
        "rpm": 30,
        "tier": "fast",
    },
    # NOTE: cerebras:zai-glm-4.7 and cerebras:gpt-oss-120b are listed in Cerebras API
    # but return 404 on chat/completions. Replaced with OpenRouter free alternatives.
    "openrouter:glm-4.5-air:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "z-ai/glm-4.5-air:free",
        "key_env": "OPENROUTER_KEY_BARTOLI",
        "provider": "openrouter",
        "max_tokens": 400,
        "rpm": 20,
        "tier": "medium",
    },
    "openrouter:gpt-oss-20b:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "openai/gpt-oss-20b:free",
        "key_env": "OPENROUTER_KEY_ORCHESTRATOR",
        "provider": "openrouter",
        "max_tokens": 400,
        "rpm": 20,
        "tier": "medium",
    },
    # ── GOOGLE GEMINI (free tier, 15 RPM per key) ──
    "google:gemini-2.5-flash": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        "model": "gemini-2.5-flash",
        "key_env": "GOOGLE_API_KEY",
        "provider": "google",
        "max_tokens": 400,
        "rpm": 14,
        "tier": "fast",
    },
    "google:gemini-3-flash": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent",
        "model": "gemini-3-flash-preview",
        "key_env": "GOOGLE_API_KEY_2",
        "provider": "google",
        "max_tokens": 400,
        "rpm": 14,
        "tier": "fast",
    },
    # ── OPENROUTER (free models, 20 RPM per key) ──
    "openrouter:gemma-4-26b:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "google/gemma-4-26b-a4b-it:free",
        "key_env": "OPENROUTER_KEY_ORCHESTRATOR",
        "provider": "openrouter",
        "max_tokens": 400,
        "rpm": 20,
        "tier": "medium",
    },
    "openrouter:nemotron-120b:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "nvidia/nemotron-3-super-120b-a12b:free",
        "key_env": "OPENROUTER_KEY_BARTOLI",
        "provider": "openrouter",
        "max_tokens": 400,
        "rpm": 20,
        "tier": "large",
    },
    "openrouter:minimax-m2.5:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "minimax/minimax-m2.5:free",
        "key_env": "OPENROUTER_KEY_PME",
        "provider": "openrouter",
        "max_tokens": 400,
        "rpm": 20,
        "tier": "medium",
    },
    "openrouter:qwen3-80b:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "qwen/qwen3-next-80b-a3b-instruct:free",
        "key_env": "OPENROUTER_KEY_ORCHESTRATOR",
        "provider": "openrouter",
        "max_tokens": 400,
        "rpm": 20,
        "tier": "large",
    },
    # ── EXTRA FREE OPENROUTER MODELS (fallback pool) ──
    "openrouter:llama-3.3-70b:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "key_env": "OPENROUTER_KEY_PME",
        "provider": "openrouter",
        "max_tokens": 400,
        "rpm": 20,
        "tier": "large",
    },
}

# ── FALLBACK CHAINS ─────────────────────────────────────────────────────────
# If primary model fails, try these in order. T12 self-host appended as last
# resort on every chain (no quota, no rate limit — slow but never fails).
FALLBACK_CHAINS = {
    "selfhost:phi-3.5":              ["cerebras:llama3.1-8b", "google:gemini-2.5-flash", "openrouter:gemma-4-26b:free", "selfhost:qwen2.5-0.5b", "selfhost:llama-3.2-1b", "selfhost:gemma-2-2b"],
    "selfhost:qwen2.5-0.5b":         ["selfhost:llama-3.2-1b", "selfhost:gemma-2-2b", "selfhost:phi-3.5", "cerebras:llama3.1-8b"],
    "selfhost:llama-3.2-1b":         ["selfhost:qwen2.5-0.5b", "selfhost:gemma-2-2b", "selfhost:phi-3.5", "cerebras:llama3.1-8b"],
    "selfhost:gemma-2-2b":           ["selfhost:llama-3.2-1b", "selfhost:qwen2.5-0.5b", "selfhost:phi-3.5", "cerebras:llama3.1-8b"],
    "cerebras:qwen-3-235b":          ["cerebras:llama3.1-8b", "openrouter:qwen3-80b:free", "google:gemini-2.5-flash", "selfhost:phi-3.5", "selfhost:qwen2.5-0.5b", "selfhost:llama-3.2-1b", "selfhost:gemma-2-2b"],
    "cerebras:llama3.1-8b":          ["cerebras:qwen-3-235b", "google:gemini-2.5-flash", "openrouter:llama-3.3-70b:free", "selfhost:phi-3.5", "selfhost:qwen2.5-0.5b", "selfhost:llama-3.2-1b", "selfhost:gemma-2-2b"],
    "openrouter:glm-4.5-air:free":   ["cerebras:llama3.1-8b", "openrouter:gpt-oss-20b:free", "google:gemini-3-flash", "selfhost:phi-3.5", "selfhost:qwen2.5-0.5b", "selfhost:llama-3.2-1b", "selfhost:gemma-2-2b"],
    "openrouter:gpt-oss-20b:free":   ["cerebras:qwen-3-235b", "openrouter:nemotron-120b:free", "cerebras:llama3.1-8b", "selfhost:phi-3.5", "selfhost:qwen2.5-0.5b", "selfhost:llama-3.2-1b", "selfhost:gemma-2-2b"],
    "google:gemini-2.5-flash":       ["google:gemini-3-flash", "cerebras:llama3.1-8b", "openrouter:gemma-4-26b:free", "selfhost:phi-3.5", "selfhost:qwen2.5-0.5b", "selfhost:llama-3.2-1b", "selfhost:gemma-2-2b"],
    "google:gemini-3-flash":         ["google:gemini-2.5-flash", "cerebras:llama3.1-8b", "openrouter:gemma-4-26b:free", "selfhost:phi-3.5", "selfhost:qwen2.5-0.5b", "selfhost:llama-3.2-1b", "selfhost:gemma-2-2b"],
    "openrouter:gemma-4-26b:free":   ["openrouter:llama-3.3-70b:free", "cerebras:llama3.1-8b", "google:gemini-2.5-flash", "selfhost:phi-3.5", "selfhost:qwen2.5-0.5b", "selfhost:llama-3.2-1b", "selfhost:gemma-2-2b"],
    "openrouter:nemotron-120b:free": ["openrouter:qwen3-80b:free", "cerebras:qwen-3-235b", "openrouter:llama-3.3-70b:free", "selfhost:phi-3.5", "selfhost:qwen2.5-0.5b", "selfhost:llama-3.2-1b", "selfhost:gemma-2-2b"],
    "openrouter:minimax-m2.5:free":  ["openrouter:gpt-oss-20b:free", "openrouter:glm-4.5-air:free", "cerebras:llama3.1-8b", "selfhost:phi-3.5", "selfhost:qwen2.5-0.5b", "selfhost:llama-3.2-1b", "selfhost:gemma-2-2b"],
    "openrouter:qwen3-80b:free":     ["cerebras:qwen-3-235b", "openrouter:nemotron-120b:free", "openrouter:llama-3.3-70b:free", "selfhost:phi-3.5", "selfhost:qwen2.5-0.5b", "selfhost:llama-3.2-1b", "selfhost:gemma-2-2b"],
    "openrouter:llama-3.3-70b:free": ["cerebras:llama3.1-8b", "openrouter:nemotron-120b:free", "google:gemini-2.5-flash", "selfhost:phi-3.5", "selfhost:qwen2.5-0.5b", "selfhost:llama-3.2-1b", "selfhost:gemma-2-2b"],
}

# ── HEALTH TRACKER ──────────────────────────────────────────────────────────
health_lock = Lock()
model_health = {}  # model_id -> {status, last_call, last_error, calls_ok, calls_fail, avg_latency}
rate_tracker = defaultdict(list)  # model_id -> [timestamps of recent calls]

def _init_health():
    for mid in MODELS:
        model_health[mid] = {
            "status": "unknown",
            "last_call": None,
            "last_error": None,
            "calls_ok": 0,
            "calls_fail": 0,
            "avg_latency_ms": 0,
            "total_latency_ms": 0,
        }

_init_health()


def _check_rate_limit(model_id: str) -> bool:
    """Return True if we can make a call (under RPM limit)."""
    rpm = MODELS[model_id]["rpm"]
    now = time.time()
    with health_lock:
        # Clean old entries (older than 60s)
        rate_tracker[model_id] = [t for t in rate_tracker[model_id] if now - t < 60]
        if len(rate_tracker[model_id]) >= rpm:
            return False
        rate_tracker[model_id].append(now)
        return True


def _update_health(model_id: str, success: bool, latency_ms: float, error: str = None):
    with health_lock:
        h = model_health[model_id]
        h["last_call"] = datetime.now(timezone.utc).isoformat()
        if success:
            h["status"] = "healthy"
            h["calls_ok"] += 1
            h["total_latency_ms"] += latency_ms
            h["avg_latency_ms"] = h["total_latency_ms"] / h["calls_ok"]
            h["last_error"] = None
        else:
            h["status"] = "error"
            h["calls_fail"] += 1
            h["last_error"] = error


# ── RAW API CALLS ───────────────────────────────────────────────────────────

def _call_cerebras(model_cfg: dict, messages: list, max_tokens: int) -> str:
    key = os.environ.get(model_cfg["key_env"], "")
    if not key:
        raise ValueError(f"Missing key: {model_cfg['key_env']}")
    resp = requests.post(
        model_cfg["url"],
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": model_cfg["model"], "messages": messages, "max_tokens": max_tokens, "temperature": 0.7},
        timeout=30,
    )
    if resp.status_code == 429:
        raise ValueError(f"Rate limited (429)")
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _call_google(model_cfg: dict, messages: list, max_tokens: int) -> str:
    key = os.environ.get(model_cfg["key_env"], "")
    if not key:
        raise ValueError(f"Missing key: {model_cfg['key_env']}")
    # Convert OpenAI format to Gemini format
    contents = []
    system_text = ""
    for m in messages:
        if m["role"] == "system":
            system_text = m["content"]
        elif m["role"] == "user":
            contents.append({"role": "user", "parts": [{"text": m["content"]}]})
        elif m["role"] == "assistant":
            contents.append({"role": "model", "parts": [{"text": m["content"]}]})

    body = {
        "contents": contents,
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
    }
    if system_text:
        body["systemInstruction"] = {"parts": [{"text": system_text}]}

    url = f"{model_cfg['url']}?key={key}"
    resp = requests.post(url, json=body, timeout=30)
    if resp.status_code == 429:
        raise ValueError("Rate limited (429)")
    resp.raise_for_status()
    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini returned no candidates")
    content = candidates[0].get("content", {})
    parts = content.get("parts", [])
    if not parts:
        raise ValueError("Gemini returned empty parts (safety filter?)")
    return parts[0].get("text", "")


def _call_openrouter(model_cfg: dict, messages: list, max_tokens: int) -> str:
    key = os.environ.get(model_cfg["key_env"], "")
    if not key:
        raise ValueError(f"Missing key: {model_cfg['key_env']}")
    resp = requests.post(
        model_cfg["url"],
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://nomos42.ai",
            "X-Title": "Nomos42 LLM Gateway",
        },
        json={"model": model_cfg["model"], "messages": messages, "max_tokens": max_tokens, "temperature": 0.7},
        timeout=45,
    )
    if resp.status_code == 429:
        raise ValueError("Rate limited (429)")
    resp.raise_for_status()
    data = resp.json()
    if "choices" in data and data["choices"]:
        return data["choices"][0]["message"]["content"]
    if "error" in data:
        raise ValueError(f"OpenRouter error: {data['error']}")
    raise ValueError(f"Unexpected response: {json.dumps(data)[:200]}")


def _call_selfhost(model_cfg: dict, messages: list, max_tokens: int) -> str:
    """T12 self-host (Nomos42/nomos42-llm-cpu). No quota, ~5-8s/call on CPU."""
    key = os.environ.get(model_cfg["key_env"], "")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    resp = requests.post(
        model_cfg["url"],
        headers=headers,
        json={"model": model_cfg["model"], "messages": messages, "max_tokens": max_tokens, "temperature": 0.7},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if "choices" in data and data["choices"]:
        return data["choices"][0]["message"]["content"]
    if "content" in data:
        return data["content"]
    raise ValueError(f"Self-host unexpected response: {json.dumps(data)[:200]}")


PROVIDER_CALLERS = {
    "cerebras": _call_cerebras,
    "google": _call_google,
    "openrouter": _call_openrouter,
    "selfhost": _call_selfhost,
}


# ── MAIN GATEWAY FUNCTION ──────────────────────────────────────────────────

def call_llm(model_id: str, messages: list, max_tokens: int = 400) -> dict:
    """
    Call an LLM model with automatic failover.

    Returns: {
        "content": str,         # The response text
        "model_used": str,      # Which model actually responded
        "fallback": bool,       # Whether a fallback was used
        "latency_ms": float,    # Response time
        "errors": list,         # Errors from failed attempts
    }
    """
    chain = [model_id] + FALLBACK_CHAINS.get(model_id, [])
    errors = []

    for mid in chain:
        if mid not in MODELS:
            errors.append({"model": mid, "error": "Model not in registry"})
            continue

        cfg = MODELS[mid]

        # Check rate limit
        if not _check_rate_limit(mid):
            errors.append({"model": mid, "error": "Rate limit exceeded"})
            continue

        # Call the model
        caller = PROVIDER_CALLERS.get(cfg["provider"])
        if not caller:
            errors.append({"model": mid, "error": f"Unknown provider: {cfg['provider']}"})
            continue

        try:
            t0 = time.time()
            content = caller(cfg, messages, max_tokens)
            latency = (time.time() - t0) * 1000

            _update_health(mid, True, latency)

            return {
                "content": content,
                "model_used": mid,
                "model_name": cfg["model"],
                "fallback": mid != model_id,
                "latency_ms": round(latency, 1),
                "errors": errors,
            }
        except Exception as e:
            latency = (time.time() - t0) * 1000
            err_msg = str(e)[:200]
            _update_health(mid, False, latency, err_msg)
            errors.append({"model": mid, "error": err_msg, "latency_ms": round(latency, 1)})
            # Brief sleep before trying fallback (avoid hammering)
            time.sleep(0.5)

    return {
        "content": None,
        "model_used": None,
        "fallback": True,
        "latency_ms": 0,
        "errors": errors,
        "error": "All models in fallback chain failed",
    }


def call_any(tier: str, messages: list, max_tokens: int = 400) -> dict:
    """
    Call any available model in a tier (fast/medium/large).
    Picks the healthiest model first.
    """
    tier_models = [mid for mid, cfg in MODELS.items() if cfg["tier"] == tier]
    if not tier_models:
        return {"content": None, "error": f"No models in tier: {tier}"}

    # Sort by health: healthy first, then unknown, then error
    def health_score(mid):
        h = model_health.get(mid, {})
        s = h.get("status", "unknown")
        if s == "healthy":
            return (0, h.get("avg_latency_ms", 9999))
        if s == "unknown":
            return (1, 0)
        return (2, 0)

    tier_models.sort(key=health_score)
    return call_llm(tier_models[0], messages, max_tokens)


# ── HEALTH CHECK ────────────────────────────────────────────────────────────

def run_health_check() -> str:
    """Ping every model with a minimal prompt and update health status."""
    results = []
    test_messages = [{"role": "user", "content": "Say OK in exactly one word."}]

    for mid in MODELS:
        cfg = MODELS[mid]
        caller = PROVIDER_CALLERS.get(cfg["provider"])
        if not caller:
            results.append(f"  {mid}: SKIP (unknown provider)")
            continue

        key = os.environ.get(cfg["key_env"], "")
        if not key:
            _update_health(mid, False, 0, "Missing API key")
            results.append(f"  {mid}: FAIL (missing {cfg['key_env']})")
            continue

        try:
            t0 = time.time()
            content = caller(cfg, test_messages, 10)
            latency = (time.time() - t0) * 1000
            _update_health(mid, True, latency)
            results.append(f"  {mid}: OK ({latency:.0f}ms) → {content[:30]}")
        except Exception as e:
            latency = (time.time() - t0) * 1000
            err = str(e)[:80]
            _update_health(mid, False, latency, err)
            results.append(f"  {mid}: FAIL ({latency:.0f}ms) → {err}")

        time.sleep(1)  # Respect rate limits during health check

    return "\n".join(results)


def get_health_dashboard() -> str:
    """Return formatted health status of all models."""
    now = datetime.now(timezone.utc)
    lines = [
        f"# Nomos42 LLM Gateway — Health Dashboard",
        f"**Updated:** {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"**Models:** {len(MODELS)} registered",
        "",
        "| Model | Status | OK | Fail | Avg Latency | Last Error |",
        "|-------|--------|-----|------|-------------|------------|",
    ]

    for mid in sorted(MODELS.keys()):
        h = model_health.get(mid, {})
        status = h.get("status", "unknown")
        emoji = {"healthy": "🟢", "error": "🔴", "unknown": "⚪"}.get(status, "⚪")
        ok = h.get("calls_ok", 0)
        fail = h.get("calls_fail", 0)
        avg_lat = h.get("avg_latency_ms", 0)
        last_err = (h.get("last_error") or "—")[:40]
        lines.append(f"| {mid} | {emoji} {status} | {ok} | {fail} | {avg_lat:.0f}ms | {last_err} |")

    # Key status
    lines.extend(["", "### API Keys"])
    for key_name in sorted(set(cfg["key_env"] for cfg in MODELS.values())):
        val = os.environ.get(key_name, "")
        status = f"SET ({val[:6]}...)" if val else "MISSING"
        lines.append(f"- **{key_name}**: {status}")

    return "\n".join(lines)


# ── GRADIO API WRAPPER ──────────────────────────────────────────────────────

def gradio_call(model_id: str, system_prompt: str, user_prompt: str, max_tokens: int = 400) -> str:
    """Gradio-compatible wrapper for call_llm."""
    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    result = call_llm(model_id, messages, int(max_tokens))
    return json.dumps(result, indent=2)


def gradio_call_any_tier(tier: str, system_prompt: str, user_prompt: str, max_tokens: int = 400) -> str:
    """Call any available model in a tier."""
    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    result = call_any(tier, messages, int(max_tokens))
    return json.dumps(result, indent=2)


def gradio_health_check() -> str:
    """Run health check and return dashboard."""
    check_results = run_health_check()
    dashboard = get_health_dashboard()
    return f"{dashboard}\n\n### Last Health Check\n```\n{check_results}\n```"


def gradio_list_models() -> str:
    """List all available models."""
    lines = []
    for mid, cfg in sorted(MODELS.items()):
        h = model_health.get(mid, {})
        status = h.get("status", "unknown")
        lines.append(f"{mid}  |  tier={cfg['tier']}  |  provider={cfg['provider']}  |  status={status}")
    return "\n".join(lines)


# ── STARTUP DIAGNOSTICS ────────────────────────────────────────────────────

print("=" * 60)
print("NOMOS42 LLM GATEWAY — STARTUP")
print("=" * 60)
keys_ok, keys_missing = 0, 0
for key_name in sorted(set(cfg["key_env"] for cfg in MODELS.values())):
    val = os.environ.get(key_name, "")
    if val:
        print(f"  {key_name}: {val[:6]}...{val[-3:]} (len={len(val)})")
        keys_ok += 1
    else:
        print(f"  {key_name}: NOT SET")
        keys_missing += 1
print(f"\nKeys: {keys_ok} OK, {keys_missing} missing")
print(f"Models: {len(MODELS)} registered")
print("=" * 60)


# ── GRADIO UI ───────────────────────────────────────────────────────────────

DARK_CSS = """
.gradio-container { background: #0a0a0a !important; }
.gr-box { background: #111 !important; border: 1px solid #333 !important; }
footer { display: none !important; }
"""

with gr.Blocks(title="Nomos42 LLM Gateway", css=DARK_CSS, theme=gr.themes.Base()) as demo:
    gr.Markdown("# Nomos42 LLM Gateway\n**Centralized proxy** — automatic failover, rate limits, health monitoring")

    with gr.Tab("Call Model"):
        with gr.Row():
            model_dd = gr.Dropdown(
                choices=sorted(MODELS.keys()),
                value="cerebras:llama3.1-8b",
                label="Model (with fallback chain)",
            )
            max_tok = gr.Number(value=400, label="Max Tokens")
        sys_prompt = gr.Textbox(label="System Prompt", placeholder="Optional system prompt...", lines=2)
        usr_prompt = gr.Textbox(label="User Prompt", placeholder="Your message to the model...", lines=4)
        call_btn = gr.Button("Call Model", variant="primary")
        output = gr.Textbox(label="Response (JSON)", lines=12)
        call_btn.click(fn=gradio_call, inputs=[model_dd, sys_prompt, usr_prompt, max_tok], outputs=output,
                       api_name="call_model")

    with gr.Tab("Call by Tier"):
        with gr.Row():
            tier_dd = gr.Dropdown(choices=["fast", "medium", "large"], value="fast", label="Tier")
            max_tok2 = gr.Number(value=400, label="Max Tokens")
        sys_prompt2 = gr.Textbox(label="System Prompt", lines=2)
        usr_prompt2 = gr.Textbox(label="User Prompt", lines=4)
        tier_btn = gr.Button("Call Any in Tier", variant="primary")
        tier_out = gr.Textbox(label="Response (JSON)", lines=12)
        tier_btn.click(fn=gradio_call_any_tier, inputs=[tier_dd, sys_prompt2, usr_prompt2, max_tok2],
                       outputs=tier_out, api_name="call_tier")

    with gr.Tab("Health Dashboard"):
        health_out = gr.Markdown("Click 'Run Health Check' to test all models...")
        health_btn = gr.Button("Run Health Check (tests all models, ~15s)", variant="primary")
        health_btn.click(fn=gradio_health_check, outputs=health_out, api_name="health_check")

    with gr.Tab("Models"):
        models_out = gr.Textbox(label="Registered Models", lines=20, value=gradio_list_models())
        refresh_btn = gr.Button("Refresh")
        refresh_btn.click(fn=gradio_list_models, outputs=models_out, api_name="list_models")


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        print("\n🔍 Running health check...")
        print(run_health_check())
        print("\n📊 Dashboard:")
        print(get_health_dashboard())
    else:
        demo.launch(server_name="0.0.0.0", server_port=7860)
