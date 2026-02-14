#!/usr/bin/env python3
"""
Node-by-Node Execution Analyzer — Automated Pipeline Diagnostics v2
====================================================================
After each eval stage (every 5/10/50 questions), this module:
  1. Fetches n8n execution logs for the tested questions
  2. Parses each node's full output (tokens, routing flags, LLM content)
  3. Detects issues: verbose LLM, token waste, routing failures, latency bottlenecks
  4. Analyzes execution timeline (waterfall), error chains, data flow integrity
  5. Compares executions for regression detection
  6. Generates actionable diagnostic reports sorted by impact

The goal: automate what a human does when inspecting n8n execution nodes manually.

Usage:
  # As module (called by iterative-eval.py after each stage):
  from node_analyzer import analyze_stage
  report = analyze_stage("graph", questions_tested, stage_name="Stage 1: Smoke (5q)")

  # Standalone:
  python eval/node-analyzer.py --pipeline graph --last 5
  python eval/node-analyzer.py --pipeline orchestrator --execution-id 18352
  python eval/node-analyzer.py --all --last 10
  python eval/node-analyzer.py --pipeline standard --last 10 --compare
  python eval/node-analyzer.py --execution-id 12345 --verbose
"""

import json
import os
import sys
import time
import re
from datetime import datetime, timedelta
from collections import defaultdict, OrderedDict
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
    "data_loss_threshold": 0.5,     # >50% items lost between connected nodes = warning
    "prompt_completion_ratio_max": 20,  # prompt/completion > 20x = wasteful context
    "retrieval_min_score": 0.3,     # Vector search score below this = low quality
    "http_timeout_ms": 30000,       # API call > 30s = likely timeout
}

# Node categories for smarter analysis
LLM_NODE_KEYWORDS = ["llm", "generation", "chat", "completion", "gpt", "hyde", "entity extraction",
                      "query decomposer", "answer", "synthesis"]
RETRIEVAL_NODE_KEYWORDS = ["pinecone", "neo4j", "supabase", "postgres", "search", "query", "bm25",
                           "embedding", "vector", "rerank"]
ROUTING_NODE_KEYWORDS = ["router", "switch", "if", "merge", "wait", "branch", "decomposition",
                         "orchestrat"]
TRANSFORM_NODE_KEYWORDS = ["set", "code", "function", "item", "split", "aggregate", "filter",
                           "transform", "map", "reduce", "edit fields"]
HTTP_NODE_KEYWORDS = ["http", "webhook", "api", "request", "fetch", "curl"]


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
        "error_class": None,
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
        # New v2 fields
        "node_category": _categorize_node(name),
        "data_size_bytes_in": 0,
        "data_size_bytes_out": 0,
        "output_fields_populated": {},
        "retrieval_scores": [],
        "http_status": None,
        "started_at": None,
        "finished_at": None,
    }

    # Timestamps (for waterfall)
    if run.get("startTime"):
        node["started_at"] = run["startTime"]
    if run.get("executionTime") and run.get("startTime"):
        try:
            start = datetime.fromisoformat(str(run["startTime"]).replace("Z", "+00:00"))
            node["finished_at"] = (start + timedelta(milliseconds=run["executionTime"])).isoformat()
        except (ValueError, TypeError):
            pass

    # Error extraction with classification
    if run.get("error"):
        err = run["error"]
        err_msg = err.get("message", str(err))[:1000] if isinstance(err, dict) else str(err)[:1000]
        node["error"] = err_msg
        node["error_class"] = _classify_error(err_msg, err if isinstance(err, dict) else {})
        # Extract HTTP status from error
        if isinstance(err, dict):
            node["http_status"] = err.get("httpCode") or err.get("statusCode")

    # Input/output counts + data sizes
    input_data = run.get("inputData", {}).get("main", [])
    output_data = run.get("data", {}).get("main", [])
    if input_data:
        node["items_in"] = sum(len(d) if isinstance(d, list) else 0 for d in input_data)
        node["data_size_bytes_in"] = _estimate_data_size(input_data)
    if output_data:
        node["items_out"] = sum(len(d) if isinstance(d, list) else 0 for d in output_data)
        node["data_size_bytes_out"] = _estimate_data_size(output_data)

    # Capture input preview (what the node received)
    first_input = _get_first_output_item(input_data)
    if first_input:
        node["input_preview"] = json.dumps(first_input, ensure_ascii=False)[:1000]
        node["input_keys"] = list(first_input.keys())[:20]

    # Extract ALL output items for deeper analysis (not just first)
    all_output_items = _get_all_output_items(output_data)
    first_item = all_output_items[0] if all_output_items else None

    if first_item:
        node["output_keys"] = list(first_item.keys())[:30]
        node["output_preview"] = json.dumps(first_item, ensure_ascii=False)[:2000]

        # Track which output fields are populated vs null/empty
        node["output_fields_populated"] = _analyze_field_population(all_output_items)

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
            if output_data and isinstance(output_data, list):
                active_branches = []
                for branch_idx, branch in enumerate(output_data):
                    if isinstance(branch, list) and len(branch) > 0:
                        active_branches.append(branch_idx)
                node["active_branches"] = active_branches
                node["total_branches"] = len(output_data)

        # Context/retrieval data + score extraction
        if "results" in first_item and isinstance(first_item["results"], list):
            node["retrieval_count"] = len(first_item["results"])
            # Extract similarity/relevance scores from results
            scores = []
            for res in first_item["results"][:20]:
                if isinstance(res, dict):
                    score = res.get("score") or res.get("relevance_score") or res.get("similarity")
                    if score is not None:
                        scores.append(float(score))
            node["retrieval_scores"] = scores

        # Check matches array (Pinecone format)
        if "matches" in first_item and isinstance(first_item["matches"], list):
            node["retrieval_count"] = len(first_item["matches"])
            scores = [m.get("score", 0) for m in first_item["matches"] if isinstance(m, dict)]
            node["retrieval_scores"] = scores

        if "metadata" in first_item and isinstance(first_item["metadata"], dict):
            meta = first_item["metadata"]
            node["retrieval_metadata"] = {
                "sources_available": meta.get("sources_available", 0),
                "total_unique_docs": meta.get("total_unique_docs", 0),
                "warnings": meta.get("warnings", []),
            }

        # HTTP response info
        if "statusCode" in first_item:
            node["http_status"] = first_item["statusCode"]
        if "headers" in first_item and isinstance(first_item["headers"], dict):
            node["http_status"] = first_item["headers"].get("status") or node.get("http_status")

        # Answer/response quality check
        if _is_node_type(name, LLM_NODE_KEYWORDS):
            _extract_answer_quality(node, first_item, all_output_items)

    return node


