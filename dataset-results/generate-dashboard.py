#!/usr/bin/env python3
"""
DATASET ANALYSIS DASHBOARD GENERATOR
======================================
Reads all per-dataset result files and generates a master dashboard
showing the current state of all datasets, questions, and answers.

Usage:
  python3 generate-dashboard.py
"""

import json
import os
from datetime import datetime

RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))


def load_result_file(filepath):
    """Load a dataset result file."""
    try:
        with open(filepath) as f:
            return json.load(f)
    except Exception as e:
        return None


def main():
    print("=" * 70)
    print("  GENERATING MASTER ANALYSIS DASHBOARD")
    print("=" * 70)

    # Find all result files
    result_files = sorted([f for f in os.listdir(RESULTS_DIR) if f.startswith("results-") and f.endswith(".json")])

    # Categorize datasets
    specialized_graph = []
    specialized_quant = []
    benchmark = []

    all_datasets = []

    for filename in result_files:
        filepath = os.path.join(RESULTS_DIR, filename)
        data = load_result_file(filepath)
        if not data:
            continue

        ds_name = data.get("dataset_name", filename.replace("results-", "").replace(".json", ""))
        rag_target = data.get("rag_target", "unknown")
        source = data.get("source", "")
        category = data.get("category", "")
        total = data.get("total_questions", 0)
        summary = data.get("summary", {})

        entry = {
            "file": filename,
            "dataset_name": ds_name,
            "rag_target": rag_target,
            "category": category,
            "total_questions": total,
            "total_tested": summary.get("total_tested", 0),
            "total_answered": summary.get("total_answered", 0),
            "total_errors": summary.get("total_errors", 0),
            "avg_f1": summary.get("avg_f1", 0),
            "answer_rate": summary.get("answer_rate", "0%"),
            "status": summary.get("status", "UNKNOWN"),
            "data_ready": data.get("data_verification", {}).get("data_ready", None)
        }

        all_datasets.append(entry)

        if source == "specialized_1000" or category in ("multi_hop_qa", "domain_finance", "table_qa"):
            if rag_target == "graph":
                specialized_graph.append(entry)
            elif rag_target == "quantitative":
                specialized_quant.append(entry)
        elif category == "benchmark" or total > 500:
            benchmark.append(entry)

    # Compute totals
    total_questions = sum(d["total_questions"] for d in all_datasets)
    total_tested = sum(d["total_tested"] for d in all_datasets)
    total_answered = sum(d["total_answered"] for d in all_datasets)
    total_errors = sum(d["total_errors"] for d in all_datasets)

    # Specialized totals
    spec_graph_total = sum(d["total_questions"] for d in specialized_graph)
    spec_graph_tested = sum(d["total_tested"] for d in specialized_graph)
    spec_graph_answered = sum(d["total_answered"] for d in specialized_graph)

    spec_quant_total = sum(d["total_questions"] for d in specialized_quant)
    spec_quant_tested = sum(d["total_tested"] for d in specialized_quant)
    spec_quant_answered = sum(d["total_answered"] for d in specialized_quant)

    bench_total = sum(d["total_questions"] for d in benchmark)
    bench_tested = sum(d["total_tested"] for d in benchmark)
    bench_answered = sum(d["total_answered"] for d in benchmark)

    # Build dashboard
    dashboard = {
        "title": "RAG Testing — Master Analysis Dashboard",
        "generated_at": datetime.now().isoformat(),
        "overview": {
            "total_datasets": len(all_datasets),
            "total_questions": total_questions,
            "total_tested": total_tested,
            "total_answered": total_answered,
            "total_errors": total_errors,
            "overall_answer_rate": f"{total_answered/total_tested*100:.1f}%" if total_tested > 0 else "0%",
            "overall_test_coverage": f"{total_tested/total_questions*100:.1f}%" if total_questions > 0 else "0%"
        },
        "specialized_graph_rag": {
            "description": "Graph RAG questions requiring multi-hop reasoning (Neo4j + entity traversal)",
            "datasets": ["musique", "2wikimultihopqa"],
            "total_questions": spec_graph_total,
            "total_tested": spec_graph_tested,
            "total_answered": spec_graph_answered,
            "answer_rate": f"{spec_graph_answered/spec_graph_tested*100:.1f}%" if spec_graph_tested > 0 else "0%",
            "details": specialized_graph,
            "known_issues": [
                "Graph RAG returns raw community summaries instead of LLM answers",
                "Neo4j data may not contain entities from musique/2wikimultihopqa",
                "Routing accuracy for graph questions is only ~21.6%"
            ]
        },
        "specialized_quantitative_rag": {
            "description": "Quantitative RAG questions requiring numerical/tabular reasoning (Text-to-SQL)",
            "datasets": ["finqa", "tatqa", "convfinqa", "wikitablequestions"],
            "total_questions": spec_quant_total,
            "total_tested": spec_quant_tested,
            "total_answered": spec_quant_answered,
            "answer_rate": f"{spec_quant_answered/spec_quant_tested*100:.1f}%" if spec_quant_tested > 0 else "0%",
            "details": specialized_quant,
            "known_issues": [
                "Quantitative RAG needs tabular data ingested into SQL tables",
                "Text-to-SQL pipeline returns NULL when data is missing",
                "Table data from finqa/tatqa needs specific schema mapping"
            ]
        },
        "benchmark_standard_rag": {
            "description": "Standard RAG benchmark questions (originally all errored due to fetch() bug)",
            "datasets": [d["dataset_name"] for d in benchmark],
            "total_questions": bench_total,
            "total_tested": bench_tested,
            "total_answered": bench_answered,
            "answer_rate": f"{bench_answered/bench_tested*100:.1f}%" if bench_tested > 0 else "0%",
            "details": benchmark,
            "known_issues": [
                "All 28,053 questions errored with 'fetch is not defined'",
                "Bug was fixed in later workflow versions",
                "Need to re-run after fix"
            ]
        },
        "already_answered_positive": {
            "description": "Questions that received a valid answer with F1 > 0",
            "count": 0,
            "details": []
        },
        "action_items": {
            "priority_1": {
                "action": "Ingest Graph RAG data into Neo4j",
                "description": "Load musique and 2wikimultihopqa entity data with relationships into Neo4j. Without this data, graph RAG questions return 'context does not contain information'.",
                "datasets_affected": ["musique", "2wikimultihopqa"],
                "questions_affected": spec_graph_total
            },
            "priority_2": {
                "action": "Ingest Quantitative RAG data into Supabase",
                "description": "Load finqa, tatqa, convfinqa, wikitablequestions tabular data into SQL tables. Without this, Text-to-SQL returns NULL.",
                "datasets_affected": ["finqa", "tatqa", "convfinqa", "wikitablequestions"],
                "questions_affected": spec_quant_total
            },
            "priority_3": {
                "action": "Fix Graph RAG answer extraction",
                "description": "Graph RAG returns raw community summaries instead of LLM-generated answers. Fix the answer extraction node in WF2.",
                "workflow": "TEST - SOTA 2026 - WF2 Graph RAG V3.3"
            },
            "priority_4": {
                "action": "Re-run benchmark questions with fixed workflows",
                "description": "The fetch() bug is fixed. Re-run 28,053 benchmark questions through Standard RAG.",
                "questions_affected": bench_total
            }
        },
        "per_dataset_breakdown": all_datasets
    }

    # Count actually answered questions with positive F1
    for entry in all_datasets:
        filepath = os.path.join(RESULTS_DIR, entry["file"])
        data = load_result_file(filepath)
        if data and "questions" in data:
            for q in data["questions"]:
                if q.get("f1_score") and q["f1_score"] > 0 and q.get("actual_answer"):
                    dashboard["already_answered_positive"]["count"] += 1
                    dashboard["already_answered_positive"]["details"].append({
                        "dataset": entry["dataset_name"],
                        "question": q.get("question", "")[:150],
                        "expected": q.get("expected_answer", "")[:100],
                        "actual": q.get("actual_answer", "")[:200],
                        "f1": q["f1_score"]
                    })

    # Save dashboard
    dashboard_path = os.path.join(RESULTS_DIR, "master-dashboard.json")
    with open(dashboard_path, "w") as f:
        json.dump(dashboard, f, indent=2, ensure_ascii=False)
    print(f"\nDashboard saved: {dashboard_path}")

    # Print summary
    print(f"\n{'─'*70}")
    print(f"  SUMMARY")
    print(f"{'─'*70}")
    print(f"  Total datasets:     {len(all_datasets)}")
    print(f"  Total questions:    {total_questions}")
    print(f"  Total tested:       {total_tested}")
    print(f"  Total answered:     {total_answered}")
    print(f"  Answer rate:        {dashboard['overview']['overall_answer_rate']}")
    print(f"  Test coverage:      {dashboard['overview']['overall_test_coverage']}")
    print(f"  Positive answers:   {dashboard['already_answered_positive']['count']}")
    print(f"\n  Graph RAG:          {spec_graph_tested}/{spec_graph_total} tested, {spec_graph_answered} answered")
    print(f"  Quantitative RAG:   {spec_quant_tested}/{spec_quant_total} tested, {spec_quant_answered} answered")
    print(f"  Benchmark (Std):    {bench_tested}/{bench_total} tested, {bench_answered} answered")
    print(f"{'─'*70}")

    return dashboard


if __name__ == "__main__":
    main()
