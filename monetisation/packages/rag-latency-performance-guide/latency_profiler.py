#!/usr/bin/env python3
"""
RAG Latency Profiler — Instrument any RAG pipeline in 3 lines of code.

Usage:
    from latency_profiler import RAGProfiler

    profiler = RAGProfiler()

    with profiler.stage("embedding"):
        embedding = embed(query)

    with profiler.stage("retrieval"):
        docs = search(embedding, top_k=10)

    with profiler.stage("llm_generation"):
        answer = generate(query, docs)

    profiler.report()  # Prints breakdown + identifies bottleneck

Part of: RAG Latency & Performance Engineering Guide
Author: Alexis Moret (Ecole Polytechnique & HEC Paris)
"""

import time
import json
import statistics
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class StageMetrics:
    """Metrics for a single pipeline stage."""
    name: str
    durations: list = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.durations)

    @property
    def total(self) -> float:
        return sum(self.durations)

    @property
    def mean(self) -> float:
        return statistics.mean(self.durations) if self.durations else 0

    @property
    def p50(self) -> float:
        return statistics.median(self.durations) if self.durations else 0

    @property
    def p95(self) -> float:
        if len(self.durations) < 2:
            return self.durations[0] if self.durations else 0
        sorted_d = sorted(self.durations)
        idx = int(len(sorted_d) * 0.95)
        return sorted_d[min(idx, len(sorted_d) - 1)]

    @property
    def p99(self) -> float:
        if len(self.durations) < 2:
            return self.durations[0] if self.durations else 0
        sorted_d = sorted(self.durations)
        idx = int(len(sorted_d) * 0.99)
        return sorted_d[min(idx, len(sorted_d) - 1)]


class RAGProfiler:
    """Profile RAG pipeline stages with minimal overhead (<1ms per stage)."""

    def __init__(self, name: str = "rag-pipeline"):
        self.name = name
        self.stages: dict[str, StageMetrics] = {}
        self.request_start: Optional[float] = None
        self.request_durations: list[float] = []
        self._current_request_start: Optional[float] = None

    def start_request(self):
        """Mark the start of a new request."""
        self._current_request_start = time.perf_counter()

    def end_request(self):
        """Mark the end of a request and record total duration."""
        if self._current_request_start:
            duration = time.perf_counter() - self._current_request_start
            self.request_durations.append(duration)
            self._current_request_start = None

    @contextmanager
    def stage(self, name: str):
        """Context manager to time a pipeline stage.

        Usage:
            with profiler.stage("embedding"):
                result = embed(query)
        """
        if name not in self.stages:
            self.stages[name] = StageMetrics(name=name)

        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.stages[name].durations.append(duration)

    def time_function(self, stage_name: str):
        """Decorator to time a function as a pipeline stage.

        Usage:
            @profiler.time_function("embedding")
            def embed(query):
                return model.encode(query)
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                with self.stage(stage_name):
                    return func(*args, **kwargs)
            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
            return wrapper
        return decorator

    def report(self, format: str = "text") -> str:
        """Generate a latency report.

        Args:
            format: "text" for human-readable, "json" for machine-readable

        Returns:
            Formatted report string
        """
        if format == "json":
            return self._json_report()
        return self._text_report()

    def _text_report(self) -> str:
        """Generate human-readable latency breakdown."""
        total_time = sum(s.total for s in self.stages.values())

        lines = [
            f"\n{'='*60}",
            f"  RAG LATENCY REPORT — {self.name}",
            f"{'='*60}\n",
        ]

        # Stage breakdown
        lines.append(f"  {'Stage':<25} {'Mean':>8} {'P50':>8} {'P95':>8} {'P99':>8} {'%Total':>8}")
        lines.append(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

        bottleneck = None
        bottleneck_pct = 0

        for stage in self.stages.values():
            pct = (stage.total / total_time * 100) if total_time > 0 else 0
            if pct > bottleneck_pct:
                bottleneck = stage.name
                bottleneck_pct = pct

            lines.append(
                f"  {stage.name:<25} "
                f"{stage.mean*1000:>7.1f}ms "
                f"{stage.p50*1000:>7.1f}ms "
                f"{stage.p95*1000:>7.1f}ms "
                f"{stage.p99*1000:>7.1f}ms "
                f"{pct:>7.1f}%"
            )

        lines.append(f"\n  Total pipeline time: {total_time*1000:.1f}ms across {max(s.count for s in self.stages.values()) if self.stages else 0} requests")

        if bottleneck:
            lines.append(f"\n  BOTTLENECK: {bottleneck} ({bottleneck_pct:.1f}% of total time)")
            lines.append(f"  -> Optimize this stage first for maximum impact\n")

        # Quick wins
        lines.append("  QUICK WINS:")
        for stage in self.stages.values():
            if stage.p95 > stage.p50 * 2:
                lines.append(f"  - {stage.name}: High P95/P50 ratio ({stage.p95/stage.p50:.1f}x) — likely tail latency issue")
            if stage.mean > 1.0:
                lines.append(f"  - {stage.name}: >1s mean — consider caching or parallel execution")

        lines.append(f"\n{'='*60}\n")

        report = "\n".join(lines)
        print(report)
        return report

    def _json_report(self) -> str:
        """Generate JSON report for programmatic consumption."""
        data = {
            "pipeline": self.name,
            "stages": {},
            "total_time_ms": sum(s.total for s in self.stages.values()) * 1000,
        }

        for stage in self.stages.values():
            total_time = sum(s.total for s in self.stages.values())
            data["stages"][stage.name] = {
                "count": stage.count,
                "mean_ms": round(stage.mean * 1000, 2),
                "p50_ms": round(stage.p50 * 1000, 2),
                "p95_ms": round(stage.p95 * 1000, 2),
                "p99_ms": round(stage.p99 * 1000, 2),
                "total_ms": round(stage.total * 1000, 2),
                "pct_of_total": round(stage.total / total_time * 100, 1) if total_time > 0 else 0,
            }

        result = json.dumps(data, indent=2)
        print(result)
        return result

    def save(self, filepath: str):
        """Save profiling data to JSON file for later analysis."""
        data = {
            "pipeline": self.name,
            "stages": {
                name: {
                    "durations": stage.durations,
                    "count": stage.count,
                    "mean": stage.mean,
                    "p50": stage.p50,
                    "p95": stage.p95,
                }
                for name, stage in self.stages.items()
            },
            "request_durations": self.request_durations,
        }
        Path(filepath).write_text(json.dumps(data, indent=2))

    def reset(self):
        """Reset all collected metrics."""
        self.stages.clear()
        self.request_durations.clear()


class CacheSimulator:
    """Simulate cache performance for RAG queries.

    Estimates cache hit rates based on query similarity and TTL settings.
    """

    def __init__(self, capacity: int = 10000, ttl_seconds: int = 3600):
        self.capacity = capacity
        self.ttl = ttl_seconds
        self.cache: dict[str, tuple[float, any]] = {}
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def query(self, key: str, timestamp: float = None) -> bool:
        """Simulate a cache lookup. Returns True if hit."""
        ts = timestamp or time.time()

        if key in self.cache:
            entry_ts, _ = self.cache[key]
            if ts - entry_ts < self.ttl:
                self.hits += 1
                return True
            else:
                del self.cache[key]
                self.evictions += 1

        self.misses += 1
        return False

    def store(self, key: str, value: any = None, timestamp: float = None):
        """Store a result in the cache."""
        ts = timestamp or time.time()

        if len(self.cache) >= self.capacity:
            # Evict oldest entry
            oldest_key = min(self.cache, key=lambda k: self.cache[k][0])
            del self.cache[oldest_key]
            self.evictions += 1

        self.cache[key] = (ts, value)

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0

    def report(self) -> str:
        total = self.hits + self.misses
        report = f"""
