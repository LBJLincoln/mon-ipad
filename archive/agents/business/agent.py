#!/usr/bin/env python3
"""BUSINESS Agent — Revenue tracking, cost analysis, conversion funnel.

Queries Stripe, Whop, Gumroad APIs every cycle.
Tracks MRR, subscriptions, API costs, burn rate.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base import load_env, llm_call, telegram_notify, log_event, http_get, run_agent_loop

CATEGORY = "business"


def check_stripe():
    """Query Stripe for revenue data."""
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key:
        return {"stripe": "NO_KEY"}

    # Get balance
    balance = http_get("https://api.stripe.com/v1/balance", headers={"Authorization": f"Bearer {key}"})

    # Get recent charges
    charges = http_get(
        "https://api.stripe.com/v1/charges?limit=10",
        headers={"Authorization": f"Bearer {key}"},
    )

    # Get subscriptions
    subs = http_get(
        "https://api.stripe.com/v1/subscriptions?limit=100&status=active",
        headers={"Authorization": f"Bearer {key}"},
    )

    result = {
        "balance_ok": balance.get("ok", False),
        "charges_count": len(charges.get("body", {}).get("data", [])) if charges.get("ok") else 0,
        "active_subscriptions": len(subs.get("body", {}).get("data", [])) if subs.get("ok") else 0,
    }

    if balance.get("ok") and balance.get("body"):
        available = balance["body"].get("available", [{}])
        pending = balance["body"].get("pending", [{}])
        result["balance_available_cents"] = sum(a.get("amount", 0) for a in available)
        result["balance_pending_cents"] = sum(p.get("amount", 0) for p in pending)

    # Calculate MRR from active subscriptions
    mrr_cents = 0
    if subs.get("ok") and subs.get("body", {}).get("data"):
        for sub in subs["body"]["data"]:
            for item in sub.get("items", {}).get("data", []):
                price = item.get("price", {})
                amount = price.get("unit_amount", 0) or 0
                interval = price.get("recurring", {}).get("interval", "month")
                if interval == "year":
                    amount = amount // 12
                mrr_cents += amount
    result["mrr_cents"] = mrr_cents

    return result


def check_whop():
    """Query Whop for sales data."""
    key = os.environ.get("WHOP_API_KEY", "")
    if not key:
        return {"whop": "NO_KEY"}

    memberships = http_get(
        "https://api.whop.com/api/v5/company/memberships?per=100",
        headers={"Authorization": f"Bearer {key}"},
    )

    return {
        "whop_ok": memberships.get("ok", False),
        "whop_memberships": len(memberships.get("body", {}).get("data", [])) if memberships.get("ok") else 0,
    }


def check_gumroad():
    """Query Gumroad for sales data."""
    token = os.environ.get("GUMROAD_ACCESS_TOKEN", "")
    if not token:
        return {"gumroad": "NO_KEY"}

    sales = http_get(
        f"https://api.gumroad.com/v2/sales?access_token={token}",
    )

    products = http_get(
        f"https://api.gumroad.com/v2/products?access_token={token}",
    )

    return {
        "gumroad_ok": sales.get("ok", False),
        "gumroad_sales": len(sales.get("body", {}).get("sales", [])) if sales.get("ok") else 0,
        "gumroad_products": len(products.get("body", {}).get("products", [])) if products.get("ok") else 0,
    }


def estimate_costs():
    """Estimate monthly infrastructure costs."""
    costs = {
        "hf_spaces_free": 0,  # Free tier
        "vercel_free": 0,  # Free tier
        "supabase_free": 0,  # Free tier
        "neo4j_free": 0,  # Free Aura tier
        "pinecone_free": 0,  # Free tier
        "openrouter_usage": "variable",  # Pay-per-token
        "groq_free": 0,  # Free tier
        "gcloud_vm": 0,  # e2-micro free tier
        "domain": 0,  # No custom domain yet
    }
    return {"estimated_monthly_cost_usd": 0, "note": "All free tiers", "breakdown": costs}


def tick():
    """One business cycle."""
    stripe_data = check_stripe()
    whop_data = check_whop()
    gumroad_data = check_gumroad()
    cost_data = estimate_costs()

    # Aggregate
    total_revenue_cents = stripe_data.get("balance_available_cents", 0)
    mrr = stripe_data.get("mrr_cents", 0) / 100
    total_subs = stripe_data.get("active_subscriptions", 0)
    total_whop = whop_data.get("whop_memberships", 0)
    total_gumroad = gumroad_data.get("gumroad_sales", 0)

    report = {
        "stripe": stripe_data,
        "whop": whop_data,
        "gumroad": gumroad_data,
        "costs": cost_data,
        "summary": {
            "mrr_usd": mrr,
            "total_subscriptions": total_subs,
            "total_revenue_available_usd": total_revenue_cents / 100,
            "whop_memberships": total_whop,
            "gumroad_sales": total_gumroad,
            "burn_rate_usd": 0,
            "runway_months": "infinite (free tier)",
        },
    }

    # Alert if first revenue ever
    if mrr > 0 or total_subs > 0:
        telegram_notify(
            f"[BUSINESS] REVENUE DETECTED!\n"
            f"MRR: ${mrr:.2f}\n"
            f"Subs: {total_subs}\n"
            f"Whop: {total_whop}\n"
            f"Gumroad: {total_gumroad}",
        )

    print(f"  MRR=${mrr:.2f} | Subs={total_subs} | Whop={total_whop} | Gumroad={total_gumroad}")
    return report


if __name__ == "__main__":
    run_agent_loop(CATEGORY, tick, interval=3600)  # Every hour
