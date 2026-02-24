#!/usr/bin/env python3
"""
Session Intelligence Analyzer — Multi-RAG Orchestrator
=======================================================

Analyzes all past session data and produces actionable recommendations.
Run at the start of every session: python3 scripts/session-intelligence.py

Data sources:
  1. Git log        → session boundaries, commit patterns, duration
  2. docs/data.json → accuracy trends per pipeline per iteration
  3. technicals/debug/fixes-library.md → recurring fix patterns
  4. logs/db-snapshots/ → database state changes over time
  5. n8n_analysis_results/ → node-level success/failure rates
  6. logs/pipeline-results/ → per-pipeline accuracy results over time
  7. docs/status.json → current live metrics

Output:
  - JSON report → logs/session-intelligence-report.json
  - Human-readable summary → stdout
"""

import json
import os
import re
import glob
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_JSON = BASE_DIR / "docs" / "data.json"
STATUS_JSON = BASE_DIR / "docs" / "status.json"
FIXES_LIBRARY = BASE_DIR / "technicals" / "debug" / "fixes-library.md"
DB_SNAPSHOTS_DIR = BASE_DIR / "logs" / "db-snapshots"
N8N_RESULTS_DIR = BASE_DIR / "n8n_analysis_results"
PIPELINE_RESULTS_DIR = BASE_DIR / "logs" / "pipeline-results"
OUTPUT_JSON = BASE_DIR / "logs" / "session-intelligence-report.json"

PIPELINES = ["standard", "graph", "quantitative", "orchestrator", "pme-gateway"]
SESSION_GAP_HOURS = 2  # commits > 2h apart = new session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def safe_json_load(path):
    """Load JSON, return None on any error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def safe_read(path):
    """Read text file, return empty string on error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def parse_iso(ts_str):
    """Parse various ISO-like timestamps into datetime."""
    if not ts_str:
        return None
    # Strip trailing Z, handle +01:00 etc.
    ts_str = ts_str.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S+%f",
        "%Y-%m-%d %H:%M:%S %z",
    ):
        try:
            return datetime.strptime(ts_str, fmt)
        except (ValueError, OverflowError):
            continue
    # Fallback: regex extract
    m = re.match(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})", ts_str)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)}T{m.group(2)}", "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pass
    return None


