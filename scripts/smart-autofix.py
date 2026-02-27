#!/usr/bin/env python3
"""
Smart Autofix — Golden-based intelligent pipeline repair.
=========================================================
Automatically detects pipeline failures, finds the best golden snapshot,
and applies it to restore service. Uses historical accuracy data and
timestamps to score candidates.

Features:
  - Detect problems via webhook health checks
  - Find best golden snapshot by score (accuracy × recency × model match)
  - Apply golden via n8n REST API
  - Re-test with quick-test.py
  - Log to Supabase + JSONL
  - Fallback to next best golden if first fails
  - Dry-run mode for safety

Usage:
    source .env.local && python3 scripts/smart-autofix.py --pipeline standard
    source .env.local && python3 scripts/smart-autofix.py --all
    source .env.local && python3 scripts/smart-autofix.py --all --dry-run
    source .env.local && python3 scripts/smart-autofix.py --pipeline graph --max-attempts 3

Exit codes:
    0 = All pipelines fixed successfully
    1 = Some pipelines failed to fix
    2 = All pipelines failed to fix
"""

import argparse
import glob
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib import request, error
from http.cookiejar import CookieJar

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
SNAPSHOT_DIR = REPO_ROOT / "snapshot"
WORKFLOW_DIR = REPO_ROOT / "hf-space" / "n8n-workflows"
LOGS_DIR = REPO_ROOT / "logs"
AUTOFIX_LOG = LOGS_DIR / "smart-autofix.jsonl"
DATA_JSON = REPO_ROOT / "docs" / "data.json"
ENV_FILE = REPO_ROOT / ".env.local"

LOGS_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Load .env.local
# ---------------------------------------------------------------------------
def load_env():
    """Load environment variables from .env.local."""
    if not ENV_FILE.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE)
    except ImportError:
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:]
                if "=" in line:
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip()
                    if val and val[0] in ('"', "'") and val[-1] == val[0]:
                        val = val[1:-1]
                    if "${" not in val:
                        os.environ.setdefault(key, val)

load_env()

# ---------------------------------------------------------------------------
# Pipeline config (from auto-revert.py)
# ---------------------------------------------------------------------------
PIPELINES = {
    "standard": {
        "workflow_patterns": ["standard", "wf5"],
        "golden_filename": "standard.json",
        "test_query": "What is the capital of Japan?",
    },
    "graph": {
        "workflow_patterns": ["graph", "wf2"],
        "golden_filename": "graph.json",
        "test_query": "What did Marie Curie win Nobel Prizes for?",
    },
    "quantitative": {
        "workflow_patterns": ["quantitative", "wf4"],
        "golden_filename": "quantitative.json",
        "test_query": "What was TechVision Inc's total revenue in 2023?",
    },
    "orchestrator": {
        "workflow_patterns": ["orchestrator"],
        "golden_filename": "orchestrator-v10.json",
        "test_query": "What is the largest ocean?",
    },
}

LOGIN_EMAIL = "ci@nomos.ai"
LOGIN_PASSWORD = "CI-Nomos-2026!"

# ---------------------------------------------------------------------------
# ANSI colors
# ---------------------------------------------------------------------------
class C:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    END = "\033[0m"

