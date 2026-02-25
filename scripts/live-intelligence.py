#!/usr/bin/env python3
"""
Live Intelligence System — Multi-RAG Orchestrator
=================================================

Continuous monitoring and mathematical analysis system.
Runs as a daemon, analyzes every 10 minutes.

Usage:
  nohup python3 scripts/live-intelligence.py > logs/live-intelligence.log 2>&1 &

Analyzes:
  - Fix patterns from fixes-library.md
  - Recent eval results from logs/pipeline-results/
  - Monitor logs from logs/monitor/
  - Trend detection (improving/degrading/stable)
  - Regression alerts (accuracy drops >10%)
  - Fix effectiveness (which fixes actually worked?)
  - Node-level bottlenecks

Outputs:
  - logs/live-intelligence-report.json (overwritten each cycle)
  - logs/intelligence-history.jsonl (append-only history)
"""

import json
import os
import re
import glob
import time
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, Counter

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
FIXES_LIBRARY = BASE_DIR / "technicals" / "debug" / "fixes-library.md"
PIPELINE_RESULTS_DIR = BASE_DIR / "logs" / "pipeline-results"
MONITOR_DIR = BASE_DIR / "logs" / "monitor"
OUTPUT_JSON = BASE_DIR / "logs" / "live-intelligence-report.json"
HISTORY_JSONL = BASE_DIR / "logs" / "intelligence-history.jsonl"

CYCLE_INTERVAL_SECONDS = 600  # 10 minutes
REGRESSION_THRESHOLD_PCT = 10  # Alert if accuracy drops >10%
LOOKBACK_HOURS = 24  # Analyze last 24 hours for trends
PIPELINES = ["standard", "graph", "quantitative", "orchestrator", "pme-gateway"]

running = True

# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------
def signal_handler(signum, frame):
    """Graceful shutdown on SIGTERM/SIGINT."""
    global running
    print(f"\n[{datetime.now().isoformat()}] Received signal {signum}, shutting down gracefully...")
    running = False

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def safe_json_load(path):
    """Load JSON, return None on error."""
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
    """Parse ISO timestamp into datetime."""
    if not ts_str:
        return None
    ts_str = ts_str.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
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

def trend_analysis(values):
    """Calculate trend from time series values. Returns: trend, delta, strength."""
    if len(values) < 2:
        return "insufficient_data", 0.0, 0.0

    # Linear regression: y = mx + b
    n = len(values)
    x_vals = list(range(n))
    y_vals = values

    x_mean = sum(x_vals) / n
    y_mean = sum(y_vals) / n

    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals))
    denominator = sum((x - x_mean) ** 2 for x in x_vals)

    if denominator == 0:
        return "stable", 0.0, 0.0

    slope = numerator / denominator
    delta = slope * (n - 1)  # Total change over period

    # Classification
    if abs(delta) < 3:
        trend = "stable"
    elif delta > 0:
        trend = "improving"
    else:
        trend = "degrading"

    # Strength: how consistent is the trend?
    predicted = [slope * x + (y_mean - slope * x_mean) for x in x_vals]
    residuals = [abs(y - p) for y, p in zip(y_vals, predicted)]
    strength = 1.0 - (sum(residuals) / (n * (max(y_vals) - min(y_vals) + 1)))
    strength = max(0.0, min(1.0, strength))

    return trend, delta, strength

# ---------------------------------------------------------------------------
# Parse fixes-library.md
# ---------------------------------------------------------------------------
def parse_fixes_library():
    """Extract all fixes and anti-patterns from fixes-library.md."""
    content = safe_read(FIXES_LIBRARY)
    if not content:
        return [], [], {}

    # Parse fixes table
    fixes = []
    table_pattern = re.compile(
        r"\|\s*(\d+)\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|"
    )
    for m in table_pattern.finditer(content):
        fix_num = m.group(1).strip()
        category = m.group(2).strip()
        problem = m.group(3).strip()
        session_str = m.group(4).strip()
        impact = m.group(5).strip()

        # Parse session numbers
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

    # Count fixes per category
    category_counts = Counter(f["category"] for f in fixes)

    return fixes, anti_patterns, dict(category_counts)

