#!/usr/bin/env python3
"""
Deep Phase 2 Readiness Verification.

Connects directly to all 3 databases and checks:
1. Supabase: tables, row counts, Phase 2 table existence, benchmark_datasets
2. Neo4j: node/relationship counts, Phase 2 entity coverage
3. Phase 1 accuracy from data.json (correct parsing)
4. Dataset file completeness
"""
import json
import os
import sys
import base64
import time
from datetime import datetime
from urllib import request, error

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============================================================
# Connection details
# ============================================================
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


def neo4j_values(resp):
    """Extract values from Neo4j response."""
    try:
        return resp.get("data", {}).get("values", [])
    except:
        return []


def supabase_query_psycopg(sql):
    """Execute SQL via psycopg2."""
    import psycopg2
    conn_str = (
        f"host=aws-0-eu-west-1.pooler.supabase.com "
        f"port=6543 "
        f"dbname=postgres "
        f"user=postgres.ayqviqmxifzmhphiqfmj "
        f"password={os.environ.get('SUPABASE_PASSWORD', '')} "
        f"sslmode=require "
        f"connect_timeout=15"
    )
    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description] if cur.description else []
        cur.close()
        conn.close()
        return {"columns": colnames, "rows": rows}
    except Exception as e:
        # Try alternate host
        conn_str2 = conn_str.replace("aws-0-eu-west-1", "aws-1-eu-west-1")
        try:
            conn = psycopg2.connect(conn_str2)
            cur = conn.cursor()
            cur.execute(sql)
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description] if cur.description else []
            cur.close()
            conn.close()
            return {"columns": colnames, "rows": rows}
        except Exception as e2:
            return {"error": f"Primary: {e} | Alternate: {e2}"}


