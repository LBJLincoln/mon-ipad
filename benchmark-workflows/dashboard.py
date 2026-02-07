#!/usr/bin/env python3
"""
RAG Benchmark Dashboard — Interactive HTML dashboard.

Generates a self-contained HTML file showing:
- Questions tested, scores, latency per RAG type
- Questions remaining (untested)
- Database coverage gaps
- Dataset relevance analysis
- Statistical confidence intervals

Usage:
  python dashboard.py [results_json]
  # Opens benchmark-dashboard.html in browser or serves on localhost
"""
import json
import os
import sys
import math
import hashlib
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_HTML = os.path.join(SCRIPT_DIR, "benchmark-dashboard.html")

# ============================================================
# Data loading
# ============================================================

def load_datasets():
    """Load all question datasets and return structured data."""
    datasets = {}
    files = {
        "50x2": os.path.join(SCRIPT_DIR, "benchmark-50x2-questions.json"),
        "std-orch": os.path.join(SCRIPT_DIR, "benchmark-standard-orchestrator-questions.json"),
        "1000q": os.path.join(SCRIPT_DIR, "rag-1000-test-questions.json"),
    }
    for label, path in files.items():
        if not os.path.exists(path):
            continue
        with open(path) as f:
            data = json.load(f)
        qs = data.get("questions", data) if isinstance(data, dict) else data
        datasets[label] = qs
    return datasets


def load_results():
    """Load evaluation results from all available result files."""
    results = []
    # Check for comprehensive eval results
    for fname in os.listdir(SCRIPT_DIR):
        if fname.endswith("-results.json") or fname == "comprehensive-rag-evaluation-results.json":
            path = os.path.join(SCRIPT_DIR, fname)
            try:
                with open(path) as f:
                    data = json.load(f)
                if isinstance(data, dict) and "results" in data:
                    for rag_type, type_results in data["results"].items():
                        if isinstance(type_results, list):
                            for r in type_results:
                                r["_source_file"] = fname
                                r["_rag_type"] = rag_type
                                results.append(r)
                        elif isinstance(type_results, dict) and "questions" in type_results:
                            for r in type_results["questions"]:
                                r["_source_file"] = fname
                                r["_rag_type"] = rag_type
                                results.append(r)
            except Exception:
                pass
    return results


def compute_question_index(datasets):
    """Build a master index of all questions with dedup detection."""
    index = []
    seen_hashes = {}
    duplicate_ids = set()

    for ds_label, qs in datasets.items():
        for q in qs:
            qtext = q.get("question", q.get("query", "")).strip()
            qhash = hashlib.md5(qtext.lower().encode()).hexdigest()
            qid = q.get("id", q.get("question_id", f"{ds_label}-{q.get('item_index', '?')}"))
            rag_target = q.get("rag_target", q.get("category", "unknown"))
            dataset_name = q.get("dataset_name", ds_label)

            is_dup = qhash in seen_hashes
            if is_dup:
                duplicate_ids.add(qid)
                duplicate_ids.add(seen_hashes[qhash])

            entry = {
                "id": qid,
                "question": qtext[:200],
                "expected_answer": str(q.get("expected_answer", ""))[:200],
                "rag_target": rag_target,
                "dataset_name": dataset_name,
                "dataset_file": ds_label,
                "has_context": bool(q.get("context") and len(str(q.get("context", ""))) > 10),
                "has_table_data": bool(q.get("table_data") and len(str(q.get("table_data", ""))) > 10),
                "is_duplicate": is_dup,
                "hash": qhash,
            }
            index.append(entry)
            if not is_dup:
                seen_hashes[qhash] = qid

    return index, duplicate_ids


