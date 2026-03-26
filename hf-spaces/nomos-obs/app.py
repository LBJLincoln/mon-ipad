#!/usr/bin/env python3
"""
Nomos42 Agent Observatory (S16) — Read-Only Dashboard
=======================================================
Gradio app that shows all agent activity, token usage, evolution health,
research feed, and island performance in a unified view.

Data sources (in priority order):
  1. Supabase pooler (DATABASE_URL env var)
  2. VM direct endpoint (http://34.136.180.66:8080/...)
  3. GitHub raw JSON fallback (https://raw.githubusercontent.com/LBJLincoln/mon-ipad/main/data/...)

READ-ONLY: never writes to Supabase or modifies any data.
"""

import os
import json
import time
import requests
import gradio as gr
from datetime import datetime, timezone, timedelta

# ── Constants ──────────────────────────────────────────────────────────────
VM_URL = "http://34.136.180.66:8080"
GITHUB_RAW = "https://raw.githubusercontent.com/LBJLincoln/mon-ipad/main/data"
SPACE_URLS = {
    "S10": "https://nomos42-nba-quant.hf.space",
    "S11": "https://nomos42-nba-quant-2.hf.space",
    "S12": "https://nomos42-nba-evo-3.hf.space",
    "S13": "https://nomos42-nba-evo-4.hf.space",
    "S14": "https://nomos42-nba-evo-5.hf.space",
    "S15": "https://nomos42-nba-evo-6.hf.space",
}
AGENT_NAMES = [
    "research-analyst",
    "market-analyst",
    "feature-engineer",
    "evolution-optimizer",
    "brain (brain-24-7)",
]

# ── Database connection ─────────────────────────────────────────────────────
_db_url = os.environ.get("DATABASE_URL", "")
_pg_pool = None


def _get_pg():
    """Lazy psycopg2 connection pool. Returns None if unavailable."""
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool
    db_url = os.environ.get("DATABASE_URL", "") or _db_url
    if not db_url:
        return None
    try:
        import psycopg2
        from psycopg2 import pool as pg_pool
        _pg_pool = pg_pool.SimpleConnectionPool(
            1, 3, db_url, options="-c search_path=public",
            connect_timeout=8,
        )
        conn = _pg_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        _pg_pool.putconn(conn)
        return _pg_pool
    except Exception as e:
        print(f"[OBS] DB connect failed: {e}")
        _pg_pool = None
        return None


def _query(sql, params=None):
    """Execute a SELECT query. Returns list of rows or None on failure."""
    pool = _get_pg()
    if not pool:
        return None
    conn = None
    try:
        conn = pool.getconn()
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    except Exception as e:
        print(f"[OBS] Query error: {e}")
        return None
    finally:
        if conn and pool:
            try:
                pool.putconn(conn)
            except Exception:
                pass


# ── HTTP helpers ────────────────────────────────────────────────────────────
def _fetch_json(url, timeout=8):
    """Fetch JSON from a URL. Returns parsed dict/list or None."""
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _fetch_health():
    """Try VM first, then GitHub raw fallback."""
    data = _fetch_json(f"{VM_URL}/health-status.json", timeout=6)
    if data:
        return data, "vm"
    data = _fetch_json(f"{GITHUB_RAW}/health-status.json", timeout=8)
    if data:
        return data, "github"
    return None, "unavailable"


def _fetch_space_status(space_key, base_url):
    """Fetch live /api/status from a single HF Space."""
    return _fetch_json(f"{base_url}/api/status", timeout=6)


# ── Tab 1: Agent Dashboard ──────────────────────────────────────────────────
def _agent_rows_from_db():
    """Pull agent_runs summary from Supabase if table exists."""
    rows = _query("""
        SELECT
            agent_name,
            COUNT(*) FILTER (WHERE ts > NOW() - INTERVAL '24h') AS runs_24h,
            COUNT(*) FILTER (WHERE ts > NOW() - INTERVAL '24h' AND status = 'success') AS success_24h,
            MAX(ts) AS last_active,
            SUM(tokens_used) FILTER (WHERE ts > NOW() - INTERVAL '24h') AS tokens_24h,
            SUM(cost_usd) FILTER (WHERE ts > NOW() - INTERVAL '24h') AS cost_24h
        FROM agent_runs
        GROUP BY agent_name
        ORDER BY MAX(ts) DESC NULLS LAST
    """)
    return rows