def _categorize_node(name):
    """Classify a node into a functional category."""
    if _is_node_type(name, LLM_NODE_KEYWORDS):
        return "llm"
    if _is_node_type(name, RETRIEVAL_NODE_KEYWORDS):
        return "retrieval"
    if _is_node_type(name, ROUTING_NODE_KEYWORDS):
        return "routing"
    if _is_node_type(name, TRANSFORM_NODE_KEYWORDS):
        return "transform"
    if _is_node_type(name, HTTP_NODE_KEYWORDS):
        return "http"
    return "other"


def _classify_error(msg, err_dict):
    """Classify an error into actionable categories."""
    msg_lower = msg.lower()
    code = err_dict.get("httpCode") or err_dict.get("statusCode") or ""
    code_str = str(code)

    if "402" in code_str or "credit" in msg_lower or "insufficient" in msg_lower:
        return {"category": "credits_exhausted", "http_code": 402, "recoverable": False,
                "action": "Add credits or switch to free model"}
    if "429" in code_str or "rate" in msg_lower or "too many" in msg_lower:
        return {"category": "rate_limited", "http_code": 429, "recoverable": True,
                "action": "Add delay between calls or implement backoff"}
    if "401" in code_str or "unauthorized" in msg_lower or "authentication" in msg_lower:
        return {"category": "auth_failure", "http_code": 401, "recoverable": False,
                "action": "Check API key configuration"}
    if "403" in code_str or "forbidden" in msg_lower:
        return {"category": "forbidden", "http_code": 403, "recoverable": False,
                "action": "Check permissions and API access"}
    if "404" in code_str or "not found" in msg_lower:
        return {"category": "not_found", "http_code": 404, "recoverable": False,
                "action": "Check endpoint URL or resource existence"}
    if "400" in code_str or "bad request" in msg_lower or "invalid" in msg_lower:
        return {"category": "bad_request", "http_code": 400, "recoverable": False,
                "action": "Check input format from upstream node"}
    if "500" in code_str or "internal server" in msg_lower:
        return {"category": "server_error", "http_code": 500, "recoverable": True,
                "action": "Retry — external API issue"}
    if "502" in code_str or "bad gateway" in msg_lower:
        return {"category": "gateway_error", "http_code": 502, "recoverable": True,
                "action": "External service temporarily down, retry later"}
    if "503" in code_str or "service unavailable" in msg_lower:
        return {"category": "service_unavailable", "http_code": 503, "recoverable": True,
                "action": "External service overloaded, retry with backoff"}
    if "timeout" in msg_lower or "timed out" in msg_lower or "etimedout" in msg_lower:
        return {"category": "timeout", "http_code": None, "recoverable": True,
                "action": "Increase timeout or check if API is responding"}
    if "econnrefused" in msg_lower or "connection refused" in msg_lower:
        return {"category": "connection_refused", "http_code": None, "recoverable": False,
                "action": "Service is down — check container/endpoint status"}
    if "enotfound" in msg_lower or "dns" in msg_lower:
        return {"category": "dns_error", "http_code": None, "recoverable": False,
                "action": "Check hostname/URL configuration"}
    if "json" in msg_lower and ("parse" in msg_lower or "unexpected" in msg_lower):
        return {"category": "json_parse_error", "http_code": None, "recoverable": False,
                "action": "Upstream node returning non-JSON data — check content type"}
    if "undefined" in msg_lower or "cannot read" in msg_lower or "property" in msg_lower:
        return {"category": "data_structure_error", "http_code": None, "recoverable": False,
                "action": "Node expects different data shape than received — check upstream output"}
    return {"category": "unknown", "http_code": code or None, "recoverable": False,
            "action": "Investigate error message manually"}


def _estimate_data_size(data):
    """Estimate the byte size of node data (for data flow analysis)."""
    try:
        return len(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError):
        return 0


def _get_all_output_items(output_data):
    """Extract ALL output items from node output (across all branches)."""
    items = []
    if not output_data or not isinstance(output_data, list):
        return items
    for branch in output_data:
        if not isinstance(branch, list):
            continue
        for raw_item in branch:
            if isinstance(raw_item, dict):
                item = raw_item.get("json", raw_item)
                items.append(item)
    return items


def _analyze_field_population(items):
    """Check which output fields are consistently populated vs null/empty."""
    if not items:
        return {}
    all_keys = set()
    for item in items:
        if isinstance(item, dict):
            all_keys.update(item.keys())

    field_stats = {}
    for key in list(all_keys)[:30]:
        populated = 0
        for item in items:
            if isinstance(item, dict):
                val = item.get(key)
                if val is not None and val != "" and val != [] and val != {}:
                    populated += 1
        rate = populated / len(items) if items else 0
        if rate < 1.0:  # Only report fields that are sometimes empty
            field_stats[key] = {"populated_pct": round(rate * 100, 1), "populated": populated, "total": len(items)}
    return field_stats