# ============================================================
# 1. SUPABASE CHECK
# ============================================================
def check_supabase():
    print("\n" + "=" * 70)
    print("1. SUPABASE (POSTGRESQL) — DEEP CHECK")
    print("=" * 70)

    results = {
        "connected": False,
        "tables": {},
        "phase_1_tables": {},
        "phase_2_tables": {},
        "benchmark_datasets": {},
        "community_summaries": 0,
        "total_rows": 0,
        "phase_2_ready": False,
        "issues": []
    }

    # List all public tables with row counts
    resp = supabase_query_psycopg("""
        SELECT relname, n_live_tup::int
        FROM pg_stat_user_tables
        WHERE schemaname = 'public'
        ORDER BY relname;
    """)

    if "error" in resp:
        results["issues"].append(f"Connection error: {resp['error']}")
        print(f"  ERROR: {resp['error']}")
        return results

    results["connected"] = True
    total = 0
    print(f"  All public tables:")
    for row in resp["rows"]:
        table_name, row_count = row[0], row[1]
        results["tables"][table_name] = row_count
        total += row_count
        print(f"    {table_name}: {row_count} rows")
    results["total_rows"] = total
    print(f"  Total rows (approx): {total}")

    # Phase 1 core tables - exact counts
    phase1_tables = ["financials", "balance_sheet", "sales_data", "products", "employees"]
    print(f"\n  Phase 1 core tables (exact counts):")
    for table in phase1_tables:
        resp = supabase_query_psycopg(f"SELECT count(*) FROM {table};")
        if "rows" in resp:
            count = resp["rows"][0][0]
            results["phase_1_tables"][table] = count
            print(f"    {table}: {count} rows")
        else:
            results["phase_1_tables"][table] = f"error: {resp.get('error', '')[:80]}"
            print(f"    {table}: ERROR ({resp.get('error', '')[:80]})")

    # Phase 2 specific tables
    phase2_tables = ["finqa_tables", "tatqa_tables", "convfinqa_tables", "benchmark_datasets"]
    print(f"\n  Phase 2 tables:")
    for table in phase2_tables:
        resp = supabase_query_psycopg(f"SELECT count(*) FROM {table};")
        if "rows" in resp:
            count = resp["rows"][0][0]
            results["phase_2_tables"][table] = count
            print(f"    {table}: {count} rows")
        else:
            results["phase_2_tables"][table] = "not_found"
            err_msg = resp.get("error", "")[:100]
            if "does not exist" in err_msg:
                print(f"    {table}: TABLE DOES NOT EXIST")
                results["issues"].append(f"Table '{table}' does not exist")
            else:
                print(f"    {table}: ERROR ({err_msg})")

    # benchmark_datasets breakdown by dataset_name
    resp = supabase_query_psycopg("""
        SELECT dataset_name, count(*) as cnt
        FROM benchmark_datasets
        GROUP BY dataset_name
        ORDER BY dataset_name;
    """)
    if "rows" in resp:
        print(f"\n  benchmark_datasets breakdown:")
        for row in resp["rows"]:
            ds_name, count = row[0], row[1]
            results["benchmark_datasets"][ds_name] = count
            print(f"    {ds_name}: {count} rows")
    else:
        print(f"  benchmark_datasets: {resp.get('error', 'not found')[:100]}")

    # Check community_summaries
    resp = supabase_query_psycopg("SELECT count(*) FROM community_summaries;")
    if "rows" in resp:
        results["community_summaries"] = resp["rows"][0][0]
        print(f"\n  community_summaries: {results['community_summaries']} rows")

    # Check what columns benchmark_datasets has
    resp = supabase_query_psycopg("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'benchmark_datasets' AND table_schema = 'public'
        ORDER BY ordinal_position;
    """)
    if "rows" in resp:
        print(f"\n  benchmark_datasets schema:")
        for row in resp["rows"]:
            print(f"    {row[0]}: {row[1]}")

    # Phase 2 readiness assessment
    needed = ["finqa_tables", "tatqa_tables", "convfinqa_tables"]
    tables_exist = all(
        isinstance(results["phase_2_tables"].get(t), int) and results["phase_2_tables"][t] > 0
        for t in needed
    )
    results["phase_2_ready"] = tables_exist

    print(f"\n  Phase 2 Supabase readiness:")
    print(f"    Phase 2 financial tables exist: {'YES' if tables_exist else 'NO — ingestion required'}")
    for t in needed:
        val = results["phase_2_tables"].get(t, "not_found")
        status = "OK" if isinstance(val, int) and val > 0 else "MISSING"
        print(f"      {t}: {val} — {status}")
    print(f"    STATUS: {'READY' if results['phase_2_ready'] else 'NOT READY'}")

    return results


# ============================================================
# 2. NEO4J DEEP CHECK
# ============================================================
def check_neo4j():
    print("\n" + "=" * 70)
    print("2. NEO4J — DEEP CHECK")
    print("=" * 70)

    results = {
        "connected": False,
        "total_nodes": 0,
        "total_relationships": 0,
        "node_labels": {},
        "relationship_types": {},
        "phase2_entity_coverage": {},
        "sample_entities_found": 0,
        "sample_entities_total": 0,
        "phase_2_ready": False,
        "issues": []
    }

    # Basic counts
    resp = neo4j_query("MATCH (n) RETURN count(n) as cnt")
    if "error" in resp:
        results["issues"].append(f"Connection error: {resp['error']}")
        print(f"  ERROR: {resp['error']}")
        return results

    results["connected"] = True
    vals = neo4j_values(resp)
    results["total_nodes"] = vals[0][0] if vals else 0
    print(f"  Total nodes: {results['total_nodes']}")

    resp = neo4j_query("MATCH ()-[r]->() RETURN count(r) as cnt")
    vals = neo4j_values(resp)
    results["total_relationships"] = vals[0][0] if vals else 0
    print(f"  Total relationships: {results['total_relationships']}")

    # Labels breakdown
    resp = neo4j_query("MATCH (n) RETURN labels(n)[0] as label, count(*) as cnt ORDER BY cnt DESC")
    vals = neo4j_values(resp)
    print(f"\n  Node labels:")
    for row in vals:
        label, cnt = row[0], row[1]
        results["node_labels"][label] = cnt
        print(f"    {label}: {cnt}")

    # Relationship types
    resp = neo4j_query("MATCH ()-[r]->() RETURN type(r) as rtype, count(*) as cnt ORDER BY cnt DESC")
    vals = neo4j_values(resp)
    print(f"\n  Relationship types:")
    for row in vals:
        rtype, cnt = row[0], row[1]
        results["relationship_types"][rtype] = cnt
        print(f"    {rtype}: {cnt}")

    # Check for entities that should have been ingested for Phase 2
    # These are entities referenced in the first 10 musique and 2wiki questions
    phase2_entities = [
        # From musique questions
        "SpongeBob", "Plankton", "Mr. Lawrence",
        "Senica", "Heinrich Gross",
        "John Knox", "Presbyterian",
        "Rutherford B. Hayes", "Spiegel",
        # From 2wikimultihopqa questions
        "Mao Zedong", "Napoleon", "Julius Caesar",
        "Aristotle", "Shakespeare", "Beethoven",
        # General entities that should be in any knowledge graph
        "Einstein", "Marie Curie", "Alan Turing",
        "Tesla", "Newton", "Darwin"
    ]

    print(f"\n  Phase 2 entity coverage check ({len(phase2_entities)} entities):")
    found = 0
    not_found = []
    for entity in phase2_entities:
        resp = neo4j_query(
            "MATCH (n) WHERE toLower(n.name) CONTAINS toLower($name) RETURN n.name as name, labels(n)[0] as label LIMIT 2",
            {"name": entity}
        )
        vals = neo4j_values(resp)
        if vals:
            found += 1
            print(f"    '{entity}': FOUND — {vals[0][0]} ({vals[0][1]})")
        else:
            not_found.append(entity)
            print(f"    '{entity}': NOT FOUND")

    results["sample_entities_found"] = found
    results["sample_entities_total"] = len(phase2_entities)
    results["entities_not_found"] = not_found

    # Check how many nodes were added recently (those from Entity label = Phase 2 ingestion)
    entity_nodes = results["node_labels"].get("Entity", 0)
    person_nodes = results["node_labels"].get("Person", 0)
    print(f"\n  Entity-labeled nodes: {entity_nodes} (likely from Phase 2 ingestion)")
    print(f"  Person-labeled nodes: {person_nodes}")

    # Try to get a sample of recently added Entity nodes
    resp = neo4j_query("MATCH (n:Entity) RETURN n.name LIMIT 20")
    vals = neo4j_values(resp)
    if vals:
        print(f"  Sample Entity nodes:")
        for row in vals:
            print(f"    - {row[0]}")

    # Phase 2 readiness
    nodes_ok = results["total_nodes"] >= 2500
    rels_ok = results["total_relationships"] >= 3000
    entity_coverage = found / len(phase2_entities) if phase2_entities else 0
    results["phase_2_ready"] = nodes_ok and rels_ok

    print(f"\n  Phase 2 Neo4j readiness:")
    print(f"    Nodes: {results['total_nodes']}/2500 — {'OK' if nodes_ok else 'NOT ENOUGH'}")
    print(f"    Relationships: {results['total_relationships']}/3000 — {'OK' if rels_ok else 'NOT ENOUGH'}")
    print(f"    Entity coverage: {found}/{len(phase2_entities)} ({entity_coverage:.0%})")
    print(f"    Entities NOT found: {not_found}")
    print(f"    STATUS: {'READY (quantity)' if results['phase_2_ready'] else 'NOT READY'}")
    if not_found:
        print(f"    NOTE: {len(not_found)} Phase 2 sample entities missing — quality verification needed")
        results["issues"].append(f"{len(not_found)}/{len(phase2_entities)} Phase 2 sample entities not found in Neo4j")

    return results


# ============================================================
# 3. PINECONE CHECK
# ============================================================
def check_pinecone():
    print("\n" + "=" * 70)
    print("3. PINECONE — NAMESPACE CHECK")
    print("=" * 70)

    results = {"connected": False, "total_vectors": 0, "namespaces": {}, "issues": []}
    url = f"{PINECONE_HOST}/describe_index_stats"
    headers = {"Api-Key": PINECONE_API_KEY, "Content-Type": "application/json"}
    req = request.Request(url, data=b"{}", headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=30) as resp:
            stats = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        results["issues"].append(f"Connection error: {e}")
        print(f"  ERROR: {e}")
        return results

    results["connected"] = True
    results["total_vectors"] = stats.get("totalVectorCount", 0)
    results["dimension"] = stats.get("dimension", 0)
    namespaces = stats.get("namespaces", {})
    print(f"  Total vectors: {results['total_vectors']}, Dimension: {results['dimension']}")
    print(f"  Namespaces ({len(namespaces)}):")
    for ns, info in sorted(namespaces.items()):
        count = info.get("vectorCount", 0)
        results["namespaces"][ns] = count
        print(f"    {ns}: {count}")

    print(f"\n  Phase 2: No additional Pinecone ingestion needed. STATUS: READY")
    return results


# ============================================================
# 4. PHASE 1 ACCURACY (from data.json)
# ============================================================
def check_phase1_accuracy():
    print("\n" + "=" * 70)
    print("4. PHASE 1 ACCURACY — from data.json pipeline trends")
    print("=" * 70)

    results = {"pipelines": {}, "overall": 0, "phase_1_gates_met": False, "issues": []}
    data_path = os.path.join(REPO_ROOT, "docs", "data.json")
    try:
        with open(data_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        results["issues"].append(f"Cannot read data.json: {e}")
        print(f"  ERROR: {e}")
        return results

    meta = data.get("meta", {})
    print(f"  Phase: {meta.get('phase', '?')}")
    print(f"  Total unique questions: {meta.get('total_unique_questions', '?')}")
    print(f"  Total iterations: {meta.get('total_iterations', '?')}")

    # Extract latest accuracy from pipeline trends
    targets = {"standard": 85, "graph": 70, "quantitative": 85, "orchestrator": 70}
    pipelines = data.get("pipelines", {})

    # Also compute from question_registry for most accurate picture
    question_registry = data.get("question_registry", {})

    # Method 1: From latest full eval (iter-002 or iter-003 which tested all 50)
    print(f"\n  Pipeline accuracy from latest trend entries:")
    weighted_sum = 0
    weighted_count = 0
    all_met = True

    for pipeline, target in targets.items():
        trend = pipelines.get(pipeline, {}).get("trend", [])
        if not trend:
            results["pipelines"][pipeline] = {"accuracy": 0, "target": target, "met": False}
            all_met = False
            continue

        # Use the latest entry with >= 25 tests as the reliable accuracy
        # If no such entry exists, use the one with most tests
        best_entry = None
        for entry in reversed(trend):
            tested = entry.get("tested", 0)
            if tested >= 25:
                best_entry = entry
                break
        if not best_entry:
            best_entry = max(trend, key=lambda x: x.get("tested", 0))

        accuracy = best_entry.get("accuracy_pct", 0)
        tested = best_entry.get("tested", 0)
        iter_label = best_entry.get("iteration_id", "?")
        met = accuracy >= target

        results["pipelines"][pipeline] = {
            "accuracy": accuracy,
            "target": target,
            "met": met,
            "tested": tested,
            "from_iteration": iter_label
        }

        gap = accuracy - target
        status = "MET" if met else f"NOT MET (gap: {gap:+.1f}pp)"
        print(f"    {pipeline}: {accuracy:.1f}% on {tested}q (target: {target}%) — {status}")
        print(f"      From iteration: {iter_label}")

        weighted_sum += accuracy * tested
        weighted_count += tested
        if not met:
            all_met = False
            results["issues"].append(f"{pipeline}: {accuracy:.1f}% < target {target}%")

    overall = weighted_sum / weighted_count if weighted_count else 0
    results["overall"] = round(overall, 1)
    overall_met = overall >= 75
    results["phase_1_gates_met"] = all_met and overall_met

    print(f"\n  Overall weighted accuracy: {overall:.1f}% (target: 75%) — {'MET' if overall_met else 'NOT MET'}")
    print(f"  All pipeline gates met: {all_met}")
    print(f"  Phase 1 gates: {'ALL MET' if results['phase_1_gates_met'] else 'NOT ALL MET'}")

    # Method 2: From question_registry (most accurate)
    if question_registry:
        print(f"\n  Cross-check from question_registry ({len(question_registry)} questions):")
        by_type = {}
        for qid, qdata in question_registry.items():
            rag_type = qdata.get("rag_type", "unknown")
            if rag_type not in by_type:
                by_type[rag_type] = {"total": 0, "correct": 0}
            by_type[rag_type]["total"] += 1
            # Check latest result
            history = qdata.get("history", [])
            if history:
                latest = history[-1]
                if latest.get("correct"):
                    by_type[rag_type]["correct"] += 1

        for rag_type, counts in sorted(by_type.items()):
            acc = (counts["correct"] / counts["total"] * 100) if counts["total"] else 0
            print(f"    {rag_type}: {counts['correct']}/{counts['total']} ({acc:.1f}%)")

    return results


# ============================================================
# 5. DATASET FILE QUICK CHECK
# ============================================================
def check_dataset_file():
    print("\n" + "=" * 70)
    print("5. PHASE 2 DATASET FILE QUICK CHECK")
    print("=" * 70)

    filepath = os.path.join(REPO_ROOT, "datasets", "phase-2", "hf-1000.json")
    results = {"exists": False, "total": 0, "by_dataset": {}, "by_rag_target": {}, "issues": []}

    if not os.path.exists(filepath):
        results["issues"].append("File not found")
        print(f"  ERROR: File not found")
        return results

    results["exists"] = True
    with open(filepath, 'r') as f:
        data = json.load(f)

    questions = data.get("questions", [])
    results["total"] = len(questions)
    print(f"  Total questions: {len(questions)}")

    missing_answer = 0
    missing_context = 0
    for q in questions:
        ds = q.get("dataset_name", "unknown")
        rag = q.get("rag_target", "unknown")
        results["by_dataset"][ds] = results["by_dataset"].get(ds, 0) + 1
        results["by_rag_target"][rag] = results["by_rag_target"].get(rag, 0) + 1
        if not q.get("expected_answer"):
            missing_answer += 1
        if not q.get("context") and not q.get("table_data"):
            missing_context += 1

    print(f"  By dataset: {json.dumps(results['by_dataset'], indent=4)}")
    print(f"  By RAG target: {json.dumps(results['by_rag_target'], indent=4)}")
    print(f"  Missing expected_answer: {missing_answer}")
    print(f"  Missing both context and table_data: {missing_context}")

    if missing_answer:
        results["issues"].append(f"{missing_answer} questions missing expected_answer")
    if missing_context:
        results["issues"].append(f"{missing_context} questions with neither context nor table_data")

    return results


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 70)
    print("PHASE 2 DEEP READINESS VERIFICATION")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 70)

    supabase_results = check_supabase()
    neo4j_results = check_neo4j()
    pinecone_results = check_pinecone()
    phase1_results = check_phase1_accuracy()
    dataset_results = check_dataset_file()

    # ============================================================
    # FINAL REPORT
    # ============================================================
    print("\n" + "=" * 70)
    print("PHASE 2 READINESS — FINAL SUMMARY")
    print("=" * 70)

    all_issues = []
    for section in [supabase_results, neo4j_results, pinecone_results, phase1_results, dataset_results]:
        all_issues.extend(section.get("issues", []))

    report = {
        "generated_at": datetime.now().isoformat(),
        "phase": 2,
        "supabase": supabase_results,
        "neo4j": neo4j_results,
        "pinecone": pinecone_results,
        "phase_1_status": phase1_results,
        "dataset_file": dataset_results,
        "all_issues": all_issues,
        "summary": {
            "supabase_connected": supabase_results.get("connected", False),
            "neo4j_connected": neo4j_results.get("connected", False),
            "pinecone_connected": pinecone_results.get("connected", False),
            "neo4j_nodes": neo4j_results.get("total_nodes", 0),
            "neo4j_relationships": neo4j_results.get("total_relationships", 0),
            "neo4j_phase2_ready": neo4j_results.get("phase_2_ready", False),
            "supabase_phase2_ready": supabase_results.get("phase_2_ready", False),
            "pinecone_phase2_ready": True,
            "phase1_gates_met": phase1_results.get("phase_1_gates_met", False),
            "dataset_file_ok": dataset_results.get("exists", False) and len(dataset_results.get("issues", [])) == 0,
            "total_issues": len(all_issues),
            "overall_ready": False
        }
    }

    report["summary"]["overall_ready"] = all([
        report["summary"]["neo4j_phase2_ready"],
        report["summary"]["supabase_phase2_ready"],
        report["summary"]["pinecone_phase2_ready"],
        report["summary"]["phase1_gates_met"],
        report["summary"]["dataset_file_ok"]
    ])

    print(f"\n  Supabase connected: {report['summary']['supabase_connected']}")
    print(f"  Neo4j connected:    {report['summary']['neo4j_connected']}")
    print(f"  Pinecone connected: {report['summary']['pinecone_connected']}")
    print(f"  Neo4j Phase 2:      {report['summary']['neo4j_phase2_ready']} ({neo4j_results.get('total_nodes',0)} nodes, {neo4j_results.get('total_relationships',0)} rels)")
    print(f"  Supabase Phase 2:   {report['summary']['supabase_phase2_ready']}")
    print(f"  Pinecone Phase 2:   {report['summary']['pinecone_phase2_ready']}")
    print(f"  Phase 1 gates met:  {report['summary']['phase1_gates_met']}")
    print(f"  Dataset file OK:    {report['summary']['dataset_file_ok']}")
    print(f"  Total issues:       {len(all_issues)}")
    print(f"  OVERALL PHASE 2:    {'READY' if report['summary']['overall_ready'] else 'NOT READY'}")

    if all_issues:
        print(f"\n  Issues:")
        for i, issue in enumerate(all_issues, 1):
            print(f"    {i}. {issue}")

    # Save report
    output_path = os.path.join(REPO_ROOT, "db", "readiness", "phase-2-verification.json")
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved: {output_path}")
