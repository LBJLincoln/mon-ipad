#!/usr/bin/env python3
"""Debug helper: fetch n8n execution statuses with full error details per node."""
import json
import os
import urllib.request
import urllib.error

N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")
CI_EMAIL = "ci@nomos.ai"
CI_PASSWORD = "CI-Nomos-2026!"


def get_cookie():
    req = urllib.request.Request(
        f"{N8N_HOST}/rest/login",
        data=json.dumps({"emailOrLdapLoginId": CI_EMAIL, "password": CI_PASSWORD}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        raw_cookies = resp.headers.get("Set-Cookie", "")
        for part in raw_cookies.split(";"):
            part = part.strip()
            if part.startswith("n8n-auth="):
                return part[9:]
    except Exception as e:
        print(f"Login failed: {e}")
    return ""


def fetch_json(url, cookie):
    req = urllib.request.Request(url, headers={"Cookie": f"n8n-auth={cookie}"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} for {url}")
        try:
            print(f"  Body: {e.read().decode()[:200]}")
        except Exception:
            pass
        return None
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None


def extract_name(e):
    wf_data = e.get("workflowData", {})
    if isinstance(wf_data, dict) and wf_data.get("name"):
        return wf_data["name"]
    if e.get("workflowName"):
        return e["workflowName"]
    return e.get("workflowId", "?")


def extract_errors_from_detail(detail):
    """Extract errors from full execution detail (with runData)."""
    errors = []
    if not isinstance(detail, dict):
        return errors

    # Unwrap n8n 2.x wrapper
    inner = detail.get("data", detail)

    # Top-level error
    for key in ("error", "errorMessage"):
        if inner.get(key):
            errors.append(f"[top-level] {str(inner[key])[:200]}")
            break

    exec_data = inner.get("data", {})
    if not isinstance(exec_data, dict):
        return errors

    result_data = exec_data.get("resultData", {})
    if result_data.get("error"):
        errors.append(f"[resultData] {str(result_data['error'])[:200]}")

    run_data = result_data.get("runData", {})
    for node_name, node_runs in (run_data or {}).items():
        for run in (node_runs if isinstance(node_runs, list) else []):
            # Check error at run level
            if run.get("error"):
                err = run["error"]
                msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                desc = err.get("description", "") if isinstance(err, dict) else ""
                errors.append(f"[{node_name}] {msg[:150]}" + (f" — {desc[:80]}" if desc else ""))
            # Check error in data outputs
            data_items = run.get("data", {})
            if isinstance(data_items, dict):
                for output_key, output_val in data_items.items():
                    if isinstance(output_val, list):
                        for item in output_val:
                            if isinstance(item, dict) and item.get("error"):
                                err = item["error"]
                                msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                                errors.append(f"[{node_name}/{output_key}] {msg[:150]}")
    return errors


def main():
    print("=== n8n Execution Debug Report ===")
    cookie = get_cookie()
    if not cookie:
        print("Could not login to n8n")
        return

    # Fetch last 20 executions (summary)
    data = fetch_json(f"{N8N_HOST}/rest/executions?limit=20", cookie)
    if not data:
        print("Could not fetch executions list")
        return

    # Parse n8n 2.x format
    inner = data.get("data", data) if isinstance(data, dict) else data
    if isinstance(inner, dict):
        execs = inner.get("results", inner.get("data", []))
    elif isinstance(inner, list):
        execs = inner
    else:
        print(f"Unexpected format: {str(data)[:200]}")
        return

    if not execs:
        print("  No executions found")
        return

    print(f"Total executions: {len(execs)}")

    # Group by status
    errors = [e for e in execs if e.get("status") != "success"]
    successes = [e for e in execs if e.get("status") == "success"]
    print(f"  Errors: {len(errors)}, Successes: {len(successes)}")

    # Show all executions with summary
    print("\n--- All executions (newest first) ---")
    for e in execs[:20]:
        status = e.get("status", "?")
        name = extract_name(e)
        wf_id = e.get("workflowId", "?")
        exec_id = e.get("id", "?")
        print(f"  [{status:8}] id={exec_id:4} wf={wf_id} {name[:45]}")

    # For each error execution, fetch full details
    print("\n--- Error execution details ---")
    shown = 0
    for e in execs[:20]:
        if e.get("status") == "success":
            continue
        exec_id = e.get("id", "?")
        name = extract_name(e)
        status = e.get("status", "?")

        detail = fetch_json(f"{N8N_HOST}/rest/executions/{exec_id}", cookie)
        errs = extract_errors_from_detail(detail) if detail else []

        print(f"\n  [{status}] id={exec_id} — {name[:50]}")
        if errs:
            for err in errs[:5]:
                print(f"    ERROR: {err}")
        else:
            print(f"    (no detailed error found in response)")
            # Show raw snippet for debugging
            if detail:
                snippet = str(detail)[:300]
                print(f"    Raw snippet: {snippet}")
        shown += 1
        if shown >= 8:
            break

    if shown == 0:
        print("  No error executions found (all succeeded)")


if __name__ == "__main__":
    main()