def _now() -> str:
    """ISO timestamp with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _days_since(timestamp_str: str) -> float:
    """Calculate days since a timestamp string (ISO format)."""
    try:
        # Handle various formats: YYYY-MM-DD, YYYYMMDD, YYYY-MM-DDTHH:MM:SS, etc.
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - ts
        return delta.total_seconds() / 86400
    except Exception:
        return 999.0  # Very old if we can't parse

# ---------------------------------------------------------------------------
# N8n Client (minimal, for API access)
# ---------------------------------------------------------------------------
class N8nClient:
    """Lightweight n8n API client using urllib.request."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.cookie_jar = CookieJar()
        self.opener = request.build_opener(
            request.HTTPCookieProcessor(self.cookie_jar)
        )
        self.logged_in = False

    def _request(self, method: str, path: str, data=None, timeout=30):
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        body = json.dumps(data).encode("utf-8") if data else None
        req = request.Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if isinstance(result, dict) and "data" in result:
                    return result["data"]
                return result
        except error.HTTPError as e:
            error_body = e.read().decode("utf-8")[:300]
            raise Exception(f"HTTP {e.code}: {error_body}")

    def login(self) -> bool:
        try:
            self._request("POST", "/rest/login", {
                "emailOrLdapLoginId": LOGIN_EMAIL,
                "password": LOGIN_PASSWORD,
            })
            self.logged_in = True
            return True
        except Exception as e:
            print(f"  {C.RED}Login failed: {e}{C.END}")
            return False

    def get_workflows(self) -> List[dict]:
        return self._request("GET", "/rest/workflows")

    def get_workflow(self, wf_id: str) -> dict:
        return self._request("GET", f"/rest/workflows/{wf_id}")

    def update_workflow(self, wf_id: str, data: dict) -> dict:
        return self._request("PATCH", f"/rest/workflows/{wf_id}", data)

    def activate_workflow(self, wf_id: str, version_id: str) -> dict:
        return self._request("POST", f"/rest/workflows/{wf_id}/activate",
                             {"versionId": version_id})

    def deactivate_workflow(self, wf_id: str) -> dict:
        return self._request("PATCH", f"/rest/workflows/{wf_id}", {"active": False})

# ---------------------------------------------------------------------------
# Webhook health detection (from webhook-health-monitor.py)
# ---------------------------------------------------------------------------
def check_pipeline_health(n8n_host: str, pipeline: str) -> dict:
    """Quick health check for a single pipeline.

    Returns:
        {
            "pipeline": str,
            "healthy": bool,
            "error_type": "429" | "404" | "timeout" | "empty" | "auth" | None,
            "http_code": int | None,
            "latency_ms": int,
            "error": str | None,
        }
    """
    config = PIPELINES.get(pipeline, {})
    if not config:
        return {"pipeline": pipeline, "healthy": False, "error_type": "unknown", "error": "Unknown pipeline"}

    # Map config to webhook format
    webhook_path = {
        "standard": "/webhook/rag-multi-index-v3",
        "graph": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "orchestrator": "/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
    }.get(pipeline, "")

    url = n8n_host.rstrip("/") + webhook_path
    payload = json.dumps({
        "query": config.get("test_query", "Test"),
        "sessionId": f"autofix-health-{int(time.time())}",
    }).encode("utf-8")

    result = {
        "pipeline": pipeline,
        "healthy": False,
        "error_type": None,
        "http_code": None,
        "latency_ms": 0,
        "error": None,
    }

    try:
        req = request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        start = time.time()
        with request.urlopen(req, timeout=90) as resp:
            latency_ms = int((time.time() - start) * 1000)
            result["http_code"] = resp.status
            result["latency_ms"] = latency_ms
            raw = resp.read().decode("utf-8")

            if not raw or len(raw.strip()) < 5:
                result["error_type"] = "empty"
                result["error"] = "Empty or very short response"
            else:
                result["healthy"] = True

    except error.HTTPError as e:
        result["http_code"] = e.code
        result["latency_ms"] = int((time.time() - start) * 1000) if 'start' in locals() else 0
        err_body = e.read().decode("utf-8")[:200] if hasattr(e, 'read') else str(e)
        result["error"] = f"HTTP {e.code}: {err_body}"

        if e.code == 404:
            result["error_type"] = "404"
        elif e.code == 429:
            result["error_type"] = "429"
        elif e.code == 401 or e.code == 403:
            result["error_type"] = "auth"
        else:
            result["error_type"] = "http_error"

    except Exception as e:
        err_str = str(e)
        if "timed out" in err_str.lower() or "timeout" in err_str.lower():
            result["error_type"] = "timeout"
            result["error"] = "Request timeout"
        else:
            result["error_type"] = "network"
            result["error"] = err_str[:200]

    return result

