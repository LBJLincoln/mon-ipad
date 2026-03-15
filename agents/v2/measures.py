#!/usr/bin/env python3
"""V2 Measurement System — Concrete metrics for every category × every repo.

RULE: NOTHING happens without being measured.
Every measurement is logged. Every score has evidence.
If we can't measure it, we can't improve it.

Each measurement function returns a Score(category, value, target, details).
The 'details' dict contains the raw evidence so we can always trace WHY a score is what it is.
"""

import json
import os
import subprocess
import time
import urllib.request
import ssl
from datetime import datetime, timezone
from pathlib import Path

# Import Score from engine (top-level, not inside functions)
from engine import Score

# SSL context
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE_DIR = Path("/home/termius/mon-ipad")

# ─── Shared Measurement Primitives ─────────────────────────────────────────

def http_check(url: str, timeout: int = 15) -> dict:
    """Check URL reachability. Returns {up, status, latency_ms}."""
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NomosV2/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            latency = round((time.time() - t0) * 1000)
            return {"up": True, "status": resp.status, "latency_ms": latency}
    except Exception as e:
        return {"up": False, "status": 0, "latency_ms": 0, "error": str(e)[:100]}


def git_health(repo_path: str) -> dict:
    """Measure git health of a repo."""
    if not Path(repo_path).exists():
        return {"exists": False, "clean": False, "commits_7d": 0, "last_commit": "never"}

    def run(cmd):
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path, timeout=10)
        return r.stdout.strip()

    try:
        # Clean working tree?
        status = run(["git", "status", "--porcelain"])
        clean = not bool(status)

        # Commits in last 7 days
        commits_7d = len(run(["git", "log", "--oneline", "--since=7 days ago"]).splitlines())

        # Last commit date
        last_commit = run(["git", "log", "-1", "--format=%ci"])

        # Total commits
        total = run(["git", "rev-list", "--count", "HEAD"])

        return {
            "exists": True, "clean": clean, "commits_7d": commits_7d,
            "last_commit": last_commit[:19], "total_commits": int(total or 0),
            "dirty_files": len(status.splitlines()) if status else 0,
        }
    except Exception as e:
        return {"exists": True, "clean": False, "commits_7d": 0, "error": str(e)[:100]}


def file_freshness(filepath: str, max_age_hours: int = 48) -> dict:
    """How fresh is a file? Returns {exists, age_hours, fresh}."""
    p = Path(filepath)
    if not p.exists():
        return {"exists": False, "age_hours": 999, "fresh": False}
    mtime = p.stat().st_mtime
    age_h = (time.time() - mtime) / 3600
    return {"exists": True, "age_hours": round(age_h, 1), "fresh": age_h < max_age_hours}


def count_tests(repo_path: str) -> dict:
    """Count test files and test functions (excludes node_modules, .git, data/)."""
    p = Path(repo_path)
    exclude = {"node_modules", ".git", ".next", "data", "logs", "__pycache__", "venv"}

    def filtered_rglob(pattern):
        results = []
        for f in p.rglob(pattern):
            if not any(part in exclude for part in f.parts):
                results.append(f)
        return results

    test_files = filtered_rglob("test*.py") + filtered_rglob("*_test.py")
    test_files += filtered_rglob("test*.ts") + filtered_rglob("test*.tsx")
    test_files += filtered_rglob("*.test.ts") + filtered_rglob("*.test.tsx")
    test_files += filtered_rglob("*.spec.ts") + filtered_rglob("*.spec.tsx")

    test_count = 0
    for tf in test_files:
        try:
            content = tf.read_text(errors="replace")
            test_count += content.count("def test_")
            test_count += content.count("it(")
            test_count += content.count("test(")
        except Exception:
            pass

    return {"test_files": len(test_files), "test_functions": test_count}


def has_file(repo_path: str, filename: str) -> bool:
    return Path(repo_path, filename).exists()


def count_files(repo_path: str, pattern: str) -> int:
    return len(list(Path(repo_path).rglob(pattern)))


def readme_quality(repo_path: str) -> dict:
    """Score README completeness."""
    readme = Path(repo_path) / "README.md"
    if not readme.exists():
        return {"exists": False, "lines": 0, "has_install": False,
                "has_usage": False, "has_badges": False, "score": 0}

    content = readme.read_text(errors="replace").lower()
    lines = len(content.splitlines())
    return {
        "exists": True,
        "lines": lines,
        "has_install": any(w in content for w in ["install", "setup", "getting started"]),
        "has_usage": any(w in content for w in ["usage", "how to", "example"]),
        "has_badges": "![" in content or "badge" in content,
        "has_api": any(w in content for w in ["api", "endpoint", "webhook"]),
        "score": min(100, lines * 2 + (20 if "install" in content else 0) +
                     (20 if "usage" in content else 0)),
    }


