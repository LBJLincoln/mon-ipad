#!/usr/bin/env python3
"""
Test script for Nomos Docling API on HF Space.
Run from VM after Space is deployed.

Usage:
    source .env.local
    python3 hf-spaces/docling/test-docling.py
    python3 hf-spaces/docling/test-docling.py --url https://example.com/test.pdf
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "https://lbjlincoln-nomos-docling-api.hf.space"


def test_health():
    """Test health endpoint."""
    print("=" * 60)
    print("TEST: GET /health")
    print("=" * 60)
    try:
        req = urllib.request.Request(f"{BASE_URL}/health")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            print(f"Status: {resp.status}")
            print(json.dumps(data, indent=2))
            return data.get("status") == "ok"
    except Exception as e:
        print(f"FAILED: {e}")
        return False


def test_info():
    """Test info endpoint."""
    print("\n" + "=" * 60)
    print("TEST: GET /info")
    print("=" * 60)
    try:
        req = urllib.request.Request(f"{BASE_URL}/info")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            print(f"Status: {resp.status}")
            print(json.dumps(data, indent=2))
            return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False


def test_convert_url(url: str):
    """Test convert-url endpoint."""
    print("\n" + "=" * 60)
    print(f"TEST: POST /convert-url")
    print(f"URL: {url}")
    print("=" * 60)

    payload = json.dumps({
        "url": url,
        "chunk_size": 500,
        "chunk_overlap": 100,
    }).encode()

    try:
        req = urllib.request.Request(
            f"{BASE_URL}/convert-url",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
            elapsed = time.time() - t0

            print(f"Status: {resp.status}")
            print(f"Time: {elapsed:.1f}s")
            print(f"Text length: {data.get('text_length', 'N/A')}")
            print(f"Pages: {data.get('num_pages', 'N/A')}")
            print(f"Tables: {data.get('num_tables', 'N/A')}")
            print(f"Chunks: {data.get('num_chunks', 'N/A')}")

            # Show first 500 chars of text
            text = data.get("full_text", "")
            if text:
                print(f"\nFirst 500 chars:")
                print("-" * 40)
                print(text[:500])
                print("-" * 40)

            # Show tables
            tables = data.get("tables", [])
            if tables:
                print(f"\nTables ({len(tables)}):")
                for t in tables[:3]:
                    if "markdown" in t:
                        print(t["markdown"][:300])
                    print()

            return data.get("status") == "success"

    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"HTTP {e.code}: {body[:500]}")
        return False
    except Exception as e:
        print(f"FAILED: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test Nomos Docling API")
    parser.add_argument("--url", help="PDF URL to test conversion")
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help=f"Base URL of Docling API (default: {BASE_URL})",
    )
    args = parser.parse_args()

    global BASE_URL
    BASE_URL = args.base_url

    results = []

    # Health check
    results.append(("health", test_health()))

    # Info check
    results.append(("info", test_info()))

    # URL conversion test
    if args.url:
        results.append(("convert-url", test_convert_url(args.url)))
    else:
        # Use a small public domain PDF for testing
        test_url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
        results.append(("convert-url", test_convert_url(test_url)))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
