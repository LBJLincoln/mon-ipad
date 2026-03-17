#!/usr/bin/env python3
"""Rate Limits Tracker — Live monitoring of ALL API keys and quotas.

Checks every provider for:
- Live rate limit status (from API responses / headers)
- Documented tier limits (hardcoded)
- Current utilization %
- Alerts when >80% utilized or dead

Usage:
    python3 ops/rate-limits-tracker.py          # Loop every 60s
    python3 ops/rate-limits-tracker.py --once    # Single check
    python3 ops/rate-limits-tracker.py --json    # JSON-only output
    python3 ops/rate-limits-tracker.py --md      # Regenerate RATE-LIMITS.md

Importable:
    from ops.rate_limits_tracker import log_api_call
    log_api_call("openrouter", "llama-70b", tokens_used=1500, latency_ms=2340)
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

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path("/home/termius/mon-ipad")
DATA_DIR = BASE_DIR / "data"
AGENTS_DIR = DATA_DIR / "agents" / "rate-limits"
LIVE_JSON = DATA_DIR / "rate-limits-live.json"
STATE_FILE = DATA_DIR / "rate-limits-state.json"
EVENTS_LOG = AGENTS_DIR / "events.jsonl"
MD_FILE = DATA_DIR / "RATE-LIMITS.md"

AGENTS_DIR.mkdir(parents=True, exist_ok=True)

# SSL — HF Spaces use self-signed certs sometimes
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

# ---------------------------------------------------------------------------
# Env loader (same pattern as agents/base.py)
# ---------------------------------------------------------------------------
def load_env():
    env_file = BASE_DIR / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                if line.startswith("export "):
                    line = line[7:]
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip("'\""))

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _http(method, url, headers=None, body=None, timeout=15):
    """Generic HTTP call returning (status, headers_dict, body_parsed, error)."""
    hdrs = {"User-Agent": "Nomos-RateLimitTracker/1.0"}
    if headers:
        hdrs.update(headers)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx) as resp:
            raw = resp.read()
            resp_headers = {k.lower(): v for k, v in resp.getheaders()}
            try:
                parsed = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                parsed = raw[:2000].decode("utf-8", errors="replace") if raw else None
            return resp.status, resp_headers, parsed, None
    except urllib.error.HTTPError as e:
        resp_headers = {k.lower(): v for k, v in e.headers.items()} if e.headers else {}
        raw_body = None
        try:
            raw_body = json.loads(e.read())
        except Exception:
            pass
        return e.code, resp_headers, raw_body, f"HTTP {e.code}"
    except Exception as e:
        return 0, {}, None, str(e)

def http_get(url, headers=None, timeout=15):
    return _http("GET", url, headers=headers, timeout=timeout)

def http_post(url, body, headers=None, timeout=15):
    return _http("POST", url, headers=headers, body=body, timeout=timeout)

# ---------------------------------------------------------------------------
# Telegram alerts
# ---------------------------------------------------------------------------
def telegram_notify(message, silent=False):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    admin_id = os.environ.get("ADMIN_TELEGRAM_ID", "")
    if not token or not admin_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({
        "chat_id": admin_id,
        "text": message[:4000],
        "parse_mode": "Markdown",
        "disable_notification": silent,
    }).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------
def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"cumulative_requests": {}, "cumulative_tokens": {}, "last_alerts": {}}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def log_event(event_type, data):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        **data,
    }
    with open(EVENTS_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

# ---------------------------------------------------------------------------
# Public API: log_api_call (importable by other scripts)
# ---------------------------------------------------------------------------
def log_api_call(provider, model="unknown", tokens_used=0, latency_ms=0):
    """Track an API call. Import this from eval runners, ingest scripts, etc."""
    state = load_state()
    state["cumulative_requests"].setdefault(provider, 0)
    state["cumulative_requests"][provider] += 1
    state["cumulative_tokens"].setdefault(provider, 0)
    state["cumulative_tokens"][provider] += tokens_used
    save_state(state)
    log_event("api_call", {
        "provider": provider,
        "model": model,
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
    })

# ---------------------------------------------------------------------------
# Mask key for display
# ---------------------------------------------------------------------------
def mask_key(key, show=8):
    if not key:
        return "(not set)"
    if len(key) <= show + 3:
        return key[:4] + "***"
    return key[:show] + "***"

# ---------------------------------------------------------------------------
# Provider check functions
# ---------------------------------------------------------------------------

def check_openrouter(env_var, label):
    """OpenRouter: GET /api/v1/auth/key returns credits, usage, rate limits."""
    key = os.environ.get(env_var, "")
    if not key:
        return {"provider": f"OpenRouter ({label})", "env_var": env_var, "key_masked": mask_key(key),
                "status": "NO_KEY", "error": "Key not set"}

    status, hdrs, body, err = http_get(
        "https://openrouter.ai/api/v1/auth/key",
        headers={"Authorization": f"Bearer {key}"}
    )
    result = {
        "provider": f"OpenRouter ({label})",
        "env_var": env_var,
        "key_masked": mask_key(key),
        "plan": "free",
        "documented_limits": {"requests_per_min": 20, "credits_total": "free tier"},
        "status": "OK" if status == 200 else "ERROR",
    }
    if status == 200 and isinstance(body, dict):
        data = body.get("data", body)
        result["live"] = {
            "credits_used": data.get("usage", 0),
            "credits_limit": data.get("limit", None),
            "credits_remaining": data.get("limit_remaining", None),
            "rate_limit": data.get("rate_limit", {}),
            "label": data.get("label", ""),
        }
        limit = data.get("limit")
        remaining = data.get("limit_remaining")
        if limit and limit > 0 and remaining is not None:
            result["utilization_pct"] = round((1 - remaining / limit) * 100, 1)
        else:
            result["utilization_pct"] = 0  # free tier with no hard limit
    elif err:
        result["error"] = err
        result["status"] = "ERROR"

    # Rate limit headers
    for h in ["x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset"]:
        if h in hdrs:
            result.setdefault("headers", {})[h] = hdrs[h]

    return result


def check_groq(env_var, label):
    """Groq: Make a tiny models list call, extract rate limit headers."""
    key = os.environ.get(env_var, "")
    if not key:
        return {"provider": f"Groq ({label})", "env_var": env_var, "key_masked": mask_key(key),
                "status": "NO_KEY", "error": "Key not set"}

    status, hdrs, body, err = http_get(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {key}"}
    )
    result = {
        "provider": f"Groq ({label})",
        "env_var": env_var,
        "key_masked": mask_key(key),
        "plan": "free",
        "documented_limits": {
            "requests_per_min": 30,
            "requests_per_day": 14400,
            "tokens_per_min": 15000,
            "tokens_per_day": 500000,
        },
        "status": "OK" if status == 200 else "ERROR",
    }
    if status == 200:
        model_count = 0
        if isinstance(body, dict) and "data" in body:
            model_count = len(body["data"])
        result["live"] = {"models_available": model_count}
    elif err:
        result["error"] = err

    # Rate limit headers
    rl = {}
    for h in ["x-ratelimit-limit-requests", "x-ratelimit-remaining-requests",
              "x-ratelimit-limit-tokens", "x-ratelimit-remaining-tokens",
              "x-ratelimit-reset-requests", "x-ratelimit-reset-tokens"]:
        if h in hdrs:
            rl[h] = hdrs[h]
    if rl:
        result["headers"] = rl
        try:
            lim_req = int(rl.get("x-ratelimit-limit-requests", 0))
            rem_req = int(rl.get("x-ratelimit-remaining-requests", 0))
            if lim_req > 0:
                result["utilization_pct"] = round((1 - rem_req / lim_req) * 100, 1)
        except (ValueError, TypeError):
            pass

    return result


def check_pinecone(env_var, label):
    """Pinecone: Describe index stats."""
    key = os.environ.get(env_var, "")
    if not key:
        return {"provider": f"Pinecone ({label})", "env_var": env_var, "key_masked": mask_key(key),
                "status": "NO_KEY", "error": "Key not set"}

    # List indexes first
    status, hdrs, body, err = http_get(
        "https://api.pinecone.io/indexes",
        headers={"Api-Key": key}
    )
    result = {
        "provider": f"Pinecone ({label})",
        "env_var": env_var,
        "key_masked": mask_key(key),
        "plan": "free (Starter)",
        "documented_limits": {
            "indexes": 5,
            "vectors_per_index": 100000,
            "dimensions": 1024,
            "namespaces": "unlimited",
            "reads_per_sec": 100,
            "writes_per_sec": 100,
        },
        "status": "OK" if status == 200 else "ERROR",
    }
    if status == 200 and isinstance(body, dict):
        indexes = body.get("indexes", [])
        result["live"] = {
            "index_count": len(indexes),
            "indexes": [],
        }
        # Get stats for each index
        for idx in indexes:
            idx_name = idx.get("name", "")
            idx_host = idx.get("host", "")
            if idx_host:
                s2, h2, b2, e2 = http_get(
                    f"https://{idx_host}/describe_index_stats",
                    headers={"Api-Key": key},
                    timeout=10,
                )
                idx_info = {"name": idx_name, "host": idx_host}
                if s2 == 200 and isinstance(b2, dict):
                    total_vectors = b2.get("totalVectorCount", b2.get("total_vector_count", 0))
                    idx_info["total_vectors"] = total_vectors
                    idx_info["dimension"] = b2.get("dimension", 0)
                    idx_info["namespaces"] = len(b2.get("namespaces", {}))
                    idx_info["utilization_pct"] = round(total_vectors / 100000 * 100, 1)
                else:
                    idx_info["error"] = e2 or f"status {s2}"
                result["live"]["indexes"].append(idx_info)

        # Overall utilization = max of any index
        utils = [i.get("utilization_pct", 0) for i in result["live"]["indexes"]]
        result["utilization_pct"] = max(utils) if utils else 0
    elif err:
        result["error"] = err

    return result


def check_supabase(env_var_url, env_var_key, label):
    """Supabase: Check health and row count via REST API."""
    url = os.environ.get(env_var_url, "")
    key = os.environ.get(env_var_key, "")
    if not url:
        return {"provider": f"Supabase ({label})", "env_var": env_var_url, "key_masked": mask_key(key),
                "status": "NO_KEY", "error": "URL not set"}

    # Health check
    status, hdrs, body, err = http_get(f"{url}/rest/v1/", headers={
        "apikey": key,
        "Authorization": f"Bearer {key}",
    })

    result = {
        "provider": f"Supabase ({label})",
        "env_var": env_var_url,
        "key_masked": mask_key(key),
        "plan": "free (500MB)",
        "documented_limits": {
            "storage_mb": 500,
            "api_requests_per_day": 500000,
            "edge_functions": 500000,
            "realtime_concurrent": 200,
            "db_size_mb": 500,
        },
        "status": "OK" if status in (200, 204, 406) else "ERROR",
    }

    # Try to get sector_documents count
    count_status, count_hdrs, count_body, count_err = http_get(
        f"{url}/rest/v1/sector_documents?select=id&limit=1",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Prefer": "count=exact",
            "Range": "0-0",
        },
        timeout=10,
    )
    if count_status in (200, 206):
        content_range = count_hdrs.get("content-range", "")
        # e.g. "0-0/43357"
        if "/" in content_range:
            try:
                total_rows = int(content_range.split("/")[1])
                result["live"] = {"sector_documents_count": total_rows}
            except (ValueError, IndexError):
                result["live"] = {"sector_documents_count": "unknown"}
        else:
            result["live"] = {"sector_documents_count": "unknown (no range header)"}
    elif count_err:
        result.setdefault("live", {})["error"] = count_err

    result["utilization_pct"] = 0  # Can't easily measure storage via REST
    return result


def check_stripe():
    """Stripe: GET /v1/balance, extract rate limit headers."""
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key:
        return {"provider": "Stripe", "env_var": "STRIPE_SECRET_KEY", "key_masked": mask_key(key),
                "status": "NO_KEY", "error": "Key not set"}

    status, hdrs, body, err = http_get(
        "https://api.stripe.com/v1/balance",
        headers={"Authorization": f"Bearer {key}"}
    )
    result = {
        "provider": "Stripe",
        "env_var": "STRIPE_SECRET_KEY",
        "key_masked": mask_key(key),
        "plan": "live",
        "documented_limits": {
            "requests_per_sec": 100,
            "requests_per_sec_read": 100,
            "requests_per_sec_write": 100,
        },
        "status": "OK" if status == 200 else "ERROR",
    }
    if status == 200 and isinstance(body, dict):
        available = body.get("available", [])
        pending = body.get("pending", [])
        result["live"] = {
            "balance_available": [{"amount": b.get("amount", 0) / 100, "currency": b.get("currency")} for b in available],
            "balance_pending": [{"amount": b.get("amount", 0) / 100, "currency": b.get("currency")} for b in pending],
        }
    elif err:
        result["error"] = err

    # Rate headers
    rl = {}
    for h in ["ratelimit-limit", "ratelimit-remaining", "ratelimit-reset"]:
        if h in hdrs:
            rl[h] = hdrs[h]
    if rl:
        result["headers"] = rl

    result["utilization_pct"] = 0  # Stripe doesn't reveal per-second usage
    return result


def check_hf_space(url, label):
    """HF Space: Health check."""
    if not url:
        return {"provider": f"HF Space ({label})", "status": "NO_URL", "error": "URL not set"}

    start = time.time()
    status, hdrs, body, err = http_get(f"{url}/", timeout=10)
    latency = round((time.time() - start) * 1000)

    # Some Spaces return 200 with HTML, some return JSON
    is_up = status in (200, 301, 302, 307, 308)
    # n8n Spaces return HTML with "n8n" in it
    if status == 200 and isinstance(body, str) and "n8n" in body.lower():
        is_up = True

    result = {
        "provider": f"HF Space ({label})",
        "url": url,
        "plan": "free (community CPU)",
        "documented_limits": {
            "ram_gb": 2,
            "disk_gb": 50,
            "auto_sleep_hours": 48,
        },
        "status": "UP" if is_up else "DOWN",
        "live": {
            "latency_ms": latency,
            "http_status": status,
        },
    }
    if err and not is_up:
        result["error"] = err
    result["utilization_pct"] = 0 if is_up else 100
    return result


def check_litellm():
    """LiteLLM Proxy: GET /model/info for available models."""
    url = os.environ.get("LITELLM_PROXY_URL", "")
    key = os.environ.get("LITELLM_MASTER_KEY", "")
    if not url:
        return {"provider": "LiteLLM Proxy", "status": "NO_URL", "error": "URL not set"}

    status, hdrs, body, err = http_get(
        f"{url}/model/info",
        headers={"Authorization": f"Bearer {key}"}
    )
    result = {
        "provider": "LiteLLM Proxy (S7)",
        "env_var": "LITELLM_PROXY_URL",
        "key_masked": mask_key(key),
        "plan": "self-hosted on HF Space",
        "documented_limits": {
            "note": "Limited by underlying HF Space CPU/RAM",
        },
        "status": "OK" if status == 200 else "ERROR",
    }
    if status == 200 and isinstance(body, dict):
        models_data = body.get("data", [])
        model_names = []
        for m in models_data:
            name = m.get("model_name", m.get("model_info", {}).get("id", "?"))
            model_names.append(name)
        result["live"] = {
            "models_available": len(model_names),
            "model_groups": list(set(model_names)),
        }
    elif err:
        result["error"] = err

    # Also check health
    h_status, _, h_body, h_err = http_get(f"{url}/health", timeout=10)
    if h_status == 200:
        result.setdefault("live", {})["health"] = "OK"
    else:
        result.setdefault("live", {})["health"] = f"ERROR ({h_err or h_status})"

    result["utilization_pct"] = 0
    return result


def check_google_gemini():
    """Google Gemini: List models to verify key."""
    key = os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        return {"provider": "Google Gemini", "env_var": "GOOGLE_API_KEY", "key_masked": mask_key(key),
                "status": "NO_KEY", "error": "Key not set"}

    status, hdrs, body, err = http_get(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
        timeout=10,
    )
    result = {
        "provider": "Google Gemini",
        "env_var": "GOOGLE_API_KEY",
        "key_masked": mask_key(key),
        "plan": "free tier",
        "documented_limits": {
            "requests_per_min": 15,
            "tokens_per_min": 1000000,
            "requests_per_day": 1500,
        },
        "status": "OK" if status == 200 else "ERROR",
    }
    if status == 200 and isinstance(body, dict):
        models = body.get("models", [])
        model_names = [m.get("name", "").split("/")[-1] for m in models if "gemini" in m.get("name", "").lower()]
        result["live"] = {
            "models_available": len(models),
            "gemini_models": model_names[:10],
        }
    elif err:
        result["error"] = err

    result["utilization_pct"] = 0  # No usage endpoint on free tier
    return result


def check_jina(env_var, label):
    """Jina: Check if the key is valid by hitting a lightweight endpoint."""
    key = os.environ.get(env_var, "")
    if not key:
        return {"provider": f"Jina ({label})", "env_var": env_var, "key_masked": mask_key(key),
                "status": "NO_KEY", "error": "Key not set"}

    # Try embeddings health (minimal call)
    status, hdrs, body, err = http_post(
        "https://api.jina.ai/v1/embeddings",
        body={"model": "jina-embeddings-v3", "input": ["test"], "dimensions": 64},
        headers={"Authorization": f"Bearer {key}"},
        timeout=10,
    )
    result = {
        "provider": f"Jina ({label})",
        "env_var": env_var,
        "key_masked": mask_key(key),
        "plan": "free tier (1M tokens)",
        "documented_limits": {
            "embeddings_per_min": 500,
            "tokens_free": 1000000,
        },
        "status": "OK" if status == 200 else "ERROR",
    }
    if status == 200 and isinstance(body, dict):
        usage = body.get("usage", {})
        result["live"] = {
            "tokens_used_in_request": usage.get("total_tokens", 0),
        }
    elif status == 402:
        result["status"] = "EXHAUSTED"
        result["error"] = "Credits exhausted (HTTP 402)"
        result["utilization_pct"] = 100
    elif err:
        result["error"] = err
        result["utilization_pct"] = 0

    result.setdefault("utilization_pct", 0)
    return result


def check_cohere(env_var, label):
    """Cohere: List models to check key validity, extract rate headers."""
    key = os.environ.get(env_var, "")
    if not key:
        return {"provider": f"Cohere ({label})", "env_var": env_var, "key_masked": mask_key(key),
                "status": "NO_KEY", "error": "Key not set"}

    status, hdrs, body, err = http_get(
        "https://api.cohere.com/v2/models",
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        timeout=10,
    )
    result = {
        "provider": f"Cohere ({label})",
        "env_var": env_var,
        "key_masked": mask_key(key),
        "plan": "trial / free",
        "documented_limits": {
            "requests_per_min": 20,
            "calls_per_month": 1000,
        },
        "status": "OK" if status == 200 else "ERROR",
    }
    if status == 200 and isinstance(body, dict):
        models = body.get("models", [])
        result["live"] = {"models_available": len(models)}
    elif err:
        result["error"] = err

    # Rate limit headers
    rl = {}
    for h in ["x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset",
              "x-trial-calls-remaining", "x-trial-calls-limit"]:
        if h in hdrs:
            rl[h] = hdrs[h]
    if rl:
        result["headers"] = rl
        try:
            trial_rem = int(rl.get("x-trial-calls-remaining", -1))
            trial_lim = int(rl.get("x-trial-calls-limit", -1))
            if trial_lim > 0 and trial_rem >= 0:
                result["utilization_pct"] = round((1 - trial_rem / trial_lim) * 100, 1)
        except (ValueError, TypeError):
            pass

    result.setdefault("utilization_pct", 0)
    return result


def check_neo4j_bolt_proxy():
    """Neo4j via Bolt Proxy on HF Space."""
    proxy_url = "https://lbjlincoln-nomos-neo4j-proxy.hf.space"
    status, hdrs, body, err = http_get(f"{proxy_url}/health", timeout=10)

    result = {
        "provider": "Neo4j (Bolt Proxy)",
        "url": proxy_url,
        "plan": "Aura Free (200K nodes, 400K rels)",
        "documented_limits": {
            "nodes": 200000,
            "relationships": 400000,
            "storage_gb": 0.5,
        },
        "status": "OK" if status == 200 else "ERROR",
    }
    if status == 200 and isinstance(body, dict):
        result["live"] = body

    # Try a count query
    q_status, q_hdrs, q_body, q_err = http_post(
        f"{proxy_url}/query",
        body={"query": "MATCH (n) RETURN count(n) AS cnt"},
        timeout=15,
    )
    if q_status == 200 and isinstance(q_body, dict):
        records = q_body.get("records", q_body.get("results", []))
        if records:
            first = records[0] if isinstance(records, list) else records
            cnt = first.get("cnt", first) if isinstance(first, dict) else first
            result.setdefault("live", {})["total_nodes"] = cnt
            try:
                result["utilization_pct"] = round(int(cnt) / 200000 * 100, 1)
            except (ValueError, TypeError):
                result["utilization_pct"] = 0
    elif q_err:
        result.setdefault("live", {})["query_error"] = q_err

    result.setdefault("utilization_pct", 0)
    return result


def check_tavily():
    """Tavily: Try a minimal search to see if credits remain."""
    key = os.environ.get("TAVILY_API_KEY", "")
    if not key:
        return {"provider": "Tavily", "env_var": "TAVILY_API_KEY", "key_masked": mask_key(key),
                "status": "NO_KEY", "error": "Key not set"}

    # Minimal search
    status, hdrs, body, err = http_post(
        "https://api.tavily.com/search",
        body={"api_key": key, "query": "test", "max_results": 1},
        timeout=15,
    )
    result = {
        "provider": "Tavily",
        "env_var": "TAVILY_API_KEY",
        "key_masked": mask_key(key),
        "plan": "free (1000 searches/mo)",
        "documented_limits": {
            "searches_per_month": 1000,
        },
        "status": "OK" if status == 200 else "ERROR",
    }
    if status == 200:
        result["live"] = {"test_search": "OK"}
        result["utilization_pct"] = 0
    elif status == 432 or (isinstance(body, dict) and "credit" in json.dumps(body).lower()):
        result["status"] = "EXHAUSTED"
        result["error"] = "Credits exhausted (HTTP 432)"
        result["utilization_pct"] = 100
    elif status == 401:
        result["status"] = "INVALID_KEY"
        result["error"] = "Unauthorized (HTTP 401)"
        result["utilization_pct"] = 100
    elif err:
        result["error"] = err
        result["utilization_pct"] = 0

    return result


def check_openai():
    """OpenAI: List models to verify key."""
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return {"provider": "OpenAI", "env_var": "OPENAI_API_KEY", "key_masked": mask_key(key),
                "status": "NO_KEY", "error": "Key not set"}

    status, hdrs, body, err = http_get(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {key}"},
        timeout=10,
    )
    result = {
        "provider": "OpenAI",
        "env_var": "OPENAI_API_KEY",
        "key_masked": mask_key(key),
        "plan": "pay-as-you-go",
        "documented_limits": {
            "requests_per_min": 500,
            "tokens_per_min": 200000,
        },
        "status": "OK" if status == 200 else "ERROR",
    }
    if status == 200 and isinstance(body, dict):
        models = body.get("data", [])
        result["live"] = {"models_available": len(models)}
    elif status == 401:
        result["status"] = "INVALID_KEY"
        result["error"] = "Unauthorized"
    elif err:
        result["error"] = err

    # Rate headers
    rl = {}
    for h in ["x-ratelimit-limit-requests", "x-ratelimit-remaining-requests",
              "x-ratelimit-limit-tokens", "x-ratelimit-remaining-tokens"]:
        if h in hdrs:
            rl[h] = hdrs[h]
    if rl:
        result["headers"] = rl

    result.setdefault("utilization_pct", 0)
    return result


def check_xai():
    """xAI/Grok: Verify key."""
    key = os.environ.get("XAI_API_KEY", "")
    if not key:
        return {"provider": "xAI (Grok)", "env_var": "XAI_API_KEY", "key_masked": mask_key(key),
                "status": "NO_KEY", "error": "Key not set"}

    status, hdrs, body, err = http_get(
        "https://api.x.ai/v1/models",
        headers={"Authorization": f"Bearer {key}"},
        timeout=10,
    )
    result = {
        "provider": "xAI (Grok)",
        "env_var": "XAI_API_KEY",
        "key_masked": mask_key(key),
        "plan": "free tier",
        "documented_limits": {
            "requests_per_sec": 1,
            "requests_per_hour": 60,
        },
        "status": "OK" if status == 200 else "ERROR",
    }
    if status == 200 and isinstance(body, dict):
        models = body.get("data", body.get("models", []))
        if isinstance(models, list):
            result["live"] = {"models_available": len(models)}
    elif err:
        result["error"] = err

    result.setdefault("utilization_pct", 0)
    return result


def check_vercel():
    """Vercel: Check token by listing projects."""
    token = os.environ.get("VERCEL_TOKEN", "")
    if not token:
        return {"provider": "Vercel", "env_var": "VERCEL_TOKEN", "key_masked": mask_key(token),
                "status": "NO_KEY", "error": "Token not set"}

    status, hdrs, body, err = http_get(
        "https://api.vercel.com/v9/projects?limit=5",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    result = {
        "provider": "Vercel",
        "env_var": "VERCEL_TOKEN",
        "key_masked": mask_key(token),
        "plan": "hobby",
        "documented_limits": {
            "deployments_per_day": 100,
            "serverless_invocations": 100000,
            "bandwidth_gb": 100,
        },
        "status": "OK" if status == 200 else "ERROR",
    }
    if status == 200 and isinstance(body, dict):
        projects = body.get("projects", [])
        result["live"] = {
            "project_count": len(projects),
            "project_names": [p.get("name", "?") for p in projects],
        }
    elif err:
        result["error"] = err

    result.setdefault("utilization_pct", 0)
    return result


def check_upstash_redis():
    """Upstash Redis: ping via REST API."""
    rest_url = os.environ.get("UPSTASH_REDIS_REST_URL", "")
    rest_token = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
    if not rest_url or not rest_token:
        return {"provider": "Upstash Redis", "status": "NO_KEY", "error": "REST URL or token not set"}

    status, hdrs, body, err = http_get(
        f"{rest_url}/info",
        headers={"Authorization": f"Bearer {rest_token}"},
        timeout=10,
    )
    result = {
        "provider": "Upstash Redis",
        "env_var": "UPSTASH_REDIS_REST_URL",
        "key_masked": mask_key(rest_token),
        "plan": "free (10K commands/day)",
        "documented_limits": {
            "commands_per_day": 10000,
            "storage_mb": 256,
            "bandwidth_mb_per_day": 50,
        },
        "status": "OK" if status == 200 else "ERROR",
    }
    if status == 200:
        result["live"] = {"ping": "OK"}
    elif err:
        result["error"] = err

    result.setdefault("utilization_pct", 0)
    return result


def check_hf_token(env_var, label):
    """HuggingFace: Verify token via whoami."""
    token = os.environ.get(env_var, "")
    if not token:
        return {"provider": f"HuggingFace ({label})", "env_var": env_var, "key_masked": mask_key(token),
                "status": "NO_KEY", "error": "Token not set"}

    status, hdrs, body, err = http_get(
        "https://huggingface.co/api/whoami",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    result = {
        "provider": f"HuggingFace ({label})",
        "env_var": env_var,
        "key_masked": mask_key(token),
        "plan": "free",
        "documented_limits": {
            "spaces": 10,
            "inference_api_calls": "unlimited (queued)",
            "private_repos": 100,
        },
        "status": "OK" if status == 200 else "ERROR",
    }
    if status == 200 and isinstance(body, dict):
        result["live"] = {
            "username": body.get("name", "?"),
            "email": body.get("email", "?"),
            "orgs": [o.get("name", "?") for o in body.get("orgs", [])],
        }
    elif err:
        result["error"] = err

    result.setdefault("utilization_pct", 0)
    return result


# ---------------------------------------------------------------------------
# Main check orchestrator
# ---------------------------------------------------------------------------

def run_all_checks():
    """Run all provider checks, return structured results."""
    ts = datetime.now(timezone.utc).isoformat()
    results = []

    print(f"  [1/14] OpenRouter keys (7)...")
    or_keys = [
        ("OPENROUTER_API_KEY", "Main"),
        ("OPENROUTER_KEY_STANDARD", "Standard"),
        ("OPENROUTER_KEY_GRAPH", "Graph"),
        ("OPENROUTER_KEY_QUANTITATIVE", "Quant"),
        ("OPENROUTER_KEY_ORCHESTRATOR", "Orchestrator"),
        ("OPENROUTER_KEY_PME", "PME"),
        ("OPENROUTER_KEY_SPARE", "Spare"),
    ]
    for env_var, label in or_keys:
        results.append(check_openrouter(env_var, label))

    print(f"  [2/14] Groq keys (5)...")
    groq_keys = [
        ("GROQ_API_KEY", "#1"),
        ("GROQ_API_KEY_2", "#2"),
        ("GROQ_API_KEY_3", "#3"),
        ("GROQ_API_KEY_4", "#4"),
        ("GROQ_API_KEY_5", "#5"),
    ]
    for env_var, label in groq_keys:
        results.append(check_groq(env_var, label))

    print(f"  [3/14] Pinecone (2)...")
    results.append(check_pinecone("PINECONE_API_KEY", "Primary"))
    results.append(check_pinecone("PINECONE_API_KEY_2", "Secondary"))

    print(f"  [4/14] Supabase (2)...")
    results.append(check_supabase("SUPABASE_URL", "SUPABASE_API_KEY", "Primary"))
    results.append(check_supabase("SUPABASE_URL_2", "SUPABASE_ANON_KEY_2", "Secondary"))

    print(f"  [5/14] Stripe...")
    results.append(check_stripe())

    print(f"  [6/14] HF Spaces (10)...")
    spaces = [
        (os.environ.get("HF_SPACE_1_URL", ""), "S1 n8n Engine"),
        (os.environ.get("HF_SPACE_2_URL", ""), "S2 n8n Engine-2"),
        (os.environ.get("HF_SPACE_3_URL", ""), "S3 n8n Engine-3"),
        (os.environ.get("HF_SPACE_4_URL", ""), "S4 n8n Engine-4"),
        (os.environ.get("HF_SPACE_5_URL", ""), "S5 n8n Engine-5"),
        (os.environ.get("HF_SPACE_6_URL", ""), "S6 Docling"),
        (os.environ.get("HF_SPACE_7_URL", ""), "S7 LiteLLM"),
        (os.environ.get("HF_SPACE_8_URL", ""), "S8"),
        (os.environ.get("HF_SPACE_9_URL", ""), "S9 Ingest"),
        (os.environ.get("HF_SPACE_10_URL", ""), "S10"),
    ]
    for url, label in spaces:
        if url:
            results.append(check_hf_space(url, label))

    print(f"  [7/14] LiteLLM Proxy...")
    results.append(check_litellm())

    print(f"  [8/14] Google Gemini...")
    results.append(check_google_gemini())

    print(f"  [9/14] Jina (2)...")
    results.append(check_jina("JINA_API_KEY", "Primary"))
    results.append(check_jina("JINA_API_KEY_2", "Secondary"))

    print(f"  [10/14] Cohere (2)...")
    results.append(check_cohere("COHERE_API_KEY", "Primary"))
    results.append(check_cohere("COHERE_API_KEY_2", "Secondary"))

    print(f"  [11/14] Neo4j Bolt Proxy...")
    results.append(check_neo4j_bolt_proxy())

    print(f"  [12/14] Tavily...")
    results.append(check_tavily())

    print(f"  [13/14] Other (OpenAI, xAI, Vercel, Upstash, HF Tokens)...")
    results.append(check_openai())
    results.append(check_xai())
    results.append(check_vercel())
    results.append(check_upstash_redis())
    results.append(check_hf_token("HF_TOKEN", "Account 1"))
    results.append(check_hf_token("HF_TOKEN_2", "Account 2"))
    results.append(check_hf_token("HF_TOKEN_3", "Account 3"))

    print(f"  [14/14] Done.")

    # Build summary
    total = len(results)
    ok_count = sum(1 for r in results if r.get("status") in ("OK", "UP"))
    error_count = sum(1 for r in results if r.get("status") in ("ERROR", "DOWN", "EXHAUSTED", "INVALID_KEY"))
    warn_count = sum(1 for r in results if r.get("utilization_pct", 0) >= 80)
    critical_count = sum(1 for r in results if r.get("utilization_pct", 0) >= 90 or r.get("status") in ("EXHAUSTED", "DOWN", "INVALID_KEY"))

    report = {
        "timestamp": ts,
        "summary": {
            "total_providers": total,
            "ok": ok_count,
            "errors": error_count,
            "warnings_80pct": warn_count,
            "critical_90pct": critical_count,
        },
        "providers": results,
    }

    return report


# ---------------------------------------------------------------------------
# Alert logic
# ---------------------------------------------------------------------------
def check_and_alert(report, state):
    """Send Telegram alerts for critical providers."""
    alerts = []
    for p in report["providers"]:
        name = p.get("provider", "Unknown")
        status = p.get("status", "")
        util = p.get("utilization_pct", 0)

        if status in ("EXHAUSTED", "INVALID_KEY"):
            alerts.append(f"  {name}: {status}")
        elif status in ("DOWN", "ERROR") and "HF Space" in name:
            alerts.append(f"  {name}: {status}")
        elif util >= 90:
            alerts.append(f"  {name}: {util}% utilized")

    if alerts:
        # Debounce: don't send the same alert within 30min
        alert_key = "|".join(sorted(alerts))
        last = state.get("last_alerts", {}).get(alert_key, 0)
        now = time.time()
        if now - last > 1800:
            msg = f"*RATE LIMITS ALERT*\n\n" + "\n".join(alerts)
            telegram_notify(msg)
            state.setdefault("last_alerts", {})[alert_key] = now
            return True
    return False


# ---------------------------------------------------------------------------
# Markdown generator
# ---------------------------------------------------------------------------
def generate_markdown(report, state):
    """Generate RATE-LIMITS.md from the report."""
    ts = report["timestamp"]
    s = report["summary"]
    providers = report["providers"]

    lines = []
    lines.append("# API Rate Limits & Key Status")
    lines.append("")
    lines.append(f"> Auto-generated by `ops/rate-limits-tracker.py` at {ts}")
    lines.append(f"> DO NOT edit manually. Run `python3 ops/rate-limits-tracker.py --once --md` to refresh.")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total providers checked | {s['total_providers']} |")
    lines.append(f"| OK / UP | {s['ok']} |")
    lines.append(f"| Errors / Down | {s['errors']} |")
    lines.append(f"| Warnings (>80% utilized) | {s['warnings_80pct']} |")
    lines.append(f"| Critical (>90% / dead) | {s['critical_90pct']} |")
    lines.append("")

    # Alerts section
    critical = [p for p in providers if p.get("utilization_pct", 0) >= 80 or p.get("status") in ("EXHAUSTED", "DOWN", "INVALID_KEY", "ERROR")]
    if critical:
        lines.append("## ALERTS")
        lines.append("")
        for p in critical:
            name = p.get("provider", "?")
            status = p.get("status", "?")
            util = p.get("utilization_pct", 0)
            error = p.get("error", "")
            icon = "!!!" if util >= 90 or status in ("EXHAUSTED", "INVALID_KEY") else "(!)"
            lines.append(f"- **{icon} {name}**: status={status}, utilization={util}%{f', error={error}' if error else ''}")
        lines.append("")

    # Provider detail table
    lines.append("## All Providers")
    lines.append("")
    lines.append("| Provider | Key (masked) | Plan | Status | Utilization | Error |")
    lines.append("|----------|-------------|------|--------|------------|-------|")
    for p in providers:
        name = p.get("provider", "?")
        key_m = p.get("key_masked", p.get("url", "-"))
        plan = p.get("plan", "-")
        status = p.get("status", "?")
        util = p.get("utilization_pct", "-")
        error = p.get("error", "")
        if isinstance(util, (int, float)):
            util_str = f"{util}%"
        else:
            util_str = str(util)
        lines.append(f"| {name} | `{key_m}` | {plan} | {status} | {util_str} | {error[:50]} |")
    lines.append("")

    # Detailed sections per provider group
    groups = {}
    for p in providers:
        base = p.get("provider", "Unknown").split("(")[0].strip()
        groups.setdefault(base, []).append(p)

    for group_name, group_providers in groups.items():
        lines.append(f"## {group_name}")
        lines.append("")
        for p in group_providers:
            lines.append(f"### {p.get('provider', '?')}")
            lines.append("")
            lines.append(f"- **Key**: `{p.get('key_masked', p.get('url', '-'))}`")
            lines.append(f"- **Env var**: `{p.get('env_var', '-')}`")
            lines.append(f"- **Plan**: {p.get('plan', '-')}")
            lines.append(f"- **Status**: {p.get('status', '?')}")
            if p.get("documented_limits"):
                lines.append(f"- **Documented limits**:")
                for k, v in p["documented_limits"].items():
                    lines.append(f"  - {k}: {v}")
            if p.get("live"):
                lines.append(f"- **Live data**:")
                for k, v in p["live"].items():
                    if isinstance(v, (list, dict)):
                        lines.append(f"  - {k}: `{json.dumps(v, default=str)[:200]}`")
                    else:
                        lines.append(f"  - {k}: {v}")
            if p.get("headers"):
                lines.append(f"- **Rate limit headers**:")
                for k, v in p["headers"].items():
                    lines.append(f"  - `{k}`: {v}")
            if p.get("utilization_pct") is not None:
                lines.append(f"- **Utilization**: {p.get('utilization_pct', 0)}%")
            if p.get("error"):
                lines.append(f"- **Error**: {p['error']}")
            lines.append("")

    # Cumulative usage from state
    cum_req = state.get("cumulative_requests", {})
    cum_tok = state.get("cumulative_tokens", {})
    if cum_req or cum_tok:
        lines.append("## Cumulative Usage (tracked by log_api_call)")
        lines.append("")
        lines.append("| Provider | Total Requests | Total Tokens |")
        lines.append("|----------|---------------|-------------|")
        all_providers = sorted(set(list(cum_req.keys()) + list(cum_tok.keys())))
        for prov in all_providers:
            lines.append(f"| {prov} | {cum_req.get(prov, 0):,} | {cum_tok.get(prov, 0):,} |")
        lines.append("")

    lines.append("---")
    lines.append(f"*Last updated: {ts}*")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pretty-print for terminal
# ---------------------------------------------------------------------------
def pretty_print(report):
    """Terminal-friendly output."""
    s = report["summary"]
    ts = report["timestamp"]
    print(f"\n{'='*70}")
    print(f"  RATE LIMITS TRACKER — {ts}")
    print(f"  {s['total_providers']} providers | {s['ok']} OK | {s['errors']} errors | {s['warnings_80pct']} warnings | {s['critical_90pct']} critical")
    print(f"{'='*70}\n")

    # Group by status
    for status_label, filter_fn in [
        ("CRITICAL / EXHAUSTED", lambda p: p.get("status") in ("EXHAUSTED", "INVALID_KEY", "DOWN") or p.get("utilization_pct", 0) >= 90),
        ("WARNINGS (>80%)", lambda p: 80 <= p.get("utilization_pct", 0) < 90 and p.get("status") not in ("EXHAUSTED", "INVALID_KEY", "DOWN")),
        ("OK", lambda p: p.get("status") in ("OK", "UP") and p.get("utilization_pct", 0) < 80),
        ("ERRORS", lambda p: p.get("status") == "ERROR" and p.get("utilization_pct", 0) < 80),
        ("NO KEY", lambda p: p.get("status") == "NO_KEY"),
    ]:
        matching = [p for p in report["providers"] if filter_fn(p)]
        if not matching:
            continue

        if status_label == "CRITICAL / EXHAUSTED":
            marker = "!!!"
        elif status_label == "WARNINGS (>80%)":
            marker = "(!)"
        elif status_label == "OK":
            marker = " * "
        elif status_label == "ERRORS":
            marker = " X "
        else:
            marker = " - "

        print(f"  [{marker}] {status_label} ({len(matching)}):")
        for p in matching:
            name = p.get("provider", "?")
            util = p.get("utilization_pct", "-")
            err = p.get("error", "")
            status = p.get("status", "?")
            live_info = ""
            live = p.get("live", {})
            if isinstance(live, dict):
                # Pick interesting live fields
                for k in ["credits_remaining", "total_vectors", "sector_documents_count",
                           "models_available", "latency_ms", "total_nodes", "health"]:
                    if k in live:
                        live_info += f" {k}={live[k]}"
            util_str = f"{util}%" if isinstance(util, (int, float)) else str(util)
            err_str = f" | {err}" if err else ""
            print(f"    {name:<35s} {status:<12s} {util_str:>6s}{live_info}{err_str}")
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    load_env()

    once = "--once" in sys.argv
    json_only = "--json" in sys.argv
    gen_md = "--md" in sys.argv
    interval = 60

    if not json_only:
        print(f"[rate-limits-tracker] {'ONE-SHOT' if once else f'LOOP {interval}s'} mode")
        print(f"[rate-limits-tracker] Output: {LIVE_JSON}")
        print(f"[rate-limits-tracker] Events: {EVENTS_LOG}")
        print()

    while True:
        ts_start = time.time()
        state = load_state()

        if not json_only:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Running checks...")

        report = run_all_checks()

        # Save JSON
        LIVE_JSON.write_text(json.dumps(report, indent=2, default=str))

        # Log event
        log_event("check", {
            "summary": report["summary"],
            "duration_s": round(time.time() - ts_start, 1),
        })

        # Check alerts
        alerted = check_and_alert(report, state)
        if alerted:
            log_event("alert", {"summary": report["summary"]})

        # Save state
        save_state(state)

        # Output
        if json_only:
            print(json.dumps(report, indent=2, default=str))
        else:
            pretty_print(report)

        # Generate markdown if requested
        if gen_md:
            md = generate_markdown(report, state)
            MD_FILE.write_text(md)
            if not json_only:
                print(f"  [MD] Written to {MD_FILE}")

        if once:
            break

        if not json_only:
            print(f"  Next check in {interval}s...")
        time.sleep(interval)


if __name__ == "__main__":
    main()
