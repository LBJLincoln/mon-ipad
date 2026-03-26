"""agent_log.py — Python helper to log agent activity for the live dashboard feed.

Usage:
    from scripts.agent_log import log_activity
    log_activity("darwin", "decision", "Injecting S14 best to S10", to="karpathy")
"""
import json
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path(__file__).parent.parent / "data" / "agent-activity.json"
MAX_ENTRIES = 200


def log_activity(agent: str, event_type: str, msg: str, to: str = None) -> dict:
    """Log an agent activity event.

    Args:
        agent: Agent name (darwin, karpathy, edge, feynman, bayes, sonnet, etc.)
        event_type: One of message, decision, result, error, thinking, deploy
        msg: Human-readable message
        to: Optional target agent name (for inter-agent communication)

    Returns:
        The logged entry dict
    """
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        entries = json.loads(LOG_FILE.read_text()) if LOG_FILE.exists() else []
    except (json.JSONDecodeError, OSError):
        entries = []

    entry = {
        "id": hashlib.sha256(f"{time.time_ns()}".encode()).hexdigest()[:12],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent": agent,
        "type": event_type,
        "msg": msg,
    }
    if to:
        entry["to"] = to

    entries.append(entry)
    entries = entries[-MAX_ENTRIES:]

    LOG_FILE.write_text(json.dumps(entries))
    return entry


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python agent_log.py <agent> <type> <message> [target]")
        sys.exit(1)
    target = sys.argv[4] if len(sys.argv) > 4 else None
    entry = log_activity(sys.argv[1], sys.argv[2], sys.argv[3], to=target)
    print(f"Logged: {json.dumps(entry)}")
