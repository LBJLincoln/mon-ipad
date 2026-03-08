#!/usr/bin/env python3
"""
Create all 14 Nomos RAG products on Lemon Squeezy marketplace.

The Lemon Squeezy public API does NOT support product creation (read-only).
This script automates the dashboard (app.lemonsqueezy.com) by:
1. Logging in via auth.lemonsqueezy.com (email + password)
2. Creating products via Inertia.js POST requests (same as browser)

Usage:
  1. Add LEMON_SQUEEZY_PASSWORD to .env.local
  2. source .env.local && python3 monetisation/lemon-squeezy-create-products.py

Alternative (if password not set):
  - Prints instructions + copy-paste data for manual dashboard creation
  - After manual creation, re-run to verify + generate checkout URLs
"""

import os, sys, json, re, time, html
import requests

# ─── Load environment ──────────────────────────────────────────────
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.local")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

API_KEY = os.environ.get("LEMON_SQUEEZY_API_KEY", "")
PASSWORD = os.environ.get("LEMON_SQUEEZY_PASSWORD", "")
EMAIL = "lahargnedebartoli@gmail.com"
STORE_ID = "310020"

AUTH_BASE = "https://auth.lemonsqueezy.com"
APP_BASE = "https://app.lemonsqueezy.com"
API_BASE = "https://api.lemonsqueezy.com/v1"

