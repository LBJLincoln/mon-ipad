#!/usr/bin/env python3
"""OpenRouter Key Rotation — distribute requests across 7 keys (3 accounts).

Each key has ~20 req/min limit. With 7 keys → ~140 req/min aggregate.

Usage:
    from openrouter_key_rotation import KeyRotator
    rotator = KeyRotator()
    key = rotator.get_next_key()  # Returns least-recently-used key
    rotator.record_usage(key)     # Track usage after request
    status = rotator.get_status() # View usage stats
"""

import os
import time
import threading
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta


class KeyRotator:
    """Rotates OpenRouter API keys to distribute load across multiple accounts.

    Attributes:
        keys: List of available OpenRouter API keys
        usage: Dict tracking request timestamps per key
        lock: Thread lock for safe concurrent access
        rate_limit: Max requests per minute per key (default: 20)
        window: Time window for rate limit calculation (seconds)
    """

    def __init__(self, rate_limit: int = 20, window: int = 60):
        """Initialize the key rotator.

        Args:
            rate_limit: Max requests per minute per key (default: 20)
            window: Time window for rate limit in seconds (default: 60)
        """
        self.rate_limit = rate_limit
        self.window = window
        self.lock = threading.Lock()

        # Load all available keys from environment
        self.keys = self._load_keys()

        # Track usage: key -> list of request timestamps
        self.usage: Dict[str, List[float]] = defaultdict(list)

        # Track total requests per key (lifetime)
        self.total_requests: Dict[str, int] = defaultdict(int)

        if not self.keys:
            raise ValueError(
                "No OpenRouter keys found. Set at least one of: "
                "OPENROUTER_API_KEY, OPENROUTER_KEY_STANDARD, OPENROUTER_KEY_GRAPH, "
                "OPENROUTER_KEY_QUANTITATIVE, OPENROUTER_KEY_ORCHESTRATOR, "
                "OPENROUTER_KEY_PME, OPENROUTER_KEY_ACCOUNT2, OPENROUTER_KEY_ACCOUNT3"
            )

        print(f"[KeyRotator] Initialized with {len(self.keys)} keys")
        print(f"[KeyRotator] Aggregate throughput: ~{len(self.keys) * rate_limit} req/min")

    def _load_keys(self) -> List[str]:
        """Load all available OpenRouter keys from environment variables.

        Returns:
            List of API keys (deduplicated)
        """
        key_vars = [
            "OPENROUTER_API_KEY",          # Main key
            "OPENROUTER_KEY_STANDARD",     # Standard RAG pipeline
            "OPENROUTER_KEY_GRAPH",        # Graph RAG pipeline
            "OPENROUTER_KEY_QUANTITATIVE", # Quantitative pipeline
            "OPENROUTER_KEY_ORCHESTRATOR", # Orchestrator pipeline
            "OPENROUTER_KEY_PME",          # PME pipelines
            "OPENROUTER_KEY_ACCOUNT2",     # Account 2 (if exists)
            "OPENROUTER_KEY_ACCOUNT3",     # Account 3 (if exists)
        ]

        keys = []
        seen = set()

        for var in key_vars:
            key = os.getenv(var)
            if key and key not in seen:
                keys.append(key)
                seen.add(key)
                # Mask key for logging (show first 8 chars)
                masked = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
                print(f"[KeyRotator] Loaded {var}: {masked}")

        return keys

    def _clean_old_timestamps(self, key: str, now: float) -> None:
        """Remove timestamps outside the rate limit window.

        Args:
            key: API key
            now: Current timestamp
        """
        cutoff = now - self.window
        self.usage[key] = [ts for ts in self.usage[key] if ts > cutoff]

    def _get_key_usage(self, key: str, now: float) -> int:
        """Get number of requests for a key in the current window.

        Args:
            key: API key
            now: Current timestamp

        Returns:
            Number of requests in the last window seconds
        """
        self._clean_old_timestamps(key, now)
        return len(self.usage[key])

    def get_next_key(self) -> str:
        """Get the best key to use (least recently used with capacity).

        Returns:
            API key to use for the next request

        Raises:
            RuntimeError: If all keys are at rate limit
        """
        with self.lock:
            now = time.time()

            # Build candidates: (key, usage_count, last_used_time)
            candidates: List[Tuple[str, int, float]] = []

            for key in self.keys:
                usage_count = self._get_key_usage(key, now)
                last_used = self.usage[key][-1] if self.usage[key] else 0
                candidates.append((key, usage_count, last_used))

            # Sort by: 1) usage count (ascending), 2) last used (ascending)
            candidates.sort(key=lambda x: (x[1], x[2]))

            # Pick the first key with capacity
            for key, usage_count, last_used in candidates:
                if usage_count < self.rate_limit:
                    # Warn if approaching limit
                    if usage_count >= self.rate_limit * 0.8:
                        print(
                            f"[KeyRotator] WARNING: Key {key[:8]}... at "
                            f"{usage_count}/{self.rate_limit} req/min "
                            f"({usage_count/self.rate_limit*100:.0f}%)"
                        )
                    return key

            # All keys at limit - wait for cooldown
            oldest_request = min(
                min(self.usage[k]) for k in self.keys if self.usage[k]
            )
            wait_time = self.window - (now - oldest_request)

            if wait_time > 0:
                print(
                    f"[KeyRotator] All keys at rate limit. "
                    f"Waiting {wait_time:.1f}s for cooldown..."
                )
                time.sleep(wait_time + 0.1)  # Add 100ms buffer
                return self.get_next_key()  # Retry

            # Fallback: return least recently used key
            return candidates[0][0]

    def record_usage(self, key: str) -> None:
        """Record that a request was made with the given key.

        Args:
            key: API key that was used
        """
        with self.lock:
            now = time.time()
            self.usage[key].append(now)
            self.total_requests[key] += 1
            self._clean_old_timestamps(key, now)

    def get_status(self) -> Dict[str, Dict[str, any]]:
        """Get current usage status for all keys.

        Returns:
            Dict mapping key prefix to usage stats:
            {
                "key_prefix": {
                    "current_usage": 5,      # Requests in last 60s
                    "total_requests": 150,   # Lifetime requests
                    "capacity": 20,          # Max req/min
                    "utilization": 0.25,     # Current utilization (0-1)
                    "last_used": "2026-02-23 16:45:30"
                }
            }
        """
        with self.lock:
            now = time.time()
            status = {}

            for key in self.keys:
                prefix = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
                current_usage = self._get_key_usage(key, now)
                last_used_ts = self.usage[key][-1] if self.usage[key] else None

                status[prefix] = {
                    "current_usage": current_usage,
                    "total_requests": self.total_requests[key],
                    "capacity": self.rate_limit,
                    "utilization": current_usage / self.rate_limit,
                    "last_used": (
                        datetime.fromtimestamp(last_used_ts).strftime("%Y-%m-%d %H:%M:%S")
                        if last_used_ts
                        else "Never"
                    )
                }

            return status

    def print_status(self) -> None:
        """Print a formatted status table to stdout."""
        status = self.get_status()

        print("\n" + "="*80)
        print("OpenRouter Key Rotation Status")
        print("="*80)
        print(f"{'Key':<20} {'Current':<10} {'Total':<10} {'Capacity':<10} {'Usage %':<10} {'Last Used':<20}")
        print("-"*80)

        for key_prefix, stats in status.items():
            utilization_pct = stats["utilization"] * 100
            print(
                f"{key_prefix:<20} "
                f"{stats['current_usage']:<10} "
                f"{stats['total_requests']:<10} "
                f"{stats['capacity']:<10} "
                f"{utilization_pct:>6.1f}%    "
                f"{stats['last_used']:<20}"
            )

        print("-"*80)
        total_current = sum(s["current_usage"] for s in status.values())
        total_lifetime = sum(s["total_requests"] for s in status.values())
        total_capacity = len(self.keys) * self.rate_limit
        aggregate_util = total_current / total_capacity if total_capacity > 0 else 0

        print(
            f"{'TOTAL':<20} "
            f"{total_current:<10} "
            f"{total_lifetime:<10} "
            f"{total_capacity:<10} "
            f"{aggregate_util*100:>6.1f}%"
        )
        print("="*80 + "\n")

    def reset_stats(self) -> None:
        """Reset all usage statistics (for testing)."""
        with self.lock:
            self.usage.clear()
            self.total_requests.clear()
            print("[KeyRotator] Stats reset")


# Singleton instance for easy import
_rotator: Optional[KeyRotator] = None

def get_rotator() -> KeyRotator:
    """Get or create the global KeyRotator instance.

    Returns:
        Global KeyRotator singleton
    """
    global _rotator
    if _rotator is None:
        _rotator = KeyRotator()
    return _rotator


# CLI for testing
if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="OpenRouter Key Rotation Tool")
    parser.add_argument(
        "--test",
        type=int,
        metavar="N",
        help="Simulate N requests and show distribution"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current usage status"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset usage statistics"
    )

    args = parser.parse_args()

    try:
        rotator = get_rotator()

        if args.reset:
            rotator.reset_stats()
            print("Statistics reset successfully")
            sys.exit(0)

        if args.status:
            rotator.print_status()
            sys.exit(0)

        if args.test:
            print(f"\nSimulating {args.test} requests...\n")
            for i in range(args.test):
                key = rotator.get_next_key()
                rotator.record_usage(key)

                if (i + 1) % 10 == 0:
                    print(f"Progress: {i + 1}/{args.test} requests")

            print(f"\nCompleted {args.test} requests")
            rotator.print_status()
            sys.exit(0)

        # Default: show help
        parser.print_help()

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
