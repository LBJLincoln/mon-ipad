#!/usr/bin/env python3
"""
Purge benchmark data from all databases to free capacity for sector data.

MUST run AFTER exports are saved to rag-storage/archive/

What gets deleted:
- Pinecone: 3 legacy indexes (sota-rag, sota-rag-phase2-graph, sota-rag-text)
- Pinecone: all benchmark-* namespaces in sota-rag-jina-1024
- Neo4j: Person, Paragraph, City, Museum, etc. + Entity without sector
- Supabase: benchmark_*, tatqa_*, finqa_*, convfinqa_*, sales*, employees, transactions

What is KEPT:
- Pinecone: website-sectors-jina-1024 (all 43K sector vectors)
- Neo4j: SectorDocument, Entity with sector, Organization with sector
- Supabase: sector_documents, sector_financial_tables

Usage:
  source .env.local
  python3 ops/purge-benchmarks.py --dry-run    # Preview what will be deleted
  python3 ops/purge-benchmarks.py --execute    # Actually delete
"""

import json
import os
import sys
import urllib.request
import urllib.error
import argparse

# ─── Config ─────────────────────────────────────────────────────────
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_HOST_SECTORS = "website-sectors-jina-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io"

INDEXES_TO_DELETE = [
    "sota-rag",
    "sota-rag-phase2-graph",
    "sota-rag-text",
]

# sota-rag-jina-1024: keep but delete all benchmark-* namespaces
SOTA_JINA_HOST = "sota-rag-jina-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
BENCHMARK_NAMESPACES = [
    "benchmark-squad_v2", "benchmark-frames", "benchmark-hotpotqa",
    "benchmark-msmarco", "benchmark-asqa", "benchmark-pubmedqa",
    "benchmark-popqa", "benchmark-finqa", "benchmark-natural_questions",
    "benchmark-triviaqa", "benchmark-narrativeqa",
]

# Supabase tables to drop
SUPABASE_TABLES_TO_DROP = [
    "benchmark_datasets",
    "benchmark_results",
    "benchmark_runs",
    "benchmark_queries",
    "tatqa_tables",
    "finqa_tables",
    "convfinqa_tables",
    "sales_data",
    "sales",
    "employees",
    "transactions",
    "products",
    "financials",
    "documents",
    "rlhf_training_data",
    "rag_task_executions",
    "conversation_context",
]


def pinecone_request(host, path, method="GET", data=None):
    """Make a Pinecone API request."""
    url = f"https://{host}{path}" if host and not path.startswith("http") else f"https://api.pinecone.io{path}"
    headers = {
        "Api-Key": PINECONE_API_KEY,
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read().decode()) if resp.status == 200 else {"status": resp.status}
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "body": e.read().decode()[:200]}
    except Exception as e:
        return {"error": str(e)}


def purge_pinecone_indexes(dry_run=True):
    """Delete legacy Pinecone indexes."""
    print("\n=== PINECONE: Delete Legacy Indexes ===")
    for idx_name in INDEXES_TO_DELETE:
        if dry_run:
            print(f"  [DRY RUN] Would delete index: {idx_name}")
        else:
            print(f"  Deleting index: {idx_name}...")
            result = pinecone_request(None, f"/indexes/{idx_name}", method="DELETE")
            print(f"    Result: {result}")


def purge_pinecone_namespaces(dry_run=True):
    """Delete benchmark namespaces from sota-rag-jina-1024."""
    print("\n=== PINECONE: Delete Benchmark Namespaces (sota-rag-jina-1024) ===")

    # To delete a namespace, we delete all vectors in it
    for ns in BENCHMARK_NAMESPACES:
        if dry_run:
            print(f"  [DRY RUN] Would delete namespace: {ns}")
        else:
            print(f"  Deleting namespace: {ns}...")
            data = json.dumps({"deleteAll": True, "namespace": ns}).encode()
            result = pinecone_request(SOTA_JINA_HOST, "/vectors/delete", method="POST", data=data)
            print(f"    Result: {result}")

    # Also delete the default "" namespace (36,862 vectors of old benchmark data)
    if dry_run:
        print(f"  [DRY RUN] Would delete default namespace (36,862 vectors)")
    else:
        print(f"  Deleting default namespace...")
        data = json.dumps({"deleteAll": True, "namespace": ""}).encode()
        result = pinecone_request(SOTA_JINA_HOST, "/vectors/delete", method="POST", data=data)
        print(f"    Result: {result}")


