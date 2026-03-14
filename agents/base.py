#!/usr/bin/env python3
"""Base class for all Nomos category agents.

Every agent follows the same pattern:
1. Load env from .env.local
2. Run in a loop (or --once)
3. Log to data/agents/{category}/
4. Optionally report to Telegram
"""

import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path("/home/termius/mon-ipad")
DATA_DIR = BASE_DIR / "data" / "agents"

# SSL context for HF spaces
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def load_env():
    """Load .env.local into os.environ."""
    env_file = BASE_DIR / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                if line.startswith("export "):
                    line = line[7:]
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip("'\""))


def llm_call(prompt, system="Tu es un assistant IA expert.", model="smart", max_tokens=1500, temperature=0.3):
    """Call LiteLLM proxy."""
    url = os.environ.get("LITELLM_PROXY_URL", "https://lbjlincoln-nomos-rag-engine-7.hf.space")
    key = os.environ.get("LITELLM_MASTER_KEY", "sk-litellm-nomos-2026")
    data = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        f"{url}/v1/chat/completions", data=data,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"LLM_ERROR: {e}"


def telegram_notify(message, silent=False):
    """Send notification to admin Telegram."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "8672296360:AAEvfje0wpQkQK2WpgUCwZnPHVvGAlHUNqk")
    admin_id = os.environ.get("ADMIN_TELEGRAM_ID", "6582544948")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({
        "chat_id": admin_id,
        "text": message[:4000],
        "disable_notification": silent,
    }).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def log_event(category, event_type, data):
    """Log structured event to JSONL."""
    log_dir = DATA_DIR / category
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "events.jsonl"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "type": event_type,
        **data,
    }
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def http_get(url, headers=None, timeout=15):
    """Simple HTTP GET. Tries JSON parse, falls back to raw text."""
    req = urllib.request.Request(url, headers=headers or {})
    req.add_header("User-Agent", "Nomos-Agent/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
            try:
                body = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                body = raw[:500].decode("utf-8", errors="replace") if raw else None
            return {"ok": True, "status": resp.status, "body": body}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "body": None}
    except Exception as e:
        return {"ok": False, "status": 0, "body": None, "error": str(e)}


def http_post(url, payload, headers=None, timeout=30):
    """Simple HTTP POST JSON."""
    data = json.dumps(payload).encode()
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return {"ok": True, "status": resp.status, "body": json.loads(resp.read())}
    except urllib.error.HTTPError as e:
        body = None
        try:
            body = json.loads(e.read())
        except Exception:
            pass
        return {"ok": False, "status": e.code, "body": body}
    except Exception as e:
        return {"ok": False, "status": 0, "body": None, "error": str(e)}


def run_agent_loop(category, tick_fn, interval=300, notify_start=True):
    """Standard agent loop. tick_fn() is called each cycle."""
    load_env()
    once = "--once" in sys.argv
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] AGENT [{category.upper()}] {'ONE-SHOT' if once else f'LOOP {interval}s'}")

    if notify_start and not once:
        telegram_notify(f"[{category.upper()}] Agent started (cycle {interval}s)", silent=True)

    while True:
        try:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] [{category}] tick...")
            result = tick_fn()
            if result:
                log_event(category, "tick", result)
        except Exception as e:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] [{category}] ERROR: {e}")
            log_event(category, "error", {"error": str(e)})

        if once:
            break
        time.sleep(interval)
