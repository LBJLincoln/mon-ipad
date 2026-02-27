#!/usr/bin/env python3
"""
Auto-Model-Swap — Automatically swap rate-limited LLM models in n8n workflow JSONs.

Tests each model on OpenRouter and swaps 429'd models to working alternatives.
Modifies workflow JSONs in hf-space/n8n-workflows/ then can push via sync.

Usage:
    python3 scripts/auto-model-swap.py --check          # Just test models, no changes
    python3 scripts/auto-model-swap.py --swap            # Test + swap rate-limited models
    python3 scripts/auto-model-swap.py --swap --dry-run  # Show what would change
    python3 scripts/auto-model-swap.py --restore-golden  # Restore golden model config
"""

import os
import sys
import json
import time
import argparse
import re
from pathlib import Path
from datetime import datetime

# --- Configuration ---

WORKFLOWS_DIR = Path(__file__).parent.parent / "hf-space" / "n8n-workflows"
BACKUP_DIR = Path(__file__).parent.parent / "snapshot" / "model-swap-backups"

# Models currently used in golden workflows (22 Feb baseline)
GOLDEN_MODELS = {
    "standard": ["arcee-ai/trinity-large-preview:free"],
    "graph": ["arcee-ai/trinity-large-preview:free", "google/gemini-2.0-flash-exp"],
    "quantitative": [
        "arcee-ai/trinity-large-preview:free",
        "mistralai/mistral-small-3.1-24b-instruct:free",
        "stepfun/step-3.5-flash:free",
    ],
    "orchestrator": [
        "meta-llama/llama-3.3-70b-instruct:free",
        "mistralai/mistral-small-3.1-24b-instruct:free",
        "google/gemma-3-27b-it:free",
        "stepfun/step-3.5-flash:free",
    ],
}

# Fallback chain: if model A is 429'd, try B, then C, etc.
# Priority: proven performers first (Trinity had best Phase2 results)
FALLBACK_CHAIN = [
    "arcee-ai/trinity-large-preview:free",           # BEST — works for Standard, Graph, Quant
    "google/gemini-2.0-flash-exp",                    # Good — works for Graph
    "mistralai/mistral-small-3.1-24b-instruct:free",  # Good — worked for Quant Phase2
    "stepfun/step-3.5-flash:free",                    # OK — worked for Quant interpretation
    "meta-llama/llama-3.3-70b-instruct:free",         # OK — worked for Orch Phase1
    "google/gemma-3-27b-it:free",                     # OK — worked for Orch lite
    "qwen/qwen-2.5-72b-instruct:free",               # Backup — large context
    "deepseek/deepseek-chat-v3-0324:free",            # Backup — good reasoning
    "microsoft/phi-4:free",                           # Backup — small but capable
]

# Workflow files → pipeline mapping
WORKFLOW_FILES = {
    "standard.json": "standard",
    "graph.json": "graph",
    "quantitative.json": "quantitative",
    "orchestrator-v10.json": "orchestrator",
}


def get_openrouter_keys():
    """Get all available OpenRouter API keys from environment."""
    keys = {}
    for var in [
        "OPENROUTER_API_KEY",
        "OPENROUTER_KEY_STANDARD",
        "OPENROUTER_KEY_GRAPH",
        "OPENROUTER_KEY_QUANTITATIVE",
        "OPENROUTER_KEY_ORCHESTRATOR",
        "OPENROUTER_KEY_PME",
        "OPENROUTER_KEY_SPARE",
    ]:
        val = os.environ.get(var)
        if val and len(val) > 10:
            keys[var] = val
    return keys


def test_model(model_id, api_key, timeout=15):
    """Test if a model responds on OpenRouter. Returns (ok, latency_ms, error)."""
    import urllib.request
    import urllib.error

    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": "Say OK"}],
        "max_tokens": 5,
        "temperature": 0,
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
            latency = int((time.time() - start) * 1000)
            content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                return True, latency, None
            return False, latency, "Empty response content"
    except urllib.error.HTTPError as e:
        latency = int((time.time() - start) * 1000)
        try:
            error_body = json.loads(e.read())
            msg = error_body.get("error", {}).get("message", str(e))
        except Exception:
            msg = str(e)
        return False, latency, f"HTTP {e.code}: {msg}"
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        return False, latency, str(e)