def compute_db_coverage():
    """Compute which datasets have corresponding DB data."""
    # Pinecone namespaces (from last audit)
    pinecone_datasets = [
        "asqa", "finqa", "frames", "hotpotqa", "msmarco",
        "narrativeqa", "natural_questions", "popqa", "pubmedqa",
        "squad_v2", "triviaqa"
    ]
    pinecone_vectors = {
        "asqa": 948, "finqa": 500, "frames": 824, "hotpotqa": 1000,
        "msmarco": 1000, "narrativeqa": 1000, "natural_questions": 1000,
        "popqa": 1000, "pubmedqa": 500, "squad_v2": 1000, "triviaqa": 1000,
        "(default)": 639,
    }

    # Neo4j (from audit)
    neo4j = {
        "total_nodes": 145,
        "total_relationships": 98,
        "labels": {"Person": 41, "Organization": 21, "Technology": 19,
                   "City": 16, "Concept": 12, "Disease": 6, "Museum": 6},
        "curated_only": True,
        "covers_datasets": [],  # No HF multi-hop data in Neo4j
    }

    # Supabase (from SQL migration)
    supabase = {
        "financials": 24, "balance_sheet": 12, "sales_data": 16,
        "products": 18, "employees": 9, "community_summaries": 9,
        "total_rows": 88,
        "companies": ["TechVision Inc", "GreenEnergy Corp", "HealthPlus Labs"],
        "covers_datasets": [],  # Only custom financial data, no HF financial data
    }

    # Which RAG pipeline uses which DB
    pipeline_db_map = {
        "standard": {"primary": "Pinecone", "datasets_in_db": pinecone_datasets},
        "graph": {"primary": "Neo4j", "datasets_in_db": []},
        "quantitative": {"primary": "Supabase SQL", "datasets_in_db": []},
        "orchestrator": {"primary": "Routes to above", "datasets_in_db": pinecone_datasets},
    }

    return {
        "pinecone": {"datasets": pinecone_datasets, "vectors": pinecone_vectors,
                     "total": sum(pinecone_vectors.values())},
        "neo4j": neo4j,
        "supabase": supabase,
        "pipeline_db_map": pipeline_db_map,
    }


def compute_stats(question_index, results, db_coverage):
    """Compute comprehensive statistics."""
    # Tested questions (from results)
    tested_ids = set()
    tested_results = {}
    for r in results:
        qid = r.get("id", r.get("question_id", ""))
        if qid:
            tested_ids.add(qid)
            tested_results[qid] = r

    # Per-RAG-type stats
    rag_stats = {}
    for entry in question_index:
        rt = entry["rag_target"]
        if rt not in rag_stats:
            rag_stats[rt] = {
                "total": 0, "tested": 0, "remaining": 0,
                "correct": 0, "errors": 0, "duplicates": 0,
                "has_db_data": 0, "no_db_data": 0,
                "latencies": [], "f1_scores": [],
                "by_dataset": {},
            }
        s = rag_stats[rt]
        s["total"] += 1
        if entry["is_duplicate"]:
            s["duplicates"] += 1

        ds_name = entry["dataset_name"]
        if ds_name not in s["by_dataset"]:
            s["by_dataset"][ds_name] = {"total": 0, "in_db": False}
        s["by_dataset"][ds_name]["total"] += 1

        # Check if this question's data is in the DB
        pipeline_map = db_coverage["pipeline_db_map"].get(rt, {})
        datasets_in_db = pipeline_map.get("datasets_in_db", [])
        custom_200q = entry["dataset_file"] in ("50x2", "std-orch")

        if custom_200q or ds_name in datasets_in_db:
            s["has_db_data"] += 1
            s["by_dataset"][ds_name]["in_db"] = True
        else:
            s["no_db_data"] += 1

        # Check if tested
        if entry["id"] in tested_ids:
            s["tested"] += 1
            r = tested_results.get(entry["id"], {})
            if r.get("correct") or r.get("match_type") not in (None, "NO_ANSWER", "PARTIAL"):
                s["correct"] += 1
            if r.get("error"):
                s["errors"] += 1
            if r.get("latency_ms"):
                s["latencies"].append(r["latency_ms"])
            if r.get("f1") is not None:
                s["f1_scores"].append(r["f1"])
        else:
            s["remaining"] += 1

    return rag_stats


def wilson_ci(p, n, z=1.96):
    """Wilson score confidence interval for proportion p with n samples."""
    if n == 0:
        return (0, 0)
    denom = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denom
    spread = z * math.sqrt((p*(1-p) + z**2/(4*n)) / n) / denom
    return (max(0, center - spread), min(1, center + spread))


# ============================================================
# HTML generation
# ============================================================