# ─── 14 Products ───────────────────────────────────────────────────
PRODUCTS = [
    {
        "name": "MEGA BUNDLE — Complete RAG Engineering Stack",
        "slug": "mega-bundle-complete-rag-engineering-stack",
        "price": 49700,
        "description": "Everything you need to build a production RAG system in one weekend. Includes all 13 products: Architecture Blueprint, 10 n8n Workflows, Enterprise Website Template, Agentic Commerce Playbook, Engineering Handbook, Eval Framework, Ingestion Toolkit, Dashboard, Benchmark Datasets, Embeddings Service, Debug Playbook, Claude Code Skills, and Agent Context Kit. Over $1,400 in value.",
    },
    {
        "name": "Multi-RAG Architecture Blueprint",
        "slug": "multi-rag-architecture-blueprint",
        "price": 19700,
        "description": "Complete architecture for a 4-pipeline RAG system handling 61K+ questions at 87-95% accuracy. Covers infrastructure setup on 100% free tiers, n8n workflow configuration, LiteLLM proxy setup, evaluation methodology, and phase-based scaling strategy. Built from 80+ production sessions.",
    },
    {
        "name": "n8n RAG Workflow Collection — 10 Production Workflows",
        "slug": "n8n-rag-workflow-collection",
        "price": 19700,
        "description": "10 battle-tested n8n workflow JSON files ready for import: Standard RAG, Graph RAG, Quantitative RAG, Orchestrator, Enrichment, Ingestion, PME Gateway, Project Chatbot, and more. Zero setup required — works with Groq, OpenRouter, and LiteLLM out of the box.",
    },
    {
        "name": "Enterprise RAG Website Template — Next.js 14",
        "slug": "enterprise-rag-website-template",
        "price": 19700,
        "description": "Production-ready Next.js 14 + Tailwind + shadcn/ui website with 4 sector-specific AI chatbots (Finance, Legal, Construction, Manufacturing). Features MacBook frame animations, live SSE streaming dashboard, and pre-configured SEO. Deploy to Vercel in 5 minutes.",
    },
    {
        "name": "Agentic Commerce Playbook",
        "slug": "agentic-commerce-playbook",
        "price": 19700,
        "description": "How to sell AI products TO AI agents. Covers ACP protocol implementation, 10-platform distribution strategy, MCP server integration, and revenue automation. Based on McKinsey's $1T agentic commerce prediction by 2030. Get the first-mover advantage.",
    },
    {
        "name": "RAG Engineering Handbook — 2,500+ Lines",
        "slug": "rag-engineering-handbook",
        "price": 14700,
        "description": "The encyclopedia of RAG engineering: 79+ production fixes with root cause analysis, complete infrastructure reference for Pinecone, Neo4j, Supabase, and n8n, project roadmap with SOTA research review, and 1,000+ document types cataloged by sector.",
    },
    {
        "name": "RAG Evaluation Framework — Phase-Gated Testing",
        "slug": "rag-evaluation-framework",
        "price": 12700,
        "description": "Complete Python evaluation suite with smoke tests, parallel batch evaluation, phase gates (200 to 1K to 10K to 61K questions), regression detection, and live metrics dashboard. 11 production scripts battle-tested across 80+ sessions.",
    },
    {
        "name": "RAG Ingestion Toolkit — Scripts & Services",
        "slug": "rag-ingestion-toolkit",
        "price": 9700,
        "description": "20+ production scripts for document ingestion: multi-format parsing (PDF, DOCX, JSONL), Pinecone/Neo4j/Supabase loaders, BM25 service, reranker service, quality validation, and contextual enrichment. Proven on 34K+ documents.",
    },
    {
        "name": "RAG Pipeline Dashboard Template",
        "slug": "rag-pipeline-dashboard-template",
        "price": 9700,
        "description": "Real-time HTML/JS dashboard for RAG pipeline monitoring. Features Chart.js visualizations, trading board with BEST/WORST/MIDDLE ranking, auto-refresh, Vercel serverless API, and offline fallback mode. Deploy in 2 minutes on GitHub Pages or Vercel.",
    },
    {
        "name": "SOTA Benchmark Dataset Toolkit",
        "slug": "sota-benchmark-dataset-toolkit",
        "price": 6700,
        "description": "18 curated SOTA benchmark datasets totaling 61,661 questions with download scripts, phase generators, and evaluation harness. Includes SQuAD v2, MS MARCO, TriviaQA, HotpotQA, FinQA, and more. Ready for RAG evaluation out of the box.",
    },
    {
        "name": "Self-Hosted Embeddings Service",
        "slug": "self-hosted-embeddings-service",
        "price": 6700,
        "description": "Deploy your own Jina-compatible embeddings API on HuggingFace Spaces for free. Features lazy model loading, health monitoring, and TEI-compatible endpoints. Stop paying per-token for embeddings. Includes complete deployment guide.",
    },
    {
        "name": "RAG Debug Playbook — 79+ Production Fixes",
        "slug": "rag-debug-playbook",
        "price": 4700,
        "description": "79+ documented production fixes with full root cause analysis, diagnostic flowcharts, and prevention strategies. Covers n8n, Pinecone, Neo4j, Supabase, LiteLLM, embeddings, and more. Stop guessing — fix RAG issues in minutes instead of hours.",
    },
    {
        "name": "Claude Code Skill Pack — 17 Custom Commands",
        "slug": "claude-code-skill-pack",
        "price": 4700,
        "description": "17 production-ready Claude Code skills for AI-powered development: session management, evaluation runners, self-healing pipelines, cross-repo sync, regression detection, metrics dashboards, website audit, and more. Drop into your .claude/commands/ folder and go.",
    },
    {
        "name": "AI Agent Context Kit",
        "slug": "ai-agent-context-kit",
        "price": 2700,
        "description": "Production-tested context management patterns for AI agents: CLAUDE.md templates, state file architecture, multi-repo coordination, session persistence, and memory management. The foundation for reliable AI agent workflows.",
    },
]


# ─── Public API helpers ────────────────────────────────────────────
def api_get(path):
    """GET from Lemon Squeezy public API."""
    r = requests.get(f"{API_BASE}{path}", headers={
        'Authorization': f'Bearer {API_KEY}',
        'Accept': 'application/vnd.api+json',
    })
    return r.json()


def list_existing_products():
    """List products already in the store."""
    data = api_get(f"/products?filter[store_id]={STORE_ID}&page[size]=50")
    products = data.get('data', [])
    return {p['attributes']['name']: p for p in products}


def list_variants(product_id):
    """List variants for a product."""
    data = api_get(f"/variants?filter[product_id]={product_id}")
    return data.get('data', [])