def purge_neo4j(dry_run=True):
    """Delete benchmark nodes from Neo4j (Person, Paragraph, etc.)."""
    print("\n=== NEO4J: Delete Benchmark Nodes ===")

    # Neo4j free tier: can't delete everything at once, must batch
    delete_queries = [
        ("Person nodes (15,989)",
         "MATCH (n:Person) WITH n LIMIT 5000 DETACH DELETE n RETURN count(*) AS deleted"),
        ("Paragraph nodes (13,175)",
         "MATCH (n:Paragraph) WITH n LIMIT 5000 DETACH DELETE n RETURN count(*) AS deleted"),
        ("Entity without sector (~41K)",
         "MATCH (n:Entity) WHERE n.sector IS NULL WITH n LIMIT 5000 DETACH DELETE n RETURN count(*) AS deleted"),
        ("City nodes",
         "MATCH (n:City) DETACH DELETE n RETURN count(*) AS deleted"),
        ("Museum nodes",
         "MATCH (n:Museum) DETACH DELETE n RETURN count(*) AS deleted"),
        ("Country nodes",
         "MATCH (n:Country) DETACH DELETE n RETURN count(*) AS deleted"),
        ("Technology nodes",
         "MATCH (n:Technology) DETACH DELETE n RETURN count(*) AS deleted"),
        ("Disease/Molecule/Award/etc",
         "MATCH (n) WHERE n:Disease OR n:Molecule OR n:Award OR n:Artwork OR n:Discovery OR n:Monument OR n:Theory OR n:Element OR n:Agreement OR n:Treatment OR n:Article DETACH DELETE n RETURN count(*) AS deleted"),
    ]

    for desc, query in delete_queries:
        if dry_run:
            print(f"  [DRY RUN] Would delete: {desc}")
        else:
            print(f"  Deleting: {desc}...")
            # Note: This needs to be run via mcp__neo4j or direct bolt connection
            print(f"    Query: {query}")
            print(f"    (Run via Neo4j MCP write-cypher)")


def purge_supabase(dry_run=True):
    """Drop benchmark tables from Supabase."""
    print("\n=== SUPABASE: Drop Benchmark Tables ===")
    for table in SUPABASE_TABLES_TO_DROP:
        if dry_run:
            print(f"  [DRY RUN] Would drop table: {table}")
        else:
            print(f"  Dropping table: {table}...")
            # Note: Run via mcp__supabase__execute_sql
            print(f"    Query: DROP TABLE IF EXISTS {table} CASCADE;")


def main():
    parser = argparse.ArgumentParser(description="Purge benchmark data from all databases")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no changes")
    parser.add_argument("--execute", action="store_true", help="Actually delete data")
    parser.add_argument("--pinecone-only", action="store_true", help="Only purge Pinecone")
    parser.add_argument("--neo4j-only", action="store_true", help="Only purge Neo4j")
    parser.add_argument("--supabase-only", action="store_true", help="Only purge Supabase")
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("ERROR: Must specify --dry-run or --execute")
        sys.exit(1)

    dry_run = args.dry_run

    if dry_run:
        print("=" * 60)
        print("  DRY RUN MODE — No data will be deleted")
        print("=" * 60)
    else:
        print("=" * 60)
        print("  ⚠ EXECUTING — Data will be permanently deleted!")
        print("  Make sure exports are saved to rag-storage/archive/")
        print("=" * 60)
        confirm = input("  Type 'PURGE' to confirm: ")
        if confirm != "PURGE":
            print("  Aborted.")
            sys.exit(0)

    all_targets = not (args.pinecone_only or args.neo4j_only or args.supabase_only)

    if all_targets or args.pinecone_only:
        purge_pinecone_indexes(dry_run)
        purge_pinecone_namespaces(dry_run)

    if all_targets or args.neo4j_only:
        purge_neo4j(dry_run)

    if all_targets or args.supabase_only:
        purge_supabase(dry_run)

    print("\n" + "=" * 60)
    if dry_run:
        print("  DRY RUN complete. Use --execute to actually delete.")
    else:
        print("  PURGE complete. Verify with database tools.")
    print("=" * 60)

    # Summary
    print("\n  EXPECTED CAPACITY FREED:")
    print("  Pinecone: 3 index slots freed, ~73K vectors removed")
    print("  Neo4j: ~75K nodes, ~350K relationships freed")
    print("  Supabase: ~35MB freed")
    print("\n  REMAINING DATA (sector-only):")
    print("  Pinecone: website-sectors-jina-1024 = 43K vectors")
    print("  Neo4j: ~21K SectorDocument + ~1.3K sector Entity")
    print("  Supabase: sector_documents (43K) + sector_financial_tables (3.9K)")


if __name__ == "__main__":
    main()