def generate_html(question_index, results, db_coverage, rag_stats):
    """Generate a self-contained HTML dashboard."""

    # Pre-compute data for charts
    total_questions = len(question_index)
    total_unique = total_questions - sum(s["duplicates"] for s in rag_stats.values())
    total_tested = sum(s["tested"] for s in rag_stats.values())
    total_testable = sum(s["has_db_data"] for s in rag_stats.values())
    total_not_testable = sum(s["no_db_data"] for s in rag_stats.values())

    # Per-type summary rows
    type_rows = []
    for rt in ["standard", "graph", "quantitative", "orchestrator"]:
        s = rag_stats.get(rt, {})
        total = s.get("total", 0)
        tested = s.get("tested", 0)
        correct = s.get("correct", 0)
        remaining = s.get("remaining", 0)
        errors = s.get("errors", 0)
        has_db = s.get("has_db_data", 0)
        no_db = s.get("no_db_data", 0)
        dups = s.get("duplicates", 0)
        accuracy = f"{correct/tested*100:.1f}%" if tested > 0 else "—"
        latencies = s.get("latencies", [])
        avg_lat = f"{sum(latencies)/len(latencies)/1000:.1f}s" if latencies else "—"
        p95_lat = f"{sorted(latencies)[int(len(latencies)*0.95)]/1000:.1f}s" if len(latencies) > 2 else "—"

        # Confidence interval
        if tested > 0:
            lo, hi = wilson_ci(correct/tested, tested)
            ci = f"{lo*100:.1f}%–{hi*100:.1f}%"
        else:
            ci = "—"

        type_rows.append({
            "type": rt, "total": total, "tested": tested, "correct": correct,
            "remaining": remaining, "errors": errors, "has_db": has_db,
            "no_db": no_db, "dups": dups, "accuracy": accuracy,
            "avg_latency": avg_lat, "p95_latency": p95_lat, "ci_95": ci,
        })

    # Dataset coverage table
    ds_rows = []
    all_ds = set()
    for rt, s in rag_stats.items():
        for ds_name, info in s.get("by_dataset", {}).items():
            if ds_name not in all_ds:
                all_ds.add(ds_name)
                pinecone_count = db_coverage["pinecone"]["vectors"].get(f"benchmark-{ds_name}", 0) if ds_name not in ("50x2", "std-orch") else 0
                ds_rows.append({
                    "dataset": ds_name, "rag_target": rt,
                    "questions": info["total"], "in_db": info["in_db"],
                    "pinecone_vectors": pinecone_count,
                    "db": db_coverage["pipeline_db_map"].get(rt, {}).get("primary", "?"),
                })

    # Question detail table (for JSON export)
    q_details = json.dumps(question_index[:50], ensure_ascii=False)  # First 50 for preview

    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RAG Benchmark Dashboard</title>