def create_checkout(variant_id, custom_price=None, product_name=None, product_desc=None):
    """Create a checkout URL via public API."""
    attrs = {
        "checkout_options": {
            "embed": False,
            "media": True,
            "discount": True,
        },
    }
    if custom_price:
        attrs["custom_price"] = custom_price
    if product_name or product_desc:
        attrs["product_options"] = {}
        if product_name:
            attrs["product_options"]["name"] = product_name
        if product_desc:
            attrs["product_options"]["description"] = product_desc

    payload = {
        "data": {
            "type": "checkouts",
            "attributes": attrs,
            "relationships": {
                "store": {"data": {"type": "stores", "id": STORE_ID}},
                "variant": {"data": {"type": "variants", "id": str(variant_id)}},
            },
        }
    }

    r = requests.post(f"{API_BASE}/checkouts", json=payload, headers={
        'Authorization': f'Bearer {API_KEY}',
        'Accept': 'application/vnd.api+json',
        'Content-Type': 'application/vnd.api+json',
    })
    if r.status_code in (200, 201):
        return r.json()['data']['attributes']['url']
    else:
        print(f"    Checkout error: {r.status_code} {r.text[:200]}")
        return None


def create_discount(name, code, percentage, max_redemptions=None):
    """Create a discount code via public API."""
    attrs = {
        "name": name,
        "code": code,
        "amount": percentage,
        "amount_type": "percent",
        "is_limited_to_products": False,
        "is_limited_redemptions": max_redemptions is not None,
    }
    if max_redemptions:
        attrs["max_redemptions"] = max_redemptions

    payload = {
        "data": {
            "type": "discounts",
            "attributes": attrs,
            "relationships": {
                "store": {"data": {"type": "stores", "id": STORE_ID}},
            },
        }
    }

    r = requests.post(f"{API_BASE}/discounts", json=payload, headers={
        'Authorization': f'Bearer {API_KEY}',
        'Accept': 'application/vnd.api+json',
        'Content-Type': 'application/vnd.api+json',
    })
    if r.status_code in (200, 201):
        d = r.json()['data']
        return d['id'], d['attributes'].get('code')
    else:
        print(f"    Discount error: {r.status_code} {r.text[:200]}")
        return None, None