# ---------------------------------------------------------------------------
# Historical accuracy loading (from docs/data.json or Supabase)
# ---------------------------------------------------------------------------
def get_historical_accuracy(pipeline: str) -> float:
    """Get the best historical accuracy for a pipeline.

    Priority:
      1. docs/data.json (latest trend value)
      2. Supabase benchmark_results (if available)
      3. Default 0.0
    """
    # Try data.json first
    if DATA_JSON.exists():
        try:
            with open(DATA_JSON) as f:
                data = json.load(f)
            pipe_data = data.get("pipelines", {}).get(pipeline, {})

            # Try accuracy_trend array
            trends = pipe_data.get("accuracy_trend", [])
            if trends:
                return max(trends)

            # Try direct accuracy field
            if "accuracy" in pipe_data:
                return pipe_data["accuracy"]
        except Exception:
            pass

    # Try Supabase (best-effort)
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_API_KEY", "")
    if supabase_url and supabase_key:
        try:
            api_url = f"{supabase_url}/rest/v1/benchmark_results"
            params = f"dataset_name=eq.{pipeline}&select=metrics&order=created_at.desc&limit=100"
            req = request.Request(
                f"{api_url}?{params}",
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                }
            )
            with request.urlopen(req, timeout=10) as resp:
                results = json.loads(resp.read().decode("utf-8"))
                if results:
                    accuracies = [r.get("metrics", {}).get("accuracy", 0) for r in results]
                    if accuracies:
                        return max(accuracies)
        except Exception:
            pass

    return 0.0

# ---------------------------------------------------------------------------
# Golden snapshot discovery and scoring
# ---------------------------------------------------------------------------
def find_all_golden_snapshots(pipeline: str) -> List[dict]:
    """Find all golden workflow JSONs for a pipeline across all snapshot directories.

    Returns:
        [
            {
                "path": Path,
                "timestamp": str,  # extracted from directory name or file mtime
                "model": str | None,  # extracted from workflow JSON if possible
            }
        ]
    """
    config = PIPELINES.get(pipeline, {})
    if not config:
        return []

    filename = config["golden_filename"]
    candidates = []

    # Search all snapshot directories
    search_dirs = [
        SNAPSHOT_DIR / "current",
        SNAPSHOT_DIR / "auto-backup",
        SNAPSHOT_DIR / "model-swap-backups",
    ]

    # Add all working-session* directories
    search_dirs.extend(sorted(SNAPSHOT_DIR.glob("working-session*"), reverse=True))

    # Also check main workflow directory
    search_dirs.append(WORKFLOW_DIR)

    for dir_path in search_dirs:
        if not dir_path.exists():
            continue

        # Try exact filename first
        candidate = dir_path / filename
        if candidate.exists() and candidate.is_file():
            candidates.append(candidate)

        # Also try pattern matching (e.g., "standard*.json")
        for pattern in config["workflow_patterns"]:
            for match in dir_path.glob(f"{pattern}*.json"):
                if match.is_file() and match not in candidates:
                    candidates.append(match)

    # Build result list with metadata
    results = []
    for path in candidates:
        # Extract timestamp
        timestamp = None

        # Try to extract from parent directory name (e.g., "working-session61")
        parent = path.parent.name
        if "session" in parent:
            # Extract number and convert to rough date
            import re
            match = re.search(r'session(\d+)', parent)
            if match:
                session_num = int(match.group(1))
                # Rough estimate: session 60 = 2026-02-25, increment by 1 day per session
                base_date = datetime(2026, 2, 25, tzinfo=timezone.utc)
                days_offset = session_num - 60
                ts = base_date.timestamp() + (days_offset * 86400)
                timestamp = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

        # Try to extract from file name (e.g., "standard-20260225.json")
        if not timestamp:
            import re
            match = re.search(r'(\d{8})', path.name)
            if match:
                date_str = match.group(1)
                try:
                    ts = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
                    timestamp = ts.isoformat()
                except Exception:
                    pass

        # Fallback to file mtime
        if not timestamp:
            mtime = path.stat().st_mtime
            timestamp = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

        # Try to extract model from workflow JSON
        model = None
        try:
            with open(path) as f:
                wf_data = json.load(f)
            # Look for model references in nodes
            for node in wf_data.get("nodes", []):
                params = node.get("parameters", {})
                # Check common parameter keys
                for key in ["model", "modelId", "llm_model"]:
                    if key in params and params[key]:
                        model = str(params[key])
                        break
                if model:
                    break
        except Exception:
            pass

        results.append({
            "path": path,
            "timestamp": timestamp,
            "model": model,
        })

    return results