<style>
:root {{
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #e6edf3; --text2: #8b949e; --accent: #58a6ff;
    --green: #3fb950; --red: #f85149; --yellow: #d29922; --orange: #db6d28;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; padding:20px; }}
h1 {{ font-size:1.8em; margin-bottom:4px; }}
h2 {{ font-size:1.3em; margin:24px 0 12px; color:var(--accent); border-bottom:1px solid var(--border); padding-bottom:6px; }}
h3 {{ font-size:1.1em; margin:16px 0 8px; color:var(--text2); }}
.subtitle {{ color:var(--text2); font-size:0.9em; margin-bottom:20px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; margin:16px 0; }}
.card {{ background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:16px; }}
.card .label {{ color:var(--text2); font-size:0.8em; text-transform:uppercase; letter-spacing:0.5px; }}
.card .value {{ font-size:2em; font-weight:700; margin:4px 0; }}
.card .sub {{ color:var(--text2); font-size:0.85em; }}
.green {{ color:var(--green); }}
.red {{ color:var(--red); }}
.yellow {{ color:var(--yellow); }}
.orange {{ color:var(--orange); }}
.accent {{ color:var(--accent); }}
table {{ width:100%; border-collapse:collapse; margin:12px 0; font-size:0.9em; }}
th {{ background:var(--surface); color:var(--text2); text-align:left; padding:8px 12px; border-bottom:2px solid var(--border); font-weight:600; }}
td {{ padding:8px 12px; border-bottom:1px solid var(--border); }}
tr:hover {{ background:rgba(88,166,255,0.05); }}
.bar {{ height:20px; border-radius:4px; display:flex; overflow:hidden; background:var(--border); }}
.bar-fill {{ height:100%; transition:width 0.3s; }}
.tag {{ display:inline-block; padding:2px 8px; border-radius:12px; font-size:0.75em; font-weight:600; }}
.tag-ok {{ background:rgba(63,185,80,0.15); color:var(--green); }}
.tag-warn {{ background:rgba(210,153,34,0.15); color:var(--yellow); }}
.tag-err {{ background:rgba(248,81,73,0.15); color:var(--red); }}
.tag-info {{ background:rgba(88,166,255,0.15); color:var(--accent); }}
.alert {{ background:rgba(248,81,73,0.1); border:1px solid rgba(248,81,73,0.3); border-radius:8px; padding:16px; margin:16px 0; }}
.alert-warn {{ background:rgba(210,153,34,0.1); border-color:rgba(210,153,34,0.3); }}
.alert h3 {{ color:var(--red); margin:0 0 8px; }}
.alert-warn h3 {{ color:var(--yellow); }}
.section {{ margin:24px 0; }}
.flex {{ display:flex; gap:16px; flex-wrap:wrap; }}
.flex > * {{ flex:1; min-width:300px; }}
.filter-bar {{ background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:12px; margin:12px 0; display:flex; gap:8px; flex-wrap:wrap; }}
.filter-bar select, .filter-bar input {{ background:var(--bg); color:var(--text); border:1px solid var(--border); border-radius:4px; padding:6px 10px; }}
.mono {{ font-family:'SF Mono',Monaco,Consolas,monospace; font-size:0.85em; }}
#question-table {{ max-height:500px; overflow-y:auto; }}
</style>
</head>
<body>

<h1>RAG Benchmark Dashboard</h1>
<p class="subtitle">Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} | Multi-RAG Orchestrator — SOTA 2026</p>

<!-- CRITICAL ALERTS -->
<div class="alert">
<h3>ALERTE CRITIQUE : 800/1200 questions ne sont pas testables</h3>
<p>Le fichier <code>rag-1000-test-questions.json</code> contient 1000 questions issues de HuggingFace (musique, 2wikimultihopqa, finqa, tatqa, convfinqa, wikitablequestions) mais <strong>800 d'entre elles n'ont aucune donnee correspondante dans les BDD</strong>.</p>
<ul style="margin:8px 0 0 20px;color:var(--text2)">
<li><strong>Graph RAG</strong> : 500q multi-hop (musique/2wiki) → Neo4j n'a que 145 noeuds curates, pas les entites HuggingFace</li>
<li><strong>Quantitative</strong> : 300q (tatqa/convfinqa/wikitablequestions) → Supabase n'a que 88 rows pour 3 entreprises fictives</li>
<li><strong>Seules 200q finqa</strong> ont un namespace Pinecone, mais le pipeline Quantitative utilise SQL, pas Pinecone</li>
</ul>
</div>

<div class="alert alert-warn">
<h3>9 questions dupliquees detectees</h3>
<p>Les datasets 50x2 et std-orch partagent 9 questions identiques (ex: "Who discovered penicillin?", "What is machine learning?"). Les scripts actuels les testent 2 fois.</p>
</div>

<!-- KPI CARDS -->
<h2>Vue d'ensemble</h2>
<div class="grid">
<div class="card">
  <div class="label">Questions Totales</div>
  <div class="value">{total_questions:,}</div>
  <div class="sub">{total_unique:,} uniques (9 doublons)</div>
</div>
<div class="card">
  <div class="label">Deja Testees</div>
  <div class="value green">{total_tested}</div>
  <div class="sub">via run-comprehensive-eval.py</div>
</div>
<div class="card">
  <div class="label">Testables (data en BDD)</div>
  <div class="value yellow">{total_testable}</div>
  <div class="sub">{total_testable - total_tested} restantes testables</div>
</div>
<div class="card">
  <div class="label">NON Testables (pas de data)</div>
  <div class="value red">{total_not_testable}</div>
  <div class="sub">Necessite ingestion HuggingFace</div>
</div>
</div>

<!-- PER-TYPE TABLE -->
<h2>Resultats par pipeline RAG</h2>
<table>
<tr>
  <th>Pipeline</th><th>Total Q</th><th>Testees</th><th>Correctes</th>
  <th>Accuracy</th><th>IC 95%</th><th>Erreurs</th>
  <th>Latence Avg</th><th>P95</th><th>Restantes</th><th>Sans data BDD</th>
</tr>"""

    for r in type_rows:
        acc_class = "green" if r["accuracy"] not in ("—",) and float(r["accuracy"].rstrip("%")) >= 70 else "yellow" if r["accuracy"] not in ("—",) and float(r["accuracy"].rstrip("%")) >= 50 else "red"
        html += f"""
<tr>
  <td><strong>{r['type'].upper()}</strong></td>
  <td>{r['total']}</td>
  <td>{r['tested']}</td>
  <td>{r['correct']}</td>
  <td class="{acc_class}"><strong>{r['accuracy']}</strong></td>
  <td class="mono">{r['ci_95']}</td>
  <td class="{'red' if r['errors'] > 0 else ''}">{r['errors']}</td>
  <td>{r['avg_latency']}</td>
  <td>{r['p95_latency']}</td>
  <td class="yellow">{r['remaining']}</td>
  <td class="{'red' if r['no_db'] > 0 else 'green'}">{r['no_db']}</td>
</tr>"""

    html += """
</table>

<!-- DATASET COVERAGE -->
<h2>Couverture BDD par dataset</h2>
<div class="flex">
<div>
<h3>Pinecone (Vectors)</h3>
<table>
<tr><th>Namespace</th><th>Vectors</th><th>Status</th></tr>"""

    for ns, cnt in sorted(db_coverage["pinecone"]["vectors"].items()):
        status = '<span class="tag tag-ok">OK</span>' if cnt > 0 else '<span class="tag tag-err">VIDE</span>'
        html += f"<tr><td class='mono'>{ns}</td><td>{cnt:,}</td><td>{status}</td></tr>"

    html += f"""
<tr style="font-weight:700"><td>TOTAL</td><td>{db_coverage['pinecone']['total']:,}</td><td></td></tr>
</table>
</div>
<div>
<h3>Neo4j (Graph)</h3>
<table>
<tr><th>Label</th><th>Nodes</th></tr>"""

    for label, cnt in sorted(db_coverage["neo4j"]["labels"].items(), key=lambda x: -x[1]):
        html += f"<tr><td>{label}</td><td>{cnt}</td></tr>"

    html += f"""
<tr style="font-weight:700"><td>TOTAL</td><td>{db_coverage['neo4j']['total_nodes']}</td></tr>
<tr><td>Relations</td><td>{db_coverage['neo4j']['total_relationships']}</td></tr>
</table>
<p style="color:var(--text2);font-size:0.85em;margin-top:8px">
  Graphe curate seulement. Aucune donnee HuggingFace (musique, 2wiki) ingéree.
  Les 500 questions graph du dataset 1000q ne sont PAS testables.
</p>
</div>
<div>
<h3>Supabase (SQL)</h3>
<table>
<tr><th>Table</th><th>Rows</th></tr>
<tr><td>financials</td><td>24</td></tr>
<tr><td>balance_sheet</td><td>12</td></tr>
<tr><td>sales_data</td><td>16</td></tr>
<tr><td>products</td><td>18</td></tr>
<tr><td>employees</td><td>9</td></tr>
<tr><td>community_summaries</td><td>9</td></tr>
<tr style="font-weight:700"><td>TOTAL</td><td>88</td></tr>
</table>
<p style="color:var(--text2);font-size:0.85em;margin-top:8px">
  3 entreprises fictives: TechVision, GreenEnergy, HealthPlus.<br>
  Aucune donnee finqa/tatqa/convfinqa/wikitablequestions.
</p>
</div>
</div>

<!-- DATASET x PIPELINE MATRIX -->
<h2>Matrice Dataset ↔ Pipeline ↔ BDD</h2>
<table>
<tr><th>Dataset</th><th>Pipeline cible</th><th>Questions</th><th>BDD utilisee</th><th>Data presente?</th><th>Testable?</th></tr>"""

    matrix = [
        ("custom-200q (50x2+std-orch)", "standard", 50, "Pinecone", True, True),
        ("custom-200q (50x2+std-orch)", "graph", 50, "Neo4j", True, True),
        ("custom-200q (50x2+std-orch)", "quantitative", 50, "Supabase SQL", True, True),
        ("custom-200q (50x2+std-orch)", "orchestrator", 50, "Multi-RAG", True, True),
        ("musique (HuggingFace)", "graph", 200, "Neo4j", False, False),
        ("2wikimultihopqa (HuggingFace)", "graph", 300, "Neo4j", False, False),
        ("finqa (HuggingFace)", "quantitative", 200, "Supabase SQL", False, False),
        ("tatqa (HuggingFace)", "quantitative", 150, "Supabase SQL", False, False),
        ("convfinqa (HuggingFace)", "quantitative", 100, "Supabase SQL", False, False),
        ("wikitablequestions (HuggingFace)", "quantitative", 50, "Supabase SQL", False, False),
    ]

    for ds, pipeline, count, db, has_data, testable in matrix:
        data_tag = '<span class="tag tag-ok">OUI</span>' if has_data else '<span class="tag tag-err">NON</span>'
        test_tag = '<span class="tag tag-ok">OUI</span>' if testable else '<span class="tag tag-err">NON</span>'
        html += f"<tr><td>{ds}</td><td>{pipeline}</td><td>{count}</td><td>{db}</td><td>{data_tag}</td><td>{test_tag}</td></tr>"

    html += """
</table>

<!-- STATISTICAL ANALYSIS -->
<h2>Analyse statistique : le sample est-il suffisant ?</h2>
<div class="card" style="max-width:800px">
<table>
<tr><th>Pipeline</th><th>n (tested)</th><th>Accuracy</th><th>IC 95%</th><th>Marge d'erreur</th><th>Suffisant?</th></tr>"""

    for r in type_rows:
        if r["tested"] > 0:
            acc = r["correct"] / r["tested"]
            lo, hi = wilson_ci(acc, r["tested"])
            margin = (hi - lo) / 2 * 100
            sufficient = margin <= 7
            suf_tag = '<span class="tag tag-ok">OUI</span>' if sufficient else '<span class="tag tag-warn">LIMITE</span>'
            html += f"""<tr>
  <td><strong>{r['type'].upper()}</strong></td>
  <td>{r['tested']}</td>
  <td>{r['accuracy']}</td>
  <td class="mono">{lo*100:.1f}%–{hi*100:.1f}%</td>
  <td class="mono">±{margin:.1f}%</td>
  <td>{suf_tag}</td>
</tr>"""

    html += """
</table>
<p style="color:var(--text2);font-size:0.85em;margin-top:12px">
<strong>Regle empirique :</strong> Pour detecter une amelioration de 5 points (ex: 78% → 83%),
il faut <strong>~250 questions par pipeline</strong> (puissance 80%, alpha 5%).<br>
Avec 50 questions par type, la marge d'erreur est de ±12-14%, ce qui masque les ameliorations de &lt;10 points.<br>
<strong>Recommandation minimum :</strong> 200-300 questions par pipeline = 800-1200 questions testables au total.
</p>
</div>

<!-- PERTINENCE ANALYSIS -->
<h2>Pertinence des datasets actuels</h2>
<div class="flex">
<div class="card">
<h3 style="color:var(--green)">Bien aligne</h3>
<ul style="margin:8px 0 0 16px;color:var(--text2)">
<li><strong>custom-200q</strong> : Crafté pour les 3 BDD existantes. Precision fiable.</li>
<li><strong>Quantitative custom</strong> : Questions alignées sur TechVision/GreenEnergy/HealthPlus → 80% accuracy</li>
<li><strong>Standard custom</strong> : Questions factuelles générales → 78% accuracy (Pinecone vectors OK)</li>
</ul>
</div>
<div class="card">
<h3 style="color:var(--red)">Non pertinent (actuellement)</h3>
<ul style="margin:8px 0 0 16px;color:var(--text2)">
<li><strong>musique/2wiki (500q graph)</strong> : Questions multi-hop complexes → Neo4j n'a PAS les entités correspondantes</li>
<li><strong>tatqa/convfinqa/wikitable (300q quant)</strong> : Données financières réelles → Supabase n'a PAS ces tables</li>
<li><strong>finqa (200q quant)</strong> : Dans Pinecone mais WF4 utilise SQL, pas vector search</li>
</ul>
</div>
<div class="card">
<h3 style="color:var(--yellow)">Pour la prochaine session</h3>
<ul style="margin:8px 0 0 16px;color:var(--text2)">
<li>Ingérer musique + 2wiki dans Neo4j (entités + relations extraites par LLM)</li>
<li>Ingérer tatqa/convfinqa tables dans Supabase (CREATE TABLE + INSERT)</li>
<li>Generer 200+ questions custom supplementaires pour chaque pipeline</li>
<li>Objectif: 300q testables par pipeline = 1200q total avec data en BDD</li>
</ul>
</div>
</div>

<!-- ROADMAP TO 10M+ -->
<h2>Roadmap vers 10M+ questions</h2>
<table>
<tr><th>Phase</th><th>Action</th><th>Questions</th><th>Prerequis</th></tr>
<tr><td><span class="tag tag-ok">FAIT</span></td><td>Custom 200q (session Feb 7)</td><td>200</td><td>—</td></tr>
<tr><td><span class="tag tag-warn">NEXT</span></td><td>Ingestion HF data + test 1000q</td><td>1,200</td><td>populate-all-databases.py + push-all-datasets.py</td></tr>
<tr><td><span class="tag tag-info">PHASE 2</span></td><td>Full HF samples (push-all-datasets.py config)</td><td>10,500</td><td>Ingestion 16 datasets (200-1000 samples chacun)</td></tr>
<tr><td><span class="tag tag-info">PHASE 3</span></td><td>Full HuggingFace datasets (max)</td><td>~2,375,000</td><td>Infra scaling (Pinecone Pro, Neo4j AuraDB Pro)</td></tr>
<tr><td><span class="tag tag-info">PHASE 4</span></td><td>Additional datasets (MMLU, BoolQ, RACE, QuAC, SearchQA, etc.)</td><td>10,000,000+</td><td>Dataset registry extension + multi-tenant scaling</td></tr>
</table>

<p style="color:var(--text2);margin-top:12px;font-size:0.9em">
<strong>Note :</strong> 10M+ questions nécessite un scaling significatif des BDD (Pinecone Pro tier, Neo4j AuraDB Enterprise, Supabase Pro)
et un pipeline d'ingestion industrialisé. Le sample actuel de 10,500 (Phase 2) est suffisant pour itérer et améliorer les pipelines avant le scaling.
</p>

<hr style="border:1px solid var(--border);margin:32px 0">
<p style="color:var(--text2);font-size:0.8em">
Dashboard genere par <code>benchmark-workflows/dashboard.py</code> |
Data: {total_questions:,} questions, {total_tested} testees |
BDD: Pinecone {db_coverage['pinecone']['total']:,} vecs, Neo4j {db_coverage['neo4j']['total_nodes']} nodes, Supabase 88 rows
</p>

</body>
</html>"""

    return html


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("RAG BENCHMARK DASHBOARD GENERATOR")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)

    # Load data
    print("\n  Loading datasets...")
    datasets = load_datasets()
    total_q = sum(len(qs) for qs in datasets.values())
    print(f"  Loaded {len(datasets)} dataset files ({total_q} questions)")

    print("\n  Loading results...")
    results = load_results()
    print(f"  Loaded {len(results)} result entries")

    print("\n  Building question index...")
    question_index, duplicate_ids = compute_question_index(datasets)
    print(f"  Indexed {len(question_index)} questions ({len(duplicate_ids)} duplicates)")

    print("\n  Computing DB coverage...")
    db_coverage = compute_db_coverage()
    print(f"  Pinecone: {db_coverage['pinecone']['total']:,} vectors in {len(db_coverage['pinecone']['datasets'])} namespaces")
    print(f"  Neo4j: {db_coverage['neo4j']['total_nodes']} nodes, {db_coverage['neo4j']['total_relationships']} relationships")
    print(f"  Supabase: {db_coverage['supabase']['total_rows']} rows across 6 tables")

    print("\n  Computing stats...")
    rag_stats = compute_stats(question_index, results, db_coverage)
    for rt, s in sorted(rag_stats.items()):
        testable = s["has_db_data"]
        not_testable = s["no_db_data"]
        print(f"  {rt.upper():15s} | total={s['total']:4d} | tested={s['tested']:3d} | testable={testable:4d} | NO_DATA={not_testable:4d}")

    print("\n  Generating HTML dashboard...")
    html = generate_html(question_index, results, db_coverage, rag_stats)

    with open(OUTPUT_HTML, "w") as f:
        f.write(html)
    print(f"\n  Dashboard saved to: {OUTPUT_HTML}")
    print(f"  Size: {os.path.getsize(OUTPUT_HTML):,} bytes")
    print("=" * 60)