# ─── Dashboard automation ──────────────────────────────────────────
class LemonDashboard:
    """Automate Lemon Squeezy dashboard via requests Session."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/131.0.0.0 Safari/537.36',
        })
        self.inertia_version = None

    def login(self, email, password):
        """Log in to the Lemon Squeezy dashboard."""
        # 1. Get login page + CSRF token
        r = self.session.get(f"{AUTH_BASE}/login")
        if r.status_code != 200:
            print(f"  Login page error: {r.status_code}")
            return False

        csrf = re.search(r'name="_token"\s+value="([^"]+)"', r.text)
        if not csrf:
            print("  No CSRF token found")
            return False

        token = csrf.group(1)

        # 2. Submit login form
        r = self.session.post(f"{AUTH_BASE}/login", data={
            '_token': token,
            'email': email,
            'password': password,
            'remember': 'on',
        }, headers={
            'Referer': f'{AUTH_BASE}/login',
            'Origin': AUTH_BASE,
        }, allow_redirects=True)

        # 3. Check if we landed on the dashboard
        final_url = r.url
        if 'dashboard' in final_url or 'app.lemonsqueezy' in final_url:
            # Extract Inertia version from page
            page_match = re.search(r'data-page="([^"]*)"', r.text)
            if page_match:
                try:
                    page_data = json.loads(html.unescape(page_match.group(1)))
                    self.inertia_version = page_data.get('version', '')
                except (json.JSONDecodeError, ValueError):
                    pass
            return True

        # Check for 2FA
        if 'two-factor' in r.text.lower() or 'verification' in r.text.lower():
            print("  Two-factor authentication required — cannot automate")
            return False

        # Check for login errors
        errors = re.findall(r'These credentials do not match|invalid|error', r.text, re.I)
        if errors:
            print(f"  Login failed: credentials rejected")
        else:
            print(f"  Login status unclear. Final URL: {final_url}")

        return False

    def _get_xsrf(self):
        """Get XSRF token from cookies."""
        for cookie in self.session.cookies:
            if cookie.name == 'XSRF-TOKEN':
                return requests.utils.unquote(cookie.value)
        return None

    def _inertia_headers(self):
        """Build Inertia.js request headers."""
        h = {
            'Accept': 'text/html, application/xhtml+xml',
            'X-Inertia': 'true',
            'X-Requested-With': 'XMLHttpRequest',
        }
        xsrf = self._get_xsrf()
        if xsrf:
            h['X-XSRF-TOKEN'] = xsrf
        if self.inertia_version:
            h['X-Inertia-Version'] = self.inertia_version
        return h

    def _refresh_inertia_version(self):
        """Fetch a page to get the current Inertia version."""
        r = self.session.get(f"{APP_BASE}/products")
        page_match = re.search(r'data-page="([^"]*)"', r.text)
        if page_match:
            try:
                page_data = json.loads(html.unescape(page_match.group(1)))
                self.inertia_version = page_data.get('version', '')
            except (json.JSONDecodeError, ValueError):
                pass

    def create_product(self, name, slug, price_cents, description):
        """Create a product through the dashboard's Inertia.js endpoint."""
        xsrf = self._get_xsrf()
        if not xsrf:
            print("    No XSRF token")
            return None

        # First, visit the product creation page to get a fresh token
        r = self.session.get(f"{APP_BASE}/products/new", headers=self._inertia_headers())

        if r.status_code == 409:
            # Inertia version mismatch — refresh
            self._refresh_inertia_version()
            r = self.session.get(f"{APP_BASE}/products/new", headers=self._inertia_headers())

        # Refresh XSRF after page load
        xsrf = self._get_xsrf()

        # Try JSON POST (Inertia.js style)
        payload = {
            'name': name,
            'slug': slug,
            'description': f'<p>{description}</p>',
            'price': price_cents,
            'status': 'published',
            'pay_what_you_want': False,
        }

        headers = self._inertia_headers()
        headers['Content-Type'] = 'application/json'
        headers['Referer'] = f'{APP_BASE}/products/new'
        headers['Origin'] = APP_BASE

        r = self.session.post(f"{APP_BASE}/products", json=payload, headers=headers)

        if r.status_code in (200, 201, 302, 303):
            # Try to extract product ID
            product_id = None
            try:
                data = r.json()
                # Inertia response
                props = data.get('props', {})
                product_id = props.get('product', {}).get('id')
                if not product_id and 'flash' in props:
                    # Success flash message — product was created
                    product_id = 'created'
            except (json.JSONDecodeError, ValueError):
                # Check redirect URL
                if r.headers.get('Location'):
                    m = re.search(r'/products/(\d+)', r.headers['Location'])
                    if m:
                        product_id = m.group(1)

            return product_id or 'created'

        elif r.status_code == 422:
            # Validation error — try to parse
            try:
                errors = r.json()
                msg = json.dumps(errors.get('errors', errors), indent=2)[:300]
            except (json.JSONDecodeError, ValueError):
                msg = r.text[:300]
            print(f"    Validation error: {msg}")
            return None

        elif r.status_code == 419:
            print("    CSRF expired")
            return None

        else:
            print(f"    HTTP {r.status_code}: {r.text[:200]}")
            return None