Cache Simulation Report
=======================
Total queries:  {total}
Cache hits:     {self.hits} ({self.hit_rate*100:.1f}%)
Cache misses:   {self.misses} ({(1-self.hit_rate)*100:.1f}%)
Evictions:      {self.evictions}
Cache size:     {len(self.cache)}/{self.capacity}
TTL:            {self.ttl}s

Estimated latency savings: {self.hits * 1.2:.0f}s
(assuming 1.2s average saved per cache hit)
"""
        print(report)
        return report


class BenchmarkRunner:
    """Load test RAG endpoints with realistic traffic patterns."""

    def __init__(self, endpoint: str = None):
        self.endpoint = endpoint
        self.results: list[dict] = []

    def run_sequential(self, queries: list[str], callback=None) -> list[dict]:
        """Run queries sequentially, measuring each."""
        for i, query in enumerate(queries):
            start = time.perf_counter()
            result = None
            error = None

            try:
                if callback:
                    result = callback(query)
            except Exception as e:
                error = str(e)

            duration = time.perf_counter() - start
            self.results.append({
                "query": query,
                "duration_ms": duration * 1000,
                "success": error is None,
                "error": error,
                "index": i,
            })

        return self.results

    def summary(self) -> dict:
        """Generate benchmark summary statistics."""
        durations = [r["duration_ms"] for r in self.results if r["success"]]
        errors = [r for r in self.results if not r["success"]]

        if not durations:
            return {"error": "No successful queries"}

        return {
            "total_queries": len(self.results),
            "successful": len(durations),
            "failed": len(errors),
            "mean_ms": round(statistics.mean(durations), 1),
            "median_ms": round(statistics.median(durations), 1),
            "p95_ms": round(sorted(durations)[int(len(durations) * 0.95)], 1) if len(durations) >= 2 else round(durations[0], 1),
            "min_ms": round(min(durations), 1),
            "max_ms": round(max(durations), 1),
            "throughput_qps": round(len(durations) / (sum(durations) / 1000), 2) if sum(durations) > 0 else 0,
        }


# --- Quick usage example ---
if __name__ == "__main__":
    print("RAG Latency Profiler — Demo\n")

    profiler = RAGProfiler(name="demo-pipeline")

    # Simulate 10 requests
    for i in range(10):
        profiler.start_request()

        with profiler.stage("query_parsing"):
            time.sleep(0.005)  # 5ms

        with profiler.stage("embedding"):
            time.sleep(0.08 + (i % 3) * 0.02)  # 80-120ms

        with profiler.stage("vector_search"):
            time.sleep(0.04 + (i % 5) * 0.01)  # 40-80ms

        with profiler.stage("reranking"):
            time.sleep(0.03)  # 30ms

        with profiler.stage("llm_generation"):
            time.sleep(0.3 + (i % 4) * 0.1)  # 300-600ms (the bottleneck)

        with profiler.stage("post_processing"):
            time.sleep(0.01)  # 10ms

        profiler.end_request()

    profiler.report()

    # Cache simulation
    print("\n--- Cache Simulation ---\n")
    cache = CacheSimulator(capacity=100, ttl_seconds=600)

    queries = ["what is RAG?", "how to chunk documents?", "embedding models comparison",
               "what is RAG?", "vector search optimization", "how to chunk documents?",
               "what is RAG?", "latency optimization", "how to chunk documents?",
               "what is RAG?"]

    for q in queries:
        hit = cache.query(q)
        if not hit:
            cache.store(q, f"answer to {q}")

    cache.report()
