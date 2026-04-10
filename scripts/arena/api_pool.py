#!/usr/bin/env python3
"""
API POOL — Key Rotation + Rate Limiting for 200+ Trading Floor Agents
=====================================================================
All providers use OpenAI-compatible format (openai Python client with custom base_url).

Supports:
  - Groq (5 keys, 14,400 RPD per key for llama-3.1-8b)
  - OpenRouter (7 keys, 200 RPD per key for free models)
  - Cohere (2 keys, command-r-plus via OpenAI compat)
  - Cerebras (1 key, 1M tokens/day, 30 RPM)
  - Google Gemini (1 key, via OpenAI compat)
  - OpenAI (1 key, GPT-4o)
  - xAI (1 key, Grok)
  - Anthropic (CLI-based, via subprocess)
  - HuggingFace (4 tokens, Inference API via OpenAI compat)
"""

import os
import json
import time
import threading
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

# Try to import openai (required for all providers)
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    print("WARNING: openai package not installed. Run: pip install openai")


# ============================================================================
# PROVIDER CONFIGURATION
# ============================================================================
@dataclass
class ProviderConfig:
    """Configuration for a single API provider."""
    name: str
    base_url: str
    models: List[str]
    rpm: int = 30           # requests per minute
    rpd: int = 14400        # requests per day
    tpm: int = 1_000_000    # tokens per minute (0 = unlimited)
    is_free: bool = False
    timeout: float = 30.0
    max_tokens: int = 512


