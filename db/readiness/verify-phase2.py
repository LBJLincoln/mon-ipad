#!/usr/bin/env python3
"""
Phase 2 Database Readiness Verification Script.

Checks all three databases (Supabase, Neo4j, Pinecone) and the Phase 2 dataset file
to determine readiness for Phase 2 evaluation (1,000 questions).

Phase 2 requirements:
- Neo4j: ~2,500 nodes, ~3,000 relationships (for musique + 2wikimultihopqa)
- Supabase: ~10,000 rows (for finqa, tatqa, convfinqa tables)
- Pinecone: No additional ingestion needed (Phase 2 focuses on graph + quant)
- Dataset file: datasets/phase-2/hf-1000.json with 1,000 questions
"""
import json
import os
import sys
import base64
import subprocess
import time
from datetime import datetime
from urllib import request, error

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============================================================
# Database connection details
# ============================================================
SUPABASE_PASSWORD = os.environ.get("SUPABASE_PASSWORD", "")
SUPABASE_CONN = f"postgresql://postgres.ayqviqmxifzmhphiqfmj:{SUPABASE_PASSWORD}@aws-1-eu-west-1.pooler.supabase.com:6543/postgres"

NEO4J_HOST = "38c949a2.databases.neo4j.io"
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")
NEO4J_HTTP_URL = f"https://{NEO4J_HOST}/db/neo4j/query/v2"
NEO4J_AUTH = base64.b64encode(f"{NEO4J_USER}:{NEO4J_PASSWORD}".encode()).decode()

PINECONE_HOST = os.environ.get("PINECONE_HOST", "https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io").rstrip("/")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")


