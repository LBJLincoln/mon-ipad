#!/usr/bin/env python3
"""V2 Repo Configuration — Goals, context, and measurement bindings for all 7 repos.

Each repo has:
  - name: identifier
  - path: absolute path on VM
  - goals: target score (0-100) per category
  - measure_fn: function that returns list[Score]
  - improve_context: description for Claude Code when making improvements
  - priority: higher = work on this repo first when scores are equal

Goals are AMBITIOUS but ACHIEVABLE:
  - 90+ = excellent, world-class
  - 80+ = good, professional
  - 70+ = acceptable, functional
  - <60 = needs work
"""

from measures import (
    measure_mon_ipad, measure_rag_website, measure_rag_ingestion,
    measure_rag_dashboard, measure_nba_agent, measure_casino,
    measure_forge_tests,
)

# ─── Default goals per category ────────────────────────────────────────────
DEFAULT_GOALS = {
    "strategie":     80,
    "produit":       85,
    "business":      70,
    "communication": 75,
    "admin":         80,
    "test_eval":     80,
    "amelioration":  70,
}


# ─── All 7 Repos ──────────────────────────────────────────────────────────

REPOS = [
    {
        "name": "mon-ipad",
        "path": "/home/termius/mon-ipad",
        "measure_fn": measure_mon_ipad,
        "priority": 10,  # Highest — it's the tower
        "improve_context": (
            "Tour de controle. Python ops scripts, eval system, 5 agents, "
            "monitoring, n8n workflow orchestration. 4 RAG pipelines "
            "(Standard, Graph, Quant, Orchestrator). Key files: ops/*.py, "
            "eval/*.py, agents/. Do NOT touch CLAUDE.md or directives/."
        ),
        "goals": {
            "strategie":     85,
            "produit":       90,  # Pipelines MUST work
            "business":      50,  # Revenue tracked but MRR=0 expected for now
            "communication": 80,
            "admin":         90,  # Infra must be solid
            "test_eval":     85,  # Eval accuracy critical
            "amelioration":  75,
        },
    },
    {
        "name": "rag-website",
        "path": "/home/termius/rag-website",
        "measure_fn": measure_rag_website,
        "priority": 9,  # High — user-facing product
        "improve_context": (
            "Next.js 15 chatbot site. 9 pages (expert, satellite, marketplace, "
            "factory, vault, dashboard, valorisation, graph, nba). Tailwind CSS. "
            "Calls RAG pipelines via webhooks. Key: src/app/*/page.tsx. "
            "Must be accessible (a11y), fast, French natural language."
        ),
        "goals": {
            "strategie":     80,
            "produit":       90,  # Must be up and fast
            "business":      60,
            "communication": 80,
            "admin":         80,
            "test_eval":     70,
            "amelioration":  70,
        },
    },
    {
        "name": "rag-data-ingestion",
        "path": "/home/termius/rag-data-ingestion",
        "measure_fn": measure_rag_ingestion,
        "priority": 8,
        "improve_context": (
            "Python ingestion engine. 30+ scripts for Pinecone, Neo4j, Supabase. "
            "Handles PDF (Docling), web (Exa.AI), datasets. E5 multilingual "
            "embeddings. Target: 100K vectors, 100+ doc types. "
            "Key: scripts/*.py, ingest-*.py."
        ),
        "goals": {
            "strategie":     80,
            "produit":       85,  # Must ingest reliably
            "business":      50,
            "communication": 70,
            "admin":         75,
            "test_eval":     75,
            "amelioration":  70,
        },
    },
    {
        "name": "rag-dashboard",
        "path": "/home/termius/rag-dashboard",
        "measure_fn": measure_rag_dashboard,
        "priority": 5,
        "improve_context": (
            "Real-time monitoring dashboard. Next.js, shows pipeline accuracy, "
            "database sizes, phase gates. Polls status.json. Must be clear, "
            "fast, useful for investors."
        ),
        "goals": DEFAULT_GOALS,
    },
    {
        "name": "nomos-nba-agent",
        "path": "/home/termius/nomos-nba-agent",
        "measure_fn": measure_nba_agent,
        "priority": 6,
        "improve_context": (
            "Autonomous NBA expert agent. Python daemon (5min cycles). "
            "Tests on golden Q&A dataset (6 categories: player stats, team "
            "history, game analysis, betting, predictions, GOAT debates). "
            "Key: agents/nba-agent.py, tests/test-nba.py."
        ),
        "goals": {
            "strategie":     80,
            "produit":       85,
            "business":      50,
            "communication": 75,
            "admin":         75,
            "test_eval":     80,  # Accuracy matters
            "amelioration":  70,
        },
    },
    {
        "name": "nomos-casino",
        "path": "/home/termius/nomos-casino",
        "measure_fn": measure_casino,
        "priority": 4,
        "improve_context": (
            "Atari-style retro games (breakout, crash, snake, slots, wheel). "
            "HTML/JS games + Python tester agent with 6 personas. "
            "Key: games/*.html, agents/casino-tester.py. Focus on engagement "
            "(time on page > 3min, return rate > 30%)."
        ),
        "goals": {
            "strategie":     75,
            "produit":       80,
            "business":      50,
            "communication": 70,
            "admin":         70,
            "test_eval":     70,
            "amelioration":  65,
        },
    },
    {
        "name": "nomos-forge-tests",
        "path": "/home/termius/nomos-forge-tests",
        "measure_fn": measure_forge_tests,
        "priority": 7,
        "improve_context": (
            "Autonomous test suite for La Forge (factory page). 3 agents: "
            "forge-tester (API testing), user-simulator (8 personas), "
            "quality-scorer. Tests 7 enterprise categories in responses. "
            "Key: agents/*.py, tests/*.py."
        ),
        "goals": {
            "strategie":     85,
            "produit":       80,
            "business":      50,
            "communication": 75,
            "admin":         75,
            "test_eval":     85,  # Testing is its PURPOSE
            "amelioration":  70,
        },
    },
]


def get_repo(name: str) -> dict:
    """Get repo config by name."""
    for r in REPOS:
        if r["name"] == name:
            return r
    return None


def get_all_repos() -> list:
    """Get all repos sorted by priority (highest first)."""
    return sorted(REPOS, key=lambda r: r["priority"], reverse=True)
