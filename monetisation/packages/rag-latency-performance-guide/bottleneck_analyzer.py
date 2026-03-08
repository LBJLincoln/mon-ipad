#!/usr/bin/env python3
"""
RAG Bottleneck Analyzer — Automatic identification of the slowest pipeline stage.

Analyzes execution logs, identifies bottlenecks, and recommends specific optimizations.

Part of: RAG Latency & Performance Engineering Guide
Author: Alexis Moret (Ecole Polytechnique & HEC Paris)
"""

import json
import statistics
from dataclasses import dataclass
from typing import Optional
from pathlib import Path


@dataclass
class BottleneckResult:
    stage: str
    severity: str  # "critical", "warning", "ok"
    latency_ms: float
    pct_of_total: float
    recommendation: str
    quick_win: Optional[str] = None


OPTIMIZATION_DB = {
    "embedding": {
        "threshold_ms": 200,
        "recommendations": [
            "Batch embeddings: Process 32-64 queries at once for 4x throughput",
            "Use Matryoshka dimensions: Start with 256-dim for retrieval, full 1024 for reranking",
            "Cache embeddings: LRU cache for repeat/similar queries (typical 40-70% hit rate)",
            "Switch to lighter model: E5-small (384-dim) is 3x faster than Jina-v3 with ~2% accuracy loss",
            "Connection pooling: Reuse HTTP sessions to avoid TLS handshake per request",
        ],
        "quick_win": "Add `@lru_cache(maxsize=10000)` to your embed function — instant 40%+ speedup for repeat queries",
    },
    "retrieval": {
        "threshold_ms": 150,
        "recommendations": [
            "Optimize HNSW params: ef_search=40 (not 100) for 2.5x speed with <1% recall loss",
            "Pre-filter with metadata: Reduce search space by 60-80% before vector search",
            "Use namespaces: Partition by document type/date for smaller search indexes",
            "Reduce top_k: top_k=5 is 2x faster than top_k=20, reranking compensates",
            "Parallel retrieval: Query multiple indexes simultaneously with asyncio",
        ],
        "quick_win": "Reduce top_k from 20 to 10 and add a reranker — faster AND more accurate",
    },
    "vector_search": {
        "threshold_ms": 150,
        "recommendations": [
            "Optimize HNSW params: ef_search=40 (not 100) for 2.5x speed with <1% recall loss",
            "Pre-filter with metadata before vector search",
            "Use serverless Pinecone for auto-scaling and lower cold-start latency",
        ],
        "quick_win": "Set ef_search=40 in your index config — immediate 2x speedup",
    },
    "llm_generation": {
        "threshold_ms": 500,
        "recommendations": [
            "Enable streaming: Users see first token in 200-400ms instead of waiting 3-8s",
            "Compress context: Summarize retrieved docs before sending to LLM (40% fewer tokens)",
            "Use smaller context: 2K-4K tokens outperforms 8K+ for most queries (faster + more accurate)",
            "Switch to faster model: Groq Llama-3.3-70B gives 200+ tok/s vs 40 tok/s on OpenRouter",
            "Parallel generation: For multi-part answers, generate sections concurrently",
            "Prompt caching: Reuse system prompt prefix (saves 30-50% on providers that support it)",
        ],
        "quick_win": "Enable streaming responses — perceived latency drops from seconds to milliseconds",
    },
    "reranking": {
        "threshold_ms": 100,
        "recommendations": [
            "Reduce candidates: Rerank top-10 instead of top-50 (5x faster, ~same accuracy)",
            "Use cross-encoder only for top candidates, bi-encoder for initial filter",
            "Cache reranking results for identical (query, doc) pairs",
        ],
        "quick_win": "Cut reranking candidates from 20 to 10 — halves latency with <1% accuracy change",
    },
    "query_parsing": {
        "threshold_ms": 50,
        "recommendations": [
            "Use regex-based classification before LLM (handles 60% of queries)",
            "Cache intent classification results",
            "Use smaller model for classification (Gemma-3-27B instead of Llama-70B)",
        ],
        "quick_win": "Add a regex pre-classifier that handles simple queries without LLM call",
    },
    "graph_traversal": {
        "threshold_ms": 300,
        "recommendations": [
            "Index all queried properties in Neo4j",
            "Limit traversal depth to 2-3 hops (exponential cost beyond that)",
            "Use APOC parallel procedures for multi-path queries",
            "Cache frequent subgraph patterns",
        ],
        "quick_win": "CREATE INDEX on your most-queried node properties — 5-10x faster lookups",
    },
    "sql_generation": {
        "threshold_ms": 200,
        "recommendations": [
            "Cache generated SQL for repeat query patterns",
            "Use few-shot examples to reduce LLM thinking time",
            "Pre-compute common aggregations as materialized views",
        ],
        "quick_win": "Add 3-5 few-shot examples to your SQL prompt — faster + more accurate generation",
    },
    "post_processing": {
        "threshold_ms": 50,
        "recommendations": [
            "Move citation formatting to client-side",
            "Use string templates instead of LLM for formatting",
            "Parallelize source attribution with response generation",
        ],
        "quick_win": "Format citations client-side instead of in the pipeline",
    },
}


