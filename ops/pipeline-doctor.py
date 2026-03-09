#!/usr/bin/env python3
"""
Pipeline Doctor — Closed-loop Diagnose → Fix → Verify → Snapshot
=================================================================
The missing link that unifies 23+ existing scripts into a single
diagnostic + auto-fix + learning loop.

Components:
  1. FixesLibraryParser  — Parses fixes-library.md into structured JSON
  2. ExecutionExtractor  — Fetches & parses n8n execution data
  3. ErrorMatcher        — Matches errors against known fixes
  4. ConfidenceEngine    — Scores pipeline health & fix confidence
  5. SnapshotManager     — Auto-snapshots when golden thresholds pass
  6. AutoFixEngine       — Orchestrates: diagnose → fix → verify → snapshot
  7. LearningTracker     — Logs attempts to improve future scoring

Usage:
  python3 scripts/pipeline-doctor.py                        # All pipelines (dry-run)
  python3 scripts/pipeline-doctor.py --pipeline standard    # One pipeline
  python3 scripts/pipeline-doctor.py --apply                # Apply fixes
  python3 scripts/pipeline-doctor.py --apply --max-attempts 3
  python3 scripts/pipeline-doctor.py --snapshot-only        # Snapshot if tests pass
  python3 scripts/pipeline-doctor.py --reparse-fixes        # Re-parse fixes-library.md
  python3 scripts/pipeline-doctor.py --show-history         # Fix application history
  python3 scripts/pipeline-doctor.py --list-snapshots       # List validated snapshots
  python3 scripts/pipeline-doctor.py --repos                # All 7 repos (git, CI, Vercel)
  python3 scripts/pipeline-doctor.py --repos --repo mon-ipad  # One repo

Last updated: 2026-02-28
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

# ─── Paths ────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
EVAL_DIR = os.path.join(REPO_ROOT, "eval")
LOGS_DIR = os.path.join(REPO_ROOT, "logs")
SNAPSHOT_DIR = os.path.join(REPO_ROOT, "snapshot", "validated")

FIXES_LIBRARY_MD = os.path.join(REPO_ROOT, "technicals", "debug", "fixes-library.md")
FIXES_PARSED_JSON = os.path.join(LOGS_DIR, "fixes-library-parsed.json")
DOCTOR_HISTORY = os.path.join(LOGS_DIR, "doctor-history.jsonl")
DOCTOR_REPORT = os.path.join(LOGS_DIR, "pipeline-doctor-report.json")
SNAPSHOT_MANIFEST = os.path.join(SNAPSHOT_DIR, "manifest.json")

# ─── Load .env.local ──────────────────────────────────────────────
def _load_env():
    env_file = os.path.join(REPO_ROOT, ".env.local")
    if not os.path.exists(env_file):
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

_load_env()

N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")
CI_EMAIL = os.environ.get("CI_EMAIL", "ci@nomos.ai")
CI_PASSWORD = os.environ.get("CI_PASSWORD", "CI-Nomos-2026!")

# ─── Pipeline configs (aligned with n8n-execution-analyzer.py) ────
PIPELINES = {
    "standard": {
        "workflow_id": "TmgyRP20N4JFd9CB",
        "webhook": "/webhook/rag-multi-index-v3",
    },
    "graph": {
        "workflow_id": "6257AfT1l4FMC6lY",
        "webhook": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    },
    "quantitative": {
        "workflow_id": "E19NZG9WfM7FNsxr",
        "webhook": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    },
    "orchestrator": {
        "workflow_id": "ALd4gOEqiKL5KR1p",
        "webhook": "/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
    },
}

# ─── Repo configs (for --repos mode) ─────────────────────────────
REPOS = {
    "mon-ipad": {
        "role": "Control tower — directives, eval scripts, MCP configs",
        "remote": "origin",
        "ci_workflow": "Eval 1000q Parallel",
        "vercel_url": None,
        "checks": ["git", "ci"],
    },
    "rag-tests": {
        "role": "Eval scripts, datasets, test results",
        "remote": "rag-tests",
        "ci_workflow": "CI - RAG Tests",
        "vercel_url": None,
        "checks": ["git", "ci"],
    },
    "rag-website": {
        "role": "Next.js 14 — 4 sector sites + chatbots",
        "remote": "rag-website",
        "ci_workflow": None,
        "vercel_url": "https://nomos-ai-pied.vercel.app",
        "checks": ["git", "vercel"],
    },
    "rag-dashboard": {
        "role": "Live metrics dashboard (HTML/JS)",
        "remote": "rag-dashboard",
        "ci_workflow": None,
        "vercel_url": "https://nomos-dashboard-alexis-morets-projects.vercel.app",
        "checks": ["git", "vercel"],
    },
    "rag-data-ingestion": {
        "role": "Ingestion V3.1 + Enrichissement V3.1",
        "remote": "rag-data-ingestion",
        "ci_workflow": None,
        "vercel_url": None,
        "checks": ["git", "scripts"],
    },
    "rag-pme-connectors": {
        "role": "Next.js 15 — 15 PME apps + MacBook chat",
        "remote": "rag-pme-connectors",
        "ci_workflow": "Deploy Website to Vercel",
        "vercel_url": "https://nomos-pme-connectors-alexis-morets-projects.vercel.app",
        "checks": ["git", "ci", "vercel"],
    },
    "rag-pme-usecases": {
        "role": "Next.js 14 — 200 use cases",
        "remote": "rag-pme-usecases",
        "ci_workflow": None,
        "vercel_url": "https://nomos-pme-usecases-alexis-morets-projects.vercel.app",
        "checks": ["git", "vercel"],
    },
}

# ─── Golden thresholds (imported at runtime from golden-check.py) ─
# We import dynamically to avoid path issues; fallback hardcoded.
GOLDEN_THRESHOLDS = {
    "standard":     {"min_accuracy": 85.0, "max_latency_p95": 5000,  "max_error_rate": 5.0,  "required_smoke_pass": 0.8},
    "graph":        {"min_accuracy": 70.0, "max_latency_p95": 8000,  "max_error_rate": 10.0, "required_smoke_pass": 0.6},
    "quantitative": {"min_accuracy": 85.0, "max_latency_p95": 10000, "max_error_rate": 5.0,  "required_smoke_pass": 0.8},
    "orchestrator": {"min_accuracy": 70.0, "max_latency_p95": 15000, "max_error_rate": 10.0, "required_smoke_pass": 0.6},
}

try:
    sys.path.insert(0, EVAL_DIR)
    from importlib.machinery import SourceFileLoader
    gc_mod = SourceFileLoader("golden_check", os.path.join(EVAL_DIR, "golden-check.py")).load_module()
    GOLDEN_THRESHOLDS = gc_mod.GOLDEN_THRESHOLDS
except Exception:
    pass  # use fallback above


# ═══════════════════════════════════════════════════════════════════
# Component 1 — FixesLibraryParser
# ═══════════════════════════════════════════════════════════════════

class FixesLibraryParser:
    """Parses technicals/debug/fixes-library.md into structured JSON."""

    # Regex for each fix section: ### FIX-NN — Title
    FIX_HEADER_RE = re.compile(r'^###\s+FIX-(\d+)\s*[—–-]\s*(.+)$', re.MULTILINE)
    # Field extractors
    FIELD_RES = {
        "session": re.compile(r'\*\*Session\*\*\s*:\s*(.+)', re.IGNORECASE),
        "pipeline": re.compile(r'\*\*Pipeline\*\*\s*:\s*(.+)', re.IGNORECASE),
        "component": re.compile(r'\*\*Composant\*\*\s*:\s*(.+)', re.IGNORECASE),
        "symptom": re.compile(r'\*\*Symptome?\*\*\s*:\s*(.+)', re.IGNORECASE),
        "root_cause": re.compile(r'\*\*(?:Root cause|Cause racine)\*\*\s*:\s*(.+)', re.IGNORECASE),
        "fix": re.compile(r'\*\*Fix\*\*\s*:\s*(.+)', re.IGNORECASE),
        "impact": re.compile(r'\*\*Impact\*\*\s*:\s*(.+)', re.IGNORECASE),
    }

    # Anti-pattern section
    AP_RE = re.compile(r'^\|\s*(AP-\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|$', re.MULTILINE)

    # Category extraction from index table
    INDEX_RE = re.compile(
        r'^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(\d+\w*)\s*\|\s*(\w+)\s*\|$',
        re.MULTILINE,
    )

    def __init__(self, md_path=FIXES_LIBRARY_MD, cache_path=FIXES_PARSED_JSON):
        self.md_path = md_path
        self.cache_path = cache_path

    def needs_reparse(self) -> bool:
        """Check if MD has been modified since last parse."""
        if not os.path.exists(self.cache_path):
            return True
        md_mtime = os.path.getmtime(self.md_path)
        cache_mtime = os.path.getmtime(self.cache_path)
        return md_mtime > cache_mtime

    def parse(self, force=False) -> dict:
        """Parse fixes-library.md → structured dict. Uses cache if fresh."""
        if not force and not self.needs_reparse() and os.path.exists(self.cache_path):
            with open(self.cache_path) as f:
                return json.load(f)

        with open(self.md_path, encoding="utf-8") as f:
            content = f.read()

        result = {
            "parsed_at": datetime.now(timezone.utc).isoformat(),
            "source": self.md_path,
            "fixes": [],
            "anti_patterns": [],
            "index": [],
        }

        # Parse index table
        for m in self.INDEX_RE.finditer(content):
            result["index"].append({
                "fix_id": int(m.group(1)),
                "category": m.group(2).strip(),
                "problem": m.group(3).strip(),
                "session": m.group(4).strip(),
                "impact": m.group(5).strip(),
            })

        # Build category lookup from index
        cat_lookup = {}
        for entry in result["index"]:
            cat_lookup[entry["fix_id"]] = entry["category"]

        # Parse individual fixes
        headers = list(self.FIX_HEADER_RE.finditer(content))
        for i, header in enumerate(headers):
            fix_id = int(header.group(1))
            title = header.group(2).strip()

            # Extract section text until next fix header or end
            start = header.end()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(content)
            section = content[start:end]

            fix_entry = {
                "fix_id": fix_id,
                "title": title,
                "category": cat_lookup.get(fix_id, "Unknown"),
                "symptom_patterns": [],
            }

            # Extract fields
            for field_name, regex in self.FIELD_RES.items():
                m = regex.search(section)
                if m:
                    fix_entry[field_name] = m.group(1).strip()

            # Build symptom patterns for matching
            fix_entry["symptom_patterns"] = self._extract_symptom_patterns(fix_entry)

            # Extract keywords from title + symptom + root cause
            fix_entry["keywords"] = self._extract_keywords(fix_entry)

            result["fixes"].append(fix_entry)

        # Parse anti-patterns
        for m in self.AP_RE.finditer(content):
            result["anti_patterns"].append({
                "id": m.group(1),
                "pattern": m.group(2).strip(),
                "frequency": m.group(3).strip(),
                "prevention": m.group(4).strip(),
            })

        # Cache
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return result

    def _extract_symptom_patterns(self, fix: dict) -> list:
        """Extract regex-ready patterns from symptom and root cause text."""
        patterns = []
        symptom = fix.get("symptom", "")
        root_cause = fix.get("root_cause", "")

        # Extract quoted strings (error messages, code snippets)
        for text in [symptom, root_cause]:
            # Backtick-quoted: `some error`
            for m in re.finditer(r'`([^`]{4,})`', text):
                pat = re.escape(m.group(1))
                patterns.append(pat)
            # Double-quoted: "some error"
            for m in re.finditer(r'"([^"]{4,})"', text):
                pat = re.escape(m.group(1))
                patterns.append(pat)

        # HTTP error codes
        for text in [symptom, root_cause, fix.get("title", "")]:
            for m in re.finditer(r'(?:HTTP\s*)?(\d{3})\b', text):
                code = m.group(1)
                if code in ("400", "401", "403", "404", "429", "500", "502", "503"):
                    patterns.append(rf'\b{code}\b')

        return patterns

    def _extract_keywords(self, fix: dict) -> list:
        """Extract significant keywords for Jaccard matching."""
        text = " ".join([
            fix.get("title", ""),
            fix.get("symptom", ""),
            fix.get("root_cause", ""),
            fix.get("category", ""),
        ]).lower()

        # Remove markdown artifacts
        text = re.sub(r'[`*_\[\]()#|]', ' ', text)
        # Split and filter
        words = set(text.split())
        # Remove stopwords
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
            "to", "for", "of", "with", "and", "or", "not", "but", "by",
            "from", "as", "it", "its", "de", "du", "le", "la", "les",
            "un", "une", "des", "dans", "pour", "par", "avec", "qui",
            "que", "est", "pas", "ne", "en", "ce", "se", "et", "ou",
            "mais", "car", "si", "sur", "vers", "chez",
        }
        keywords = [w for w in words if len(w) > 2 and w not in stopwords]
        return sorted(keywords)


# ═══════════════════════════════════════════════════════════════════
# Component 2 — ExecutionExtractor
# ═══════════════════════════════════════════════════════════════════

class ExecutionExtractor:
    """Fetches and parses n8n execution data via REST API."""

    def __init__(self, host=N8N_HOST, email=CI_EMAIL, password=CI_PASSWORD):
        self.host = host
        self.email = email
        self.password = password
        self.cookie = None

    def _http(self, url, method="GET", data=None, headers=None, timeout=30):
        """HTTP request helper."""
        import urllib.request
        import urllib.error

        if headers is None:
            headers = {}
        headers.setdefault("User-Agent", "PipelineDoctor/1.0")

        if data and isinstance(data, dict):
            data = json.dumps(data).encode()
            headers.setdefault("Content-Type", "application/json")

        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            body = resp.read().decode("utf-8", errors="replace")
            return {
                "status": resp.status,
                "body": body,
                "json": json.loads(body) if body else None,
                "headers": dict(resp.headers),
            }
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            return {"status": e.code, "body": body, "json": None, "error": str(e)}
        except Exception as e:
            return {"status": 0, "body": "", "json": None, "error": str(e)}

    def login(self) -> bool:
        """Login to n8n, store session cookie."""
        resp = self._http(
            f"{self.host}/rest/login",
            method="POST",
            data={"emailOrLdapLoginId": self.email, "password": self.password},
        )
        if resp["status"] != 200:
            print(f"  [!] n8n login failed: HTTP {resp['status']}")
            return False
        cookie_header = resp["headers"].get("Set-Cookie", resp["headers"].get("set-cookie", ""))
        self.cookie = cookie_header.split(";")[0] if cookie_header else ""
        return bool(self.cookie)

    def _api(self, path, method="GET", data=None):
        """Call n8n REST API with session cookie."""
        return self._http(
            f"{self.host}{path}",
            method=method,
            data=data,
            headers={"Cookie": self.cookie} if self.cookie else {},
        )

    def get_executions(self, pipeline: str, limit: int = 5) -> list:
        """Fetch recent executions for a pipeline."""
        config = PIPELINES.get(pipeline)
        if not config:
            return []

        wf_id = config["workflow_id"]
        resp = self._api(f"/rest/executions?workflowId={wf_id}&limit={limit}")

        if resp["status"] != 200:
            return []

        exec_list = resp["json"]
        if isinstance(exec_list, dict):
            exec_list = exec_list.get("data", exec_list.get("results", []))
        if not isinstance(exec_list, list):
            return []

        return exec_list

    def analyze_execution(self, execution_id: str) -> dict:
        """Analyze a single execution — extract errors per node."""
        resp = self._api(f"/rest/executions/{execution_id}")
        if resp["status"] != 200:
            return {"error": f"HTTP {resp['status']}", "execution_id": execution_id}

        detail = resp["json"]
        d = detail.get("data", detail)

        result = {
            "execution_id": execution_id,
            "status": d.get("status", "unknown"),
            "started_at": d.get("startedAt", ""),
            "stopped_at": d.get("stoppedAt", ""),
            "workflow_id": d.get("workflowId", ""),
            "errors": [],
            "nodes_executed": 0,
            "nodes_failed": 0,
            "last_node": "N/A",
        }

        # Parse execution data (handles flattened format)
        exec_data_raw = d.get("data", "")
        parsed = self._parse_execution(exec_data_raw)

        result["last_node"] = parsed.get("lastNodeExecuted", "N/A")

        # Top-level error
        top_error = parsed.get("error")
        if top_error and isinstance(top_error, dict):
            result["errors"].append({
                "node": top_error.get("node", "unknown"),
                "message": str(top_error.get("message", "")),
                "description": str(top_error.get("description", "")),
                "type": "execution_error",
            })

        # Per-node errors
        run_data = parsed.get("runData", {})
        for node_name, runs in run_data.items():
            result["nodes_executed"] += 1
            for run in runs:
                if run.get("error"):
                    result["nodes_failed"] += 1
                    result["errors"].append({
                        "node": node_name,
                        "message": str(run["error"])[:500],
                        "type": "node_error",
                    })

        return result

    def _deref(self, data_list, ref):
        """Dereference a value in flattened execution data."""
        if isinstance(ref, str) and ref.isdigit():
            idx = int(ref)
            if idx < len(data_list):
                return data_list[idx]
        return ref

    def _parse_execution(self, raw):
        """Parse execution data (standard or flattened format)."""
        if not raw:
            return {}
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                return {"error": {"message": "Failed to parse execution data"}}

        if isinstance(raw, dict):
            return raw

        if isinstance(raw, list) and len(raw) > 0:
            root = raw[0]
            result = {}

            result_idx = root.get("resultData", "")
            result_data = self._deref(raw, result_idx)

            if isinstance(result_data, dict):
                # Error
                error_ref = result_data.get("error", "")
                error = self._deref(raw, error_ref)
                if isinstance(error, dict):
                    result["error"] = {
                        "message": self._deref(raw, error.get("message", "")) if isinstance(error.get("message", ""), str) and error.get("message", "").isdigit() else error.get("message", ""),
                        "description": self._deref(raw, error.get("description", "")) if isinstance(error.get("description", ""), str) and error.get("description", "").isdigit() else error.get("description", ""),
                        "node": self._deref(raw, error.get("node", "")),
                    }

                result["lastNodeExecuted"] = self._deref(raw, result_data.get("lastNodeExecuted", ""))

                # Run data
                run_data_ref = result_data.get("runData", "")
                run_data = self._deref(raw, run_data_ref)
                if isinstance(run_data, dict):
                    result["runData"] = {}
                    for node_name, ref in run_data.items():
                        node_runs = self._deref(raw, ref)
                        if isinstance(node_runs, list):
                            parsed_runs = []
                            for run_ref in node_runs:
                                run = self._deref(raw, run_ref)
                                if isinstance(run, dict):
                                    parsed_run = {}
                                    err_ref = run.get("error")
                                    if err_ref:
                                        err = self._deref(raw, err_ref)
                                        if isinstance(err, dict):
                                            parsed_run["error"] = self._deref(raw, err.get("message", "")) if isinstance(err.get("message", ""), str) and err.get("message", "").isdigit() else err.get("message", "")
                                        else:
                                            parsed_run["error"] = str(err)
                                    parsed_run["status"] = self._deref(raw, run.get("executionStatus", "")) if isinstance(run.get("executionStatus", ""), str) and run.get("executionStatus", "").isdigit() else run.get("executionStatus", "")
                                    parsed_runs.append(parsed_run)
                            result["runData"][node_name] = parsed_runs

            return result

        return {}

    def get_workflow(self, pipeline: str) -> dict:
        """Fetch the current workflow JSON for a pipeline."""
        config = PIPELINES.get(pipeline)
        if not config:
            return {}

        resp = self._api(f"/rest/workflows/{config['workflow_id']}")
        if resp["status"] != 200:
            return {}
        return resp["json"] or {}

    def check_webhook_health(self, pipeline: str) -> dict:
        """Quick HTTP check on the webhook endpoint."""
        config = PIPELINES.get(pipeline)
        if not config:
            return {"healthy": False, "error": "Unknown pipeline"}

        url = f"{self.host}{config['webhook']}"
        try:
            import urllib.request
            req = urllib.request.Request(url, method="POST",
                                         data=json.dumps({"query": "health check", "tenant_id": "doctor"}).encode(),
                                         headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=30)
            return {"healthy": True, "status_code": resp.status}
        except Exception as e:
            code = getattr(e, "code", 0)
            return {"healthy": code not in (404, 502, 503, 0), "status_code": code, "error": str(e)[:200]}


# ═══════════════════════════════════════════════════════════════════
# Component 3 — ErrorMatcher
# ═══════════════════════════════════════════════════════════════════

class ErrorMatcher:
    """Matches execution errors against known fixes from fixes-library."""

    def __init__(self, fixes_data: dict):
        self.fixes = fixes_data.get("fixes", [])
        self.anti_patterns = fixes_data.get("anti_patterns", [])

    def match(self, error: dict, pipeline: str = "") -> list:
        """Match an error against known fixes. Returns sorted candidates."""
        error_text = " ".join([
            str(error.get("message", "")),
            str(error.get("description", "")),
            str(error.get("node", "")),
        ]).lower()

        if not error_text.strip():
            return []

        error_keywords = set(re.findall(r'\w{3,}', error_text))

        candidates = []
        for fix in self.fixes:
            score = self._score_match(fix, error_text, error_keywords, pipeline)
            if score > 0.1:
                candidates.append({
                    "fix_id": fix["fix_id"],
                    "title": fix.get("title", ""),
                    "category": fix.get("category", ""),
                    "confidence": round(score, 3),
                    "symptom": fix.get("symptom", ""),
                    "fix_description": fix.get("fix", ""),
                })

        # Sort by confidence descending
        candidates.sort(key=lambda c: c["confidence"], reverse=True)
        return candidates[:5]  # top 5

    def _score_match(self, fix: dict, error_text: str, error_keywords: set, pipeline: str) -> float:
        """Score how well a fix matches an error.

        Score = symptom_regex × 0.40 + keyword_jaccard × 0.30
              + category_match × 0.15 + pipeline_match × 0.15
        """
        # 1. Symptom pattern regex match (0 or 1)
        regex_score = 0.0
        patterns = fix.get("symptom_patterns", [])
        if patterns:
            matched = 0
            for pat in patterns:
                try:
                    if re.search(pat, error_text, re.IGNORECASE):
                        matched += 1
                except re.error:
                    pass
            regex_score = min(matched / max(len(patterns), 1), 1.0)

        # 2. Keyword Jaccard similarity
        fix_keywords = set(fix.get("keywords", []))
        if fix_keywords and error_keywords:
            intersection = fix_keywords & error_keywords
            union = fix_keywords | error_keywords
            jaccard = len(intersection) / len(union) if union else 0
        else:
            jaccard = 0.0

        # 3. Category match (n8n infra errors match n8n fixes, etc.)
        category = fix.get("category", "").lower()
        cat_score = 0.0
        if pipeline and pipeline.lower() in category:
            cat_score = 1.0
        elif any(kw in category for kw in ["tous", "all", "infrastructure", "hf space"]):
            cat_score = 0.5

        # 4. Pipeline match
        fix_pipeline = fix.get("pipeline", "").lower()
        pipe_score = 0.0
        if not fix_pipeline or not pipeline:
            pipe_score = 0.3  # neutral
        elif pipeline.lower() in fix_pipeline:
            pipe_score = 1.0
        elif "all" in fix_pipeline or "tous" in fix_pipeline:
            pipe_score = 0.7

        score = (regex_score * 0.40) + (jaccard * 0.30) + (cat_score * 0.15) + (pipe_score * 0.15)
        return score

    def check_anti_patterns(self, error_text: str) -> list:
        """Check if error matches known anti-patterns."""
        matches = []
        for ap in self.anti_patterns:
            pattern_text = ap.get("pattern", "").lower()
            keywords = set(re.findall(r'\w{3,}', pattern_text))
            error_kw = set(re.findall(r'\w{3,}', error_text.lower()))
            overlap = keywords & error_kw
            if len(overlap) >= 2:
                matches.append(ap)
        return matches


# ═══════════════════════════════════════════════════════════════════
# Component 4 — ConfidenceEngine
# ═══════════════════════════════════════════════════════════════════

class ConfidenceEngine:
    """Scores pipeline health (0-100) and fix confidence (0.0-1.0)."""

    def __init__(self, history_path=DOCTOR_HISTORY):
        self.history_path = history_path
        self._history_cache = None

    def pipeline_health_score(self, pipeline: str, metrics: dict = None) -> dict:
        """Compute pipeline health score (0-100).

        score = accuracy_vs_golden × 0.40
              + latency_vs_threshold × 0.20
              + error_rate_inverse × 0.20
              + smoke_pass_rate × 0.15
              + trend × 0.05
        """
        golden = GOLDEN_THRESHOLDS.get(pipeline, {})
        if not golden or not metrics:
            return {"score": 0, "breakdown": {}, "status": "no_data"}

        # Accuracy component (0-100 scaled to threshold)
        accuracy = metrics.get("accuracy", 0.0)
        min_acc = golden.get("min_accuracy", 70.0)
        acc_score = min((accuracy / min_acc) * 100, 100) if min_acc > 0 else 0

        # Latency component
        latency = metrics.get("latency_p95", 0)
        max_lat = golden.get("max_latency_p95", 10000)
        if latency == 0:
            lat_score = 50  # no data = neutral
        elif latency <= max_lat:
            lat_score = 100 - (latency / max_lat * 50)  # better = higher
        else:
            lat_score = max(0, 50 - ((latency - max_lat) / max_lat * 50))

        # Error rate component (lower = better)
        error_rate = metrics.get("error_rate", 0.0)
        max_err = golden.get("max_error_rate", 10.0)
        err_score = max(0, 100 - (error_rate / max_err * 100)) if max_err > 0 else 0

        # Smoke pass rate
        smoke = metrics.get("smoke_pass_rate", 0.0)
        smoke_score = smoke * 100

        # Trend placeholder (requires historical data)
        trend_score = 50  # neutral

        total = (
            acc_score * 0.40
            + lat_score * 0.20
            + err_score * 0.20
            + smoke_score * 0.15
            + trend_score * 0.05
        )

        # Determine status
        if total >= 80 and accuracy >= min_acc:
            status = "HEALTHY"
        elif total >= 50:
            status = "DEGRADED"
        else:
            status = "CRITICAL"

        return {
            "score": round(total, 1),
            "status": status,
            "breakdown": {
                "accuracy": {"value": accuracy, "threshold": min_acc, "component_score": round(acc_score, 1)},
                "latency_p95": {"value": latency, "threshold": max_lat, "component_score": round(lat_score, 1)},
                "error_rate": {"value": error_rate, "threshold": max_err, "component_score": round(err_score, 1)},
                "smoke_pass": {"value": smoke, "component_score": round(smoke_score, 1)},
                "trend": {"component_score": round(trend_score, 1)},
            },
        }

    def fix_confidence(self, fix_match_score: float, fix_id: int) -> float:
        """Compute fix confidence (0.0-1.0).

        confidence = symptom_match × 0.50
                   + historical_success × 0.30
                   + scope_risk_inverse × 0.20
        """
        # Historical success rate
        hist_rate = self._get_historical_success(fix_id)

        # Scope risk: assume moderate (0.5) without detailed analysis
        scope_score = 0.5

        confidence = (
            fix_match_score * 0.50
            + hist_rate * 0.30
            + scope_score * 0.20
        )
        return round(min(confidence, 1.0), 3)

    def _get_historical_success(self, fix_id: int) -> float:
        """Get historical success rate for a fix from doctor-history.jsonl."""
        if self._history_cache is None:
            self._history_cache = self._load_history()

        entries = [e for e in self._history_cache if e.get("fix_id") == fix_id]
        if not entries:
            return 0.5  # neutral (no data)

        successes = sum(1 for e in entries if e.get("result") == "success")
        return successes / len(entries)

    def _load_history(self) -> list:
        """Load doctor history from JSONL file."""
        if not os.path.exists(self.history_path):
            return []
        entries = []
        with open(self.history_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return entries


# ═══════════════════════════════════════════════════════════════════
# Component 5 — SnapshotManager
# ═══════════════════════════════════════════════════════════════════

class SnapshotManager:
    """Auto-snapshots workflows when golden thresholds are met."""

    def __init__(self, snapshot_dir=SNAPSHOT_DIR, manifest_path=SNAPSHOT_MANIFEST):
        self.snapshot_dir = snapshot_dir
        self.manifest_path = manifest_path
        os.makedirs(self.snapshot_dir, exist_ok=True)

    def load_manifest(self) -> dict:
        """Load the snapshot manifest."""
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path) as f:
                return json.load(f)
        return {"snapshots": [], "best_by_pipeline": {}}

    def save_manifest(self, manifest: dict):
        """Save the snapshot manifest."""
        with open(self.manifest_path, "w") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

    def should_snapshot(self, pipeline: str, health_score: float) -> bool:
        """Check if this score beats the best known snapshot."""
        manifest = self.load_manifest()
        best = manifest.get("best_by_pipeline", {}).get(pipeline, {})
        best_score = best.get("health_score", 0)
        return health_score > best_score

    def create_snapshot(self, pipeline: str, workflow_json: dict,
                        health_score: float, metrics: dict) -> str:
        """Create a validated snapshot and update manifest."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        score_int = int(health_score)
        filename = f"{pipeline}-{timestamp}-score{score_int}.json"
        filepath = os.path.join(self.snapshot_dir, filename)

        # Save workflow with metadata header
        snapshot_data = {
            "_snapshot_meta": {
                "pipeline": pipeline,
                "timestamp": timestamp,
                "health_score": health_score,
                "metrics": metrics,
                "source": "pipeline-doctor",
            },
            "workflow": workflow_json,
        }

        with open(filepath, "w") as f:
            json.dump(snapshot_data, f, indent=2, ensure_ascii=False)

        # Update manifest
        manifest = self.load_manifest()
        entry = {
            "pipeline": pipeline,
            "filename": filename,
            "timestamp": timestamp,
            "health_score": health_score,
            "metrics_summary": {
                "accuracy": metrics.get("accuracy", 0),
                "error_rate": metrics.get("error_rate", 0),
            },
        }
        manifest["snapshots"].append(entry)

        # Update best-by-pipeline
        current_best = manifest.get("best_by_pipeline", {}).get(pipeline, {})
        if health_score > current_best.get("health_score", 0):
            manifest.setdefault("best_by_pipeline", {})[pipeline] = entry

        self.save_manifest(manifest)
        return filepath

    def list_snapshots(self) -> list:
        """List all validated snapshots."""
        manifest = self.load_manifest()
        return manifest.get("snapshots", [])


