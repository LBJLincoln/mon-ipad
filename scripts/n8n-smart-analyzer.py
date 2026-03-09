#!/usr/bin/env python3
"""
n8n Smart Execution Analyzer — LLM-powered deep analysis of pipeline health.

For each execution:
- Extracts ALL node timings, inputs, outputs, errors
- Identifies bottleneck nodes (top 3 slowest)
- Detects failing nodes with error classification
- Computes node-level success rates across executions
- Uses LLM (via LiteLLM proxy) to analyze patterns and suggest improvements

Usage:
  source .env.local
  python3 scripts/n8n-smart-analyzer.py                    # Analyze last 10 execs
  python3 scripts/n8n-smart-analyzer.py --deep             # Deep analysis with LLM
  python3 scripts/n8n-smart-analyzer.py --workflow TmgyRP  # Specific workflow
  python3 scripts/n8n-smart-analyzer.py --hours 24         # Last 24h only
"""

import json
import os
import sys
import time
import argparse
import urllib.request
import urllib.error
import http.cookiejar
from collections import defaultdict
from datetime import datetime, timedelta

HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")
CI_EMAIL = os.environ.get("N8N_CI_EMAIL", "ci@nomos.ai")
CI_PASSWORD = os.environ.get("N8N_CI_PASSWORD", "CI-Nomos-2026!")
LITELLM_URL = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-litellm-nomos-2026")

PIPELINE_IDS = {
    "TmgyRP20N4JFd9CB": "Standard",
    "6257AfT1l4FMC6lY": "Graph",
    "cjhEhVs0KV1ExHqX": "Quant",
    "ALd4gOEqiKL5KR1p": "Orchestrator",
}

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(REPO_ROOT, "logs")


# ─── n8n API helpers ────────────────────────────────────────────────────

def get_opener():
    cj = http.cookiejar.MozillaCookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    data = json.dumps({"emailOrLdapLoginId": CI_EMAIL, "password": CI_PASSWORD}).encode()
    req = urllib.request.Request(f"{HOST}/rest/login", data=data,
                                headers={"Content-Type": "application/json"}, method="POST")
    opener.open(req, timeout=20)
    return opener


def api_get(opener, path, timeout=30):
    req = urllib.request.Request(f"{HOST}/rest{path}", method="GET")
    resp = opener.open(req, timeout=timeout)
    data = json.loads(resp.read().decode())
    return data.get("data", data)


# ─── Execution data extraction ──────────────────────────────────────────

def extract_run_data(opener, exec_id):
    """Extract node-by-node run data from an execution."""
    try:
        data = api_get(opener, f"/executions/{exec_id}?includeData=true")
    except Exception:
        return None

    exec_data_raw = data.get("data", "")

    # Parse the potentially compressed/nested format
    if isinstance(exec_data_raw, str):
        try:
            parsed = json.loads(exec_data_raw)
            if isinstance(parsed, list):
                for entry in reversed(parsed):
                    if isinstance(entry, dict) and "resultData" in entry:
                        parsed = entry
                        break
                else:
                    return None
            if not isinstance(parsed, dict):
                return None
        except (json.JSONDecodeError, TypeError):
            return None
    elif isinstance(exec_data_raw, dict):
        parsed = exec_data_raw
    else:
        return None

    result_data = parsed.get("resultData", {})
    if isinstance(result_data, str):
        try:
            result_data = json.loads(result_data)
        except (json.JSONDecodeError, TypeError):
            return None
    if not isinstance(result_data, dict):
        return None

    return result_data.get("runData", {})


