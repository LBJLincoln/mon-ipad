#!/usr/bin/env python3
"""
Self-Healing Pipeline Orchestrator v2.0 — Structured 5-Level Architecture

Levels:
  L0: Health check all HF Spaces (parallel curl)
  L1: Smoke-test 3 sector questions per pipeline (9 total)
  L2: On failure — fetch last n8n execution, match against fixes-structured.json
  L3: Apply auto-fixable fixes (P0-P1 only)
  L4: Log everything to logs/self-heal.jsonl

Usage:
    source .env.local
    python3 scripts/self-heal-orchestrator.py --smoke        # L0 + L1 only (for cron)
    python3 scripts/self-heal-orchestrator.py --full         # L0 through L4
    python3 scripts/self-heal-orchestrator.py --loop 15      # Full cycle every 15 min
"""

import os
import sys
import json
import re
import time
import ssl
import urllib.request
import subprocess
import argparse
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")
FIXES_FILE = BASE_DIR / "technicals" / "fixes-structured.json"
LOG_FILE = BASE_DIR / "logs" / "self-heal.jsonl"

HF_SPACES = [
    {"name": "n8n-engine", "url": "https://lbjlincoln-nomos-rag-engine.hf.space"},
    {"name": "n8n-engine-3", "url": "https://lbjlincoln-nomos-rag-engine-3.hf.space"},
    {"name": "n8n-engine-5", "url": "https://lbjlincoln-nomos-rag-engine-5.hf.space"},
    {"name": "n8n-engine-7", "url": "https://lbjlincoln-nomos-rag-engine-7.hf.space"},
    {"name": "n8n-engine-9", "url": "https://lbjlincoln-nomos-rag-engine-9.hf.space"},
]

PIPELINES = {
    "standard": {
        "webhook": f"{N8N_HOST}/webhook/rag-multi-index-v3",
        "timeout": 90,
        "test_questions": [
            {"question": "Quelles sont les normes de construction parasismique en France ?"},
            {"question": "What are the main risks in private equity investments?"},
            {"question": "Comment calculer la marge brute d'une entreprise ?"},
        ],
    },
    "graph": {
        "webhook": f"{N8N_HOST}/webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "timeout": 90,
        "test_questions": [
            {"question": "What are the relationships between GDP and inflation?"},
            {"question": "Quels sont les acteurs principaux du BTP en Ile-de-France ?"},
            {"question": "How does machine learning relate to natural language processing?"},
        ],
    },
    "quantitative": {
        "webhook": f"{N8N_HOST}/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "timeout": 120,
        "test_questions": [
            {"question": "What is the revenue of the largest company in the dataset?"},
            {"question": "Quel est le taux de croissance du PIB en 2023 ?"},
            {"question": "What is the average profit margin across all sectors?"},
        ],
    },
}

# SSL context for urllib
SSL_CTX = ssl.create_default_context()


