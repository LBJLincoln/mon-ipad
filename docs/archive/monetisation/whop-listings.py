#!/usr/bin/env python3
"""Whop.com marketplace listings — create and manage products via API.

Creates all 14 Nomos AI products on Whop with one-time pricing plans.
Uses the Whop REST API v1 (https://api.whop.com/api/v1/).

Usage:
    export $(grep -v '^#' .env.local | xargs)
    python3 monetisation/whop-listings.py --list            # List existing products
    python3 monetisation/whop-listings.py --list-plans       # List existing plans
    python3 monetisation/whop-listings.py --create           # Create all products + plans
    python3 monetisation/whop-listings.py --create --dry-run # Preview without creating
    python3 monetisation/whop-listings.py --companies        # List companies (find company_id)

Env vars:
    WHOP_API_KEY     - Bearer token (from https://dash.whop.com/settings/developer)
    WHOP_COMPANY_ID  - Company ID (biz_xxxxxxxxxxxx). Use --companies to find it.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://api.whop.com/api/v1"

# Product catalog — 14 products matching Stripe catalog
# Whop product titles: max 40 chars
PRODUCTS = [
    {
        "id": "mega_bundle",
        "title": "MEGA BUNDLE - All 13 RAG Products",
        "price": 497.00,
        "stripe_url": "https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d",
        "route": "rag-mega-bundle",
        "headline": "Everything. One payment. Lifetime access.",
        "description": (
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
        "title": "RAG Architecture Blueprint",
        "price": 197.00,
        "stripe_url": "https://buy.stripe.com/aFa14g4vob1x3f5bcp5J602",
        "route": "architecture-blueprint",
        "headline": "Multi-pipeline RAG system design.",
        "description": (
            "Complete architecture for a production multi-pipeline RAG system. "
            "Standard, Graph, and Quantitative pipelines. "
            "n8n orchestration, Pinecone + Neo4j + Supabase integration. "
            "Battle-tested across 61,000+ questions."
        ),
    },
    {
        "id": "n8n_workflows",
        "title": "n8n RAG Workflow Collection",
        "price": 197.00,
        "stripe_url": "https://buy.stripe.com/bJe00c9PI8Tp2b1a8l5J603",
        "route": "n8n-workflows",
        "headline": "10 production n8n RAG workflows.",
        "description": (
            "7 production n8n workflow files covering Standard RAG, "
            "Graph RAG, Quantitative RAG, website pipelines, and the orchestrator. "
            "Ready to import and customize."
        ),
    },
    {
        "id": "enterprise_site",
        "title": "Enterprise Site Template - Next.js",
        "price": 197.00,
        "stripe_url": "https://buy.stripe.com/14A6oAaTM4D94j93JX5J604",
        "route": "enterprise-site-template",
        "headline": "Next.js 15 site with 4 AI chatbots.",
        "description": (
            "Full Next.js 15 website template with 4 sector verticals "
            "(Finance, Legal, Construction, Industry), embedded chatbots, "
            "responsive design, and deployment config."
        ),
    },
    {
        "id": "agentic_commerce",
        "title": "Agentic Commerce Playbook",
        "price": 197.00,
        "stripe_url": "https://buy.stripe.com/aFa3co9PI5Hd2b11BP5J607",
        "route": "agentic-commerce",
        "headline": "Sell to AI agents. ACP protocol.",
        "description": (
            "The definitive guide to agentic commerce. "
            "How to make your products discoverable and purchasable by AI agents. "
            "ACP protocol implementation, structured data, GEO strategy."
        ),
    },
    {
        "id": "rag_handbook",
        "title": "RAG Engineering Handbook",
        "price": 147.00,
        "stripe_url": "https://buy.stripe.com/eVq14g6Dwd9F6rh54h5J606",
        "route": "rag-handbook",
        "headline": "80+ sessions distilled into one book.",
        "description": (
            "Comprehensive handbook distilled from 80+ engineering sessions. "
            "Covers retrieval strategies, prompt engineering, embedding optimization, "
            "reranking, evaluation methodology, and production deployment patterns."
        ),
    },
    {
        "id": "eval_framework",
        "title": "RAG Eval Framework - 61K Questions",
        "price": 127.00,
        "stripe_url": "https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605",
        "route": "eval-framework",
        "headline": "Evaluate RAG with 61K SOTA questions.",
        "description": (
            "Complete evaluation framework: 61,661 questions from 18 SOTA benchmarks. "
            "Parallel runner, golden evals, regression detection."
        ),
    },
    {
        "id": "ingestion_toolkit",
        "title": "Ingestion Toolkit - V4 Pipeline",
        "price": 97.00,
        "stripe_url": "https://buy.stripe.com/dRm7sEfa27PlcPFgwJ5J608",
        "route": "ingestion-toolkit",
        "headline": "Ingest 34K+ docs across 4 sectors.",
        "description": (
            "Data ingestion pipeline: 34,000+ records across 4 sectors. "
            "Docling integration, sector-aware chunking, multi-database upsert."
        ),
    },
    {
        "id": "dashboard_template",
        "title": "Dashboard Template - RAG Metrics",
        "price": 97.00,
        "stripe_url": "https://buy.stripe.com/14AcMYbXQ7PldTJ5S55J60a",
        "route": "dashboard-template",
        "headline": "Real-time RAG pipeline dashboard.",
        "description": (
            "HTML/JS dashboard showing live pipeline metrics, accuracy trends, "
            "infrastructure status, and phase progress. Auto-generates from status.json."
        ),
    },
    {
        "id": "benchmark_dataset",
        "title": "Benchmark Dataset - 61K Questions",
        "price": 67.00,
        "stripe_url": "https://buy.stripe.com/cNi5kwaTMfhN5nd3JX5J60b",
        "route": "benchmark-dataset",
        "headline": "18 SOTA benchmarks, 61K questions.",
        "description": (
            "Curated dataset of 61,661 questions from 18 SOTA benchmarks. "
            "Pre-categorized by pipeline type (Standard, Graph, Quant)."
        ),
    },
    {
        "id": "embeddings_service",
        "title": "Self-Hosted Embeddings Service",
        "price": 67.00,
        "stripe_url": "https://buy.stripe.com/aFa00ce5Y0mT9Dtcgt5J60c",
        "route": "embeddings-service",
        "headline": "Jina-compatible, free-tier hosting.",
        "description": (
            "Self-hosted embedding service on HF Spaces. Jina v3 1024-dim, "
            "Gradio API, health monitoring. Drop-in Jina Cloud replacement."
        ),
    },
    {
        "id": "debug_playbook",
        "title": "RAG Debug Playbook - 75+ Fixes",
        "price": 47.00,
        "stripe_url": "https://buy.stripe.com/00w7sEd1U2v14j92FT5J600",
        "route": "debug-playbook",
        "headline": "75+ real production fixes cataloged.",
        "description": (
            "Library of 75+ real fixes. Diagnostic flowcharts, n8n gotchas, "
            "Pinecone/Neo4j/Supabase patterns, embedding pitfalls, LLM prompt fixes."
        ),
    },
    {
        "id": "claude_skills",
        "title": "Claude Code Skills - 17 Commands",
        "price": 47.00,
        "stripe_url": "https://buy.stripe.com/7sY8wIge64D93f53JX5J609",
        "route": "claude-skills",
        "headline": "17 production Claude Code skills.",
        "description": (
            "17 production slash commands for Claude Code: session-start, eval, "
            "sync-directives, self-heal, progress-10pct, regression-check, and more."
        ),
    },
    {
        "id": "agent_context_kit",
        "title": "Agent Context Kit - CLAUDE.md",
        "price": 27.00,
        "stripe_url": "https://buy.stripe.com/7sY9AMbXQ4D94j95S55J601",
        "route": "agent-context-kit",
        "headline": "AI agent context template system.",
        "description": (
            "Template system for AI agent context: CLAUDE.md, PROJECT-STATE.md, "
            "DEBUG-PLAYBOOK.md, INFRASTRUCTURE.md. The exact system powering this project."
        ),
    },
]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get_api_key():
    """Get the raw API key from environment."""
    api_key = os.environ.get("WHOP_API_KEY", "")
    if not api_key:
        print("ERROR: WHOP_API_KEY not set in environment.")
        print("  Get your key at: https://dash.whop.com/settings/developer")
        sys.exit(1)
    return api_key


def _get_access_token(company_id):
    """Generate a short-lived JWT access token scoped to a company.

    Company API keys (apik_*) cannot directly call v1 endpoints for a specific
    company.  They must first POST /access_tokens to obtain a JWT that is
    scoped to the target company.  The JWT inherits all permissions from the
    parent key.
    """
    api_key = _get_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {"company_id": company_id}
    status, resp = http_request("POST", f"{BASE_URL}/access_tokens", data=payload, headers=headers)
    if status not in (200, 201):
        print(f"ERROR: Failed to create access token (HTTP {status})")
        print(f"  {json.dumps(resp, indent=2)[:500]}")
        sys.exit(1)
    token = resp.get("token", "")
    if not token:
        print("ERROR: Empty access token returned.")
        sys.exit(1)
    return token


# Cache the token so we don't create one per API call
_cached_token = None


def _get_headers():
    """Build auth headers using a company-scoped JWT access token."""
    global _cached_token
    if _cached_token is None:
        company_id = _get_company_id()
        _cached_token = _get_access_token(company_id)
    return {
        "Authorization": f"Bearer {_cached_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _get_company_id():
    """Get company ID from env."""
    cid = os.environ.get("WHOP_COMPANY_ID", "")
    if not cid:
        print("ERROR: WHOP_COMPANY_ID not set in environment.")
        print("  Run:  python3 monetisation/whop-listings.py --companies")
        print("  Then: export WHOP_COMPANY_ID=biz_xxxxxxxxxxxx")
        sys.exit(1)
    return cid


def http_request(method, url, data=None, headers=None):
    """Make an HTTP request. Returns (status_code, parsed_json)."""
    if data is not None:
        body = json.dumps(data).encode("utf-8")
    else:
        body = None

    req = urllib.request.Request(url, data=body, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:1000]}
    except Exception as e:
        return 0, {"error": str(e)}


# ---------------------------------------------------------------------------
# API operations
# ---------------------------------------------------------------------------

def list_companies():
    """List companies accessible with the current API key.

    Uses the raw API key (not a company-scoped JWT) since we don't know the
    company_id yet.  Falls back to looking up a known route slug if the
    /companies endpoint is unavailable.
    """
    api_key = _get_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    print("\n" + "=" * 60)
    print("  WHOP — List Companies")
    print("=" * 60)

    status, resp = http_request("GET", f"{BASE_URL}/companies", headers=headers)
    if status == 200:
        companies = resp.get("data", [])
        if not companies:
            print("\n  No companies found via /companies endpoint.")
        else:
            print(f"\n  Found {len(companies)} company(ies):\n")
            for c in companies:
                print(f"  ID:      {c.get('id', 'N/A')}")
                print(f"  Title:   {c.get('title', 'N/A')}")
                print(f"  Route:   {c.get('route', 'N/A')}")
                print(f"  URL:     https://whop.com/{c.get('route', '')}")
                print(f"  Members: {c.get('member_count', 0)}")
                owner = c.get("owner_user", {})
                print(f"  Owner:   {owner.get('name', 'N/A')} (@{owner.get('username', 'N/A')})")
                print()
            print("  To use a company, add to .env.local:")
            print(f"  WHOP_COMPANY_ID={companies[0].get('id', 'biz_xxxxxxxxxxxx')}")
            print()
            return

    # Fallback: /companies endpoint may fail with company-scoped API keys.
    # Try looking up the company by route slug instead.
    print(f"\n  /companies returned HTTP {status} — trying route-slug lookup...")
    for slug in ["nomosai", "nomos42", "nomos-ai"]:
        s2, r2 = http_request("GET", f"{BASE_URL}/companies/{slug}", headers=headers)
        if s2 == 200 and r2.get("id"):
            print(f"\n  Found company via route '{slug}':\n")
            print(f"  ID:      {r2.get('id')}")
            print(f"  Title:   {r2.get('title')}")
            print(f"  Route:   {r2.get('route')}")
            print(f"  URL:     https://whop.com/{r2.get('route', '')}")
            print(f"  Members: {r2.get('member_count', 0)}")
            owner = r2.get("owner_user", {})
            print(f"  Owner:   {owner.get('name', 'N/A')} (@{owner.get('username', 'N/A')})")
            print()
            print("  Add to .env.local:")
            print(f"  export WHOP_COMPANY_ID=\"{r2.get('id')}\"")
            print()
            return

    print("\n  Could not find any company. Create one at https://whop.com/sell")
    print()


def list_products():
    """List existing products on Whop."""
    headers = _get_headers()
    company_id = _get_company_id()

    print("\n" + "=" * 60)
    print("  WHOP — List Products")
    print("=" * 60)

    url = f"{BASE_URL}/products?company_id={company_id}&first=100"
    status, resp = http_request("GET", url, headers=headers)

    if status != 200:
        print(f"\n  ERROR: HTTP {status}")
        print(f"  {json.dumps(resp, indent=2)[:500]}")
        return []

    products = resp.get("data", [])
    print(f"\n  Found {len(products)} product(s):\n")

    if not products:
        print("  No products yet. Run with --create to create them.")
        return []

    print(f"  {'#':<3} {'Title':<40} {'Visibility':<12} {'Members':<8} {'ID'}")
    print(f"  {'-'*3} {'-'*40} {'-'*12} {'-'*8} {'-'*20}")

    for i, p in enumerate(products, 1):
        title = (p.get("title", "N/A"))[:40]
        vis = p.get("visibility", "N/A")
        members = p.get("member_count", 0)
        pid = p.get("id", "N/A")
        print(f"  {i:<3} {title:<40} {vis:<12} {members:<8} {pid}")

    print()
    return products


def list_plans():
    """List existing plans on Whop."""
    headers = _get_headers()
    company_id = _get_company_id()

    print("\n" + "=" * 60)
    print("  WHOP — List Plans")
    print("=" * 60)

    url = f"{BASE_URL}/plans?company_id={company_id}&first=100"
    status, resp = http_request("GET", url, headers=headers)

    if status != 200:
        print(f"\n  ERROR: HTTP {status}")
        print(f"  {json.dumps(resp, indent=2)[:500]}")
        return []

    plans = resp.get("data", [])
    print(f"\n  Found {len(plans)} plan(s):\n")

    if not plans:
        print("  No plans yet. Plans are created alongside products with --create.")
        return []

    print(f"  {'#':<3} {'Plan ID':<22} {'Product ID':<22} {'Type':<10} {'Price':<10} {'Visibility'}")
    print(f"  {'-'*3} {'-'*22} {'-'*22} {'-'*10} {'-'*10} {'-'*12}")

    for i, p in enumerate(plans, 1):
        plan_id = p.get("id", "N/A")
        prod_id = p.get("product_id", p.get("product", {}).get("id", "N/A") if isinstance(p.get("product"), dict) else "N/A")
        plan_type = p.get("plan_type", "N/A")
        price = p.get("initial_price", p.get("renewal_price", "N/A"))
        vis = p.get("visibility", "N/A")
        print(f"  {i:<3} {plan_id:<22} {prod_id:<22} {plan_type:<10} ${price:<9} {vis}")

    print()
    return plans


def create_product(product, company_id, headers, dry_run=False):
    """Create a single product with an attached one-time plan on Whop.

    Uses plan_options in the create-product call to auto-create the plan.
    Returns (product_response, success_bool).
    """
    payload = {
        "company_id": company_id,
        "title": product["title"],
        "description": product["description"],
        "headline": product["headline"],
        "route": product["route"],
        "visibility": "visible",
        "plan_options": {
            "base_currency": "usd",
            "plan_type": "one_time",
            "initial_price": product["price"],
            "release_method": "buy_now",
            "visibility": "visible",
        },
    }

    if dry_run:
        print(f"  [DRY RUN] Would create: {product['title']} (${product['price']:.0f})")
        return None, True

    status, resp = http_request("POST", f"{BASE_URL}/products", data=payload, headers=headers)

    if status in (200, 201):
        prod_id = resp.get("id", "N/A")
        route = resp.get("route", product["route"])
        print(f"  CREATED: {product['title']} (${product['price']:.0f})")
        print(f"           ID: {prod_id}")
        print(f"           URL: https://whop.com/{route}")
        return resp, True
    else:
        error_msg = ""
        if isinstance(resp, dict):
            # Try to extract meaningful error
            error_msg = resp.get("message", resp.get("error", ""))
            if not error_msg and "raw" in resp:
                error_msg = resp["raw"][:200]
            if not error_msg:
                error_msg = json.dumps(resp)[:200]
        print(f"  FAILED:  {product['title']} — HTTP {status}: {error_msg}")
        return resp, False


def create_plan_separately(product_id, product, company_id, headers, dry_run=False):
    """Create a plan for an existing product (fallback if plan_options fails)."""
    payload = {
        "company_id": company_id,
        "product_id": product_id,
        "plan_type": "one_time",
        "currency": "usd",
        "initial_price": product["price"],
        "release_method": "buy_now",
        "visibility": "visible",
        "unlimited_stock": True,
    }

    if dry_run:
        print(f"  [DRY RUN] Would create plan: ${product['price']:.0f} for {product_id}")
        return None, True

    status, resp = http_request("POST", f"{BASE_URL}/plans", data=payload, headers=headers)

    if status in (200, 201):
        plan_id = resp.get("id", "N/A")
        purchase_url = resp.get("purchase_url", "")
        print(f"           Plan: {plan_id} — ${product['price']:.0f}")
        if purchase_url:
            print(f"           Checkout: {purchase_url}")
        return resp, True
    else:
        error_msg = ""
        if isinstance(resp, dict):
            error_msg = resp.get("message", resp.get("error", json.dumps(resp)[:200]))
        print(f"           Plan FAILED — HTTP {status}: {error_msg}")
        return resp, False


def create_all_products(dry_run=False):
    """Create all 14 products on Whop."""
    headers = _get_headers()
    company_id = _get_company_id()

    print("\n" + "=" * 60)
    print(f"  WHOP — Create Products {'(DRY RUN)' if dry_run else ''}")
    print("=" * 60)
    print(f"\n  Company: {company_id}")
    print(f"  Products to create: {len(PRODUCTS)}")
    print()

    # First check existing products to avoid duplicates
    url = f"{BASE_URL}/products?company_id={company_id}&first=100"
    status, resp = http_request("GET", url, headers=headers)
    existing_titles = set()
    existing_routes = set()
    if status == 200:
        for p in resp.get("data", []):
            existing_titles.add(p.get("title", "").lower())
            existing_routes.add(p.get("route", "").lower())
        if existing_titles:
            print(f"  Existing products: {len(existing_titles)}")
            print()

    created = 0
    skipped = 0
    failed = 0
    results = []

    for product in PRODUCTS:
        # Skip if already exists (match by title or route)
        if product["title"].lower() in existing_titles or product["route"].lower() in existing_routes:
            print(f"  SKIP:    {product['title']} (already exists)")
            skipped += 1
            continue

        resp_data, success = create_product(product, company_id, headers, dry_run)

        if success:
            created += 1
            if resp_data:
                results.append({
                    "id": product["id"],
                    "whop_id": resp_data.get("id", ""),
                    "title": product["title"],
                    "price": product["price"],
                    "route": resp_data.get("route", product["route"]),
                    "url": f"https://whop.com/{resp_data.get('route', product['route'])}",
                })
        else:
            failed += 1

        # Rate limiting — be gentle with the API
        if not dry_run:
            time.sleep(1.0)

    # Summary
    print("\n" + "-" * 60)
    print(f"  SUMMARY")
    print(f"  Created: {created}  |  Skipped: {skipped}  |  Failed: {failed}")
    print("-" * 60)

    if results:
        print("\n  Product URLs:")
        for r in results:
            print(f"    {r['title']}: {r['url']}")

    # Save results to JSON for reference
    if results and not dry_run:
        output_path = "/home/termius/mon-ipad/monetisation/whop-products.json"
        with open(output_path, "w") as f:
            json.dump({
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "company_id": company_id,
                "products": results,
            }, f, indent=2)
        print(f"\n  Results saved to: {output_path}")

    print()
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_usage():
    """Print usage information."""
    print("""
