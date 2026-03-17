#!/usr/bin/env python3
"""
Metrics Analyzer — LLM-powered analysis of pipeline metrics.

Reads JSON metrics from data/metrics/, sends a structured summary to Groq LLM,
and produces health reports, bottleneck detection, regression alerts, capacity
analysis, and actionable recommendations.

Usage:
    source .env.local
    python3 ops/metrics-analyzer.py              # Full analysis
    python3 ops/metrics-analyzer.py --summary    # One-line summary only
    python3 ops/metrics-analyzer.py --alerts     # Only show alerts
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
METRICS_DIR = REPO_ROOT / "data" / "metrics"
REPORT_PATH = METRICS_DIR / "analysis_report.json"

METRICS_FILES = {
    "execution_log":      METRICS_DIR / "execution_log.json",
    "node_performance":   METRICS_DIR / "node_performance.json",
    "error_catalog":      METRICS_DIR / "error_catalog.json",
    "regression_tracker": METRICS_DIR / "regression_tracker.json",
}

PIPELINES = ["Standard", "Graph", "Quantitative", "Orchestrator"]

# ---------------------------------------------------------------------------
# Groq key rotation (same pattern as rag-proxy.py)
# ---------------------------------------------------------------------------
_GROQ_KEYS = [v for k, v in sorted(os.environ.items())
              if k.startswith("GROQ_API_KEY") and v]
if not _GROQ_KEYS:
    _GROQ_KEYS = [os.environ.get("GROQ_API_KEY", "")]
_groq_key_idx = 0


def _next_groq_key():
    """Round-robin through available Groq API keys."""
    global _groq_key_idx
    key = _GROQ_KEYS[_groq_key_idx % len(_GROQ_KEYS)]
    _groq_key_idx += 1
    return key


# Model fallback chain (Groq free tier)
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "qwen/qwen3-32b",
    "llama-3.1-8b-instant",
]

# Premium fallback providers (for critical analysis when Groq exhausted)
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
GEMINI_KEY = os.environ.get("GOOGLE_API_KEY", "")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict | list | None:
    """Load a JSON file, returning None on any error."""
    try:
        if not path.exists() or path.stat().st_size == 0:
            return None
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks (qwen models)."""
    if "<think>" in text:
        text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
    return text


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Metrics loading & pre-processing
# ---------------------------------------------------------------------------

def load_all_metrics() -> dict:
    """Load all metrics files and return a structured dict."""
    data = {}
    for name, path in METRICS_FILES.items():
        raw = _load_json(path)
        data[name] = raw
    return data


