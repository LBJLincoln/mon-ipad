#!/usr/bin/env python3
"""Export and optionally delete inactive n8n workflows from HF Spaces.

Connects to n8n Spaces via cookie auth, lists all workflows, identifies
inactive ones, exports their full JSON to n8n/archive/inactive/, and
optionally deletes them with --delete flag.

Usage:
  python3 ops/cleanup-workflows.py              # Export only (safe)
  python3 ops/cleanup-workflows.py --delete     # Export + delete inactive
  python3 ops/cleanup-workflows.py --space S1   # Specific Space only
  python3 ops/cleanup-workflows.py --dry-run    # Show what would be archived
  python3 ops/cleanup-workflows.py --space S1 --delete --yes  # Skip confirmation
"""

import argparse
import datetime
import json
import http.cookiejar
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request

# ─── Force IPv4 (HF Spaces resolve to IPv6 that times out) ───
_original_getaddrinfo = socket.getaddrinfo
def _ipv4_only_getaddrinfo(*args, **kwargs):
    responses = _original_getaddrinfo(*args, **kwargs)
    return [r for r in responses if r[0] == socket.AF_INET] or responses
socket.getaddrinfo = _ipv4_only_getaddrinfo

# ─── Constants ───
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE_DIR = os.path.join(REPO_ROOT, "n8n", "archive", "inactive")
INDEX_FILE = os.path.join(ARCHIVE_DIR, "INDEX.md")

N8N_EMAIL = "ci@nomos.ai"
N8N_PASSWORD = "CI-Nomos-2026!"

SPACES = {
    "S1": "https://lbjlincoln-nomos-rag-engine.hf.space",
    "S3": "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "S5": "https://lbjlincoln-nomos-rag-engine-5.hf.space",
    "S9": "https://lbjlincoln-nomos-rag-engine-9.hf.space",
}

# SSL context that skips verification for HF proxy
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


# ─── HTTP helpers ───

def _make_opener():
    """Create a new urllib opener with cookie jar."""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPSHandler(context=_ssl_ctx),
    )
    return opener


def _http_request(opener, url, method="GET", data=None, timeout=30):
    """Make an HTTP request, return (status_code, parsed_json)."""
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = opener.open(req, timeout=timeout)
        raw = resp.read().decode("utf-8")
        return resp.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"error": raw[:500]}
    except Exception as e:
        return 0, {"error": str(e)}


def login(opener, base_url):
    """Login to n8n and acquire session cookie. Returns True on success."""
    login_data = {
        "emailOrLdapLoginId": N8N_EMAIL,
        "password": N8N_PASSWORD,
    }
    status, resp = _http_request(opener, f"{base_url}/rest/login", method="POST", data=login_data)
    return status == 200


def list_workflows(opener, base_url):
    """Fetch all workflows from a Space. Returns list of workflow summaries."""
    all_wfs = []
    # n8n paginates — fetch in batches
    cursor = None
    limit = 250  # n8n max per page
    for _ in range(20):  # safety limit
        url = f"{base_url}/rest/workflows?limit={limit}"
        if cursor:
            url += f"&cursor={cursor}"
        status, resp = _http_request(opener, url, timeout=60)
        if status != 200:
            print(f"  [ERROR] GET /rest/workflows -> HTTP {status}: {resp}")
            break

        data = resp.get("data", resp) if isinstance(resp, dict) else resp
        if isinstance(data, list):
            all_wfs.extend(data)
            break  # no pagination metadata, got everything
        elif isinstance(data, dict):
            items = data.get("data", [])
            all_wfs.extend(items)
            next_cursor = data.get("nextCursor")
            if not next_cursor or not items:
                break
            cursor = next_cursor
        else:
            break
    return all_wfs


def get_workflow_full(opener, base_url, wf_id):
    """Fetch the full workflow JSON (with nodes, connections, etc.)."""
    status, resp = _http_request(opener, f"{base_url}/rest/workflows/{wf_id}", timeout=30)
    if status != 200:
        return None
    # n8n wraps in "data" sometimes
    return resp.get("data", resp) if isinstance(resp, dict) else resp


