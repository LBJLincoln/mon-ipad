#!/usr/bin/env python3
"""
Node-by-Node Execution Analyzer — Automated Pipeline Diagnostics
================================================================
After each eval stage (every 5/10/50 questions), this module:
  1. Fetches n8n execution logs for the tested questions
  2. Parses each node's full output (tokens, routing flags, LLM content)
  3. Detects issues: verbose LLM, token waste, routing failures, latency bottlenecks
  4. Generates actionable diagnostic reports with suggested JSON patches

The goal: automate what a human does when inspecting n8n execution nodes manually.

Usage:
  # As module (called by iterative-eval.py after each stage):
  from node_analyzer import analyze_stage
  report = analyze_stage("graph", questions_tested, stage_name="Stage 1: Smoke (5q)")

  # Standalone:
  python eval/node-analyzer.py --pipeline graph --last 5
  python eval/node-analyzer.py --pipeline orchestrator --execution-id 18352
  python eval/node-analyzer.py --all --last 10
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from collections import defaultdict
from urllib import request, error

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(EVAL_DIR)
DIAG_DIR = os.path.join(REPO_ROOT, "logs", "diagnostics")
N8N_LIVE_DIR = os.path.join(REPO_ROOT, "logs", "n8n-live")
os.makedirs(DIAG_DIR, exist_ok=True)

N8N_HOST = os.environ.get("N8N_HOST", "http://34.136.180.66:5678")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "")

WORKFLOW_IDS = {
    "standard": "M12n4cmiVBoBusUe",
    "graph": "Vxm4TDdOLdb7j3Jy",
    "quantitative": "nQnAJyT06NTbEQ3y",
    "orchestrator": "P1no6VZkNtnRdlBi",
}

# ============================================================
# Thresholds for automated issue detection
# ============================================================
THRESHOLDS = {
    "llm_verbose_chars": 500,       # LLM output > this = verbose warning
    "llm_very_verbose_chars": 1500, # LLM output > this = critical verbose
    "node_slow_ms": 5000,           # Node > 5s = slow
    "node_very_slow_ms": 15000,     # Node > 15s = very slow
    "total_slow_ms": 30000,         # Total execution > 30s = slow
    "total_very_slow_ms": 60000,    # Total > 60s = critical
    "max_completion_tokens": 500,   # LLM completion > 500 tokens = verbose
    "empty_context_warning": True,  # Flag when no context docs retrieved
}

# Node categories for smarter analysis
LLM_NODE_KEYWORDS = ["llm", "generation", "chat", "completion", "gpt", "hyde", "entity extraction",
                      "query decomposer", "answer", "synthesis"]
RETRIEVAL_NODE_KEYWORDS = ["pinecone", "neo4j", "supabase", "postgres", "search", "query", "bm25",
                           "embedding", "vector"]
ROUTING_NODE_KEYWORDS = ["router", "switch", "if", "merge", "wait", "branch", "decomposition",
                         "orchestrat"]


def _is_node_type(name, keywords):
    """Check if a node name matches a category."""
    name_lower = name.lower()
    return any(kw in name_lower for kw in keywords)


# ============================================================
# n8n API — Rich Execution Fetcher
# ============================================================
def n8n_api(path, timeout=30):
    """Call n8n REST API."""
    url = f"{N8N_HOST}/api/v1{path}"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if N8N_API_KEY:
        headers["X-N8N-API-KEY"] = N8N_API_KEY
    req = request.Request(url, headers=headers)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except error.HTTPError as e:
        body = e.read().decode()[:200] if e.fp else ""
        print(f"  [node-analyzer] n8n API error: {e.code} — {body}")
        return None
    except Exception as e:
        print(f"  [node-analyzer] n8n API error: {e}")
        return None


def fetch_rich_executions(pipeline, limit=10, since_minutes=30):
    """Fetch executions with FULL node data (not truncated)."""
    wf_id = WORKFLOW_IDS.get(pipeline)
    if not wf_id:
        return []

    path = f"/executions?workflowId={wf_id}&limit={limit}&includeData=true"
    result = n8n_api(path)
    if not result:
        return []

    executions = []
    for raw_exec in result.get("data", []):
        parsed = parse_rich_execution(raw_exec, pipeline)
        if parsed:
            executions.append(parsed)

    return executions


def fetch_execution_by_id(exec_id):
    """Fetch a single execution with full data."""
    result = n8n_api(f"/executions/{exec_id}?includeData=true")
    if not result:
        return None
    # Determine pipeline from workflow ID
    wf_id = result.get("workflowId", "")
    pipeline = {v: k for k, v in WORKFLOW_IDS.items()}.get(wf_id, "unknown")
    return parse_rich_execution(result, pipeline)


def parse_rich_execution(raw, pipeline):
    """Parse execution with FULL node data extraction — no truncation."""
    exec_id = raw.get("id", "unknown")
    status = raw.get("status", "unknown")
    started = raw.get("startedAt", "")
    finished = raw.get("stoppedAt", "")

    run_data = raw.get("data", {}).get("resultData", {}).get("runData", {})
    if not run_data:
        return None

    # Extract trigger query
    trigger_query = ""
    for node_name, runs in run_data.items():
        if "webhook" in node_name.lower() or "trigger" in node_name.lower():
            if isinstance(runs, list) and runs:
                out = runs[0].get("data", {}).get("main", [[]])
                if out and isinstance(out[0], list) and out[0]:
                    item = out[0][0].get("json", {})
                    trigger_query = item.get("query", item.get("question", ""))

    # Parse each node with RICH data
    nodes = []
    for node_name, node_runs in run_data.items():
        if not isinstance(node_runs, list):
            continue
        for run in node_runs:
            node = _parse_rich_node(node_name, run)
            nodes.append(node)

    # Compute total duration
    duration_ms = 0
    if started and finished:
        try:
            s = datetime.fromisoformat(started.replace("Z", "+00:00"))
            e = datetime.fromisoformat(finished.replace("Z", "+00:00"))
            duration_ms = int((e - s).total_seconds() * 1000)
        except (ValueError, TypeError):
            pass

    return {
        "execution_id": exec_id,
        "pipeline": pipeline,
        "status": status,
        "started_at": started,
        "finished_at": finished,
        "duration_ms": duration_ms,
        "trigger_query": str(trigger_query)[:300],
        "nodes": nodes,
        "node_count": len(nodes),
    }


def _parse_rich_node(name, run):
    """Extract rich data from a single node execution."""
    node = {
        "name": name,
        "duration_ms": run.get("executionTime", 0),
        "status": "error" if run.get("error") else "success",
        "error": None,
        # Rich fields
        "llm_output": None,
        "llm_tokens": None,
        "llm_model": None,
        "llm_provider": None,
        "routing_flags": {},
        "items_in": 0,
        "items_out": 0,
        "output_keys": [],
        "output_preview": None,
    }

    # Error extraction
    if run.get("error"):
        err = run["error"]
        node["error"] = err.get("message", str(err))[:1000] if isinstance(err, dict) else str(err)[:1000]

    # Input/output counts
    input_data = run.get("inputData", {}).get("main", [])
    output_data = run.get("data", {}).get("main", [])
    if input_data:
        node["items_in"] = sum(len(d) if isinstance(d, list) else 0 for d in input_data)
    if output_data:
        node["items_out"] = sum(len(d) if isinstance(d, list) else 0 for d in output_data)

    # Capture input preview (what the node received)
    first_input = _get_first_output_item(input_data)  # Same structure as output
    if first_input:
        node["input_preview"] = json.dumps(first_input, ensure_ascii=False)[:1000]
        node["input_keys"] = list(first_input.keys())[:20]

    # Extract first output item for analysis
    first_item = _get_first_output_item(output_data)
    if first_item:
        node["output_keys"] = list(first_item.keys())[:30]
        node["output_preview"] = json.dumps(first_item, ensure_ascii=False)[:2000]

        # LLM-specific extraction
        if "choices" in first_item:
            _extract_llm_data(node, first_item)

        # Routing flags extraction
        _extract_routing_flags(node, first_item)

        # Token budgeting extraction
        if "tokens_used" in first_item or "tokens_remaining" in first_item:
            node["token_budget"] = {
                "used": first_item.get("tokens_used", 0),
                "remaining": first_item.get("tokens_remaining", 0),
            }

        # Conditional flow tracing (IF/Switch path detection)
        if _is_node_type(name, ROUTING_NODE_KEYWORDS):
            # Track which output branches have items
            if output_data and isinstance(output_data, list):
                active_branches = []
                for branch_idx, branch in enumerate(output_data):
                    if isinstance(branch, list) and len(branch) > 0:
                        active_branches.append(branch_idx)
                node["active_branches"] = active_branches
                node["total_branches"] = len(output_data)

        # Context/retrieval data
        if "results" in first_item and isinstance(first_item["results"], list):
            node["retrieval_count"] = len(first_item["results"])
        if "metadata" in first_item and isinstance(first_item["metadata"], dict):
            meta = first_item["metadata"]
            node["retrieval_metadata"] = {
                "sources_available": meta.get("sources_available", 0),
                "total_unique_docs": meta.get("total_unique_docs", 0),
                "warnings": meta.get("warnings", []),
            }

    return node


def _get_first_output_item(output_data):
    """Safely extract the first JSON item from node output."""
    if not output_data or not isinstance(output_data, list):
        return None
    if not output_data[0] or not isinstance(output_data[0], list):
        return None
    if not output_data[0][0]:
        return None
    item = output_data[0][0]
    if isinstance(item, dict):
        return item.get("json", item)
    return None


def _extract_llm_data(node, item):
    """Extract LLM-specific data: content, tokens, model."""
    choices = item.get("choices", [])
    if choices and isinstance(choices, list):
        msg = choices[0].get("message", {})
        content = msg.get("content", "")
        node["llm_output"] = {
            "content": content[:3000],
            "length_chars": len(content),
            "finish_reason": choices[0].get("finish_reason", ""),
        }

    usage = item.get("usage", {})
    if usage:
        node["llm_tokens"] = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "cost": usage.get("cost", 0),
        }

    node["llm_model"] = item.get("model", "")
    node["llm_provider"] = item.get("provider", "")


def _extract_routing_flags(node, item):
    """Extract boolean routing/skip flags from node output."""
    flag_keys = [
        "skip_neo4j", "skip_graph", "skip_llm", "skip_reranker",
        "fallback", "embedding_fallback", "empty_database",
        "is_simple", "is_decomposed", "needs_decomposition",
        "reranked", "hyde_success",
    ]
    for key in flag_keys:
        if key in item:
            node["routing_flags"][key] = item[key]

    # Also extract from nested structures
    if "fallback_response" in item:
        node["routing_flags"]["has_fallback_response"] = True


# ============================================================
# Issue Detection Engine
# ============================================================
def detect_node_issues(node):
    """Analyze a single node and detect issues."""
    issues = []
    name = node["name"]

    # 1. LLM Verbosity check
    if node.get("llm_output"):
        length = node["llm_output"]["length_chars"]
        if length > THRESHOLDS["llm_very_verbose_chars"]:
            issues.append({
                "type": "VERBOSE_LLM_CRITICAL",
                "severity": "high",
                "node": name,
                "detail": f"LLM output is {length} chars — likely producing near-final answers instead of intermediate results",
                "metric": {"output_chars": length},
                "suggestion": "Constrain the system prompt to output ONLY the required intermediate data (entities, SQL, routing decision). Add max_tokens limit.",
            })
        elif length > THRESHOLDS["llm_verbose_chars"]:
            issues.append({
                "type": "VERBOSE_LLM",
                "severity": "medium",
                "node": name,
                "detail": f"LLM output is {length} chars — may be overly detailed for an intermediate step",
                "metric": {"output_chars": length},
                "suggestion": "Consider adding max_tokens constraint or simplifying the prompt.",
            })

    # 2. Token usage check
    if node.get("llm_tokens"):
        comp = node["llm_tokens"]["completion_tokens"]
        if comp > THRESHOLDS["max_completion_tokens"]:
            issues.append({
                "type": "HIGH_TOKEN_USAGE",
                "severity": "medium",
                "node": name,
                "detail": f"Completion tokens: {comp} (threshold: {THRESHOLDS['max_completion_tokens']})",
                "metric": {"completion_tokens": comp, "prompt_tokens": node["llm_tokens"]["prompt_tokens"]},
                "suggestion": "Reduce completion length via max_tokens parameter or streamline the prompt.",
            })

    # 3. Latency check
    dur = node.get("duration_ms", 0)
    if dur > THRESHOLDS["node_very_slow_ms"]:
        issues.append({
            "type": "VERY_SLOW_NODE",
            "severity": "high",
            "node": name,
            "detail": f"Node took {dur}ms (>{THRESHOLDS['node_very_slow_ms']}ms threshold)",
            "metric": {"duration_ms": dur},
            "suggestion": "Check if this node is making external API calls that could be cached or parallelized.",
        })
    elif dur > THRESHOLDS["node_slow_ms"]:
        issues.append({
            "type": "SLOW_NODE",
            "severity": "low",
            "node": name,
            "detail": f"Node took {dur}ms (>{THRESHOLDS['node_slow_ms']}ms threshold)",
            "metric": {"duration_ms": dur},
            "suggestion": "Monitor — may be acceptable for LLM/embedding calls.",
        })

    # 4. Error check
    if node.get("error"):
        err = node["error"]
        severity = "high"
        err_type = "NODE_ERROR"
        if "402" in err or "credit" in err.lower():
            err_type = "CREDITS_EXHAUSTED"
            severity = "critical"
        elif "429" in err or "rate" in err.lower():
            err_type = "RATE_LIMITED"
            severity = "high"
        elif "400" in err:
            err_type = "BAD_REQUEST"

        issues.append({
            "type": err_type,
            "severity": severity,
            "node": name,
            "detail": err[:300],
            "suggestion": _error_suggestion(err_type, name),
        })

    # 5. Empty output check
    if node.get("items_out", 0) == 0 and node["status"] == "success":
        if _is_node_type(name, RETRIEVAL_NODE_KEYWORDS):
            issues.append({
                "type": "EMPTY_RETRIEVAL",
                "severity": "high",
                "node": name,
                "detail": "Retrieval node returned 0 items",
                "suggestion": "Check query formation, index configuration, or embedding quality.",
            })

    # 6. Routing flag checks
    flags = node.get("routing_flags", {})
    if flags.get("empty_database"):
        issues.append({
            "type": "EMPTY_DATABASE",
            "severity": "critical",
            "node": name,
            "detail": "Database flagged as empty — no documents to search",
            "suggestion": "Verify data ingestion and index population.",
        })
    if flags.get("embedding_fallback"):
        issues.append({
            "type": "EMBEDDING_FALLBACK",
            "severity": "medium",
            "node": name,
            "detail": "Using embedding fallback — primary embedding failed",
            "suggestion": "Check OpenRouter credits or embedding API configuration.",
        })

    # 7. Retrieval quality check
    if node.get("retrieval_metadata"):
        meta = node["retrieval_metadata"]
        if meta.get("total_unique_docs", 0) == 0 and meta.get("sources_available", 0) == 0:
            issues.append({
                "type": "ZERO_RETRIEVAL",
                "severity": "critical",
                "node": name,
                "detail": f"0 documents retrieved. Warnings: {meta.get('warnings', [])}",
                "suggestion": "Check embedding generation, vector index, and query formation.",
            })

    return issues


def _error_suggestion(err_type, node_name):
    """Provide contextual fix suggestion for error types."""
    suggestions = {
        "CREDITS_EXHAUSTED": "Add OpenRouter credits or switch to a different free model. Check https://openrouter.ai/settings/credits",
        "RATE_LIMITED": "Increase delay between API calls or implement exponential backoff in the workflow.",
        "BAD_REQUEST": f"Check the input format for node '{node_name}'. A preceding node may be passing malformed data.",
        "NODE_ERROR": f"Review error details for '{node_name}' and check if upstream nodes are producing expected output.",
    }
    return suggestions.get(err_type, "Investigate node configuration and input data.")


# ============================================================
# Cross-Execution Pattern Analysis
# ============================================================
def analyze_cross_execution_patterns(executions):
    """Analyze patterns across multiple executions."""
    patterns = {
        "node_failure_rates": defaultdict(lambda: {"total": 0, "errors": 0, "issues": []}),
        "latency_distribution": defaultdict(list),
        "llm_verbosity": defaultdict(list),
        "routing_patterns": defaultdict(lambda: defaultdict(int)),
        "bottleneck_nodes": [],
        "common_issues": defaultdict(int),
    }

    for ex in executions:
        for node in ex.get("nodes", []):
            name = node["name"]

            # Failure rates
            patterns["node_failure_rates"][name]["total"] += 1
            if node.get("error"):
                patterns["node_failure_rates"][name]["errors"] += 1

            # Latency
            if node.get("duration_ms", 0) > 0:
                patterns["latency_distribution"][name].append(node["duration_ms"])

            # LLM verbosity
            if node.get("llm_output"):
                patterns["llm_verbosity"][name].append(node["llm_output"]["length_chars"])

            # Routing flags
            for flag, val in node.get("routing_flags", {}).items():
                patterns["routing_patterns"][name][f"{flag}={val}"] += 1

    # Compute aggregates
    result = {
        "node_health": {},
        "latency_bottlenecks": [],
        "verbosity_report": {},
        "routing_summary": {},
    }

    # Node health scores
    for name, stats in patterns["node_failure_rates"].items():
        error_rate = stats["errors"] / stats["total"] if stats["total"] > 0 else 0
        result["node_health"][name] = {
            "total_runs": stats["total"],
            "errors": stats["errors"],
            "error_rate_pct": round(error_rate * 100, 1),
            "health": "critical" if error_rate > 0.5 else ("warning" if error_rate > 0.1 else "healthy"),
        }

    # Latency bottlenecks
    for name, latencies in patterns["latency_distribution"].items():
        avg = sum(latencies) / len(latencies) if latencies else 0
        p95 = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else (latencies[0] if latencies else 0)
        if avg > THRESHOLDS["node_slow_ms"]:
            result["latency_bottlenecks"].append({
                "node": name,
                "avg_ms": int(avg),
                "p95_ms": int(p95),
                "max_ms": max(latencies) if latencies else 0,
                "samples": len(latencies),
            })

    result["latency_bottlenecks"].sort(key=lambda x: x["avg_ms"], reverse=True)

    # Verbosity report
    for name, lengths in patterns["llm_verbosity"].items():
        avg_len = sum(lengths) / len(lengths) if lengths else 0
        result["verbosity_report"][name] = {
            "avg_chars": int(avg_len),
            "max_chars": max(lengths) if lengths else 0,
            "min_chars": min(lengths) if lengths else 0,
            "samples": len(lengths),
            "verdict": "critical" if avg_len > THRESHOLDS["llm_very_verbose_chars"] else (
                "warning" if avg_len > THRESHOLDS["llm_verbose_chars"] else "ok"),
        }

    # Routing summary
    for name, flags in patterns["routing_patterns"].items():
        result["routing_summary"][name] = dict(flags)

    return result


# ============================================================
# Main Analysis: analyze_stage()
# ============================================================
def analyze_stage(pipeline, questions_tested, stage_name="", label=""):
    """Main entry point: analyze a stage after it completes.

    Args:
        pipeline: "standard"|"graph"|"quantitative"|"orchestrator"
        questions_tested: list of question dicts with at least "id" and "question"
        stage_name: e.g. "Stage 1: Smoke (5q)"
        label: iteration label

    Returns:
        Diagnostic report dict, also saved to logs/diagnostics/
    """
    print(f"\n  [NODE-ANALYZER] Analyzing {pipeline} — {stage_name} ({len(questions_tested)} questions)...")

    # Step 1: Fetch recent executions for this pipeline
    # Fetch more than needed to match against tested questions
    limit = max(len(questions_tested) * 2, 10)
    executions = fetch_rich_executions(pipeline, limit=limit)

    if not executions:
        print(f"  [NODE-ANALYZER] No executions found for {pipeline}")
        return _empty_report(pipeline, stage_name, questions_tested)

    # Step 2: Match executions to tested questions
    query_texts = {q["question"].lower().strip()[:100] for q in questions_tested}
    matched = []
    for ex in executions:
        trigger = ex.get("trigger_query", "").lower().strip()[:100]
        if trigger and any(trigger.startswith(qt[:50]) or qt.startswith(trigger[:50]) for qt in query_texts):
            matched.append(ex)

    # If matching by query text doesn't work well, use the most recent N
    if len(matched) < len(questions_tested) // 2:
        matched = executions[:len(questions_tested)]
        print(f"  [NODE-ANALYZER] Query matching found {len(matched)} — using {len(matched)} most recent executions")
    else:
        print(f"  [NODE-ANALYZER] Matched {len(matched)} executions to {len(questions_tested)} questions")

    # Step 3: Per-node issue detection
    all_issues = []
    node_summaries = {}
    for ex in matched:
        for node in ex.get("nodes", []):
            issues = detect_node_issues(node)
            all_issues.extend(issues)

            name = node["name"]
            if name not in node_summaries:
                node_summaries[name] = {
                    "name": name,
                    "executions": 0,
                    "errors": 0,
                    "avg_duration_ms": 0,
                    "total_duration_ms": 0,
                    "is_llm": _is_node_type(name, LLM_NODE_KEYWORDS),
                    "is_retrieval": _is_node_type(name, RETRIEVAL_NODE_KEYWORDS),
                    "is_routing": _is_node_type(name, ROUTING_NODE_KEYWORDS),
                    "issues": [],
                    "llm_avg_output_chars": 0,
                    "llm_avg_tokens": 0,
                    "llm_outputs": [],
                }
            ns = node_summaries[name]
            ns["executions"] += 1
            ns["total_duration_ms"] += node.get("duration_ms", 0)
            ns["avg_duration_ms"] = ns["total_duration_ms"] // ns["executions"]
            if node.get("error"):
                ns["errors"] += 1
            if node.get("llm_output"):
                ns["llm_outputs"].append(node["llm_output"]["length_chars"])
                ns["llm_avg_output_chars"] = sum(ns["llm_outputs"]) // len(ns["llm_outputs"])
            if node.get("llm_tokens"):
                ns["llm_avg_tokens"] = node["llm_tokens"].get("completion_tokens", 0)
            ns["issues"].extend(issues)

    # Step 4: Cross-execution pattern analysis
    cross_patterns = analyze_cross_execution_patterns(matched)

    # Step 5: Generate top-level recommendations
    recommendations = _generate_recommendations(pipeline, all_issues, cross_patterns, node_summaries)

    # Step 6: Build report
    # Clean up node_summaries (remove raw lists)
    for ns in node_summaries.values():
        ns.pop("llm_outputs", None)
        # Deduplicate issues by type+node
        seen = set()
        unique = []
        for iss in ns["issues"]:
            key = (iss["type"], iss["node"])
            if key not in seen:
                seen.add(key)
                unique.append(iss)
        ns["issues"] = unique

    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "pipeline": pipeline,
        "stage": stage_name,
        "label": label,
        "questions_tested": len(questions_tested),
        "executions_analyzed": len(matched),
        "total_issues": len(all_issues),
        "issues_by_severity": {
            "critical": sum(1 for i in all_issues if i["severity"] == "critical"),
            "high": sum(1 for i in all_issues if i["severity"] == "high"),
            "medium": sum(1 for i in all_issues if i["severity"] == "medium"),
            "low": sum(1 for i in all_issues if i["severity"] == "low"),
        },
        "node_analysis": node_summaries,
        "cross_execution_patterns": cross_patterns,
        "top_issues": _deduplicate_issues(all_issues)[:20],
        "recommendations": recommendations,
        "execution_ids": [ex["execution_id"] for ex in matched],
    }

    # Step 7: Save report
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    safe_stage = stage_name.replace(" ", "-").replace("(", "").replace(")", "").lower()
    report_path = os.path.join(DIAG_DIR, f"diag-{pipeline}-{safe_stage}-{ts}.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Also save as latest for this pipeline
    latest_path = os.path.join(DIAG_DIR, f"latest-{pipeline}.json")
    with open(latest_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Save combined latest
    _update_latest_combined(report)

    # Print summary
    _print_summary(report)

    return report


def _empty_report(pipeline, stage_name, questions):
    """Return empty report when no executions found."""
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "pipeline": pipeline,
        "stage": stage_name,
        "questions_tested": len(questions),
        "executions_analyzed": 0,
        "total_issues": 0,
        "issues_by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "node_analysis": {},
        "cross_execution_patterns": {},
        "top_issues": [],
        "recommendations": ["No executions found — check n8n API connectivity and workflow status."],
        "execution_ids": [],
    }


def _deduplicate_issues(issues):
    """Deduplicate issues by type+node, keeping highest severity."""
    seen = {}
    for iss in issues:
        key = (iss["type"], iss["node"])
        if key not in seen or _severity_rank(iss["severity"]) > _severity_rank(seen[key]["severity"]):
            seen[key] = iss
    return sorted(seen.values(), key=lambda x: _severity_rank(x["severity"]), reverse=True)


def _severity_rank(s):
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(s, 0)


def _generate_recommendations(pipeline, all_issues, cross_patterns, node_summaries):
    """Generate prioritized fix recommendations."""
    recs = []

    # Critical issues first
    critical = [i for i in all_issues if i["severity"] == "critical"]
    if critical:
        types = set(i["type"] for i in critical)
        for t in types:
            examples = [i for i in critical if i["type"] == t]
            recs.append({
                "priority": "CRITICAL",
                "type": t,
                "affected_nodes": list(set(i["node"] for i in examples)),
                "description": examples[0]["detail"],
                "action": examples[0].get("suggestion", "Investigate immediately."),
                "occurrences": len(examples),
            })

    # Verbosity issues (user's specific concern for graph pipeline)
    for name, info in cross_patterns.get("verbosity_report", {}).items():
        if info["verdict"] in ("critical", "warning"):
            recs.append({
                "priority": "HIGH" if info["verdict"] == "critical" else "MEDIUM",
                "type": "VERBOSE_LLM",
                "affected_nodes": [name],
                "description": f"LLM node '{name}' avg output: {info['avg_chars']} chars (max: {info['max_chars']})",
                "action": "Constrain system prompt to output only required intermediate data. Add max_tokens parameter.",
                "occurrences": info["samples"],
            })

    # Latency bottlenecks
    for bn in cross_patterns.get("latency_bottlenecks", [])[:3]:
        recs.append({
            "priority": "MEDIUM",
            "type": "LATENCY_BOTTLENECK",
            "affected_nodes": [bn["node"]],
            "description": f"Node '{bn['node']}' avg {bn['avg_ms']}ms (p95: {bn['p95_ms']}ms)",
            "action": "Consider caching, parallelization, or model optimization.",
            "occurrences": bn["samples"],
        })

    # Sort by priority
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    recs.sort(key=lambda r: priority_order.get(r["priority"], 99))

    return recs


def _update_latest_combined(report):
    """Update the combined latest diagnostics file."""
    latest_path = os.path.join(DIAG_DIR, "latest.json")
    combined = {}
    if os.path.exists(latest_path):
        try:
            with open(latest_path) as f:
                combined = json.load(f)
        except (json.JSONDecodeError, IOError):
            combined = {}

    combined[report["pipeline"]] = report
    combined["_updated_at"] = datetime.utcnow().isoformat() + "Z"

    with open(latest_path, "w") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)


def _print_summary(report):
    """Print a concise summary of the diagnostic report."""
    sev = report["issues_by_severity"]
    total = report["total_issues"]
    print(f"  [NODE-ANALYZER] {report['pipeline']} — {report['stage']}")
    print(f"    Executions analyzed: {report['executions_analyzed']}")
    print(f"    Issues found: {total} "
          f"(critical:{sev['critical']} high:{sev['high']} med:{sev['medium']} low:{sev['low']})")

    # Top recommendations
    for rec in report["recommendations"][:3]:
        if isinstance(rec, dict):
            print(f"    [{rec['priority']}] {rec['type']}: {rec['description'][:100]}")
            print(f"      → {rec['action'][:100]}")
        else:
            print(f"    → {rec}")

    # Node health quick view
    node_analysis = report.get("node_analysis", {})
    problem_nodes = [
        (name, info) for name, info in node_analysis.items()
        if info.get("issues") or info.get("errors", 0) > 0
    ]
    if problem_nodes:
        print(f"    Problem nodes ({len(problem_nodes)}):")
        for name, info in problem_nodes[:5]:
            issues_str = ", ".join(set(i["type"] for i in info.get("issues", [])))
            print(f"      • {name}: {info['avg_duration_ms']}ms avg"
                  + (f" | {info['errors']} errors" if info.get("errors") else "")
                  + (f" | LLM: {info['llm_avg_output_chars']} chars" if info.get("llm_avg_output_chars") else "")
                  + (f" | {issues_str}" if issues_str else ""))


# ============================================================
# Standalone CLI
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Node-by-node execution analyzer")
    parser.add_argument("--pipeline", type=str, default=None,
                        choices=["standard", "graph", "quantitative", "orchestrator"],
                        help="Pipeline to analyze")
    parser.add_argument("--all", action="store_true", help="Analyze all pipelines")
    parser.add_argument("--last", type=int, default=5, help="Number of recent executions to analyze")
    parser.add_argument("--execution-id", type=str, default=None, help="Analyze a specific execution")

    args = parser.parse_args()

    if args.execution_id:
        ex = fetch_execution_by_id(args.execution_id)
        if ex:
            print(f"\n  Execution {args.execution_id} — {ex['pipeline']}")
            print(f"  Status: {ex['status']} | Duration: {ex['duration_ms']}ms")
            print(f"  Query: {ex['trigger_query'][:100]}")
            print(f"  Nodes: {ex['node_count']}")
            for node in ex["nodes"]:
                issues = detect_node_issues(node)
                status = "ERR" if node.get("error") else "OK"
                print(f"\n    [{status}] {node['name']} ({node['duration_ms']}ms)")
                if node.get("llm_output"):
                    print(f"        LLM: {node['llm_output']['length_chars']} chars | "
                          f"Model: {node.get('llm_model', '?')}")
                if node.get("llm_tokens"):
                    t = node["llm_tokens"]
                    print(f"        Tokens: {t['prompt_tokens']}→{t['completion_tokens']} "
                          f"(total: {t['total_tokens']})")
                if node.get("routing_flags"):
                    print(f"        Flags: {node['routing_flags']}")
                if node.get("error"):
                    print(f"        Error: {node['error'][:200]}")
                for iss in issues:
                    print(f"        ⚠ [{iss['severity'].upper()}] {iss['type']}: {iss['detail'][:100]}")
        return


    pipelines = ["standard", "graph", "quantitative", "orchestrator"] if args.all else [args.pipeline]
    pipelines = [p for p in pipelines if p]

    if not pipelines:
        print("  Specify --pipeline <name> or --all")
        return

    for pipe in pipelines:
        print(f"\n{'='*60}")
        print(f"  Analyzing {pipe} (last {args.last} executions)")
        print(f"{'='*60}")

        dummy_questions = [{"id": f"q{i}", "question": f"dummy-{i}"} for i in range(args.last)]
        report = analyze_stage(pipe, dummy_questions, stage_name="manual-analysis")

        print(f"\n  Report saved to: logs/diagnostics/latest-{pipe}.json")


if __name__ == "__main__":
    main()
