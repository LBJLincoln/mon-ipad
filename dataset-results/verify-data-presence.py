#!/usr/bin/env python3
"""
DATA PRESENCE VERIFICATION SCRIPT
==================================
Checks whether the required data for Graph RAG and Quantitative RAG
is actually present in the databases before running any tests.

Databases checked:
- Neo4j: Entity nodes and relationships for graph questions
- Pinecone: Vector embeddings for context retrieval
- Supabase: Tabular data for quantitative questions

Usage:
  python3 verify-data-presence.py

Environment variables required:
  NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
  PINECONE_API_KEY, PINECONE_HOST
  POSTGRES_CONNECTION_STRING
"""

import json
import os
import sys
import re
from datetime import datetime

# ─── Configuration ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
QUESTIONS_FILE = os.path.join(REPO_DIR, "benchmark-workflows", "rag-1000-test-questions.json")
RESULTS_DIR = BASE_DIR

# Database credentials from environment
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt+s://38c949a2.databases.neo4j.io:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_HOST = os.environ.get("PINECONE_HOST", "https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io")
POSTGRES_CONN = os.environ.get("POSTGRES_CONNECTION_STRING", "")


def check_neo4j():
    """Check Neo4j for graph data presence."""
    results = {
        "status": "unchecked",
        "labels": [],
        "node_counts": {},
        "relationship_types": [],
        "tenant_data": {},
        "graph_data_ready": False,
        "details": {}
    }

    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

        with driver.session() as session:
            # Get labels
            res = session.run("CALL db.labels() YIELD label RETURN label")
            results["labels"] = [r["label"] for r in res]

            # Count nodes per label
            for label in results["labels"][:30]:
                res = session.run(f"MATCH (n:`{label}`) RETURN count(n) as cnt")
                results["node_counts"][label] = res.single()["cnt"]

            # Get relationship types
            res = session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")
            results["relationship_types"] = [r["relationshipType"] for r in res]

            # Check for benchmark tenant data
            res = session.run("""
                MATCH (n) WHERE n.tenant_id IS NOT NULL
                RETURN DISTINCT n.tenant_id as tid, count(n) as cnt
                ORDER BY cnt DESC LIMIT 20
            """)
            for r in res:
                results["tenant_data"][r["tid"]] = r["cnt"]

            # Check for community summaries (needed for graph RAG)
            res = session.run("MATCH (n) WHERE n.community IS NOT NULL RETURN count(n) as cnt")
            results["details"]["nodes_with_community"] = res.single()["cnt"]

            # Check for entity nodes with embeddings
            res = session.run("MATCH (n) WHERE n.embedding IS NOT NULL RETURN count(n) as cnt")
            results["details"]["nodes_with_embedding"] = res.single()["cnt"]

            # Check for specific graph RAG entities (sample from musique/2wikimultihopqa)
            sample_entities = ["John Knox", "Henry II", "Normandy", "SpongeBob", "Spongebob Squarepants"]
            found_entities = []
            for entity in sample_entities:
                res = session.run(
                    "MATCH (n) WHERE toLower(n.name) CONTAINS toLower($name) RETURN count(n) as cnt",
                    name=entity
                )
                cnt = res.single()["cnt"]
                if cnt > 0:
                    found_entities.append(entity)
            results["details"]["sample_entities_found"] = found_entities
            results["details"]["sample_entities_checked"] = sample_entities

            # Determine readiness
            total_nodes = sum(results["node_counts"].values())
            has_communities = results["details"].get("nodes_with_community", 0) > 0
            has_benchmark_tenant = "benchmark" in results["tenant_data"]

            results["graph_data_ready"] = total_nodes > 100 and (has_communities or has_benchmark_tenant)
            results["status"] = "checked"

        driver.close()

    except ImportError:
        results["status"] = "error"
        results["error"] = "neo4j package not installed. Run: pip install neo4j"
    except Exception as e:
        results["status"] = "error"
        results["error"] = str(e)

    return results


