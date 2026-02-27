#!/usr/bin/env python3
"""
Live Intelligence Report Viewer
================================

Displays the current live intelligence report in a human-readable format.

Usage:
  python3 scripts/view-live-intelligence.py
  python3 scripts/view-live-intelligence.py --watch  # Auto-refresh every 30s
"""

import json
import sys
import time
import os
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_FILE = BASE_DIR / "logs" / "live-intelligence-report.json"

def clear_screen():
    """Clear terminal screen."""
    os.system('clear' if os.name != 'nt' else 'cls')

def format_timestamp(ts_str):
    """Format timestamp for display."""
    if not ts_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ts_str

def display_report():
    """Display the live intelligence report."""
    if not REPORT_FILE.exists():
        print("No report found. Live Intelligence System may not be running.")
        print(f"Expected: {REPORT_FILE}")
        return False

    try:
        with open(REPORT_FILE, "r", encoding="utf-8") as f:
            report = json.load(f)
    except Exception as e:
        print(f"Error reading report: {e}")
        return False

    # Header
    print("=" * 80)
    print("  LIVE INTELLIGENCE REPORT")
    print("=" * 80)
    print(f"Generated: {format_timestamp(report.get('generated_at'))}")
    print(f"Analysis window: {report.get('analysis_window_hours', 'N/A')} hours")
    print(f"Cycle interval: {report.get('cycle_interval_seconds', 0) // 60} minutes")
    print()

    # Pipeline Health
    print("--- PIPELINE HEALTH ---")
    health = report.get("pipeline_health", {})
    if health:
        print(f"{'Pipeline':<20} {'Status':<12} {'Accuracy':<10} {'Trend':<12} {'Delta':<10} {'Strength':<10}")
        print("-" * 80)
        for pipeline, h in sorted(health.items()):
            status = h.get("status", "unknown")
            acc = h.get("current_accuracy")
            acc_str = f"{acc:.1f}%" if acc is not None else "N/A"
            trend = h.get("trend", "N/A")
            delta = h.get("trend_delta", 0)
            delta_str = f"{delta:+.1f}%" if delta else "0.0%"
            strength = h.get("trend_strength", 0)
            strength_str = f"{strength:.2f}"

            # Color code status
            status_icon = {"ok": "✓", "degraded": "!", "critical": "!!", "no_data": "?"}
            icon = status_icon.get(status, "?")

            print(f"{pipeline:<20} [{icon}] {status:<8} {acc_str:<10} {trend:<12} {delta_str:<10} {strength_str:<10}")
    else:
        print("  No pipeline health data available.")
    print()

    # Alerts
    alerts = report.get("alerts", [])
    if alerts:
        print(f"--- ALERTS ({len(alerts)}) ---")
        for alert in alerts:
            severity = alert.get("severity", "unknown")
            message = alert.get("message", "")
            print(f"  [{severity.upper()}] {message}")
        print()

    # Recommendations
    recs = report.get("recommendations", [])
    if recs:
        print(f"--- RECOMMENDATIONS ({len(recs)}) ---")
        # Group by priority
        high = [r for r in recs if r.get("priority") == "high"]
        medium = [r for r in recs if r.get("priority") == "medium"]
        low = [r for r in recs if r.get("priority") == "low"]

        if high:
            print(f"\n  HIGH PRIORITY ({len(high)}):")
            for r in high:
                print(f"    - {r.get('action', '')}")
                print(f"      Reason: {r.get('reason', '')[:70]}")

        if medium:
            print(f"\n  MEDIUM PRIORITY ({len(medium)}):")
            for r in medium:
                print(f"    - {r.get('action', '')}")

        if low:
            print(f"\n  LOW PRIORITY ({len(low)}):")
            for r in low[:5]:  # Show first 5 only
                print(f"    - {r.get('action', '')}")
            if len(low) > 5:
                print(f"    ... and {len(low) - 5} more")
        print()

    # Failure Patterns
    failure_patterns = report.get("failure_patterns", [])
    if failure_patterns:
        print(f"--- FAILURE PATTERNS ({len(failure_patterns)}) ---")
        for fp in failure_patterns[:5]:
            pipeline = fp.get("pipeline", "unknown")
            failure_rate = fp.get("failure_rate", 0)
            failure_count = fp.get("failure_count", 0)
            total_runs = fp.get("total_runs", 0)
            print(f"  {pipeline:<20} {failure_rate:>5.1f}% failure rate ({failure_count}/{total_runs} runs)")
        print()

    # Fix Summary
    fix_summary = report.get("fix_summary", {})
    if fix_summary:
        print("--- FIX SUMMARY ---")
        print(f"  Total fixes: {fix_summary.get('total_fixes', 0)}")
        print(f"  Anti-patterns: {fix_summary.get('total_anti_patterns', 0)}")
        category_counts = fix_summary.get("category_counts", {})
        if category_counts:
            print("  Top categories:")
            for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"    {cat}: {count} fixes")
        print()

    # Data Freshness
    freshness = report.get("data_freshness", {})
    print("--- DATA FRESHNESS ---")
    print(f"  Pipeline results: {freshness.get('pipeline_results_count', 0)} entries")
    print(f"  Oldest: {format_timestamp(freshness.get('oldest_result'))}")
    print(f"  Newest: {format_timestamp(freshness.get('newest_result'))}")
    print(f"  Monitor events: {report.get('monitor_events_count', 0)}")
    print()

    print("=" * 80)
    print(f"Report file: {REPORT_FILE}")
    print("=" * 80)

    return True

def main():
    """Main entry point."""
    watch_mode = "--watch" in sys.argv

    if watch_mode:
        print("Watch mode enabled. Press Ctrl+C to exit.")
        print()
        try:
            while True:
                clear_screen()
                display_report()
                print("\nRefreshing in 30 seconds...")
                time.sleep(30)
        except KeyboardInterrupt:
            print("\nExiting watch mode.")
            return 0
    else:
        display_report()
        return 0

if __name__ == "__main__":
    sys.exit(main())
