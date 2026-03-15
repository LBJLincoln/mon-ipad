#!/usr/bin/env python3
"""
Lemon Squeezy API Research Script
==================================
Checks Lemon Squeezy's public API capabilities for product management.
Tests which endpoints exist and what operations are available.

Usage:
    python3 monetisation/lemon-squeezy-setup.py
    python3 monetisation/lemon-squeezy-setup.py --api-key YOUR_KEY  # test with real key
"""

import json
import sys
import urllib.request
import urllib.error

BASE_URL = "https://api.lemonsqueezy.com/v1"

# All known Lemon Squeezy API resources (from docs.lemonsqueezy.com/api)
API_RESOURCES = {
    "users": {
        "endpoints": [
            {"method": "GET", "path": "/v1/users/me", "desc": "Get authenticated user"},
        ]
    },
    "stores": {
        "endpoints": [
            {"method": "GET", "path": "/v1/stores", "desc": "List all stores"},
            {"method": "GET", "path": "/v1/stores/{id}", "desc": "Get a store"},
        ]
    },
    "products": {
        "endpoints": [
            {"method": "GET", "path": "/v1/products", "desc": "List all products"},
            {"method": "GET", "path": "/v1/products/{id}", "desc": "Get a product"},
            # POST /v1/products does NOT exist (feature request pending)
        ]
    },
    "variants": {
        "endpoints": [
            {"method": "GET", "path": "/v1/variants", "desc": "List all variants"},
            {"method": "GET", "path": "/v1/variants/{id}", "desc": "Get a variant"},
        ]
    },
    "prices": {
        "endpoints": [
            {"method": "GET", "path": "/v1/prices", "desc": "List all prices"},
            {"method": "GET", "path": "/v1/prices/{id}", "desc": "Get a price"},
        ]
    },
    "checkouts": {
        "endpoints": [
            {"method": "GET", "path": "/v1/checkouts", "desc": "List all checkouts"},
            {"method": "GET", "path": "/v1/checkouts/{id}", "desc": "Get a checkout"},
            {"method": "POST", "path": "/v1/checkouts", "desc": "Create a checkout"},
        ]
    },
    "orders": {
        "endpoints": [
            {"method": "GET", "path": "/v1/orders", "desc": "List all orders"},
            {"method": "GET", "path": "/v1/orders/{id}", "desc": "Get an order"},
        ]
    },
    "order-items": {
        "endpoints": [
            {"method": "GET", "path": "/v1/order-items", "desc": "List all order items"},
            {"method": "GET", "path": "/v1/order-items/{id}", "desc": "Get an order item"},
        ]
    },
    "subscriptions": {
        "endpoints": [
            {"method": "GET", "path": "/v1/subscriptions", "desc": "List all subscriptions"},
            {"method": "GET", "path": "/v1/subscriptions/{id}", "desc": "Get a subscription"},
            {"method": "PATCH", "path": "/v1/subscriptions/{id}", "desc": "Update a subscription"},
            {"method": "DELETE", "path": "/v1/subscriptions/{id}", "desc": "Cancel a subscription"},
        ]
    },
    "subscription-invoices": {
        "endpoints": [
            {"method": "GET", "path": "/v1/subscription-invoices", "desc": "List subscription invoices"},
            {"method": "GET", "path": "/v1/subscription-invoices/{id}", "desc": "Get a subscription invoice"},
        ]
    },
    "discounts": {
        "endpoints": [
            {"method": "GET", "path": "/v1/discounts", "desc": "List all discounts"},
            {"method": "GET", "path": "/v1/discounts/{id}", "desc": "Get a discount"},
            {"method": "POST", "path": "/v1/discounts", "desc": "Create a discount"},
            {"method": "DELETE", "path": "/v1/discounts/{id}", "desc": "Delete a discount"},
        ]
    },
    "discount-redemptions": {
        "endpoints": [
            {"method": "GET", "path": "/v1/discount-redemptions", "desc": "List discount redemptions"},
            {"method": "GET", "path": "/v1/discount-redemptions/{id}", "desc": "Get a discount redemption"},
        ]
    },
    "license-keys": {
        "endpoints": [
            {"method": "GET", "path": "/v1/license-keys", "desc": "List all license keys"},
            {"method": "GET", "path": "/v1/license-keys/{id}", "desc": "Get a license key"},
            {"method": "PATCH", "path": "/v1/license-keys/{id}", "desc": "Update a license key"},
        ]
    },
    "license-key-instances": {
        "endpoints": [
            {"method": "GET", "path": "/v1/license-key-instances", "desc": "List license key instances"},
            {"method": "GET", "path": "/v1/license-key-instances/{id}", "desc": "Get a license key instance"},
        ]
    },
    "files": {
        "endpoints": [
            {"method": "GET", "path": "/v1/files", "desc": "List all files"},
            {"method": "GET", "path": "/v1/files/{id}", "desc": "Get a file"},
        ]
    },
    "webhooks": {
        "endpoints": [
            {"method": "GET", "path": "/v1/webhooks", "desc": "List all webhooks"},
            {"method": "GET", "path": "/v1/webhooks/{id}", "desc": "Get a webhook"},
            {"method": "POST", "path": "/v1/webhooks", "desc": "Create a webhook"},
            {"method": "PATCH", "path": "/v1/webhooks/{id}", "desc": "Update a webhook"},
            {"method": "DELETE", "path": "/v1/webhooks/{id}", "desc": "Delete a webhook"},
        ]
    },
    "customers": {
        "endpoints": [
            {"method": "GET", "path": "/v1/customers", "desc": "List all customers"},
            {"method": "GET", "path": "/v1/customers/{id}", "desc": "Get a customer"},
        ]
    },
}


