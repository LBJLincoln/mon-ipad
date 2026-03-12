#!/usr/bin/env python3
"""
Dashboard Generator — Creates a live HTML dashboard for GitHub Pages.

Pulls real data from Supabase + Pinecone + pipeline health checks,
generates a self-contained HTML dashboard that can be served via GitHub Pages.

Usage:
  source .env.local
  python3 eval/dashboard-generator.py              # Generate dashboard
  python3 eval/dashboard-generator.py --push       # Generate + git push
"""

# ── IPv4 fix ──
import socket
from socket import AF_INET
_orig = socket.getaddrinfo
def _v4(*a, **kw):
    r = _orig(*a, **kw)
    return [x for x in r if x[0] == AF_INET] or r
socket.getaddrinfo = _v4

import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(REPO_ROOT, ".env.local")

if os.path.exists(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                if line.startswith("export "):
                    line = line[7:]
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and v:
                    os.environ.setdefault(k, v)

_ssl = ssl.create_default_context()
_ssl.check_hostname = False
_ssl.verify_mode = ssl.CERT_NONE

DB_URL = os.environ.get("DATABASE_URL", "")


def get_db_stats():
    """Get all stats from Supabase."""
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        stats = {}
        with conn.cursor() as c:
            c.execute("SET search_path TO public")

            c.execute("SELECT COUNT(*) FROM sector_documents")
            stats["total_docs"] = c.fetchone()[0]

            c.execute("SELECT sector, COUNT(*) FROM sector_documents GROUP BY sector ORDER BY sector")
            stats["docs_by_sector"] = {r[0]: r[1] for r in c.fetchall()}

            c.execute("SELECT COUNT(*) FROM eval_question_bank")
            stats["total_questions"] = c.fetchone()[0]

            c.execute("SELECT sector, COUNT(*) FROM eval_question_bank GROUP BY sector ORDER BY sector")
            stats["questions_by_sector"] = {r[0]: r[1] for r in c.fetchall()}

            c.execute("SELECT dataset_source, COUNT(*) FROM eval_question_bank GROUP BY dataset_source ORDER BY dataset_source")
            stats["questions_by_source"] = {r[0]: r[1] for r in c.fetchall()}

            c.execute("SELECT COUNT(*) FROM financials")
            stats["financials"] = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM eval_results")
            stats["total_eval_results"] = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM eval_runs")
            stats["total_eval_runs"] = c.fetchone()[0]

            # Recent accuracy by pipeline
            c.execute("""
                SELECT pipeline,
                       COUNT(*) as total,
                       SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) as passed,
                       ROUND(100.0 * SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as accuracy
                FROM eval_results
                WHERE created_at > now() - interval '24 hours'
                GROUP BY pipeline ORDER BY pipeline
            """)
            stats["accuracy_24h"] = {r[0]: {"total": r[1], "passed": r[2], "accuracy": float(r[3] or 0)}
                                      for r in c.fetchall()}

            # Accuracy by sector
            c.execute("""
                SELECT sector,
                       COUNT(*) as total,
                       SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) as passed,
                       ROUND(100.0 * SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as accuracy
                FROM eval_results
                WHERE created_at > now() - interval '24 hours'
                GROUP BY sector ORDER BY sector
            """)
            stats["accuracy_by_sector_24h"] = {r[0]: {"total": r[1], "passed": r[2], "accuracy": float(r[3] or 0)}
                                                for r in c.fetchall()}

            # Chronic failures
            c.execute("SELECT COUNT(*) FROM eval_question_bank WHERE consecutive_fails >= 3")
            stats["chronic_failures"] = c.fetchone()[0]

            # Score trends
            c.execute("""
                SELECT score_trend, COUNT(*)
                FROM eval_question_bank
                WHERE score_trend IS NOT NULL AND score_trend != ''
                GROUP BY score_trend
            """)
            stats["score_trends"] = {r[0]: r[1] for r in c.fetchall()}

        conn.close()
        return stats
    except Exception as e:
        return {"error": str(e)}


def check_spaces():
    """Check all HF Spaces health."""
    spaces = {
        "S1 (engine)": "https://lbjlincoln-nomos-rag-engine.hf.space",
        "S2 (engine-2)": "https://lbjlincoln26-nomos-rag-engine-2.hf.space",
        "S3 (engine-3)": "https://lbjlincoln-nomos-rag-engine-3.hf.space",
        "S4 (engine-4)": "https://lbjlincoln26-nomos-rag-engine-4.hf.space",
        "S5 (engine-5)": "https://lbjlincoln-nomos-rag-engine-5.hf.space",
        "S7 (LiteLLM)": "https://lbjlincoln-nomos-rag-engine-7.hf.space",
        "S9 (Ingest)": "https://lbjlincoln-nomos-rag-engine-9.hf.space",
        "Embeddings": "https://lbjlincoln-nomos-embeddings-api.hf.space",
        "S6 (Docling)": "https://lbjlincoln-nomos-docling-api.hf.space",
    }
    results = {}
    for name, url in spaces.items():
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, context=_ssl, timeout=8) as resp:
                results[name] = {"status": "UP", "code": resp.status}
        except Exception as e:
            results[name] = {"status": "DOWN", "error": str(e)[:60]}
    return results