def check_pinecone():
    """Check Pinecone for vector embeddings presence."""
    results = {
        "status": "unchecked",
        "index_stats": {},
        "namespaces": {},
        "total_vectors": 0,
        "vector_data_ready": False,
        "details": {}
    }

    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(host=PINECONE_HOST)

        stats = index.describe_index_stats()
        stats_dict = stats.to_dict()

        results["total_vectors"] = stats_dict.get("total_vector_count", 0)
        results["namespaces"] = {}

        if "namespaces" in stats_dict:
            for ns_name, ns_info in stats_dict["namespaces"].items():
                results["namespaces"][ns_name] = ns_info.get("vector_count", 0)

        results["index_stats"] = {
            "dimension": stats_dict.get("dimension", 0),
            "total_vectors": results["total_vectors"],
            "namespace_count": len(results["namespaces"])
        }

        # Check for benchmark-specific namespaces
        benchmark_ns = [ns for ns in results["namespaces"] if "benchmark" in ns.lower()]
        results["details"]["benchmark_namespaces"] = benchmark_ns
        results["details"]["benchmark_vector_count"] = sum(
            results["namespaces"].get(ns, 0) for ns in benchmark_ns
        )

        # Check for dataset-specific namespaces
        dataset_names = ["musique", "2wikimultihopqa", "finqa", "tatqa", "convfinqa", "wikitablequestions"]
        for ds in dataset_names:
            matching = [ns for ns in results["namespaces"] if ds.lower() in ns.lower()]
            results["details"][f"ns_{ds}"] = matching

        results["vector_data_ready"] = results["total_vectors"] > 1000
        results["status"] = "checked"

    except ImportError:
        results["status"] = "error"
        results["error"] = "pinecone package not installed. Run: pip install pinecone"
    except Exception as e:
        results["status"] = "error"
        results["error"] = str(e)

    return results


def check_supabase():
    """Check Supabase for benchmark data presence."""
    results = {
        "status": "unchecked",
        "tables": {},
        "benchmark_questions": {},
        "benchmark_results": {},
        "tabular_data_ready": False,
        "details": {}
    }

    try:
        import psycopg2
        conn = psycopg2.connect(POSTGRES_CONN, connect_timeout=10)
        cur = conn.cursor()

        # List tables
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name
        """)
        for row in cur.fetchall():
            table = row[0]
            cur.execute(f'SELECT count(*) FROM "{table}"')
            results["tables"][table] = cur.fetchone()[0]

        # Check benchmark_questions table
        if "benchmark_questions" in results["tables"]:
            cur.execute("""
                SELECT dataset_name, count(*) as cnt
                FROM benchmark_questions
                GROUP BY dataset_name
                ORDER BY cnt DESC
            """)
            for row in cur.fetchall():
                results["benchmark_questions"][row[0]] = row[1]

        # Check benchmark_results table
        if "benchmark_results" in results["tables"]:
            cur.execute("""
                SELECT dataset_name,
                       count(*) as total,
                       count(actual_answer) as answered,
                       count(error) as errors
                FROM benchmark_results
                GROUP BY dataset_name
                ORDER BY total DESC
            """)
            for row in cur.fetchall():
                results["benchmark_results"][row[0]] = {
                    "total": row[1],
                    "answered": row[2],
                    "errors": row[3]
                }

        # Check for tabular/financial data tables
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            AND (table_name LIKE '%transaction%' OR table_name LIKE '%account%'
                 OR table_name LIKE '%financial%' OR table_name LIKE '%table_%')
        """)
        results["details"]["financial_tables"] = [r[0] for r in cur.fetchall()]

        # Check if transactions table has benchmark data
        if "transactions" in results["tables"]:
            cur.execute("""
                SELECT tenant_id, count(*) FROM transactions
                WHERE tenant_id LIKE '%benchmark%'
                GROUP BY tenant_id LIMIT 10
            """)
            results["details"]["benchmark_transactions"] = {
                r[0]: r[1] for r in cur.fetchall()
            }

        results["tabular_data_ready"] = bool(results["details"].get("financial_tables"))
        results["status"] = "checked"

        cur.close()
        conn.close()

    except ImportError:
        results["status"] = "error"
        results["error"] = "psycopg2 package not installed. Run: pip install psycopg2-binary"
    except Exception as e:
        results["status"] = "error"
        results["error"] = str(e)

    return results