def score_golden_snapshot(golden: dict, pipeline: str, current_model: Optional[str] = None) -> float:
    """Score a golden snapshot candidate.

    Formula:
        score = accuracy_historical * (1 / max(1, days_since_success)) * (1 if same_model else 0.8)

    Args:
        golden: Dict with path, timestamp, model
        pipeline: Pipeline name
        current_model: Currently broken model (for model match bonus)

    Returns:
        Score as float (higher = better)
    """
    # Get historical accuracy for this pipeline
    accuracy = get_historical_accuracy(pipeline)

    # Calculate recency factor (1 / max(1, days_since))
    days_since = _days_since(golden["timestamp"])
    recency_factor = 1.0 / max(1.0, days_since)

    # Model match bonus (1.0 if match, 0.8 if different)
    model_factor = 1.0
    if current_model and golden["model"]:
        if golden["model"] != current_model:
            model_factor = 0.8

    score = accuracy * recency_factor * model_factor
    return score

def find_best_golden(pipeline: str, current_model: Optional[str] = None) -> Optional[dict]:
    """Find the best golden snapshot for a pipeline.

    Returns:
        {
            "path": Path,
            "timestamp": str,
            "model": str | None,
            "score": float,
        }
        or None if no candidates found.
    """
    candidates = find_all_golden_snapshots(pipeline)
    if not candidates:
        return None

    # Score all candidates
    scored = []
    for golden in candidates:
        score = score_golden_snapshot(golden, pipeline, current_model)
        scored.append({
            **golden,
            "score": score,
        })

    # Sort by score (highest first)
    scored.sort(key=lambda x: x["score"], reverse=True)

    return scored[0] if scored else None

# ---------------------------------------------------------------------------
# Apply golden workflow via n8n REST API (from auto-revert.py)
# ---------------------------------------------------------------------------
def apply_golden_workflow(client: N8nClient, pipeline: str, golden_path: Path) -> dict:
    """Apply a golden workflow to n8n via REST API.

    Returns:
        {
            "success": bool,
            "details": str,
            "workflow_id": str | None,
        }
    """
    config = PIPELINES[pipeline]

    # Load golden workflow
    try:
        with open(golden_path) as f:
            golden_wf = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        return {"success": False, "details": f"Cannot load golden: {e}", "workflow_id": None}

    # Find matching workflow on n8n
    try:
        workflows = client.get_workflows()
    except Exception as e:
        return {"success": False, "details": f"Cannot list workflows: {e}", "workflow_id": None}

    target_wf_id = None
    for wf in workflows:
        name_lower = wf.get("name", "").lower()
        if any(p in name_lower for p in config["workflow_patterns"]):
            target_wf_id = wf["id"]
            break

    if not target_wf_id:
        return {"success": False, "details": f"No matching workflow found for {pipeline}", "workflow_id": None}

    # Apply update
    try:
        # Deactivate first
        client.deactivate_workflow(target_wf_id)
        time.sleep(1)

        # Update with golden nodes and connections
        update_data = {
            "nodes": golden_wf.get("nodes", []),
            "connections": golden_wf.get("connections", {}),
            "settings": golden_wf.get("settings", {}),
        }
        client.update_workflow(target_wf_id, update_data)

        # Re-activate
        updated_wf = client.get_workflow(target_wf_id)
        version_id = updated_wf.get("versionId", "1")
        client.activate_workflow(target_wf_id, version_id)

        return {
            "success": True,
            "details": f"Applied golden and re-activated (versionId={version_id})",
            "workflow_id": target_wf_id,
        }

    except Exception as e:
        return {"success": False, "details": f"Apply failed: {e}", "workflow_id": target_wf_id}