def build_agent_dashboard():
    """Build the agent dashboard table (Tab 1)."""
    rows = None
    source = "fallback"

    db_rows = _agent_rows_from_db()
    if db_rows is not None:
        rows = db_rows
        source = "supabase"

    if rows:
        table_data = []
        for r in rows:
            agent_name = r[0] or "unknown"
            runs_24h = r[1] or 0
            success_24h = r[2] or 0
            last_active = r[3].strftime("%Y-%m-%d %H:%M") if r[3] else "never"
            tokens_24h = int(r[4] or 0)
            cost_24h = f"${float(r[5] or 0):.4f}"
            success_rate = f"{100 * success_24h / runs_24h:.0f}%" if runs_24h > 0 else "N/A"
            status = "active" if runs_24h > 0 else "idle"
            table_data.append([
                agent_name, status, last_active,
                runs_24h, success_rate, tokens_24h, cost_24h
            ])
        md = f"*Source: {source} — updated {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}*\n\n"
        md += "| Agent | Status | Last Active | Runs (24h) | Success Rate | Tokens (24h) | Cost (24h) |\n"
        md += "|-------|--------|-------------|------------|--------------|--------------|------------|\n"
        for row in table_data:
            md += "| " + " | ".join(str(x) for x in row) + " |\n"
        return md

    # Fallback: static known agents with no live data
    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    md = f"*Source: static fallback — Supabase agent_runs table not available — {now_str}*\n\n"
    md += "| Agent | Role | Status |\n"
    md += "|-------|------|--------|\n"
    for name in AGENT_NAMES:
        role = {
            "research-analyst": "Research (arXiv, papers)",
            "market-analyst": "Odds & value bets",
            "feature-engineer": "Feature proposals",
            "evolution-optimizer": "GA tuning",
            "brain (brain-24-7)": "24/7 autonomous brain",
        }.get(name, "—")
        md += f"| {name} | {role} | idle (no data) |\n"
    md += "\n> To populate this tab: create `agent_runs` table in Supabase (Phase 2).\n"
    return md


# ── Tab 2: Activity Timeline ────────────────────────────────────────────────
def build_activity_timeline():
    """Recent agent runs as a markdown timeline (Tab 2)."""
    rows = _query("""
        SELECT ts, agent_name, skill, status, duration_s, output_summary
        FROM agent_runs
        WHERE ts > NOW() - INTERVAL '48h'
        ORDER BY ts DESC
        LIMIT 50
    """)

    if rows:
        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        md = f"*Activity in last 48h — {now_str}*\n\n"
        for r in rows:
            ts = r[0].strftime("%Y-%m-%d %H:%M") if r[0] else "?"
            agent = r[1] or "?"
            skill = r[2] or "?"
            status = r[3] or "?"
            dur = f"{float(r[4]):.0f}s" if r[4] else "?"
            summary = (r[5] or "")[:120]
            status_icon = "OK" if status == "success" else "FAIL" if status == "error" else "RUN"
            md += f"**[{ts}]** `{agent}` / `{skill}` [{status_icon}] {dur}\n"
            if summary:
                md += f"> {summary}\n"
            md += "\n"
        return md

    # Fallback: try GitHub raw for recent picks/results
    data = _fetch_json(f"{GITHUB_RAW}/nba-agent/latest-picks.json")
    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    if data:
        md = f"*No agent_runs table — showing latest picks instead — {now_str}*\n\n"
        picks = data if isinstance(data, list) else data.get("picks", [])
        for p in picks[:20]:
            game = p.get("game", "?")
            pick = p.get("pick", "?")
            prob = p.get("probability", 0)
            edge = p.get("edge", 0)
            md += f"- **{game}** | pick: {pick} | prob: {prob:.1%} | edge: {edge:+.1%}\n"
        return md

    return f"*No activity data available — {now_str}*\n\nDeploy Phase 2 (agent_runs table) to see live activity."


# ── Tab 3: Token & Cost Tracker ─────────────────────────────────────────────
def build_token_cost():
    """7-day token/cost summary per agent (Tab 3)."""
    rows = _query("""
        SELECT
            agent_name,
            SUM(tokens_used) AS tokens_7d,
            SUM(cost_usd) AS cost_7d,
            COUNT(*) AS runs_7d,
            MAX(budget_cap_usd) AS budget_cap
        FROM agent_runs
        WHERE ts > NOW() - INTERVAL '7d'
        GROUP BY agent_name
        ORDER BY SUM(cost_usd) DESC NULLS LAST
    """)

    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    if rows:
        total_tokens = sum(int(r[1] or 0) for r in rows)
        total_cost = sum(float(r[2] or 0) for r in rows)
        md = f"*7-day rolling — {now_str}*\n\n"
        md += f"**Total tokens**: {total_tokens:,} | **Total cost**: ${total_cost:.4f}\n\n"
        md += "| Agent | Tokens (7d) | Cost (7d) | Runs | Budget Cap | Utilization |\n"
        md += "|-------|-------------|-----------|------|------------|-------------|\n"
        for r in rows:
            agent = r[0] or "?"
            tokens = int(r[1] or 0)
            cost = float(r[2] or 0)
            runs = int(r[3] or 0)
            cap = float(r[4] or 0)
            util = f"{100 * cost / cap:.0f}%" if cap > 0 else "N/A"
            md += f"| {agent} | {tokens:,} | ${cost:.4f} | {runs} | ${cap:.2f} | {util} |\n"
        return md, _build_cost_bar_data(rows)

    md = f"*No token data — agent_runs table not available — {now_str}*\n\n"
    md += "Token tracking requires Phase 2 (agent_runs table with `tokens_used` and `cost_usd` columns).\n"
    return md, []


