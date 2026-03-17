#!/usr/bin/env python3
"""ADMIN Agent — Credential auditing, cost tracking, infrastructure health.

Checks all API keys are valid, monitors resource usage, tracks costs.
"""

import os
import sys
import subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base import load_env, telegram_notify, log_event, http_get, http_post, run_agent_loop, ctx

CATEGORY = "admin"


def audit_credentials():
    """Check if all API keys are still valid by pinging each service."""
    results = {}

    # LiteLLM proxy
    r = http_get(
        f"{os.environ.get('LITELLM_PROXY_URL', 'https://lbjlincoln-nomos-rag-engine-7.hf.space')}/health",
    )
    results["litellm"] = "OK" if r.get("ok") else f"DOWN ({r.get('status')})"

    # OpenRouter — check models endpoint
    r = http_get(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY', '')}"},
    )
    results["openrouter"] = "OK" if r.get("ok") else f"FAIL ({r.get('status')})"

    # Groq
    r = http_get(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {os.environ.get('GROQ_API_KEY', '')}"},
    )
    results["groq"] = "OK" if r.get("ok") else f"FAIL ({r.get('status')})"

    # Pinecone
    r = http_get(
        "https://api.pinecone.io/indexes",
        headers={"Api-Key": os.environ.get("PINECONE_API_KEY", "")},
    )
    results["pinecone"] = "OK" if r.get("ok") else f"FAIL ({r.get('status')})"

    # Supabase
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_API_KEY", "")
    if url and key:
        r = http_get(f"{url}/rest/v1/", headers={"apikey": key, "Authorization": f"Bearer {key}"})
        results["supabase"] = "OK" if r.get("ok") or r.get("status") == 200 else f"FAIL ({r.get('status')})"

    # Stripe
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if stripe_key:
        r = http_get("https://api.stripe.com/v1/balance", headers={"Authorization": f"Bearer {stripe_key}"})
        results["stripe"] = "OK" if r.get("ok") else f"FAIL ({r.get('status')})"

    # HF Spaces
    for space_num in [1, 3, 5, 7, 9]:
        env_key = f"HF_SPACE_{space_num}_URL"
        url = os.environ.get(env_key, "")
        if url:
            r = http_get(url, timeout=10)
            name = f"hf_s{space_num}"
            results[name] = "OK" if r.get("ok") or r.get("status") in (200, 301, 302) else f"DOWN ({r.get('status')})"

    # Tavily
    r = http_post(
        "https://api.tavily.com/search",
        {"api_key": os.environ.get("TAVILY_API_KEY", ""), "query": "test", "max_results": 1},
    )
    results["tavily"] = "OK" if r.get("ok") else f"FAIL ({r.get('status')})"

    # Jina
    r = http_get(
        "https://api.jina.ai/v1/embeddings",
        headers={"Authorization": f"Bearer {os.environ.get('JINA_API_KEY', '')}"},
    )
    # Jina returns 422 for missing body but 401 for bad key
    results["jina"] = "OK" if r.get("status") in (200, 422) else f"FAIL ({r.get('status')})"

    return results


def check_vm_resources():
    """Check VM resource usage."""
    try:
        # Memory
        r = subprocess.run("free -m | awk '/Mem:/{printf \"%d/%dMB (%.0f%%)\", $3, $2, $3/$2*100}'",
                          shell=True, capture_output=True, text=True, timeout=5)
        memory = r.stdout.strip()

        # Disk
        r = subprocess.run("df -h / | awk 'NR==2{printf \"%s/%s (%s)\", $3, $2, $5}'",
                          shell=True, capture_output=True, text=True, timeout=5)
        disk = r.stdout.strip()

        # Processes
        r = subprocess.run("ps aux --no-headers | wc -l",
                          shell=True, capture_output=True, text=True, timeout=5)
        processes = r.stdout.strip()

        # Agent processes
        r = subprocess.run("ps aux --no-headers | grep -E 'python3.*(ops/|eval/|agents/)' | grep -v grep | wc -l",
                          shell=True, capture_output=True, text=True, timeout=5)
        agent_procs = r.stdout.strip()

        return {
            "memory": memory,
            "disk": disk,
            "total_processes": int(processes),
            "agent_processes": int(agent_procs),
        }
    except Exception as e:
        return {"error": str(e)}


def count_active_daemons():
    """Count running daemon processes."""
    try:
        r = subprocess.run(
            "ps aux --no-headers | grep -E 'python3.*(ops/|eval/|agents/)' | grep -v grep | awk '{for(i=11;i<=NF;i++) printf \"%s \",$(i); print \"\"}'",
            shell=True, capture_output=True, text=True, timeout=5,
        )
        daemons = [line.strip() for line in r.stdout.strip().split("\n") if line.strip()]
        return {"count": len(daemons), "list": daemons[:20]}
    except Exception:
        return {"count": 0, "list": []}


def tick():
    """One admin cycle."""
    print("  Auditing credentials...")
    creds = audit_credentials()
    ok_count = sum(1 for v in creds.values() if v == "OK")
    total = len(creds)
    print(f"  Credentials: {ok_count}/{total} OK")

    failed = {k: v for k, v in creds.items() if v != "OK"}
    if failed:
        print(f"  FAILED: {failed}")

    print("  Checking VM resources...")
    resources = check_vm_resources()
    print(f"  RAM: {resources.get('memory', '?')} | Disk: {resources.get('disk', '?')}")

    daemons = count_active_daemons()
    print(f"  Active daemons: {daemons['count']}")

    report = {
        "credentials": creds,
        "credentials_ok": ok_count,
        "credentials_total": total,
        "resources": resources,
        "daemons": daemons,
    }

    # Alert on failed credentials
    if failed:
        telegram_notify(
            f"[ADMIN] Credential audit: {ok_count}/{total} OK\n"
            f"FAILED: {', '.join(f'{k}={v}' for k,v in list(failed.items())[:5])}",
            silent=True,
        )

    return report


if __name__ == "__main__":
    run_agent_loop(CATEGORY, tick, interval=3600)  # Every hour
