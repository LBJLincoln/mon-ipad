#!/usr/bin/env python3
"""
OpenRouter Error Pattern Detection — Multi-RAG Orchestrator

Monitors eval logs and detects known OpenRouter error signatures.
Integrates with openrouter-key-rotation.py for automatic key rotation.

Usage:
    source .env.local && python3 scripts/openrouter-monitor.py --once
    source .env.local && python3 scripts/openrouter-monitor.py --daemon
    source .env.local && python3 scripts/openrouter-monitor.py --once --alert

Daemon mode:
    nohup python3 scripts/openrouter-monitor.py --daemon > logs/openrouter-monitor.log 2>&1 &
"""

import argparse
import glob
import json
import os
import re
import signal
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(REPO_ROOT, "logs")
MONITOR_LOGS_DIR = os.path.join(LOGS_DIR, "monitor")
EVAL_LOGS_DIR = os.path.join(LOGS_DIR, "iterative-eval")
SESSION_INTEL = os.path.join(LOGS_DIR, "session-intelligence-report.json")
ALERTS_LOG = os.path.join(LOGS_DIR, "openrouter-alerts.jsonl")

os.makedirs(MONITOR_LOGS_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Load .env.local if dotenv available, otherwise manual fallback
# ---------------------------------------------------------------------------
def load_env():
    """Load environment variables from .env.local."""
    env_file = os.path.join(REPO_ROOT, ".env.local")
    if not os.path.exists(env_file):
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        # Manual parsing — handles `export VAR=value`
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:]
                if "=" in line:
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip()
                    # Remove surrounding quotes
                    if val and val[0] in ('"', "'") and val[-1] == val[0]:
                        val = val[1:-1]
                    # Skip variable references like ${VAR}
                    if "${" not in val:
                        os.environ.setdefault(key, val)


load_env()

# ---------------------------------------------------------------------------
# Error Signatures (from agentic-automation-spec.md Section 1.2)
# ---------------------------------------------------------------------------
ERROR_SIGNATURES: Dict[str, dict] = {
    "rate_limit": {
        "patterns": ["429", "rate limit", "too many requests"],
        "severity": "warning",
        "auto_action": "rotate_key",
        "cooldown_minutes": 5,
    },
    "auth_failure": {
        "patterns": ["401", "invalid api key", "authentication failed"],
        "severity": "critical",
        "auto_action": "alert_rotate",
        "cooldown_minutes": 1,
    },
    "model_overload": {
        "patterns": ["503", "overloaded", "unavailable"],
        "severity": "warning",
        "auto_action": "fallback_model",
        "cooldown_minutes": 2,
    },
    "empty_response": {
        "patterns": ["empty body", "null response", "no output"],
        "severity": "high",
        "auto_action": "retry_with_backup",
        "cooldown_minutes": 0,
    },
    "timeout": {
        "patterns": ["timeout", "deadline exceeded", "ETIMEDOUT"],
        "severity": "warning",
        "auto_action": "increase_timeout",
        "cooldown_minutes": 3,
    },
}

# Severity ranking for sorting/filtering
SEVERITY_ORDER = {"critical": 0, "high": 1, "warning": 2, "info": 3}

# ---------------------------------------------------------------------------
# ANSI colors
# ---------------------------------------------------------------------------
class C:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    END = "\033[0m"

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
SHUTDOWN = False
# Track last action time per signature to enforce cooldowns
_last_action: Dict[str, float] = {}


def handle_signal(signum, frame):
    global SHUTDOWN
    print(f"\n[{_now()}] Signal {signum} received -- shutting down gracefully")
    SHUTDOWN = True


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Log collection
# ---------------------------------------------------------------------------
def collect_recent_log_lines(max_age_minutes: int = 30) -> List[str]:
    """Gather recent text from eval logs, monitor logs, and session intel.

    Returns a list of text lines to scan for error patterns.
    """
    lines: List[str] = []
    cutoff = time.time() - max_age_minutes * 60

    # 1. Eval session logs (plain text)
    for pattern in ["eval-session*.log", "eval-*.log"]:
        for path in glob.glob(os.path.join(LOGS_DIR, pattern)):
            try:
                if os.path.getmtime(path) < cutoff:
                    continue
                with open(path) as f:
                    lines.extend(f.readlines()[-200:])  # tail 200 lines
            except (OSError, IOError):
                pass

    # 2. Monitor JSONL logs (today)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    monitor_log = os.path.join(MONITOR_LOGS_DIR, f"{today}.jsonl")
    if os.path.exists(monitor_log):
        try:
            with open(monitor_log) as f:
                for raw_line in f.readlines()[-100:]:
                    try:
                        entry = json.loads(raw_line)
                        # Flatten JSON to text for pattern matching
                        lines.append(json.dumps(entry))
                    except json.JSONDecodeError:
                        lines.append(raw_line)
        except (OSError, IOError):
            pass

    # 3. Iterative eval JSON logs
    for path in glob.glob(os.path.join(EVAL_LOGS_DIR, "*.json")):
        try:
            if os.path.getmtime(path) < cutoff:
                continue
            with open(path) as f:
                data = json.load(f)
            lines.append(json.dumps(data))
        except (OSError, IOError, json.JSONDecodeError):
            pass

    # 4. Session intelligence report
    if os.path.exists(SESSION_INTEL):
        try:
            if os.path.getmtime(SESSION_INTEL) >= cutoff:
                with open(SESSION_INTEL) as f:
                    lines.append(f.read())
        except (OSError, IOError):
            pass

    return lines


