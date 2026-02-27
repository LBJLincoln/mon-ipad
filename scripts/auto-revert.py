#!/usr/bin/env python3
"""
Auto-Revert — Automated rollback to last known good snapshot.

Reverts n8n pipeline workflows to their last validated golden state
from the snapshot/ directory. Integrates with workflow-diff-engine.py.

Usage:
    source .env.local && python3 scripts/auto-revert.py --pipeline standard --dry-run
    source .env.local && python3 scripts/auto-revert.py --pipeline all --confirm
    source .env.local && python3 scripts/auto-revert.py --pipeline graph --confirm

Dry-run mode (default):
    Shows what would be reverted without making changes.

Confirm mode:
    Actually performs the revert after showing the plan.
"""

import argparse
import glob
import importlib.util
import json
import os
import signal
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib import request, error
from http.cookiejar import CookieJar

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT_DIR = os.path.join(REPO_ROOT, "snapshot")
WORKFLOW_DIR = os.path.join(REPO_ROOT, "hf-space", "n8n-workflows")
LOGS_DIR = os.path.join(REPO_ROOT, "logs")
REVERT_LOG = os.path.join(LOGS_DIR, "auto-revert.jsonl")
BACKUP_DIR = os.path.join(SNAPSHOT_DIR, "auto-backup")