def update_result_files(neo4j_results, pinecone_results, supabase_results):
    """Update dataset result files with data verification info."""
    now = datetime.now().isoformat()

    # Specialized dataset files
    dataset_files = {
        "musique": "results-musique.json",
        "2wikimultihopqa": "results-2wikimultihopqa.json",
        "finqa-quantitative": "results-finqa-quantitative.json",
        "tatqa": "results-tatqa.json",
        "convfinqa": "results-convfinqa.json",
        "wikitablequestions": "results-wikitablequestions.json",
    }

    for ds_name, filename in dataset_files.items():
        filepath = os.path.join(RESULTS_DIR, filename)
        if not os.path.exists(filepath):
            continue

        with open(filepath) as f:
            data = json.load(f)

        rag_target = data.get("rag_target", "")

        if rag_target == "graph":
            data["data_verification"] = {
                "neo4j_status": neo4j_results["status"],
                "neo4j_total_nodes": sum(neo4j_results.get("node_counts", {}).values()),
                "neo4j_has_communities": neo4j_results.get("details", {}).get("nodes_with_community", 0) > 0,
                "neo4j_has_benchmark_tenant": "benchmark" in neo4j_results.get("tenant_data", {}),
                "pinecone_status": pinecone_results["status"],
                "pinecone_total_vectors": pinecone_results.get("total_vectors", 0),
                "pinecone_benchmark_ns": pinecone_results.get("details", {}).get("benchmark_namespaces", []),
                "verified_at": now,
                "data_ready": neo4j_results.get("graph_data_ready", False)
            }
        elif rag_target == "quantitative":
            data["data_verification"] = {
                "supabase_status": supabase_results["status"],
                "supabase_tables": list(supabase_results.get("tables", {}).keys()),
                "supabase_financial_tables": supabase_results.get("details", {}).get("financial_tables", []),
                "pinecone_status": pinecone_results["status"],
                "pinecone_total_vectors": pinecone_results.get("total_vectors", 0),
                "verified_at": now,
                "data_ready": supabase_results.get("tabular_data_ready", False)
            }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    print("Updated dataset result files with verification data")