def analyze_nodes(run_data):
    """Deep analysis of each node in an execution."""
    nodes = []
    for node_name, runs in run_data.items():
        if not runs or not isinstance(runs, list):
            continue
        run = runs[0] if isinstance(runs[0], dict) else {}

        err = run.get("error")
        exec_time = run.get("executionTime", 0)

        main_data = run.get("data", {})
        if isinstance(main_data, dict):
            main = main_data.get("main", [[]])
        else:
            main = [[]]
        items = main[0] if main and isinstance(main[0], list) else []

        node_info = {
            "name": node_name,
            "items_out": len(items),
            "time_ms": exec_time,
            "error": None,
            "error_type": None,
            "output_preview": {},
        }

        if err:
            err_msg = err.get("message", str(err))[:500] if isinstance(err, dict) else str(err)[:500]
            node_info["error"] = err_msg
            # Classify error
            err_lower = err_msg.lower()
            if "timeout" in err_lower or "timedout" in err_lower:
                node_info["error_type"] = "TIMEOUT"
            elif "401" in err_lower or "403" in err_lower or "unauthorized" in err_lower:
                node_info["error_type"] = "AUTH"
            elif "429" in err_lower or "rate limit" in err_lower:
                node_info["error_type"] = "RATE_LIMIT"
            elif "500" in err_lower or "502" in err_lower or "503" in err_lower:
                node_info["error_type"] = "SERVER_ERROR"
            elif "connect" in err_lower or "econnrefused" in err_lower:
                node_info["error_type"] = "CONNECTION"
            elif "json" in err_lower or "parse" in err_lower:
                node_info["error_type"] = "PARSE_ERROR"
            else:
                node_info["error_type"] = "OTHER"

        # Extract key outputs for context
        if items and isinstance(items[0], dict):
            j = items[0].get("json", {})
            preview = {}
            for k in ["answer", "response", "error", "status", "fallback", "skip_neo4j",
                       "skip_graph", "valid", "dimensions", "context_sources",
                       "embedding_fallback", "results_count", "query"]:
                if k in j:
                    preview[k] = str(j[k])[:200]
            # Count items for array fields
            for k in ["matches", "results", "merged_results", "reranked_results"]:
                if k in j and isinstance(j[k], list):
                    preview[f"{k}_count"] = len(j[k])
            node_info["output_preview"] = preview

        nodes.append(node_info)

    return nodes


# ─── Aggregation ────────────────────────────────────────────────────────

def aggregate_analysis(all_execs_data):
    """Aggregate node-level stats across all executions."""
    node_stats = defaultdict(lambda: {
        "total_runs": 0, "errors": 0, "total_time_ms": 0,
        "times": [], "error_types": defaultdict(int), "error_messages": [],
    })

    for exec_info in all_execs_data:
        for node in exec_info.get("nodes", []):
            name = node["name"]
            stats = node_stats[name]
            stats["total_runs"] += 1
            stats["times"].append(node["time_ms"])
            stats["total_time_ms"] += node["time_ms"]
            if node["error"]:
                stats["errors"] += 1
                stats["error_types"][node["error_type"]] += 1
                stats["error_messages"].append(node["error"][:200])

    # Compute derived metrics
    result = {}
    for name, stats in node_stats.items():
        times = stats["times"]
        result[name] = {
            "total_runs": stats["total_runs"],
            "error_count": stats["errors"],
            "error_rate": round(stats["errors"] / max(stats["total_runs"], 1) * 100, 1),
            "avg_time_ms": int(sum(times) / max(len(times), 1)),
            "max_time_ms": max(times) if times else 0,
            "min_time_ms": min(times) if times else 0,
            "total_time_ms": stats["total_time_ms"],
            "error_types": dict(stats["error_types"]),
            "sample_errors": stats["error_messages"][:3],
        }

    return result


# ─── LLM Analysis ──────────────────────────────────────────────────────