# ---------------------------------------------------------------------------
# Parse pipeline results
# ---------------------------------------------------------------------------
def parse_pipeline_results(lookback_hours=LOOKBACK_HOURS):
    """Parse recent pipeline results from logs/pipeline-results/."""
    if not PIPELINE_RESULTS_DIR.exists():
        return {}

    cutoff = datetime.now() - timedelta(hours=lookback_hours)
    pipeline_history = defaultdict(list)

    for fpath in sorted(PIPELINE_RESULTS_DIR.glob("*.json")):
        data = safe_json_load(fpath)
        if not data:
            continue

        ts_str = data.get("timestamp")
        ts = parse_iso(ts_str)

        # Skip if too old (make timezone-naive for comparison)
        if ts:
            ts_naive = ts.replace(tzinfo=None) if ts.tzinfo else ts
            cutoff_naive = cutoff.replace(tzinfo=None) if cutoff.tzinfo else cutoff
            if ts_naive < cutoff_naive:
                continue

        pipeline = data.get("pipeline", "unknown")
        pipeline_history[pipeline].append({
            "timestamp": ts_str,
            "timestamp_dt": ts,
            "accuracy": data.get("accuracy_pct", 0),
            "tested": data.get("total_tested", 0),
            "correct": data.get("correct", 0),
            "errors": data.get("errors", 0),
            "avg_latency_ms": data.get("avg_latency_ms"),
            "label": data.get("label", ""),
            "file": fpath.name,
        })

    # Sort by timestamp
    for pipeline in pipeline_history:
        pipeline_history[pipeline].sort(key=lambda x: x["timestamp_dt"] or datetime.min)

    return dict(pipeline_history)

# ---------------------------------------------------------------------------
# Parse monitor logs
# ---------------------------------------------------------------------------
def parse_monitor_logs(lookback_hours=LOOKBACK_HOURS):
    """Parse recent monitor logs from logs/monitor/."""
    if not MONITOR_DIR.exists():
        return []

    cutoff = datetime.now() - timedelta(hours=lookback_hours)
    events = []

    for fpath in sorted(MONITOR_DIR.glob("*.jsonl")):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        ts_str = data.get("timestamp")
                        ts = parse_iso(ts_str)

                        # Make timezone-naive for comparison
                        if ts:
                            ts_naive = ts.replace(tzinfo=None) if ts.tzinfo else ts
                            cutoff_naive = cutoff.replace(tzinfo=None) if cutoff.tzinfo else cutoff
                            if ts_naive >= cutoff_naive:
                                events.append(data)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue

    events.sort(key=lambda x: parse_iso(x.get("timestamp")) or datetime.min)
    return events

# ---------------------------------------------------------------------------
# Analyze pipeline health
# ---------------------------------------------------------------------------
def analyze_pipeline_health(pipeline_history):
    """Analyze per-pipeline trends, regressions, stability."""
    health = {}
    alerts = []

    for pipeline in PIPELINES:
        history = pipeline_history.get(pipeline, [])

        if not history:
            health[pipeline] = {
                "status": "no_data",
                "trend": "insufficient_data",
                "trend_delta": 0.0,
                "trend_strength": 0.0,
                "current_accuracy": None,
                "prev_accuracy": None,
                "data_points": 0,
                "avg_latency_ms": None,
                "error_rate": 0.0,
            }
            continue

        # Extract accuracy values
        accuracies = [h["accuracy"] for h in history if h["tested"] > 0]

        if not accuracies:
            health[pipeline] = {
                "status": "no_valid_data",
                "trend": "insufficient_data",
                "trend_delta": 0.0,
                "trend_strength": 0.0,
                "current_accuracy": None,
                "prev_accuracy": None,
                "data_points": 0,
                "avg_latency_ms": None,
                "error_rate": 0.0,
            }
            continue

        # Trend analysis
        trend, delta, strength = trend_analysis(accuracies)

        current_acc = accuracies[-1]
        prev_acc = accuracies[-2] if len(accuracies) > 1 else None

        # Regression detection
        if prev_acc is not None and (prev_acc - current_acc) > REGRESSION_THRESHOLD_PCT:
            alerts.append({
                "type": "regression",
                "severity": "high",
                "pipeline": pipeline,
                "message": f"{pipeline} accuracy dropped {prev_acc - current_acc:.1f}% ({prev_acc:.1f}% → {current_acc:.1f}%)",
                "prev_accuracy": prev_acc,
                "current_accuracy": current_acc,
                "timestamp": history[-1]["timestamp"],
            })

        # Calculate average latency
        latencies = [h["avg_latency_ms"] for h in history if h["avg_latency_ms"]]
        avg_latency = sum(latencies) / len(latencies) if latencies else None

        # Calculate error rate
        total_tested = sum(h["tested"] for h in history)
        total_errors = sum(h["errors"] for h in history)
        error_rate = (total_errors / total_tested * 100) if total_tested > 0 else 0.0

        health[pipeline] = {
            "status": "ok" if current_acc >= 70 else "degraded" if current_acc >= 50 else "critical",
            "trend": trend,
            "trend_delta": round(delta, 2),
            "trend_strength": round(strength, 3),
            "current_accuracy": current_acc,
            "prev_accuracy": prev_acc,
            "data_points": len(history),
            "avg_latency_ms": round(avg_latency) if avg_latency else None,
            "error_rate": round(error_rate, 2),
        }

    return health, alerts

