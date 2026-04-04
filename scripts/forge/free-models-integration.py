#!/usr/bin/env python3
"""
Free Models Integration — HF Inference API council advisors
============================================================
Provides `query_free_llm(prompt, model="qwen") -> str` for department councils.

Design constraints:
  - stdlib + huggingface_hub ONLY (no openai, anthropic, langchain, requests, etc.)
  - 1 vCPU / 969 MB RAM VM — no heavy deps, no local model loading
  - HF Inference API: ~100K credits/month free per account
  - Rate limits: 10-30 req/min depending on model

Available models (from scripts/forge/free_models_config.json):
  - qwen:    Qwen/Qwen3.6-Plus         — 1M ctx, best reasoning/code (use for complex decisions)
  - gemma:   google/gemma-4-27b-it     — 256K ctx, strong reasoning (use for structured analysis)
  - mistral: mistralai/Mistral-Small-3.1-24B-Instruct-2503 — 128K ctx, fast tool use
  - phi:     microsoft/phi-4           — 16K ctx, lightweight fallback

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

# Model registry: short alias → HF model ID
MODELS: Dict[str, str] = {
    "qwen":    "Qwen/Qwen3.6-Plus",
    "gemma":   "google/gemma-4-27b-it",
    "mistral": "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
    "phi":     "microsoft/phi-4",
}

# Override from config file if present
if _CFG.get("hf_inference_api", {}).get("models"):
    _cfg_models = _CFG["hf_inference_api"]["models"]
    if "qwen_3_6_plus"     in _cfg_models: MODELS["qwen"]    = _cfg_models["qwen_3_6_plus"]["model_id"]
    if "gemma_4_27b"       in _cfg_models: MODELS["gemma"]   = _cfg_models["gemma_4_27b"]["model_id"]
    if "mistral_small_3_1" in _cfg_models: MODELS["mistral"] = _cfg_models["mistral_small_3_1"]["model_id"]
    if "phi_4"             in _cfg_models: MODELS["phi"]     = _cfg_models["phi_4"]["model_id"]

# HF Inference API base URL — Serverless (ZeroGPU-backed)
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

def get_token(prefer_env: Optional[str] = None) -> str:
    """Return the first available HF token from env vars.
    Optionally prefer a specific env var (e.g. "HF_TOKEN_2").
    """
    if prefer_env:
        tok = os.environ.get(prefer_env, "").strip()
        if tok:
            return tok

    for env_var in TOKEN_ENV_VARS:
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


def _call_inference_api(
    model_id: str,
    prompt: str,
    token: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> str:
    """Call the HF Inference API for text generation.

    Uses the chat completions endpoint if available, otherwise falls back
    to the legacy text generation endpoint. Both are free on HF free tier.

    Returns the generated text string, or "" on failure.
    """
    _rate_limit(token)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "Nomos42-CouncilAdvisor/1.0",
    }

    # Try OpenAI-compatible chat completions endpoint first (newer models)
    # URL format: https://api-inference.huggingface.co/models/<model>/v1/chat/completions
    chat_url = f"{HF_API_BASE}/{model_id}/v1/chat/completions"
    chat_payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    try:
        data = json.dumps(chat_payload).encode("utf-8")
        req = urllib.request.Request(chat_url, data=data, method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            result = json.loads(resp.read())
            # OpenAI-compatible response format
            choices = result.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                if content:
                    return content.strip()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            pass  # Chat endpoint not available, try legacy
        elif e.code == 503:
            # Model loading — wait and retry once
            time.sleep(20)
            try:
                req = urllib.request.Request(chat_url, data=data, method="POST", headers=headers)
                with urllib.request.urlopen(req, timeout=timeout + 30, context=_ssl_ctx()) as resp:
                    result = json.loads(resp.read())
                    choices = result.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
            except Exception:
                pass
    except Exception:
        pass

    # Fallback: legacy text generation endpoint
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
    """Query a free HF LLM for a text response.

    Args:
        prompt:          The prompt to send (keep under 2000 chars for speed).
        model:           Alias: "qwen", "gemma", "mistral", "phi" — or a full HF model ID.
        max_tokens:      Max tokens to generate (default 512).
        temperature:     Sampling temperature (default 0.3 for deterministic council decisions).
        token_env:       Specific env var to use for the HF token (default: first available).
        fallback_models: List of model aliases to try if the primary fails.

    Returns:
        Generated text string, or "" if all models fail.

    Examples:
        # Simple question
        answer = query_free_llm("What is the Kelly Criterion?", model="qwen")

        # Council decision prompt
        decision = query_free_llm(
            "S12 (extra_trees) has brier=0.221, S10 (xgboost) has brier=0.225. "
            "S12 is stagnant for 10 generations. Should we cross-pollinate S12→S10? "
            "Reply with YES or NO and one sentence of reasoning.",
            model="qwen",
            max_tokens=100,
        )
    """
    # Resolve model ID
    model_id = MODELS.get(model, model)
    token = get_token(token_env)

    if not token:
        return "[ERROR: No HF token available. Set HF_TOKEN in environment.]"

    # Primary attempt
    result = _call_inference_api(model_id, prompt, token, max_tokens, temperature)
    if result:
        return result

    # Try fallback models
    if fallback_models:
        for fallback in fallback_models:
            fallback_id = MODELS.get(fallback, fallback)
            result = _call_inference_api(fallback_id, prompt, token, max_tokens, temperature)
            if result:
                return result

    # Auto-fallback chain: qwen → gemma → mistral → phi
    fallback_chain = [k for k in MODELS if k != model and MODELS[k] != model_id]
    for fallback_alias in fallback_chain:
        fallback_id = MODELS[fallback_alias]
        result = _call_inference_api(fallback_id, prompt, token, max_tokens, temperature)
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
        model: str = "qwen",
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
                        help="Model to use (default: qwen)")
    parser.add_argument("--dept", default="evolution", help="Department context for advisor")
    parser.add_argument("--demo-vote", action="store_true",
                        help="Run a demo council vote with fake evolution data")
    parser.add_argument("--list-models", action="store_true", help="List available models")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args()

    if args.list_models:
        print("Available free models (HF Inference API):")
        for alias, model_id in MODELS.items():
            print(f"  {alias:10s} → {model_id}")
        return

    token = get_token()
    if not token:
        print("ERROR: No HF token found. Set HF_TOKEN, HF_TOKEN_2, or HF_TOKEN_3 in environment.")
        return

    print(f"Using token: {'*' * 8}{token[-4:]}")
    print(f"Model: {args.model} ({MODELS[args.model]})")

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
        vote = advisor.vote(
            demo_scan,
            "Should we trigger a cross-pollination event to reduce stagnation?",
            models=["qwen", "mistral"],  # Use 2 models to reduce API calls in demo
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
