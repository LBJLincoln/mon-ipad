#!/usr/bin/env python3
"""
Kaggle Live Status Fetcher — reads kernel status + recent log lines
Saves to data/kaggle-live.json for dashboard consumption.
Run by infra-agent.sh every 30 min, or standalone.
"""
import json, os, subprocess, sys, re
from datetime import datetime, timezone
from pathlib import Path

OUTPUT = Path("/home/termius/mon-ipad/data/kaggle-live.json")

KERNELS = [
    {"id": "alexismoret6/nba-karpathy-loop", "name": "NBA Karpathy", "project": "nba"},
    {"id": "alexismoret6/political-alpha-karpathy-loop", "name": "Political Karpathy", "project": "political"},
]

def get_kernel_status(kernel_id):
    """Get kernel status via kaggle CLI."""
    try:
        r = subprocess.run(["kaggle", "kernels", "status", kernel_id],
                          capture_output=True, text=True, timeout=30)
        out = r.stdout.strip()
        match = re.search(r'KernelWorkerStatus\.(\w+)', out)
        return match.group(1) if match else "UNKNOWN"
    except Exception as e:
        return f"ERROR: {e}"

def get_kernel_log(kernel_id, max_lines=50):
    """Get recent kernel output log."""
    tmp_dir = Path(f"/tmp/kaggle-live-{kernel_id.replace('/', '-')}")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Fetch kernel output
        r = subprocess.run(["kaggle", "kernels", "output", kernel_id, "-p", str(tmp_dir)],
                          capture_output=True, text=True, timeout=60)

        # Find the log file
        log_file = None
        for f in tmp_dir.glob("*.log"):
            log_file = f
            break

        if not log_file:
            return [], {}

        # Parse JSONL log
        raw = log_file.read_text()
        lines = []
        best_brier = None
        last_iter = None
        model_type = None

        for entry_str in raw.split("\n,"):
            entry_str = entry_str.strip().strip("[,]")
            if not entry_str:
                continue
            try:
                entry = json.loads(entry_str)
                data = entry.get("data", "").strip()
                if data:
                    lines.append(data)
                    # Parse Karpathy loop output
                    if "best=" in data:
                        match = re.search(r'best=(\d+\.\d+)', data)
                        if match:
                            b = float(match.group(1))
                            if best_brier is None or b < best_brier:
                                best_brier = b
                    if "Iter " in data:
                        match = re.search(r'Iter (\d+)', data)
                        if match:
                            last_iter = int(match.group(1))
                    if "NEW BEST" in data:
                        # Extract model type
                        match = re.search(r'\((\w+),', data)
                        if match:
                            model_type = match.group(1)
            except json.JSONDecodeError:
                continue

        # Return last N lines + parsed metrics
        metrics = {}
        if best_brier is not None:
            metrics["best_brier"] = best_brier
        if last_iter is not None:
            metrics["last_iteration"] = last_iter
        if model_type:
            metrics["best_model"] = model_type

        return lines[-max_lines:], metrics

    except Exception as e:
        return [f"Error fetching log: {e}"], {}
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

def main():
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kernels": []
    }

    for kernel in KERNELS:
        print(f"Checking {kernel['name']}...")
        status = get_kernel_status(kernel["id"])
        log_lines, metrics = [], {}

        # Only fetch logs if kernel has run
        if status in ("RUNNING", "COMPLETE", "ERROR"):
            log_lines, metrics = get_kernel_log(kernel["id"], max_lines=30)

        entry = {
            "id": kernel["id"],
            "name": kernel["name"],
            "project": kernel["project"],
            "status": status,
            "metrics": metrics,
            "recent_log": log_lines[-20:],  # Last 20 lines for dashboard
            "url": f"https://www.kaggle.com/code/{kernel['id']}",
        }
        results["kernels"].append(entry)
        print(f"  {kernel['name']}: {status} | {metrics}")

    OUTPUT.write_text(json.dumps(results, indent=2))
    print(f"\nSaved to {OUTPUT}")

if __name__ == "__main__":
    main()
