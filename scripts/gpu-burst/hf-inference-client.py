#!/usr/bin/env python3
"""
Nomos42 -- HF Inference Client for Council Advisor LLM Voting
==============================================================
Uses HuggingFace Inference API for free model queries.
Models: Gemma 4 27B, Qwen 3.6 Plus (serverless inference).

Functions:
    query_gemma4(prompt)          -- Gemma 4 27B IT
    query_qwen36(prompt)          -- Qwen 3.6 Plus
    query_best_available(prompt)  -- Try best model first, fall back

Used by council advisor system for:
    - Evolution strategy voting (which experiments to prioritize)
    - Feature importance analysis (which features look promising)
    - Model selection advice (which model type for current data)
    - Risk assessment (should we bet on this edge?)

Usage:
    python3 scripts/gpu-burst/hf-inference-client.py                    # Run tests
    python3 scripts/gpu-burst/hf-inference-client.py --query "..."      # Single query
    python3 scripts/gpu-burst/hf-inference-client.py --council "..."    # Council vote

As library:
    from scripts.gpu_burst.hf_inference_client import query_best_available
    response = query_best_available("What features should we add?")
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

# ══════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════

REPO_ROOT = Path("/home/termius/mon-ipad")
RESULT_DIR = REPO_ROOT / "data" / "gpu-burst"
LOG_FILE = RESULT_DIR / "hf-inference-log.jsonl"

# Model registry -- serverless inference endpoints (free tier)
# These run on HF's shared GPU pool, no cost to us.
MODELS = {
    "gemma4_27b": {
        "model_id": "google/gemma-3-27b-it",
        "display_name": "Gemma 3 27B IT",
        "provider": "Google",
        "max_tokens": 1024,
        "temperature": 0.7,
        "priority": 1,  # Try first
    },
    "qwen3_plus": {
        "model_id": "Qwen/Qwen2.5-72B-Instruct",
        "display_name": "Qwen 2.5 72B Instruct",
        "provider": "Alibaba",
        "max_tokens": 1024,
        "temperature": 0.7,
        "priority": 2,
    },
    "llama31_8b": {
        "model_id": "meta-llama/Llama-3.1-8B-Instruct",
        "display_name": "Llama 3.1 8B Instruct",
        "provider": "Meta",
        "max_tokens": 1024,
        "temperature": 0.7,
        "priority": 3,
    },
    "qwen25_7b": {
        "model_id": "Qwen/Qwen2.5-7B-Instruct",
        "display_name": "Qwen 2.5 7B Instruct",
        "provider": "Alibaba",
        "max_tokens": 1024,
        "temperature": 0.7,
        "priority": 4,  # Smallest, most reliable fallback
    },
}

# Account rotation for rate limit management
ACCOUNTS = [
    {"name": "LBJLincoln", "token_env": "HF_TOKEN"},
    {"name": "LBJLincoln26", "token_env": "HF_TOKEN_2"},
    {"name": "Nomos42", "token_env": "HF_TOKEN_3"},
]

# System prompts for different council roles
COUNCIL_PROMPTS = {
    "evolution": (
        "You are an AI evolution strategist for NBA prediction models. "
        "You advise on feature selection, model architecture, and hyperparameter tuning. "
        "Your goal is to minimize Brier score (currently 0.21570, target < 0.20). "
        "Be concise and actionable. Respond in JSON when asked."
    ),
    "betting": (
        "You are a quantitative betting strategist. "
        "You advise on Kelly sizing, bankroll management, and edge detection. "
        "Your goal is to maximize ROI while maintaining a Sharpe ratio > 1.5. "
        "Be precise with numbers and probabilities."
    ),
    "research": (
        "You are an ML research advisor specializing in sports prediction. "
        "You analyze papers, suggest techniques, and evaluate research proposals. "
        "Focus on practical improvements that can be implemented in < 1 hour."
    ),
    "risk": (
        "You are a risk analyst for a sports prediction system. "
        "You evaluate model confidence, identify potential failures, "
        "and flag when predictions might be unreliable. Be conservative."
    ),
}


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_entry(entry: dict):
    """Append to JSONL log."""
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ══════════════════════════════════════════════════════════
# INFERENCE CLIENT
# ══════════════════════════════════════════════════════════

def _get_client(token: Optional[str] = None):
    """Get HuggingFace InferenceClient."""
    from huggingface_hub import InferenceClient

    if token is None:
        # Try accounts in order
        for account in ACCOUNTS:
            t = os.environ.get(account["token_env"], "")
            if t:
                token = t
                break

    if not token:
        raise ValueError(
            "No HF token found. Set HF_TOKEN, HF_TOKEN_2, or HF_TOKEN_3 env var."
        )

    return InferenceClient(token=token)


def _query_model(
    model_key: str,
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    token: Optional[str] = None,
) -> Optional[str]:
    """Query a specific model via HF Inference API."""
    if model_key not in MODELS:
        print(f"[WARN] Unknown model: {model_key}")
        return None

    model_cfg = MODELS[model_key]
    model_id = model_cfg["model_id"]

    try:
        client = _get_client(token)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        t0 = time.time()
        response = client.chat_completion(
            model=model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        elapsed = time.time() - t0

        if response and response.choices:
            content = response.choices[0].message.content
            usage = response.usage

            log_entry({
                "ts": ts(),
                "model": model_key,
                "model_id": model_id,
                "prompt_len": len(prompt),
                "response_len": len(content) if content else 0,
                "elapsed_sec": round(elapsed, 2),
                "tokens_in": usage.prompt_tokens if usage else None,
                "tokens_out": usage.completion_tokens if usage else None,
                "status": "ok",
            })

            return content

    except Exception as e:
        error_str = str(e)
        # Common errors: rate limit, model loading, quota exceeded
        if "rate limit" in error_str.lower() or "429" in error_str:
            print(f"[RATE_LIMIT] {model_key}: {error_str[:100]}")
        elif "loading" in error_str.lower() or "503" in error_str:
            print(f"[LOADING] {model_key}: model is loading, try again in ~30s")
        else:
            print(f"[ERROR] {model_key}: {error_str[:150]}")

        log_entry({
            "ts": ts(),
            "model": model_key,
            "model_id": model_id,
            "status": "error",
            "error": error_str[:200],
        })

    return None


# ══════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════

def query_gemma4(
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 1024,
) -> Optional[str]:
    """Query Google Gemma 3 27B IT via HF Inference API."""
    return _query_model(
        "gemma4_27b", prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
    )


def query_qwen36(
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 1024,
) -> Optional[str]:
    """Query Qwen 2.5 72B Instruct via HF Inference API."""
    return _query_model(
        "qwen3_plus", prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
    )


def query_llama31(
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 1024,
) -> Optional[str]:
    """Query Meta Llama 3.1 8B Instruct via HF Inference API."""
    return _query_model(
        "llama31_8b", prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
    )


def query_qwen25_7b(
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 1024,
) -> Optional[str]:
    """Query Qwen 2.5 7B Instruct via HF Inference API."""
    return _query_model(
        "qwen25_7b", prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
    )


def query_best_available(
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 1024,
    fallback_chain: Optional[List[str]] = None,
) -> Optional[str]:
    """Try best model first, fall back through chain until one responds.

    Default chain: gemma4_27b -> qwen3_plus -> mistral_large -> phi4
    """
    if fallback_chain is None:
        # Sort by priority
        fallback_chain = sorted(MODELS.keys(), key=lambda k: MODELS[k]["priority"])

    for model_key in fallback_chain:
        print(f"[QUERY] Trying {MODELS[model_key]['display_name']}...")
        result = _query_model(
            model_key, prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )
        if result:
            print(f"[QUERY] Got response from {MODELS[model_key]['display_name']} "
                  f"({len(result)} chars)")
            return result
        # Brief pause between attempts to avoid rate limiting
        time.sleep(1)

    print("[QUERY] All models failed")
    return None


# ══════════════════════════════════════════════════════════
# COUNCIL VOTING
# ══════════════════════════════════════════════════════════

def council_vote(
    question: str,
    role: str = "evolution",
    models: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run a council vote: multiple models answer the same question.

    Returns a dict with each model's response and a synthesized consensus.

    Args:
        question: The question to ask the council
        role: Council role (evolution, betting, research, risk)
        models: Which models to poll (default: all available)

    Returns:
        {
            "question": str,
            "role": str,
            "votes": {"model_key": "response", ...},
            "n_responses": int,
            "timestamp": str,
        }
    """
    system_prompt = COUNCIL_PROMPTS.get(role, COUNCIL_PROMPTS["evolution"])

    if models is None:
        models = sorted(MODELS.keys(), key=lambda k: MODELS[k]["priority"])

    votes = {}
    for model_key in models:
        print(f"[COUNCIL] Polling {MODELS[model_key]['display_name']}...")
        response = _query_model(
            model_key, question,
            system_prompt=system_prompt,
            max_tokens=512,
        )
        if response:
            votes[model_key] = response
            print(f"  --> {MODELS[model_key]['display_name']}: {response[:80]}...")
        else:
            votes[model_key] = None
            print(f"  --> {MODELS[model_key]['display_name']}: NO RESPONSE")
        time.sleep(1)  # Rate limit courtesy

    result = {
        "question": question,
        "role": role,
        "votes": votes,
        "n_responses": sum(1 for v in votes.values() if v),
        "n_models": len(models),
        "timestamp": ts(),
    }

    # Log the council session
    log_entry({
        "ts": ts(),
        "type": "council_vote",
        "role": role,
        "question_len": len(question),
        "n_responses": result["n_responses"],
        "n_models": result["n_models"],
        "models_responded": [k for k, v in votes.items() if v],
    })

    return result