def delete_workflow(opener, base_url, wf_id):
    """Delete a workflow by ID. Returns (success, response)."""
    status, resp = _http_request(opener, f"{base_url}/rest/workflows/{wf_id}", method="DELETE", timeout=30)
    return status == 200, resp


# ─── Filename sanitizer ───

def sanitize_name(name):
    """Convert workflow name to a safe filename component."""
    # Replace special chars with hyphens, collapse multiples, strip edges
    s = re.sub(r'[^\w\s-]', '-', name)
    s = re.sub(r'[\s]+', '-', s)
    s = re.sub(r'-{2,}', '-', s)
    s = s.strip('-')
    # Truncate to 80 chars to keep paths reasonable
    return s[:80] if s else "unnamed"


# ─── Core logic ───

def process_space(space_name, base_url, delete=False, dry_run=False, auto_yes=False):
    """Process a single Space: export (and optionally delete) inactive workflows.

    Returns dict with stats and list of archived workflow info.
    """
    print(f"\n{'='*70}")
    print(f"  {space_name}: {base_url}")
    print(f"{'='*70}")

    opener = _make_opener()

    # Login
    print(f"  [AUTH] Logging in...")
    if not login(opener, base_url):
        print(f"  [AUTH] Login FAILED — skipping {space_name}")
        return {"space": space_name, "error": "login_failed", "archived": [], "active": []}

    print(f"  [AUTH] Login OK")

    # List workflows
    print(f"  [LIST] Fetching workflows...")
    workflows = list_workflows(opener, base_url)
    print(f"  [LIST] Found {len(workflows)} total workflows")

    if not workflows:
        return {"space": space_name, "total": 0, "archived": [], "active": []}

    # Partition active vs inactive
    active = [w for w in workflows if w.get("active", False)]
    inactive = [w for w in workflows if not w.get("active", False)]

    print(f"  [FILTER] Active: {len(active)} | Inactive: {len(inactive)}")
    print()

    # Show active workflows (for reference)
    if active:
        print(f"  ACTIVE (will NOT be touched):")
        for w in sorted(active, key=lambda x: x.get("name", "")):
            print(f"    + {w['id']:25s} {w['name'][:60]}")
        print()

    if not inactive:
        print(f"  No inactive workflows to archive.")
        return {
            "space": space_name,
            "total": len(workflows),
            "active": [{"id": w["id"], "name": w["name"]} for w in active],
            "archived": [],
        }

    # Show inactive workflows
    print(f"  INACTIVE (will be archived):")
    for w in sorted(inactive, key=lambda x: x.get("name", "")):
        print(f"    - {w['id']:25s} {w['name'][:60]}")
    print()

    # Dry run stops here
    if dry_run:
        print(f"  [DRY-RUN] Would archive {len(inactive)} workflows. No files written.")
        return {
            "space": space_name,
            "total": len(workflows),
            "active": [{"id": w["id"], "name": w["name"]} for w in active],
            "archived": [{"id": w["id"], "name": w["name"], "dry_run": True} for w in inactive],
        }

    # Delete confirmation
    if delete and not auto_yes:
        print(f"  WARNING: --delete flag is set. {len(inactive)} inactive workflows will be")
        print(f"  PERMANENTLY DELETED from {space_name} after export.")
        answer = input(f"  Type 'yes' to confirm deletion on {space_name}: ").strip().lower()
        if answer != "yes":
            print(f"  Deletion cancelled. Will export only.")
            delete = False

    # Create space-specific subdirectory
    space_dir = os.path.join(ARCHIVE_DIR, space_name.lower())
    os.makedirs(space_dir, exist_ok=True)

    archived = []
    deleted_ids = []
    errors = []

    for i, w in enumerate(inactive, 1):
        wf_id = w["id"]
        wf_name = w.get("name", "unnamed")
        safe_name = sanitize_name(wf_name)
        filename = f"{safe_name}_{wf_id}.json"
        filepath = os.path.join(space_dir, filename)

        print(f"  [{i}/{len(inactive)}] Exporting: {wf_name[:50]}...")

        # Fetch full workflow
        full_wf = get_workflow_full(opener, base_url, wf_id)
        if full_wf is None:
            print(f"    [ERROR] Could not fetch workflow {wf_id}")
            errors.append({"id": wf_id, "name": wf_name, "error": "fetch_failed"})
            continue

        # Add export metadata
        export_data = {
            "_export_metadata": {
                "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
                "source_space": space_name,
                "source_url": base_url,
                "original_id": wf_id,
                "original_name": wf_name,
                "was_active": False,
            },
            "workflow": full_wf,
        }

        # Write JSON
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        record = {
            "id": wf_id,
            "name": wf_name,
            "file": os.path.relpath(filepath, REPO_ROOT),
            "nodes": len(full_wf.get("nodes", [])),
            "created": full_wf.get("createdAt", ""),
            "updated": full_wf.get("updatedAt", ""),
        }

        print(f"    Saved: {filename} ({record['nodes']} nodes)")

        # Delete if requested
        if delete:
            print(f"    [DELETE] Removing from {space_name}...")
            ok, del_resp = delete_workflow(opener, base_url, wf_id)
            if ok:
                print(f"    [DELETE] Deleted successfully")
                record["deleted"] = True
                deleted_ids.append(wf_id)
            else:
                print(f"    [DELETE] FAILED: {del_resp}")
                record["deleted"] = False
                record["delete_error"] = str(del_resp)[:200]
        else:
            record["deleted"] = False

        archived.append(record)

        # Small delay to avoid hammering the API
        time.sleep(0.3)

    # Summary for this space
    print(f"\n  DONE: {len(archived)} exported", end="")
    if delete:
        print(f", {len(deleted_ids)} deleted", end="")
    if errors:
        print(f", {len(errors)} errors", end="")
    print()

    return {
        "space": space_name,
        "url": base_url,
        "total": len(workflows),
        "active": [{"id": w["id"], "name": w["name"]} for w in active],
        "archived": archived,
        "errors": errors,
        "deleted_count": len(deleted_ids),
    }


