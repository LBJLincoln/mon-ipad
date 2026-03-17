#!/usr/bin/env python3
"""PRODUIT Agent — Product health, feature tracking, UX monitoring.

Checks all 8 websites, measures response times, tracks feature completion.
"""

import os
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base import load_env, llm_call, telegram_notify, log_event, http_get, http_post, run_agent_loop

CATEGORY = "produit"

SITES = [
    {"name": "Expert (main)", "url": "https://nomos42.vercel.app", "critical": True},
    {"name": "Satellite", "url": "https://nomos42.vercel.app/satellite", "critical": False},
    {"name": "Marketplace", "url": "https://nomos42.vercel.app/marketplace", "critical": False},
    {"name": "Factory", "url": "https://nomos42.vercel.app/factory", "critical": True},
    {"name": "Vault", "url": "https://nomos42.vercel.app/vault", "critical": False},
    {"name": "Dashboard", "url": "https://nomos42.vercel.app/dashboard", "critical": False},
    {"name": "Valorisation", "url": "https://nomos42.vercel.app/valorisation", "critical": False},
    {"name": "Graph", "url": "https://nomos42.vercel.app/graph", "critical": False},
    {"name": "Casino", "url": "https://nomos42.vercel.app/casino", "critical": False},
]

FEATURES = [
    {"name": "Stripe checkout (Factory)", "endpoint": "/api/stripe/checkout", "status": "deployed"},
    {"name": "Stripe webhook", "endpoint": "/api/stripe/webhook", "status": "deployed"},
    {"name": "Forge AI analysis", "endpoint": "/api/forge", "status": "deployed"},
    {"name": "Friends & Family", "endpoint": "/api/friends", "status": "deployed"},
    {"name": "Price Negotiator", "component": "PriceNegotiator.tsx", "status": "deployed"},
    {"name": "Casino slot machine", "page": "/casino", "status": "deployed"},
    {"name": "Refinement chat", "endpoint": "/api/forge/chat", "status": "deployed"},
    {"name": "RAG query", "endpoint": "/api/query", "status": "needs_check"},
]


def check_sites():
    """Check all websites for availability and response time."""
    results = []
    down_sites = []

    for site in SITES:
        start = time.time()
        resp = http_get(site["url"])
        latency_ms = int((time.time() - start) * 1000)

        status = "UP" if resp.get("ok") or resp.get("status") == 200 else "DOWN"
        if resp.get("status") in (301, 302, 307, 308):
            status = "REDIRECT"

        results.append({
            "name": site["name"],
            "url": site["url"],
            "status": status,
            "http_code": resp.get("status", 0),
            "latency_ms": latency_ms,
            "critical": site["critical"],
        })

        if status == "DOWN" and site["critical"]:
            down_sites.append(site["name"])

    return results, down_sites


def check_api_endpoints():
    """Quick health check on API endpoints."""
    results = []
    base = "https://nomos42.vercel.app"

    # Test forge endpoint with minimal request
    forge = http_post(f"{base}/api/forge", {"idea": "test", "sector": "finance"})
    results.append({
        "endpoint": "/api/forge",
        "status": "OK" if forge.get("ok") or forge.get("status") in (200, 400, 502) else "DOWN",
        "http_code": forge.get("status", 0),
    })

    return results


def tick():
    """One product cycle."""
    print("  Checking all sites...")
    site_results, down_sites = check_sites()

    up_count = sum(1 for s in site_results if s["status"] == "UP")
    avg_latency = sum(s["latency_ms"] for s in site_results) / max(len(site_results), 1)

    print(f"  Sites: {up_count}/{len(site_results)} UP | Avg latency: {avg_latency:.0f}ms")

    print("  Checking API endpoints...")
    api_results = check_api_endpoints()

    report = {
        "sites": site_results,
        "apis": api_results,
        "features": FEATURES,
        "summary": {
            "sites_up": up_count,
            "sites_total": len(site_results),
            "avg_latency_ms": round(avg_latency),
            "features_deployed": sum(1 for f in FEATURES if f["status"] == "deployed"),
            "features_total": len(FEATURES),
        },
    }

    # Alert on critical sites down
    if down_sites:
        telegram_notify(
            f"[PRODUIT] SITES DOWN: {', '.join(down_sites)}\n"
            f"UP: {up_count}/{len(site_results)}",
        )

    return report


if __name__ == "__main__":
    run_agent_loop(CATEGORY, tick, interval=600)  # Every 10 minutes