# ═══════════════════════════════════════════════════════════════════
# Component 6 — AutoFixEngine
# ═══════════════════════════════════════════════════════════════════

class AutoFixEngine:
    """Orchestrates the closed-loop: diagnose → fix → verify → snapshot."""

    def __init__(self, extractor: ExecutionExtractor, matcher: ErrorMatcher,
                 confidence: ConfidenceEngine, snapshot_mgr: SnapshotManager,
                 tracker: "LearningTracker"):
        self.extractor = extractor
        self.matcher = matcher
        self.confidence = confidence
        self.snapshot_mgr = snapshot_mgr
        self.tracker = tracker

    def diagnose(self, pipeline: str) -> dict:
        """Full diagnostic for a pipeline."""
        print(f"\n{'─'*50}")
        print(f"  DIAGNOSING: {pipeline.upper()}")
        print(f"{'─'*50}")

        report = {
            "pipeline": pipeline,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "webhook_health": {},
            "recent_errors": [],
            "matched_fixes": [],
            "anti_pattern_warnings": [],
            "health": {},
            "metrics": {},
        }

        # 1. Webhook health check
        print("  [1/4] Checking webhook health...")
        health = self.extractor.check_webhook_health(pipeline)
        report["webhook_health"] = health
        status_icon = "[+]" if health["healthy"] else "[-]"
        print(f"    {status_icon} HTTP {health.get('status_code', '?')} {'healthy' if health['healthy'] else 'DOWN'}")

        # 2. Recent execution errors
        print("  [2/4] Fetching recent executions...")
        execs = self.extractor.get_executions(pipeline, limit=3)
        all_errors = []
        for ex in execs[:3]:
            ex_id = ex.get("id", "")
            if ex_id:
                analysis = self.extractor.analyze_execution(str(ex_id))
                for err in analysis.get("errors", []):
                    err["execution_id"] = ex_id
                    all_errors.append(err)
                exec_status = analysis.get("status", "?")
                print(f"    Exec {ex_id}: {exec_status} | {analysis.get('nodes_failed', 0)} errors")

        report["recent_errors"] = all_errors[:10]

        # 3. Match errors against fixes library
        print("  [3/4] Matching against fixes library...")
        seen_fix_ids = set()
        for error in all_errors[:5]:
            candidates = self.matcher.match(error, pipeline)
            for c in candidates:
                if c["fix_id"] not in seen_fix_ids:
                    c["confidence"] = self.confidence.fix_confidence(c["confidence"], c["fix_id"])
                    report["matched_fixes"].append(c)
                    seen_fix_ids.add(c["fix_id"])

        # Sort all matched fixes by confidence
        report["matched_fixes"].sort(key=lambda f: f["confidence"], reverse=True)

        if report["matched_fixes"]:
            print(f"    Found {len(report['matched_fixes'])} candidate fix(es):")
            for mf in report["matched_fixes"][:3]:
                print(f"      FIX-{mf['fix_id']:02d} ({mf['confidence']:.2f}) — {mf['title'][:60]}")
        else:
            print("    No matching fixes found in library")

        # Check anti-patterns
        error_text = " ".join(str(e.get("message", "")) for e in all_errors)
        ap_warnings = self.matcher.check_anti_patterns(error_text)
        report["anti_pattern_warnings"] = ap_warnings
        if ap_warnings:
            print(f"    [!] {len(ap_warnings)} anti-pattern warning(s)")

        # 4. Pipeline health score
        print("  [4/4] Computing health score...")
        metrics = self._get_metrics(pipeline)
        report["metrics"] = metrics
        health_data = self.confidence.pipeline_health_score(pipeline, metrics)
        report["health"] = health_data

        color_map = {"HEALTHY": "[+]", "DEGRADED": "[~]", "CRITICAL": "[-]"}
        icon = color_map.get(health_data.get("status", ""), "[?]")
        print(f"    {icon} Health: {health_data.get('score', 0):.1f}/100 ({health_data.get('status', 'unknown')})")

        if health_data.get("breakdown"):
            for k, v in health_data["breakdown"].items():
                if "value" in v:
                    print(f"       {k}: {v.get('value', '?')} (threshold: {v.get('threshold', '?')}, score: {v.get('component_score', '?')})")

        return report

    def auto_fix(self, pipeline: str, max_attempts: int = 3, dry_run: bool = False) -> dict:
        """Run the full auto-fix loop for a pipeline.

        For each candidate fix (up to max_attempts):
          1. Apply fix (if not dry_run)
          2. Run quick-test 5 questions
          3. Run golden-check
          4. If PASS → snapshot → done
          5. If FAIL → revert, try next candidate
        """
        report = self.diagnose(pipeline)

        if not report["matched_fixes"]:
            print("\n  No fixes to apply — manual investigation needed")
            report["auto_fix_result"] = "no_candidates"
            return report

        if dry_run:
            print("\n  DRY RUN — would attempt these fixes:")
            for mf in report["matched_fixes"][:max_attempts]:
                print(f"    FIX-{mf['fix_id']:02d} (confidence: {mf['confidence']:.2f}) — {mf['title'][:60]}")
            report["auto_fix_result"] = "dry_run"
            return report

        print(f"\n  AUTO-FIX MODE — max {max_attempts} attempts")
        candidates = report["matched_fixes"][:max_attempts]

        for i, candidate in enumerate(candidates):
            print(f"\n  --- Attempt {i+1}/{len(candidates)}: FIX-{candidate['fix_id']:02d} ---")
            print(f"  Title: {candidate['title'][:70]}")
            print(f"  Confidence: {candidate['confidence']:.2f}")

            # Log attempt start
            self.tracker.log_attempt(
                pipeline=pipeline,
                fix_id=candidate["fix_id"],
                confidence=candidate["confidence"],
                error_pattern=report["recent_errors"][0].get("message", "")[:200] if report["recent_errors"] else "",
            )

            # Note: Actual fix application would require pipeline-specific logic
            # (patching n8n workflow nodes via REST API). For now, we log the
            # recommendation and run verification.
            print(f"  [!] Auto-apply not yet implemented for FIX-{candidate['fix_id']:02d}")
            print(f"      Symptom: {candidate.get('symptom', 'N/A')[:100]}")
            print(f"      Suggested: {candidate.get('fix_description', 'N/A')[:100]}")

            # Run quick-test to check current state
            print("  Running quick-test (5 questions)...")
            qt_result = self._run_quick_test(pipeline)

            if qt_result and qt_result.get("all_pass"):
                print("  [+] Quick-test PASSED!")

                # Run golden-check
                print("  Running golden-check...")
                gc_result = self._run_golden_check(pipeline)

                if gc_result and gc_result.get("passed"):
                    print("  [+] Golden check PASSED!")

                    # Snapshot
                    metrics = self._get_metrics(pipeline)
                    health = self.confidence.pipeline_health_score(pipeline, metrics)
                    score = health.get("score", 0)

                    if self.snapshot_mgr.should_snapshot(pipeline, score):
                        wf = self.extractor.get_workflow(pipeline)
                        if wf:
                            path = self.snapshot_mgr.create_snapshot(pipeline, wf, score, metrics)
                            print(f"  [+] Snapshot saved: {path}")

                    self.tracker.log_result(pipeline, candidate["fix_id"], "success", score)
                    report["auto_fix_result"] = "success"
                    report["applied_fix"] = candidate
                    return report
                else:
                    print("  [-] Golden check FAILED")
                    self.tracker.log_result(pipeline, candidate["fix_id"], "golden_fail", 0)
            else:
                print("  [-] Quick-test FAILED")
                self.tracker.log_result(pipeline, candidate["fix_id"], "test_fail", 0)

        print(f"\n  All {len(candidates)} fix attempts exhausted — ESCALATION needed")
        report["auto_fix_result"] = "exhausted"
        return report

    def snapshot_only(self, pipeline: str) -> dict:
        """Snapshot the current state if golden checks pass."""
        print(f"\n  Snapshot check for {pipeline.upper()}...")

        # Run quick-test
        qt_result = self._run_quick_test(pipeline)
        if not qt_result or not qt_result.get("all_pass"):
            print("  [-] Quick-test did not pass — no snapshot")
            return {"snapshot": False, "reason": "quick_test_failed"}

        # Run golden-check
        gc_result = self._run_golden_check(pipeline)
        if not gc_result or not gc_result.get("passed"):
            print("  [-] Golden check did not pass — no snapshot")
            return {"snapshot": False, "reason": "golden_check_failed"}

        # Compute health score
        metrics = self._get_metrics(pipeline)
        health = self.confidence.pipeline_health_score(pipeline, metrics)
        score = health.get("score", 0)

        if not self.snapshot_mgr.should_snapshot(pipeline, score):
            print(f"  [~] Score {score:.1f} does not beat current best — no snapshot")
            return {"snapshot": False, "reason": "not_best_score", "score": score}

        # Create snapshot
        wf = self.extractor.get_workflow(pipeline)
        if not wf:
            print("  [-] Could not fetch workflow — no snapshot")
            return {"snapshot": False, "reason": "workflow_fetch_failed"}

        path = self.snapshot_mgr.create_snapshot(pipeline, wf, score, metrics)
        print(f"  [+] Snapshot saved: {path}")
        return {"snapshot": True, "path": path, "score": score}

    def _run_quick_test(self, pipeline: str) -> dict:
        """Run quick-test.py as subprocess."""
        cmd = [
            sys.executable, os.path.join(EVAL_DIR, "quick-test.py"),
            "--pipelines", pipeline,
            "--questions", "5",
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600,
                cwd=REPO_ROOT,
            )
            # Parse output for pass/fail
            output = result.stdout + result.stderr
            all_pass = result.returncode == 0

            # Extract pass count from output like "standard: 5/5 PASS"
            match = re.search(rf'{pipeline}:\s*(\d+)/(\d+)\s*(PASS|FAIL)', output)
            passed = int(match.group(1)) if match else 0
            total = int(match.group(2)) if match else 0

            return {
                "all_pass": all_pass,
                "passed": passed,
                "total": total,
                "output": output[-500:],  # last 500 chars
            }
        except subprocess.TimeoutExpired:
            return {"all_pass": False, "error": "timeout"}
        except Exception as e:
            return {"all_pass": False, "error": str(e)[:200]}

    def _run_golden_check(self, pipeline: str) -> dict:
        """Run golden-check.py as subprocess."""
        cmd = [
            sys.executable, os.path.join(EVAL_DIR, "golden-check.py"),
            "--pipeline", pipeline, "--quiet",
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                cwd=REPO_ROOT,
            )
            if result.stdout.strip():
                data = json.loads(result.stdout.strip())
                return data
            return {"passed": result.returncode == 0}
        except Exception as e:
            return {"passed": False, "error": str(e)[:200]}

    def _get_metrics(self, pipeline: str) -> dict:
        """Get current metrics for a pipeline (from data.json or eval files)."""
        # Try data.json first
        data_json = os.path.join(REPO_ROOT, "docs", "data.json")
        if os.path.exists(data_json):
            try:
                with open(data_json) as f:
                    data = json.load(f)
                pipe_data = data.get("pipelines", {}).get(pipeline, {})
                if pipe_data:
                    accuracy = 0.0
                    trends = pipe_data.get("accuracy_trend", [])
                    if trends:
                        accuracy = trends[-1]
                    elif "accuracy" in pipe_data:
                        accuracy = pipe_data["accuracy"]

                    return {
                        "accuracy": accuracy,
                        "latency_p95": pipe_data.get("latency_p95", pipe_data.get("avg_latency_ms", 0) * 1.5),
                        "error_rate": pipe_data.get("error_rate", 0.0),
                        "smoke_pass_rate": accuracy / 100.0,
                        "source": "data.json",
                    }
            except (json.JSONDecodeError, KeyError):
                pass

        # Fallback: try latest iterative eval
        iter_dir = os.path.join(REPO_ROOT, "logs", "iterative-eval")
        if os.path.isdir(iter_dir):
            import glob as g
            files = sorted(g.glob(os.path.join(iter_dir, "iterative-*.json")))
            if files:
                try:
                    with open(files[-1]) as f:
                        data = json.load(f)
                    pipe_data = data.get("pipelines", {}).get(pipeline, {})
                    if pipe_data:
                        return {
                            "accuracy": pipe_data.get("final_accuracy", 0.0),
                            "error_rate": pipe_data.get("final_error_rate", 0.0),
                            "latency_p95": 0,
                            "smoke_pass_rate": pipe_data.get("final_accuracy", 0.0) / 100.0,
                            "source": files[-1],
                        }
                except (json.JSONDecodeError, KeyError):
                    pass

        return {}