def trend_label(values):
    """Determine trend from a list of numeric values."""
    if len(values) < 2:
        return "insufficient_data"
    # Use last 5 values if available
    recent = values[-5:]
    if len(recent) < 2:
        return "insufficient_data"
    first_half = recent[: len(recent) // 2]
    second_half = recent[len(recent) // 2 :]
    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)
    delta = avg_second - avg_first
    if delta > 3:
        return "improving"
    elif delta < -3:
        return "degrading"
    return "stable"


# ---------------------------------------------------------------------------
# 1. Parse git log → session boundaries
# ---------------------------------------------------------------------------
def parse_git_sessions():
    """Parse git log, group commits into sessions (gaps > 2 hours)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(BASE_DIR), "log", "--oneline",
             "--format=%H|%ai|%s", "--all", "--date-order"],
            capture_output=True, text=True, timeout=30
        )
        lines = result.stdout.strip().split("\n")
    except Exception:
        return [], []

    commits = []
    for line in lines:
        if not line.strip():
            continue
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        sha, ts_str, msg = parts
        dt = parse_iso(ts_str.strip())
        if dt:
            commits.append({"sha": sha.strip(), "timestamp": dt, "message": msg.strip()})

    if not commits:
        return [], []

    # Sort chronologically (oldest first)
    commits.sort(key=lambda c: c["timestamp"])

    # Group into sessions
    sessions = []
    current_session = [commits[0]]
    for c in commits[1:]:
        gap = (c["timestamp"] - current_session[-1]["timestamp"]).total_seconds() / 3600
        if gap > SESSION_GAP_HOURS:
            sessions.append(current_session)
            current_session = [c]
        else:
            current_session.append(c)
    if current_session:
        sessions.append(current_session)

    # Extract session IDs from commit messages
    session_id_pattern = re.compile(r"[Ss]ession\s*(\d+)")
    for sess in sessions:
        for c in sess:
            m = session_id_pattern.search(c["message"])
            if m:
                c["session_id"] = int(m.group(1))

    return sessions, commits


def build_session_metrics(sessions):
    """Build per-session metrics."""
    fix_pattern = re.compile(r"(?:fix|FIX)[-: ]", re.IGNORECASE)
    metrics = []

    for idx, sess in enumerate(sessions):
        start_dt = sess[0]["timestamp"]
        end_dt = sess[-1]["timestamp"]
        duration_h = max(0.1, (end_dt - start_dt).total_seconds() / 3600)

        # Try to find explicit session ID
        session_ids = [c.get("session_id") for c in sess if c.get("session_id")]
        session_id = str(max(session_ids)) if session_ids else str(idx + 1)

        fixes = sum(1 for c in sess if fix_pattern.search(c["message"]))

        metrics.append({
            "session_id": session_id,
            "date": start_dt.strftime("%Y-%m-%d"),
            "commits": len(sess),
            "fixes_applied": fixes,
            "accuracy_delta": "N/A",  # Will be enriched later
            "duration_hours": round(duration_h, 1),
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
        })

    return metrics


# ---------------------------------------------------------------------------
# 2. Parse docs/data.json → accuracy trends
# ---------------------------------------------------------------------------
def parse_accuracy_data():
    """Extract per-pipeline accuracy trends from data.json iterations."""
    data = safe_json_load(DATA_JSON)
    if not data:
        return {}

    pipeline_history = defaultdict(list)  # pipeline -> [(timestamp, accuracy)]
    iterations = data.get("iterations", [])

    for it in iterations:
        rs = it.get("results_summary", {})
        ts_str = it.get("timestamp_start") or it.get("timestamp_end")
        ts = parse_iso(ts_str) if ts_str else None

        for pipeline, stats in rs.items():
            acc = stats.get("accuracy_pct")
            tested = stats.get("tested", 0)
            if acc is not None and tested > 0:
                pipeline_history[pipeline].append({
                    "timestamp": ts.isoformat() if ts else None,
                    "accuracy": acc,
                    "tested": tested,
                    "errors": stats.get("errors", 0),
                    "avg_latency_ms": stats.get("avg_latency_ms"),
                })

    return dict(pipeline_history)


def parse_pipeline_results():
    """Parse logs/pipeline-results/ for per-pipeline accuracy over time."""
    if not PIPELINE_RESULTS_DIR.exists():
        return {}

    pipeline_history = defaultdict(list)

    for fpath in sorted(PIPELINE_RESULTS_DIR.glob("*.json")):
        data = safe_json_load(fpath)
        if not data:
            continue
        pipeline = data.get("pipeline", "unknown")
        pipeline_history[pipeline].append({
            "timestamp": data.get("timestamp"),
            "accuracy": data.get("accuracy_pct", 0),
            "tested": data.get("total_tested", 0),
            "correct": data.get("correct", 0),
            "errors": data.get("errors", 0),
            "avg_latency_ms": data.get("avg_latency_ms"),
            "label": data.get("label", ""),
            "file": fpath.name,
        })

    return dict(pipeline_history)


def build_pipeline_health(iteration_data, results_data, status_data):
    """Build pipeline health summary combining all accuracy sources."""
    health = {}

    for pipeline in PIPELINES:
        # Gather accuracy values from all sources
        accuracies = []

        # From data.json iterations
        for entry in iteration_data.get(pipeline, []):
            if entry["accuracy"] is not None and entry["tested"] > 2:
                accuracies.append(entry["accuracy"])

        # From pipeline-results files
        for entry in results_data.get(pipeline, []):
            if entry["accuracy"] is not None and entry["tested"] > 2:
                accuracies.append(entry["accuracy"])

        # Current from status.json
        current_acc = None
        if status_data and "pipelines" in status_data:
            ps = status_data["pipelines"].get(pipeline, {})
            current_acc = ps.get("accuracy")

        # Common errors from pipeline-results
        common_errors = []
        error_counts = Counter()
        for entry in results_data.get(pipeline, []):
            if entry.get("errors", 0) > 0:
                error_counts["execution_errors"] += entry["errors"]
            if entry.get("accuracy", 100) == 0 and entry.get("tested", 0) > 5:
                error_counts["total_failure_runs"] += 1

        for err, count in error_counts.most_common(5):
            common_errors.append(f"{err} ({count}x)")

        health[pipeline] = {
            "trend": trend_label(accuracies),
            "last_accuracy": current_acc if current_acc is not None else (accuracies[-1] if accuracies else None),
            "best_accuracy": max(accuracies) if accuracies else None,
            "worst_accuracy": min(accuracies) if accuracies else None,
            "data_points": len(accuracies),
            "common_errors": common_errors,
        }

    return health


# ---------------------------------------------------------------------------
# 3. Parse fixes-library.md → recurring patterns
# ---------------------------------------------------------------------------
def parse_fixes_library():
    """Parse the fixes-library.md to extract all fixes and detect recurring patterns."""
    content = safe_read(FIXES_LIBRARY)
    if not content:
        return [], [], []

    # Parse the INDEX table
    fixes = []
    # Match table rows: | # | Category | Problem | Session | Impact |
    table_pattern = re.compile(
        r"\|\s*(\d+)\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|"
    )
    for m in table_pattern.finditer(content):
        fix_num = m.group(1).strip()
        category = m.group(2).strip()
        problem = m.group(3).strip()
        session_str = m.group(4).strip()
        impact = m.group(5).strip()

        # Parse session numbers (can be "24" or "40b" or "40c")
        sess_match = re.findall(r"\d+", session_str)
        sessions = [int(s) for s in sess_match] if sess_match else []

        fixes.append({
            "fix_id": f"FIX-{fix_num}",
            "category": category,
            "problem": problem,
            "sessions": sessions,
            "impact": impact,
        })

    # Parse anti-patterns
    anti_patterns = []
    ap_pattern = re.compile(
        r"\|\s*(AP-\d+)\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|"
    )
    for m in ap_pattern.finditer(content):
        ap_id = m.group(1).strip()
        description = m.group(2).strip()
        frequency = m.group(3).strip()
        prevention = m.group(4).strip()
        anti_patterns.append({
            "id": ap_id,
            "description": description,
            "frequency": frequency,
            "prevention": prevention,
        })

    # Detect recurring issues: same category appears multiple times
    category_fixes = defaultdict(list)
    for fix in fixes:
        category_fixes[fix["category"]].append(fix)

    recurring_issues = []
    for cat, cat_fixes in category_fixes.items():
        if len(cat_fixes) >= 2:
            all_sessions = []
            for f in cat_fixes:
                all_sessions.extend(f["sessions"])
            all_sessions = sorted(set(all_sessions))

            # Check if latest session is recent (within last 5 sessions)
            max_session = max(all_sessions) if all_sessions else 0
            # We consider "still recurring" if the most recent fix was in a recent session
            still_recurring = max_session >= 50  # session 50+

            recurring_issues.append({
                "issue": f"{cat}: {'; '.join(f['problem'][:60] for f in cat_fixes[:3])}",
                "occurrences": len(cat_fixes),
                "sessions": all_sessions,
                "fix_applied": "; ".join(f["fix_id"] for f in cat_fixes),
                "still_recurring": still_recurring,
                "category": cat,
            })

    # Sort by occurrence count descending
    recurring_issues.sort(key=lambda x: x["occurrences"], reverse=True)

    return fixes, anti_patterns, recurring_issues


# ---------------------------------------------------------------------------
# 4. Parse db-snapshots → database state changes
# ---------------------------------------------------------------------------
def parse_db_snapshots():
    """Track database state changes over time from snapshot files."""
    if not DB_SNAPSHOTS_DIR.exists():
        return []

    snapshots = []
    for fpath in sorted(DB_SNAPSHOTS_DIR.glob("snap-*.json")):
        data = safe_json_load(fpath)
        if not data:
            continue

        ts_str = data.get("timestamp") or ""
        # Also try to extract timestamp from filename
        fname_match = re.search(r"snap-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})", fpath.name)
        if not ts_str and fname_match:
            ts_str = fname_match.group(1).replace("-", ":", 2)  # rough fix

        entry = {
            "snapshot_id": data.get("snapshot_id", fpath.stem),
            "timestamp": ts_str,
            "file": fpath.name,
        }

        # Extract DB stats
        pinecone = data.get("pinecone", {})
        neo4j = data.get("neo4j", {})
        supabase = data.get("supabase", {})

        entry["pinecone_vectors"] = pinecone.get("total_vectors")
        entry["pinecone_namespaces"] = len(pinecone.get("namespaces", {}))
        entry["neo4j_nodes"] = neo4j.get("total_nodes")
        entry["neo4j_relationships"] = neo4j.get("total_relationships")
        entry["supabase_rows"] = supabase.get("total_rows")

        snapshots.append(entry)

    return snapshots


def summarize_db_changes(snapshots):
    """Summarize meaningful DB state changes."""
    if not snapshots:
        return {"changes": [], "current_state": {}}

    # Get first and last with data
    first_with_data = None
    last_with_data = None
    for s in snapshots:
        if s.get("pinecone_vectors") is not None:
            if first_with_data is None:
                first_with_data = s
            last_with_data = s

    if not first_with_data or not last_with_data:
        return {"changes": [], "current_state": {}}

    changes = []
    for key, label in [
        ("pinecone_vectors", "Pinecone vectors"),
        ("neo4j_nodes", "Neo4j nodes"),
        ("neo4j_relationships", "Neo4j relationships"),
        ("supabase_rows", "Supabase rows"),
    ]:
        first_val = first_with_data.get(key)
        last_val = last_with_data.get(key)
        if first_val is not None and last_val is not None:
            delta = last_val - first_val
            if delta != 0:
                changes.append({
                    "metric": label,
                    "from": first_val,
                    "to": last_val,
                    "delta": delta,
                    "direction": "increased" if delta > 0 else "decreased",
                })

    current_state = {
        "pinecone_vectors": last_with_data.get("pinecone_vectors"),
        "neo4j_nodes": last_with_data.get("neo4j_nodes"),
        "neo4j_relationships": last_with_data.get("neo4j_relationships"),
        "supabase_rows": last_with_data.get("supabase_rows"),
        "snapshot_count": len(snapshots),
        "last_snapshot": last_with_data.get("timestamp"),
    }

    return {"changes": changes, "current_state": current_state}


# ---------------------------------------------------------------------------
# 5. Parse n8n_analysis_results → node-level performance
# ---------------------------------------------------------------------------
def parse_n8n_executions():
    """Parse n8n execution analysis files for node-level performance."""
    if not N8N_RESULTS_DIR.exists():
        return {}

    node_stats = defaultdict(lambda: {
        "success": 0, "failure": 0, "total_duration_ms": 0, "count": 0,
        "last_failure": None, "last_failure_error": None, "workflow": None,
    })

    execution_count = 0

    for fpath in sorted(N8N_RESULTS_DIR.glob("execution_*.json")):
        data = safe_json_load(fpath)
        if not data:
            continue

        execution_count += 1
        workflow_name = data.get("workflow_name", "unknown")
        exec_status = data.get("status", "unknown")
        exec_timestamp = data.get("started_at")

        for node in data.get("nodes", []):
            node_name = node.get("name", "unknown")
            key = f"{workflow_name}|{node_name}"
            duration = node.get("duration_ms") or 0
            status = node.get("status", "unknown")
            error = node.get("error")

            node_stats[key]["workflow"] = workflow_name
            node_stats[key]["count"] += 1
            node_stats[key]["total_duration_ms"] += duration

            if status == "success":
                node_stats[key]["success"] += 1
            else:
                node_stats[key]["failure"] += 1
                if exec_timestamp:
                    node_stats[key]["last_failure"] = exec_timestamp
                if error:
                    node_stats[key]["last_failure_error"] = str(error)[:200]

    # Build structured output grouped by workflow
    performance = {}
    for key, stats in node_stats.items():
        workflow, node_name = key.split("|", 1)
        if workflow not in performance:
            performance[workflow] = {}

        total = stats["success"] + stats["failure"]
        performance[workflow][node_name] = {
            "success_rate": round(stats["success"] / total, 3) if total > 0 else 0,
            "avg_duration_ms": round(stats["total_duration_ms"] / stats["count"]) if stats["count"] > 0 else 0,
            "failure_count": stats["failure"],
            "execution_count": stats["count"],
            "last_failure": stats["last_failure"],
            "last_failure_error": stats["last_failure_error"],
        }

    return performance


# ---------------------------------------------------------------------------
# 6. Generate recommendations
# ---------------------------------------------------------------------------
def generate_recommendations(pipeline_health, recurring_issues, node_performance,
                             db_summary, session_metrics, anti_patterns, fixes):
    """Generate prioritized, evidence-based recommendations."""
    recommendations = []
    priority = 0

    # --- Recommendation: Pipelines at 0% accuracy (only if enough data to be meaningful) ---
    for pipeline, health in pipeline_health.items():
        if health.get("last_accuracy") is not None and health["last_accuracy"] == 0:
            dp = health.get("data_points", 0)
            best = health.get("best_accuracy", 0)
            # Skip if barely tested (e.g., PME-gateway with 1 data point and 0 historical best)
            if dp <= 1 and (best is None or best == 0):
                continue
            priority += 1
            recommendations.append({
                "priority": priority,
                "action": f"CRITICAL: Fix {pipeline} pipeline — currently at 0% accuracy",
                "reason": f"{pipeline} last measured at 0% accuracy. Best historical: {best}%. "
                          f"This is a total pipeline failure requiring immediate investigation. "
                          f"({dp} data points collected.)",
                "estimated_impact": f"Restore to {best}% (historical best)",
                "category": "pipeline_failure",
            })

    # --- Recommendation: Degrading pipelines ---
    for pipeline, health in pipeline_health.items():
        if health["trend"] == "degrading":
            priority += 1
            recommendations.append({
                "priority": priority,
                "action": f"Investigate {pipeline} pipeline degradation",
                "reason": f"{pipeline} accuracy is trending downward. Last: {health.get('last_accuracy')}%, "
                          f"Best: {health.get('best_accuracy')}%.",
                "estimated_impact": f"Recover {(health.get('best_accuracy', 0) or 0) - (health.get('last_accuracy', 0) or 0):.0f}% accuracy",
                "category": "regression",
            })

    # --- Recommendation: Recurring issues that are still active ---
    for issue in recurring_issues:
        if issue["still_recurring"]:
            priority += 1
            recommendations.append({
                "priority": priority,
                "action": f"Address systemic issue: {issue['category']}",
                "reason": f"This category has {issue['occurrences']} separate fixes across sessions "
                          f"{issue['sessions'][:5]}{'...' if len(issue['sessions']) > 5 else ''}. "
                          f"Still recurring — needs architectural solution, not another point fix.",
                "estimated_impact": "Reduce debug time by 30-50% for this category",
                "category": "systemic",
            })

    # --- Recommendation: Anti-patterns with CHAQUE SESSION frequency ---
    for ap in anti_patterns:
        if "CHAQUE" in ap.get("frequency", "").upper() or "CRITIQUE" in ap.get("frequency", "").upper():
            priority += 1
            recommendations.append({
                "priority": priority,
                "action": f"Eliminate anti-pattern {ap['id']}: {ap['description'][:80]}",
                "reason": f"Frequency: {ap['frequency']}. Prevention: {ap['prevention'][:100]}",
                "estimated_impact": "Avoid 15-30 min wasted per session on known pitfall",
                "category": "anti_pattern",
            })

    # --- Recommendation: Nodes with high failure rates ---
    for workflow, nodes in node_performance.items():
        for node_name, stats in nodes.items():
            if stats["failure_count"] >= 3 and stats["success_rate"] < 0.8:
                priority += 1
                recommendations.append({
                    "priority": priority,
                    "action": f"Fix unreliable node: '{node_name}' in '{workflow[:50]}'",
                    "reason": f"Success rate: {stats['success_rate']*100:.0f}% "
                              f"({stats['failure_count']} failures / {stats['execution_count']} executions). "
                              f"Last error: {(stats.get('last_failure_error') or 'unknown')[:80]}",
                    "estimated_impact": f"Improve pipeline reliability by fixing {stats['failure_count']} known failures",
                    "category": "node_reliability",
                })

    # --- Recommendation: Session productivity ---
    if session_metrics:
        recent = session_metrics[-5:]
        avg_commits = sum(s["commits"] for s in recent) / len(recent)
        avg_fixes = sum(s["fixes_applied"] for s in recent) / len(recent)
        if avg_fixes > avg_commits * 0.4:
            priority += 1
            recommendations.append({
                "priority": priority,
                "action": "Shift from reactive fixing to proactive improvement",
                "reason": f"Recent sessions average {avg_fixes:.1f} fixes vs {avg_commits:.1f} total commits "
                          f"({avg_fixes/max(avg_commits,1)*100:.0f}% fix ratio). "
                          f"High fix ratio suggests systemic issues need architectural attention.",
                "estimated_impact": "20-30% more time on feature work vs debugging",
                "category": "process",
            })

    # --- Recommendation: Database health ---
    for change in db_summary.get("changes", []):
        if change["direction"] == "decreased" and abs(change["delta"]) > 100:
            priority += 1
            recommendations.append({
                "priority": priority,
                "action": f"Investigate {change['metric']} decrease: {change['from']} -> {change['to']}",
                "reason": f"{change['metric']} dropped by {abs(change['delta'])} "
                          f"({abs(change['delta'])/max(change['from'],1)*100:.1f}%). "
                          f"Could indicate data loss or intentional cleanup.",
                "estimated_impact": "Ensure no unintended data loss affecting pipeline accuracy",
                "category": "data_integrity",
            })

    # Sort by priority (already ordered by importance of detection)
    for i, rec in enumerate(recommendations):
        rec["priority"] = i + 1

    return recommendations


# ---------------------------------------------------------------------------
# 7. Enrich session metrics with accuracy deltas
# ---------------------------------------------------------------------------
def enrich_session_metrics(session_metrics, sessions, iteration_data):
    """Try to associate accuracy changes with specific sessions."""
    if not iteration_data or not session_metrics:
        return session_metrics

    # Build a timeline of accuracy measurements
    all_measurements = []
    for pipeline, entries in iteration_data.items():
        for entry in entries:
            ts = parse_iso(entry.get("timestamp"))
            if ts and entry.get("accuracy") is not None:
                all_measurements.append({
                    "timestamp": ts,
                    "pipeline": pipeline,
                    "accuracy": entry["accuracy"],
                    "tested": entry.get("tested", 0),
                })

    def to_naive(dt):
        """Strip timezone info for safe comparison."""
        if dt is None:
            return datetime.min
        return dt.replace(tzinfo=None) if dt.tzinfo else dt

    all_measurements.sort(key=lambda x: to_naive(x["timestamp"]))

    # For each session, find accuracy measurements within its timeframe
    for sm, sess in zip(session_metrics, sessions):
        start_naive = to_naive(sess[0]["timestamp"])
        end_naive = to_naive(sess[-1]["timestamp"])

        session_accs = []
        for m in all_measurements:
            m_naive = to_naive(m["timestamp"])
            if start_naive <= m_naive <= end_naive + timedelta(hours=1):
                session_accs.append(m["accuracy"])

        if len(session_accs) >= 2:
            delta = session_accs[-1] - session_accs[0]
            sm["accuracy_delta"] = f"{delta:+.1f}%"
        elif len(session_accs) == 1:
            sm["accuracy_delta"] = f"={session_accs[0]:.0f}%"

    return session_metrics


# ---------------------------------------------------------------------------
# 8. Human-readable summary
# ---------------------------------------------------------------------------
def print_summary(report):
    """Print a human-readable summary to stdout."""
    print("=" * 72)
    print("  SESSION INTELLIGENCE REPORT")
    print(f"  Generated: {report['generated_at']}")
    print(f"  Sessions analyzed: {report['sessions_analyzed']}")
    print(f"  Total commits: {report['total_commits']}")
    print("=" * 72)

    # Pipeline Health
    print("\n--- PIPELINE HEALTH ---")
    ph = report.get("pipeline_health", {})
    for pipeline in PIPELINES:
        h = ph.get(pipeline, {})
        if not h or h.get("data_points", 0) == 0:
            print(f"  {pipeline:20s}  [NO DATA]")
            continue
        last = h.get("last_accuracy")
        best = h.get("best_accuracy")
        trend = h.get("trend", "?")
        trend_symbol = {"improving": "+", "degrading": "!", "stable": "=", "insufficient_data": "?"}
        symbol = trend_symbol.get(trend, "?")
        last_str = f"{last:.0f}%" if last is not None else "N/A"
        best_str = f"{best:.0f}%" if best is not None else "N/A"
        print(f"  {pipeline:20s}  [{symbol}] {trend:14s}  last={last_str:>5s}  best={best_str:>5s}  ({h.get('data_points', 0)} measurements)")

    # Recurring Issues
    recurring = report.get("recurring_issues", [])
    if recurring:
        print(f"\n--- RECURRING ISSUES ({len(recurring)} detected) ---")
        for issue in recurring[:5]:
            still = "ACTIVE" if issue["still_recurring"] else "resolved"
            print(f"  [{still:8s}] {issue['category']}: {issue['occurrences']}x across {len(issue['sessions'])} sessions")
            print(f"             Fixes: {issue['fix_applied'][:70]}")

    # Anti-patterns reminder
    anti_patterns = report.get("anti_patterns", [])
    critical_aps = [ap for ap in anti_patterns if "CHAQUE" in ap.get("frequency", "").upper() or "CRITIQUE" in ap.get("frequency", "").upper()]
    if critical_aps:
        print(f"\n--- CRITICAL ANTI-PATTERNS ({len(critical_aps)}) ---")
        for ap in critical_aps:
            print(f"  {ap['id']}: {ap['description'][:70]}")
            print(f"         Frequency: {ap['frequency']}")

    # Database State
    db = report.get("database_state", {})
    cs = db.get("current_state", {})
    if cs:
        print("\n--- DATABASE STATE ---")
        for key in ["pinecone_vectors", "neo4j_nodes", "neo4j_relationships", "supabase_rows"]:
            val = cs.get(key)
            if val is not None:
                print(f"  {key:25s}  {val:>8,d}")
        changes = db.get("changes", [])
        if changes:
            print("  Changes since first snapshot:")
            for ch in changes:
                sign = "+" if ch["delta"] > 0 else ""
                print(f"    {ch['metric']:25s}  {sign}{ch['delta']:,d} ({ch['direction']})")

    # Node Performance Issues
    node_perf = report.get("node_performance", {})
    problem_nodes = []
    for wf, nodes in node_perf.items():
        for node_name, stats in nodes.items():
            if stats["failure_count"] >= 2 and stats["success_rate"] < 0.9:
                problem_nodes.append((wf, node_name, stats))
    problem_nodes.sort(key=lambda x: x[2]["success_rate"])

    if problem_nodes:
        print(f"\n--- UNRELIABLE NODES (success < 90%) ---")
        for wf, node, stats in problem_nodes[:8]:
            wf_short = wf[:40] + "..." if len(wf) > 40 else wf
            print(f"  {node[:30]:30s}  {stats['success_rate']*100:5.1f}% success  ({stats['failure_count']} failures)  [{wf_short}]")

    # Recommendations
    recs = report.get("recommendations", [])
    if recs:
        print(f"\n--- TOP RECOMMENDATIONS ({len(recs)} total) ---")
        for rec in recs[:7]:
            cat_icon = {
                "pipeline_failure": "!!",
                "regression": "!-",
                "systemic": "**",
                "anti_pattern": "AP",
                "node_reliability": "NR",
                "process": "PR",
                "data_integrity": "DI",
            }
            icon = cat_icon.get(rec.get("category", ""), "  ")
            print(f"  #{rec['priority']:2d} [{icon}] {rec['action'][:68]}")
            print(f"       Impact: {rec['estimated_impact'][:65]}")

    # Recent Session Activity
    sm = report.get("session_metrics", [])
    if sm:
        recent = sm[-6:]
        print(f"\n--- RECENT SESSIONS (last {len(recent)}) ---")
        print(f"  {'ID':>4s}  {'Date':10s}  {'Commits':>7s}  {'Fixes':>5s}  {'Hours':>5s}  {'Accuracy':>10s}")
        print(f"  {'----':>4s}  {'----------':10s}  {'-------':>7s}  {'-----':>5s}  {'-----':>5s}  {'----------':>10s}")
        for s in recent:
            print(f"  {s['session_id']:>4s}  {s['date']:10s}  {s['commits']:>7d}  {s['fixes_applied']:>5d}  {s['duration_hours']:>5.1f}  {s['accuracy_delta']:>10s}")

    print("\n" + "=" * 72)
    print(f"  Full report: {OUTPUT_JSON}")
    print("=" * 72)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Analyzing session data...", file=sys.stderr)

    # 1. Git sessions
    sessions, all_commits = parse_git_sessions()
    session_metrics = build_session_metrics(sessions)
    print(f"  Git: {len(sessions)} sessions, {len(all_commits)} commits", file=sys.stderr)

    # 2. Accuracy data
    iteration_data = parse_accuracy_data()
    results_data = parse_pipeline_results()
    status_data = safe_json_load(STATUS_JSON)
    pipeline_health = build_pipeline_health(iteration_data, results_data, status_data)
    print(f"  Accuracy: {sum(len(v) for v in iteration_data.values())} iteration data points, "
          f"{sum(len(v) for v in results_data.values())} result files", file=sys.stderr)

    # 3. Fixes library
    fixes, anti_patterns, recurring_issues = parse_fixes_library()
    print(f"  Fixes: {len(fixes)} fixes, {len(anti_patterns)} anti-patterns, "
          f"{len(recurring_issues)} recurring categories", file=sys.stderr)

    # 4. DB snapshots
    snapshots = parse_db_snapshots()
    db_summary = summarize_db_changes(snapshots)
    print(f"  DB: {len(snapshots)} snapshots", file=sys.stderr)

    # 5. Node performance
    node_performance = parse_n8n_executions()
    total_nodes = sum(len(v) for v in node_performance.values())
    print(f"  Nodes: {total_nodes} unique nodes across {len(node_performance)} workflows", file=sys.stderr)

    # 6. Enrich session metrics
    session_metrics = enrich_session_metrics(session_metrics, sessions, iteration_data)

    # 7. Generate recommendations
    recommendations = generate_recommendations(
        pipeline_health, recurring_issues, node_performance,
        db_summary, session_metrics, anti_patterns, fixes,
    )

    # 8. Build final report
    report = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "sessions_analyzed": len(sessions),
        "total_commits": len(all_commits),
        "total_fixes": len(fixes),
        "recurring_issues": recurring_issues,
        "anti_patterns": [
            {"id": ap["id"], "description": ap["description"],
             "frequency": ap["frequency"], "prevention": ap["prevention"]}
            for ap in anti_patterns
        ],
        "pipeline_health": pipeline_health,
        "node_performance": node_performance,
        "database_state": db_summary,
        "recommendations": recommendations,
        "session_metrics": session_metrics,
    }

    # 9. Write JSON report
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    # 10. Print human-readable summary
    print_summary(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