def analyze_profiler_output(profiler_data: dict) -> list[BottleneckResult]:
    """Analyze profiler output and identify bottlenecks with recommendations.

    Args:
        profiler_data: Output from RAGProfiler.save() or similar structure
            Expected: {"stages": {"name": {"mean": float, "p95": float, ...}}}

    Returns:
        List of BottleneckResult sorted by severity
    """
    results = []
    total_time = sum(
        s.get("mean", s.get("mean_ms", 0) / 1000 if "mean_ms" in s else 0)
        for s in profiler_data.get("stages", {}).values()
    )

    for stage_name, metrics in profiler_data.get("stages", {}).items():
        mean_ms = metrics.get("mean_ms", metrics.get("mean", 0) * 1000)
        stage_total = metrics.get("mean", mean_ms / 1000)
        pct = (stage_total / total_time * 100) if total_time > 0 else 0

        # Find matching optimization advice
        opt_key = stage_name.lower().replace(" ", "_").replace("-", "_")
        opt = OPTIMIZATION_DB.get(opt_key, {})
        threshold = opt.get("threshold_ms", 200)

        if mean_ms > threshold * 2:
            severity = "critical"
        elif mean_ms > threshold:
            severity = "warning"
        else:
            severity = "ok"

        recommendations = opt.get("recommendations", [
            f"Stage '{stage_name}' takes {mean_ms:.0f}ms — profile internal operations to find specific bottleneck"
        ])

        results.append(BottleneckResult(
            stage=stage_name,
            severity=severity,
            latency_ms=mean_ms,
            pct_of_total=pct,
            recommendation=recommendations[0] if recommendations else "No specific recommendation",
            quick_win=opt.get("quick_win"),
        ))

    # Sort: critical first, then by latency
    severity_order = {"critical": 0, "warning": 1, "ok": 2}
    results.sort(key=lambda r: (severity_order.get(r.severity, 3), -r.latency_ms))

    return results


def print_analysis(results: list[BottleneckResult]):
    """Pretty-print bottleneck analysis."""
    print("\n" + "=" * 60)
    print("  RAG BOTTLENECK ANALYSIS")
    print("=" * 60)

    for r in results:
        icon = {"critical": "[!!!]", "warning": "[!!]", "ok": "[ok]"}[r.severity]
        print(f"\n  {icon} {r.stage} — {r.latency_ms:.0f}ms ({r.pct_of_total:.1f}% of total)")
        print(f"      Recommendation: {r.recommendation}")
        if r.quick_win:
            print(f"      Quick win: {r.quick_win}")

    critical = [r for r in results if r.severity == "critical"]
    if critical:
        print(f"\n  ACTION REQUIRED: {len(critical)} critical bottleneck(s) found")
        total_savings = sum(r.latency_ms * 0.5 for r in critical)
        print(f"  Estimated savings if fixed: ~{total_savings:.0f}ms per request")

    print("\n" + "=" * 60 + "\n")


def analyze_from_file(filepath: str):
    """Load profiler data from file and analyze."""
    data = json.loads(Path(filepath).read_text())
    results = analyze_profiler_output(data)
    print_analysis(results)
    return results


if __name__ == "__main__":
    # Demo with sample data
    sample_data = {
        "pipeline": "standard-rag",
        "stages": {
            "query_parsing": {"mean_ms": 35, "p95_ms": 52},
            "embedding": {"mean_ms": 280, "p95_ms": 420},
            "vector_search": {"mean_ms": 95, "p95_ms": 180},
            "reranking": {"mean_ms": 150, "p95_ms": 230},
            "llm_generation": {"mean_ms": 1850, "p95_ms": 3200},
            "post_processing": {"mean_ms": 25, "p95_ms": 40},
        }
    }

    print("Analyzing sample RAG pipeline...")
    results = analyze_profiler_output(sample_data)
    print_analysis(results)