def neo4j_query(cypher, params=None):
    """Execute a Cypher query against Neo4j HTTP API."""
    headers = {
        "Authorization": f"Basic {NEO4J_AUTH}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    body = {"statement": cypher}
    if params:
        body["parameters"] = params
    data = json.dumps(body).encode("utf-8")
    req = request.Request(NEO4J_HTTP_URL, data=data, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def pinecone_describe():
    """Get Pinecone index statistics."""
    url = f"{PINECONE_HOST}/describe_index_stats"
    headers = {
        "Api-Key": PINECONE_API_KEY,
        "Content-Type": "application/json"
    }
    req = request.Request(url, data=b"{}", headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def supabase_query(sql):
    """Execute SQL via psql."""
    try:
        result = subprocess.run(
            ["psql", SUPABASE_CONN, "-t", "-A", "-c", sql],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip()}
        return {"data": result.stdout.strip()}
    except FileNotFoundError:
        # psql not available, try raw HTTP
        return {"error": "psql not installed"}
    except Exception as e:
        return {"error": str(e)}


def check_dataset_file():
    """Verify the Phase 2 dataset file."""
    print("\n" + "=" * 70)
    print("1. PHASE 2 DATASET FILE VERIFICATION")
    print("=" * 70)

    filepath = os.path.join(REPO_ROOT, "datasets", "phase-2", "hf-1000.json")
    results = {
        "file_exists": False,
        "total_questions": 0,
        "graph_questions": 0,
        "quantitative_questions": 0,
        "datasets_found": {},
        "questions_with_context": 0,
        "questions_with_table_data": 0,
        "issues": []
    }

    if not os.path.exists(filepath):
        results["issues"].append("File not found: datasets/phase-2/hf-1000.json")
        print(f"  ERROR: File not found at {filepath}")
        return results

    results["file_exists"] = True
    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"  File found: {file_size_mb:.1f} MB")

    # Stream-parse the large JSON file
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        results["issues"].append(f"JSON parse error: {e}")
        print(f"  ERROR: Invalid JSON: {e}")
        return results

    metadata = data.get("metadata", {})
    questions = data.get("questions", [])
    results["total_questions"] = len(questions)
    print(f"  Total questions: {len(questions)}")
    print(f"  Metadata: {json.dumps(metadata, indent=2)[:500]}")

    # Analyze questions by dataset and type
    dataset_counts = {}
    rag_target_counts = {}
    context_count = 0
    table_count = 0
    missing_answer = 0
    missing_context_and_table = 0

    for q in questions:
        ds = q.get("dataset_name", "unknown")
        rag = q.get("rag_target", "unknown")
        dataset_counts[ds] = dataset_counts.get(ds, 0) + 1
        rag_target_counts[rag] = rag_target_counts.get(rag, 0) + 1

        if q.get("context"):
            context_count += 1
        if q.get("table_data"):
            table_count += 1
        if not q.get("expected_answer"):
            missing_answer += 1
        if not q.get("context") and not q.get("table_data"):
            missing_context_and_table += 1

    results["datasets_found"] = dataset_counts
    results["rag_target_counts"] = rag_target_counts
    results["questions_with_context"] = context_count
    results["questions_with_table_data"] = table_count
    results["graph_questions"] = rag_target_counts.get("graph", 0)
    results["quantitative_questions"] = rag_target_counts.get("quantitative", 0)

    print(f"\n  By dataset:")
    for ds, count in sorted(dataset_counts.items()):
        print(f"    {ds}: {count}")

    print(f"\n  By RAG target:")
    for rag, count in sorted(rag_target_counts.items()):
        print(f"    {rag}: {count}")

    print(f"\n  Questions with context (paragraphs): {context_count}")
    print(f"  Questions with table_data: {table_count}")
    print(f"  Questions missing expected_answer: {missing_answer}")
    print(f"  Questions with neither context nor table_data: {missing_context_and_table}")

    # Phase 2 expects: 500 graph (musique + 2wiki) + 500 quantitative (finqa + tatqa + convfinqa)
    expected_graph = 500
    expected_quant = 450  # finqa 200 + tatqa 150 + convfinqa 100 (wikitablequestions is Phase 3)
    actual_graph = rag_target_counts.get("graph", 0)
    actual_quant = rag_target_counts.get("quantitative", 0)

    if actual_graph < expected_graph:
        results["issues"].append(f"Graph questions: {actual_graph} < expected {expected_graph}")
    if actual_quant < expected_quant:
        results["issues"].append(f"Quantitative questions: {actual_quant} < expected {expected_quant}")
    if missing_answer > 0:
        results["issues"].append(f"{missing_answer} questions missing expected_answer")

    # Check specific dataset counts from Phase 2 plan
    expected_datasets = {
        "musique": 200,
        "2wikimultihopqa": 300,
        "finqa": 200,
        "tatqa": 150,
        "convfinqa": 100
    }
    for ds_name, expected_count in expected_datasets.items():
        actual = dataset_counts.get(ds_name, 0)
        status = "OK" if actual >= expected_count else f"LOW ({actual} < {expected_count})"
        print(f"  Phase 2 dataset '{ds_name}': {actual}/{expected_count} — {status}")
        if actual < expected_count:
            results["issues"].append(f"Dataset '{ds_name}': {actual} < expected {expected_count}")

    return results


def check_neo4j():
    """Check Neo4j readiness for Phase 2."""
    print("\n" + "=" * 70)
    print("2. NEO4J DATABASE VERIFICATION")
    print("=" * 70)

    results = {
        "connected": False,
        "total_nodes": 0,
        "total_relationships": 0,
        "node_labels": {},
        "relationship_types": {},
        "phase_2_ready": False,
        "phase_2_required_nodes": 2500,
        "phase_2_required_relationships": 3000,
        "issues": []
    }

    if not NEO4J_PASSWORD:
        results["issues"].append("NEO4J_PASSWORD not set")
        print("  ERROR: NEO4J_PASSWORD not set")
        return results

    # Count nodes
    resp = neo4j_query("MATCH (n) RETURN count(n) as cnt")
    if "error" in resp:
        results["issues"].append(f"Connection error: {resp['error']}")
        print(f"  ERROR: {resp['error']}")
        return results

    results["connected"] = True

    try:
        rows = resp.get("data", {}).get("values", [])
        if rows:
            results["total_nodes"] = rows[0][0]
    except (KeyError, IndexError, TypeError):
        # Try alternate response format
        try:
            results["total_nodes"] = resp["data"]["values"][0][0]
        except:
            pass
    print(f"  Total nodes: {results['total_nodes']}")

    # Count relationships
    resp = neo4j_query("MATCH ()-[r]->() RETURN count(r) as cnt")
    try:
        results["total_relationships"] = resp.get("data", {}).get("values", [[0]])[0][0]
    except:
        pass
    print(f"  Total relationships: {results['total_relationships']}")

    # Node labels breakdown
    resp = neo4j_query("MATCH (n) RETURN labels(n)[0] as label, count(*) as cnt ORDER BY cnt DESC")
    try:
        for row in resp.get("data", {}).get("values", []):
            label, cnt = row[0], row[1]
            results["node_labels"][label] = cnt
            print(f"    {label}: {cnt}")
    except:
        pass

    # Relationship types breakdown
    resp = neo4j_query("MATCH ()-[r]->() RETURN type(r) as rtype, count(*) as cnt ORDER BY cnt DESC")
    try:
        for row in resp.get("data", {}).get("values", []):
            rtype, cnt = row[0], row[1]
            results["relationship_types"][rtype] = cnt
            print(f"    {rtype}: {cnt}")
    except:
        pass

    # Check for Phase 2 specific entities (musique / 2wikimultihopqa entities)
    # Sample entities from the dataset: SpongeBob characters, Slovak districts, etc.
    phase2_sample_entities = [
        "Plankton", "SpongeBob", "Senica", "John Knox",
        "Presbyterian", "Spongebob Squarepants"
    ]
    print(f"\n  Checking Phase 2 sample entities:")
    found_entities = 0
    for entity in phase2_sample_entities:
        resp = neo4j_query(
            "MATCH (n) WHERE toLower(n.name) CONTAINS toLower($name) RETURN n.name as name LIMIT 3",
            {"name": entity}
        )
        try:
            matches = resp.get("data", {}).get("values", [])
            if matches:
                found_entities += 1
                print(f"    '{entity}': FOUND ({matches[0][0]})")
            else:
                print(f"    '{entity}': NOT FOUND")
        except:
            print(f"    '{entity}': QUERY ERROR")

    results["phase2_sample_entities_found"] = found_entities
    results["phase2_sample_entities_total"] = len(phase2_sample_entities)

    # Phase 2 readiness assessment
    nodes_ok = results["total_nodes"] >= results["phase_2_required_nodes"]
    rels_ok = results["total_relationships"] >= results["phase_2_required_relationships"]
    results["phase_2_ready"] = nodes_ok and rels_ok

    gap_nodes = max(0, results["phase_2_required_nodes"] - results["total_nodes"])
    gap_rels = max(0, results["phase_2_required_relationships"] - results["total_relationships"])

    print(f"\n  Phase 2 Neo4j readiness:")
    print(f"    Nodes: {results['total_nodes']}/{results['phase_2_required_nodes']} — {'OK' if nodes_ok else f'NEED {gap_nodes} more'}")
    print(f"    Relationships: {results['total_relationships']}/{results['phase_2_required_relationships']} — {'OK' if rels_ok else f'NEED {gap_rels} more'}")
    print(f"    Phase 2 entities present: {found_entities}/{len(phase2_sample_entities)}")
    print(f"    STATUS: {'READY' if results['phase_2_ready'] else 'NOT READY — ingestion required'}")

    if not nodes_ok:
        results["issues"].append(f"Nodes: {results['total_nodes']} < required {results['phase_2_required_nodes']} (need {gap_nodes} more)")
    if not rels_ok:
        results["issues"].append(f"Relationships: {results['total_relationships']} < required {results['phase_2_required_relationships']} (need {gap_rels} more)")

    return results


def check_supabase():
    """Check Supabase readiness for Phase 2."""
    print("\n" + "=" * 70)
    print("3. SUPABASE (POSTGRESQL) DATABASE VERIFICATION")
    print("=" * 70)

    results = {
        "connected": False,
        "tables": {},
        "total_rows": 0,
        "phase_1_tables": {},
        "phase_2_tables": {},
        "benchmark_datasets_table": {},
        "phase_2_ready": False,
        "phase_2_required_rows": 10000,
        "issues": []
    }

    if not SUPABASE_PASSWORD:
        results["issues"].append("SUPABASE_PASSWORD not set")
        print("  ERROR: SUPABASE_PASSWORD not set")
        return results

    # List all tables
    resp = supabase_query("""
        SELECT table_name, (
            SELECT count(*) FROM information_schema.columns c
            WHERE c.table_name = t.table_name AND c.table_schema = 'public'
        ) as col_count
        FROM information_schema.tables t
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)

    if "error" in resp:
        results["issues"].append(f"Connection error: {resp['error']}")
        print(f"  ERROR: {resp['error']}")
        return results

    results["connected"] = True
    print(f"  Connected to Supabase.")

    # Get row counts for each table
    resp = supabase_query("""
        SELECT schemaname, relname, n_live_tup
        FROM pg_stat_user_tables
        WHERE schemaname = 'public'
        ORDER BY relname;
    """)

    if "data" in resp and resp["data"]:
        total = 0
        for line in resp["data"].strip().split("\n"):
            parts = line.split("|")
            if len(parts) >= 3:
                table_name = parts[1].strip()
                try:
                    row_count = int(parts[2].strip())
                except ValueError:
                    row_count = 0
                results["tables"][table_name] = row_count
                total += row_count
                print(f"    {table_name}: {row_count} rows")
        results["total_rows"] = total
        print(f"  Total rows (approx): {total}")

    # Phase 1 core tables check
    phase1_tables = ["financials", "balance_sheet", "sales_data", "products", "employees"]
    print(f"\n  Phase 1 tables:")
    for table in phase1_tables:
        resp = supabase_query(f"SELECT count(*) FROM {table};")
        if "data" in resp:
            try:
                count = int(resp["data"].strip())
                results["phase_1_tables"][table] = count
                print(f"    {table}: {count} rows")
            except:
                results["phase_1_tables"][table] = "error"
                print(f"    {table}: parse error ({resp['data'][:50]})")
        else:
            results["phase_1_tables"][table] = "not_found"
            print(f"    {table}: NOT FOUND or error ({resp.get('error', '')[:100]})")

    # Phase 2 specific tables check (finqa_tables, tatqa_tables, convfinqa_tables)
    phase2_tables = ["finqa_tables", "tatqa_tables", "convfinqa_tables", "benchmark_datasets"]
    print(f"\n  Phase 2 tables:")
    for table in phase2_tables:
        resp = supabase_query(f"SELECT count(*) FROM {table};")
        if "data" in resp:
            try:
                count = int(resp["data"].strip())
                results["phase_2_tables"][table] = count
                print(f"    {table}: {count} rows")
            except:
                results["phase_2_tables"][table] = "error"
                print(f"    {table}: parse error ({resp['data'][:50]})")
        else:
            results["phase_2_tables"][table] = "not_found"
            print(f"    {table}: NOT FOUND ({resp.get('error', '')[:100]})")

    # Check benchmark_datasets for ingestion status
    resp = supabase_query("""
        SELECT dataset_name, count(*) as cnt
        FROM benchmark_datasets
        GROUP BY dataset_name
        ORDER BY dataset_name;
    """)
    if "data" in resp and resp["data"]:
        print(f"\n  benchmark_datasets breakdown:")
        for line in resp["data"].strip().split("\n"):
            parts = line.split("|")
            if len(parts) >= 2:
                ds_name = parts[0].strip()
                try:
                    count = int(parts[1].strip())
                except:
                    count = 0
                results["benchmark_datasets_table"][ds_name] = count
                print(f"    {ds_name}: {count} rows")
    else:
        print(f"  benchmark_datasets: empty or not found")

    # Check community_summaries
    resp = supabase_query("SELECT count(*) FROM community_summaries;")
    if "data" in resp:
        try:
            count = int(resp["data"].strip())
            results["community_summaries"] = count
            print(f"\n  community_summaries: {count} rows")
        except:
            pass

    # Phase 2 readiness assessment
    phase2_needed_tables = ["finqa_tables", "tatqa_tables", "convfinqa_tables"]
    tables_exist = all(
        isinstance(results["phase_2_tables"].get(t), int) and results["phase_2_tables"][t] > 0
        for t in phase2_needed_tables
    )
    rows_ok = results["total_rows"] >= results["phase_2_required_rows"]
    results["phase_2_ready"] = tables_exist and rows_ok

    print(f"\n  Phase 2 Supabase readiness:")
    print(f"    Total rows: {results['total_rows']}/{results['phase_2_required_rows']} — {'OK' if rows_ok else 'NOT ENOUGH'}")
    print(f"    Phase 2 tables exist: {'YES' if tables_exist else 'NO — ingestion required'}")
    for t in phase2_needed_tables:
        status = results["phase_2_tables"].get(t, "not_found")
        print(f"      {t}: {status}")
    print(f"    STATUS: {'READY' if results['phase_2_ready'] else 'NOT READY — ingestion required'}")

    if not tables_exist:
        for t in phase2_needed_tables:
            if not isinstance(results["phase_2_tables"].get(t), int) or results["phase_2_tables"][t] == 0:
                results["issues"].append(f"Table '{t}' missing or empty")
    if not rows_ok:
        results["issues"].append(f"Total rows {results['total_rows']} < required {results['phase_2_required_rows']}")

    return results


def check_pinecone():
    """Check Pinecone readiness for Phase 2."""
    print("\n" + "=" * 70)
    print("4. PINECONE VECTOR DATABASE VERIFICATION")
    print("=" * 70)

    results = {
        "connected": False,
        "total_vectors": 0,
        "namespaces": {},
        "dimension": 0,
        "phase_2_ready": True,  # Phase 2 doesn't require new Pinecone data
        "issues": []
    }

    if not PINECONE_API_KEY:
        results["issues"].append("PINECONE_API_KEY not set")
        print("  ERROR: PINECONE_API_KEY not set")
        return results

    stats = pinecone_describe()
    if "error" in stats:
        results["issues"].append(f"Connection error: {stats['error']}")
        print(f"  ERROR: {stats['error']}")
        return results

    results["connected"] = True
    results["total_vectors"] = stats.get("totalVectorCount", 0)
    results["dimension"] = stats.get("dimension", 0)

    print(f"  Connected to Pinecone.")
    print(f"  Total vectors: {results['total_vectors']}")
    print(f"  Dimension: {results['dimension']}")

    namespaces = stats.get("namespaces", {})
    print(f"  Namespaces ({len(namespaces)}):")
    for ns, info in sorted(namespaces.items()):
        count = info.get("vectorCount", 0)
        results["namespaces"][ns] = count
        print(f"    {ns}: {count} vectors")

    # Phase 2 does NOT require new Pinecone data (focuses on graph + quant)
    print(f"\n  Phase 2 Pinecone readiness:")
    print(f"    Phase 2 focuses on graph (Neo4j) and quantitative (Supabase) pipelines.")
    print(f"    No additional Pinecone ingestion required for Phase 2.")
    print(f"    STATUS: READY (no changes needed)")

    # But check Phase 1 namespaces are still healthy
    phase1_namespaces = ["benchmark-squad_v2", "benchmark-triviaqa", "benchmark-popqa"]
    for ns in phase1_namespaces:
        if ns not in namespaces:
            results["issues"].append(f"Phase 1 namespace '{ns}' missing")
            print(f"    WARNING: Phase 1 namespace '{ns}' missing!")

    return results


def check_phase1_status():
    """Check Phase 1 exit criteria based on docs/data.json."""
    print("\n" + "=" * 70)
    print("5. PHASE 1 EXIT CRITERIA CHECK")
    print("=" * 70)

    data_path = os.path.join(REPO_ROOT, "docs", "data.json")
    results = {
        "phase_1_gates_met": False,
        "pipeline_accuracy": {},
        "overall_accuracy": 0,
        "issues": []
    }

    try:
        with open(data_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        results["issues"].append(f"Cannot read data.json: {e}")
        print(f"  ERROR: Cannot read data.json: {e}")
        return results

    # Extract pipeline accuracy from data.json
    pipelines = data.get("pipelines", {})
    targets = {
        "standard": 85,
        "graph": 70,
        "quantitative": 85,
        "orchestrator": 70
    }

    all_met = True
    for pipeline, target in targets.items():
        pipeline_data = pipelines.get(pipeline, {})
        accuracy = pipeline_data.get("accuracy", 0)
        if isinstance(accuracy, dict):
            accuracy = accuracy.get("current", 0)
        results["pipeline_accuracy"][pipeline] = {
            "current": accuracy,
            "target": target,
            "met": accuracy >= target
        }
        gap = accuracy - target
        status = "MET" if accuracy >= target else f"NOT MET (gap: {gap:+.1f}pp)"
        print(f"  {pipeline}: {accuracy:.1f}% / {target}% — {status}")
        if accuracy < target:
            all_met = False
            results["issues"].append(f"{pipeline}: {accuracy:.1f}% < {target}%")

    # Overall
    overall = data.get("meta", {}).get("overall_accuracy", 0)
    if not overall:
        # Calculate from pipelines
        accuracies = [v["current"] for v in results["pipeline_accuracy"].values() if v["current"] > 0]
        overall = sum(accuracies) / len(accuracies) if accuracies else 0
    results["overall_accuracy"] = overall
    overall_met = overall >= 75
    print(f"  Overall: {overall:.1f}% / 75% — {'MET' if overall_met else f'NOT MET (gap: {overall-75:+.1f}pp)'}")
    if not overall_met:
        all_met = False
        results["issues"].append(f"Overall: {overall:.1f}% < 75%")

    results["phase_1_gates_met"] = all_met
    print(f"\n  Phase 1 gates: {'ALL MET' if all_met else 'NOT ALL MET'}")

    return results


def generate_report(dataset_results, neo4j_results, supabase_results, pinecone_results, phase1_results):
    """Generate the comprehensive verification report."""
    print("\n" + "=" * 70)
    print("PHASE 2 READINESS VERIFICATION REPORT")
    print(f"Generated: {datetime.now().isoformat()}")
    print("=" * 70)

    report = {
        "generated_at": datetime.now().isoformat(),
        "phase": 2,
        "summary": {},
        "dataset_file": dataset_results,
        "neo4j": neo4j_results,
        "supabase": supabase_results,
        "pinecone": pinecone_results,
        "phase_1_status": phase1_results,
        "all_issues": [],
        "recommendations": []
    }

    # Collect all issues
    for section in [dataset_results, neo4j_results, supabase_results, pinecone_results, phase1_results]:
        report["all_issues"].extend(section.get("issues", []))

    # Overall readiness
    dataset_ready = dataset_results["file_exists"] and len(dataset_results.get("issues", [])) == 0
    neo4j_ready = neo4j_results.get("phase_2_ready", False)
    supabase_ready = supabase_results.get("phase_2_ready", False)
    pinecone_ready = pinecone_results.get("phase_2_ready", True)
    phase1_met = phase1_results.get("phase_1_gates_met", False)

    report["summary"] = {
        "dataset_file_ready": dataset_ready,
        "neo4j_ready": neo4j_ready,
        "supabase_ready": supabase_ready,
        "pinecone_ready": pinecone_ready,
        "phase_1_gates_met": phase1_met,
        "overall_phase_2_ready": all([dataset_ready, neo4j_ready, supabase_ready, pinecone_ready, phase1_met]),
        "total_issues": len(report["all_issues"])
    }

    # Generate recommendations
    if not phase1_met:
        report["recommendations"].append({
            "priority": "P0",
            "action": "Continue Phase 1 iteration to meet all pipeline accuracy targets before starting Phase 2.",
            "details": phase1_results.get("issues", [])
        })

    if not neo4j_ready:
        report["recommendations"].append({
            "priority": "P1",
            "action": "Ingest musique and 2wikimultihopqa entities into Neo4j.",
            "details": [
                f"Current nodes: {neo4j_results.get('total_nodes', 0)} / Required: {neo4j_results.get('phase_2_required_nodes', 2500)}",
                f"Current relationships: {neo4j_results.get('total_relationships', 0)} / Required: {neo4j_results.get('phase_2_required_relationships', 3000)}",
                "Run entity extraction from question contexts and create Neo4j entities",
                "Options: extend populate-neo4j-entities.py, use WF-Benchmark-Dataset-Ingestion, or batch Cypher"
            ]
        })

    if not supabase_ready:
        missing_tables = [t for t in ["finqa_tables", "tatqa_tables", "convfinqa_tables"]
                         if not isinstance(supabase_results.get("phase_2_tables", {}).get(t), int)
                         or supabase_results["phase_2_tables"][t] == 0]
        report["recommendations"].append({
            "priority": "P1",
            "action": "Create and populate Phase 2 financial tables in Supabase.",
            "details": [
                f"Missing tables: {missing_tables}",
                f"Current total rows: {supabase_results.get('total_rows', 0)} / Required: {supabase_results.get('phase_2_required_rows', 10000)}",
                "Parse table_data from Phase 2 questions and create tables in Supabase",
                "Options: per-dataset tables, universal JSONB table, or WF-Benchmark-Dataset-Ingestion workflow"
            ]
        })

    if not dataset_ready:
        report["recommendations"].append({
            "priority": "P1",
            "action": "Fix Phase 2 dataset file issues.",
            "details": dataset_results.get("issues", [])
        })

    print(f"\n  SUMMARY:")
    print(f"    Dataset file ready: {'YES' if dataset_ready else 'NO'}")
    print(f"    Neo4j ready:        {'YES' if neo4j_ready else 'NO'}")
    print(f"    Supabase ready:     {'YES' if supabase_ready else 'NO'}")
    print(f"    Pinecone ready:     {'YES' if pinecone_ready else 'NO'}")
    print(f"    Phase 1 gates met:  {'YES' if phase1_met else 'NO'}")
    print(f"    Overall Phase 2:    {'READY' if report['summary']['overall_phase_2_ready'] else 'NOT READY'}")
    print(f"    Total issues:       {len(report['all_issues'])}")

    if report["recommendations"]:
        print(f"\n  RECOMMENDATIONS:")
        for rec in report["recommendations"]:
            print(f"    [{rec['priority']}] {rec['action']}")
            for detail in rec.get("details", []):
                print(f"         - {detail}")

    if report["all_issues"]:
        print(f"\n  ALL ISSUES:")
        for i, issue in enumerate(report["all_issues"], 1):
            print(f"    {i}. {issue}")

    return report


if __name__ == "__main__":
    print("=" * 70)
    print("PHASE 2 DATABASE READINESS VERIFICATION")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 70)

    # Run all checks
    dataset_results = check_dataset_file()
    neo4j_results = check_neo4j()
    supabase_results = check_supabase()
    pinecone_results = check_pinecone()
    phase1_results = check_phase1_status()

    # Generate comprehensive report
    report = generate_report(dataset_results, neo4j_results, supabase_results, pinecone_results, phase1_results)

    # Save report
    output_path = os.path.join(REPO_ROOT, "db", "readiness", "phase-2-verification.json")
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved: {output_path}")