def _extract_answer_quality(node, first_item, all_items):
    """Analyze the quality signals of an LLM answer node."""
    quality = {}

    # Check for common "I don't know" / refusal patterns
    content = ""
    if node.get("llm_output"):
        content = node["llm_output"].get("content", "")
    elif isinstance(first_item, dict):
        content = first_item.get("answer", first_item.get("response", first_item.get("text", "")))

    if content:
        content_lower = content.lower()
        refusal_patterns = [
            "i don't have", "i cannot", "i'm unable", "no information",
            "not available", "insufficient data", "cannot determine",
            "i don't know", "no relevant", "unable to find",
            "based on the available", "no data found",
        ]
        quality["has_refusal"] = any(p in content_lower for p in refusal_patterns)
        quality["answer_length"] = len(content)
        quality["has_sources"] = "source" in content_lower or "reference" in content_lower or "[" in content
        # Check if answer is just echoing the question
        if node.get("input_preview"):
            try:
                inp = json.loads(node["input_preview"])
                query = str(inp.get("query", inp.get("question", "")))[:200].lower()
                if query and len(query) > 20 and query in content_lower:
                    quality["echoes_question"] = True
            except (json.JSONDecodeError, TypeError):
                pass

    node["answer_quality"] = quality


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

    # 8. Retrieval score quality
    scores = node.get("retrieval_scores", [])
    if scores:
        avg_score = sum(scores) / len(scores)
        min_score = min(scores)
        if avg_score < THRESHOLDS["retrieval_min_score"]:
            issues.append({
                "type": "LOW_RETRIEVAL_QUALITY",
                "severity": "high",
                "node": name,
                "detail": f"Avg retrieval score: {avg_score:.3f} (min: {min_score:.3f}) — below {THRESHOLDS['retrieval_min_score']} threshold",
                "metric": {"avg_score": round(avg_score, 3), "min_score": round(min_score, 3),
                           "max_score": round(max(scores), 3), "count": len(scores)},
                "suggestion": "Improve query embedding quality, check if HyDE is working, or reindex with better chunks.",
            })
        elif min_score < THRESHOLDS["retrieval_min_score"] * 0.5:
            issues.append({
                "type": "LOW_SCORE_OUTLIER",
                "severity": "medium",
                "node": name,
                "detail": f"Some retrieval scores very low: min={min_score:.3f} (avg={avg_score:.3f})",
                "metric": {"avg_score": round(avg_score, 3), "min_score": round(min_score, 3), "count": len(scores)},
                "suggestion": "Review reranker configuration or add score threshold filtering.",
            })

    # 9. Data flow anomalies
    items_in = node.get("items_in", 0)
    items_out = node.get("items_out", 0)
    if items_in > 0 and items_out == 0 and node["status"] == "success":
        if not _is_node_type(name, ROUTING_NODE_KEYWORDS):
            issues.append({
                "type": "DATA_LOSS",
                "severity": "high",
                "node": name,
                "detail": f"Node received {items_in} items but output 0 — data silently dropped",
                "suggestion": "Check node logic — it may be filtering everything out or returning empty.",
            })
    elif items_in > 1 and items_out == 1 and _is_node_type(name, TRANSFORM_NODE_KEYWORDS):
        issues.append({
            "type": "AGGRESSIVE_FILTER",
            "severity": "low",
            "node": name,
            "detail": f"Node reduced {items_in} items to {items_out} — heavy filtering",
            "suggestion": "Verify this is intentional. May be losing relevant context.",
        })

    # 10. LLM prompt/completion efficiency
    if node.get("llm_tokens"):
        tokens = node["llm_tokens"]
        prompt = tokens.get("prompt_tokens", 0)
        completion = tokens.get("completion_tokens", 0)
        if completion > 0 and prompt > 0:
            ratio = prompt / completion
            if ratio > THRESHOLDS["prompt_completion_ratio_max"]:
                issues.append({
                    "type": "WASTEFUL_CONTEXT",
                    "severity": "medium",
                    "node": name,
                    "detail": f"Prompt/completion ratio: {ratio:.0f}x ({prompt} prompt / {completion} completion tokens). Huge context for tiny output.",
                    "metric": {"prompt_tokens": prompt, "completion_tokens": completion, "ratio": round(ratio, 1)},
                    "suggestion": "Reduce context size — trim irrelevant docs, use summarization, or increase max_tokens.",
                })

    # 11. Answer quality issues
    quality = node.get("answer_quality", {})
    if quality.get("has_refusal"):
        issues.append({
            "type": "LLM_REFUSAL",
            "severity": "high",
            "node": name,
            "detail": "LLM response contains refusal/uncertainty pattern ('I don't have information', etc.)",
            "suggestion": "Check if retrieval provided relevant context. May need better prompt or fallback.",
        })
    if quality.get("echoes_question"):
        issues.append({
            "type": "ECHO_RESPONSE",
            "severity": "medium",
            "node": name,
            "detail": "LLM response appears to echo the input question without adding value",
            "suggestion": "Improve system prompt to guide the model toward generating useful output.",
        })

    # 12. Unpopulated output fields
    unpopulated = node.get("output_fields_populated", {})
    critical_empty = [k for k, v in unpopulated.items()
                      if v.get("populated_pct", 100) < 50 and k in ("answer", "response", "context", "results", "text")]
    if critical_empty:
        issues.append({
            "type": "EMPTY_CRITICAL_FIELDS",
            "severity": "high",
            "node": name,
            "detail": f"Critical output fields mostly empty: {critical_empty}",
            "suggestion": "Check node logic — key fields are not being populated.",
        })

    # 13. HTTP error classification
    if node.get("http_status"):
        status = int(node["http_status"]) if str(node["http_status"]).isdigit() else 0
        if 500 <= status < 600:
            issues.append({
                "type": "HTTP_5XX",
                "severity": "high",
                "node": name,
                "detail": f"HTTP {status} — server-side error from external API",
                "suggestion": "External service error. May be transient — check if retryable.",
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
# Execution Timeline / Waterfall Analysis
# ============================================================
def build_execution_timeline(execution):
    """Build a waterfall timeline showing where time is spent."""
    nodes = execution.get("nodes", [])
    total_ms = execution.get("duration_ms", 0)
    if total_ms == 0:
        total_ms = sum(n.get("duration_ms", 0) for n in nodes) or 1

    timeline = []
    for node in sorted(nodes, key=lambda n: n.get("duration_ms", 0), reverse=True):
        dur = node.get("duration_ms", 0)
        pct = (dur / total_ms * 100) if total_ms > 0 else 0
        timeline.append({
            "node": node["name"],
            "duration_ms": dur,
            "pct_of_total": round(pct, 1),
            "category": node.get("node_category", "other"),
            "status": node["status"],
            "items_in": node.get("items_in", 0),
            "items_out": node.get("items_out", 0),
        })

    # Identify critical path (top nodes that make up 80% of time)
    cumulative_pct = 0
    critical_path = []
    for entry in timeline:
        cumulative_pct += entry["pct_of_total"]
        critical_path.append(entry["node"])
        if cumulative_pct >= 80:
            break

    # Time by category
    time_by_category = defaultdict(int)
    for node in nodes:
        cat = node.get("node_category", "other")
        time_by_category[cat] += node.get("duration_ms", 0)
    time_by_category_pct = {cat: round(ms / total_ms * 100, 1) for cat, ms in time_by_category.items()}

    return {
        "total_ms": total_ms,
        "node_waterfall": timeline[:20],
        "critical_path_nodes": critical_path,
        "critical_path_pct": round(cumulative_pct, 1),
        "time_by_category": dict(time_by_category),
        "time_by_category_pct": time_by_category_pct,
        "slowest_node": timeline[0]["node"] if timeline else None,
        "slowest_node_ms": timeline[0]["duration_ms"] if timeline else 0,
    }


# ============================================================
# Error Chain Analysis
# ============================================================
def trace_error_chain(execution):
    """Find the first failure point and trace downstream impact."""
    nodes = execution.get("nodes", [])
    error_nodes = [n for n in nodes if n.get("error")]

    if not error_nodes:
        return {"has_errors": False, "chain": [], "first_failure": None}

    # Sort by start time if available, otherwise by position
    error_nodes_sorted = sorted(error_nodes, key=lambda n: n.get("started_at", "") or "")

    first_failure = error_nodes_sorted[0]

    # Find nodes that ran after the first failure (potential cascade)
    cascade = []
    for node in error_nodes_sorted[1:]:
        cascade.append({
            "node": node["name"],
            "error": node["error"][:200] if node.get("error") else "",
            "error_class": node.get("error_class", {}).get("category", "unknown"),
            "likely_cascade": _is_likely_cascade(first_failure, node),
        })

    # Count nodes that produced 0 output after the error
    downstream_empty = sum(1 for n in nodes if n.get("items_out", 0) == 0
                          and n["status"] == "success"
                          and n.get("started_at", "Z") > first_failure.get("started_at", ""))

    return {
        "has_errors": True,
        "error_count": len(error_nodes),
        "first_failure": {
            "node": first_failure["name"],
            "error": first_failure["error"][:300] if first_failure.get("error") else "",
            "error_class": first_failure.get("error_class", {}),
            "duration_ms": first_failure.get("duration_ms", 0),
            "category": first_failure.get("node_category", "other"),
        },
        "cascade_errors": cascade,
        "downstream_empty_nodes": downstream_empty,
        "root_cause_likely": first_failure.get("error_class", {}).get("action", "Investigate first failure"),
    }


def _is_likely_cascade(first, subsequent):
    """Determine if a subsequent error is likely caused by the first failure."""
    # Same error class = likely cascade
    fc = first.get("error_class", {}).get("category", "")
    sc = subsequent.get("error_class", {}).get("category", "")
    if fc == sc:
        return True
    # Data structure errors after any error = likely cascade
    if sc in ("data_structure_error", "json_parse_error"):
        return True
    return False


# ============================================================
# Data Flow Integrity Analysis
# ============================================================
def analyze_data_flow(execution):
    """Track data flow through the pipeline — where items are created, transformed, or lost."""
    nodes = execution.get("nodes", [])
    flow = []
    total_items_created = 0
    total_items_lost = 0

    for node in nodes:
        items_in = node.get("items_in", 0)
        items_out = node.get("items_out", 0)
        size_in = node.get("data_size_bytes_in", 0)
        size_out = node.get("data_size_bytes_out", 0)

        delta = items_out - items_in
        if delta > 0:
            total_items_created += delta
        elif delta < 0 and items_in > 0:
            total_items_lost += abs(delta)

        entry = {
            "node": node["name"],
            "category": node.get("node_category", "other"),
            "items_in": items_in,
            "items_out": items_out,
            "delta": delta,
            "size_in_kb": round(size_in / 1024, 1),
            "size_out_kb": round(size_out / 1024, 1),
        }

        if items_in > 0 and items_out == 0 and node["status"] == "success":
            entry["anomaly"] = "SILENT_DROP"
        elif items_in > 0 and items_out < items_in * THRESHOLDS["data_loss_threshold"]:
            entry["anomaly"] = "HEAVY_FILTER"

        flow.append(entry)

    # Find data bottlenecks (nodes that drastically reduce data)
    bottlenecks = [f for f in flow if f.get("anomaly")]

    return {
        "flow": flow,
        "total_items_created": total_items_created,
        "total_items_lost": total_items_lost,
        "data_bottlenecks": bottlenecks,
        "largest_payload_node": max(flow, key=lambda f: f["size_out_kb"])["node"] if flow else None,
    }


# ============================================================
# Success vs Failure Correlation
# ============================================================
def analyze_success_factors(executions):
    """Compare successful vs failed executions to find what differentiates them."""
    successful = [e for e in executions if e["status"] == "success"]
    failed = [e for e in executions if e["status"] != "success"]

    if not successful or not failed:
        return {
            "total_success": len(successful),
            "total_failed": len(failed),
            "success_rate_pct": round(len(successful) / max(len(executions), 1) * 100, 1),
            "differentiators": [],
            "note": "Need both successful and failed executions to compare",
        }

    # Compare average durations
    avg_success_ms = sum(e["duration_ms"] for e in successful) / len(successful)
    avg_failed_ms = sum(e["duration_ms"] for e in failed) / len(failed)

    # Find nodes that only fail in failed executions
    success_error_nodes = set()
    fail_error_nodes = set()
    for e in successful:
        for n in e.get("nodes", []):
            if n.get("error"):
                success_error_nodes.add(n["name"])
    for e in failed:
        for n in e.get("nodes", []):
            if n.get("error"):
                fail_error_nodes.add(n["name"])

    failure_exclusive_nodes = fail_error_nodes - success_error_nodes

    # Compare node durations between success and failure
    success_durations = defaultdict(list)
    fail_durations = defaultdict(list)
    for e in successful:
        for n in e.get("nodes", []):
            success_durations[n["name"]].append(n.get("duration_ms", 0))
    for e in failed:
        for n in e.get("nodes", []):
            fail_durations[n["name"]].append(n.get("duration_ms", 0))

    duration_diffs = []
    for name in set(list(success_durations.keys()) + list(fail_durations.keys())):
        s_avg = sum(success_durations[name]) / max(len(success_durations[name]), 1)
        f_avg = sum(fail_durations[name]) / max(len(fail_durations[name]), 1)
        if s_avg > 0 and abs(f_avg - s_avg) / s_avg > 0.5:
            duration_diffs.append({
                "node": name,
                "success_avg_ms": int(s_avg),
                "fail_avg_ms": int(f_avg),
                "diff_pct": round((f_avg - s_avg) / s_avg * 100, 0),
            })

    duration_diffs.sort(key=lambda d: abs(d["diff_pct"]), reverse=True)

    # Error pattern analysis in failed executions
    error_patterns = defaultdict(int)
    for e in failed:
        for n in e.get("nodes", []):
            if n.get("error_class"):
                cat = n["error_class"].get("category", "unknown")
                error_patterns[cat] += 1
    error_patterns_sorted = sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)

    return {
        "total_success": len(successful),
        "total_failed": len(failed),
        "success_rate_pct": round(len(successful) / len(executions) * 100, 1),
        "avg_duration_success_ms": int(avg_success_ms),
        "avg_duration_failed_ms": int(avg_failed_ms),
        "failure_exclusive_error_nodes": list(failure_exclusive_nodes)[:10],
        "duration_anomalies": duration_diffs[:5],
        "top_error_patterns": error_patterns_sorted[:5],
    }


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

    # Step 4b: Execution timelines (waterfall)
    timelines = [build_execution_timeline(ex) for ex in matched]
    avg_timeline = _aggregate_timelines(timelines)

    # Step 4c: Error chain analysis
    error_chains = [trace_error_chain(ex) for ex in matched if ex["status"] != "success"]
    error_chain_summary = _summarize_error_chains(error_chains)

    # Step 4d: Data flow analysis
    data_flows = [analyze_data_flow(ex) for ex in matched]
    data_flow_summary = _summarize_data_flows(data_flows)

    # Step 4e: Success vs failure correlation
    success_factors = analyze_success_factors(matched)

    # Step 5: Generate top-level recommendations (enriched)
    recommendations = _generate_recommendations(pipeline, all_issues, cross_patterns,
                                                node_summaries, avg_timeline,
                                                error_chain_summary, success_factors)

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
        "success_rate_pct": success_factors.get("success_rate_pct", 0),
        "total_issues": len(all_issues),
        "issues_by_severity": {
            "critical": sum(1 for i in all_issues if i["severity"] == "critical"),
            "high": sum(1 for i in all_issues if i["severity"] == "high"),
            "medium": sum(1 for i in all_issues if i["severity"] == "medium"),
            "low": sum(1 for i in all_issues if i["severity"] == "low"),
        },
        "execution_timeline": avg_timeline,
        "error_chain_analysis": error_chain_summary,
        "data_flow_analysis": data_flow_summary,
        "success_vs_failure": success_factors,
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


def _aggregate_timelines(timelines):
    """Aggregate multiple execution timelines into summary stats."""
    if not timelines:
        return {}

    # Average total duration
    avg_total = sum(t["total_ms"] for t in timelines) / len(timelines)

    # Aggregate time by category
    cat_totals = defaultdict(list)
    for t in timelines:
        for cat, ms in t.get("time_by_category", {}).items():
            cat_totals[cat].append(ms)

    avg_by_category = {cat: int(sum(vals) / len(vals)) for cat, vals in cat_totals.items()}
    avg_by_category_pct = {cat: round(ms / avg_total * 100, 1) for cat, ms in avg_by_category.items()} if avg_total else {}

    # Most common critical path nodes
    critical_freq = defaultdict(int)
    for t in timelines:
        for node in t.get("critical_path_nodes", []):
            critical_freq[node] += 1
    top_critical = sorted(critical_freq.items(), key=lambda x: x[1], reverse=True)[:5]

    # Slowest nodes across all executions
    node_durations = defaultdict(list)
    for t in timelines:
        for entry in t.get("node_waterfall", []):
            node_durations[entry["node"]].append(entry["duration_ms"])

    slowest_avg = sorted(
        [(name, int(sum(durs) / len(durs)), max(durs), len(durs))
         for name, durs in node_durations.items()],
        key=lambda x: x[1], reverse=True
    )[:10]

    return {
        "avg_total_ms": int(avg_total),
        "min_total_ms": min(t["total_ms"] for t in timelines),
        "max_total_ms": max(t["total_ms"] for t in timelines),
        "avg_time_by_category": avg_by_category,
        "avg_time_by_category_pct": avg_by_category_pct,
        "critical_path_nodes": top_critical,
        "slowest_nodes": [{"node": n, "avg_ms": a, "max_ms": m, "samples": s}
                          for n, a, m, s in slowest_avg],
        "executions_analyzed": len(timelines),
    }


def _summarize_error_chains(chains):
    """Summarize error chains across multiple executions."""
    if not chains:
        return {"total_with_errors": 0, "root_causes": [], "cascade_patterns": []}

    error_chains = [c for c in chains if c.get("has_errors")]
    if not error_chains:
        return {"total_with_errors": 0, "root_causes": [], "cascade_patterns": []}

    # Count root cause nodes
    root_causes = defaultdict(lambda: {"count": 0, "errors": [], "categories": []})
    for c in error_chains:
        ff = c.get("first_failure", {})
        node = ff.get("node", "unknown")
        root_causes[node]["count"] += 1
        root_causes[node]["errors"].append(ff.get("error", "")[:100])
        cat = ff.get("error_class", {}).get("category", "unknown")
        if cat not in root_causes[node]["categories"]:
            root_causes[node]["categories"].append(cat)

    sorted_roots = sorted(root_causes.items(), key=lambda x: x[1]["count"], reverse=True)

    # Cascade patterns
    cascade_freq = defaultdict(int)
    for c in error_chains:
        for cascade in c.get("cascade_errors", []):
            cascade_freq[cascade["node"]] += 1

    return {
        "total_with_errors": len(error_chains),
        "root_causes": [
            {"node": name, "count": info["count"], "categories": info["categories"],
             "sample_error": info["errors"][0] if info["errors"] else ""}
            for name, info in sorted_roots[:5]
        ],
        "cascade_nodes": sorted(cascade_freq.items(), key=lambda x: x[1], reverse=True)[:5],
        "avg_errors_per_execution": round(sum(c["error_count"] for c in error_chains) / len(error_chains), 1),
    }


def _summarize_data_flows(flows):
    """Summarize data flow analysis across executions."""
    if not flows:
        return {}

    # Find consistent bottlenecks
    bottleneck_freq = defaultdict(int)
    for f in flows:
        for bn in f.get("data_bottlenecks", []):
            bottleneck_freq[bn["node"]] += 1

    # Average items created/lost
    avg_created = sum(f.get("total_items_created", 0) for f in flows) / len(flows)
    avg_lost = sum(f.get("total_items_lost", 0) for f in flows) / len(flows)

    return {
        "avg_items_created": round(avg_created, 1),
        "avg_items_lost": round(avg_lost, 1),
        "consistent_bottlenecks": sorted(bottleneck_freq.items(), key=lambda x: x[1], reverse=True)[:5],
        "executions_analyzed": len(flows),
    }


def _generate_recommendations(pipeline, all_issues, cross_patterns, node_summaries,
                              timeline=None, error_chains=None, success_factors=None):
    """Generate prioritized fix recommendations with enriched context."""
    recs = []

    # 0. ROOT CAUSE from error chain analysis (highest priority)
    if error_chains and error_chains.get("root_causes"):
        for rc in error_chains["root_causes"][:2]:
            recs.append({
                "priority": "CRITICAL",
                "type": "ROOT_CAUSE_FAILURE",
                "affected_nodes": [rc["node"]],
                "description": f"Root cause of {rc['count']} failures: {rc['node']} ({', '.join(rc['categories'])}). Error: {rc.get('sample_error', '')[:100]}",
                "action": f"Fix this node FIRST — all other errors may cascade from it.",
                "occurrences": rc["count"],
            })

    # 1. Critical issues
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

    # 2. Time bottleneck (user's specific request)
    if timeline and timeline.get("slowest_nodes"):
        for sn in timeline["slowest_nodes"][:3]:
            if sn["avg_ms"] > THRESHOLDS["node_slow_ms"]:
                pct = round(sn["avg_ms"] / max(timeline.get("avg_total_ms", 1), 1) * 100, 0)
                recs.append({
                    "priority": "HIGH",
                    "type": "TIME_BOTTLENECK",
                    "affected_nodes": [sn["node"]],
                    "description": f"'{sn['node']}' takes {sn['avg_ms']}ms avg ({pct}% of total). Max: {sn['max_ms']}ms",
                    "action": "This is the #1 time sink. Optimize: cache results, reduce context, switch to faster model, or parallelize.",
                    "occurrences": sn["samples"],
                })

    # 3. Success differentiators
    if success_factors and success_factors.get("failure_exclusive_error_nodes"):
        nodes = success_factors["failure_exclusive_error_nodes"]
        recs.append({
            "priority": "HIGH",
            "type": "FAILURE_EXCLUSIVE_ERRORS",
            "affected_nodes": nodes[:5],
            "description": f"These nodes ONLY error in failed executions: {', '.join(nodes[:3])}",
            "action": "Fixing these nodes directly improves success rate.",
            "occurrences": success_factors.get("total_failed", 0),
        })

    # 4. Verbosity issues
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

    # 5. Latency bottlenecks (from cross patterns)
    for bn in cross_patterns.get("latency_bottlenecks", [])[:3]:
        # Skip if already covered by timeline
        if any(r["type"] == "TIME_BOTTLENECK" and bn["node"] in r["affected_nodes"] for r in recs):
            continue
        recs.append({
            "priority": "MEDIUM",
            "type": "LATENCY_BOTTLENECK",
            "affected_nodes": [bn["node"]],
            "description": f"Node '{bn['node']}' avg {bn['avg_ms']}ms (p95: {bn['p95_ms']}ms)",
            "action": "Consider caching, parallelization, or model optimization.",
            "occurrences": bn["samples"],
        })

    # 6. Data flow issues
    high_issues = [i for i in all_issues if i["severity"] == "high" and i["type"] == "DATA_LOSS"]
    if high_issues:
        nodes = list(set(i["node"] for i in high_issues))
        recs.append({
            "priority": "HIGH",
            "type": "DATA_LOSS",
            "affected_nodes": nodes,
            "description": f"Data silently dropped at: {', '.join(nodes[:3])}",
            "action": "These nodes receive items but output nothing. Check filtering/transformation logic.",
            "occurrences": len(high_issues),
        })

    # Deduplicate by type+affected_nodes
    seen = set()
    deduped = []
    for r in recs:
        key = (r["type"], tuple(sorted(r["affected_nodes"])))
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    # Sort by priority
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    deduped.sort(key=lambda r: priority_order.get(r["priority"], 99))

    return deduped


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
    """Print a rich, actionable summary of the diagnostic report."""
    pipeline = report["pipeline"]
    sev = report["issues_by_severity"]
    total = report["total_issues"]

    print(f"\n{'='*70}")
    print(f"  DIAGNOSTIC REPORT: {pipeline.upper()} — {report['stage']}")
    print(f"{'='*70}")

    # Overview
    sr = report.get("success_rate_pct", "?")
    print(f"\n  Executions: {report['executions_analyzed']} | Success rate: {sr}%")
    print(f"  Issues: {total} (CRIT:{sev['critical']} HIGH:{sev['high']} MED:{sev['medium']} LOW:{sev['low']})")

    # Timeline summary
    tl = report.get("execution_timeline", {})
    if tl:
        print(f"\n  --- TIMING ---")
        print(f"  Avg total: {tl.get('avg_total_ms', 0)}ms | Range: {tl.get('min_total_ms', 0)}-{tl.get('max_total_ms', 0)}ms")
        if tl.get("avg_time_by_category_pct"):
            cats = tl["avg_time_by_category_pct"]
            parts = [f"{cat}={pct}%" for cat, pct in sorted(cats.items(), key=lambda x: x[1], reverse=True)]
            print(f"  Time split: {' | '.join(parts)}")
        if tl.get("slowest_nodes"):
            print(f"  Top bottlenecks:")
            for sn in tl["slowest_nodes"][:5]:
                pct = round(sn["avg_ms"] / max(tl.get("avg_total_ms", 1), 1) * 100, 0)
                bar = "#" * min(int(pct / 2), 30)
                print(f"    {sn['node'][:40]:<40} {sn['avg_ms']:>6}ms ({pct:>3.0f}%) {bar}")

    # Error chain
    ec = report.get("error_chain_analysis", {})
    if ec and ec.get("total_with_errors", 0) > 0:
        print(f"\n  --- ERROR CHAIN ---")
        print(f"  Executions with errors: {ec['total_with_errors']} | Avg errors/exec: {ec.get('avg_errors_per_execution', 0)}")
        if ec.get("root_causes"):
            print(f"  Root causes (fix FIRST):")
            for rc in ec["root_causes"][:3]:
                print(f"    >> {rc['node']} ({rc['count']}x) [{', '.join(rc['categories'])}]")
                if rc.get("sample_error"):
                    print(f"       {rc['sample_error'][:100]}")

    # Data flow
    df = report.get("data_flow_analysis", {})
    if df and df.get("consistent_bottlenecks"):
        print(f"\n  --- DATA FLOW ---")
        print(f"  Avg items created: {df.get('avg_items_created', 0)} | Lost: {df.get('avg_items_lost', 0)}")
        for bn_name, bn_count in df["consistent_bottlenecks"][:3]:
            print(f"    Data drop at: {bn_name} ({bn_count}x)")

    # Success vs failure
    sf = report.get("success_vs_failure", {})
    if sf and sf.get("total_failed", 0) > 0:
        print(f"\n  --- SUCCESS vs FAILURE ---")
        print(f"  Success: {sf.get('total_success', 0)} ({sf.get('avg_duration_success_ms', 0)}ms avg) | "
              f"Failed: {sf.get('total_failed', 0)} ({sf.get('avg_duration_failed_ms', 0)}ms avg)")
        if sf.get("failure_exclusive_error_nodes"):
            print(f"  Nodes that ONLY fail in failed runs: {', '.join(sf['failure_exclusive_error_nodes'][:3])}")
        if sf.get("top_error_patterns"):
            patterns = [f"{cat}({n})" for cat, n in sf["top_error_patterns"][:3]]
            print(f"  Error patterns: {' | '.join(patterns)}")

    # Top recommendations (THE most important section)
    recs = report.get("recommendations", [])
    if recs:
        print(f"\n  --- RECOMMENDATIONS (fix in this order) ---")
        for i, rec in enumerate(recs[:5], 1):
            if isinstance(rec, dict):
                print(f"  {i}. [{rec['priority']}] {rec['type']}")
                print(f"     Nodes: {', '.join(rec['affected_nodes'][:3])}")
                print(f"     {rec['description'][:120]}")
                print(f"     -> {rec['action'][:120]}")
            else:
                print(f"  {i}. {rec}")

    # Problem nodes quick view
    node_analysis = report.get("node_analysis", {})
    problem_nodes = [
        (name, info) for name, info in node_analysis.items()
        if info.get("issues") or info.get("errors", 0) > 0
    ]
    if problem_nodes:
        print(f"\n  --- PROBLEM NODES ({len(problem_nodes)}) ---")
        for name, info in sorted(problem_nodes, key=lambda x: x[1].get("errors", 0), reverse=True)[:8]:
            issues_str = ", ".join(set(i["type"] for i in info.get("issues", [])))[:60]
            print(f"    {name[:40]:<40} {info['avg_duration_ms']:>5}ms"
                  + (f" | {info['errors']}err" if info.get("errors") else "     ")
                  + (f" | LLM:{info['llm_avg_output_chars']}ch" if info.get("llm_avg_output_chars") else "")
                  + (f" | {issues_str}" if issues_str else ""))

    print(f"\n{'='*70}\n")


# ============================================================
# Standalone CLI
# ============================================================
def _print_single_execution(ex, verbose=False):
    """Rich output for a single execution analysis."""
    print(f"\n{'='*70}")
    print(f"  EXECUTION #{ex['execution_id']} — {ex['pipeline'].upper()}")
    print(f"{'='*70}")
    print(f"  Status: {ex['status']} | Duration: {ex['duration_ms']}ms")
    print(f"  Query: {ex['trigger_query'][:120]}")
    print(f"  Nodes: {ex['node_count']}")

    # Timeline waterfall
    timeline = build_execution_timeline(ex)
    print(f"\n  --- TIMELINE (total {timeline['total_ms']}ms) ---")
    for entry in timeline["node_waterfall"][:15]:
        bar = "#" * min(int(entry["pct_of_total"] / 2), 30)
        status_icon = "X" if entry["status"] == "error" else " "
        print(f"  [{status_icon}] {entry['node'][:38]:<38} {entry['duration_ms']:>6}ms "
              f"({entry['pct_of_total']:>5.1f}%) {bar}")

    if timeline.get("time_by_category_pct"):
        cats = timeline["time_by_category_pct"]
        parts = [f"{cat}={pct}%" for cat, pct in sorted(cats.items(), key=lambda x: x[1], reverse=True)]
        print(f"  Categories: {' | '.join(parts)}")

    # Error chain
    error_chain = trace_error_chain(ex)
    if error_chain["has_errors"]:
        print(f"\n  --- ERROR CHAIN ({error_chain['error_count']} errors) ---")
        ff = error_chain["first_failure"]
        print(f"  FIRST FAILURE: {ff['node']} [{ff.get('error_class', {}).get('category', '?')}]")
        print(f"    {ff['error'][:200]}")
        print(f"    -> {ff.get('error_class', {}).get('action', 'Investigate')}")
        if error_chain.get("cascade_errors"):
            print(f"  Cascade ({len(error_chain['cascade_errors'])} downstream):")
            for c in error_chain["cascade_errors"][:3]:
                cascade_mark = " (CASCADE)" if c.get("likely_cascade") else ""
                print(f"    {c['node']}: {c['error_class']}{cascade_mark}")

    # Data flow
    data_flow = analyze_data_flow(ex)
    if data_flow.get("data_bottlenecks"):
        print(f"\n  --- DATA FLOW ISSUES ---")
        for bn in data_flow["data_bottlenecks"]:
            print(f"  {bn['anomaly']}: {bn['node']} (in:{bn['items_in']} -> out:{bn['items_out']})")

    # Per-node details
    print(f"\n  --- NODES ---")
    all_issues = []
    for node in sorted(ex["nodes"], key=lambda n: n.get("duration_ms", 0), reverse=True):
        issues = detect_node_issues(node)
        all_issues.extend(issues)
        status_icon = "X" if node.get("error") else "."
        cat = node.get("node_category", "?")[:5]

        print(f"\n  [{status_icon}] {node['name']} ({node['duration_ms']}ms) [{cat}] "
              f"in:{node.get('items_in', 0)} out:{node.get('items_out', 0)}")

        if node.get("llm_output"):
            lo = node["llm_output"]
            print(f"      LLM output: {lo['length_chars']} chars | Model: {node.get('llm_model', '?')}")
            if verbose and lo.get("content"):
                # Show first 300 chars of LLM output
                print(f"      Content: {lo['content'][:300]}...")
        if node.get("llm_tokens"):
            t = node["llm_tokens"]
            ratio = t['prompt_tokens'] / max(t['completion_tokens'], 1)
            print(f"      Tokens: {t['prompt_tokens']} prompt -> {t['completion_tokens']} completion "
                  f"(ratio: {ratio:.1f}x, total: {t['total_tokens']})")
        if node.get("retrieval_scores"):
            scores = node["retrieval_scores"]
            print(f"      Retrieval: {len(scores)} results, scores: "
                  f"avg={sum(scores)/len(scores):.3f} min={min(scores):.3f} max={max(scores):.3f}")
        if node.get("routing_flags"):
            print(f"      Flags: {node['routing_flags']}")
        if node.get("answer_quality"):
            aq = node["answer_quality"]
            parts = []
            if aq.get("has_refusal"):
                parts.append("REFUSAL")
            if aq.get("echoes_question"):
                parts.append("ECHO")
            if aq.get("has_sources"):
                parts.append("has_sources")
            if parts:
                print(f"      Quality: {' | '.join(parts)} (len={aq.get('answer_length', 0)})")
        if node.get("error"):
            cls = node.get("error_class", {})
            cat = cls.get("category", "unknown") if cls else "unknown"
            print(f"      ERROR [{cat}]: {node['error'][:200]}")
            if cls and cls.get("action"):
                print(f"      -> {cls['action']}")
        if verbose and node.get("output_fields_populated"):
            empty_fields = {k: v for k, v in node["output_fields_populated"].items() if v.get("populated_pct", 100) < 80}
            if empty_fields:
                parts = [f"{k}({v['populated_pct']}%)" for k, v in list(empty_fields.items())[:5]]
                print(f"      Sparse fields: {', '.join(parts)}")
        for iss in issues:
            print(f"      >> [{iss['severity'].upper()}] {iss['type']}: {iss['detail'][:100]}")

    # Summary
    if all_issues:
        print(f"\n  --- ISSUE SUMMARY ---")
        by_sev = defaultdict(list)
        for iss in all_issues:
            by_sev[iss["severity"]].append(iss)
        for sev in ["critical", "high", "medium", "low"]:
            if by_sev[sev]:
                types = defaultdict(int)
                for i in by_sev[sev]:
                    types[i["type"]] += 1
                parts = [f"{t}({n})" for t, n in sorted(types.items(), key=lambda x: x[1], reverse=True)]
                print(f"  {sev.upper()}: {', '.join(parts)}")

    print(f"\n{'='*70}")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Node-by-node execution analyzer v2 — with timeline, error chains, data flow, and regression detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --execution-id 12345                   # Deep-dive single execution
  %(prog)s --execution-id 12345 --verbose          # With LLM outputs and field stats
  %(prog)s --pipeline standard --last 5            # Analyze last 5 standard runs
  %(prog)s --pipeline graph --last 10 --compare    # Compare success vs failure
  %(prog)s --all --last 10                         # All pipelines overview
        """
    )
    parser.add_argument("--pipeline", type=str, default=None,
                        choices=["standard", "graph", "quantitative", "orchestrator"],
                        help="Pipeline to analyze")
    parser.add_argument("--all", action="store_true", help="Analyze all pipelines")
    parser.add_argument("--last", type=int, default=5, help="Number of recent executions to analyze")
    parser.add_argument("--execution-id", type=str, default=None, help="Analyze a specific execution")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detailed output (LLM content, field stats)")
    parser.add_argument("--compare", action="store_true",
                        help="Compare successful vs failed executions")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON report instead of formatted text")

    args = parser.parse_args()

    if args.execution_id:
        ex = fetch_execution_by_id(args.execution_id)
        if ex:
            if args.json:
                print(json.dumps(ex, indent=2, ensure_ascii=False))
            else:
                _print_single_execution(ex, verbose=args.verbose)
        else:
            print(f"  Could not fetch execution {args.execution_id}")
        return

    pipelines = ["standard", "graph", "quantitative", "orchestrator"] if args.all else [args.pipeline]
    pipelines = [p for p in pipelines if p]

    if not pipelines:
        print("  Specify --pipeline <name> or --all")
        return

    for pipe in pipelines:
        print(f"\n{'='*70}")
        print(f"  Analyzing {pipe} (last {args.last} executions)")
        print(f"{'='*70}")

        dummy_questions = [{"id": f"q{i}", "question": f"dummy-{i}"} for i in range(args.last)]
        report = analyze_stage(pipe, dummy_questions, stage_name="manual-analysis")

        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        elif args.compare and report.get("success_vs_failure"):
            sf = report["success_vs_failure"]
            print(f"\n  --- DETAILED COMPARISON ---")
            print(f"  Success: {sf.get('total_success', 0)} | Failed: {sf.get('total_failed', 0)}")
            print(f"  Success avg: {sf.get('avg_duration_success_ms', 0)}ms | Failed avg: {sf.get('avg_duration_failed_ms', 0)}ms")
            if sf.get("duration_anomalies"):
                print(f"\n  Nodes with biggest time difference (success vs failure):")
                for da in sf["duration_anomalies"]:
                    direction = "SLOWER" if da["diff_pct"] > 0 else "FASTER"
                    print(f"    {da['node'][:40]:<40} success:{da['success_avg_ms']}ms vs fail:{da['fail_avg_ms']}ms ({direction} {abs(da['diff_pct']):.0f}%)")
            if sf.get("top_error_patterns"):
                print(f"\n  Error pattern distribution in failures:")
                for cat, count in sf["top_error_patterns"]:
                    print(f"    {cat}: {count}x")

        print(f"\n  Report saved: logs/diagnostics/latest-{pipe}.json")


if __name__ == "__main__":
    main()
