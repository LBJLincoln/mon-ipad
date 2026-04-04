#!/usr/bin/env python3
"""
Free Models Integration — multi-provider council advisors
==========================================================
Provides `query_free_llm(prompt, model="qwen") -> str` for department councils.

Design constraints:
  - stdlib ONLY (no openai, anthropic, langchain) — compatible with 1 vCPU / 969 MB RAM VM
  - Multi-provider fallback: Cerebras → Groq → OpenRouter → HF Inference API
  - All providers are OpenAI-compatible (POST /v1/chat/completions)

Provider summary (as of Apr 4 2026):
  CEREBRAS (primary):
    - qwen3_235b: qwen-3-235b-a22b-instruct-2507 — 235B MoE, 1400 tps, 64K ctx, 1M tokens/day FREE
    - qwen3_32b:  qwen-3-32b                     — 32B, 2600 tps, 131K ctx, 1M tokens/day FREE
    - llama33:    llama3.3-70b                   — 70B, fast, 131K ctx, FREE
  GROQ (fast fallback):
    - llama4:     meta-llama/llama-4-scout-17b-16e-instruct — 750 tps, 131K ctx, 1K RPD FREE
    - llama8b:    llama-3.1-8b-instant           — 14400 RPD, 20K TPM, best for bulk queries
    - qwen32b:    qwen-qwq-32b                   — 32B reasoning, 60 RPM FREE
  OPENROUTER (long-context):
    - qwen36:     qwen/qwen3.6-plus:free         — 1M ctx, 600 RPM, $0 FREE
    - gemma3_27b: google/gemma-3-27b-it:free     — 131K ctx, FREE
    - mistral_or: mistralai/mistral-small-3.1-24b-instruct:free — FREE
  HF INFERENCE (fallback only — $0.10/month free credit limit):
    - mistral_hf: mistralai/Mistral-Small-3.1-24B-Instruct-2503
    - phi:        microsoft/phi-4

CORRECTION from previous version:
  - google/gemma-4-27b-it DOES NOT EXIST. Correct IDs: E2B, E4B, 26B-A4B, 31B.
    Gemma 4 is NOT available on HF Inference Providers yet (weights only as of Apr 4 2026).
  - Qwen/Qwen3.6-Plus DOES NOT EXIST as open weights. Cloud-only (Alibaba).
    Free access only via OpenRouter: qwen/qwen3.6-plus:free

Usage in a department council:
    from scripts.forge.free_models_integration import query_free_llm, CouncilAdvisor

    # Simple one-shot query
    answer = query_free_llm(
        "Should we cross-pollinate S12 → S10? S12 brier=0.221, S10 brier=0.225",
        model="qwen"
    )
    print(answer)

    # Structured council decision (SCAN data → YES/NO + reasoning)
    advisor = CouncilAdvisor(dept="evolution")
    decision = advisor.advise(scan_data={...}, question="Should we cross-pollinate?")
    print(decision)

    # Multi-model council vote (3 models, majority rules)
    vote = advisor.vote(scan_data={...}, question="Should we increase mutation rate?")
    print(vote)  # {"decision": "YES", "votes": {"qwen": "YES", "gemma": "YES", "mistral": "NO"}}
"""

import os
import json
import time
import urllib.request
import urllib.parse
import ssl
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

# ══════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════

_SCRIPT_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _SCRIPT_DIR / "free_models_config.json"

def _load_config() -> dict:
    try:
        with open(_CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}

_CFG = _load_config()

# ══════════════════════════════════════════════════════════
# PROVIDER CONFIG
# ══════════════════════════════════════════════════════════

# Provider base URLs (all OpenAI-compatible /v1/chat/completions)
PROVIDER_URLS = {
    "cerebras":    "https://api.cerebras.ai/v1/chat/completions",
    "groq":        "https://api.groq.com/openai/v1/chat/completions",
    "openrouter":  "https://openrouter.ai/api/v1/chat/completions",
    "hf":          "https://api-inference.huggingface.co/v1/chat/completions",
}

