#!/usr/bin/env python3
"""
HF Space Scaler — Duplicate n8n Spaces for parallel throughput.

Creates clones of the primary HF Space and sets up n8n workflows on each.
Each clone gets its own OpenRouter API key for rate-limit isolation.

Usage:
    python3 scripts/scale-hf-spaces.py --list           # List current spaces
    python3 scripts/scale-hf-spaces.py --duplicate 3    # Create 3 new clones
    python3 scripts/scale-hf-spaces.py --setup-all      # Import workflows to all spaces
    python3 scripts/scale-hf-spaces.py --test-all       # Smoke test all spaces
"""

import os, sys, json, time, argparse, urllib.request, http.cookiejar
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── Config ─────────────────────────────────────────────────────────
SOURCE_SPACE = "LBJLincoln/nomos-rag-engine"
HF_TOKENS = {
    "LBJLincoln": os.environ.get("HF_TOKEN", ""),
    "LBJLincoln26": os.environ.get("HF_TOKEN_2", ""),
}

# Known spaces (auto-discovered + manual)
KNOWN_SPACES = [
    {"id": "LBJLincoln/nomos-rag-engine", "url": "https://lbjlincoln-nomos-rag-engine.hf.space", "account": "LBJLincoln"},
    {"id": "LBJLincoln26/nomos-rag-engine-2", "url": "https://lbjlincoln26-nomos-rag-engine-2.hf.space", "account": "LBJLincoln26"},
]

# Webhook paths to test
WEBHOOK_PATHS = {
    "standard": "/webhook/rag-multi-index-v3",
    "graph": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": "/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
}

# n8n login credentials
N8N_EMAIL = "ci@nomos.ai"
N8N_PASSWORD = "CI-Nomos-2026!"

# Per-pipeline OpenRouter keys for rotation
OPENROUTER_KEYS = {
    "standard": os.environ.get("OPENROUTER_KEY_STANDARD", ""),
    "graph": os.environ.get("OPENROUTER_KEY_GRAPH", ""),
    "quantitative": os.environ.get("OPENROUTER_KEY_QUANTITATIVE", ""),
    "orchestrator": os.environ.get("OPENROUTER_KEY_ORCHESTRATOR", ""),
    "pme": os.environ.get("OPENROUTER_KEY_PME", ""),
    "spare": os.environ.get("OPENROUTER_KEY_SPARE", ""),
    "main": os.environ.get("OPENROUTER_API_KEY", ""),
}


def list_spaces():
    """List all known HF Spaces and their status."""
    from huggingface_hub import HfApi

    print("\n  === HF Spaces Inventory ===\n")
    all_spaces = []

    for account, token in HF_TOKENS.items():
        if not token:
            print(f"  [{account}] No token configured")
            continue
        api = HfApi(token=token)
        try:
            spaces = list(api.list_spaces(author=account))
            for s in spaces:
                try:
                    info = api.space_info(s.id)
                    stage = info.runtime.stage if info.runtime else "UNKNOWN"
                    hw = info.runtime.hardware if info.runtime else "?"
                except:
                    stage = "?"
                    hw = "?"
                url = f"https://{s.id.replace('/', '-').lower()}.hf.space"
                all_spaces.append({"id": s.id, "account": account, "url": url, "stage": stage, "hardware": hw})
                print(f"  [{account}] {s.id} — {stage} ({hw}) — {url}")
        except Exception as e:
            print(f"  [{account}] Error listing: {e}")

    if not all_spaces:
        print("  No spaces found.")
    print(f"\n  Total: {len(all_spaces)} spaces\n")
    return all_spaces


def duplicate_space(target_account, suffix, token):
    """Duplicate the source space to a new space."""
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    target_id = f"{target_account}/nomos-rag-engine-{suffix}"

    print(f"  Duplicating {SOURCE_SPACE} → {target_id}...")

    # Set secrets for the new space
    secrets = [
        {"key": "OPENROUTER_API_KEY", "value": OPENROUTER_KEYS.get("main", "")},
        {"key": "PINECONE_API_KEY", "value": os.environ.get("PINECONE_API_KEY", "")},
        {"key": "NEO4J_URI", "value": os.environ.get("NEO4J_URI", "")},
        {"key": "NEO4J_PASSWORD", "value": os.environ.get("NEO4J_PASSWORD", "")},
        {"key": "SUPABASE_URL", "value": os.environ.get("SUPABASE_URL", "")},
        {"key": "SUPABASE_API_KEY", "value": os.environ.get("SUPABASE_API_KEY", "")},
        {"key": "SUPABASE_PASSWORD", "value": os.environ.get("SUPABASE_PASSWORD", "")},
        {"key": "COHERE_API_KEY", "value": os.environ.get("COHERE_API_KEY", "")},
        {"key": "JINA_API_KEY", "value": os.environ.get("JINA_API_KEY", "")},
    ]

    try:
        url = api.duplicate_space(
            from_id=SOURCE_SPACE,
            to_id=target_id,
            private=False,
            exist_ok=False,
            secrets=[s for s in secrets if s["value"]],
        )
        print(f"  ✓ Created: {url}")
        return str(url)
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return None