def _build_cost_bar_data(rows):
    """Build data for gr.BarPlot from DB rows."""
    data = []
    for r in rows:
        agent = r[0] or "unknown"
        cost = float(r[2] or 0)
        data.append({"agent": agent, "cost_usd": cost})
    return data


# ── Tab 4: Health Status ────────────────────────────────────────────────────
def build_health_status():
    """Fetch health-status.json and render all 6 island statuses (Tab 4)."""
    health, source = _fetch_health()
    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    if not health:
        return f"*Health data unavailable — {now_str}*\n\nCould not reach VM or GitHub raw."

    ts = health.get("timestamp", "?")
    md = f"*Source: {source} | Data ts: {ts} | Refreshed: {now_str}*\n\n"

    # Best overall
    best = health.get("best_overall", {})
    if best:
        brier = best.get("brier", "?")
        space = best.get("space", "?").upper()
        model = best.get("model_type", "?")
        feats = best.get("features", "?")
        roi = best.get("roi", 0)
        gap_target = best.get("gap_to_target_0_20", "?")
        all_time = best.get("all_time_record", "?")
        md += f"## Best Overall\n"
        md += f"| Metric | Value |\n|--------|-------|\n"
        md += f"| Brier | **{brier}** (target: < 0.20, gap: {gap_target}) |\n"
        md += f"| All-Time Record | {all_time} |\n"
        md += f"| Best Space | {space} ({model}, {feats} features, ROI={roi:.1%}) |\n\n"

    # Engine parity
    parity = health.get("engine_parity", {})
    parity_ok = parity.get("match", False)
    parity_icon = "OK" if parity_ok else "MISMATCH"
    sha = parity.get("sha_features_engine", "?")[:12]
    version = parity.get("version", "?")
    md += f"## Engine Parity\n"
    md += f"**Status**: [{parity_icon}] | SHA: `{sha}` | Version: `{version}`\n\n"
    if not parity_ok:
        md += "> **WARNING**: Engine files do not match — fix immediately!\n\n"

    # Island statuses
    spaces = health.get("spaces", {})
    md += "## Island Status\n\n"
    md += "| Space | Role | Status | Gen | Brier | Stagnation | Model | Mut | Features |\n"
    md += "|-------|------|--------|-----|-------|------------|-------|-----|----------|\n"

    for key in ["s10", "s11", "s12", "s13", "s14", "s15"]:
        s = spaces.get(key, {})
        if not s:
            md += f"| {key.upper()} | ? | no data | ? | ? | ? | ? | ? | ? |\n"
            continue
        status = s.get("status", "?")
        role = s.get("role", "?")
        gen = s.get("generation", "?")
        brier = s.get("best_brier", 1.0)
        stag = s.get("stagnation", "?")
        model = s.get("best_model_type", "?")
        mut = s.get("mutation_rate", 0)
        feats = s.get("best_features", "?")

        brier_str = f"**{brier:.4f}**" if isinstance(brier, float) and brier < 0.23 else (
            f"{brier:.4f}" if isinstance(brier, float) else str(brier)
        )
        status_short = status[:20]
        md += f"| {key.upper()} | {role} | {status_short} | {gen} | {brier_str} | {stag} | {model} | {mut:.3f} | {feats} |\n"

    # Recommendations
    recs = health.get("recommendations", [])
    if recs:
        md += "\n## Recommendations\n\n"
        for rec in recs:
            md += f"- {rec}\n"

    # Recent events
    delta = health.get("delta_from_last_cycle", {})
    events = delta.get("new_events", [])
    if events:
        md += "\n## Recent Events\n\n"
        for ev in events:
            md += f"- {ev}\n"

    return md