# ---------------------------------------------------------------------------
# Analyze fix effectiveness
# ---------------------------------------------------------------------------
def analyze_fix_effectiveness(fixes, pipeline_history):
    """Correlate fixes with accuracy improvements."""
    fix_effectiveness = []

    # Group fixes by session
    session_fixes = defaultdict(list)
    for fix in fixes:
        for sess in fix["sessions"]:
            session_fixes[sess].append(fix)

    # For each session with fixes, check if accuracy improved
    for sess, sess_fixes in session_fixes.items():
        # This is a simplified analysis - in production, you'd correlate with git timestamps
        fix_effectiveness.append({
            "session": sess,
            "fixes_applied": len(sess_fixes),
            "categories": list(set(f["category"] for f in sess_fixes)),
            # Would need temporal correlation with pipeline results to measure actual impact
            "impact_measured": False,
        })

    return fix_effectiveness

# ---------------------------------------------------------------------------
# Analyze failure patterns
# ---------------------------------------------------------------------------
def analyze_failure_patterns(pipeline_history):
    """Identify most common failure patterns."""
    patterns = []

    for pipeline, history in pipeline_history.items():
        # Find runs with 0% accuracy or high error rates
        failures = [h for h in history if h["accuracy"] == 0 or h["errors"] > h["tested"] * 0.5]

        if failures:
            patterns.append({
                "pipeline": pipeline,
                "failure_count": len(failures),
                "total_runs": len(history),
                "failure_rate": round(len(failures) / len(history) * 100, 1),
                "recent_failure": failures[-1]["timestamp"] if failures else None,
            })

    patterns.sort(key=lambda x: x["failure_rate"], reverse=True)
    return patterns

# ---------------------------------------------------------------------------
# Generate recommendations
# ---------------------------------------------------------------------------
def generate_recommendations(health, alerts, failure_patterns, category_counts):
    """Generate prioritized recommendations based on live analysis."""
    recommendations = []

    # Priority 1: Active regressions
    for alert in alerts:
        if alert["type"] == "regression":
            recommendations.append({
                "priority": "high",
                "category": "regression",
                "action": f"Investigate {alert['pipeline']} regression",
                "reason": alert["message"],
                "impact": f"Recover {alert['prev_accuracy'] - alert['current_accuracy']:.1f}% accuracy",
            })

    # Priority 2: Degrading trends with high strength
    for pipeline, h in health.items():
        if h["trend"] == "degrading" and h["trend_strength"] > 0.7 and h["data_points"] >= 3:
            recommendations.append({
                "priority": "medium",
                "category": "trend",
                "action": f"Address {pipeline} degrading trend",
                "reason": f"Consistent downward trend ({h['trend_delta']:.1f}% over {h['data_points']} measurements, strength={h['trend_strength']:.2f})",
                "impact": f"Prevent further degradation from {h['current_accuracy']:.1f}%",
            })

    # Priority 3: High failure rates
    for fp in failure_patterns[:3]:
        if fp["failure_rate"] > 20:
            recommendations.append({
                "priority": "medium",
                "category": "reliability",
                "action": f"Fix {fp['pipeline']} reliability issues",
                "reason": f"{fp['failure_rate']}% failure rate ({fp['failure_count']}/{fp['total_runs']} runs)",
                "impact": f"Improve reliability by {fp['failure_rate']:.0f}%",
            })

    # Priority 4: Recurring fix categories
    for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        if count >= 3:
            recommendations.append({
                "priority": "low",
                "category": "systemic",
                "action": f"Architectural fix for {category}",
                "reason": f"{count} separate fixes applied - needs systemic solution",
                "impact": "Reduce debug time by 30-50% for this category",
            })

    return recommendations