def check_api_endpoint(method: str, path: str, api_key: str | None = None) -> dict:
    """Test if an API endpoint exists and what it returns."""
    url = f"https://api.lemonsqueezy.com{path}"
    headers = {
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        req = urllib.request.Request(url, headers=headers, method=method)
        if method == "POST":
            req.data = b'{"data":{"type":"checkouts","attributes":{},"relationships":{}}}'

        with urllib.request.urlopen(req, timeout=10) as resp:
            return {
                "status": resp.status,
                "exists": True,
                "authenticated": True,
            }
    except urllib.error.HTTPError as e:
        return {
            "status": e.code,
            "exists": e.code != 404,
            "authenticated": e.code != 401,
            "error": e.reason,
        }
    except Exception as e:
        return {
            "status": 0,
            "exists": None,
            "error": str(e),
        }


def print_api_map():
    """Print the full API capability map."""
    print("=" * 70)
    print("LEMON SQUEEZY API — CAPABILITY MAP")
    print("=" * 70)
    print(f"Base URL: {BASE_URL}")
    print(f"Auth: Bearer token (API key)")
    print(f"Format: JSON:API spec")
    print(f"Rate limit: 300 req/min")
    print("=" * 70)

    total_endpoints = 0
    create_capable = []
    read_only = []

    for resource, info in API_RESOURCES.items():
        methods = set()
        for ep in info["endpoints"]:
            methods.add(ep["method"])
            total_endpoints += 1

        has_create = "POST" in methods
        has_update = "PATCH" in methods or "PUT" in methods
        has_delete = "DELETE" in methods

        crud = []
        if has_create:
            crud.append("CREATE")
            create_capable.append(resource)
        crud.append("READ")  # all have GET
        if has_update:
            crud.append("UPDATE")
        if has_delete:
            crud.append("DELETE")

        print(f"\n  {resource.upper()}")
        print(f"  Operations: {' | '.join(crud)}")
        for ep in info["endpoints"]:
            print(f"    {ep['method']:6s} {ep['path']:45s} — {ep['desc']}")

        if not has_create:
            read_only.append(resource)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total endpoints catalogued: {total_endpoints}")
    print(f"Resources: {len(API_RESOURCES)}")
    print(f"\nCan CREATE via API: {', '.join(create_capable) if create_capable else 'NONE'}")
    print(f"Read-only resources: {', '.join(read_only)}")

    print("\n" + "-" * 70)
    print("KEY FINDINGS FOR PRODUCT CREATION:")
    print("-" * 70)
    print("""
  1. PRODUCTS: READ-ONLY — Cannot create products via API.
     Products must be created manually in the Lemon Squeezy dashboard.
     This is a known limitation; feature request is open on their feedback board.

  2. CHECKOUTS: CAN CREATE — POST /v1/checkouts
     You CAN create checkout sessions programmatically.
     This means an AI agent can generate unique purchase links for customers.
     This is the KEY capability for agentic commerce.

  3. DISCOUNTS: CAN CREATE — POST /v1/discounts
     You can programmatically create discount codes.
     Useful for promotional campaigns and affiliate programs.

  4. WEBHOOKS: FULL CRUD — POST/PATCH/DELETE /v1/webhooks
     Full webhook management for event-driven automation.

  5. SUBSCRIPTIONS: CAN UPDATE/CANCEL
     Manage subscription lifecycle programmatically.

  6. LICENSE KEYS: CAN UPDATE
     Manage software license keys after creation.
""")

    print("-" * 70)
    print("RECOMMENDED WORKFLOW:")
    print("-" * 70)
    print("""
  Step 1: Manually create products in Lemon Squeezy dashboard
  Step 2: Use API to list products and get variant IDs
  Step 3: Use API to create checkout URLs for each variant
  Step 4: Use API to create webhooks for order notifications
  Step 5: Use API to manage discounts and license keys
  Step 6: AI agents use checkout URLs to enable purchases
""")


def test_with_key(api_key: str):
    """Test API endpoints with a real API key."""
    print("\n" + "=" * 70)
    print("LIVE API TEST")
    print("=" * 70)

    test_endpoints = [
        ("GET", "/v1/users/me", "Authenticated user"),
        ("GET", "/v1/stores", "List stores"),
        ("GET", "/v1/products", "List products"),
        ("GET", "/v1/variants", "List variants"),
        ("GET", "/v1/checkouts", "List checkouts"),
        ("GET", "/v1/orders", "List orders"),
        ("GET", "/v1/customers", "List customers"),
        ("GET", "/v1/webhooks", "List webhooks"),
    ]

    for method, path, desc in test_endpoints:
        result = check_api_endpoint(method, path, api_key)
        status_icon = "OK" if result.get("status") == 200 else f"ERR {result.get('status')}"
        print(f"  [{status_icon:>7s}] {method} {path:40s} — {desc}")

    # Try creating a checkout (will fail without valid variant, but tests endpoint existence)
    print("\n  Testing POST endpoints...")
    post_result = check_api_endpoint("POST", "/v1/checkouts", api_key)
    if post_result.get("status") == 422:
        print("  [  OK  ] POST /v1/checkouts exists (422 = validation error, endpoint exists)")
    else:
        print(f"  [{post_result.get('status'):>5}] POST /v1/checkouts — {post_result.get('error', 'unknown')}")

    # Try product creation (expected to fail with 404 or 405)
    print("\n  Testing product creation (expected to fail)...")
    url = f"{BASE_URL}/products"
    headers = {
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
        "Authorization": f"Bearer {api_key}",
    }
    body = json.dumps({
        "data": {
            "type": "products",
            "attributes": {
                "name": "Test Product",
                "description": "API creation test",
            },
            "relationships": {
                "store": {
                    "data": {
                        "type": "stores",
                        "id": "1"
                    }
                }
            }
        }
    }).encode()

    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"  [SURPRISE] POST /v1/products returned {resp.status} — product creation MAY be supported!")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  [CONFIRMED] POST /v1/products returns 404 — product creation NOT supported via API")
        elif e.code == 405:
            print(f"  [CONFIRMED] POST /v1/products returns 405 Method Not Allowed — endpoint exists but POST disabled")
        elif e.code == 422:
            print(f"  [SURPRISE] POST /v1/products returns 422 — endpoint exists! Product creation MAY be supported!")
        else:
            print(f"  [  {e.code}  ] POST /v1/products — {e.reason}")
    except Exception as e:
        print(f"  [ERROR] {e}")


def main():
    api_key = None
    if "--api-key" in sys.argv:
        idx = sys.argv.index("--api-key")
        if idx + 1 < len(sys.argv):
            api_key = sys.argv[idx + 1]

    print_api_map()

    if api_key:
        test_with_key(api_key)
    else:
        print("\n" + "-" * 70)
        print("To test with a real API key:")
        print("  python3 monetisation/lemon-squeezy-setup.py --api-key YOUR_KEY")
        print("-" * 70)

    print("\nDone.")


if __name__ == "__main__":
    main()