def generate_html(stats, spaces):
    """Generate the dashboard HTML."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Build accuracy rows
    acc_rows = ""
    for pipeline, data in sorted(stats.get("accuracy_24h", {}).items()):
        color = "#22c55e" if data["accuracy"] >= 75 else "#eab308" if data["accuracy"] >= 50 else "#ef4444"
        acc_rows += f"""<tr>
            <td>{pipeline}</td>
            <td><span style="color:{color};font-weight:bold">{data['accuracy']}%</span></td>
            <td>{data['passed']}/{data['total']}</td>
        </tr>"""

    # Sector accuracy rows
    sector_rows = ""
    for sector, data in sorted(stats.get("accuracy_by_sector_24h", {}).items()):
        color = "#22c55e" if data["accuracy"] >= 75 else "#eab308" if data["accuracy"] >= 50 else "#ef4444"
        sector_rows += f"""<tr>
            <td>{sector}</td>
            <td><span style="color:{color};font-weight:bold">{data['accuracy']}%</span></td>
            <td>{data['passed']}/{data['total']}</td>
        </tr>"""

    # Space status
    space_rows = ""
    for name, info in sorted(spaces.items()):
        color = "#22c55e" if info["status"] == "UP" else "#ef4444"
        space_rows += f"""<tr>
            <td>{name}</td>
            <td><span style="color:{color};font-weight:bold">{info['status']}</span></td>
        </tr>"""

    # Questions by source
    q_source_rows = ""
    for source, count in sorted(stats.get("questions_by_source", {}).items()):
        q_source_rows += f"<tr><td>{source}</td><td>{count:,}</td></tr>"

    # Docs by sector
    docs_rows = ""
    for sector, count in sorted(stats.get("docs_by_sector", {}).items()):
        docs_rows += f"<tr><td>{sector}</td><td>{count:,}</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nomos Sector AI — Live Dashboard</title>
<style>
:root {{ --bg: #0f172a; --card: #1e293b; --border: #334155; --text: #e2e8f0; --dim: #94a3b8; --accent: #3b82f6; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Inter', -apple-system, system-ui, sans-serif; background: var(--bg); color: var(--text); padding: 1rem; }}
.header {{ text-align: center; padding: 1.5rem 0; border-bottom: 1px solid var(--border); margin-bottom: 1.5rem; }}
.header h1 {{ font-size: 1.8rem; font-weight: 700; }}
.header .ts {{ color: var(--dim); font-size: 0.85rem; margin-top: 0.3rem; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; }}
.card {{ background: var(--card); border: 1px solid var(--border); border-radius: 0.75rem; padding: 1.2rem; }}
.card h2 {{ font-size: 1rem; color: var(--accent); margin-bottom: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
.stat {{ display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid var(--border); }}
.stat:last-child {{ border-bottom: none; }}
.stat .label {{ color: var(--dim); }}
.stat .value {{ font-weight: 600; font-variant-numeric: tabular-nums; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
th {{ text-align: left; color: var(--dim); padding: 0.4rem 0.6rem; border-bottom: 1px solid var(--border); font-weight: 500; }}
td {{ padding: 0.4rem 0.6rem; border-bottom: 1px solid rgba(51,65,85,0.5); }}
.kpi {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.8rem; margin-bottom: 1.5rem; }}
.kpi-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 0.5rem; padding: 1rem; text-align: center; }}
.kpi-card .num {{ font-size: 1.6rem; font-weight: 700; color: var(--accent); }}
.kpi-card .lbl {{ color: var(--dim); font-size: 0.75rem; margin-top: 0.2rem; }}
.footer {{ text-align: center; color: var(--dim); font-size: 0.75rem; margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border); }}
</style>
</head>
<body>
<div class="header">
    <h1>Nomos Sector AI Expert</h1>
    <div class="ts">Last updated: {ts}</div>
</div>

<div class="kpi">
    <div class="kpi-card"><div class="num">{stats.get('total_docs', 0):,}</div><div class="lbl">Documents</div></div>
    <div class="kpi-card"><div class="num">{stats.get('total_questions', 0):,}</div><div class="lbl">Eval Questions</div></div>
    <div class="kpi-card"><div class="num">{stats.get('financials', 0)}</div><div class="lbl">Financial Tables</div></div>
    <div class="kpi-card"><div class="num">{stats.get('total_eval_results', 0):,}</div><div class="lbl">Eval Results</div></div>
    <div class="kpi-card"><div class="num">{stats.get('total_eval_runs', 0)}</div><div class="lbl">Eval Runs</div></div>
    <div class="kpi-card"><div class="num">{stats.get('chronic_failures', 0)}</div><div class="lbl">Chronic Failures</div></div>
</div>

<div class="grid">
    <div class="card">
        <h2>Pipeline Accuracy (24h)</h2>
        <table>
            <tr><th>Pipeline</th><th>Accuracy</th><th>Pass/Total</th></tr>
            {acc_rows if acc_rows else '<tr><td colspan="3" style="color:var(--dim)">No eval data in last 24h</td></tr>'}
        </table>
    </div>

    <div class="card">
        <h2>Sector Accuracy (24h)</h2>
        <table>
            <tr><th>Sector</th><th>Accuracy</th><th>Pass/Total</th></tr>
            {sector_rows if sector_rows else '<tr><td colspan="3" style="color:var(--dim)">No eval data in last 24h</td></tr>'}
        </table>
    </div>

    <div class="card">
        <h2>HF Spaces Status</h2>
        <table>
            <tr><th>Space</th><th>Status</th></tr>
            {space_rows}
        </table>
    </div>

    <div class="card">
        <h2>Documents by Sector</h2>
        <table>
            <tr><th>Sector</th><th>Count</th></tr>
            {docs_rows}
        </table>
    </div>

    <div class="card">
        <h2>Questions by Source</h2>
        <table>
            <tr><th>Source</th><th>Count</th></tr>
            {q_source_rows}
        </table>
    </div>

    <div class="card">
        <h2>Score Trends</h2>
        <table>
            <tr><th>Trend</th><th>Questions</th></tr>
            {''.join(f'<tr><td>{t}</td><td>{c:,}</td></tr>' for t, c in sorted(stats.get('score_trends', {}).items()))}
        </table>
    </div>
</div>

<div class="footer">
    Nomos Sector AI Expert System — Dashboard auto-generated by eval/dashboard-generator.py
</div>
</body>
</html>"""
    return html


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--push", action="store_true", help="Git push after generating")
    parser.add_argument("--output", default="", help="Output path (default: docs/dashboard.html)")
    args = parser.parse_args()

    print("Collecting stats from Supabase...")
    stats = get_db_stats()

    print("Checking HF Spaces...")
    spaces = check_spaces()

    output = args.output or os.path.join(REPO_ROOT, "docs", "dashboard.html")
    os.makedirs(os.path.dirname(output), exist_ok=True)

    print("Generating dashboard HTML...")
    html = generate_html(stats, spaces)
    with open(output, "w") as f:
        f.write(html)
    print(f"Dashboard saved: {output}")

    # Also save raw data as JSON
    data_file = os.path.join(os.path.dirname(output), "dashboard-data.json")
    with open(data_file, "w") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stats": {k: v for k, v in stats.items() if not isinstance(v, Exception)},
            "spaces": spaces,
        }, f, indent=2, default=str)
    print(f"Data saved: {data_file}")


if __name__ == "__main__":
    main()