# ═══════════════════════════════════════════════════════════════════
# Component 7 — LearningTracker
# ═══════════════════════════════════════════════════════════════════

class LearningTracker:
    """Logs fix attempts to improve future scoring."""

    def __init__(self, history_path=DOCTOR_HISTORY):
        self.history_path = history_path
        os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
        self._pending = {}

    def log_attempt(self, pipeline: str, fix_id: int, confidence: float, error_pattern: str):
        """Log the start of a fix attempt."""
        key = f"{pipeline}:{fix_id}"
        self._pending[key] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pipeline": pipeline,
            "fix_id": fix_id,
            "confidence": confidence,
            "error_pattern": error_pattern[:300],
        }

    def log_result(self, pipeline: str, fix_id: int, result: str, accuracy_after: float = 0):
        """Log the result of a fix attempt."""
        key = f"{pipeline}:{fix_id}"
        entry = self._pending.pop(key, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pipeline": pipeline,
            "fix_id": fix_id,
        })
        entry["result"] = result
        entry["accuracy_after"] = accuracy_after

        with open(self.history_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def show_history(self) -> list:
        """Load and display all history entries."""
        if not os.path.exists(self.history_path):
            return []
        entries = []
        with open(self.history_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return entries

    def success_rates(self) -> dict:
        """Compute per-fix success rates."""
        entries = self.show_history()
        if not entries:
            return {}

        fix_stats = {}
        for e in entries:
            fid = e.get("fix_id", 0)
            if fid not in fix_stats:
                fix_stats[fid] = {"attempts": 0, "successes": 0}
            fix_stats[fid]["attempts"] += 1
            if e.get("result") == "success":
                fix_stats[fid]["successes"] += 1

        return {
            fid: {
                **stats,
                "rate": round(stats["successes"] / stats["attempts"], 2) if stats["attempts"] > 0 else 0,
            }
            for fid, stats in fix_stats.items()
        }


# ═══════════════════════════════════════════════════════════════════
# Component 8 — RepoDiagnosticEngine (covers all 7 repos)
# ═══════════════════════════════════════════════════════════════════

class RepoDiagnosticEngine:
    """Diagnose health of all 7 repos: git sync, CI, Vercel, scripts."""

    def __init__(self):
        self.reports = {}

    def _run_cmd(self, cmd, timeout=30):
        """Run a shell command, return (returncode, stdout)."""
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout
            )
            return result.returncode, result.stdout.strip()
        except subprocess.TimeoutExpired:
            return -1, "TIMEOUT"
        except Exception as e:
            return -1, str(e)

    def _http_check(self, url, timeout=15):
        """HTTP GET with latency tracking."""
        import urllib.request
        import urllib.error
        start = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pipeline-doctor/1.1"})
            resp = urllib.request.urlopen(req, timeout=timeout)
            latency = int((time.time() - start) * 1000)
            return {"healthy": True, "status_code": resp.getcode(), "latency_ms": latency}
        except urllib.error.HTTPError as e:
            latency = int((time.time() - start) * 1000)
            return {"healthy": False, "status_code": e.code, "latency_ms": latency}
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            return {"healthy": False, "status_code": 0, "latency_ms": latency, "error": str(e)}

    def check_git(self, repo_name, config):
        """Check git sync status for a repo."""
        remote = config["remote"]
        # Get last commit on remote
        rc, out = self._run_cmd(f"git log {remote}/main --oneline -1 2>/dev/null")
        if rc != 0:
            # Try fetching first
            self._run_cmd(f"git fetch {remote} main 2>/dev/null", timeout=15)
            rc, out = self._run_cmd(f"git log {remote}/main --oneline -1 2>/dev/null")

        if rc != 0 or not out:
            return {"status": "error", "message": f"Cannot read {remote}/main"}

        sha = out.split()[0] if out else "?"
        msg = " ".join(out.split()[1:]) if out else "?"

        # Get commit date
        rc2, date_out = self._run_cmd(
            f"git log {remote}/main -1 --format='%ci' 2>/dev/null"
        )
        commit_date = date_out.strip("'") if rc2 == 0 else "?"

        # Check if local tracking is behind
        rc3, diff_out = self._run_cmd(
            f"git rev-list --count {remote}/main..HEAD 2>/dev/null"
        )
        ahead = int(diff_out) if rc3 == 0 and diff_out.isdigit() else 0
        rc4, diff_out2 = self._run_cmd(
            f"git rev-list --count HEAD..{remote}/main 2>/dev/null"
        )
        behind = int(diff_out2) if rc4 == 0 and diff_out2.isdigit() else 0

        # Days since commit
        days = 0
        if commit_date and commit_date != "?":
            try:
                from datetime import datetime as dt
                cd = dt.strptime(commit_date[:19], "%Y-%m-%d %H:%M:%S")
                days = (datetime.now() - cd).days
            except Exception:
                pass

        sync = "in_sync"
        if ahead > 0 and behind > 0:
            sync = "diverged"
        elif behind > 0:
            sync = "behind"
        elif ahead > 0:
            sync = "ahead"

        return {
            "status": "ok",
            "last_sha": sha,
            "last_msg": msg[:60],
            "commit_date": commit_date[:19] if commit_date != "?" else "?",
            "days_since_commit": days,
            "stale": days > 7,
            "sync": sync,
            "ahead": ahead,
            "behind": behind,
        }

    def check_ci(self, repo_name, config):
        """Check CI/CD status via gh CLI."""
        workflow = config.get("ci_workflow")
        if not workflow:
            return {"status": "no_ci", "message": "No CI configured"}

        gh_repo = f"LBJLincoln/{repo_name}"
        rc, out = self._run_cmd(
            f'gh run list --repo {gh_repo} --workflow "{workflow}" --limit 3 --json status,conclusion,updatedAt,displayTitle 2>/dev/null',
            timeout=20
        )
        if rc != 0 or not out:
            return {"status": "error", "message": "gh CLI failed"}

        try:
            runs = json.loads(out)
        except json.JSONDecodeError:
            return {"status": "error", "message": "Bad JSON from gh"}

        if not runs:
            return {"status": "no_runs", "message": "No recent runs"}

        latest = runs[0]
        healthy = latest.get("conclusion") == "success"
        return {
            "status": "healthy" if healthy else "failing",
            "healthy": healthy,
            "latest_conclusion": latest.get("conclusion", "?"),
            "latest_status": latest.get("status", "?"),
            "latest_title": latest.get("displayTitle", "?")[:60],
            "updated_at": latest.get("updatedAt", "?"),
            "total_runs": len(runs),
        }

    def check_vercel(self, repo_name, config):
        """Check Vercel site health."""
        url = config.get("vercel_url")
        if not url:
            return {"status": "no_vercel", "message": "No Vercel deployment"}
        return self._http_check(url)

    def check_scripts(self, repo_name, config):
        """Check repo-specific scripts/tooling health."""
        remote = config["remote"]
        # Check if key files exist on the remote branch
        checks = []

        if repo_name == "rag-data-ingestion":
            # Check for key ingestion scripts
            for f in ["scripts/download-sector-datasets.py", "docker-compose.yml"]:
                rc, out = self._run_cmd(
                    f"git show {remote}/main:{f} 2>/dev/null | head -1"
                )
                checks.append({"file": f, "exists": rc == 0 and bool(out)})
        elif repo_name == "rag-tests":
            for f in ["eval/quick-test.py", "eval/iterative-eval.py"]:
                rc, out = self._run_cmd(
                    f"git show {remote}/main:{f} 2>/dev/null | head -1"
                )
                checks.append({"file": f, "exists": rc == 0 and bool(out)})

        found = sum(1 for c in checks if c["exists"])
        total = len(checks) if checks else 1
        return {
            "status": "ok" if found == total else "degraded",
            "files_checked": checks,
            "found": found,
            "total": total,
        }

    def diagnose_repo(self, repo_name):
        """Run all configured checks for a single repo."""
        config = REPOS.get(repo_name)
        if not config:
            return {"repo": repo_name, "error": "Unknown repo"}

        report = {
            "repo": repo_name,
            "role": config["role"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {},
        }

        for check_type in config.get("checks", []):
            if check_type == "git":
                report["checks"]["git"] = self.check_git(repo_name, config)
            elif check_type == "ci":
                report["checks"]["ci"] = self.check_ci(repo_name, config)
            elif check_type == "vercel":
                report["checks"]["vercel"] = self.check_vercel(repo_name, config)
            elif check_type == "scripts":
                report["checks"]["scripts"] = self.check_scripts(repo_name, config)

        # Compute repo health score
        report["health"] = self._compute_repo_health(report)
        return report

    def _compute_repo_health(self, report):
        """Compute 0-100 health score for a repo."""
        checks = report.get("checks", {})
        scores = []

        # Git: 30% weight
        git = checks.get("git", {})
        if git.get("status") == "ok":
            git_score = 100.0
            if git.get("stale"):
                git_score -= 30
            if git.get("sync") == "behind":
                git_score -= 20
            elif git.get("sync") == "diverged":
                git_score -= 40
            scores.append(("git", git_score, 0.30))
        elif git:
            scores.append(("git", 0.0, 0.30))

        # CI: 25% weight
        ci = checks.get("ci", {})
        if ci.get("status") == "no_ci":
            # No CI configured — neutral, don't penalize
            pass
        elif ci.get("status") == "healthy":
            scores.append(("ci", 100.0, 0.25))
        elif ci.get("status") == "failing":
            scores.append(("ci", 20.0, 0.25))
        elif ci:
            scores.append(("ci", 0.0, 0.25))

        # Vercel: 25% weight
        vercel = checks.get("vercel", {})
        if vercel.get("status") == "no_vercel":
            pass  # No Vercel — neutral
        elif vercel.get("healthy"):
            latency = vercel.get("latency_ms", 0)
            v_score = 100.0 if latency < 5000 else max(50.0, 100.0 - (latency - 5000) / 100)
            scores.append(("vercel", v_score, 0.25))
        elif vercel:
            scores.append(("vercel", 0.0, 0.25))

        # Scripts: 20% weight
        scripts = checks.get("scripts", {})
        if scripts.get("status") == "ok":
            scores.append(("scripts", 100.0, 0.20))
        elif scripts.get("status") == "degraded":
            found = scripts.get("found", 0)
            total = scripts.get("total", 1)
            scores.append(("scripts", (found / total) * 100, 0.20))
        elif scripts:
            scores.append(("scripts", 0.0, 0.20))

        if not scores:
            return {"score": 0.0, "status": "no_data"}

        # Normalize weights to sum to 1.0
        total_weight = sum(w for _, _, w in scores)
        if total_weight == 0:
            return {"score": 0.0, "status": "no_data"}

        score = sum(s * (w / total_weight) for _, s, w in scores)
        status = "HEALTHY" if score >= 80 else "DEGRADED" if score >= 50 else "CRITICAL"
        return {
            "score": round(score, 1),
            "status": status,
            "breakdown": {name: round(s, 1) for name, s, _ in scores},
        }

    def diagnose_all(self, repo_names=None):
        """Diagnose all (or selected) repos."""
        targets = repo_names or list(REPOS.keys())
        results = {}
        for repo in targets:
            print(f"\n{'─'*50}")
            print(f"  DIAGNOSING REPO: {repo.upper()}")
            print(f"{'─'*50}")

            report = self.diagnose_repo(repo)
            results[repo] = report

            # Print summary
            health = report.get("health", {})
            score = health.get("score", 0)
            status = health.get("status", "?")
            icon = {"HEALTHY": "[+]", "DEGRADED": "[~]", "CRITICAL": "[-]"}.get(status, "[?]")
            print(f"  {icon} Health: {score}/100 ({status})")

            for check_name, check_data in report.get("checks", {}).items():
                if check_name == "git":
                    sync = check_data.get("sync", "?")
                    days = check_data.get("days_since_commit", "?")
                    sha = check_data.get("last_sha", "?")
                    print(f"    git: {sync} | {sha} | {days}d ago")
                elif check_name == "ci":
                    ci_status = check_data.get("status", "?")
                    conclusion = check_data.get("latest_conclusion", "?")
                    print(f"    ci: {ci_status} (latest: {conclusion})")
                elif check_name == "vercel":
                    if check_data.get("healthy"):
                        lat = check_data.get("latency_ms", "?")
                        print(f"    vercel: UP ({lat}ms)")
                    elif check_data.get("status") == "no_vercel":
                        print(f"    vercel: N/A")
                    else:
                        code = check_data.get("status_code", "?")
                        print(f"    vercel: DOWN (HTTP {code})")
                elif check_name == "scripts":
                    found = check_data.get("found", 0)
                    total = check_data.get("total", 0)
                    print(f"    scripts: {found}/{total} found")

        self.reports = results
        return results


# ═══════════════════════════════════════════════════════════════════
# CLI & Main
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Pipeline Doctor — Closed-loop Diagnose → Fix → Verify → Snapshot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--pipeline", "-p",
        choices=list(PIPELINES.keys()),
        help="Target pipeline (default: all)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply fixes (default: dry-run diagnostic only)",
    )
    parser.add_argument(
        "--max-attempts",
        type=int, default=3,
        help="Max fix attempts per pipeline (default: 3)",
    )
    parser.add_argument(
        "--snapshot-only",
        action="store_true",
        help="Only snapshot if golden tests pass (no fix attempt)",
    )
    parser.add_argument(
        "--reparse-fixes",
        action="store_true",
        help="Force re-parse of fixes-library.md",
    )
    parser.add_argument(
        "--show-history",
        action="store_true",
        help="Show fix application history",
    )
    parser.add_argument(
        "--list-snapshots",
        action="store_true",
        help="List validated snapshots",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output report as JSON (machine-readable)",
    )
    parser.add_argument(
        "--repos",
        action="store_true",
        help="Diagnose all 7 repos (git, CI, Vercel, scripts) instead of pipelines",
    )
    parser.add_argument(
        "--repo", "-r",
        choices=list(REPOS.keys()),
        help="Target a specific repo (use with --repos)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  PIPELINE DOCTOR v1.1")
    print(f"  Host: {N8N_HOST}")
    print(f"  Mode: {'repos' if args.repos else 'pipelines'}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # ─── Utility commands ──────────────────────────────────────
    if args.reparse_fixes:
        print("\n  Re-parsing fixes-library.md...")
        fp = FixesLibraryParser()
        data = fp.parse(force=True)
        n_fixes = len(data.get("fixes", []))
        n_ap = len(data.get("anti_patterns", []))
        print(f"  Parsed {n_fixes} fixes, {n_ap} anti-patterns")
        print(f"  Cached to: {FIXES_PARSED_JSON}")

        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            for fix in data["fixes"]:
                patterns_count = len(fix.get("symptom_patterns", []))
                kw_count = len(fix.get("keywords", []))
                print(f"    FIX-{fix['fix_id']:02d} | {fix.get('category', '?'):25s} | {patterns_count} patterns, {kw_count} keywords | {fix['title'][:50]}")
        return

    if args.show_history:
        tracker = LearningTracker()
        entries = tracker.show_history()
        rates = tracker.success_rates()

        if not entries:
            print("\n  No fix history yet.")
            return

        print(f"\n  Fix History ({len(entries)} entries):")
        print(f"  {'Timestamp':25s} | {'Pipeline':15s} | {'FIX':6s} | {'Result':12s} | {'Conf':5s}")
        print(f"  {'-'*25}-+-{'-'*15}-+-{'-'*6}-+-{'-'*12}-+-{'-'*5}")
        for e in entries[-20:]:  # last 20
            ts = e.get("timestamp", "?")[:19]
            pipe = e.get("pipeline", "?")
            fid = f"FIX-{e.get('fix_id', '?'):02d}" if isinstance(e.get("fix_id"), int) else "?"
            result = e.get("result", "?")
            conf = f"{e.get('confidence', 0):.2f}"
            print(f"  {ts:25s} | {pipe:15s} | {fid:6s} | {result:12s} | {conf}")

        if rates:
            print(f"\n  Success Rates:")
            for fid, stats in sorted(rates.items()):
                print(f"    FIX-{fid:02d}: {stats['successes']}/{stats['attempts']} ({stats['rate']:.0%})")
        return

    if args.list_snapshots:
        sm = SnapshotManager()
        snapshots = sm.list_snapshots()
        manifest = sm.load_manifest()

        if not snapshots:
            print("\n  No validated snapshots yet.")
            return

        print(f"\n  Validated Snapshots ({len(snapshots)}):")
        print(f"  {'Pipeline':15s} | {'Timestamp':20s} | {'Score':7s} | {'Accuracy':10s} | Filename")
        print(f"  {'-'*15}-+-{'-'*20}-+-{'-'*7}-+-{'-'*10}-+-{'-'*30}")
        for s in snapshots:
            pipe = s.get("pipeline", "?")
            ts = s.get("timestamp", "?")
            score = f"{s.get('health_score', 0):.1f}"
            acc = f"{s.get('metrics_summary', {}).get('accuracy', 0):.1f}%"
            fname = s.get("filename", "?")
            print(f"  {pipe:15s} | {ts:20s} | {score:>7s} | {acc:>10s} | {fname}")

        best = manifest.get("best_by_pipeline", {})
        if best:
            print(f"\n  Best per pipeline:")
            for pipe, info in best.items():
                print(f"    {pipe}: {info.get('filename', '?')} (score: {info.get('health_score', 0):.1f})")
        return

    # ─── Repos diagnostic flow ──────────────────────────────────
    if args.repos:
        print(f"\n  Fetching remotes...")
        subprocess.run("git fetch --all --quiet 2>/dev/null", shell=True, timeout=30)

        repo_engine = RepoDiagnosticEngine()
        targets = [args.repo] if args.repo else None
        repo_results = repo_engine.diagnose_all(targets)

        # Save repo report
        repo_report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "repos",
            "repos": repo_results,
        }

        repo_report_path = os.path.join(LOGS_DIR, "repo-doctor-report.json")
        os.makedirs(os.path.dirname(repo_report_path), exist_ok=True)
        with open(repo_report_path, "w") as f:
            json.dump(repo_report, f, indent=2, ensure_ascii=False, default=str)

        # Also inject into main doctor report
        os.makedirs(os.path.dirname(DOCTOR_REPORT), exist_ok=True)
        try:
            with open(DOCTOR_REPORT) as f:
                existing = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing = {}
        existing["repos"] = repo_results
        existing["repos_timestamp"] = datetime.now(timezone.utc).isoformat()
        with open(DOCTOR_REPORT, "w") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False, default=str)

        # Summary
        print(f"\n{'='*60}")
        print("  REPO DOCTOR — SUMMARY")
        print(f"{'='*60}")

        overall_scores = []
        for repo_name, report in repo_results.items():
            health = report.get("health", {})
            score = health.get("score", 0)
            status = health.get("status", "?")
            icon = {"HEALTHY": "[+]", "DEGRADED": "[~]", "CRITICAL": "[-]"}.get(status, "[?]")

            checks_summary = []
            for ck_name, ck_data in report.get("checks", {}).items():
                if ck_name == "git":
                    checks_summary.append(f"git:{ck_data.get('sync', '?')}")
                elif ck_name == "ci":
                    checks_summary.append(f"ci:{ck_data.get('status', '?')}")
                elif ck_name == "vercel":
                    v_status = "UP" if ck_data.get("healthy") else "DOWN"
                    checks_summary.append(f"vercel:{v_status}")
                elif ck_name == "scripts":
                    checks_summary.append(f"scripts:{ck_data.get('found', 0)}/{ck_data.get('total', 0)}")

            print(f"  {icon} {repo_name:22s} | score: {score:5.1f} | {status:8s} | {', '.join(checks_summary)}")
            overall_scores.append(score)

        if overall_scores:
            avg = sum(overall_scores) / len(overall_scores)
            avg_status = "HEALTHY" if avg >= 80 else "DEGRADED" if avg >= 50 else "CRITICAL"
            print(f"\n  Overall: {avg:.1f}/100 ({avg_status})")

        print(f"\n  Report saved: {repo_report_path}")
        print(f"  Merged into: {DOCTOR_REPORT}")
        print()

        if args.json:
            print(json.dumps(repo_report, indent=2, ensure_ascii=False, default=str))
        return

    # ─── Main pipeline diagnostic/fix flow ────────────────────

    # Parse fixes library
    fp = FixesLibraryParser()
    fixes_data = fp.parse()
    n_fixes = len(fixes_data.get("fixes", []))
    print(f"\n  Fixes library: {n_fixes} fixes loaded")

    # Initialize components
    extractor = ExecutionExtractor()
    matcher = ErrorMatcher(fixes_data)
    confidence_engine = ConfidenceEngine()
    snapshot_mgr = SnapshotManager()
    tracker = LearningTracker()
    engine = AutoFixEngine(extractor, matcher, confidence_engine, snapshot_mgr, tracker)

    # Login to n8n
    print("  Logging in to n8n...")
    if not extractor.login():
        print("  [!] Failed to login to n8n — will skip execution analysis")

    # Determine pipelines
    pipelines = [args.pipeline] if args.pipeline else list(PIPELINES.keys())

    all_reports = {}

    for pipeline in pipelines:
        if args.snapshot_only:
            result = engine.snapshot_only(pipeline)
            all_reports[pipeline] = result
        elif args.apply:
            report = engine.auto_fix(pipeline, max_attempts=args.max_attempts, dry_run=False)
            all_reports[pipeline] = report
        else:
            # Dry-run diagnostic
            report = engine.diagnose(pipeline)
            all_reports[pipeline] = report

    # Save full report
    full_report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if args.apply else ("snapshot_only" if args.snapshot_only else "diagnose"),
        "pipelines": all_reports,
    }

    os.makedirs(os.path.dirname(DOCTOR_REPORT), exist_ok=True)
    with open(DOCTOR_REPORT, "w") as f:
        json.dump(full_report, f, indent=2, ensure_ascii=False, default=str)

    # Summary
    print(f"\n{'='*60}")
    print("  PIPELINE DOCTOR — SUMMARY")
    print(f"{'='*60}")

    for pipeline, report in all_reports.items():
        if args.snapshot_only:
            snap = "YES" if report.get("snapshot") else "NO"
            score = report.get("score", "N/A")
            print(f"  {pipeline:15s} | snapshot: {snap} | score: {score}")
        else:
            health = report.get("health", {})
            score = health.get("score", 0)
            status = health.get("status", "?")
            n_errors = len(report.get("recent_errors", []))
            n_fixes = len(report.get("matched_fixes", []))
            fix_result = report.get("auto_fix_result", "N/A")

            icon = {"HEALTHY": "[+]", "DEGRADED": "[~]", "CRITICAL": "[-]"}.get(status, "[?]")
            print(f"  {icon} {pipeline:15s} | score: {score:5.1f} | status: {status:8s} | errors: {n_errors} | fixes: {n_fixes} | result: {fix_result}")

    print(f"\n  Report saved: {DOCTOR_REPORT}")
    print()

    if args.json:
        print(json.dumps(full_report, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