# ---------------------------------------------------------------------------
# Test pipeline with quick-test.py
# ---------------------------------------------------------------------------
def test_pipeline(pipeline: str, num_questions: int = 5) -> dict:
    """Run quick-test.py to validate a pipeline.

    Returns:
        {
            "success": bool,
            "accuracy": float,
            "details": str,
        }
    """
    try:
        quick_test_script = REPO_ROOT / "eval" / "quick-test.py"
        result = subprocess.run(
            ["python3", str(quick_test_script), "--pipeline", pipeline, "--questions", str(num_questions)],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=REPO_ROOT,
        )

        # Parse output for accuracy
        output = result.stdout + result.stderr
        accuracy = 0.0

        # Look for "X/Y correct" or "accuracy: X%"
        import re
        match = re.search(r'(\d+)/(\d+)\s+correct', output, re.IGNORECASE)
        if match:
            correct = int(match.group(1))
            total = int(match.group(2))
            accuracy = (correct / total * 100) if total > 0 else 0.0
        else:
            match = re.search(r'accuracy[:\s]+(\d+(?:\.\d+)?)', output, re.IGNORECASE)
            if match:
                accuracy = float(match.group(1))

        success = result.returncode == 0 and accuracy > 0

        return {
            "success": success,
            "accuracy": accuracy,
            "details": output[:500] if not success else f"Passed with {accuracy:.1f}% accuracy",
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "accuracy": 0.0, "details": "Test timeout"}
    except Exception as e:
        return {"success": False, "accuracy": 0.0, "details": f"Test failed: {e}"}

# ---------------------------------------------------------------------------
# Logging to JSONL and Supabase
# ---------------------------------------------------------------------------
def log_autofix_result(result: dict):
    """Append autofix result to JSONL log."""
    try:
        with open(AUTOFIX_LOG, "a") as f:
            f.write(json.dumps(result) + "\n")
    except (OSError, IOError) as e:
        print(f"  {C.YELLOW}WARN{C.END} Cannot write autofix log: {e}")

def log_to_supabase(result: dict):
    """Log autofix result to Supabase (best-effort, no failure on error)."""
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_API_KEY", "")

    if not supabase_url or not supabase_key:
        return

    try:
        # Log to trading_board_snapshots table
        snapshot_data = {
            "pipeline": result["pipeline"],
            "action": "autofix",
            "snapshot_type": "golden_applied",
            "snapshot_path": str(result.get("golden_path", "")),
            "accuracy_before": result.get("accuracy_before", 0.0),
            "accuracy_after": result.get("accuracy_after", 0.0),
            "status": "success" if result.get("fixed", False) else "failed",
            "details": json.dumps({
                "error_type": result.get("error_type"),
                "attempts": result.get("attempts", 1),
                "golden_score": result.get("golden_score", 0.0),
            }),
            "created_at": _now(),
        }

        api_url = f"{supabase_url}/rest/v1/trading_board_snapshots"
        req = request.Request(
            api_url,
            data=json.dumps(snapshot_data).encode("utf-8"),
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            method="POST",
        )
        request.urlopen(req, timeout=10)

    except Exception:
        pass  # Best-effort, don't fail the whole autofix