# ══════════════════════════════════════════════════════════
# MODEL STATUS CHECK
# ══════════════════════════════════════════════════════════

def check_model_status() -> Dict[str, str]:
    """Quick health check of all models. Returns status per model."""
    statuses = {}
    test_prompt = "Say 'OK' in one word."

    for model_key, model_cfg in sorted(MODELS.items(), key=lambda x: x[1]["priority"]):
        print(f"Testing {model_cfg['display_name']}...", end=" ", flush=True)
        t0 = time.time()
        result = _query_model(model_key, test_prompt, max_tokens=10, temperature=0.1)
        elapsed = time.time() - t0

        if result:
            statuses[model_key] = f"OK ({elapsed:.1f}s)"
            print(f"OK ({elapsed:.1f}s) -> '{result.strip()[:30]}'")
        else:
            statuses[model_key] = "FAIL"
            print("FAIL")

    return statuses


# ══════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="HF Inference Client for Nomos42 Council Advisors"
    )
    parser.add_argument(
        "--query", type=str, default=None,
        help="Single query to best available model"
    )
    parser.add_argument(
        "--model", type=str, default=None,
        choices=list(MODELS.keys()),
        help="Specific model to query"
    )
    parser.add_argument(
        "--council", type=str, default=None,
        help="Run council vote with all models on this question"
    )
    parser.add_argument(
        "--role", type=str, default="evolution",
        choices=list(COUNCIL_PROMPTS.keys()),
        help="Council role/system prompt (default: evolution)"
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Test all models with a simple query"
    )

    args = parser.parse_args()

    # Load env
    env_file = REPO_ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                # Strip 'export ' prefix if present
                if line.startswith("export "):
                    line = line[7:]
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and val and key not in os.environ:
                    os.environ[key] = val

    if args.test:
        print("=" * 60)
        print("  HF Inference Client -- Model Health Check")
        print("=" * 60)
        statuses = check_model_status()
        print("\n" + "=" * 60)
        print("  Summary:")
        for model_key, status in statuses.items():
            name = MODELS[model_key]["display_name"]
            print(f"  {name:30s} {status}")
        ok_count = sum(1 for s in statuses.values() if s.startswith("OK"))
        print(f"\n  {ok_count}/{len(statuses)} models available")
        print("=" * 60)

    elif args.council:
        print("=" * 60)
        print(f"  Council Vote (role: {args.role})")
        print("=" * 60)
        result = council_vote(args.council, role=args.role)
        print(f"\n{'=' * 60}")
        print(f"  Results: {result['n_responses']}/{result['n_models']} responded")
        for model_key, response in result["votes"].items():
            name = MODELS[model_key]["display_name"]
            if response:
                # Truncate long responses for display
                display = response[:200] + "..." if len(response) > 200 else response
                print(f"\n  [{name}]:")
                print(f"  {display}")
            else:
                print(f"\n  [{name}]: NO RESPONSE")
        print("=" * 60)

    elif args.query:
        if args.model:
            result = _query_model(args.model, args.query)
        else:
            result = query_best_available(args.query)

        if result:
            print(f"\n{result}")
        else:
            print("No response from any model", file=sys.stderr)
            sys.exit(1)

    else:
        # Default: run tests
        print("Running model health check (use --help for options)...")
        print()
        statuses = check_model_status()
        ok_count = sum(1 for s in statuses.values() if s.startswith("OK"))
        print(f"\n{ok_count}/{len(statuses)} models available")

        if ok_count > 0:
            print("\nTesting council vote...")
            result = council_vote(
                "What is the single most impactful feature category for NBA game prediction? "
                "Answer in one sentence.",
                role="evolution",
            )
            print(f"Council: {result['n_responses']}/{result['n_models']} responded")


if __name__ == "__main__":
    main()