def build_metrics_summary(data: dict) -> str:
    """
    Build a compact text summary of metrics for the LLM prompt.
    Kept under ~1200 tokens so the total prompt stays small.
    """
    parts = []
    ts = _ts()
    parts.append(f"Metrics snapshot at {ts}")
    parts.append(f"Pipelines: {', '.join(PIPELINES)}")

    # --- Execution log ---
    execs = data.get("execution_log")
    if execs and isinstance(execs, list):
        total = len(execs)
        successes = sum(1 for e in execs if e.get("status") == "success"
                        or e.get("finished") is True
                        or e.get("success") is True)
        failures = total - successes
        parts.append(f"\n## Executions: {total} total, {successes} success, {failures} failures")
        # Per-pipeline breakdown
        by_pipeline = {}
        for e in execs:
            p = e.get("pipeline") or e.get("workflow") or "unknown"
            by_pipeline.setdefault(p, {"ok": 0, "fail": 0})
            is_ok = (e.get("status") == "success"
                     or e.get("finished") is True
                     or e.get("success") is True)
            by_pipeline[p]["ok" if is_ok else "fail"] += 1
        for p, c in sorted(by_pipeline.items()):
            rate = c["ok"] / max(c["ok"] + c["fail"], 1) * 100
            parts.append(f"  {p}: {c['ok']}/{c['ok']+c['fail']} ok ({rate:.0f}%)")
        # Avg duration
        durations = [e.get("duration") or e.get("duration_ms") or e.get("elapsed")
                     for e in execs if (e.get("duration") or e.get("duration_ms") or e.get("elapsed"))]
        durations = [d for d in durations if isinstance(d, (int, float)) and d > 0]
        if durations:
            parts.append(f"  Avg duration: {sum(durations)/len(durations):.1f}ms, "
                         f"P95: {sorted(durations)[int(len(durations)*0.95)]:.0f}ms")
    elif execs is None:
        parts.append("\n## Executions: NO DATA (execution_log.json missing/empty)")
    else:
        parts.append("\n## Executions: empty log")

    # --- Node performance ---
    nodes = data.get("node_performance")
    if nodes and isinstance(nodes, (list, dict)):
        items = nodes if isinstance(nodes, list) else nodes.values() if isinstance(nodes, dict) else []
        if isinstance(nodes, dict) and not isinstance(list(nodes.values())[0] if nodes else None, dict):
            # Flat key:value
            parts.append(f"\n## Node Performance: {len(nodes)} entries (flat)")
        else:
            items = list(items)
            parts.append(f"\n## Node Performance: {len(items)} nodes")
            # Top 5 slowest
            for_sort = []
            for n in items:
                if isinstance(n, dict):
                    avg = n.get("avg_ms") or n.get("avg_duration") or n.get("mean") or 0
                    name = n.get("name") or n.get("node") or "?"
                    errs = n.get("errors") or n.get("error_count") or 0
                    for_sort.append((name, avg, errs))
            if for_sort:
                for_sort.sort(key=lambda x: -x[1])
                parts.append("  Top 5 slowest nodes:")
                for name, avg, errs in for_sort[:5]:
                    parts.append(f"    {name}: avg {avg:.0f}ms, errors={errs}")
    elif nodes is None:
        parts.append("\n## Node Performance: NO DATA")

    # --- Error catalog ---
    errors = data.get("error_catalog")
    if errors and isinstance(errors, (list, dict)):
        items = errors if isinstance(errors, list) else list(errors.values())
        parts.append(f"\n## Error Catalog: {len(items)} error types")
        # Top 5 by count
        for_sort = []
        for e in items:
            if isinstance(e, dict):
                count = e.get("count") or e.get("occurrences") or 1
                msg = e.get("message") or e.get("error") or e.get("type") or "?"
                pipeline = e.get("pipeline") or e.get("workflow") or "?"
                for_sort.append((msg[:80], count, pipeline))
        if for_sort:
            for_sort.sort(key=lambda x: -x[1])
            parts.append("  Top 5 errors:")
            for msg, count, pipeline in for_sort[:5]:
                parts.append(f"    [{pipeline}] ({count}x) {msg}")
    elif errors is None:
        parts.append("\n## Error Catalog: NO DATA")

    # --- Regression tracker ---
    regressions = data.get("regression_tracker")
    if regressions and isinstance(regressions, (list, dict)):
        items = regressions if isinstance(regressions, list) else list(regressions.values())
        parts.append(f"\n## Regression Tracker: {len(items)} entries")
        alerts = []
        for r in items:
            if isinstance(r, dict):
                pipeline = r.get("pipeline") or r.get("name") or "?"
                prev = r.get("previous") or r.get("prev_accuracy") or r.get("baseline")
                curr = r.get("current") or r.get("accuracy") or r.get("latest")
                if isinstance(prev, (int, float)) and isinstance(curr, (int, float)):
                    delta = curr - prev
                    parts.append(f"  {pipeline}: {prev:.1f}% -> {curr:.1f}% (delta {delta:+.1f}%)")
                    if delta < -5:
                        alerts.append(f"REGRESSION {pipeline}: {delta:+.1f}%")
        if alerts:
            parts.append("  ** ALERTS: " + "; ".join(alerts))
    elif regressions is None:
        parts.append("\n## Regression Tracker: NO DATA")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Groq LLM call
# ---------------------------------------------------------------------------