os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Load .env.local
# ---------------------------------------------------------------------------
def load_env():
    """Load environment variables from .env.local."""
    env_file = os.path.join(REPO_ROOT, ".env.local")
    if not os.path.exists(env_file):
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        with open(env_file) as f:
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
# Pipeline config
# ---------------------------------------------------------------------------
PIPELINES = {
    "standard": {
        "workflow_patterns": ["standard", "wf5"],
        "golden_filename": "standard.json",
    },
    "graph": {
        "workflow_patterns": ["graph", "wf2"],
        "golden_filename": "graph.json",
    },
    "quantitative": {
        "workflow_patterns": ["quantitative", "wf4"],
        "golden_filename": "quantitative.json",
    },
    "orchestrator": {
        "workflow_patterns": ["orchestrator"],
        "golden_filename": "orchestrator-v10.json",
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
    BOLD = "\033[1m"
    END = "\033[0m"

def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# N8n Client (minimal, for direct revert — mirrors patterns from existing scripts)
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
# Snapshot discovery
# ---------------------------------------------------------------------------
def find_latest_snapshot() -> Optional[str]:
    """Find the latest working-session snapshot directory.

    Returns the path to the latest snapshot directory, or None.
    """
    pattern = os.path.join(SNAPSHOT_DIR, "working-session*")
    dirs = sorted(glob.glob(pattern))
    if not dirs:
        return None
    # Return the highest-numbered session
    return dirs[-1]


def find_golden_workflow(pipeline: str) -> Optional[str]:
    """Find the golden workflow JSON for a pipeline.

    Search order:
    1. Latest working-session snapshot
    2. hf-space/n8n-workflows directory
    3. snapshot/current directory

    Returns the file path to the golden workflow JSON, or None.
    """
    config = PIPELINES.get(pipeline)
    if not config:
        return None

    filename = config["golden_filename"]

    # Search locations in priority order
    search_paths = []

    # 1. Latest working-session snapshot
    latest_snapshot = find_latest_snapshot()
    if latest_snapshot:
        search_paths.append(os.path.join(latest_snapshot, filename))
        # Also check without specific filename -- look for pipeline pattern in filenames
        for f in glob.glob(os.path.join(latest_snapshot, "*.json")):
            basename = os.path.basename(f).lower()
            if any(p in basename for p in config["workflow_patterns"]):
                search_paths.append(f)

    # 2. Workflow directory
    search_paths.append(os.path.join(WORKFLOW_DIR, filename))
    for f in glob.glob(os.path.join(WORKFLOW_DIR, "*.json")):
        basename = os.path.basename(f).lower()
        if any(p in basename for p in config["workflow_patterns"]):
            search_paths.append(f)

    # 3. snapshot/current
    current_dir = os.path.join(SNAPSHOT_DIR, "current")
    if os.path.isdir(current_dir):
        search_paths.append(os.path.join(current_dir, filename))
        for f in glob.glob(os.path.join(current_dir, "*.json")):
            basename = os.path.basename(f).lower()
            if any(p in basename for p in config["workflow_patterns"]):
                search_paths.append(f)

    # Deduplicate while preserving order
    seen = set()
    unique_paths = []
    for p in search_paths:
        if p not in seen:
            seen.add(p)
            unique_paths.append(p)

    # Return the first existing file
    for path in unique_paths:
        if os.path.exists(path):
            # Validate it is actually a workflow JSON
            try:
                with open(path) as f:
                    data = json.load(f)
                if "nodes" in data or "name" in data:
                    return path
            except (json.JSONDecodeError, IOError):
                continue

    return None


# ---------------------------------------------------------------------------
# Backup current state before revert
# ---------------------------------------------------------------------------
def backup_current_workflow(client: N8nClient, wf_id: str, pipeline: str) -> Optional[str]:
    """Download and save current workflow state before reverting.

    Returns the backup file path, or None on failure.
    """
    try:
        wf = client.get_workflow(wf_id)
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        backup_file = os.path.join(BACKUP_DIR, f"{pipeline}-pre-revert-{timestamp}.json")
        with open(backup_file, "w") as f:
            json.dump(wf, f, indent=2)
        return backup_file
    except Exception as e:
        print(f"  {C.YELLOW}WARN{C.END} Could not backup current workflow: {e}")
        return None


# ---------------------------------------------------------------------------
# Revert logic
# ---------------------------------------------------------------------------
def revert_pipeline(client: N8nClient, pipeline: str, golden_path: str,
                    dry_run: bool = True) -> dict:
    """Revert a single pipeline to its golden workflow state.

    Args:
        client: Authenticated N8nClient.
        pipeline: Pipeline name (standard, graph, etc.).
        golden_path: Path to the golden workflow JSON file.
        dry_run: If True, only show what would happen.

    Returns:
        Result dict with status and details.
    """
    config = PIPELINES[pipeline]
    result = {
        "pipeline": pipeline,
        "golden_path": golden_path,
        "action": "dry_run" if dry_run else "revert",
        "status": "pending",
        "details": "",
        "backup_path": None,
        "timestamp": _now(),
    }

    # Load golden workflow
    try:
        with open(golden_path) as f:
            golden_wf = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        result["status"] = "error"
        result["details"] = f"Cannot load golden workflow: {e}"
        return result

    golden_node_count = len(golden_wf.get("nodes", []))
    golden_name = golden_wf.get("name", "unknown")
    print(f"\n  Golden: {golden_name} ({golden_node_count} nodes) from {os.path.basename(golden_path)}")

    # Find matching workflow on n8n
    try:
        workflows = client.get_workflows()
    except Exception as e:
        result["status"] = "error"
        result["details"] = f"Cannot list workflows: {e}"
        return result

    target_wf_id = None
    target_wf_name = None
    for wf in workflows:
        name_lower = wf.get("name", "").lower()
        if any(p in name_lower for p in config["workflow_patterns"]):
            target_wf_id = wf["id"]
            target_wf_name = wf["name"]
            break

    if not target_wf_id:
        result["status"] = "error"
        result["details"] = f"No matching workflow found for pipeline '{pipeline}'"
        return result

    print(f"  Live:   {target_wf_name} (ID: {target_wf_id})")

    if dry_run:
        result["status"] = "dry_run"
        result["details"] = (
            f"Would revert '{target_wf_name}' (ID: {target_wf_id}) "
            f"to golden '{golden_name}' ({golden_node_count} nodes)"
        )
        print(f"  {C.CYAN}[DRY-RUN]{C.END} {result['details']}")
        return result

    # Backup current state
    backup_path = backup_current_workflow(client, target_wf_id, pipeline)
    result["backup_path"] = backup_path
    if backup_path:
        print(f"  {C.BLUE}Backup:{C.END} {backup_path}")

    # Perform revert
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
        print(f"  {C.GREEN}Reverted{C.END} workflow to golden state")

        # Re-activate with new versionId
        updated_wf = client.get_workflow(target_wf_id)
        version_id = updated_wf.get("versionId", "1")
        client.activate_workflow(target_wf_id, version_id)
        print(f"  {C.GREEN}Re-activated{C.END} with versionId={version_id}")

        result["status"] = "success"
        result["details"] = (
            f"Reverted '{target_wf_name}' to golden state and re-activated"
        )

    except Exception as e:
        result["status"] = "error"
        result["details"] = f"Revert failed: {e}"
        print(f"  {C.RED}ERROR{C.END} {result['details']}")

        # Attempt to restore from backup if revert failed partway
        if backup_path:
            print(f"  {C.YELLOW}Attempting restore from backup...{C.END}")
            try:
                with open(backup_path) as f:
                    backup_wf = json.load(f)
                client.update_workflow(target_wf_id, {
                    "nodes": backup_wf.get("nodes", []),
                    "connections": backup_wf.get("connections", {}),
                    "settings": backup_wf.get("settings", {}),
                })
                fresh = client.get_workflow(target_wf_id)
                client.activate_workflow(target_wf_id, fresh.get("versionId", "1"))
                print(f"  {C.GREEN}Restored from backup successfully{C.END}")
                result["details"] += " (restored from backup)"
            except Exception as restore_err:
                print(f"  {C.RED}Backup restore also failed: {restore_err}{C.END}")
                result["details"] += f" (backup restore also failed: {restore_err})"

    return result


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def log_revert(results: List[dict]):
    """Append revert results to JSONL log."""
    entry = {
        "timestamp": _now(),
        "results": results,
    }
    try:
        with open(REVERT_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except (OSError, IOError) as e:
        print(f"  {C.YELLOW}WARN{C.END} Cannot write revert log: {e}")


# ---------------------------------------------------------------------------
# Attempt to use workflow-diff-engine.py revert if available
# ---------------------------------------------------------------------------
def try_workflow_diff_engine_revert(pipeline: str, space_url: str, dry_run: bool) -> Optional[bool]:
    """Try to use workflow-diff-engine.py's revert_workflow function.

    Returns True/False on success/failure, or None if the module is unavailable.
    """
    diff_engine_path = os.path.join(REPO_ROOT, "scripts", "workflow-diff-engine.py")
    if not os.path.exists(diff_engine_path):
        return None

    try:
        spec = importlib.util.spec_from_file_location("workflow_diff_engine", diff_engine_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Check if the function exists and has the expected signature
        if not hasattr(mod, "revert_workflow"):
            return None

        golden_file = PIPELINES.get(pipeline, {}).get("golden_filename")
        if not golden_file:
            return None

        return mod.revert_workflow(space_url, pipeline, golden_file, dry_run=dry_run)

    except Exception as e:
        print(f"  {C.YELLOW}WARN{C.END} workflow-diff-engine import failed: {e}")
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Auto-Revert -- Rollback pipelines to last known good snapshot"
    )
    parser.add_argument(
        "--pipeline", type=str, required=True,
        choices=list(PIPELINES.keys()) + ["all"],
        help="Pipeline to revert (or 'all' for all pipelines)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Show what would be reverted without making changes (default)"
    )
    parser.add_argument(
        "--confirm", action="store_true",
        help="Actually perform the revert (disables dry-run)"
    )
    parser.add_argument(
        "--space", type=str,
        help="Target a specific HF Space URL (default: N8N_HOST from env)"
    )
    parser.add_argument(
        "--use-diff-engine", action="store_true",
        help="Try to use workflow-diff-engine.py's revert logic first"
    )

    args = parser.parse_args()

    # Determine dry-run state: --confirm overrides --dry-run
    dry_run = not args.confirm

    n8n_host = args.space or os.environ.get(
        "N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space"
    )

    # Determine which pipelines to revert
    if args.pipeline == "all":
        target_pipelines = list(PIPELINES.keys())
    else:
        target_pipelines = [args.pipeline]

    # Header
    mode_str = f"{C.CYAN}DRY-RUN{C.END}" if dry_run else f"{C.RED}LIVE REVERT{C.END}"
    print(f"\n{C.BOLD}{'=' * 60}")
    print(f" Auto-Revert -- {mode_str}")
    print(f"{'=' * 60}{C.END}")
    print(f"  Time:      {_now()}")
    print(f"  Target:    {', '.join(target_pipelines)}")
    print(f"  Space:     {n8n_host}")
    print(f"  Dry-run:   {dry_run}")

    # Find golden snapshots
    latest = find_latest_snapshot()
    if latest:
        print(f"  Snapshot:  {latest}")
    else:
        print(f"  Snapshot:  {C.YELLOW}No working-session snapshot found{C.END}")

    # Locate golden workflows
    golden_map: Dict[str, str] = {}
    print(f"\n  Locating golden workflows:")
    for pipe in target_pipelines:
        golden = find_golden_workflow(pipe)
        if golden:
            golden_map[pipe] = golden
            print(f"    {C.GREEN}OK{C.END}  {pipe}: {os.path.relpath(golden, REPO_ROOT)}")
        else:
            print(f"    {C.RED}MISS{C.END} {pipe}: no golden workflow found")

    if not golden_map:
        print(f"\n  {C.RED}ERROR: No golden workflows found. Cannot revert.{C.END}")
        sys.exit(1)

    # If using diff-engine mode, try that first
    if args.use_diff_engine:
        print(f"\n  Attempting revert via workflow-diff-engine.py...")
        for pipe in target_pipelines:
            if pipe not in golden_map:
                continue
            result = try_workflow_diff_engine_revert(pipe, n8n_host, dry_run)
            if result is not None:
                status = "success" if result else "failed"
                print(f"    {pipe}: {status} (via diff-engine)")
            else:
                print(f"    {pipe}: diff-engine unavailable, falling back to direct revert")
        # If diff-engine handled everything, we're done
        if all(
            try_workflow_diff_engine_revert(p, n8n_host, dry_run) is not None
            for p in target_pipelines if p in golden_map
        ):
            print(f"\n  Revert complete via workflow-diff-engine.")
            sys.exit(0)

    # Direct revert path
    print(f"\n  Connecting to n8n at {n8n_host}...")
    client = N8nClient(n8n_host)
    if not client.login():
        print(f"  {C.RED}ERROR: Cannot login to n8n. Aborting.{C.END}")
        sys.exit(1)
    print(f"  {C.GREEN}Logged in{C.END}")

    # Confirm step (for non-dry-run)
    if not dry_run:
        print(f"\n  {C.YELLOW}WARNING: This will OVERWRITE live workflows!{C.END}")
        print(f"  Pipelines: {', '.join(golden_map.keys())}")
        print(f"  Backups will be saved to: {BACKUP_DIR}")
        try:
            answer = input(f"\n  Type 'yes' to proceed: ")
            if answer.strip().lower() != "yes":
                print(f"  Aborted by user.")
                sys.exit(0)
        except EOFError:
            # Running non-interactively (e.g., from nohup)
            print(f"  Non-interactive mode: proceeding with revert")

    # Execute reverts
    results: List[dict] = []
    for pipe in target_pipelines:
        if pipe not in golden_map:
            results.append({
                "pipeline": pipe,
                "status": "skipped",
                "details": "No golden workflow found",
                "timestamp": _now(),
            })
            continue

        result = revert_pipeline(client, pipe, golden_map[pipe], dry_run=dry_run)
        results.append(result)

    # Log results
    log_revert(results)

    # Summary
    print(f"\n{C.BOLD}{'=' * 60}")
    print(f" Summary")
    print(f"{'=' * 60}{C.END}")
    for r in results:
        status = r["status"]
        if status == "success":
            icon = f"{C.GREEN}OK{C.END}"
        elif status == "dry_run":
            icon = f"{C.CYAN}DRY{C.END}"
        elif status == "skipped":
            icon = f"{C.YELLOW}SKIP{C.END}"
        else:
            icon = f"{C.RED}ERR{C.END}"
        print(f"  {icon}  {r['pipeline']}: {r['details'][:80]}")

    print(f"\n  Log: {REVERT_LOG}")

    # Exit code
    errors = sum(1 for r in results if r["status"] == "error")
    sys.exit(1 if errors > 0 else 0)


if __name__ == "__main__":
    main()