# ---------------------------------------------------------------------------
# Logging (L4)
# ---------------------------------------------------------------------------
def log_event(level: str, event: str, data: dict = None):
    """Append a structured JSON line to the self-heal log."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "event": event,
    }
    if data:
        entry["data"] = data

    # Print to stdout
    summary = f"[{level}] {event}"
    if data and "pipeline" in data:
        summary += f" ({data['pipeline']})"
    print(summary)

    # Append to JSONL
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# L0: Health check all HF Spaces (parallel)
# ---------------------------------------------------------------------------
def check_space_health(space: dict) -> dict:
    """Check a single HF Space health. Returns dict with name, status, latency."""
    url = space["url"]
    t0 = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        resp = urllib.request.urlopen(req, timeout=15, context=SSL_CTX)
        code = resp.getcode()
        latency_ms = int((time.time() - t0) * 1000)
        return {"name": space["name"], "url": url, "status": code, "latency_ms": latency_ms, "ok": 200 <= code < 400}
    except urllib.error.HTTPError as e:
        latency_ms = int((time.time() - t0) * 1000)
        return {"name": space["name"], "url": url, "status": e.code, "latency_ms": latency_ms, "ok": False}
    except Exception as e:
        latency_ms = int((time.time() - t0) * 1000)
        return {"name": space["name"], "url": url, "status": 0, "latency_ms": latency_ms, "ok": False, "error": str(e)[:200]}


def level_0_health_check() -> dict:
    """L0: Parallel health check of all 5 HF Spaces."""
    log_event("L0", "Health check START", {"spaces_count": len(HF_SPACES)})
    results = {}

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(check_space_health, s): s["name"] for s in HF_SPACES}
        for future in as_completed(futures):
            name = futures[future]
            try:
                r = future.result(timeout=20)
                results[name] = r
            except Exception as e:
                results[name] = {"name": name, "ok": False, "error": str(e)[:200]}

    up = sum(1 for r in results.values() if r.get("ok"))
    down = len(results) - up
    log_event("L0", f"Health check DONE: {up}/{len(results)} UP", {
        "up": up, "down": down,
        "details": {k: {"status": v.get("status"), "latency_ms": v.get("latency_ms")} for k, v in results.items()}
    })

    return results


# ---------------------------------------------------------------------------
# L1: Smoke-test pipelines (3 questions each)
# ---------------------------------------------------------------------------
def call_webhook(url: str, payload: dict, timeout: int = 90) -> tuple:
    """POST to webhook, returns (success, response_or_error, latency_ms)."""
    data = json.dumps(payload).encode()
    t0 = time.time()
    try:
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX)
        body = resp.read().decode()
        latency_ms = int((time.time() - t0) * 1000)

        if not body or body.strip() == "":
            return False, "Empty response", latency_ms

        try:
            parsed = json.loads(body)
            # Check for known error patterns
            body_str = json.dumps(parsed).lower()
            if "no item to return" in body_str:
                return False, parsed, latency_ms
            if parsed.get("code") == 0:
                return False, parsed, latency_ms
            if "error" in parsed and isinstance(parsed["error"], str):
                return False, parsed, latency_ms
            return True, parsed, latency_ms
        except json.JSONDecodeError:
            return bool(body.strip()), body[:300], latency_ms

    except urllib.error.HTTPError as e:
        latency_ms = int((time.time() - t0) * 1000)
        try:
            err_body = e.read().decode()[:300]
        except Exception:
            err_body = ""
        return False, f"HTTP {e.code}: {err_body}", latency_ms
    except Exception as e:
        latency_ms = int((time.time() - t0) * 1000)
        return False, str(e)[:300], latency_ms


def level_1_smoke_test() -> dict:
    """L1: Run 3 sector questions per pipeline (9 total). Returns per-pipeline results."""
    log_event("L1", "Smoke test START", {"pipelines": list(PIPELINES.keys())})
    results = {}

    for name, config in PIPELINES.items():
        pipeline_pass = 0
        pipeline_fail = 0
        errors = []

        for q in config["test_questions"]:
            success, response, latency = call_webhook(config["webhook"], q, config["timeout"])
            if success:
                pipeline_pass += 1
            else:
                pipeline_fail += 1
                err_str = json.dumps(response) if isinstance(response, dict) else str(response)
                errors.append({"question": q["question"][:80], "error": err_str[:300], "latency_ms": latency})

        total = pipeline_pass + pipeline_fail
        results[name] = {
            "pass": pipeline_pass,
            "fail": pipeline_fail,
            "total": total,
            "ok": pipeline_fail == 0,
            "errors": errors,
        }

        status = "PASS" if pipeline_fail == 0 else f"FAIL ({pipeline_fail}/{total})"
        log_event("L1", f"{name}: {status}", {
            "pipeline": name, "pass": pipeline_pass, "fail": pipeline_fail,
        })

    total_pass = sum(r["pass"] for r in results.values())
    total_fail = sum(r["fail"] for r in results.values())
    log_event("L1", f"Smoke test DONE: {total_pass}/{total_pass + total_fail} passed", {
        "total_pass": total_pass, "total_fail": total_fail,
    })

    return results


# ---------------------------------------------------------------------------
# L2: Match failures against fixes-structured.json
# ---------------------------------------------------------------------------
def load_fixes() -> list:
    """Load structured fixes from JSON file."""
    if not FIXES_FILE.exists():
        log_event("L2", f"WARNING: {FIXES_FILE} not found")
        return []
    with open(FIXES_FILE, "r") as f:
        return json.load(f)


def match_fix(error_text: str, pipeline: str, fixes: list) -> list:
    """Match an error against structured fixes. Returns list of matching fixes sorted by confidence."""
    matches = []
    error_lower = error_text.lower()

    for fix in fixes:
        # Check pipeline match (fix applies to this pipeline or 'all')
        fix_pipeline = fix.get("pipeline", "all")
        if fix_pipeline != "all" and fix_pipeline != pipeline:
            continue

        # Check symptom regex match
        pattern = fix.get("symptom_regex", "")
        if not pattern:
            continue

        try:
            if re.search(pattern, error_text, re.IGNORECASE):
                matches.append(fix)
        except re.error:
            # Invalid regex in fix definition — try plain substring
            if pattern.lower() in error_lower:
                matches.append(fix)

    # Sort by confidence descending
    matches.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    return matches


def level_2_diagnose(smoke_results: dict) -> dict:
    """L2: For each failed pipeline, match errors against fixes-structured.json."""
    fixes = load_fixes()
    if not fixes:
        log_event("L2", "No fixes loaded — skipping diagnosis")
        return {}

    log_event("L2", "Diagnosis START", {"fixes_loaded": len(fixes)})
    diagnoses = {}

    for pipeline, result in smoke_results.items():
        if result["ok"]:
            continue

        # Concatenate all error texts for matching
        all_errors = " ".join(e["error"] for e in result.get("errors", []))
        matched = match_fix(all_errors, pipeline, fixes)

        if matched:
            top = matched[0]
            log_event("L2", f"{pipeline}: matched {top['fix_id']} ({top['title']})", {
                "pipeline": pipeline,
                "fix_id": top["fix_id"],
                "severity": top["severity"],
                "confidence": top["confidence"],
                "action_type": top["action_type"],
                "total_matches": len(matched),
            })
        else:
            log_event("L2", f"{pipeline}: NO MATCH in fixes database", {
                "pipeline": pipeline,
                "error_preview": all_errors[:200],
            })

        diagnoses[pipeline] = {
            "matched_fixes": matched,
            "error_text": all_errors[:500],
        }

    return diagnoses


# ---------------------------------------------------------------------------
# L3: Apply auto-fixable fixes (P0-P1 only)
# ---------------------------------------------------------------------------
def restart_hf_space(space_url: str) -> bool:
    """Restart an HF Space by hitting its /restart endpoint (requires HF token)."""
    hf_token = os.environ.get("HF_TOKEN", "")
    if not hf_token:
        log_event("L3", "Cannot restart space — HF_TOKEN not set")
        return False

    # Extract space id from URL: https://lbjlincoln-nomos-rag-engine.hf.space -> lbjlincoln/nomos-rag-engine
    import re as re_mod
    m = re_mod.search(r"https://([^.]+)\.hf\.space", space_url)
    if not m:
        log_event("L3", f"Cannot parse space URL: {space_url}")
        return False

    slug = m.group(1).replace("-", "/", 1)  # lbjlincoln-nomos-rag-engine -> lbjlincoln/nomos-rag-engine
    api_url = f"https://huggingface.co/api/spaces/{slug}/restart"

    try:
        req = urllib.request.Request(api_url, method="POST", headers={"Authorization": f"Bearer {hf_token}"})
        resp = urllib.request.urlopen(req, timeout=30, context=SSL_CTX)
        log_event("L3", f"Space restart triggered: {slug}", {"status": resp.getcode()})
        return True
    except Exception as e:
        log_event("L3", f"Space restart failed: {slug}", {"error": str(e)[:200]})
        return False


def apply_fix(fix: dict, pipeline: str) -> dict:
    """Apply a single fix. Returns result dict."""
    fix_id = fix["fix_id"]
    action = fix["action_type"]
    severity = fix["severity"]

    # Only auto-apply P0-P1
    if severity not in ("P0", "P1"):
        log_event("L3", f"Skip {fix_id} ({severity}) — auto-fix only for P0/P1", {"pipeline": pipeline})
        return {"fix_id": fix_id, "applied": False, "reason": f"Severity {severity} requires manual intervention"}

    log_event("L3", f"Applying {fix_id}: {fix['title']}", {
        "pipeline": pipeline, "action": action, "severity": severity,
    })

    if action == "restart_space":
        ok = restart_hf_space(N8N_HOST)
        if ok:
            log_event("L3", f"{fix_id}: Space restart triggered — waiting 60s for startup")
            time.sleep(60)
        return {"fix_id": fix_id, "applied": ok, "action": "restart_space"}

    elif action == "switch_model":
        # Model switching requires workflow PATCH — delegate to Claude Code
        log_event("L3", f"{fix_id}: Model switch requires Claude Code CLI", {"pipeline": pipeline})
        return {"fix_id": fix_id, "applied": False, "reason": "Model switch needs Claude Code CLI intervention"}

    elif action == "patch_workflow":
        # Workflow patching is complex — delegate to Claude Code
        log_event("L3", f"{fix_id}: Workflow patch requires Claude Code CLI", {"pipeline": pipeline})
        return {"fix_id": fix_id, "applied": False, "reason": "Workflow patch needs Claude Code CLI intervention"}

    elif action == "rotate_key":
        log_event("L3", f"{fix_id}: Key rotation requires manual action", {"pipeline": pipeline})
        return {"fix_id": fix_id, "applied": False, "reason": "Key rotation requires manual action"}

    else:
        log_event("L3", f"{fix_id}: Unknown action type '{action}'", {"pipeline": pipeline})
        return {"fix_id": fix_id, "applied": False, "reason": f"Unknown action: {action}"}


def level_3_auto_fix(diagnoses: dict) -> dict:
    """L3: Apply auto-fixable fixes (P0-P1 only)."""
    if not diagnoses:
        return {}

    log_event("L3", "Auto-fix START", {"pipelines_to_fix": list(diagnoses.keys())})
    results = {}

    for pipeline, diag in diagnoses.items():
        matched = diag.get("matched_fixes", [])
        if not matched:
            continue

        # Try the highest-confidence fix first
        top_fix = matched[0]
        fix_result = apply_fix(top_fix, pipeline)
        results[pipeline] = fix_result

        # If fix was applied, re-test the pipeline
        if fix_result.get("applied"):
            config = PIPELINES.get(pipeline)
            if config:
                log_event("L3", f"Re-testing {pipeline} after {top_fix['fix_id']}")
                success, response, latency = call_webhook(
                    config["webhook"], config["test_questions"][0], config["timeout"]
                )
                healed = success
                fix_result["healed"] = healed
                fix_result["retest_latency_ms"] = latency
                status = "HEALED" if healed else "STILL BROKEN"
                log_event("L3", f"{pipeline}: {status} after {top_fix['fix_id']}", {
                    "pipeline": pipeline, "healed": healed, "latency_ms": latency,
                })

    applied_count = sum(1 for r in results.values() if r.get("applied"))
    healed_count = sum(1 for r in results.values() if r.get("healed"))
    log_event("L3", f"Auto-fix DONE: {applied_count} applied, {healed_count} healed", {
        "applied": applied_count, "healed": healed_count,
    })

    return results


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------
def run_smoke(args=None):
    """Quick mode: L0 + L1 only (designed for cron every 15 min)."""
    log_event("CYCLE", "=== SMOKE CYCLE START ===")
    t0 = time.time()

    # L0: Health check
    health = level_0_health_check()
    spaces_up = sum(1 for r in health.values() if r.get("ok"))

    if spaces_up == 0:
        log_event("CYCLE", "ALL SPACES DOWN — skipping smoke test")
        log_event("CYCLE", f"=== SMOKE CYCLE END ({int(time.time()-t0)}s) ===")
        return {"health": health, "smoke": None, "status": "ALL_DOWN"}

    # L1: Smoke test
    smoke = level_1_smoke_test()
    total_pass = sum(r["pass"] for r in smoke.values())
    total_fail = sum(r["fail"] for r in smoke.values())

    status = "ALL_PASS" if total_fail == 0 else "DEGRADED"
    log_event("CYCLE", f"=== SMOKE CYCLE END: {status} ({int(time.time()-t0)}s) ===", {
        "spaces_up": spaces_up,
        "questions_pass": total_pass,
        "questions_fail": total_fail,
    })

    return {"health": health, "smoke": smoke, "status": status}


def run_full(args=None):
    """Full mode: L0 through L4."""
    log_event("CYCLE", "=== FULL CYCLE START ===")
    t0 = time.time()

    # L0: Health check
    health = level_0_health_check()
    spaces_up = sum(1 for r in health.values() if r.get("ok"))

    if spaces_up == 0:
        log_event("CYCLE", "ALL SPACES DOWN — attempting restart of primary")
        restart_hf_space(N8N_HOST)
        time.sleep(60)
        health = level_0_health_check()
        spaces_up = sum(1 for r in health.values() if r.get("ok"))
        if spaces_up == 0:
            log_event("CYCLE", "ALL SPACES STILL DOWN after restart — aborting")
            log_event("CYCLE", f"=== FULL CYCLE END: CRITICAL ({int(time.time()-t0)}s) ===")
            return {"status": "CRITICAL", "health": health}

    # L1: Smoke test
    smoke = level_1_smoke_test()
    total_fail = sum(r["fail"] for r in smoke.values())

    if total_fail == 0:
        log_event("CYCLE", f"=== FULL CYCLE END: ALL_PASS ({int(time.time()-t0)}s) ===")
        return {"status": "ALL_PASS", "health": health, "smoke": smoke}

    # L2: Diagnose
    diagnoses = level_2_diagnose(smoke)

    # L3: Auto-fix
    fixes_applied = level_3_auto_fix(diagnoses)

    # Final status
    healed = sum(1 for r in fixes_applied.values() if r.get("healed"))
    still_broken = total_fail - healed
    status = "HEALED" if still_broken == 0 else "DEGRADED"

    log_event("CYCLE", f"=== FULL CYCLE END: {status} ({int(time.time()-t0)}s) ===", {
        "spaces_up": spaces_up,
        "total_fail": total_fail,
        "fixes_applied": len(fixes_applied),
        "healed": healed,
        "still_broken": still_broken,
    })

    return {
        "status": status,
        "health": health,
        "smoke": smoke,
        "diagnoses": {k: {"matched_fix": v["matched_fixes"][0]["fix_id"] if v.get("matched_fixes") else None} for k, v in diagnoses.items()},
        "fixes": fixes_applied,
    }


def main():
    parser = argparse.ArgumentParser(description="Self-Healing Pipeline Orchestrator v2.0")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--smoke", action="store_true", help="Quick: L0 health + L1 smoke (for cron)")
    group.add_argument("--full", action="store_true", help="Full: L0 through L4 (diagnose + auto-fix)")
    group.add_argument("--loop", type=int, metavar="MINUTES", help="Full cycle every N minutes")
    args = parser.parse_args()

    if args.smoke:
        result = run_smoke()
        print(json.dumps({"summary": result.get("status", "UNKNOWN")}, indent=2))

    elif args.full:
        result = run_full()
        print(json.dumps({"summary": result.get("status", "UNKNOWN")}, indent=2))

    elif args.loop:
        interval = max(5, args.loop)
        log_event("LOOP", f"Starting self-heal loop (interval: {interval}min)")
        while True:
            try:
                run_full()
            except KeyboardInterrupt:
                log_event("LOOP", "Interrupted by user")
                break
            except Exception as e:
                log_event("LOOP", f"Cycle error: {e}")
            time.sleep(interval * 60)


if __name__ == "__main__":
    main()