def call_groq(prompt: str, max_tokens: int = 2000) -> tuple[str | None, str | None]:
    """
    Call Groq API with key rotation and model fallback.
    Returns (response_text, error_message).
    """
    import requests as req

    for model in GROQ_MODELS:
        for _attempt in range(len(_GROQ_KEYS)):
            key = _next_groq_key()
            if not key:
                continue
            try:
                r = req.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": 0.2,
                    },
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    timeout=60,
                )
                if r.status_code == 200:
                    content = r.json()["choices"][0]["message"]["content"]
                    return _strip_think_tags(content), None
                if r.status_code == 429:
                    continue  # try next key
                return None, f"Groq HTTP {r.status_code}: {r.text[:300]}"
            except Exception as e:
                if _attempt == len(_GROQ_KEYS) - 1:
                    break  # try next model
        # All keys exhausted for this model — fall through to next

    # Premium fallback: OpenAI
    if OPENAI_KEY:
        try:
            r = req.post("https://api.openai.com/v1/chat/completions",
                json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": max_tokens, "temperature": 0.2},
                headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                timeout=60)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"], None
        except Exception:
            pass

    # Premium fallback: Gemini
    if GEMINI_KEY:
        try:
            r = req.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}",
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2}},
                headers={"Content-Type": "application/json"}, timeout=60)
            if r.status_code == 200:
                content = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                return content, None
        except Exception:
            pass

    return None, "All LLM providers exhausted (Groq + OpenAI + Gemini)"


# ---------------------------------------------------------------------------
# Analysis prompt
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = """\
You are a DevOps metrics analyst for a RAG pipeline system (4 pipelines: Standard, Graph, Quantitative, Orchestrator).
Analyze the following metrics and produce a structured report.

METRICS:
{metrics_summary}

Produce EXACTLY this JSON structure (no markdown fences, pure JSON):
{{
  "timestamp": "<ISO UTC>",
  "health": {{
    "overall": "GREEN|YELLOW|RED",
    "pipelines": {{
      "Standard": {{"status": "GREEN|YELLOW|RED", "reason": "..."}},
      "Graph": {{"status": "GREEN|YELLOW|RED", "reason": "..."}},
      "Quantitative": {{"status": "GREEN|YELLOW|RED", "reason": "..."}},
      "Orchestrator": {{"status": "GREEN|YELLOW|RED", "reason": "..."}}
    }}
  }},
  "bottlenecks": [
    {{"node": "...", "issue": "...", "impact": "HIGH|MEDIUM|LOW"}}
  ],
  "regressions": [
    {{"pipeline": "...", "delta_pct": -0.0, "severity": "CRITICAL|WARNING|OK"}}
  ],
  "capacity": {{
    "volume_trend": "INCREASING|STABLE|DECREASING",
    "saturation_risk": "HIGH|MEDIUM|LOW|NONE",
    "notes": "..."
  }},
  "recommendations": [
    {{"rank": 1, "action": "...", "impact": "HIGH|MEDIUM|LOW", "effort": "LOW|MEDIUM|HIGH"}},
    {{"rank": 2, "action": "...", "impact": "...", "effort": "..."}},
    {{"rank": 3, "action": "...", "impact": "...", "effort": "..."}}
  ],
  "summary_oneliner": "One sentence max 120 chars summarizing system state"
}}

Rules:
- If data is missing for a pipeline, mark it YELLOW with reason "no data".
- GREEN = >95% success rate and no regressions. YELLOW = 80-95% or minor issues. RED = <80% or critical regression.
- Regressions >5% are CRITICAL. 2-5% are WARNING.
- Be specific and actionable in recommendations.
- Output ONLY valid JSON, no explanation before or after.
"""