# ---------------------------------------------------------------------------
# Signature matching
# ---------------------------------------------------------------------------
def match_signatures(lines: List[str]) -> List[dict]:
    """Scan text lines for known error signatures.

    Returns a list of detected signatures with metadata.
    """
    detections: List[dict] = []
    seen_combos = set()  # dedup within one scan pass

    for line in lines:
        lower = line.lower()
        for sig_name, sig in ERROR_SIGNATURES.items():
            for pattern in sig["patterns"]:
                if pattern.lower() in lower:
                    combo_key = f"{sig_name}:{pattern}"
                    if combo_key in seen_combos:
                        continue
                    seen_combos.add(combo_key)

                    # Extract a snippet around the match
                    idx = lower.find(pattern.lower())
                    start = max(0, idx - 60)
                    end = min(len(line), idx + len(pattern) + 60)
                    snippet = line[start:end].strip()

                    detections.append({
                        "signature": sig_name,
                        "matched_pattern": pattern,
                        "severity": sig["severity"],
                        "auto_action": sig["auto_action"],
                        "cooldown_minutes": sig["cooldown_minutes"],
                        "snippet": snippet[:200],
                        "detected_at": _now(),
                    })
                    break  # one detection per signature per line group

    # Sort by severity
    detections.sort(key=lambda d: SEVERITY_ORDER.get(d["severity"], 99))
    return detections


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
def _cooldown_ok(sig_name: str, cooldown_minutes: int) -> bool:
    """Check if enough time has passed since last action for this signature."""
    last = _last_action.get(sig_name, 0)
    return (time.time() - last) >= cooldown_minutes * 60