def main():
    print("=" * 70)
    print("  DATA PRESENCE VERIFICATION — Graph RAG & Quantitative RAG")
    print("=" * 70)

    # Check credentials
    missing = []
    if not NEO4J_PASSWORD:
        missing.append("NEO4J_PASSWORD")
    if not PINECONE_API_KEY:
        missing.append("PINECONE_API_KEY")
    if not POSTGRES_CONN:
        missing.append("POSTGRES_CONNECTION_STRING")

    if missing:
        print(f"\n  WARNING: Missing environment variables: {', '.join(missing)}")
        print("  Set them before running. Example:")
        print('    export NEO4J_PASSWORD="your-password"')
        print('    export PINECONE_API_KEY="your-key"')
        print('    export POSTGRES_CONNECTION_STRING="postgresql://..."')

    # ── Neo4j ──
    print("\n[1/3] Checking Neo4j (Graph RAG)...")
    neo4j_results = check_neo4j()
    if neo4j_results["status"] == "checked":
        total_nodes = sum(neo4j_results["node_counts"].values())
        print(f"  Labels: {len(neo4j_results['labels'])}")
        print(f"  Total nodes: {total_nodes}")
        print(f"  Relationships: {len(neo4j_results['relationship_types'])}")
        print(f"  Communities: {neo4j_results['details'].get('nodes_with_community', 0)}")
        print(f"  Benchmark tenant: {'benchmark' in neo4j_results['tenant_data']}")
        print(f"  Sample entities found: {neo4j_results['details'].get('sample_entities_found', [])}")
        print(f"  GRAPH DATA READY: {neo4j_results['graph_data_ready']}")
    else:
        print(f"  Status: {neo4j_results['status']}")
        print(f"  Error: {neo4j_results.get('error', 'unknown')}")

    # ── Pinecone ──
    print("\n[2/3] Checking Pinecone (Vector Embeddings)...")
    pinecone_results = check_pinecone()
    if pinecone_results["status"] == "checked":
        print(f"  Total vectors: {pinecone_results['total_vectors']}")
        print(f"  Namespaces: {len(pinecone_results['namespaces'])}")
        print(f"  Benchmark namespaces: {pinecone_results['details'].get('benchmark_namespaces', [])}")
        print(f"  VECTOR DATA READY: {pinecone_results['vector_data_ready']}")
    else:
        print(f"  Status: {pinecone_results['status']}")
        print(f"  Error: {pinecone_results.get('error', 'unknown')}")

    # ── Supabase ──
    print("\n[3/3] Checking Supabase (Tabular/Quantitative Data)...")
    supabase_results = check_supabase()
    if supabase_results["status"] == "checked":
        print(f"  Tables: {len(supabase_results['tables'])}")
        print(f"  Benchmark questions: {sum(supabase_results['benchmark_questions'].values())}")
        print(f"  Financial tables: {supabase_results['details'].get('financial_tables', [])}")
        print(f"  TABULAR DATA READY: {supabase_results['tabular_data_ready']}")
    else:
        print(f"  Status: {supabase_results['status']}")
        print(f"  Error: {supabase_results.get('error', 'unknown')}")

    # ── Update result files ──
    print("\n[4/4] Updating dataset result files...")
    update_result_files(neo4j_results, pinecone_results, supabase_results)

    # ── Save full verification report ──
    report = {
        "title": "Data Presence Verification Report",
        "generated_at": datetime.now().isoformat(),
        "neo4j": neo4j_results,
        "pinecone": pinecone_results,
        "supabase": supabase_results,
        "overall_readiness": {
            "graph_rag_ready": neo4j_results.get("graph_data_ready", False),
            "quantitative_rag_ready": supabase_results.get("tabular_data_ready", False),
            "vector_search_ready": pinecone_results.get("vector_data_ready", False),
        },
        "recommendations": []
    }

    if not neo4j_results.get("graph_data_ready"):
        report["recommendations"].append(
            "CRITICAL: Neo4j does not have graph data for benchmark questions. "
            "Run the ingestion workflow to load musique and 2wikimultihopqa entities."
        )
    if not supabase_results.get("tabular_data_ready"):
        report["recommendations"].append(
            "CRITICAL: Supabase does not have tabular data for quantitative questions. "
            "Ingest finqa, tatqa, convfinqa, wikitablequestions table data."
        )
    if not pinecone_results.get("vector_data_ready"):
        report["recommendations"].append(
            "CRITICAL: Pinecone does not have sufficient vector embeddings. "
            "Run the embedding pipeline for all benchmark datasets."
        )

    report_path = os.path.join(RESULTS_DIR, "data-verification-report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport saved: {report_path}")

    # ── Summary ──
    print(f"\n{'='*70}")
    print("  VERIFICATION SUMMARY")
    print(f"{'='*70}")
    print(f"  Graph RAG ready:        {report['overall_readiness']['graph_rag_ready']}")
    print(f"  Quantitative RAG ready: {report['overall_readiness']['quantitative_rag_ready']}")
    print(f"  Vector search ready:    {report['overall_readiness']['vector_search_ready']}")

    if report["recommendations"]:
        print(f"\n  RECOMMENDATIONS:")
        for i, rec in enumerate(report["recommendations"], 1):
            print(f"    {i}. {rec}")

    print(f"\n{'='*70}")

    return report


if __name__ == "__main__":
    main()