def _fallback_report(metrics_summary: str, error: str) -> dict:
    """Generate a best-effort report without LLM when Groq is unavailable."""
    ts = _ts()
    report = {
        "timestamp": ts,
        "llm_error": error,
        "health": {
            "overall": "YELLOW",
            "pipelines": {p: {"status": "YELLOW", "reason": "LLM unavailable — manual review needed"}
                          for p in PIPELINES},
        },
        "bottlenecks": [],
        "regressions": [],
        "capacity": {
            "volume_trend": "UNKNOWN",
            "saturation_risk": "UNKNOWN",
            "notes": f"LLM analysis failed: {error}",
        },
        "recommendations": [
            {"rank": 1, "action": "Fix Groq API access to enable automated analysis",
             "impact": "HIGH", "effort": "LOW"},
        ],
        "summary_oneliner": f"Analysis degraded — Groq unavailable ({error[:60]})",
        "raw_metrics_summary": metrics_summary,
    }
    return report


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def run_analysis() -> dict:
    """Run full metrics analysis. Returns the report dict."""
    # Load metrics
    data = load_all_metrics()
    metrics_summary = build_metrics_summary(data)

    # Check if we have ANY data at all
    has_data = any(v is not None for v in data.values())

    if not has_data:
        ts = _ts()
        return {
            "timestamp": ts,
            "health": {
                "overall": "YELLOW",
                "pipelines": {p: {"status": "YELLOW", "reason": "no metrics data found"}
                              for p in PIPELINES},
            },
            "bottlenecks": [],
            "regressions": [],
            "capacity": {
                "volume_trend": "UNKNOWN",
                "saturation_risk": "UNKNOWN",
                "notes": "No metrics files found in data/metrics/. Populate execution_log.json, "
                         "node_performance.json, error_catalog.json, regression_tracker.json.",
            },
            "recommendations": [
                {"rank": 1, "action": "Set up metrics collection to populate data/metrics/ JSON files",
                 "impact": "HIGH", "effort": "MEDIUM"},
                {"rank": 2, "action": "Run eval/quick-test.py --sector all to generate baseline data",
                 "impact": "HIGH", "effort": "LOW"},
                {"rank": 3, "action": "Enable auto-healer cron to collect execution logs automatically",
                 "impact": "MEDIUM", "effort": "LOW"},
            ],
            "summary_oneliner": "No metrics data — run pipelines and collect logs first",
            "raw_metrics_summary": metrics_summary,
        }

    # Call LLM
    prompt = ANALYSIS_PROMPT.format(metrics_summary=metrics_summary)
    response, error = call_groq(prompt, max_tokens=2000)

    if error or not response:
        return _fallback_report(metrics_summary, error or "empty response")

    # Parse JSON from response
    # Handle cases where LLM wraps in markdown fences
    cleaned = response.strip()
    if cleaned.startswith("```"):
        # Remove ```json ... ```
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        report = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract JSON object from the response
        match = re.search(r"\{[\s\S]+\}", cleaned)
        if match:
            try:
                report = json.loads(match.group())
            except json.JSONDecodeError:
                report = _fallback_report(metrics_summary, f"LLM returned invalid JSON")
                report["llm_raw_response"] = response[:500]
                return report
        else:
            report = _fallback_report(metrics_summary, "LLM returned no JSON")
            report["llm_raw_response"] = response[:500]
            return report

    # Ensure timestamp
    if "timestamp" not in report:
        report["timestamp"] = _ts()

    # Attach raw summary for debugging
    report["raw_metrics_summary"] = metrics_summary

    return report


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

STATUS_COLORS = {"GREEN": "\033[92m", "YELLOW": "\033[93m", "RED": "\033[91m"}
RESET = "\033[0m"


def _color(status: str) -> str:
    c = STATUS_COLORS.get(status, "")
    return f"{c}{status}{RESET}" if c else status


def print_full_report(report: dict):
    """Print human-readable report to stdout."""
    ts = report.get("timestamp", "?")
    print(f"\n{'='*60}")
    print(f"  METRICS ANALYSIS REPORT  —  {ts}")
    print(f"{'='*60}")

    # Health
    health = report.get("health", {})
    overall = health.get("overall", "UNKNOWN")
    print(f"\n  Overall Health: {_color(overall)}")
    print(f"  {'─'*40}")
    pipelines = health.get("pipelines", {})
    for p in PIPELINES:
        info = pipelines.get(p, {})
        st = info.get("status", "UNKNOWN")
        reason = info.get("reason", "")
        print(f"    {p:15s} {_color(st):>20s}  {reason}")

    # Bottlenecks
    bottlenecks = report.get("bottlenecks", [])
    if bottlenecks:
        print(f"\n  Bottlenecks")
        print(f"  {'─'*40}")
        for b in bottlenecks:
            node = b.get("node", "?")
            issue = b.get("issue", "?")
            impact = b.get("impact", "?")
            print(f"    [{impact}] {node}: {issue}")

    # Regressions
    regressions = report.get("regressions", [])
    alerts = [r for r in regressions if r.get("severity") in ("CRITICAL", "WARNING")]
    if alerts:
        print(f"\n  Regression Alerts")
        print(f"  {'─'*40}")
        for r in alerts:
            pipeline = r.get("pipeline", "?")
            delta = r.get("delta_pct", 0)
            severity = r.get("severity", "?")
            color = "\033[91m" if severity == "CRITICAL" else "\033[93m"
            print(f"    {color}{severity}{RESET} {pipeline}: {delta:+.1f}%")
    elif regressions:
        print(f"\n  Regressions: None detected")

    # Capacity
    capacity = report.get("capacity", {})
    if capacity:
        print(f"\n  Capacity")
        print(f"  {'─'*40}")
        print(f"    Volume trend:    {capacity.get('volume_trend', '?')}")
        print(f"    Saturation risk: {capacity.get('saturation_risk', '?')}")
        notes = capacity.get("notes", "")
        if notes:
            print(f"    Notes: {notes}")

    # Recommendations
    recs = report.get("recommendations", [])
    if recs:
        print(f"\n  Top Recommendations")
        print(f"  {'─'*40}")
        for r in recs:
            rank = r.get("rank", "?")
            action = r.get("action", "?")
            impact = r.get("impact", "?")
            effort = r.get("effort", "?")
            print(f"    #{rank}  [{impact} impact / {effort} effort]")
            print(f"        {action}")

    # LLM error
    llm_err = report.get("llm_error")
    if llm_err:
        print(f"\n  \033[93mNote: LLM analysis failed ({llm_err}) — report is best-effort\033[0m")

    print(f"\n{'='*60}\n")