def test_all_models(api_keys):
    """Test all models in FALLBACK_CHAIN. Returns {model: {ok, latency, error, key_used}}."""
    # Use the first available key for testing
    test_key = list(api_keys.values())[0] if api_keys else None
    if not test_key:
        print("ERROR: No OpenRouter API key found in environment")
        sys.exit(1)

    results = {}
    # Collect unique models from all workflows + fallback chain
    all_models = set()
    for models in GOLDEN_MODELS.values():
        all_models.update(models)
    all_models.update(FALLBACK_CHAIN)

    print(f"\nTesting {len(all_models)} models on OpenRouter...\n")
    for model in sorted(all_models):
        ok, latency, error = test_model(model, test_key)
        status = "OK" if ok else "FAIL"
        err_short = ""
        if error:
            if "429" in str(error):
                err_short = "429 RATE-LIMITED"
            elif "401" in str(error):
                err_short = "401 AUTH"
            elif "404" in str(error):
                err_short = "404 NOT FOUND"
            else:
                err_short = error[:60]
        print(f"  {'OK' if ok else 'XX'}  {model:55s}  {latency:5d}ms  {err_short}")
        results[model] = {"ok": ok, "latency": latency, "error": error}
        time.sleep(0.5)  # Rate-limit courtesy

    return results


def find_best_replacement(current_model, model_results):
    """Find the best working replacement model from the fallback chain."""
    for candidate in FALLBACK_CHAIN:
        if candidate == current_model:
            continue
        result = model_results.get(candidate, {})
        if result.get("ok"):
            return candidate
    return None


def extract_models_from_workflow(workflow_json):
    """Extract all model references from a workflow JSON string."""
    # Pattern 1: 'model': 'xxx' or "model": "xxx" in Code nodes
    pattern1 = r"""model['"]\s*:\s*['"]([a-zA-Z0-9\-_/.:]+:free)['"]"""
    # Pattern 2: "model": "xxx" in HTTP Request jsonBody
    pattern2 = r'''"model"\s*:\s*"([a-zA-Z0-9\-_/.:]+:free)"'''
    # Pattern 3: {{ model-id || 'fallback' }} in n8n expressions
    pattern3 = r"""(?:{{|\|\|)\s*['\"]?([a-zA-Z0-9\-_/.:]+:free)['\"]?\s*(?:}}|\|\|)"""
    # Pattern 4: bare model refs like: meta-llama/llama-3.3-70b-instruct:free || 'fallback'
    pattern4 = r"""(?<![a-zA-Z])([a-zA-Z0-9\-_]+/[a-zA-Z0-9\-_.:]+:free)(?![a-zA-Z])"""

    models = set()
    for pattern in [pattern1, pattern2, pattern3, pattern4]:
        models.update(re.findall(pattern, workflow_json))
    return models


def swap_model_in_workflow(workflow_json, old_model, new_model):
    """Replace all occurrences of old_model with new_model in a workflow JSON string."""
    count = workflow_json.count(old_model)
    if count == 0:
        return workflow_json, 0
    new_json = workflow_json.replace(old_model, new_model)
    return new_json, count