def llm_analyze(analysis_data, pipeline_name):
    """Use LLM to analyze execution patterns and suggest improvements."""
    # Build a concise summary for the LLM
    bottlenecks = sorted(analysis_data.items(), key=lambda x: x[1]["avg_time_ms"], reverse=True)[:5]
    error_nodes = [(n, d) for n, d in analysis_data.items() if d["error_count"] > 0]

    summary = f"Pipeline: {pipeline_name}\n\n"
    summary += "TOP 5 SLOWEST NODES:\n"
    for name, data in bottlenecks:
        summary += f"  {name}: avg={data['avg_time_ms']}ms, max={data['max_time_ms']}ms, runs={data['total_runs']}\n"

    if error_nodes:
        summary += f"\nFAILING NODES ({len(error_nodes)}):\n"
        for name, data in error_nodes:
            summary += f"  {name}: {data['error_count']}/{data['total_runs']} failures ({data['error_rate']}%)\n"
            summary += f"    Error types: {data['error_types']}\n"
            if data['sample_errors']:
                summary += f"    Sample: {data['sample_errors'][0][:150]}\n"

    summary += f"\nTOTAL NODES: {len(analysis_data)}\n"
    total_time = sum(d["avg_time_ms"] for d in analysis_data.values())
    summary += f"TOTAL AVG PIPELINE TIME: {total_time}ms ({total_time/1000:.1f}s)\n"

    prompt = f"""You are an n8n workflow optimization expert. Analyze this RAG pipeline execution data and provide:

1. **BOTTLENECK DIAGNOSIS** — Which nodes are the performance bottlenecks and why?
2. **ERROR ROOT CAUSE** — For any failing nodes, what's the likely root cause?
3. **TOP 3 IMPROVEMENTS** — Ranked by impact, what should be fixed first?
4. **ARCHITECTURE ISSUES** — Any structural problems in the pipeline flow?
5. **QUICK WINS** — Changes that would immediately improve performance/reliability

Be specific and actionable. Reference node names directly.

{summary}"""

    payload = json.dumps({
        "model": "gemma-27b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 800,
    }).encode()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LITELLM_KEY}",
    }

    try:
        req = urllib.request.Request(LITELLM_URL, data=payload, headers=headers, method="POST")
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode())
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"LLM analysis failed: {e}"


# ─── Report ─────────────────────────────────────────────────────────────

def print_deep_report(pipeline_name, node_stats, llm_insight=None):
    """Print deep analysis report for a pipeline."""
    print(f"\n{'=' * 70}")
    print(f"  DEEP ANALYSIS: {pipeline_name}")
    print(f"{'=' * 70}")

    # Bottleneck table
    sorted_by_time = sorted(node_stats.items(), key=lambda x: x[1]["avg_time_ms"], reverse=True)
    total_time = sum(d["avg_time_ms"] for d in node_stats.values())

    print(f"\n  NODE TIMING (total pipeline: {total_time/1000:.1f}s)")
    print(f"  {'Node':<45} {'Avg(ms)':>8} {'Max':>8} {'%':>6} {'Err%':>6}")
    print(f"  {'-' * 75}")
    for name, data in sorted_by_time[:15]:
        pct = data["avg_time_ms"] / max(total_time, 1) * 100
        marker = " <<<" if pct > 25 else " !!" if data["error_rate"] > 0 else ""
        print(f"  {name[:44]:<45} {data['avg_time_ms']:>8} {data['max_time_ms']:>8} "
              f"{pct:>5.1f}% {data['error_rate']:>5.1f}%{marker}")

    # Error analysis
    error_nodes = [(n, d) for n, d in node_stats.items() if d["error_count"] > 0]
    if error_nodes:
        print(f"\n  ERRORS ({len(error_nodes)} failing nodes)")
        print(f"  {'-' * 75}")
        for name, data in error_nodes:
            print(f"  {name}")
            print(f"    Failures: {data['error_count']}/{data['total_runs']} ({data['error_rate']}%)")
            print(f"    Types: {data['error_types']}")
            if data["sample_errors"]:
                print(f"    Example: {data['sample_errors'][0][:120]}")
    else:
        print(f"\n  No errors detected across all executions.")

    # Bottleneck identification
    if sorted_by_time:
        top = sorted_by_time[0]
        pct = top[1]["avg_time_ms"] / max(total_time, 1) * 100
        print(f"\n  BOTTLENECK: '{top[0]}' — {pct:.0f}% of total time ({top[1]['avg_time_ms']}ms avg)")

    # LLM insight
    if llm_insight:
        print(f"\n  {'=' * 70}")
        print(f"  LLM ANALYSIS (Gemma-27B)")
        print(f"  {'=' * 70}")
        for line in llm_insight.split("\n"):
            print(f"  {line}")

    print()