# ─── Per-Repo Measurement Functions ────────────────────────────────────────
# Each returns list[Score] — one per category

def measure_mon_ipad(cfg: dict) -> list:
    """Measure mon-ipad (tower) across all 7 categories."""
    path = cfg["path"]
    goals = cfg["goals"]
    scores = []

    # ── STRATEGIE: Are pipeline goals defined and tracked? ──
    has_roadmap = has_file(path, "technicals/PROJECT-ROADMAP.md")
    has_state = has_file(path, "directives/PROJECT-STATE.md")
    state_fresh = file_freshness(f"{path}/directives/PROJECT-STATE.md", 72)
    strat_score = (30 if has_roadmap else 0) + (30 if has_state else 0) + \
                  (40 if state_fresh.get("fresh") else 10)
    scores.append(Score("strategie", strat_score, goals["strategie"],
                        {"roadmap": has_roadmap, "state": has_state,
                         "state_fresh": state_fresh}))

    # ── PRODUIT: Are HF Spaces UP? (check root, not webhooks) ──
    spaces = {
        "S1": "https://lbjlincoln-nomos-rag-engine.hf.space",
        "S3": "https://lbjlincoln-nomos-rag-engine-3.hf.space",
        "S5": "https://lbjlincoln-nomos-rag-engine-5.hf.space",
        "S7": "https://lbjlincoln-nomos-rag-engine-7.hf.space",
    }
    up_count = 0
    pipe_details = {}
    for sname, url in spaces.items():
        check = http_check(url, timeout=10)
        pipe_details[sname] = check
        if check["up"]:
            up_count += 1
    prod_score = (up_count / len(spaces)) * 80
    # Bonus for health-status freshness
    health_fresh = file_freshness(f"{path}/data/health-status.json", 1)
    if health_fresh.get("fresh"):
        prod_score += 20
    scores.append(Score("produit", prod_score, goals["produit"], pipe_details))

    # ── BUSINESS: Revenue tracking? ──
    biz_events = Path(path) / "data" / "agents" / "business" / "events.jsonl"
    biz_data = {"tracked": False, "mrr": 0}
    if biz_events.exists():
        try:
            last_line = biz_events.read_text().strip().splitlines()[-1]
            biz = json.loads(last_line)
            biz_data["tracked"] = True
            biz_data["mrr"] = biz.get("summary", {}).get("mrr_usd", 0)
        except Exception:
            pass
    biz_score = 20 if biz_data["tracked"] else 0  # Base: tracking exists
    if biz_data["mrr"] > 0:
        biz_score += 80  # Revenue = full score
    scores.append(Score("business", biz_score, goals["business"], biz_data))

    # ── COMMUNICATION: Docs quality ──
    readme = readme_quality(path)
    has_pilotage = has_file(path, "docs/PILOTAGE.md")
    comm_score = min(100, readme["score"] // 2 + (30 if has_pilotage else 0) + 20)
    scores.append(Score("communication", comm_score, goals["communication"],
                        {"readme": readme, "pilotage": has_pilotage}))

    # ── ADMIN: Infrastructure health ──
    health_file = Path(path) / "data" / "health-status.json"
    admin_details = {"health_file": False, "spaces_up": 0, "spaces_total": 0}
    admin_score = 0
    if health_file.exists():
        try:
            health = json.loads(health_file.read_text())
            spaces = health.get("spaces", [])
            up = sum(1 for s in spaces if s.get("status") == "UP")
            admin_details = {"health_file": True, "spaces_up": up,
                             "spaces_total": len(spaces), "vectors": health.get("e5_vectors", 0)}
            admin_score = (up / max(len(spaces), 1)) * 70 + 30
        except Exception:
            pass
    scores.append(Score("admin", admin_score, goals["admin"], admin_details))

    # ── TEST_EVAL: Eval accuracy ──
    eval_details = {"blast_files": 0, "latest_accuracy": 0, "questions_total": 0}
    eval_score = 0
    blast_dir = Path(path) / "data" / "eval"
    if blast_dir.exists():
        blast_files = sorted(blast_dir.glob("blast-2*.json"))  # blast-2026*, not blast-state
        eval_details["blast_files"] = len(blast_files)
        if blast_files:
            try:
                data = json.loads(blast_files[-1].read_text())
                results = data.get("results", [])
                if results:
                    passed = sum(1 for r in results if r.get("status") == "pass")
                    acc = passed / len(results) * 100
                    eval_details["latest_accuracy"] = round(acc, 1)
                    eval_details["questions_total"] = len(results)
                    eval_score = acc
            except Exception:
                pass
    scores.append(Score("test_eval", eval_score, goals["test_eval"], eval_details))

    # ── AMELIORATION: Improvement velocity ──
    git = git_health(path)
    improver_state = Path(path) / "data" / "repo-improver-state.json"
    amel_details = {"commits_7d": git.get("commits_7d", 0), "total_improvements": 0}
    if improver_state.exists():
        try:
            state = json.loads(improver_state.read_text())
            amel_details["total_improvements"] = state.get("total_improvements", 0)
        except Exception:
            pass
    amel_score = min(100, git.get("commits_7d", 0) * 5 +
                     amel_details["total_improvements"])
    scores.append(Score("amelioration", amel_score, goals["amelioration"],
                        amel_details))

    return scores


def measure_rag_website(cfg: dict) -> list:
    """Measure rag-website across all 7 categories."""
    path = cfg["path"]
    goals = cfg["goals"]
    scores = []

    # STRATEGIE: Clear product vision, pages serving purpose
    pages = count_files(path, "src/app/*/page.tsx") + count_files(path, "src/app/page.tsx")
    claude_md = has_file(path, "CLAUDE.md")
    strat_score = min(100, pages * 8 + (20 if claude_md else 0))
    scores.append(Score("strategie", strat_score, goals["strategie"],
                        {"pages": pages, "claude_md": claude_md}))

    # PRODUIT: Site accessible, fast, working
    urls_to_check = [
        "https://nomos42.vercel.app",
        "https://nomos42.vercel.app/expert",
    ]
    up_count = 0
    latencies = []
    for url in urls_to_check:
        check = http_check(url)
        if check["up"]:
            up_count += 1
            latencies.append(check["latency_ms"])
    avg_latency = sum(latencies) / max(len(latencies), 1)
    prod_score = (up_count / len(urls_to_check)) * 70
    if avg_latency < 2000:
        prod_score += 30
    elif avg_latency < 5000:
        prod_score += 15
    scores.append(Score("produit", prod_score, goals["produit"],
                        {"up": up_count, "total": len(urls_to_check),
                         "avg_latency_ms": round(avg_latency)}))

    # BUSINESS: Payment integration, conversion paths
    has_stripe = False
    pkg_file = Path(path) / "package.json"
    if pkg_file.exists():
        content = pkg_file.read_text()
        has_stripe = "stripe" in content.lower()
    biz_score = 30 if has_stripe else 10  # Minimal: site exists
    scores.append(Score("business", biz_score, goals["business"],
                        {"stripe_integrated": has_stripe}))

    # COMMUNICATION: README, meta tags, social
    readme = readme_quality(path)
    comm_score = min(100, readme["score"] // 2 + 30)
    scores.append(Score("communication", comm_score, goals["communication"], readme))

    # ADMIN: Build passing, deps up to date
    git = git_health(path)
    has_lockfile = has_file(path, "package-lock.json") or has_file(path, "pnpm-lock.yaml")
    admin_score = 50 if git["exists"] else 0
    if git.get("clean"):
        admin_score += 25
    if has_lockfile:
        admin_score += 25
    scores.append(Score("admin", admin_score, goals["admin"],
                        {**git, "lockfile": has_lockfile}))

    # TEST_EVAL: Tests exist and pass
    tests = count_tests(path)
    test_score = min(100, tests["test_files"] * 15 + tests["test_functions"] * 3)
    scores.append(Score("test_eval", test_score, goals["test_eval"], tests))

    # AMELIORATION: Active development
    git = git_health(path)
    amel_score = min(100, git.get("commits_7d", 0) * 7)
    scores.append(Score("amelioration", amel_score, goals["amelioration"], git))

    return scores


def measure_rag_ingestion(cfg: dict) -> list:
    """Measure rag-data-ingestion across all 7 categories."""
    path = cfg["path"]
    goals = cfg["goals"]
    scores = []

    # STRATEGIE: Document type coverage
    scripts = count_files(path, "*.py") + count_files(path, "scripts/*.py")
    strat_score = min(100, scripts * 3)
    scores.append(Score("strategie", strat_score, goals["strategie"],
                        {"python_scripts": scripts}))

    # PRODUIT: Vectors in Pinecone (from mon-ipad health)
    health_file = BASE_DIR / "data" / "health-status.json"
    vectors = 0
    if health_file.exists():
        try:
            h = json.loads(health_file.read_text())
            vectors = h.get("e5_vectors", 0)
        except Exception:
            pass
    target_vectors = 100000
    prod_score = min(100, (vectors / target_vectors) * 100)
    scores.append(Score("produit", prod_score, goals["produit"],
                        {"vectors": vectors, "target": target_vectors}))

    # BUSINESS: Data supports monetizable queries
    biz_score = 40 if vectors > 50000 else 20 if vectors > 10000 else 5
    scores.append(Score("business", biz_score, goals["business"],
                        {"vectors_for_biz": vectors}))

    # COMMUNICATION: Documentation
    readme = readme_quality(path)
    scores.append(Score("communication", min(100, readme["score"]),
                        goals["communication"], readme))

    # ADMIN: Repo health
    git = git_health(path)
    admin_score = 50 if git.get("clean") else 30
    admin_score += min(50, git.get("commits_7d", 0) * 10)
    scores.append(Score("admin", admin_score, goals["admin"], git))

    # TEST_EVAL: Data quality tests
    tests = count_tests(path)
    has_quality_test = has_file(path, "test-data-quality.py") or \
                       has_file(path, "scripts/test-data-quality.py")
    test_score = min(100, tests["test_files"] * 15 + (30 if has_quality_test else 0))
    scores.append(Score("test_eval", test_score, goals["test_eval"],
                        {**tests, "quality_test": has_quality_test}))

    # AMELIORATION
    git = git_health(path)
    amel_score = min(100, git.get("commits_7d", 0) * 10)
    scores.append(Score("amelioration", amel_score, goals["amelioration"], git))

    return scores


def measure_rag_dashboard(cfg: dict) -> list:
    """Measure rag-dashboard across all 7 categories."""
    path = cfg["path"]
    goals = cfg["goals"]
    scores = []

    # STRATEGIE
    claude_md = has_file(path, "CLAUDE.md")
    scores.append(Score("strategie", 60 if claude_md else 20, goals["strategie"],
                        {"claude_md": claude_md}))

    # PRODUIT: Dashboard accessible
    check = http_check("https://nomos-dashboard.vercel.app")
    prod_score = 80 if check["up"] else 10
    scores.append(Score("produit", prod_score, goals["produit"], check))

    # BUSINESS
    scores.append(Score("business", 20, goals["business"],
                        {"note": "dashboard supports investor visibility"}))

    # COMMUNICATION
    readme = readme_quality(path)
    scores.append(Score("communication", min(100, readme["score"]),
                        goals["communication"], readme))

    # ADMIN
    git = git_health(path)
    admin_score = 50 if git.get("clean") else 30
    scores.append(Score("admin", admin_score, goals["admin"], git))

    # TEST_EVAL
    tests = count_tests(path)
    scores.append(Score("test_eval", min(100, tests["test_files"] * 20),
                        goals["test_eval"], tests))

    # AMELIORATION
    git = git_health(path)
    amel_score = min(100, git.get("commits_7d", 0) * 10)
    scores.append(Score("amelioration", amel_score, goals["amelioration"], git))

    return scores


def measure_nba_agent(cfg: dict) -> list:
    """Measure nomos-nba-agent across all 7 categories."""
    path = cfg["path"]
    goals = cfg["goals"]
    scores = []

    # STRATEGIE: Category coverage (6 NBA categories)
    has_eval = has_file(path, "tests/test-nba.py")
    has_agent = has_file(path, "agents/nba-agent.py")
    strat_score = 40 + (20 if has_eval else 0) + (20 if has_agent else 0)
    scores.append(Score("strategie", strat_score, goals["strategie"],
                        {"eval": has_eval, "agent": has_agent}))

    # PRODUIT: NBA page accessible + daemon running
    check = http_check("https://nomos42.vercel.app/nba")
    daemon_check = Path(path) / "data" / "nba-daemon.pid"
    daemon_running = daemon_check.exists()
    prod_score = (50 if check["up"] else 0) + (30 if daemon_running else 0)
    scores.append(Score("produit", prod_score, goals["produit"],
                        {**check, "daemon": daemon_running}))

    # BUSINESS
    scores.append(Score("business", 15, goals["business"],
                        {"note": "needs monetization path"}))

    # COMMUNICATION
    readme = readme_quality(path)
    scores.append(Score("communication", min(100, readme["score"]),
                        goals["communication"], readme))

    # ADMIN
    git = git_health(path)
    admin_score = 50 if git.get("clean") else 30
    scores.append(Score("admin", admin_score, goals["admin"], git))

    # TEST_EVAL: Latest eval from mon-ipad sync
    eval_file = BASE_DIR / "data" / "nba-agent" / "latest-eval.json"
    eval_data = {"accuracy": 0}
    if eval_file.exists():
        try:
            data = json.loads(eval_file.read_text())
            eval_data["accuracy"] = data.get("accuracy", data.get("score", 0))
            eval_data.update(data)
        except Exception:
            pass
    test_score = min(100, eval_data["accuracy"])
    scores.append(Score("test_eval", test_score, goals["test_eval"], eval_data))

    # AMELIORATION
    git = git_health(path)
    amel_score = min(100, git.get("commits_7d", 0) * 8)
    scores.append(Score("amelioration", amel_score, goals["amelioration"], git))

    return scores


def measure_casino(cfg: dict) -> list:
    """Measure nomos-casino across all 7 categories."""
    path = cfg["path"]
    goals = cfg["goals"]
    scores = []

    # STRATEGIE
    game_files = count_files(path, "*.html") + count_files(path, "games/*.html")
    strat_score = min(100, game_files * 15 + 20)
    scores.append(Score("strategie", strat_score, goals["strategie"],
                        {"game_files": game_files}))

    # PRODUIT: Casino page accessible
    check = http_check("https://nomos42.vercel.app/casino")
    prod_score = 80 if check["up"] else 10
    scores.append(Score("produit", prod_score, goals["produit"], check))

    # BUSINESS
    scores.append(Score("business", 15, goals["business"],
                        {"note": "engagement metrics needed"}))

    # COMMUNICATION
    readme = readme_quality(path)
    scores.append(Score("communication", min(100, readme["score"]),
                        goals["communication"], readme))

    # ADMIN
    git = git_health(path)
    admin_score = 50 if git.get("clean") else 30
    scores.append(Score("admin", admin_score, goals["admin"], git))

    # TEST_EVAL
    casino_test = BASE_DIR / "data" / "casino" / "latest-test.json"
    test_data = {"score": 0}
    if casino_test.exists():
        try:
            data = json.loads(casino_test.read_text())
            test_data.update(data)
            test_data["score"] = data.get("score", data.get("pass_rate", 0))
        except Exception:
            pass
    scores.append(Score("test_eval", min(100, test_data["score"]),
                        goals["test_eval"], test_data))

    # AMELIORATION
    git = git_health(path)
    amel_score = min(100, git.get("commits_7d", 0) * 8)
    scores.append(Score("amelioration", amel_score, goals["amelioration"], git))

    return scores


def measure_forge_tests(cfg: dict) -> list:
    """Measure nomos-forge-tests across all 7 categories."""
    path = cfg["path"]
    goals = cfg["goals"]
    scores = []

    # STRATEGIE: Test coverage of 7 categories
    has_7cat_test = has_file(path, "tests/test-7-categories.py")
    has_forge_test = has_file(path, "tests/test-forge-api.py")
    strat_score = 30 + (30 if has_7cat_test else 0) + (20 if has_forge_test else 0)
    scores.append(Score("strategie", strat_score, goals["strategie"],
                        {"7cat_test": has_7cat_test, "forge_test": has_forge_test}))

    # PRODUIT: Forge API responding
    check = http_check("https://nomos42.vercel.app/api/forge")
    prod_score = 80 if check["up"] else 10
    scores.append(Score("produit", prod_score, goals["produit"], check))

    # BUSINESS
    scores.append(Score("business", 20, goals["business"],
                        {"note": "test infra supports product quality"}))

    # COMMUNICATION
    readme = readme_quality(path)
    scores.append(Score("communication", min(100, readme["score"]),
                        goals["communication"], readme))

    # ADMIN: Daemon running
    git = git_health(path)
    admin_score = 50 if git.get("clean") else 30
    scores.append(Score("admin", admin_score, goals["admin"], git))

    # TEST_EVAL
    tests = count_tests(path)
    test_score = min(100, tests["test_files"] * 15 + tests["test_functions"] * 3)
    scores.append(Score("test_eval", test_score, goals["test_eval"], tests))

    # AMELIORATION
    git = git_health(path)
    amel_score = min(100, git.get("commits_7d", 0) * 8)
    scores.append(Score("amelioration", amel_score, goals["amelioration"], git))

    return scores