def backup_workflow(filepath):
    """Create a timestamped backup of a workflow JSON."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{filepath.stem}-{timestamp}.json"
    backup_path = BACKUP_DIR / backup_name
    import shutil
    shutil.copy2(filepath, backup_path)
    return backup_path


def run_check(args):
    """Check mode: test all models and report status."""
    api_keys = get_openrouter_keys()
    print(f"Found {len(api_keys)} OpenRouter API keys")

    results = test_all_models(api_keys)

    # Show per-pipeline impact
    print("\n--- Per-Pipeline Model Status ---\n")
    for pipeline, models in GOLDEN_MODELS.items():
        all_ok = True
        for model in models:
            r = results.get(model, {})
            status = "OK" if r.get("ok") else "RATE-LIMITED"
            if not r.get("ok"):
                all_ok = False
                replacement = find_best_replacement(model, results)
                rep_str = f" → swap to {replacement}" if replacement else " → NO REPLACEMENT AVAILABLE"
            else:
                rep_str = ""
            print(f"  {pipeline:15s}  {model:55s}  {status}{rep_str}")
        pipeline_status = "ALL OK" if all_ok else "NEEDS SWAP"
        print(f"  {'':15s}  Pipeline status: {pipeline_status}\n")

    # Summary
    working = [m for m, r in results.items() if r.get("ok")]
    broken = [m for m, r in results.items() if not r.get("ok")]
    print(f"\nSummary: {len(working)} working, {len(broken)} rate-limited/broken")
    if working:
        print(f"  Working: {', '.join(working)}")
    if broken:
        print(f"  Broken:  {', '.join(broken)}")

    return results


def run_swap(args):
    """Swap mode: replace rate-limited models with working alternatives."""
    api_keys = get_openrouter_keys()
    results = test_all_models(api_keys)

    swaps_needed = []
    for wf_file, pipeline in WORKFLOW_FILES.items():
        filepath = WORKFLOWS_DIR / wf_file
        if not filepath.exists():
            print(f"  SKIP {wf_file} — not found")
            continue

        content = filepath.read_text()
        models_in_wf = extract_models_from_workflow(content)

        for model in models_in_wf:
            r = results.get(model, {})
            if not r.get("ok"):
                replacement = find_best_replacement(model, results)
                if replacement:
                    swaps_needed.append({
                        "file": wf_file,
                        "pipeline": pipeline,
                        "old_model": model,
                        "new_model": replacement,
                    })

    if not swaps_needed:
        print("\nNo swaps needed — all models are working.")
        return

    print(f"\n--- {len(swaps_needed)} swaps needed ---\n")
    for s in swaps_needed:
        print(f"  {s['pipeline']:15s}  {s['old_model']}  →  {s['new_model']}")

    if args.dry_run:
        print("\n  (dry-run mode — no files modified)")
        return

    # Apply swaps
    print("\nApplying swaps...")
    modified_files = set()
    for s in swaps_needed:
        filepath = WORKFLOWS_DIR / s["file"]
        if filepath not in modified_files:
            backup = backup_workflow(filepath)
            print(f"  Backup: {backup}")
            modified_files.add(filepath)

        content = filepath.read_text()
        new_content, count = swap_model_in_workflow(content, s["old_model"], s["new_model"])
        filepath.write_text(new_content)
        print(f"  {s['file']}: {s['old_model']} → {s['new_model']} ({count} occurrences)")

    print(f"\n{len(modified_files)} workflow files modified.")
    print("Next steps:")
    print("  1. python3 n8n/sync.py  — push to HF Space")
    print("  2. python3 eval/quick-test.py --questions 5  — validate")
    print("  3. python3 eval/golden-check.py --all  — check thresholds")


def run_restore_golden(args):
    """Restore golden model configuration from GOLDEN_MODELS."""
    print("Restoring golden model configuration...")
    print("  (This restores the models used during the best Phase 2 results)\n")

    # For each workflow, check if current models match golden
    for wf_file, pipeline in WORKFLOW_FILES.items():
        filepath = WORKFLOWS_DIR / wf_file
        if not filepath.exists():
            print(f"  SKIP {wf_file} — not found")
            continue

        content = filepath.read_text()
        models_in_wf = extract_models_from_workflow(content)
        golden = set(GOLDEN_MODELS.get(pipeline, []))

        non_golden = models_in_wf - golden
        if not non_golden:
            print(f"  {pipeline:15s}  Already at golden config")
            continue

        print(f"  {pipeline:15s}  Non-golden models found: {non_golden}")
        if args.dry_run:
            print(f"  {'':15s}  (dry-run — no changes)")
            continue

        # We can't easily restore without knowing what each non-golden model should revert to
        # Instead, we restore from backups if available
        backups = sorted(BACKUP_DIR.glob(f"{filepath.stem}-*.json"), reverse=True)
        if backups:
            print(f"  {'':15s}  Restoring from backup: {backups[0].name}")
            import shutil
            shutil.copy2(backups[0], filepath)
        else:
            print(f"  {'':15s}  No backup found — manual restore needed")


def main():
    parser = argparse.ArgumentParser(description="Auto-Model-Swap for n8n workflows")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Test all models, no changes")
    group.add_argument("--swap", action="store_true", help="Test and swap rate-limited models")
    group.add_argument("--restore-golden", action="store_true", help="Restore golden model config")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change")

    args = parser.parse_args()

    if args.check:
        run_check(args)
    elif args.swap:
        run_swap(args)
    elif args.restore_golden:
        run_restore_golden(args)


if __name__ == "__main__":
    main()