# ---------------------------------------------------------------------------
# Main autofix logic
# ---------------------------------------------------------------------------
def autofix_pipeline(
    n8n_client: N8nClient,
    pipeline: str,
    dry_run: bool = True,
    max_attempts: int = 3,
) -> dict:
    """Attempt to autofix a single pipeline.

    Args:
        n8n_client: Authenticated N8nClient
        pipeline: Pipeline name
        dry_run: If True, only show what would happen
        max_attempts: Maximum number of golden snapshots to try

    Returns:
        {
            "pipeline": str,
            "fixed": bool,
            "error_type": str | None,
            "attempts": int,
            "golden_path": str | None,
            "golden_score": float,
            "accuracy_before": float,
            "accuracy_after": float,
            "details": str,
            "timestamp": str,
        }
    """
    result = {
        "pipeline": pipeline,
        "fixed": False,
        "error_type": None,
        "attempts": 0,
        "golden_path": None,
        "golden_score": 0.0,
        "accuracy_before": 0.0,
        "accuracy_after": 0.0,
        "details": "",
        "timestamp": _now(),
    }

    print(f"\n{C.BOLD}[AUTOFIX] {pipeline}{C.END}")

    # Step 1: Detect problem
    print(f"  [1/5] Detecting problem...", end=" ", flush=True)
    n8n_host = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")
    health = check_pipeline_health(n8n_host, pipeline)

    if health["healthy"]:
        result["details"] = "Pipeline is already healthy"
        print(f"{C.GREEN}Healthy{C.END}")
        return result

    result["error_type"] = health["error_type"]
    print(f"{C.RED}{health['error_type']}{C.END} - {health.get('error', '')[:60]}")

    # For 429 rate-limit errors, we need model swap instead of golden revert
    if health["error_type"] == "429":
        result["details"] = "Rate-limit error detected. Use auto-model-swap.py instead."
        print(f"  {C.YELLOW}SKIP{C.END} Rate-limit errors require model swap, not golden revert")
        return result

    # Step 2: Find best golden snapshots
    print(f"  [2/5] Finding golden snapshots...", end=" ", flush=True)
    all_goldens = find_all_golden_snapshots(pipeline)
    if not all_goldens:
        result["details"] = "No golden snapshots found"
        print(f"{C.RED}None found{C.END}")
        return result

    # Score and sort
    scored_goldens = []
    for golden in all_goldens:
        score = score_golden_snapshot(golden, pipeline)
        scored_goldens.append({**golden, "score": score})
    scored_goldens.sort(key=lambda x: x["score"], reverse=True)

    print(f"{C.GREEN}Found {len(scored_goldens)}{C.END} (best score: {scored_goldens[0]['score']:.3f})")

    # Step 3: Try goldens in order until one works
    for attempt_num, golden in enumerate(scored_goldens[:max_attempts], start=1):
        result["attempts"] = attempt_num
        result["golden_path"] = str(golden["path"])
        result["golden_score"] = golden["score"]

        print(f"\n  [3/5] Attempt {attempt_num}/{max_attempts}: {golden['path'].name}")
        print(f"        Score: {golden['score']:.3f} | Model: {golden['model'] or 'unknown'} | Age: {_days_since(golden['timestamp']):.1f} days")

        if dry_run:
            print(f"  {C.CYAN}[DRY-RUN]{C.END} Would apply this golden and test")
            result["details"] = f"Dry-run: would apply {golden['path'].name}"
            result["fixed"] = True  # Assume success in dry-run
            return result

        # Apply golden
        print(f"  [4/5] Applying golden...", end=" ", flush=True)
        apply_result = apply_golden_workflow(n8n_client, pipeline, golden["path"])
        if not apply_result["success"]:
            print(f"{C.RED}Failed{C.END} - {apply_result['details'][:60]}")
            continue
        print(f"{C.GREEN}OK{C.END}")

        # Wait for n8n to stabilize
        time.sleep(3)

        # Test
        print(f"  [5/5] Testing with 5 questions...", end=" ", flush=True)
        test_result = test_pipeline(pipeline, num_questions=5)
        result["accuracy_after"] = test_result["accuracy"]

        if test_result["success"] and test_result["accuracy"] >= 60.0:  # Lowered threshold for quick test
            result["fixed"] = True
            result["details"] = f"Fixed with {golden['path'].name} (accuracy: {test_result['accuracy']:.1f}%)"
            print(f"{C.GREEN}PASS{C.END} ({test_result['accuracy']:.1f}%)")
            return result
        else:
            print(f"{C.YELLOW}FAIL{C.END} ({test_result['accuracy']:.1f}%)")

    # All attempts exhausted
    result["details"] = f"Tried {result['attempts']} goldens, none worked"
    print(f"\n  {C.RED}FAILED{C.END} All {result['attempts']} attempts exhausted")
    return result

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Smart Autofix — Golden-based intelligent pipeline repair"
    )
    parser.add_argument(
        "--pipeline",
        type=str,
        choices=list(PIPELINES.keys()) + ["all"],
        help="Pipeline to fix (or 'all' for all broken pipelines)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Fix all broken pipelines (same as --pipeline all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making changes",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum number of golden snapshots to try per pipeline (default: 3)",
    )
    parser.add_argument(
        "--space",
        type=str,
        help="Target a specific HF Space URL (default: N8N_HOST from env)",
    )

    args = parser.parse_args()

    # Determine target pipelines
    if args.all or (args.pipeline == "all"):
        target_pipelines = list(PIPELINES.keys())
    elif args.pipeline:
        target_pipelines = [args.pipeline]
    else:
        parser.print_help()
        sys.exit(1)

    n8n_host = args.space or os.environ.get(
        "N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space"
    )

    # Header
    mode_str = f"{C.CYAN}DRY-RUN{C.END}" if args.dry_run else f"{C.RED}LIVE{C.END}"
    print(f"\n{C.BOLD}{'=' * 70}")
    print(f" Smart Autofix — {mode_str}")
    print(f"{'=' * 70}{C.END}")
    print(f"  Time:         {_now()}")
    print(f"  Target:       {', '.join(target_pipelines)}")
    print(f"  Space:        {n8n_host}")
    print(f"  Max attempts: {args.max_attempts}")
    print(f"  Dry-run:      {args.dry_run}")

    # Connect to n8n (unless dry-run)
    client = None
    if not args.dry_run:
        print(f"\n  Connecting to n8n...", end=" ", flush=True)
        client = N8nClient(n8n_host)
        if not client.login():
            print(f"\n  {C.RED}ERROR: Cannot login to n8n. Aborting.{C.END}")
            sys.exit(2)
        print(f"{C.GREEN}Logged in{C.END}")

    # Run autofix for each pipeline
    results = []
    for pipeline in target_pipelines:
        if args.dry_run:
            # In dry-run, create a mock client
            client = N8nClient(n8n_host)

        result = autofix_pipeline(
            client,
            pipeline,
            dry_run=args.dry_run,
            max_attempts=args.max_attempts,
        )
        results.append(result)

        # Log result
        log_autofix_result(result)
        if not args.dry_run:
            log_to_supabase(result)

    # Summary
    print(f"\n{C.BOLD}{'=' * 70}")
    print(f" Summary")
    print(f"{'=' * 70}{C.END}")

    fixed = sum(1 for r in results if r["fixed"])
    skipped = sum(1 for r in results if r.get("error_type") == "429" or "already healthy" in r.get("details", ""))
    failed = len(results) - fixed - skipped

    for r in results:
        if r["fixed"]:
            icon = f"{C.GREEN}FIXED{C.END}"
        elif "already healthy" in r.get("details", ""):
            icon = f"{C.BLUE}HEALTHY{C.END}"
        elif r.get("error_type") == "429":
            icon = f"{C.YELLOW}SKIP{C.END}"
        else:
            icon = f"{C.RED}FAILED{C.END}"

        details = r["details"][:60]
        print(f"  {icon:20s} {r['pipeline']:15s} {details}")

    print(f"\n  Total: {len(results)} | Fixed: {fixed} | Skipped: {skipped} | Failed: {failed}")
    print(f"  Log:   {AUTOFIX_LOG}")

    # Exit code
    if failed == len(results):
        sys.exit(2)  # All failed
    elif failed > 0:
        sys.exit(1)  # Some failed
    else:
        sys.exit(0)  # All OK

if __name__ == "__main__":
    main()