# ── Tab 5: Research Feed ────────────────────────────────────────────────────
def build_research_feed():
    """Latest research proposals (Tab 5)."""
    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    # Try Supabase research_proposals table
    rows = _query("""
        SELECT
            title,
            status,
            expected_impact,
            agent_source,
            created_at,
            notes
        FROM research_proposals
        ORDER BY created_at DESC
        LIMIT 30
    """)

    if rows:
        md = f"*Source: Supabase research_proposals — {now_str}*\n\n"
        for r in rows:
            title = r[0] or "Untitled"
            status = r[1] or "pending"
            impact = r[2] or "?"
            agent = r[3] or "?"
            ts = r[4].strftime("%Y-%m-%d") if r[4] else "?"
            notes = (r[5] or "")[:100]
            status_badge = {
                "implemented": "[DONE]",
                "rejected": "[SKIP]",
                "pending": "[PEND]",
                "testing": "[TEST]",
            }.get(status, f"[{status.upper()[:4]}]")
            md += f"### {status_badge} {title}\n"
            md += f"*{ts} | agent: {agent} | impact: {impact}*\n"
            if notes:
                md += f"> {notes}\n"
            md += "\n"
        return md

    # Fallback: GitHub raw crew-research.json or crew-features.json
    for fname in ["results/crew-features.json", "results/crew-research.json", "nba-agent/improve-results.json"]:
        data = _fetch_json(f"{GITHUB_RAW}/{fname}")
        if data:
            md = f"*Source: GitHub raw ({fname}) — {now_str}*\n\n"
            # crew-features format
            if "new_features" in data:
                features = data.get("new_features", [])
                md += f"**Feature Engine**: {data.get('current_features', '?')} current features\n\n"
                for feat in features:
                    name = feat.get("name", "?")
                    cat = feat.get("category", "?")
                    impact = feat.get("expected_impact", "?")
                    md += f"- **{name}** ({cat}) — {impact}\n"
                return md
            # generic JSON dump
            md += f"```json\n{json.dumps(data, indent=2, default=str)[:2000]}\n```\n"
            return md

    return (
        f"*No research data available — {now_str}*\n\n"
        "Research proposals are stored in Supabase `research_proposals` table or "
        "as JSON files in `data/results/`. Neither source was reachable."
    )


# ── Top-level refresh wrapper for Tab 3 (returns md + plot data) ────────────
def refresh_token_tab():
    md, bar_data = build_token_cost()
    return md, bar_data


# ── Build Gradio app ─────────────────────────────────────────────────────────
with gr.Blocks(
    title="Nomos42 Agent Observatory",
    theme=gr.themes.Monochrome(),
) as app:
    gr.Markdown("# Nomos42 Agent Observatory (S16)")
    gr.Markdown(
        "*Read-only dashboard — agent activity, token usage, evolution health, research feed.*  "
        "Auto-refreshes every 60 seconds."
    )

    with gr.Tabs():
        # ── Tab 1: Agent Dashboard ───────────────────────────────────────────
        with gr.Tab("Agent Dashboard"):
            agent_md = gr.Markdown(build_agent_dashboard)
            agent_refresh = gr.Button("Refresh", size="sm")
            agent_refresh.click(build_agent_dashboard, outputs=agent_md)

        # ── Tab 2: Activity Timeline ─────────────────────────────────────────
        with gr.Tab("Activity Timeline"):
            timeline_md = gr.Markdown(build_activity_timeline)
            timeline_refresh = gr.Button("Refresh", size="sm")
            timeline_refresh.click(build_activity_timeline, outputs=timeline_md)

        # ── Tab 3: Token & Cost Tracker ──────────────────────────────────────
        with gr.Tab("Token & Cost"):
            token_md = gr.Markdown()
            cost_plot = gr.BarPlot(
                x="agent",
                y="cost_usd",
                title="Cost (USD) per Agent — 7 Days",
                x_title="Agent",
                y_title="Cost (USD)",
                height=280,
            )
            token_refresh = gr.Button("Refresh", size="sm")
            # Initialize on load
            app.load(refresh_token_tab, outputs=[token_md, cost_plot])
            token_refresh.click(refresh_token_tab, outputs=[token_md, cost_plot])

        # ── Tab 4: Health Status ─────────────────────────────────────────────
        with gr.Tab("Health Status"):
            health_md = gr.Markdown(build_health_status)
            health_refresh = gr.Button("Refresh Now", size="sm")
            health_refresh.click(build_health_status, outputs=health_md)

        # ── Tab 5: Research Feed ─────────────────────────────────────────────
        with gr.Tab("Research Feed"):
            research_md = gr.Markdown(build_research_feed)
            research_refresh = gr.Button("Refresh", size="sm")
            research_refresh.click(build_research_feed, outputs=research_md)

    # ── Auto-refresh timer (60s) ─────────────────────────────────────────────
    timer = gr.Timer(60)
    timer.tick(build_agent_dashboard, outputs=agent_md)
    timer.tick(build_activity_timeline, outputs=timeline_md)
    timer.tick(build_health_status, outputs=health_md)
    timer.tick(build_research_feed, outputs=research_md)


if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)