# Provider templates
PROVIDERS = {
    # --- PAID ---
    "openai": ProviderConfig(
        name="openai",
        base_url="https://api.openai.com/v1",
        models=["gpt-4o", "gpt-4o-mini"],
        rpm=500, rpd=10000, is_free=False, timeout=30.0
    ),
    "xai": ProviderConfig(
        name="xai",
        base_url="https://api.x.ai/v1",
        models=["grok-3-mini", "grok-3"],
        rpm=60, rpd=5000, is_free=False, timeout=30.0
    ),
    "google": ProviderConfig(
        name="google",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        models=["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro",
                "gemini-2.5-flash-thinking", "gemini-2.0-flash-lite"],
        rpm=60, rpd=10000, is_free=False, timeout=60.0
    ),

    # --- Claude Code CLI (subprocess-based, not OpenAI-compat) ---
    # NOTE: Only works when TF runs standalone (not during interactive claude session)
    # VM has 969MB RAM — claude CLI subprocess needs ~300MB which conflicts
    "anthropic_cli": ProviderConfig(
        name="anthropic_cli",
        base_url="",   # unused — handled via subprocess
        models=["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
        rpm=10, rpd=500, is_free=False, timeout=90.0, max_tokens=1024
    ),

    # --- DEAD: GROQ (restricted/banned 2026-04-05) ---
    # "groq": disabled — Organization restricted

    # --- DEAD: OPENROUTER (free models 404/429 2026-04-05) ---
    # "openrouter": disabled — free models removed or rate limited

    # --- FREE: COHERE ---
    "cohere": ProviderConfig(
        name="cohere",
        base_url="https://api.cohere.com/compatibility/v1",
        models=["command-a-03-2025", "command-r7b-12-2024"],
        rpm=20, rpd=1000, is_free=True, timeout=30.0, max_tokens=512
    ),

    # --- FREE: CEREBRAS ---
    "cerebras": ProviderConfig(
        name="cerebras",
        base_url="https://api.cerebras.ai/v1",
        models=["qwen-3-32b"],
        rpm=30, rpd=1000, tpm=1_000_000, is_free=True, timeout=15.0, max_tokens=512
    ),

    # --- PRIMARY FREE: HUGGINGFACE (4 tokens, dozens of models) ---
    "huggingface": ProviderConfig(
        name="huggingface",
        base_url="https://router.huggingface.co/v1",
        models=[
            "Qwen/Qwen2.5-72B-Instruct",     # Best: clean JSON, fast
            "google/gemma-3-27b-it",           # Great JSON compliance
            "meta-llama/Llama-3.3-70B-Instruct",
            "mistralai/Mistral-Small-24B-Instruct-2501",
            "nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
            "Qwen/Qwen3-8B",                  # Note: adds <think> blocks
            "Qwen/Qwen2.5-Coder-32B-Instruct",
            "microsoft/Phi-3.5-mini-instruct",
            "deepseek-ai/DeepSeek-R1-0528",   # DeepSeek R1 reasoning model
        ],
        rpm=15, rpd=2000, is_free=True, timeout=60.0, max_tokens=512
    ),
}

# --- HF Router aliases for named T1_premium agents ---
# These share the same HF Router infra but get distinct provider identities
for _alias in ("google-gemma", "qwen", "deepseek", "mistral", "meta-llama"):
    PROVIDERS[_alias] = ProviderConfig(
        name=_alias,
        base_url="https://router.huggingface.co/v1",
        models=PROVIDERS["huggingface"].models,
        rpm=15, rpd=2000, is_free=True, timeout=60.0, max_tokens=512
    )


# ============================================================================
# API KEY POOL
# ============================================================================
@dataclass
class APIKeySlot:
    """One API key with usage tracking."""
    key: str
    provider: str
    slot_index: int
    calls_today: int = 0
    calls_this_minute: int = 0
    last_minute_reset: float = 0.0
    last_call_time: float = 0.0
    total_calls: int = 0
    total_errors: int = 0
    total_tokens: int = 0
    is_exhausted: bool = False

    def can_call(self, provider_config: ProviderConfig) -> bool:
        """Check if this key slot has capacity."""
        if self.is_exhausted:
            return False
        now = time.time()
        # Reset minute counter
        if now - self.last_minute_reset > 60:
            self.calls_this_minute = 0
            self.last_minute_reset = now
        if self.calls_this_minute >= provider_config.rpm:
            return False
        if self.calls_today >= provider_config.rpd:
            self.is_exhausted = True
            return False
        return True

    def record_call(self, tokens_used: int = 0, error: bool = False):
        """Record a call against this key."""
        now = time.time()
        if now - self.last_minute_reset > 60:
            self.calls_this_minute = 0
            self.last_minute_reset = now
        self.calls_this_minute += 1
        self.calls_today += 1
        self.total_calls += 1
        self.total_tokens += tokens_used
        self.last_call_time = now
        if error:
            self.total_errors += 1

    def reset_daily(self):
        """Reset daily counters."""
        self.calls_today = 0
        self.is_exhausted = False


class APIPool:
    """
    Manages all API keys across all providers with rotation + rate limiting.

    Usage:
        pool = APIPool()
        pool.load_keys_from_env()
        client, model, slot = pool.get_client("groq")
        response = client.chat.completions.create(model=model, messages=[...])
        pool.record_usage(slot)
    """

    def __init__(self):
        self.slots: Dict[str, List[APIKeySlot]] = defaultdict(list)
        self._lock = threading.Lock()
        self._clients: Dict[str, OpenAI] = {}  # cache clients
        self._last_daily_reset = datetime.now(timezone.utc).date()
        self.stats = {
            "total_calls": 0,
            "total_errors": 0,
            "calls_by_provider": defaultdict(int),
            "errors_by_provider": defaultdict(int),
        }

    def load_keys_from_env(self, env_file: Optional[str] = None):
        """Load all API keys from environment variables and optional .env file."""
        # Load .env file if provided
        if env_file and os.path.exists(env_file):
            self._load_env_file(env_file)

        # Also try common locations
        for path in [
            "/home/termius/mon-ipad/.env.local",
            "/home/termius/.env",
            ".env.local",
            ".env",
        ]:
            if os.path.exists(path):
                self._load_env_file(path)

        # --- GROQ (5 keys) ---
        groq_keys = []
        for var in ["GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3",
                     "GROQ_API_KEY_4", "GROQ_API_KEY_5"]:
            val = os.environ.get(var, "")
            if val:
                groq_keys.append(val)
        for i, key in enumerate(groq_keys):
            self.add_key("groq", key, i)

        # --- OPENROUTER (7 keys) ---
        or_keys = []
        for var in ["OPENROUTER_API_KEY", "OPENROUTER_API_KEY_2",
                     "OPENROUTER_API_KEY_3", "OPENROUTER_API_KEY_4",
                     "OPENROUTER_API_KEY_5", "OPENROUTER_API_KEY_6",
                     "OPENROUTER_API_KEY_7"]:
            val = os.environ.get(var, "")
            if val:
                or_keys.append(val)
        # Also check pipeline keys
        for var in ["OPENROUTER_PIPELINE_KEY_1", "OPENROUTER_PIPELINE_KEY_2",
                     "OPENROUTER_PIPELINE_KEY_3", "OPENROUTER_PIPELINE_KEY_4",
                     "OPENROUTER_PIPELINE_KEY_5", "OPENROUTER_PIPELINE_KEY_6",
                     # Alternative naming used in .env.local
                     "OPENROUTER_KEY_STANDARD", "OPENROUTER_KEY_GRAPH",
                     "OPENROUTER_KEY_QUANTITATIVE", "OPENROUTER_KEY_ORCHESTRATOR",
                     "OPENROUTER_KEY_PME", "OPENROUTER_KEY_SPARE"]:
            val = os.environ.get(var, "")
            if val and val not in or_keys:
                or_keys.append(val)
        for i, key in enumerate(or_keys):
            self.add_key("openrouter", key, i)

        # --- COHERE (2 keys) ---
        for i, var in enumerate(["COHERE_API_KEY", "COHERE_API_KEY_2"]):
            val = os.environ.get(var, "")
            if val:
                self.add_key("cohere", val, i)

        # --- CEREBRAS ---
        val = os.environ.get("CEREBRAS_API_KEY", "")
        if val:
            self.add_key("cerebras", val, 0)

        # --- HUGGINGFACE (4 tokens) ---
        hf_keys = []
        for var in ["HF_TOKEN", "HF_TOKEN_2", "HF_TOKEN_3", "HF_TOKEN_USERS"]:
            val = os.environ.get(var, "")
            if val:
                hf_keys.append(val)
        for i, key in enumerate(hf_keys):
            self.add_key("huggingface", key, i)

        # --- HF Router aliases (named T1_premium agents share HF keys) ---
        for alias in ("google-gemma", "qwen", "deepseek", "mistral", "meta-llama"):
            for i, key in enumerate(hf_keys):
                self.add_key(alias, key, i)

        # --- PAID: OpenAI ---
        val = os.environ.get("OPENAI_API_KEY", "")
        if val:
            self.add_key("openai", val, 0)

        # --- PAID: xAI ---
        val = os.environ.get("XAI_API_KEY", "")
        if val:
            self.add_key("xai", val, 0)

        # --- PAID: Google (multiple keys for quota rotation) ---
        for idx, key_name in enumerate(["GOOGLE_API_KEY", "GOOGLE_API_KEY_2", "GOOGLE_API_KEY_3"]):
            val = os.environ.get(key_name, "")
            if val:
                self.add_key("google", val, idx)

        # --- Claude Code CLI (subprocess, no key needed — uses local claude CLI) ---
        self.add_key("anthropic_cli", "cli", 0)

    def _load_env_file(self, path: str):
        """Load environment variables from a file (KEY=VALUE or export KEY=VALUE format)."""
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    # Strip 'export ' prefix (bash-style env files use this)
                    if line.startswith("export "):
                        line = line[7:].strip()
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and val and key not in os.environ:
                        os.environ[key] = val
        except Exception:
            pass

    def add_key(self, provider: str, key: str, slot_index: int):
        """Add an API key slot."""
        slot = APIKeySlot(key=key, provider=provider, slot_index=slot_index)
        self.slots[provider].append(slot)

    def get_client(self, provider: str, preferred_model: Optional[str] = None
                   ) -> Optional[Tuple[Any, str, APIKeySlot]]:
        """
        Get an OpenAI-compatible client for a provider, with the least-used available key.
        Returns (client, model_name, key_slot) or None if no capacity.
        """
        if not HAS_OPENAI:
            return None

        self._maybe_daily_reset()

        config = PROVIDERS.get(provider)
        if not config:
            return None

        with self._lock:
            available = [s for s in self.slots.get(provider, []) if s.can_call(config)]
            if not available:
                return None

            # Pick the slot with the fewest calls today (round-robin effect)
            slot = min(available, key=lambda s: s.calls_today)

            # Build or cache client
            cache_key = f"{provider}_{slot.slot_index}"
            if cache_key not in self._clients:
                extra_headers = {}
                if provider == "openrouter":
                    extra_headers = {
                        "HTTP-Referer": "https://nomos42.ai",
                        "X-Title": "Nomos42 Trading Floor"
                    }
                self._clients[cache_key] = OpenAI(
                    api_key=slot.key,
                    base_url=config.base_url,
                    timeout=config.timeout,
                    default_headers=extra_headers if extra_headers else None,
                )

            model = preferred_model if preferred_model and preferred_model in config.models \
                else config.models[0]

            return self._clients[cache_key], model, slot

    def call_llm(self, provider: str, prompt: str,
                 model: Optional[str] = None,
                 system: str = "You are an NBA betting analyst. Respond only with valid JSON.",
                 max_tokens: int = 0,
                 temperature: float = 0.3) -> Optional[dict]:
        """
        High-level: call an LLM and parse JSON response.
        Handles retry on a different key if one fails.
        Returns parsed JSON dict or None on failure.
        """
        config = PROVIDERS.get(provider)
        if not config:
            return None

        max_tok = max_tokens if max_tokens > 0 else config.max_tokens
        attempts = min(3, len(self.slots.get(provider, [])) or 1)

        for attempt in range(attempts):
            result = self.get_client(provider, preferred_model=model)
            if not result:
                return None

            client, model_name, slot = result
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=max_tok,
                    temperature=temperature,
                )
                text = response.choices[0].message.content.strip()
                tokens_used = getattr(response.usage, 'total_tokens', 0) if response.usage else 0
                self.record_usage(slot, tokens_used=tokens_used)

                # Parse JSON from response
                return self._parse_json(text)

            except Exception as e:
                self.record_usage(slot, error=True)
                err_msg = str(e)[:120]
                # Mark key as exhausted if restricted/banned
                if any(x in err_msg.lower() for x in ['restricted', 'banned', 'suspended', 'deactivated']):
                    slot.is_exhausted = True
                if attempt < attempts - 1:
                    time.sleep(0.5)
                    continue
                # Log the error for debugging (but don't spam)
                if not hasattr(self, '_error_log'):
                    self._error_log = {}
                self._error_log[provider] = err_msg
                return None

    def call_llm_raw(self, provider: str, prompt: str,
                     model: Optional[str] = None,
                     system: str = "You are an NBA betting analyst.",
                     max_tokens: int = 0,
                     temperature: float = 0.3) -> Optional[str]:
        """Like call_llm but returns raw text instead of parsed JSON."""
        config = PROVIDERS.get(provider)
        if not config:
            return None

        max_tok = max_tokens if max_tokens > 0 else config.max_tokens
        result = self.get_client(provider, preferred_model=model)
        if not result:
            return None

        client, model_name, slot = result
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tok,
                temperature=temperature,
            )
            text = response.choices[0].message.content.strip()
            tokens_used = getattr(response.usage, 'total_tokens', 0) if response.usage else 0
            self.record_usage(slot, tokens_used=tokens_used)
            return text
        except Exception as e:
            self.record_usage(slot, error=True)
            return None

    def call_llm_cli(self, model: str, prompt: str,
                     system: str = "You are an NBA betting analyst. Respond only with valid JSON.",
                     max_tokens: int = 1024,
                     temperature: float = 0.3) -> "Optional[dict]":
        """
        Call Claude Code CLI via subprocess (anthropic_cli provider).
        Uses: claude -p PROMPT --model MODEL --output-format json
        Falls back to raw text parse if JSON mode fails.
        """
        config = PROVIDERS.get("anthropic_cli")
        slots = self.slots.get("anthropic_cli", [])
        if not slots:
            return None
        slot = slots[0]
        if not slot.can_call(config):
            return None

        full_prompt = f"{system}\n\n{prompt}" if system else prompt

        try:
            result = subprocess.run(
                ["claude", "-p", full_prompt, "--model", model,
                 "--output-format", "json"],
                capture_output=True, text=True,
                timeout=config.timeout,
            )
            slot.record_call()
            with self._lock:
                self.stats["total_calls"] += 1
                self.stats["calls_by_provider"]["anthropic_cli"] += 1

            if result.returncode != 0:
                slot.record_call(error=True)
                return None

            # claude --output-format json wraps output in {"result": "..."}
            raw = result.stdout.strip()
            try:
                outer = json.loads(raw)
                if isinstance(outer, dict) and "result" in outer:
                    inner_text = outer["result"]
                    parsed = self._parse_json(inner_text)
                    return parsed if parsed else outer
                return outer
            except json.JSONDecodeError:
                return self._parse_json(raw)

        except subprocess.TimeoutExpired:
            slot.record_call(error=True)
            with self._lock:
                self.stats["total_errors"] += 1
            return None
        except FileNotFoundError:
            # claude CLI not installed
            return None
        except Exception:
            slot.record_call(error=True)
            return None

    def record_usage(self, slot: APIKeySlot, tokens_used: int = 0, error: bool = False):
        """Record usage against a key slot."""
        with self._lock:
            slot.record_call(tokens_used=tokens_used, error=error)
            self.stats["total_calls"] += 1
            self.stats["calls_by_provider"][slot.provider] += 1
            if error:
                self.stats["total_errors"] += 1
                self.stats["errors_by_provider"][slot.provider] += 1

    def _maybe_daily_reset(self):
        """Reset daily counters at midnight UTC."""
        today = datetime.now(timezone.utc).date()
        if today > self._last_daily_reset:
            with self._lock:
                for provider_slots in self.slots.values():
                    for slot in provider_slots:
                        slot.reset_daily()
                self._last_daily_reset = today

    def _parse_json(self, text: str) -> Optional[dict]:
        """Extract JSON from LLM response text, handling <think> blocks and markdown."""
        if not text:
            return None

        # Strip <think>...</think> blocks (Qwen3, DeepSeek-R1 style)
        import re
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from ```json ... ``` blocks
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start) if "```" in text[start:] else len(text)
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

        # Try extracting from ``` ... ``` blocks (without json tag)
        if "```" in text:
            parts = text.split("```")
            for part in parts[1::2]:  # odd indices are inside backticks
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    try:
                        return json.loads(part)
                    except json.JSONDecodeError:
                        pass

        # Try finding first { to last }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1:
            try:
                return json.loads(text[first_brace:last_brace + 1])
            except json.JSONDecodeError:
                pass

        return None

    def get_capacity_report(self) -> dict:
        """Get a report of available capacity across all providers."""
        report = {}
        for provider, config in PROVIDERS.items():
            slots = self.slots.get(provider, [])
            if not slots:
                report[provider] = {"keys": 0, "status": "NO_KEYS"}
                continue

            available = sum(1 for s in slots if s.can_call(config))
            total_remaining = sum(max(0, config.rpd - s.calls_today) for s in slots)
            total_used = sum(s.calls_today for s in slots)

            report[provider] = {
                "keys": len(slots),
                "keys_available": available,
                "calls_today": total_used,
                "calls_remaining": total_remaining,
                "max_daily": config.rpd * len(slots),
                "models": config.models,
                "is_free": config.is_free,
                "status": "OK" if available > 0 else "EXHAUSTED",
            }
        return report

    def get_total_daily_capacity(self) -> int:
        """Total API calls available per day across all providers."""
        total = 0
        for provider, config in PROVIDERS.items():
            slots = self.slots.get(provider, [])
            total += config.rpd * len(slots)
        return total

    def summary(self) -> str:
        """Human-readable summary of the pool."""
        lines = ["API Pool Summary", "=" * 50]
        total_keys = 0
        total_capacity = 0
        for provider, config in PROVIDERS.items():
            slots = self.slots.get(provider, [])
            if not slots:
                continue
            cap = config.rpd * len(slots)
            total_keys += len(slots)
            total_capacity += cap
            lines.append(
                f"  {provider:<15} {len(slots)} keys | "
                f"{cap:>7,} RPD | "
                f"models: {', '.join(config.models[:2])}"
            )
        lines.append(f"\n  TOTAL: {total_keys} keys, {total_capacity:,} calls/day capacity")
        return "\n".join(lines)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================
_pool_instance: Optional[APIPool] = None


def get_pool() -> APIPool:
    """Get or create the singleton API pool."""
    global _pool_instance
    if _pool_instance is None:
        _pool_instance = APIPool()
        _pool_instance.load_keys_from_env()
    return _pool_instance


# ============================================================================
# CLI
# ============================================================================
if __name__ == "__main__":
    pool = get_pool()
    print(pool.summary())
    print()
    report = pool.get_capacity_report()
    for provider, info in report.items():
        print(f"  {provider}: {info}")