def generate_index(results):
    """Generate INDEX.md from all archive results."""
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        "# Archived Inactive n8n Workflows",
        "",
        f"> Generated: {now}",
        "",
        "These workflows were exported from n8n HF Spaces because they were **inactive**.",
        "Each JSON file contains the full workflow definition and can be re-imported if needed.",
        "",
    ]

    total_archived = 0
    total_active = 0
    total_deleted = 0

    for r in results:
        space = r.get("space", "?")
        url = r.get("url", "")
        active_list = r.get("active", [])
        archived_list = r.get("archived", [])
        deleted_count = r.get("deleted_count", 0)
        errors = r.get("errors", [])

        total_archived += len(archived_list)
        total_active += len(active_list)
        total_deleted += deleted_count

        lines.append(f"## {space}")
        if url:
            lines.append(f"")
            lines.append(f"URL: `{url}`")
        lines.append(f"")
        lines.append(f"- Total workflows: {r.get('total', '?')}")
        lines.append(f"- Active (kept): {len(active_list)}")
        lines.append(f"- Inactive (archived): {len(archived_list)}")
        if deleted_count:
            lines.append(f"- Deleted from Space: {deleted_count}")
        if errors:
            lines.append(f"- Errors: {len(errors)}")
        lines.append(f"")

        # Active workflows table
        if active_list:
            lines.append(f"### Active Workflows (kept)")
            lines.append(f"")
            lines.append(f"| ID | Name |")
            lines.append(f"|---|---|")
            for w in sorted(active_list, key=lambda x: x.get("name", "")):
                lines.append(f"| `{w['id']}` | {w['name'][:70]} |")
            lines.append(f"")

        # Archived workflows table
        if archived_list:
            lines.append(f"### Archived Workflows")
            lines.append(f"")
            lines.append(f"| ID | Name | Nodes | File | Deleted |")
            lines.append(f"|---|---|---|---|---|")
            for w in sorted(archived_list, key=lambda x: x.get("name", "")):
                deleted_mark = "yes" if w.get("deleted") else "no"
                file_link = w.get("file", "?")
                lines.append(
                    f"| `{w['id']}` | {w['name'][:50]} | {w.get('nodes', '?')} "
                    f"| `{file_link}` | {deleted_mark} |"
                )
            lines.append(f"")

        if errors:
            lines.append(f"### Errors")
            lines.append(f"")
            for e in errors:
                lines.append(f"- `{e['id']}` {e['name']}: {e['error']}")
            lines.append(f"")

    # Summary at top
    summary_lines = [
        f"## Summary",
        f"",
        f"| Metric | Count |",
        f"|---|---|",
        f"| Spaces processed | {len(results)} |",
        f"| Active workflows (kept) | {total_active} |",
        f"| Inactive workflows (archived) | {total_archived} |",
        f"| Deleted from Spaces | {total_deleted} |",
        f"",
        f"---",
        f"",
    ]

    # Insert summary after header
    insert_pos = 7  # after the intro paragraph
    for i, sl in enumerate(summary_lines):
        lines.insert(insert_pos + i, sl)

    content = "\n".join(lines)

    os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n[INDEX] Written: {INDEX_FILE}")
    return INDEX_FILE