# Model registry: short alias → (provider, model_id)
# Primary: Cerebras Qwen3-235B — best free quality, 1M tokens/day
# Fallbacks ordered by quality/availability
MODELS: Dict[str, tuple] = {
    # Primary council models
    "qwen":        ("cerebras",   "qwen-3-235b-a22b-instruct-2507"),   # 235B MoE, 1400 tps
    "qwen_fast":   ("cerebras",   "qwen-3-32b"),                        # 32B, 2600 tps
    "llama4":      ("groq",       "meta-llama/llama-4-scout-17b-16e-instruct"),  # 750 tps, 1K RPD
    "llama8b":     ("groq",       "llama-3.1-8b-instant"),             # 14400 RPD bulk
    "llama70b":    ("groq",       "llama-3.3-70b-versatile"),          # 70B, 1K RPD
    "qwen36":      ("openrouter", "qwen/qwen3.6-plus:free"),           # 1M ctx, 600 RPM
    "gemma3":      ("openrouter", "google/gemma-3-27b-it:free"),       # Gemma 3, 131K ctx
    "mistral":     ("openrouter", "mistralai/mistral-small-3.1-24b-instruct:free"),  # fast
    "deepseek":    ("openrouter", "deepseek/deepseek-r1:free"),        # reasoning
    # HF fallback (limited credits — use sparingly)
    "phi":         ("hf",         "microsoft/phi-4"),                   # 16K ctx
    "mistral_hf":  ("hf",         "mistralai/Mistral-Small-3.1-24B-Instruct-2503"),
}

# Legacy alias compatibility (old code using "gemma" will now get gemma3 from OpenRouter)
MODELS["gemma"] = MODELS["gemma3"]

# HF Inference API base URL (legacy text-generation endpoint for non-chat models)
HF_API_BASE = "https://api-inference.huggingface.co/models"

# Account token env vars (try in order until one works)
TOKEN_ENV_VARS = ["HF_TOKEN", "HF_TOKEN_2", "HF_TOKEN_3"]

# Reasonable defaults for council queries (short, decisive answers)
DEFAULT_MAX_TOKENS = 512
DEFAULT_TEMPERATURE = 0.3   # Low temp for consistent council decisions
DEFAULT_TIMEOUT_SEC = 60

# Rate limiting: track last call time per token
_last_call: Dict[str, float] = {}
_MIN_INTERVAL_SEC = 2.0  # Min seconds between calls with same token


# ══════════════════════════════════════════════════════════
# TOKEN MANAGEMENT
# ══════════════════════════════════════════════════════════

def get_token(provider: str = "hf", prefer_env: Optional[str] = None) -> str:
    """Return the API token for a given provider.

    Provider token env vars:
      cerebras  → CEREBRAS_API_KEY
      groq      → GROQ_API_KEY
      openrouter→ OPENROUTER_API_KEY
      hf        → HF_TOKEN / HF_TOKEN_2 / HF_TOKEN_3
    """
    if prefer_env:
        tok = os.environ.get(prefer_env, "").strip()
        if tok:
            return tok

    provider_env_map = {
        "cerebras":   ["CEREBRAS_API_KEY"],
        "groq":       ["GROQ_API_KEY"],
        "openrouter": ["OPENROUTER_API_KEY"],
        "hf":         TOKEN_ENV_VARS,
    }

    env_vars = provider_env_map.get(provider, TOKEN_ENV_VARS)
    for env_var in env_vars:
        tok = os.environ.get(env_var, "").strip()
        if tok:
            return tok

    return ""


def _rate_limit(token: str):
    """Enforce minimum interval between calls with the same token."""
    now = time.time()
    last = _last_call.get(token, 0)
    wait = _MIN_INTERVAL_SEC - (now - last)
    if wait > 0:
        time.sleep(wait)
    _last_call[token] = time.time()


# ══════════════════════════════════════════════════════════
# CORE INFERENCE
# ══════════════════════════════════════════════════════════