def trigger_key_rotation(sig_name: str) -> bool:
    """Attempt to rotate OpenRouter key via the KeyRotator singleton."""
    try:
        sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
        from importlib import import_module
        mod = import_module("openrouter-key-rotation".replace("-", "_"))
        # Actually we can't import with hyphens; use importlib with path
    except Exception:
        pass

    # Fallback: direct import from the file
    key_rotation_path = os.path.join(REPO_ROOT, "scripts", "openrouter-key-rotation.py")
    if not os.path.exists(key_rotation_path):
        print(f"  {C.YELLOW}WARN{C.END} Key rotation script not found at {key_rotation_path}")
        return False

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("openrouter_key_rotation", key_rotation_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rotator = mod.get_rotator()
        next_key = rotator.get_next_key()
        masked = f"{next_key[:8]}...{next_key[-4:]}" if len(next_key) > 12 else "***"
        print(f"  {C.GREEN}ACTION{C.END} Rotated to key: {masked} (sig={sig_name})")
        _last_action[sig_name] = time.time()
        return True
    except Exception as e:
        print(f"  {C.RED}ERROR{C.END} Key rotation failed: {e}")
        return False


def execute_action(detection: dict) -> Optional[str]:
    """Execute the auto_action for a detection if cooldown allows.

    Returns a description of the action taken, or None.
    """
    sig_name = detection["signature"]
    action = detection["auto_action"]
    cooldown = detection["cooldown_minutes"]

    if not _cooldown_ok(sig_name, cooldown):
        return None

    if action in ("rotate_key", "alert_rotate"):
        if trigger_key_rotation(sig_name):
            return f"rotate_key for {sig_name}"

    if action == "fallback_model":
        print(f"  {C.BLUE}INFO{C.END} Model overload detected -- consider switching LLM model in n8n")
        _last_action[sig_name] = time.time()
        return f"fallback_model advisory for {sig_name}"

    if action == "retry_with_backup":
        print(f"  {C.BLUE}INFO{C.END} Empty response detected -- next request will use rotated key")
        _last_action[sig_name] = time.time()
        return f"retry_with_backup advisory for {sig_name}"

    if action == "increase_timeout":
        print(f"  {C.BLUE}INFO{C.END} Timeout detected -- consider increasing pipeline timeout")
        _last_action[sig_name] = time.time()
        return f"increase_timeout advisory for {sig_name}"

    return None


# ---------------------------------------------------------------------------
# Alerting
# ---------------------------------------------------------------------------
def log_alert(detection: dict, action_taken: Optional[str] = None):
    """Append an alert entry to the JSONL alerts log."""
    entry = {
        **detection,
        "action_taken": action_taken,
    }
    try:
        with open(ALERTS_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except (OSError, IOError) as e:
        print(f"  {C.YELLOW}WARN{C.END} Cannot write alert log: {e}")


def print_alert(detection: dict):
    """Print a formatted alert to stdout."""
    sev = detection["severity"]
    if sev == "critical":
        color = C.RED
    elif sev == "high":
        color = C.MAGENTA
    else:
        color = C.YELLOW

    print(
        f"  {color}[{sev.upper()}]{C.END} "
        f"{detection['signature']} -- matched '{detection['matched_pattern']}' "
        f"(action={detection['auto_action']})"
    )
    if detection.get("snippet"):
        print(f"           snippet: {detection['snippet'][:120]}")


# ---------------------------------------------------------------------------
# Main scan logic
# ---------------------------------------------------------------------------
def run_scan(alert: bool = False, execute_actions: bool = True) -> List[dict]:
    """Run one full scan cycle.

    Args:
        alert: If True, print alerts to stdout.
        execute_actions: If True, trigger auto-actions (key rotation, etc.).

    Returns:
        List of detections.
    """
    print(f"[{_now()}] Scanning logs for OpenRouter error patterns...")
    lines = collect_recent_log_lines(max_age_minutes=30)
    print(f"  Collected {len(lines)} log lines to scan")

    detections = match_signatures(lines)

    if not detections:
        print(f"  {C.GREEN}No error signatures detected{C.END}")
        return []

    print(f"  {C.YELLOW}Detected {len(detections)} signature(s){C.END}")

    for det in detections:
        if alert:
            print_alert(det)

        action_taken = None
        if execute_actions:
            action_taken = execute_action(det)

        log_alert(det, action_taken)

    # Summary
    by_severity = {}
    for d in detections:
        by_severity.setdefault(d["severity"], []).append(d["signature"])

    print(f"\n  Summary:")
    for sev in ["critical", "high", "warning"]:
        sigs = by_severity.get(sev, [])
        if sigs:
            print(f"    {sev}: {', '.join(sigs)}")

    return detections


# ---------------------------------------------------------------------------
# Daemon loop
# ---------------------------------------------------------------------------
def run_daemon(interval: int = 60, alert: bool = False):
    """Run in continuous monitoring mode.

    Args:
        interval: Seconds between scan cycles (default 60).
        alert: If True, print alerts each cycle.
    """
    print(f"[{_now()}] OpenRouter Monitor daemon started (PID {os.getpid()})")
    print(f"  Interval: {interval}s")
    print(f"  Alerts log: {ALERTS_LOG}")
    print(f"  Scanning dirs: {LOGS_DIR}")

    while not SHUTDOWN:
        try:
            run_scan(alert=alert, execute_actions=True)
        except Exception as e:
            print(f"[{_now()}] ERROR in scan cycle: {e}")

        # Sleep in small increments so SIGTERM is responsive
        for _ in range(interval):
            if SHUTDOWN:
                break
            time.sleep(1)

    print(f"[{_now()}] OpenRouter Monitor daemon stopped")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="OpenRouter Error Pattern Detection — Multi-RAG Orchestrator"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--daemon", action="store_true",
        help="Run in continuous monitoring mode"
    )
    mode.add_argument(
        "--once", action="store_true",
        help="Run a single scan and exit"
    )
    parser.add_argument(
        "--alert", action="store_true",
        help="Print formatted alerts to stdout"
    )
    parser.add_argument(
        "--interval", type=int, default=60,
        help="Scan interval in seconds for daemon mode (default: 60)"
    )
    parser.add_argument(
        "--no-action", action="store_true",
        help="Disable automatic actions (diagnostic only)"
    )

    args = parser.parse_args()

    if args.once:
        detections = run_scan(alert=args.alert, execute_actions=not args.no_action)
        sys.exit(1 if any(d["severity"] == "critical" for d in detections) else 0)
    elif args.daemon:
        run_daemon(interval=args.interval, alert=args.alert)


if __name__ == "__main__":
    main()
