#!/usr/bin/env python3
"""Multi-channel product setup for Gumroad and Lemon Squeezy.

Both platforms have restricted their APIs:
- Gumroad: Product creation endpoint removed (404). Read-only API only.
- Lemon Squeezy: Products endpoint is read-only (405). Must create via dashboard.

This script:
1. Verifies API connectivity to both platforms
2. Checks for any existing products
3. Provides step-by-step manual creation instructions
4. After manual creation: fetches all product links via API
5. Generates consolidated multi-channel-links.md

Usage:
    export $(grep -v '^#' .env.local | xargs)
    python3 monetisation/multi-channel-setup.py           # Full setup
    python3 monetisation/multi-channel-setup.py --fetch    # Fetch existing products only
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

# ---------------------------------------------------------------------------
# Product catalog
# ---------------------------------------------------------------------------
PRODUCTS = [
    {
        "id": "mega_bundle",
        "name": "MEGA BUNDLE - All 13 RAG Products",
        "price_cents": 49700,
        "price_display": "$497",
        "stripe_url": "https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d",
        "description": (
            "Everything. One payment. Lifetime access.\n\n"
            "Complete RAG engineering toolkit: Architecture Blueprint, n8n Workflows, "
            "Enterprise Site Template, Agentic Commerce Playbook, RAG Engineering Handbook, "
            "Eval Framework, Ingestion Toolkit, Dashboard Template, Benchmark Dataset, "
            "Embeddings Service, Debug Playbook, Claude Code Skills, Agent Context Kit.\n\n"
            "Over $1,400 in value. Built across 80+ engineering sessions, "
            "tested on 61,661 questions from 18 SOTA benchmarks.\n\n"
            "By Alexis Moret (Polytechnique + HEC Paris)."
        ),
    },
    {
        "id": "architecture",
        "name": "Architecture Blueprint - Multi-Pipeline RAG System",
        "price_cents": 19700,
        "price_display": "$197",
        "stripe_url": "https://buy.stripe.com/aFa14g4vob1x3f5bcp5J602",
        "description": (
            "Complete architecture for a production multi-pipeline RAG system. "
            "Standard, Graph, and Quantitative pipelines. "
            "n8n orchestration, Pinecone + Neo4j + Supabase integration. "
            "Battle-tested across 61,000+ questions."
        ),
    },
    {
        "id": "n8n_workflows",
        "name": "n8n Workflow Collection - Production RAG Workflows",
        "price_cents": 19700,
        "price_display": "$197",
        "stripe_url": "https://buy.stripe.com/bJe00c9PI8Tp2b1a8l5J603",
        "description": (
            "7 production n8n workflow files covering Standard RAG, "
            "Graph RAG, Quantitative RAG, website pipelines, and the orchestrator. "
            "Ready to import and customize."
        ),
    },
    {
        "id": "enterprise_site",
        "name": "Enterprise Site Template - Next.js 15",
        "price_cents": 19700,
        "price_display": "$197",
        "stripe_url": "https://buy.stripe.com/14A6oAaTM4D94j93JX5J604",
        "description": (
            "Full Next.js 15 website template with 4 sector verticals "
            "(Finance, Legal, Construction, Industry), embedded chatbots, "
            "responsive design, and deployment config."
        ),
    },
    {
        "id": "agentic_commerce",
        "name": "Agentic Commerce Playbook",
        "price_cents": 19700,
        "price_display": "$197",
        "stripe_url": "https://buy.stripe.com/aFa3co9PI5Hd2b11BP5J607",
        "description": (
            "The definitive guide to agentic commerce. "
            "How to make your products discoverable and purchasable by AI agents. "
            "ACP protocol implementation, structured data, GEO strategy."
        ),
    },
    {
        "id": "rag_handbook",
        "name": "RAG Engineering Handbook",
        "price_cents": 14700,
        "price_display": "$147",
        "stripe_url": "https://buy.stripe.com/eVq14g6Dwd9F6rh54h5J606",
        "description": (
            "Comprehensive handbook distilled from 80+ engineering sessions. "
            "Covers retrieval strategies, prompt engineering, embedding optimization, "
            "reranking, evaluation methodology, and production deployment patterns."
        ),
    },
    {
        "id": "eval_framework",
        "name": "RAG Eval Framework - 61K-Question System",
        "price_cents": 12700,
        "price_display": "$127",
        "stripe_url": "https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605",
        "description": (
            "Complete evaluation framework: 61,661 questions from 18 SOTA benchmarks. "
            "Parallel runner, golden evals, regression detection."
        ),
    },
    {
        "id": "ingestion_toolkit",
        "name": "Ingestion Toolkit - V4 Pipeline",
        "price_cents": 9700,
        "price_display": "$97",
        "stripe_url": "https://buy.stripe.com/dRm7sEfa27PlcPFgwJ5J608",
        "description": (
            "Data ingestion pipeline: 34,000+ records across 4 sectors. "
            "Docling integration, sector-aware chunking, multi-database upsert."
        ),
    },
    {
        "id": "dashboard_template",
        "name": "Dashboard Template - Real-Time RAG Metrics",
        "price_cents": 9700,
        "price_display": "$97",
        "stripe_url": "https://buy.stripe.com/14AcMYbXQ7PldTJ5S55J60a",
        "description": (
            "HTML/JS dashboard showing live pipeline metrics, accuracy trends, "
            "infrastructure status, and phase progress. Auto-generates from status.json."
        ),
    },
    {
        "id": "benchmark_dataset",
        "name": "Benchmark Dataset Toolkit - 61K Questions",
        "price_cents": 6700,
        "price_display": "$67",
        "stripe_url": "https://buy.stripe.com/cNi5kwaTMfhN5nd3JX5J60b",
        "description": (
            "Curated dataset of 61,661 questions from 18 SOTA benchmarks. "
            "Pre-categorized by pipeline type (Standard, Graph, Quant)."
        ),
    },
    {
        "id": "embeddings_service",
        "name": "Embeddings Service - Self-Hosted Jina",
        "price_cents": 6700,
        "price_display": "$67",
        "stripe_url": "https://buy.stripe.com/aFa00ce5Y0mT9Dtcgt5J60c",
        "description": (
            "Self-hosted embedding service on HF Spaces. Jina v3 1024-dim, "
            "Gradio API, health monitoring. Drop-in Jina Cloud replacement."
        ),
    },
    {
        "id": "debug_playbook",
        "name": "RAG Debug Playbook - 75+ Fixes",
        "price_cents": 4700,
        "price_display": "$47",
        "stripe_url": "https://buy.stripe.com/00w7sEd1U2v14j92FT5J600",
        "description": (
            "Library of 75+ real fixes. Diagnostic flowcharts, n8n gotchas, "
            "Pinecone/Neo4j/Supabase patterns, embedding pitfalls, LLM prompt fixes."
        ),
    },
    {
        "id": "claude_skills",
        "name": "Claude Code Skills Pack - 17 Commands",
        "price_cents": 4700,
        "price_display": "$47",
        "stripe_url": "https://buy.stripe.com/7sY8wIge64D93f53JX5J609",
        "description": (
            "17 production slash commands for Claude Code: session-start, eval, "
            "sync-directives, self-heal, progress-10pct, regression-check, and more."
        ),
    },
    {
        "id": "agent_context_kit",
        "name": "Agent Context Kit - CLAUDE.md Templates",
        "price_cents": 2700,
        "price_display": "$27",
        "stripe_url": "https://buy.stripe.com/7sY9AMbXQ4D94j95S55J601",
        "description": (
            "Template system for AI agent context: CLAUDE.md, PROJECT-STATE.md, "
            "DEBUG-PLAYBOOK.md, INFRASTRUCTURE.md. The exact system powering this project."
        ),
    },
]

# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def http_get(url, headers=None):
    """GET request. Returns (status, parsed_json)."""
    req = urllib.request.Request(url)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body[:500]}
    except Exception as e:
        return 0, {"error": str(e)}


# ---------------------------------------------------------------------------
# GUMROAD: Fetch existing products
# ---------------------------------------------------------------------------

def fetch_gumroad_products(access_token):
    """Fetch existing products from Gumroad."""
    print("\n  Fetching Gumroad products...")
    status, resp = http_get(
        f"https://api.gumroad.com/v2/products?access_token={access_token}"
    )
    if status == 200 and resp.get("success"):
        products = resp.get("products", [])
        print(f"    Found: {len(products)} products")
        results = []
        for p in products:
            results.append({
                "gumroad_id": p.get("id", ""),
                "name": p.get("name", ""),
                "price_cents": p.get("price", 0),
                "short_url": p.get("short_url", ""),
                "published": p.get("published", False),
                "sales_count": p.get("sales_count", 0),
            })
            print(f"    - {p.get('name', 'N/A')} | ${p.get('price', 0)/100:.0f} | {p.get('short_url', '')}")
        return results
    else:
        print(f"    Failed: HTTP {status}")
        return []


# ---------------------------------------------------------------------------
# LEMON SQUEEZY: Fetch existing products and store info
# ---------------------------------------------------------------------------

def fetch_lemon_squeezy_store(api_key):
    """Get Lemon Squeezy store info."""
    print("\n  Fetching Lemon Squeezy store...")
    status, resp = http_get(
        "https://api.lemonsqueezy.com/v1/stores",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/vnd.api+json",
        },
    )
    if status == 200:
        stores = resp.get("data", [])
        if stores:
            store = stores[0]
            attrs = store.get("attributes", {})
            store_id = store["id"]
            store_name = attrs.get("name", "Unknown")
            store_url = attrs.get("url", "")
            store_slug = attrs.get("slug", "")
            print(f"    Store: {store_name} (ID: {store_id})")
            print(f"    URL: {store_url}")
            return {
                "id": store_id,
                "name": store_name,
                "url": store_url,
                "slug": store_slug,
            }
    print("    No store found")
    return None


def fetch_lemon_squeezy_products(api_key):
    """Fetch existing products from Lemon Squeezy."""
    print("\n  Fetching Lemon Squeezy products...")
    status, resp = http_get(
        "https://api.lemonsqueezy.com/v1/products",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/vnd.api+json",
        },
    )
    if status == 200:
        products = resp.get("data", [])
        print(f"    Found: {len(products)} products")
        results = []
        for p in products:
            attrs = p.get("attributes", {})
            results.append({
                "ls_id": p.get("id", ""),
                "name": attrs.get("name", ""),
                "price": attrs.get("price", 0),
                "status": attrs.get("status", ""),
                "buy_now_url": attrs.get("buy_now_url", ""),
                "store_url": attrs.get("store_url", ""),
            })
            url = attrs.get("buy_now_url", "") or attrs.get("store_url", "")
            print(f"    - {attrs.get('name', 'N/A')} | {attrs.get('status', '')} | {url}")
        return results
    else:
        print(f"    Failed: HTTP {status}")
        return []


def fetch_lemon_squeezy_variants(api_key):
    """Fetch variants from Lemon Squeezy (needed for checkout URLs)."""
    print("\n  Fetching Lemon Squeezy variants...")
    status, resp = http_get(
        "https://api.lemonsqueezy.com/v1/variants",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/vnd.api+json",
        },
    )
    if status == 200:
        variants = resp.get("data", [])
        print(f"    Found: {len(variants)} variants")
        results = []
        for v in variants:
            attrs = v.get("attributes", {})
            results.append({
                "variant_id": v.get("id", ""),
                "name": attrs.get("name", ""),
                "price": attrs.get("price", 0),
                "product_id": attrs.get("product_id", ""),
            })
        return results
    return []


# ---------------------------------------------------------------------------
# Generate links file
# ---------------------------------------------------------------------------

def generate_links_file(gumroad_products, ls_store, ls_products):
    """Generate multi-channel-links.md."""
    output_path = "/home/termius/mon-ipad/monetisation/multi-channel-links.md"

    lines = [
        "# Multi-Channel Payment Links",
        "",
        f"> Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "All Nomos AI products across 3 payment platforms.",
        "",
        "---",
        "",
        "## 1. Stripe (Primary) -- 14 products LIVE",
        "",
        "| # | Product | Price | Payment Link |",
        "|---|---------|-------|--------------|",
    ]

    for i, p in enumerate(PRODUCTS, 1):
        lines.append(f"| {i} | {p['name']} | {p['price_display']} | {p['stripe_url']} |")

    # Gumroad section
    lines.extend(["", "---", "", "## 2. Gumroad", ""])

    if gumroad_products:
        lines.extend([
            f"Store: https://nomos42.gumroad.com",
            "",
            "| # | Product | Price | Link |",
            "|---|---------|-------|------|",
        ])
        for i, gp in enumerate(gumroad_products, 1):
            price_str = f"${gp['price_cents']/100:.0f}" if gp.get('price_cents') else "N/A"
            lines.append(f"| {i} | {gp['name']} | {price_str} | {gp.get('short_url', 'N/A')} |")
    else:
        lines.extend([
            "**Status**: No products yet. Create manually at https://gumroad.com/products/new",
            "",
            "**API Note**: Gumroad has removed product creation from their API (POST /v2/products returns 404).",
            "Products must be created through the web dashboard.",
            "",
            "Store URL: https://nomos42.gumroad.com",
        ])

    lines.extend([
        "",
        "### Gumroad Manual Creation Steps",
        "",
        "1. Log in at https://gumroad.com/login",
        "2. Go to https://gumroad.com/products/new",
        "3. Create each product with these details:",
        "",
    ])

    for p in PRODUCTS:
        slug = p['id'].replace('_', '-')
        lines.extend([
            f"**{p['name']}** ({p['price_display']})",
            f"- Price: {p['price_cents']} cents",
            f"- Slug: `{slug}`",
            f"- Description: {p['description'][:120]}...",
            "",
        ])

    lines.extend([
        "4. After creating all products, run:",
        "   ```",
        "   export $(grep -v '^#' .env.local | xargs)",
        "   python3 monetisation/multi-channel-setup.py --fetch",
        "   ```",
    ])

    # Lemon Squeezy section
    lines.extend(["", "---", "", "## 3. Lemon Squeezy", ""])

    store_url = ls_store.get("url", "") if ls_store else ""
    store_slug = ls_store.get("slug", "nomos42") if ls_store else "nomos42"

    if ls_products:
        lines.extend([
            f"Store: {store_url}",
            "",
            "| # | Product | Status | Link |",
            "|---|---------|--------|------|",
        ])
        for i, lp in enumerate(ls_products, 1):
            url = lp.get("buy_now_url", "") or lp.get("store_url", "")
            lines.append(f"| {i} | {lp['name']} | {lp.get('status', '')} | {url or 'N/A'} |")
    else:
        lines.extend([
            f"**Status**: No products yet. Create at https://app.lemonsqueezy.com",
            "",
            "**API Note**: Lemon Squeezy API does not support POST on /v1/products.",
            "Products must be created through the dashboard.",
            "",
            f"Store: {store_url}",
        ])

    lines.extend([
        "",
        "### Lemon Squeezy Manual Creation Steps",
        "",
        "1. Log in at https://app.lemonsqueezy.com",
        "2. Navigate to Products > New Product",
        "3. Create each product with these details:",
        "",
    ])

    for p in PRODUCTS:
        slug = p['id'].replace('_', '-')
        lines.extend([
            f"**{p['name']}** ({p['price_display']})",
            f"- Price: ${p['price_cents']/100:.0f}",
            f"- Slug: `{slug}`",
            f"- Description: {p['description'][:120]}...",
            "",
        ])

    lines.extend([
        "4. After creating all products, run:",
        "   ```",
        "   export $(grep -v '^#' .env.local | xargs)",
        "   python3 monetisation/multi-channel-setup.py --fetch",
        "   ```",
    ])

    # Summary
    lines.extend([
        "",
        "---",
        "",
        "## Sales Pages & Bots",
        "",
        "- **Main store**: https://lbjlincoln.github.io/rag-dashboard/store.html",
        "- **Telegram bot**: @Nomos42Bot",
        f"- **Gumroad store**: https://nomos42.gumroad.com",
        f"- **Lemon Squeezy store**: {store_url}",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"| Platform | Products | Status |",
        f"|----------|----------|--------|",
        f"| Stripe | 14 | LIVE |",
        f"| Gumroad | {len(gumroad_products)} | {'LIVE' if gumroad_products else 'PENDING (manual creation needed)'} |",
        f"| Lemon Squeezy | {len(ls_products)} | {'LIVE' if ls_products else 'PENDING (manual creation needed)'} |",
        "",
        "## API Limitations Discovered",
        "",
        "- **Gumroad**: POST /v2/products returns 404. Product creation API has been removed.",
        "  Read endpoints (GET /v2/products, GET /v2/user) still work.",
        "  Write endpoints for webhooks (PUT /v2/resource_subscriptions) still work.",
        "- **Lemon Squeezy**: POST /v1/products returns 405 (Method Not Allowed).",
        "  Only GET/HEAD supported. Products must be created via dashboard.",
        "  POST /v1/checkouts IS supported (for creating checkout sessions from existing products).",
        "",
    ])

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"\n  Generated: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  Multi-Channel Product Setup")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    gumroad_token = os.environ.get("GUMROAD_ACCESS_TOKEN", "")
    ls_key = os.environ.get("LEMON_SQUEEZY_API_KEY", "")

    if not gumroad_token:
        print("\n  WARNING: GUMROAD_ACCESS_TOKEN not set")
    if not ls_key:
        print("\n  WARNING: LEMON_SQUEEZY_API_KEY not set")

    fetch_only = "--fetch" in sys.argv

    # --- GUMROAD ---
    print("\n" + "=" * 60)
    print("  GUMROAD")
    print("=" * 60)

    gumroad_products = []
    if gumroad_token:
        # Verify connection
        status, resp = http_get(
            f"https://api.gumroad.com/v2/user?access_token={gumroad_token}"
        )
        if status == 200 and resp.get("success"):
            user = resp.get("user", {})
            print(f"\n  Connected as: {user.get('name', 'N/A')}")
            print(f"  Store URL: {user.get('url', 'N/A')}")
            print(f"  Email: {user.get('email', 'N/A')}")
        else:
            print(f"\n  Connection failed: HTTP {status}")

        gumroad_products = fetch_gumroad_products(gumroad_token)

        if not gumroad_products and not fetch_only:
            print("\n  NOTE: Gumroad API does not support product creation (404).")
            print("  Products must be created manually at: https://gumroad.com/products/new")
    else:
        print("\n  Skipped (no access token)")

    # --- LEMON SQUEEZY ---
    print("\n" + "=" * 60)
    print("  LEMON SQUEEZY")
    print("=" * 60)

    ls_store = None
    ls_products = []
    if ls_key:
        ls_store = fetch_lemon_squeezy_store(ls_key)
        ls_products = fetch_lemon_squeezy_products(ls_key)

        if not ls_products and not fetch_only:
            print("\n  NOTE: Lemon Squeezy API does not support product creation (405).")
            print("  Products must be created at: https://app.lemonsqueezy.com")
    else:
        print("\n  Skipped (no API key)")

    # --- GENERATE LINKS FILE ---
    print("\n" + "=" * 60)
    print("  GENERATING LINKS FILE")
    print("=" * 60)

    output = generate_links_file(gumroad_products, ls_store, ls_products)

    # --- SUMMARY ---
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"\n  Stripe:         14 products (LIVE)")
    print(f"  Gumroad:        {len(gumroad_products)} products found")
    print(f"  Lemon Squeezy:  {len(ls_products)} products found")
    print(f"\n  Links file: {output}")

    if not gumroad_products or not ls_products:
        print("\n  NEXT STEPS:")
        if not gumroad_products:
            print("  1. Create products manually on Gumroad:")
            print("     https://gumroad.com/products/new")
        if not ls_products:
            print("  2. Create products manually on Lemon Squeezy:")
            print("     https://app.lemonsqueezy.com")
        print("  3. Then re-run: python3 monetisation/multi-channel-setup.py --fetch")

    print()


if __name__ == "__main__":
    main()