def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _call_chat_completions(
    provider: str,
    model_id: str,
    prompt: str,
    token: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> str:
    """Call any OpenAI-compatible /v1/chat/completions endpoint.

    Supports: cerebras, groq, openrouter, hf (all use same wire format).
    Returns the generated text string, or "" on failure.
    """
    _rate_limit(token)

    url = PROVIDER_URLS.get(provider)
    if not url:
        return ""

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "Nomos42-CouncilAdvisor/1.0",
    }
    # OpenRouter requires HTTP-Referer header
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://nomos42.com"
        headers["X-Title"] = "Nomos42 NBA Council"

    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            result = json.loads(resp.read())
            choices = result.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                if content:
                    return content.strip()
    except urllib.error.HTTPError as e:
        if e.code == 503:
            # HF model loading — wait and retry once
            if provider == "hf":
                time.sleep(20)
                try:
                    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
                    with urllib.request.urlopen(req, timeout=timeout + 30, context=_ssl_ctx()) as resp:
                        result = json.loads(resp.read())
                        choices = result.get("choices", [])
                        if choices:
                            return choices[0].get("message", {}).get("content", "").strip()
                except Exception:
                    pass
    except Exception:
        pass

    # HF fallback: legacy text generation endpoint (for older models)
    if provider == "hf":
        legacy_url = f"{HF_API_BASE}/{model_id}"
        legacy_payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "return_full_text": False,
            },
        }
        try:
            data = json.dumps(legacy_payload).encode("utf-8")
            req = urllib.request.Request(legacy_url, data=data, method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
                result = json.loads(resp.read())
                if isinstance(result, list) and result:
                    text = result[0].get("generated_text", "")
                    if text:
                        return text.strip()
                elif isinstance(result, dict):
                    text = result.get("generated_text", "")
                    if text:
                        return text.strip()
        except Exception:
            pass

    return ""


# ══════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════

def query_free_llm(
    prompt: str,
    model: str = "qwen",
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    token_env: Optional[str] = None,
    fallback_models: Optional[List[str]] = None,
) -> str:
    """Query a free LLM for a text response using the best available provider.

    Provider priority: Cerebras → Groq → OpenRouter → HF Inference API.

    Args:
        prompt:          The prompt to send.
        model:           Alias from MODELS dict, e.g. "qwen", "llama4", "gemma3", "phi".
                         Or a tuple (provider, model_id) for direct addressing.
        max_tokens:      Max tokens to generate (default 512).
        temperature:     Sampling temperature (default 0.3 for deterministic council decisions).
        token_env:       Force a specific env var for the token (overrides provider default).
        fallback_models: List of model aliases to try if the primary model fails.

    Returns:
        Generated text string, or "" if all models fail.

    Examples:
        # Cerebras Qwen3-235B (primary)
        answer = query_free_llm("What is the Kelly Criterion?", model="qwen")

        # Groq Llama4 Scout (fast, 750 tps)
        fast = query_free_llm("YES/NO: cross-pollinate?", model="llama4", max_tokens=50)

        # OpenRouter Qwen3.6-Plus (1M context)
        long = query_free_llm(very_long_prompt, model="qwen36")
    """
    # Resolve (provider, model_id) tuple
    if isinstance(model, tuple):
        provider, model_id = model
    elif model in MODELS:
        provider, model_id = MODELS[model]
    else:
        # Assume raw HF model ID passed directly
        provider, model_id = "hf", model

    token = get_token(provider=provider, prefer_env=token_env)

    if not token:
        # Try fallback providers automatically
        for alt_provider in ["cerebras", "groq", "openrouter", "hf"]:
            if alt_provider != provider:
                alt_token = get_token(provider=alt_provider)
                if alt_token:
                    provider = alt_provider
                    token = alt_token
                    break

    if not token:
        return "[ERROR: No API token found. Set CEREBRAS_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, or HF_TOKEN.]"

    # Primary attempt
    result = _call_chat_completions(provider, model_id, prompt, token, max_tokens, temperature)
    if result:
        return result

    # Try explicit fallback models
    if fallback_models:
        for fallback in fallback_models:
            if fallback in MODELS:
                fb_provider, fb_model_id = MODELS[fallback]
                fb_token = get_token(provider=fb_provider)
                if fb_token:
                    result = _call_chat_completions(fb_provider, fb_model_id, prompt, fb_token, max_tokens, temperature)
                    if result:
                        return result

    # Auto-fallback chain: try all providers in priority order with their best model
    auto_fallback = [
        ("cerebras",   "qwen-3-235b-a22b-instruct-2507"),
        ("groq",       "llama-3.1-8b-instant"),
        ("openrouter", "qwen/qwen3.6-plus:free"),
        ("hf",         "microsoft/phi-4"),
    ]
    for fb_provider, fb_model_id in auto_fallback:
        if fb_provider == provider and fb_model_id == model_id:
            continue  # Already tried
        fb_token = get_token(provider=fb_provider)
        if fb_token:
            result = _call_chat_completions(fb_provider, fb_model_id, prompt, fb_token, max_tokens, temperature)
            if result:
                return result

    return ""


# ══════════════════════════════════════════════════════════
# COUNCIL ADVISOR CLASS
# ══════════════════════════════════════════════════════════

# System prompt templates per department
DEPT_SYSTEM_PROMPTS: Dict[str, str] = {
    "evolution": (
        "You are an NBA AI evolution advisor. You analyze Brier scores (lower=better), "
        "stagnation patterns, and genetic diversity for an NBA game prediction system. "
        "Be terse and decisive. Always give a clear YES/NO recommendation."
    ),
    "engineering": (
        "You are a senior ML engineer for an NBA prediction system. "
        "You review feature engineering, model configs, and Brier score improvements. "
        "Be terse and decisive. Always give a clear recommendation."
    ),
    "research": (
        "You are an ML research analyst. You evaluate techniques from papers and repos "
        "for NBA game prediction (improving Brier score below 0.215). "
        "Be terse. Prioritize actionable techniques."
    ),
    "evaluation": (
        "You are an NBA prediction evaluator. You assess calibration, Brier scores, ECE, "
        "and ROI metrics. Flag regressions decisively. Be terse."
    ),
    "betting": (
        "You are a sports betting strategist using Kelly Criterion and value betting. "
        "You analyze NBA edges and ROI. Be terse and quantitative."
    ),
    "infra": (
        "You are a DevOps engineer for a 1-vCPU/969MB VM running an NBA AI system. "
        "You monitor disk, memory, HF Spaces health. Be terse. Flag critical issues immediately."
    ),
    "default": (
        "You are an AI advisor for a quantitative NBA prediction system. "
        "Be terse, precise, and give clear actionable recommendations."
    ),
}


class CouncilAdvisor:
    """High-level interface for department councils to query free LLMs.

    Formats the prompt with department context, queries the LLM,
    and parses YES/NO decisions for structured council loops.

    Example:
        advisor = CouncilAdvisor(dept="evolution", model="qwen")
        decision = advisor.advise(
            scan_data={"best_fleet_brier": 0.225, "stagnant_islands": 3},
            question="Should we cross-pollinate the 3 stagnant islands?",
        )
        # decision = {"recommendation": "YES", "reasoning": "...", "model": "qwen"}
    """

    def __init__(
        self,
        dept: str = "default",
        model: str = "qwen",       # Default: Cerebras Qwen3-235B (best free quality)
        max_tokens: int = 256,
        temperature: float = 0.3,
    ):
        self.dept = dept
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.system_prompt = DEPT_SYSTEM_PROMPTS.get(dept, DEPT_SYSTEM_PROMPTS["default"])

    def _build_prompt(self, scan_data: dict, question: str) -> str:
        """Build a compact council decision prompt."""
        scan_str = json.dumps(scan_data, indent=None, separators=(",", ":"))
        if len(scan_str) > 800:
            # Truncate large scan data to keep prompt short for VM speed
            scan_str = scan_str[:800] + "..."

        return (
            f"{self.system_prompt}\n\n"
            f"CURRENT STATE:\n{scan_str}\n\n"
            f"QUESTION: {question}\n\n"
            "Reply with: [YES/NO] <one sentence of reasoning>"
        )

    def advise(self, scan_data: dict, question: str) -> dict:
        """Query one LLM and return a structured decision.

        Returns:
            {
                "recommendation": "YES" or "NO",
                "reasoning": "...",
                "raw_response": "...",
                "model": "qwen",
                "dept": "evolution",
                "ts": "2026-04-03T...",
            }
        """
        prompt = self._build_prompt(scan_data, question)
        raw = query_free_llm(
            prompt,
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        # Parse YES/NO
        recommendation = "NO"
        reasoning = raw
        if raw:
            upper = raw.upper()
            if upper.startswith("YES") or " YES " in upper[:50] or upper.startswith("[YES]"):
                recommendation = "YES"
            elif upper.startswith("NO") or " NO " in upper[:50] or upper.startswith("[NO]"):
                recommendation = "NO"
            # Extract reasoning (everything after YES/NO keyword)
            for prefix in ["YES ", "NO ", "[YES] ", "[NO] "]:
                if raw.upper().startswith(prefix.upper()):
                    reasoning = raw[len(prefix):].strip()
                    break

        return {
            "recommendation": recommendation,
            "reasoning": reasoning,
            "raw_response": raw,
            "model": self.model,
            "dept": self.dept,
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    def vote(
        self,
        scan_data: dict,
        question: str,
        models: Optional[List[str]] = None,
    ) -> dict:
        """Query multiple models and return a majority vote.

        Uses 3 models by default (qwen, gemma, mistral).
        Returns the majority YES/NO plus individual votes.

        Args:
            scan_data: Current department scan data.
            question:  Decision question.
            models:    List of model aliases to vote. Default: ["qwen", "gemma", "mistral"].

        Returns:
            {
                "decision": "YES" or "NO",
                "votes": {"qwen": "YES", "gemma": "NO", "mistral": "YES"},
                "vote_count": {"YES": 2, "NO": 1},
                "reasoning": {...},
                "ts": "...",
            }
        """
        if models is None:
            models = ["qwen", "gemma", "mistral"]

        votes: Dict[str, str] = {}
        reasoning: Dict[str, str] = {}

        for model_alias in models:
            original_model = self.model
            self.model = model_alias
            result = self.advise(scan_data, question)
            self.model = original_model

            votes[model_alias] = result["recommendation"]
            reasoning[model_alias] = result["reasoning"]

        # Tally
        yes_count = sum(1 for v in votes.values() if v == "YES")
        no_count = len(votes) - yes_count
        decision = "YES" if yes_count > no_count else "NO"

        return {
            "decision": decision,
            "votes": votes,
            "vote_count": {"YES": yes_count, "NO": no_count},
            "reasoning": reasoning,
            "ts": datetime.now(timezone.utc).isoformat(),
        }


# ══════════════════════════════════════════════════════════
# COUNCIL INTEGRATION HELPERS
# (pre-built prompts for common department decisions)
# ══════════════════════════════════════════════════════════

def advise_cross_pollinate(scan_data: dict, source: str, target: str) -> dict:
    """Should we cross-pollinate a source island config to a target island?"""
    advisor = CouncilAdvisor(dept="evolution", model="qwen")
    return advisor.advise(
        scan_data,
        f"Should we cross-pollinate config from {source} to {target}? "
        "Consider Brier scores, stagnation, and diversity."
    )


def advise_mutation_rate(scan_data: dict) -> dict:
    """Should we increase the mutation rate due to stagnation?"""
    advisor = CouncilAdvisor(dept="evolution", model="qwen")
    return advisor.advise(
        scan_data,
        "Should we increase the mutation rate to escape a local minimum? "
        "Current mutation_rate and stagnation_cycles are in the scan data."
    )


def advise_feature_injection(scan_data: dict, category: str) -> dict:
    """Should we inject a new feature category into the evolution pool?"""
    advisor = CouncilAdvisor(dept="engineering", model="qwen")
    return advisor.advise(
        scan_data,
        f"Should we inject features from category '{category}' into the evolution pool? "
        "Evaluate based on current Brier gap to ATR (0.21570)."
    )


def advise_betting_strategy(scan_data: dict) -> dict:
    """Which betting strategy should we prioritize today?"""
    advisor = CouncilAdvisor(dept="betting", model="gemma")
    return advisor.advise(
        scan_data,
        "Which betting strategy should we prioritize: value_hunter, half_kelly, or full_kelly? "
        "Base decision on current ROI, Sharpe, and bankroll."
    )


def summarize_council_state(dept: str, scan_data: dict) -> str:
    """Get a brief LLM summary of the department's current state for dashboards."""
    system = DEPT_SYSTEM_PROMPTS.get(dept, DEPT_SYSTEM_PROMPTS["default"])
    scan_str = json.dumps(scan_data, separators=(",", ":"))[:600]
    prompt = (
        f"{system}\n\n"
        f"CURRENT STATE:\n{scan_str}\n\n"
        "Write a 2-sentence status summary for the department dashboard. "
        "Include the most important metric and any urgent issues."
    )
    return query_free_llm(prompt, model="mistral", max_tokens=150, temperature=0.4)


# ══════════════════════════════════════════════════════════
# CLI — test / demo
# ══════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Free Models Integration — Council Advisor")
    parser.add_argument("--query", type=str, help="Simple query to test LLM connectivity")
    parser.add_argument("--model", default="qwen", choices=list(MODELS.keys()),
                        help="Model alias (default: qwen = Cerebras Qwen3-235B)")
    parser.add_argument("--dept", default="evolution", help="Department context for advisor")
    parser.add_argument("--demo-vote", action="store_true",
                        help="Run a demo council vote with fake evolution data")
    parser.add_argument("--list-models", action="store_true", help="List available models")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args()

    if args.list_models:
        print("Available free models (multi-provider):")
        print(f"  {'alias':15s}  {'provider':12s}  model_id")
        print(f"  {'-'*15}  {'-'*12}  {'-'*45}")
        for alias, (provider, model_id) in MODELS.items():
            print(f"  {alias:15s}  {provider:12s}  {model_id}")
        return

    provider, model_id = MODELS.get(args.model, ("hf", args.model))
    token = get_token(provider=provider)
    if not token:
        print(f"WARNING: No token for provider '{provider}'. Will try auto-fallback.")
        token = get_token()
    if not token:
        print("ERROR: No API tokens found. Set CEREBRAS_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, or HF_TOKEN.")
        return

    print(f"Provider: {provider} | Token: {'*' * 8}{token[-4:]}")
    print(f"Model: {args.model} → {model_id}")

    if args.query:
        print(f"\nQuery: {args.query}")
        print("Response:")
        result = query_free_llm(args.query, model=args.model, max_tokens=args.max_tokens)
        print(result or "[No response]")

    elif args.demo_vote:
        print(f"\nDemo council vote — dept: {args.dept}")
        demo_scan = {
            "best_fleet_brier": 0.22408,
            "stagnant_islands": 3,
            "total_generations": 39712,
            "all_up": True,
            "fleet_size": 6,
        }
        advisor = CouncilAdvisor(dept=args.dept, model=args.model)
        # Use fast models: Groq llama8b (14400 RPD) + Cerebras qwen for vote
        vote = advisor.vote(
            demo_scan,
            "Should we trigger a cross-pollination event to reduce stagnation?",
            models=["qwen", "llama8b"],
        )
        print(json.dumps(vote, indent=2))

    else:
        # Default: connectivity test
        print("\nRunning connectivity test...")
        test_prompt = (
            "NBA prediction AI question: "
            "S12 Brier=0.221, S10 Brier=0.225. Should we cross-pollinate? Reply YES or NO."
        )
        result = query_free_llm(test_prompt, model=args.model, max_tokens=50)
        if result:
            print(f"SUCCESS — response: {result}")
        else:
            print("FAILED — no response from API. Check token and model availability.")
            print(f"Token prefix: {token[:8]}...")
            print(f"Model: {MODELS[args.model]}")


if __name__ == "__main__":
    main()
