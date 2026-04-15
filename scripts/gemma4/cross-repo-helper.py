#!/usr/bin/env python3
"""
Cross-Repo Helper — Self-host Phi-3.5 (T12 "gemma4-selfhost")
==============================================================
Inspects a checked-out Nomos42 repo (git log + 2 recent files) and asks the
self-hosted Phi-3.5 Space (Nomos42/nomos42-llm-cpu, proxied via llm-gateway)
for ONE concrete improvement suggestion.

Model: selfhost:phi-3.5 (CPU GGUF, ~5-8s/call, no quota)
Role : suggestion-only, low-stakes, never auto-merge

Usage:
  python3 cross-repo-helper.py --repo <path> --name <repo-name> --out <mon-ipad>

Limits:
  - max 3 suggestions per orchestrator run (enforced by caller via env var
    GEMMA4_MAX_SUGGESTIONS — default 3)
  - reads up to 2 recently-modified files
  - truncates file content to 6000 chars each to respect Phi-3.5 context
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ── CONFIG ────────────────────────────────────────────────────────────────
# Primary: direct call to the self-host Space (already OpenAI-compatible).
# The llm-gateway (LBJLincoln26/llm-gateway) proxies the same endpoint for
# fallbacks — we use direct here because this task is low-stakes.
SELFHOST_URL = os.environ.get(
    "SELFHOST_LLM_URL",
    "https://nomos42-nomos42-llm-cpu.hf.space/chat/completions",
)
SELFHOST_MODEL = os.environ.get("SELFHOST_LLM_MODEL", "phi-3.5-mini")
SELFHOST_TOKEN = os.environ.get("NOMOS_HF_TOKEN", "") or os.environ.get("HF_TOKEN_3", "")
REQUEST_TIMEOUT = int(os.environ.get("SELFHOST_TIMEOUT", "90"))

MAX_FILES = 2
MAX_FILE_CHARS = 6000
MAX_SUGGESTION_TOKENS = 350


def _git(args: list[str], cwd: Path) -> str:
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return r.stdout.strip()
    except Exception as exc:  # pragma: no cover
        return f"[git error: {exc}]"


def recent_commits(repo: Path, n: int = 20) -> str:
    out = _git(["log", "--oneline", f"-{n}"], repo)
    return out or "[no commits]"


def recent_files(repo: Path, limit: int = MAX_FILES) -> list[Path]:
    """Files touched by the most recent N commits, de-duped, existing only."""
    raw = _git(
        ["log", "--name-only", "--pretty=format:", "-10"],
        repo,
    )
    seen: list[Path] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        p = repo / line
        # skip huge / binary / vendored / lockfiles
        low = line.lower()
        if any(
            low.endswith(ext)
            for ext in (".lock", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".whl")
        ):
            continue
        if "/node_modules/" in line or "/vendor/" in line or "/__pycache__/" in line:
            continue
        if not p.is_file():
            continue
        if p in seen:
            continue
        seen.append(p)
        if len(seen) >= limit:
            break
    return seen


def read_trimmed(path: Path, max_chars: int = MAX_FILE_CHARS) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"[read error: {exc}]"
    if len(text) > max_chars:
        head = text[: max_chars // 2]
        tail = text[-max_chars // 2 :]
        return f"{head}\n... [TRUNCATED {len(text) - max_chars} chars] ...\n{tail}"
    return text


def build_prompt(repo_name: str, commits: str, files: list[Path], repo_root: Path) -> list[dict]:
    file_blob = []
    for f in files:
        rel = f.relative_to(repo_root)
        file_blob.append(f"### {rel}\n```\n{read_trimmed(f)}\n```")
    files_section = "\n\n".join(file_blob) if file_blob else "[no recent files captured]"

    system = (
        "You are a senior code reviewer helping the Nomos42 NBA-quant org. "
        "You look at a repo snapshot and propose ONE concrete, small improvement. "
        "Be terse, specific, and actionable. Suggestion-only — no auto-merge. "
        "Output format:\n"
        "  TITLE: <under 70 chars>\n"
        "  WHY: <1-2 sentences>\n"
        "  WHAT: <bullet list, 2-5 items, each < 120 chars>\n"
        "  RISK: <low|med|high> — <one-line justification>\n"
        "Avoid essays. No intro / outro."
    )
    user = (
        f"Repo: {repo_name}\n\n"
        f"Recent commits (git log --oneline -20):\n{commits}\n\n"
        f"Recently-modified files (trimmed):\n{files_section}\n\n"
        "Give ONE improvement."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def call_selfhost(messages: list[dict]) -> tuple[str, dict]:
    headers = {"Content-Type": "application/json"}
    if SELFHOST_TOKEN:
        headers["Authorization"] = f"Bearer {SELFHOST_TOKEN}"
    payload = {
        "model": SELFHOST_MODEL,
        "messages": messages,
        "max_tokens": MAX_SUGGESTION_TOKENS,
        "temperature": 0.5,
    }
    t0 = time.time()
    resp = requests.post(SELFHOST_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    latency = time.time() - t0
    resp.raise_for_status()
    data = resp.json()
    if "choices" in data and data["choices"]:
        content = data["choices"][0]["message"]["content"]
    elif "content" in data:
        content = data["content"]
    else:
        content = f"[unexpected response: {json.dumps(data)[:200]}]"
    return content, {"latency_s": round(latency, 2), "model": SELFHOST_MODEL}


def write_suggestion(out_dir: Path, repo_name: str, suggestion: str, meta: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    date_tag = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = out_dir / f"{repo_name}-{date_tag}.md"
    header = (
        f"# Gemma4 Helper Suggestion — {repo_name}\n\n"
        f"- **Date (UTC):** {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n"
        f"- **Model:** {meta.get('model', SELFHOST_MODEL)} (self-host Phi-3.5 CPU)\n"
        f"- **Latency:** {meta.get('latency_s', '?')}s\n"
        f"- **Source:** {SELFHOST_URL}\n"
        f"- **Status:** suggestion-only — never auto-merge\n\n"
        "---\n\n"
    )
    path.write_text(header + suggestion.strip() + "\n", encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="Self-host Phi-3.5 cross-repo helper")
    ap.add_argument("--repo", required=True, help="Path to checked-out repo")
    ap.add_argument("--name", required=True, help="Repo short name (e.g. nomos-dashboard)")
    ap.add_argument(
        "--out",
        required=True,
        help="Output dir (typically mon-ipad/data/gemma4-helper)",
    )
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out_dir = Path(args.out).resolve()
    if not repo.is_dir():
        print(f"[skip] {args.name}: repo path missing → {repo}", file=sys.stderr)
        return 0  # soft-fail: the orchestrator continues with other repos

    commits = recent_commits(repo)
    files = recent_files(repo)
    messages = build_prompt(args.name, commits, files, repo)

    try:
        suggestion, meta = call_selfhost(messages)
    except Exception as exc:
        print(f"[llm-error] {args.name}: {exc}", file=sys.stderr)
        suggestion = (
            f"TITLE: helper offline\n"
            f"WHY: self-host Phi-3.5 call failed ({exc.__class__.__name__}).\n"
            f"WHAT:\n- retry next cycle\n- verify Space is awake\n"
            f"RISK: low — suggestion-only, no code touched"
        )
        meta = {"latency_s": 0, "model": SELFHOST_MODEL, "error": str(exc)[:200]}

    out_path = write_suggestion(out_dir, args.name, suggestion, meta)
    print(f"[ok] {args.name}: wrote {out_path} (latency={meta.get('latency_s')}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