# ---------------------------------------------------------------------------
# Analysis cycle
# ---------------------------------------------------------------------------
def run_analysis_cycle():
    """Run one complete analysis cycle."""
    print(f"[{datetime.now().isoformat()}] Starting analysis cycle...")

    # Parse data sources
    fixes, anti_patterns, category_counts = parse_fixes_library()
    pipeline_history = parse_pipeline_results(LOOKBACK_HOURS)
    monitor_events = parse_monitor_logs(LOOKBACK_HOURS)

    # Analyze
    health, alerts = analyze_pipeline_health(pipeline_history)
    fix_effectiveness = analyze_fix_effectiveness(fixes, pipeline_history)
    failure_patterns = analyze_failure_patterns(pipeline_history)
    recommendations = generate_recommendations(health, alerts, failure_patterns, category_counts)

    # Build report
    report = {
        "generated_at": datetime.now().isoformat(),
        "analysis_window_hours": LOOKBACK_HOURS,
        "cycle_interval_seconds": CYCLE_INTERVAL_SECONDS,
        "pipeline_health": health,
        "alerts": alerts,
        "recommendations": recommendations,
        "failure_patterns": failure_patterns,
        "fix_summary": {
            "total_fixes": len(fixes),
            "total_anti_patterns": len(anti_patterns),
            "category_counts": category_counts,
        },
        "monitor_events_count": len(monitor_events),
        "data_freshness": {
            "pipeline_results_count": sum(len(v) for v in pipeline_history.values()),
            "oldest_result": min((h[0]["timestamp"] for h in pipeline_history.values() if h), default=None),
            "newest_result": max((h[-1]["timestamp"] for h in pipeline_history.values() if h), default=None),
        },
    }

    # Write current report (overwrite)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Append to history
    HISTORY_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_JSONL, "a", encoding="utf-8") as f:
        # Write compact summary to history
        history_entry = {
            "timestamp": report["generated_at"],
            "pipeline_health": {p: {"accuracy": h["current_accuracy"], "trend": h["trend"]}
                               for p, h in health.items() if h["current_accuracy"] is not None},
            "alerts_count": len(alerts),
            "high_priority_recs": len([r for r in recommendations if r["priority"] == "high"]),
        }
        f.write(json.dumps(history_entry, ensure_ascii=False) + "\n")

    print(f"[{datetime.now().isoformat()}] Analysis complete:")
    print(f"  - Pipeline health: {sum(1 for h in health.values() if h['status'] == 'ok')}/{len(PIPELINES)} OK")
    print(f"  - Alerts: {len(alerts)}")
    print(f"  - Recommendations: {len(recommendations)}")
    print(f"  - Report: {OUTPUT_JSON}")

    return report

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main():
    """Main daemon loop."""
    print(f"[{datetime.now().isoformat()}] Live Intelligence System starting...")
    print(f"  Cycle interval: {CYCLE_INTERVAL_SECONDS}s ({CYCLE_INTERVAL_SECONDS // 60} minutes)")
    print(f"  Lookback window: {LOOKBACK_HOURS} hours")
    print(f"  Output: {OUTPUT_JSON}")
    print(f"  History: {HISTORY_JSONL}")

    cycle_count = 0

    while running:
        try:
            cycle_count += 1
            print(f"\n{'='*72}")
            print(f"CYCLE {cycle_count} — {datetime.now().isoformat()}")
            print(f"{'='*72}")

            run_analysis_cycle()

            if running:
                print(f"[{datetime.now().isoformat()}] Sleeping {CYCLE_INTERVAL_SECONDS}s until next cycle...")
                time.sleep(CYCLE_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print("\n[{datetime.now().isoformat()}] Keyboard interrupt, exiting...")
            break
        except Exception as e:
            print(f"[{datetime.now().isoformat()}] ERROR in analysis cycle: {e}")
            import traceback
            traceback.print_exc()
            if running:
                print(f"[{datetime.now().isoformat()}] Retrying in 60s...")
                time.sleep(60)

    print(f"[{datetime.now().isoformat()}] Live Intelligence System stopped after {cycle_count} cycles.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