# ─── Main ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="n8n Smart Execution Analyzer")
    parser.add_argument("--hours", type=int, default=0, help="Filter to last N hours")
    parser.add_argument("--limit", type=int, default=20, help="Max executions to analyze")
    parser.add_argument("--workflow", type=str, help="Specific workflow ID")
    parser.add_argument("--deep", action="store_true", help="Include LLM analysis")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    print("Connecting to n8n...")
    opener = get_opener()

    # Determine which pipelines to analyze
    if args.workflow:
        pipelines = {args.workflow: PIPELINE_IDS.get(args.workflow, args.workflow)}
    else:
        pipelines = PIPELINE_IDS.copy()

    full_report = {"timestamp": datetime.utcnow().isoformat() + "Z", "pipelines": {}}

    for wf_id, pipeline_name in pipelines.items():
        print(f"\nAnalyzing {pipeline_name} ({wf_id})...")

        # Fetch executions for this workflow
        try:
            execs = api_get(opener, f"/executions?limit={args.limit}&workflowId={wf_id}")
            if isinstance(execs, dict):
                exec_list = execs.get("results", execs.get("data", []))
            elif isinstance(execs, list):
                exec_list = execs
            else:
                exec_list = []
        except Exception as e:
            print(f"  Failed to fetch executions: {e}")
            continue

        if not exec_list:
            print(f"  No executions found")
            continue

        # Filter by time
        if args.hours > 0:
            cutoff = datetime.utcnow() - timedelta(hours=args.hours)
            exec_list = [e for e in exec_list if e.get("startedAt", "")[:19] >= cutoff.isoformat()[:19]]

        print(f"  Found {len(exec_list)} executions")

        # Deep analysis of each execution
        all_exec_data = []
        for i, ex in enumerate(exec_list[:min(args.limit, 10)]):  # Analyze max 10 per pipeline
            exec_id = ex.get("id")
            if not exec_id:
                continue
            run_data = extract_run_data(opener, exec_id)
            if run_data:
                nodes = analyze_nodes(run_data)
                all_exec_data.append({
                    "exec_id": exec_id,
                    "status": ex.get("status"),
                    "nodes": nodes,
                })
                sys.stdout.write(f"\r  Analyzed {i+1}/{min(len(exec_list), 10)} executions")
                sys.stdout.flush()

        if not all_exec_data:
            print(f"\n  No execution data available (may be compressed)")
            continue

        print()

        # Aggregate stats
        node_stats = aggregate_analysis(all_exec_data)

        # LLM analysis if requested
        llm_insight = None
        if args.deep:
            print(f"  Running LLM analysis...")
            llm_insight = llm_analyze(node_stats, pipeline_name)

        # Print report
        if not args.json:
            print_deep_report(pipeline_name, node_stats, llm_insight)

        # Store for JSON output
        full_report["pipelines"][pipeline_name] = {
            "workflow_id": wf_id,
            "executions_analyzed": len(all_exec_data),
            "node_stats": node_stats,
            "llm_insight": llm_insight,
        }

    # Save report
    if args.json:
        print(json.dumps(full_report, indent=2))

    report_file = os.path.join(REPORT_DIR, "n8n-smart-analysis.json")
    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(report_file, "w") as f:
        json.dump(full_report, f, indent=2)
    print(f"\nReport saved to {report_file}")


if __name__ == "__main__":
    main()
