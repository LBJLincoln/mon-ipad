#!/usr/bin/env python3
"""
Master script: Populate all 3 databases for the RAG benchmark.

Execution order (following blocker priority):
1. B3: Create financial tables in Supabase + seed data
2. B2: Replace pseudo-vectors with real embeddings in Pinecone
3. B1: Populate Neo4j with entity graph for Graph RAG

Prerequisites:
  - Environment variables: SUPABASE_PASSWORD, PINECONE_API_KEY, NEO4J_PASSWORD
  - For real embeddings: OPENAI_API_KEY or OPENROUTER_API_KEY
  - psql client installed

Usage:
  python populate-all-databases.py [--skip-financial] [--skip-embeddings] [--skip-neo4j]
"""
import json
import os
import sys
import subprocess
import time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SUPABASE_CONN = f"postgresql://postgres:{os.environ.get('SUPABASE_PASSWORD', '')}@db.ayqviqmxifzmhphiqfmj.supabase.co:5432/postgres"


def check_prerequisites():
    """Check that all required env vars and tools are available."""
    print("=" * 60)
    print("CHECKING PREREQUISITES")
    print("=" * 60)

    missing = []
    for var in ["SUPABASE_PASSWORD", "PINECONE_API_KEY", "NEO4J_PASSWORD"]:
        if not os.environ.get(var):
            missing.append(var)
            print(f"  MISSING: {var}")
        else:
            print(f"  OK: {var}")

    # Check for embedding API key
    has_embedding = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if not has_embedding:
        print(f"  WARNING: No OPENAI_API_KEY or OPENROUTER_API_KEY — embeddings will be skipped")
    else:
        print(f"  OK: Embedding API key found")

    # Check psql
    try:
        result = subprocess.run(["psql", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"  OK: psql available ({result.stdout.strip()})")
        else:
            missing.append("psql")
            print(f"  MISSING: psql client")
    except FileNotFoundError:
        missing.append("psql")
        print(f"  MISSING: psql client not found")

    if missing:
        print(f"\n  FATAL: Missing required: {', '.join(missing)}")
        print("  Set environment variables and retry.")
        return False

    return True


def run_financial_tables():
    """B3: Create financial tables and seed data in Supabase."""
    print("\n" + "=" * 60)
    print("B3: CREATING FINANCIAL TABLES IN SUPABASE")
    print("=" * 60)

    sql_file = os.path.join(SCRIPT_DIR, "financial-tables-migration.sql")
    if not os.path.exists(sql_file):
        print(f"  ERROR: SQL file not found: {sql_file}")
        return False

    result = subprocess.run(
        ["psql", SUPABASE_CONN, "-f", sql_file],
        capture_output=True, text=True, timeout=120
    )

    if result.returncode == 0:
        print(f"  SUCCESS: Financial tables created and seeded")
        # Print the verification counts
        for line in result.stdout.split("\n"):
            if line.strip():
                print(f"    {line.strip()}")
        return True
    else:
        print(f"  OUTPUT: {result.stdout[:1000]}")
        if result.stderr:
            # Filter out NOTICEs which are informational
            errors = [l for l in result.stderr.split("\n") if "ERROR" in l]
            if errors:
                print(f"  ERRORS: {chr(10).join(errors[:5])}")
            else:
                print(f"  (Only notices/warnings, no fatal errors)")
                return True
        return False


def run_embeddings():
    """B2: Replace pseudo-vectors with real embeddings."""
    print("\n" + "=" * 60)
    print("B2: POPULATING PINECONE WITH REAL EMBEDDINGS")
    print("=" * 60)

    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")):
        print("  SKIPPED: No embedding API key available")
        return True

    script = os.path.join(SCRIPT_DIR, "populate-pinecone-embeddings.py")
    if not os.path.exists(script):
        print(f"  ERROR: Script not found: {script}")
        return False

    result = subprocess.run(
        [sys.executable, script],
        capture_output=False,  # Stream output
        timeout=3600  # 1 hour max
    )

    return result.returncode == 0


def run_neo4j():
    """B1: Populate Neo4j with entity graph."""
    print("\n" + "=" * 60)
    print("B1: POPULATING NEO4J WITH ENTITY GRAPH")
    print("=" * 60)

    script = os.path.join(SCRIPT_DIR, "populate-neo4j-entities.py")
    if not os.path.exists(script):
        print(f"  ERROR: Script not found: {script}")
        return False

    result = subprocess.run(
        [sys.executable, script],
        capture_output=False,
        timeout=3600
    )

    return result.returncode == 0


def verify_all():
    """Verify all databases have been populated."""
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    # Check Supabase financial tables
    print("\n  Supabase Financial Tables:")
    for table in ["financials", "balance_sheet", "sales_data", "employees", "products"]:
        result = subprocess.run(
            ["psql", SUPABASE_CONN, "-t", "-A", "-c",
             f"SELECT COUNT(*) FROM {table} WHERE tenant_id = 'benchmark';"],
            capture_output=True, text=True, timeout=10
        )
        count = result.stdout.strip() if result.returncode == 0 else "ERROR"
        print(f"    {table}: {count} rows")

    # Check Supabase benchmark data
    print("\n  Supabase Benchmark Datasets:")
    result = subprocess.run(
        ["psql", SUPABASE_CONN, "-t", "-A", "-c",
         "SELECT dataset_name, COUNT(*) FROM benchmark_datasets WHERE tenant_id = 'benchmark' GROUP BY dataset_name ORDER BY COUNT(*) DESC;"],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                print(f"    {line.strip()}")

    # Check Pinecone
    print("\n  Pinecone Index:")
    try:
        from urllib import request as urllib_request
        req = urllib_request.Request(
            f"https://n8nultimate-a4mkzmz.svc.aped-4627-b74a.pinecone.io/describe_index_stats",
            data=b"{}",
            headers={
                "Api-Key": os.environ.get("PINECONE_API_KEY", ""),
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib_request.urlopen(req, timeout=10) as resp:
            stats = json.loads(resp.read())
            print(f"    Total vectors: {stats.get('totalVectorCount', 0)}")
            for ns, info in stats.get("namespaces", {}).items():
                print(f"    Namespace '{ns}': {info.get('vectorCount', 0)}")
    except Exception as e:
        print(f"    Pinecone check failed: {e}")

    # Check Neo4j
    print("\n  Neo4j Graph:")
    try:
        import base64
        neo4j_auth = base64.b64encode(
            f"{os.environ.get('NEO4J_USER', 'neo4j')}:{os.environ.get('NEO4J_PASSWORD', '')}".encode()
        ).decode()
        body = json.dumps({
            "statements": [
                {"statement": "MATCH (n) RETURN labels(n)[0] as label, count(*) as cnt ORDER BY cnt DESC LIMIT 10"},
                {"statement": "MATCH ()-[r]->() RETURN type(r) as rel, count(*) as cnt ORDER BY cnt DESC LIMIT 10"}
            ]
        }).encode()
        req = urllib_request.Request(
            "https://38c949a2.databases.neo4j.io:7473/db/neo4j/tx/commit",
            data=body,
            headers={
                "Authorization": f"Basic {neo4j_auth}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib_request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            if result.get("results"):
                print("    Node labels:")
                for row in result["results"][0].get("data", []):
                    vals = row.get("row", [])
                    if vals:
                        print(f"      {vals[0]}: {vals[1]}")
                if len(result["results"]) > 1:
                    print("    Relationship types:")
                    for row in result["results"][1].get("data", []):
                        vals = row.get("row", [])
                        if vals:
                            print(f"      {vals[0]}: {vals[1]}")
    except Exception as e:
        print(f"    Neo4j check failed: {e}")


if __name__ == "__main__":
    args = sys.argv[1:]
    skip_financial = "--skip-financial" in args
    skip_embeddings = "--skip-embeddings" in args
    skip_neo4j = "--skip-neo4j" in args

    print("=" * 60)
    print("RAG BENCHMARK — DATABASE POPULATION MASTER SCRIPT")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)

    if not check_prerequisites():
        sys.exit(1)

    results = {}
    start = time.time()

    # B3: Financial tables
    if not skip_financial:
        results["B3_financial"] = run_financial_tables()
    else:
        print("\n  SKIPPED: Financial tables (--skip-financial)")

    # B2: Embeddings
    if not skip_embeddings:
        results["B2_embeddings"] = run_embeddings()
    else:
        print("\n  SKIPPED: Embeddings (--skip-embeddings)")

    # B1: Neo4j
    if not skip_neo4j:
        results["B1_neo4j"] = run_neo4j()
    else:
        print("\n  SKIPPED: Neo4j (--skip-neo4j)")

    elapsed = time.time() - start

    # Verify
    try:
        verify_all()
    except Exception as e:
        print(f"\n  Verification error: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("POPULATION SUMMARY")
    print("=" * 60)
    for step, success in results.items():
        status = "OK" if success else "FAILED"
        print(f"  [{status}] {step}")
    print(f"\n  Total duration: {elapsed:.1f}s")
    print("=" * 60)

    # Exit with error if any step failed
    if not all(results.values()):
        sys.exit(1)