Usage: python3 monetisation/whop-listings.py [OPTIONS]

Options:
    --companies       List your Whop companies (to find company_id)
    --list            List existing products
    --list-plans      List existing plans (pricing)
    --create          Create all 14 products with pricing
    --create --dry-run Preview what would be created
    --catalog         Show the product catalog (no API call)
    -h, --help        Show this help

Required env vars:
    WHOP_API_KEY      API key from https://dash.whop.com/settings/developer
    WHOP_COMPANY_ID   Company ID (biz_xxx...). Use --companies to find it.

Example:
    source .env.local
    python3 monetisation/whop-listings.py --companies
    export WHOP_COMPANY_ID=biz_xxxxxxxxxxxx
    python3 monetisation/whop-listings.py --create --dry-run
    python3 monetisation/whop-listings.py --create
""")


def show_catalog():
    """Print the product catalog without making API calls."""
    print("\n" + "=" * 60)
    print("  PRODUCT CATALOG (14 products)")
    print("=" * 60)
    print()
    print(f"  {'#':<3} {'Title':<40} {'Price':<8} {'Route'}")
    print(f"  {'-'*3} {'-'*40} {'-'*8} {'-'*25}")
    for i, p in enumerate(PRODUCTS, 1):
        print(f"  {i:<3} {p['title']:<40} ${p['price']:<7.0f} {p['route']}")
    total = sum(p["price"] for p in PRODUCTS)
    print(f"\n  Total catalog value: ${total:,.0f}")
    print(f"  Bundle price:        ${PRODUCTS[0]['price']:,.0f}")
    print()


def main():
    args = sys.argv[1:]

    if not args or "-h" in args or "--help" in args:
        print_usage()
        return

    if "--catalog" in args:
        show_catalog()
        return

    if "--companies" in args:
        list_companies()
        return

    if "--list-plans" in args:
        list_plans()
        return

    if "--list" in args:
        list_products()
        return

    if "--create" in args:
        dry_run = "--dry-run" in args
        create_all_products(dry_run=dry_run)
        return

    print(f"Unknown option: {' '.join(args)}")
    print_usage()


if __name__ == "__main__":
    main()