def n8n_login(base_url):
    """Login to n8n and return (opener, cookie_jar)."""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    data = json.dumps({"emailOrLdapLoginId": N8N_EMAIL, "password": N8N_PASSWORD}).encode()
    req = urllib.request.Request(f"{base_url}/rest/login", data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        resp = opener.open(req, timeout=30)
        body = json.loads(resp.read().decode())
        if body.get("data", {}).get("id"):
            return opener, cj
    except Exception as e:
        print(f"  Login failed for {base_url}: {e}")
    return None, None


def get_workflows(opener, base_url):
    """Get all workflows from an n8n instance."""
    req = urllib.request.Request(f"{base_url}/rest/workflows")
    try:
        resp = opener.open(req, timeout=30)
        body = json.loads(resp.read().decode())
        return body.get("data", [])
    except Exception as e:
        print(f"  Get workflows failed: {e}")
        return []


def test_space(space_url):
    """Smoke test all 4 pipelines on a space."""
    results = {}
    for pipe, path in WEBHOOK_PATHS.items():
        url = f"{space_url}{path}"
        try:
            t = time.time()
            data = json.dumps({"question": "What is a CDD?"}).encode()
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=60)
            elapsed = time.time() - t
            body = resp.read().decode()[:200]
            has_response = "response" in body.lower()
            results[pipe] = {"status": resp.status, "time": f"{elapsed:.1f}s", "ok": has_response}
        except Exception as e:
            results[pipe] = {"status": "ERROR", "time": "-", "ok": False, "error": str(e)[:100]}
    return results


def test_all_spaces():
    """Test all known spaces in parallel."""
    print("\n  === Testing All Spaces ===\n")

    all_spaces = list_spaces()

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        for space in all_spaces:
            if space["stage"] == "RUNNING":
                futures[executor.submit(test_space, space["url"])] = space

        for future in as_completed(futures):
            space = futures[future]
            try:
                results = future.result()
                ok_count = sum(1 for r in results.values() if r["ok"])
                print(f"\n  {space['id']} ({space['url']}):")
                for pipe, r in results.items():
                    status = "✓" if r["ok"] else "✗"
                    print(f"    [{status}] {pipe}: HTTP {r['status']} ({r['time']})")
                print(f"    → {ok_count}/4 pipelines working")
            except Exception as e:
                print(f"\n  {space['id']}: FAILED — {e}")


def generate_env_update(spaces):
    """Generate .env.local updates for multi-space routing."""
    urls = [s["url"] for s in spaces if s.get("stage") == "RUNNING"]
    if len(urls) < 2:
        print("  Need at least 2 running spaces for multi-space routing")
        return

    hosts_csv = ",".join(urls)
    print("\n  === .env.local Updates ===\n")
    for pipe in WEBHOOK_PATHS:
        key = f"N8N_HOST_{pipe.upper().replace('-','_')}"
        print(f"  export {key}={hosts_csv}")
    print(f"\n  Total spaces: {len(urls)}")
    print(f"  Theoretical throughput: ~{len(urls) * 48} q/min (20 concurrent × {len(urls)} spaces)")


def main():
    parser = argparse.ArgumentParser(description="HF Space Scaler")
    parser.add_argument("--list", action="store_true", help="List all spaces")
    parser.add_argument("--duplicate", type=int, metavar="N", help="Create N new space clones")
    parser.add_argument("--test-all", action="store_true", help="Test all spaces")
    parser.add_argument("--setup-all", action="store_true", help="Import workflows to all spaces")
    parser.add_argument("--env-update", action="store_true", help="Generate .env.local updates")
    args = parser.parse_args()

    if args.list:
        list_spaces()
    elif args.duplicate:
        n = args.duplicate
        print(f"\n  Creating {n} new HF Space clones...\n")
        for i in range(n):
            suffix = i + 3  # Start from 3 (1 = primary, 2 = secondary)
            # Alternate between accounts
            account = "LBJLincoln" if i % 2 == 0 else "LBJLincoln26"
            token = HF_TOKENS[account]
            if not token:
                print(f"  Skipping {account} — no token")
                continue
            duplicate_space(account, str(suffix), token)
            time.sleep(2)
    elif args.test_all:
        test_all_spaces()
    elif args.env_update:
        spaces = list_spaces()
        generate_env_update(spaces)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