def main():
    parser = argparse.ArgumentParser(
        description="Export and optionally delete inactive n8n workflows from HF Spaces.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 ops/cleanup-workflows.py              # Export only (safe)
  python3 ops/cleanup-workflows.py --delete     # Export + delete
  python3 ops/cleanup-workflows.py --space S1   # Specific Space
  python3 ops/cleanup-workflows.py --dry-run    # Preview only
  python3 ops/cleanup-workflows.py --delete --yes  # Skip confirmation
""",
    )
    parser.add_argument(
        "--space",
        choices=list(SPACES.keys()),
        help="Process only this Space (default: all Spaces)",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete inactive workflows from Space AFTER exporting (requires confirmation)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be archived without writing any files",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip deletion confirmation prompt (use with --delete)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  n8n Workflow Cleanup — Export & Archive Inactive Workflows")
    print(f"  Mode: {'DRY-RUN' if args.dry_run else 'DELETE + EXPORT' if args.delete else 'EXPORT ONLY (safe)'}")
    print(f"  Archive: {ARCHIVE_DIR}")
    print("=" * 70)

    # Ensure archive dir exists
    if not args.dry_run:
        os.makedirs(ARCHIVE_DIR, exist_ok=True)

    # Determine which spaces to process
    if args.space:
        targets = {args.space: SPACES[args.space]}
    else:
        targets = SPACES

    results = []
    for space_name, base_url in targets.items():
        try:
            result = process_space(
                space_name,
                base_url,
                delete=args.delete,
                dry_run=args.dry_run,
                auto_yes=args.yes,
            )
            results.append(result)
        except Exception as e:
            print(f"\n  [FATAL] {space_name}: {e}")
            results.append({"space": space_name, "error": str(e), "archived": [], "active": []})

    # Generate INDEX.md (skip on dry-run)
    if not args.dry_run and any(r.get("archived") for r in results):
        generate_index(results)

    # Final summary
    total_active = sum(len(r.get("active", [])) for r in results)
    total_archived = sum(len(r.get("archived", [])) for r in results)
    total_deleted = sum(r.get("deleted_count", 0) for r in results)
    total_errors = sum(len(r.get("errors", [])) for r in results)

    print(f"\n{'='*70}")
    print(f"  FINAL SUMMARY")
    print(f"{'='*70}")
    print(f"  Spaces processed: {len(results)}")
    print(f"  Active workflows (kept):      {total_active}")
    print(f"  Inactive workflows (archived): {total_archived}")
    if args.delete:
        print(f"  Deleted from Spaces:           {total_deleted}")
    if total_errors:
        print(f"  Errors:                        {total_errors}")
    if not args.dry_run and total_archived > 0:
        print(f"\n  Archive: {ARCHIVE_DIR}")
        print(f"  Index:   {INDEX_FILE}")
    print(f"{'='*70}")

    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