# ─── Main ──────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("  LEMON SQUEEZY — Create 14 Products")
    print(f"  Store: Nomos 42 (ID: {STORE_ID}) | Email: {EMAIL}")
    print(f"  Total catalog: ${sum(p['price'] for p in PRODUCTS)/100:,.0f}")
    print("=" * 65)

    if not API_KEY:
        print("\nERROR: LEMON_SQUEEZY_API_KEY not set")
        print("Run: source .env.local")
        sys.exit(1)

    # ─── Check existing products ───────────────────────────────────
    print("\n[1/4] Checking existing products...")
    existing = list_existing_products()
    print(f"  Found {len(existing)} products in store")
    for name, p in existing.items():
        attrs = p['attributes']
        print(f"    - {name} (${attrs.get('price', 0)/100:.0f}) [{attrs.get('status')}]")
        buy_url = attrs.get('buy_now_url', '')
        if buy_url:
            print(f"      {buy_url}")

    to_create = [p for p in PRODUCTS if p['name'] not in existing]
    if not to_create:
        print("\n  All 14 products already exist!")
    else:
        print(f"\n  {len(to_create)} products to create")

    # ─── Dashboard product creation ────────────────────────────────
    if to_create:
        if PASSWORD:
            print(f"\n[2/4] Dashboard automation (password provided)...")
            dash = LemonDashboard()

            print("  Logging in...")
            if dash.login(EMAIL, PASSWORD):
                print("  Login successful!")

                created = 0
                failed = 0
                for i, product in enumerate(to_create, 1):
                    price_str = f"${product['price']/100:.0f}"
                    print(f"\n  [{i}/{len(to_create)}] {product['name']} ({price_str})")

                    result = dash.create_product(
                        name=product['name'],
                        slug=product['slug'],
                        price_cents=product['price'],
                        description=product['description'],
                    )

                    if result:
                        print(f"    OK (ID: {result})")
                        created += 1
                    else:
                        print(f"    FAILED")
                        failed += 1
                        if failed >= 3:
                            print("\n  3+ failures — stopping dashboard automation")
                            break

                    time.sleep(2)

                print(f"\n  Dashboard results: {created} created, {failed} failed")

                # Re-check via API
                if created > 0:
                    print("  Verifying via API...")
                    existing = list_existing_products()
                    print(f"  Now {len(existing)} products in store")
                    to_create = [p for p in PRODUCTS if p['name'] not in existing]

            else:
                print("  Login failed!")
        else:
            print(f"\n[2/4] No LEMON_SQUEEZY_PASSWORD set — skipping dashboard automation")

    # ─── Generate checkout URLs for existing products ──────────────
    if existing:
        print(f"\n[3/4] Generating checkout URLs...")
        checkout_urls = {}

        for name, p in existing.items():
            pid = p['id']
            variants = list_variants(pid)
            if variants:
                vid = variants[0]['id']
                url = create_checkout(vid)
                if url:
                    checkout_urls[name] = url
                    print(f"  {name}: {url}")
                time.sleep(0.5)

        if checkout_urls:
            # Save to file
            output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lemon-squeezy-links.json")
            with open(output_path, 'w') as f:
                json.dump(checkout_urls, f, indent=2)
            print(f"\n  Saved {len(checkout_urls)} checkout URLs to {output_path}")
    else:
        print(f"\n[3/4] No products exist yet — skipping checkout URL generation")

    # ─── Create discount codes ─────────────────────────────────────
    print(f"\n[4/4] Creating discount codes...")
    existing_discounts = api_get(f"/discounts?filter[store_id]={STORE_ID}")
    existing_codes = {d['attributes']['code'] for d in existing_discounts.get('data', [])}

    discounts = [
        ("Launch 20% Off", "LAUNCH20", 20, 100),
        ("Bundle 30% Off", "BUNDLE30", 30, 50),
        ("Reddit 25% Off", "REDDIT25", 25, None),
        ("Hacker News 20% Off", "HN20", 20, None),
        ("Dev.to 15% Off", "DEVTO15", 15, None),
        ("Early Bird 40% Off", "EARLYBIRD40", 40, 10),
    ]

    for name, code, pct, limit in discounts:
        if code in existing_codes:
            print(f"  SKIP (exists): {code}")
            continue
        did, dcode = create_discount(name, code, pct, limit)
        if did:
            print(f"  OK: {code} ({pct}% off, limit={limit or 'unlimited'})")
        time.sleep(0.5)

    # ─── Summary ───────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  SUMMARY")
    print("=" * 65)

    final_products = list_existing_products()
    print(f"\n  Products in store: {len(final_products)}/14")

    if len(final_products) < 14:
        remaining = [p for p in PRODUCTS if p['name'] not in final_products]
        print(f"  Still need to create {len(remaining)} products:")
        for p in remaining:
            print(f"    - {p['name']} (${p['price']/100:.0f})")
        print(f"\n  To create them:")
        print(f"    Option A: Add LEMON_SQUEEZY_PASSWORD to .env.local, re-run")
        print(f"    Option B: Create manually at https://app.lemonsqueezy.com/products/new")
        print(f"    Guide: monetisation/lemon-squeezy-products-guide.md")

    for name, p in final_products.items():
        attrs = p['attributes']
        buy = attrs.get('buy_now_url', 'N/A')
        print(f"\n  {name}")
        print(f"    Price: ${attrs.get('price', 0)/100:.0f} | Status: {attrs.get('status')}")
        print(f"    Buy: {buy}")

    store_url = f"https://nomos42.lemonsqueezy.com"
    print(f"\n  Store URL: {store_url}")
    print("=" * 65)


if __name__ == '__main__':
    main()
