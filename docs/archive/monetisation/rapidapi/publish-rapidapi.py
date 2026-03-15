#!/usr/bin/env python3
"""
publish-rapidapi.py — Publish the Nomos Multi-RAG API to RapidAPI.

This script uses the RapidAPI Platform API to:
1. Create or update the API listing
2. Upload the OpenAPI 3.0 specification
3. Configure pricing tiers (Free / Basic / Pro)
4. Set rate limits per tier

Prerequisites:
  - RAPIDAPI_KEY env var (your RapidAPI provider key)
  - RAPIDAPI_OWNER env var (your RapidAPI username or team slug)
  - openapi.json in the same directory

Usage:
  source .env.local
  python3 monetisation/rapidapi/publish-rapidapi.py [--dry-run]

RapidAPI Platform API docs:
  https://docs.rapidapi.com/docs/platform-api
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
OPENAPI_PATH = SCRIPT_DIR / "openapi.json"

RAPIDAPI_PLATFORM_URL = "https://platformapi.p.rapidapi.com"

# API metadata
API_NAME = "nomos-multi-rag"
API_DISPLAY_NAME = "Nomos Multi-RAG API"
API_DESCRIPTION = (
    "Production-grade Retrieval-Augmented Generation (RAG) API with 3 specialized pipelines. "
    "Standard (vector search over 46K+ documents), Graph (Neo4j knowledge graph with 86K+ nodes), "
    "and Quantitative (SQL generation over 3,800+ financial tables). "
    "Covers 4 industry sectors: Construction, Finance, Legal, Industrial. "
    "Powered by Llama 3.3 70B with Jina v3 embeddings."
)
API_CATEGORY = "Artificial Intelligence/Machine Learning"

# Pricing tiers
PRICING_TIERS = [
    {
        "name": "Free",
        "price": 0,
        "rate_limit": {
            "requests_per_day": 10,
            "requests_per_hour": 5,
        },
        "description": "Try the API with 10 requests per day. All 3 pipelines included.",
    },
    {
        "name": "Basic",
        "price": 9.99,
        "rate_limit": {
            "requests_per_day": 100,
            "requests_per_hour": 50,
        },
        "description": "100 requests/day. Suitable for prototyping and small-scale integrations.",
    },
    {
        "name": "Pro",
        "price": 29.99,
        "rate_limit": {
            "requests_per_day": 1000,
            "requests_per_hour": 200,
        },
        "description": "1000 requests/day. Full production access with priority support.",
    },
]


def get_env(key: str) -> str:
    """Get a required environment variable."""
    val = os.environ.get(key)
    if not val:
        print(f"ERROR: {key} environment variable is not set.", file=sys.stderr)
        print(f"  Set it with: export {key}='your-key-here'", file=sys.stderr)
        sys.exit(1)
    return val


def api_request(method: str, path: str, api_key: str, data: dict | None = None) -> dict:
    """Make a request to the RapidAPI Platform API."""
    url = f"{RAPIDAPI_PLATFORM_URL}{path}"
    headers = {
        "Content-Type": "application/json",
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "platformapi.p.rapidapi.com",
    }

    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code} from {method} {path}: {body_text}", file=sys.stderr)
        raise
    except urllib.error.URLError as e:
        print(f"Network error for {method} {path}: {e.reason}", file=sys.stderr)
        raise


def load_openapi_spec() -> dict:
    """Load and validate the OpenAPI spec."""
    if not OPENAPI_PATH.exists():
        print(f"ERROR: OpenAPI spec not found at {OPENAPI_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(OPENAPI_PATH, "r") as f:
        spec = json.load(f)

    # Basic validation
    assert spec.get("openapi", "").startswith("3."), "Not an OpenAPI 3.x spec"
    assert "paths" in spec, "No paths defined"
    assert len(spec["paths"]) == 3, f"Expected 3 paths, got {len(spec['paths'])}"
    print(f"  Loaded OpenAPI spec: {len(spec['paths'])} endpoints")
    return spec


def step_1_create_or_find_api(api_key: str, owner: str, dry_run: bool) -> str | None:
    """Create the API on RapidAPI or find an existing one."""
    print("\n[Step 1] Create or find API on RapidAPI...")

    if dry_run:
        print("  [DRY RUN] Would create API:", API_DISPLAY_NAME)
        return "dry-run-api-id"

    # Try to list existing APIs first
    try:
        result = api_request("GET", f"/v1/apis?owner={owner}&name={API_NAME}", api_key)
        apis = result.get("apis", [])
        if apis:
            api_id = apis[0]["id"]
            print(f"  Found existing API: {api_id}")
            return api_id
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        print("  No existing API found, creating new one...")

    # Create new API
    payload = {
        "name": API_NAME,
        "displayName": API_DISPLAY_NAME,
        "description": API_DESCRIPTION,
        "category": API_CATEGORY,
        "owner": owner,
    }

    try:
        result = api_request("POST", "/v1/apis", api_key, payload)
        api_id = result.get("id", result.get("apiId"))
        print(f"  Created API: {api_id}")
        return api_id
    except urllib.error.HTTPError:
        print("  WARNING: Could not create API via Platform API.")
        print("  You may need to create the API manually at https://rapidapi.com/provider")
        print("  Then re-run this script.")
        return None


def step_2_upload_spec(api_key: str, api_id: str, dry_run: bool) -> str | None:
    """Upload the OpenAPI specification."""
    print("\n[Step 2] Upload OpenAPI specification...")
    spec = load_openapi_spec()

    if dry_run:
        print("  [DRY RUN] Would upload spec with endpoints:")
        for path in spec["paths"]:
            print(f"    POST {path}")
        return "dry-run-version-id"

    payload = {
        "openapi": spec,
    }

    try:
        result = api_request("POST", f"/v1/apis/{api_id}/versions", api_key, payload)
        version_id = result.get("id", result.get("versionId"))
        print(f"  Uploaded spec, version: {version_id}")
        return version_id
    except urllib.error.HTTPError:
        print("  WARNING: Could not upload spec via Platform API.")
        print("  Upload manually at: https://rapidapi.com/provider/dashboard")
        print(f"  Spec file: {OPENAPI_PATH}")
        return None


def step_3_configure_pricing(api_key: str, api_id: str, dry_run: bool):
    """Configure pricing tiers."""
    print("\n[Step 3] Configure pricing tiers...")

    for tier in PRICING_TIERS:
        price_str = f"${tier['price']}/mo" if tier["price"] > 0 else "Free"
        limits = tier["rate_limit"]
        print(
            f"  {tier['name']:8s} {price_str:12s} "
            f"{limits['requests_per_day']} req/day, "
            f"{limits['requests_per_hour']} req/hour"
        )

        if dry_run:
            print(f"    [DRY RUN] Would set plan: {tier['name']}")
            continue

        payload = {
            "name": tier["name"],
            "price": tier["price"],
            "billingPeriod": "monthly",
            "rateLimit": {
                "requestsPerDay": limits["requests_per_day"],
                "requestsPerHour": limits["requests_per_hour"],
            },
            "description": tier["description"],
            "acl": [
                {"endpoint": "/webhook/rag-multi-index-v3", "method": "POST"},
                {"endpoint": "/webhook/ff622742-6d71-4e91-af71-b5c666088717", "method": "POST"},
                {"endpoint": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9", "method": "POST"},
            ],
        }

        try:
            api_request("POST", f"/v1/apis/{api_id}/plans", api_key, payload)
            print(f"    Plan created: {tier['name']}")
        except urllib.error.HTTPError:
            print(f"    WARNING: Could not create plan {tier['name']} via API.")
            print("    Configure manually in the RapidAPI provider dashboard.")


def step_4_print_summary(api_id: str, dry_run: bool):
    """Print a summary of what was done."""
    print("\n" + "=" * 60)
    if dry_run:
        print("DRY RUN COMPLETE -- no changes were made to RapidAPI.")
    else:
        print("PUBLISH COMPLETE")
    print("=" * 60)
    print()
    print("API Details:")
    print(f"  Name:     {API_DISPLAY_NAME}")
    print(f"  ID:       {api_id}")
    print(f"  Spec:     {OPENAPI_PATH}")
    print()
    print("Endpoints:")
    print("  POST /webhook/rag-multi-index-v3                           (Standard)")
    print("  POST /webhook/ff622742-6d71-4e91-af71-b5c666088717         (Graph)")
    print("  POST /webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9         (Quantitative)")
    print()
    print("Pricing Tiers:")
    for tier in PRICING_TIERS:
        price_str = f"${tier['price']}/mo" if tier["price"] > 0 else "Free"
        print(f"  {tier['name']:8s} {price_str:12s} {tier['rate_limit']['requests_per_day']} req/day")
    print()
    print("Next steps:")
    print("  1. Visit https://rapidapi.com/provider/dashboard")
    print("  2. Review and publish the API listing")
    print("  3. Add a logo and long description")
    print("  4. Test each endpoint from the RapidAPI UI")
    print("  5. Share the listing URL")
    print()
    if dry_run:
        print("Re-run without --dry-run to publish for real:")
        print("  python3 monetisation/rapidapi/publish-rapidapi.py")


def main():
    parser = argparse.ArgumentParser(description="Publish Nomos Multi-RAG API to RapidAPI")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making any API calls",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Nomos Multi-RAG API -- RapidAPI Publisher")
    print("=" * 60)

    if args.dry_run:
        print("\n*** DRY RUN MODE -- no API calls will be made ***\n")
        api_key = os.environ.get("RAPIDAPI_KEY", "dry-run-key")
        owner = os.environ.get("RAPIDAPI_OWNER", "dry-run-owner")
    else:
        api_key = get_env("RAPIDAPI_KEY")
        owner = get_env("RAPIDAPI_OWNER")

    # Validate spec exists
    load_openapi_spec()

    # Step 1: Create or find the API
    api_id = step_1_create_or_find_api(api_key, owner, args.dry_run)
    if not api_id:
        print("\nAborting: could not create or find API.", file=sys.stderr)
        sys.exit(1)

    # Step 2: Upload OpenAPI spec
    step_2_upload_spec(api_key, api_id, args.dry_run)

    # Step 3: Configure pricing
    step_3_configure_pricing(api_key, api_id, args.dry_run)

    # Step 4: Summary
    step_4_print_summary(api_id, args.dry_run)


if __name__ == "__main__":
    main()