def print_summary(report: dict):
    """Print one-line summary for cron notification."""
    oneliner = report.get("summary_oneliner", "No summary available")
    overall = report.get("health", {}).get("overall", "?")
    ts = report.get("timestamp", "?")
    print(f"[{ts}] [{overall}] {oneliner}")


def print_alerts(report: dict):
    """Print only alerts (regressions and errors)."""
    ts = report.get("timestamp", "?")
    has_alerts = False

    # Regression alerts
    regressions = report.get("regressions", [])
    critical = [r for r in regressions if r.get("severity") == "CRITICAL"]
    warnings = [r for r in regressions if r.get("severity") == "WARNING"]

    if critical or warnings:
        has_alerts = True
        print(f"\n  ALERTS — {ts}")
        print(f"  {'─'*40}")
        for r in critical:
            print(f"  \033[91mCRITICAL\033[0m {r.get('pipeline','?')}: {r.get('delta_pct',0):+.1f}% regression")
        for r in warnings:
            print(f"  \033[93mWARNING\033[0m  {r.get('pipeline','?')}: {r.get('delta_pct',0):+.1f}% regression")

    # RED pipelines
    health = report.get("health", {})
    red_pipes = [p for p, info in health.get("pipelines", {}).items()
                 if info.get("status") == "RED"]
    if red_pipes:
        has_alerts = True
        print(f"\n  RED Pipelines: {', '.join(red_pipes)}")
        for p in red_pipes:
            reason = health["pipelines"][p].get("reason", "")
            print(f"    {p}: {reason}")

    # LLM error
    llm_err = report.get("llm_error")
    if llm_err:
        has_alerts = True
        print(f"\n  \033[93mLLM unavailable: {llm_err}\033[0m")

    if not has_alerts:
        print(f"[{ts}] No alerts — all pipelines nominal")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Analyze pipeline metrics with Groq LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Reads from data/metrics/*.json. Set GROQ_API_KEY* env vars.",
    )
    parser.add_argument("--summary", action="store_true",
                        help="One-line summary only (for cron)")
    parser.add_argument("--alerts", action="store_true",
                        help="Show only alerts (regressions, RED pipelines)")
    parser.add_argument("--no-save", action="store_true",
                        help="Do not write analysis_report.json")
    args = parser.parse_args()

    # Check for Groq keys
    if not any(k for k in _GROQ_KEYS if k):
        print("WARNING: No GROQ_API_KEY* env vars found. Run: source .env.local",
              file=sys.stderr)

    # Run analysis
    report = run_analysis()

    # Save JSON report
    if not args.no_save:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        with open(REPORT_PATH, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    # Output
    if args.summary:
        print_summary(report)
    elif args.alerts:
        print_alerts(report)
    else:
        print_full_report(report)
        if not args.no_save:
            print(f"  JSON report saved to: {REPORT_PATH}")

    # Exit code: 2 for RED, 1 for YELLOW, 0 for GREEN
    overall = report.get("health", {}).get("overall", "YELLOW")
    if overall == "RED":
        sys.exit(2)
    elif overall == "YELLOW":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
