#!/usr/bin/env python3
"""
Nomos42 W&B-Style Local Logger
================================
Lightweight experiment logging to local files -- no account required.
Provides a W&B-compatible API for logging metrics, configs, and summaries.

Usage as CLI:
    python3 wandb-logger.py init --project nba-quant --name "xgboost-110f"
    python3 wandb-logger.py log --metric brier_score --value 0.2157 --step 435
    python3 wandb-logger.py config --data '{"features": 110, "model": "xgboost"}'
    python3 wandb-logger.py summary
    python3 wandb-logger.py list
    python3 wandb-logger.py compare --runs run1,run2,run3

Usage as library:
    from wandb_logger import LocalLogger
    logger = LocalLogger(project="nba-quant", name="xgboost-110f")
    logger.log_config({"features": 110, "model": "xgboost"})
    logger.log_metric("brier_score", 0.2157, step=435)
    logger.log_metric("roi_pct", -8.11)
    logger.finish()

Data is stored in: data/experiments/runs/<run_id>/
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ---------- paths ----------------------------------------------------------
BASE = Path(__file__).resolve().parents[2]  # mon-ipad root
RUNS_DIR = BASE / "data" / "experiments" / "runs"
ACTIVE_RUN_FILE = BASE / "data" / "experiments" / ".active_run"


# ---------- LocalLogger class ----------------------------------------------

class LocalLogger:
    """W&B-style local experiment logger."""

    def __init__(
        self,
        project: str = "nomos42",
        name: Optional[str] = None,
        run_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        notes: str = "",
        resume: bool = False,
    ):
        self.project = project
        self.name = name or f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.tags = tags or []
        self.notes = notes
        self.start_time = datetime.now(timezone.utc)

        # Run directory
        self.run_dir = RUNS_DIR / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # State
        self._config: dict = {}
        self._metrics: list[dict] = []
        self._step = 0
        self._best: dict = {}

        # Resume existing run
        if resume and (self.run_dir / "metrics.json").exists():
            self._load_existing()

        # Save initial metadata
        self._save_metadata()

        # Set as active run
        ACTIVE_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
        ACTIVE_RUN_FILE.write_text(self.run_id)

    def _load_existing(self):
        """Load existing run data for resumption."""
        try:
            metrics_path = self.run_dir / "metrics.json"
            if metrics_path.exists():
                self._metrics = json.loads(metrics_path.read_text())
                if self._metrics:
                    self._step = max(m.get("step", 0) for m in self._metrics) + 1
                    # Rebuild best tracking from existing metrics
                    loss_metrics = {"brier_score", "log_loss", "mse", "rmse", "mae", "loss", "error",
                                    "spread_err", "total_err", "max_drawdown_pct"}
                    for m in self._metrics:
                        name, value, step = m["name"], m["value"], m.get("step", 0)
                        if name in loss_metrics:
                            if name not in self._best or value < self._best[name]["value"]:
                                self._best[name] = {"value": value, "step": step}
                        else:
                            if name not in self._best or value > self._best[name]["value"]:
                                self._best[name] = {"value": value, "step": step}
        except Exception:
            pass

        try:
            config_path = self.run_dir / "config.json"
            if config_path.exists():
                self._config = json.loads(config_path.read_text())
        except Exception:
            pass

    def _save_metadata(self):
        """Save run metadata."""
        meta = {
            "run_id": self.run_id,
            "project": self.project,
            "name": self.name,
            "tags": self.tags,
            "notes": self.notes,
            "start_time": self.start_time.isoformat(),
            "status": "running",
        }
        (self.run_dir / "metadata.json").write_text(json.dumps(meta, indent=2))

    def log_config(self, config: dict):
        """Log experiment configuration."""
        self._config.update(config)
        (self.run_dir / "config.json").write_text(json.dumps(self._config, indent=2))

    def log_metric(self, name: str, value: float, step: Optional[int] = None):
        """Log a single metric value."""
        if step is None:
            step = self._step
            self._step += 1

        entry = {
            "name": name,
            "value": value,
            "step": step,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "wall_time": time.time(),
        }
        self._metrics.append(entry)

        # Track best values (min for loss-like, max for accuracy-like)
        loss_metrics = {"brier_score", "log_loss", "mse", "rmse", "mae", "loss", "error",
                        "spread_err", "total_err", "max_drawdown_pct"}
        if name in loss_metrics:
            if name not in self._best or value < self._best[name]["value"]:
                self._best[name] = {"value": value, "step": step}
        else:
            if name not in self._best or value > self._best[name]["value"]:
                self._best[name] = {"value": value, "step": step}

        # Persist (append-friendly)
        (self.run_dir / "metrics.json").write_text(json.dumps(self._metrics, indent=2))

        # Also append to metrics.jsonl for streaming reads
        with open(self.run_dir / "metrics.jsonl", "a") as f:
            f.write(json.dumps(entry) + "\n")

    def log_metrics(self, metrics: dict, step: Optional[int] = None):
        """Log multiple metrics at once."""
        if step is None:
            step = self._step
            self._step += 1

        for name, value in metrics.items():
            if isinstance(value, (int, float)):
                self.log_metric(name, value, step)

    def log_artifact(self, name: str, data: Any):
        """Log an artifact (any JSON-serializable data)."""
        artifacts_dir = self.run_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        (artifacts_dir / f"{name}.json").write_text(json.dumps(data, indent=2, default=str))

    def log_summary(self) -> dict:
        """Generate and save run summary."""
        # Compute metric summaries
        metric_names = set(m["name"] for m in self._metrics)
        metric_summary = {}
        for name in sorted(metric_names):
            values = [m["value"] for m in self._metrics if m["name"] == name]
            metric_summary[name] = {
                "last": values[-1] if values else None,
                "min": min(values) if values else None,
                "max": max(values) if values else None,
                "mean": sum(values) / len(values) if values else None,
                "count": len(values),
                "best": self._best.get(name, {}).get("value"),
                "best_step": self._best.get(name, {}).get("step"),
            }

        summary = {
            "run_id": self.run_id,
            "project": self.project,
            "name": self.name,
            "tags": self.tags,
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "duration_s": (datetime.now(timezone.utc) - self.start_time).total_seconds(),
            "total_steps": self._step,
            "total_metrics_logged": len(self._metrics),
            "config": self._config,
            "metrics": metric_summary,
            "best": {k: v for k, v in self._best.items()},
        }

        (self.run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
        return summary

    def finish(self):
        """Finalize the run."""
        summary = self.log_summary()

        # Update metadata
        meta_path = self.run_dir / "metadata.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            meta["status"] = "finished"
            meta["end_time"] = datetime.now(timezone.utc).isoformat()
            meta["duration_s"] = summary["duration_s"]
            meta_path.write_text(json.dumps(meta, indent=2))

        # Clear active run
        if ACTIVE_RUN_FILE.exists():
            try:
                if ACTIVE_RUN_FILE.read_text().strip() == self.run_id:
                    ACTIVE_RUN_FILE.unlink()
            except Exception:
                pass

        return summary

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finish()


# ---------- CLI functions --------------------------------------------------

def get_active_run_id() -> Optional[str]:
    """Get the active run ID."""
    if ACTIVE_RUN_FILE.exists():
        return ACTIVE_RUN_FILE.read_text().strip()
    return None


def list_runs(project: Optional[str] = None, limit: int = 20):
    """List all runs."""
    if not RUNS_DIR.exists():
        print("No runs found.")
        return

    runs = []
    for run_dir in sorted(RUNS_DIR.iterdir(), reverse=True):
        if not run_dir.is_dir() or run_dir.name.startswith("."):
            continue

        meta_path = run_dir / "metadata.json"
        summary_path = run_dir / "summary.json"

        meta = {}
        summary = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
            except Exception:
                pass
        if summary_path.exists():
            try:
                summary = json.loads(summary_path.read_text())
            except Exception:
                pass

        if project and meta.get("project") != project:
            continue

        runs.append({
            "run_id": run_dir.name,
            "name": meta.get("name", "?"),
            "project": meta.get("project", "?"),
            "status": meta.get("status", "?"),
            "start_time": meta.get("start_time", "?"),
            "metrics_count": summary.get("total_metrics_logged", 0),
            "best_brier": summary.get("best", {}).get("brier_score", {}).get("value", "N/A") if isinstance(summary.get("best", {}).get("brier_score"), dict) else "N/A",
        })

    if not runs:
        print("No runs found.")
        return

    # Print table
    print(f"{'Run ID':>20} {'Name':>25} {'Status':>10} {'Metrics':>8} {'Best Brier':>12} {'Started':>22}")
    print("-" * 100)
    for r in runs[:limit]:
        print(f"{r['run_id']:>20} {r['name']:>25} {r['status']:>10} {r['metrics_count']:>8} {str(r['best_brier']):>12} {str(r['start_time'])[:19]:>22}")

    print(f"\nTotal: {len(runs)} runs | Showing: {min(limit, len(runs))}")
    print(f"Runs dir: {RUNS_DIR}")


def compare_runs(run_ids: list[str]):
    """Compare multiple runs side by side."""
    print(f"\nComparing {len(run_ids)} runs:\n")

    summaries = []
    for rid in run_ids:
        summary_path = RUNS_DIR / rid / "summary.json"
        if summary_path.exists():
            try:
                summaries.append(json.loads(summary_path.read_text()))
            except Exception:
                print(f"  WARNING: Could not load summary for {rid}")
                summaries.append({"run_id": rid, "metrics": {}})
        else:
            print(f"  WARNING: No summary found for {rid}")
            summaries.append({"run_id": rid, "metrics": {}})

    if not summaries:
        print("No valid runs to compare.")
        return

    # Collect all metric names
    all_metrics = set()
    for s in summaries:
        all_metrics.update(s.get("metrics", {}).keys())

    # Print comparison
    col_width = 22
    header = f"{'Metric':<20}" + "".join(f"{s.get('run_id', '?')[:col_width]:>{col_width}}" for s in summaries)
    print(header)
    print("-" * (20 + col_width * len(summaries)))

    for metric in sorted(all_metrics):
        row = f"{metric:<20}"
        for s in summaries:
            val = s.get("metrics", {}).get(metric, {})
            if isinstance(val, dict):
                last = val.get("last", "N/A")
                best = val.get("best", "N/A")
                display = f"{last}" if last == best else f"{last} (best:{best})"
            else:
                display = str(val)
            row += f"{display:>{col_width}}"
        print(row)


def show_run_summary(run_id: str):
    """Show detailed summary for a single run."""
    summary_path = RUNS_DIR / run_id / "summary.json"
    if not summary_path.exists():
        print(f"No summary found for run {run_id}")
        return

    summary = json.loads(summary_path.read_text())
    print(json.dumps(summary, indent=2))


# ---------- main -----------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Nomos42 W&B-Style Local Logger",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # init
    init_p = subparsers.add_parser("init", help="Initialize a new run")
    init_p.add_argument("--project", "-p", default="nomos42", help="Project name")
    init_p.add_argument("--name", "-n", help="Run name")
    init_p.add_argument("--tags", nargs="*", help="Tags for this run")
    init_p.add_argument("--notes", default="", help="Notes")

    # log
    log_p = subparsers.add_parser("log", help="Log a metric")
    log_p.add_argument("--metric", "-m", required=True, help="Metric name")
    log_p.add_argument("--value", "-v", type=float, required=True, help="Metric value")
    log_p.add_argument("--step", "-s", type=int, help="Step number")
    log_p.add_argument("--run", help="Run ID (default: active run)")

    # config
    config_p = subparsers.add_parser("config", help="Log config")
    config_p.add_argument("--data", "-d", required=True, help="JSON config string")
    config_p.add_argument("--run", help="Run ID (default: active run)")

    # summary
    summary_p = subparsers.add_parser("summary", help="Show run summary")
    summary_p.add_argument("--run", help="Run ID (default: active run)")

    # list
    list_p = subparsers.add_parser("list", help="List all runs")
    list_p.add_argument("--project", "-p", help="Filter by project")
    list_p.add_argument("--limit", type=int, default=20, help="Max runs to show")

    # compare
    compare_p = subparsers.add_parser("compare", help="Compare runs")
    compare_p.add_argument("--runs", "-r", required=True, help="Comma-separated run IDs")

    # finish
    finish_p = subparsers.add_parser("finish", help="Finish active run")
    finish_p.add_argument("--run", help="Run ID (default: active run)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "init":
        logger = LocalLogger(
            project=args.project,
            name=args.name,
            tags=args.tags or [],
            notes=args.notes,
        )
        print(f"Run initialized: {logger.run_id}")
        print(f"Directory: {logger.run_dir}")

    elif args.command == "log":
        run_id = getattr(args, "run", None) or get_active_run_id()
        if not run_id:
            print("ERROR: No active run. Use 'init' first or specify --run")
            sys.exit(1)
        logger = LocalLogger(run_id=run_id, resume=True)
        logger.log_metric(args.metric, args.value, args.step)
        print(f"Logged: {args.metric}={args.value} (step={args.step or logger._step - 1})")

    elif args.command == "config":
        run_id = getattr(args, "run", None) or get_active_run_id()
        if not run_id:
            print("ERROR: No active run. Use 'init' first or specify --run")
            sys.exit(1)
        logger = LocalLogger(run_id=run_id, resume=True)
        config_data = json.loads(args.data)
        logger.log_config(config_data)
        print(f"Config updated: {list(config_data.keys())}")

    elif args.command == "summary":
        run_id = getattr(args, "run", None) or get_active_run_id()
        if not run_id:
            print("ERROR: No active run. Specify --run")
            sys.exit(1)
        show_run_summary(run_id)

    elif args.command == "list":
        list_runs(project=args.project, limit=args.limit)

    elif args.command == "compare":
        run_ids = [r.strip() for r in args.runs.split(",")]
        compare_runs(run_ids)

    elif args.command == "finish":
        run_id = getattr(args, "run", None) or get_active_run_id()
        if not run_id:
            print("ERROR: No active run.")
            sys.exit(1)
        logger = LocalLogger(run_id=run_id, resume=True)
        summary = logger.finish()
        print(f"Run {run_id} finished.")
        print(f"Total metrics logged: {summary.get('total_metrics_logged', 0)}")


if __name__ == "__main__":
    main()
