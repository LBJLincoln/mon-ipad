#!/usr/bin/env python3
"""
Obsidian Knowledge Vault — Ingest Pipeline
============================================
Collects knowledge from ALL sources into raw/ for compile.py to process.

Sources:
  1. Agent memory files (.claude/agent-memory/**/*.md)
  2. Research scan results (data/research/*.json → markdown)
  3. Experiment reports (data/experiments/*.md)
  4. Scientific results (data/scientific-results/*.md)
  5. Arena docs (data/arena/docs/*.md)
  6. Karpathy history (data/karpathy/*.json → markdown)
  7. Department council outputs (data/departments/*.json → markdown)
  8. Weekly research digests (data/research/weekly-digest*.md)

Pattern: Karpathy's LLM Knowledge Base (March 2026)
  - Stage 1: THIS SCRIPT populates raw/
  - Stage 2: compile.py reads raw/ → writes wiki/
  - Stage 3: lint.py checks health

Usage:
  python3 ingest.py              # Full ingest from all sources
  python3 ingest.py --source research  # Single source
  python3 ingest.py --stats      # Show source stats
"""

import json
import os
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

VAULT_ROOT = Path(__file__).parent
RAW_DIR = VAULT_ROOT / "raw"
ROOT = Path("/home/termius/mon-ipad")
POL_ROOT = Path("/home/termius/nomos-political-alpha")


def ensure_dirs():
    """Create raw/ subdirectories for each source."""
    for subdir in [
        "agent-memory", "research", "experiments", "scientific",
        "arena-docs", "karpathy", "councils", "political",
    ]:
        (RAW_DIR / subdir).mkdir(parents=True, exist_ok=True)


def ingest_agent_memory():
    """Ingest agent memory files from .claude/agent-memory/."""
    count = 0
    memory_root = ROOT / ".claude" / "agent-memory"
    if not memory_root.exists():
        return count

    for md_file in memory_root.rglob("*.md"):
        if md_file.name == "MEMORY.md":
            continue
        content = md_file.read_text(errors="replace")
        if len(content) < 50:
            continue

        # Write to raw/ with agent prefix
        agent_name = md_file.parent.name
        out_name = f"{agent_name}_{md_file.stem}.md"
        out_path = RAW_DIR / "agent-memory" / out_name
        out_path.write_text(content)
        count += 1

    return count


def ingest_research_scans():
    """Convert research JSON scans to markdown."""
    count = 0
    research_dir = ROOT / "data" / "research"
    if not research_dir.exists():
        return count

    for json_file in research_dir.glob("*.json"):
        try:
            data = json.loads(json_file.read_text())
        except:
            continue

        md_lines = [f"# Research Scan: {json_file.stem}\n"]

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    md_lines.append(f"\n## {key}\n")
                    for item in value[:20]:  # Cap at 20 items
                        if isinstance(item, dict):
                            name = item.get("name", item.get("title", item.get("repo", "?")))
                            desc = item.get("description", item.get("summary", ""))
                            url = item.get("url", item.get("html_url", ""))
                            md_lines.append(f"- **{name}**: {desc[:200]}")
                            if url:
                                md_lines.append(f"  - URL: {url}")
                        elif isinstance(item, str):
                            md_lines.append(f"- {item[:200]}")
                elif isinstance(value, str):
                    md_lines.append(f"\n## {key}\n{value[:500]}\n")

        content = "\n".join(md_lines)
        if len(content) > 100:
            out_path = RAW_DIR / "research" / f"{json_file.stem}.md"
            out_path.write_text(content)
            count += 1

    # Also copy markdown digests directly
    for md_file in research_dir.glob("*.md"):
        content = md_file.read_text(errors="replace")
        if len(content) > 100:
            out_path = RAW_DIR / "research" / md_file.name
            out_path.write_text(content)
            count += 1

    return count


def ingest_experiments():
    """Copy experiment reports."""
    count = 0
    for exp_dir in [ROOT / "data" / "experiments", ROOT / "data" / "scientific-results"]:
        if not exp_dir.exists():
            continue
        subdir = "experiments" if "experiment" in str(exp_dir) else "scientific"
        for md_file in exp_dir.glob("*.md"):
            content = md_file.read_text(errors="replace")
            if len(content) > 100:
                out_path = RAW_DIR / subdir / md_file.name
                out_path.write_text(content)
                count += 1

    return count


def ingest_arena_docs():
    """Copy arena season documentation."""
    count = 0
    docs_dir = ROOT / "data" / "arena" / "docs"
    if not docs_dir.exists():
        return count

    for md_file in docs_dir.glob("*.md"):
        content = md_file.read_text(errors="replace")
        if len(content) > 100:
            out_path = RAW_DIR / "arena-docs" / md_file.name
            out_path.write_text(content)
            count += 1

    return count


def ingest_karpathy():
    """Convert Karpathy loop history to knowledge articles."""
    count = 0
    karp_dir = ROOT / "data" / "karpathy"
    if not karp_dir.exists():
        return count

    for json_file in karp_dir.glob("*.json"):
        try:
            data = json.loads(json_file.read_text())
        except:
            continue

        md_lines = [f"# Karpathy Loop: {json_file.stem}\n"]

        if isinstance(data, dict):
            if "best_brier" in data or "best" in data:
                md_lines.append(f"- Best Brier: {data.get('best_brier', data.get('best', '?'))}")
            if "iterations" in data or "history" in data:
                history = data.get("history", data.get("iterations", []))
                if isinstance(history, list) and history:
                    md_lines.append(f"- Total iterations: {len(history)}")
                    # Last 5 iterations
                    md_lines.append("\n## Recent Iterations\n")
                    for entry in history[-5:]:
                        if isinstance(entry, dict):
                            ts = entry.get("timestamp", entry.get("time", "?"))
                            brier = entry.get("brier", entry.get("best_brier", "?"))
                            action = entry.get("action", entry.get("change", "?"))
                            md_lines.append(f"- [{ts}] Brier={brier}, Action: {action}")
            for key in ["config", "params", "best_config"]:
                if key in data and isinstance(data[key], dict):
                    md_lines.append(f"\n## {key}\n```json\n{json.dumps(data[key], indent=2)[:500]}\n```")

        content = "\n".join(md_lines)
        if len(content) > 100:
            out_path = RAW_DIR / "karpathy" / f"{json_file.stem}.md"
            out_path.write_text(content)
            count += 1

    return count


def ingest_councils():
    """Convert council outputs to knowledge."""
    count = 0
    dept_dir = ROOT / "data" / "departments"
    if not dept_dir.exists():
        return count

    for json_file in dept_dir.glob("council-*.json"):
        try:
            data = json.loads(json_file.read_text())
        except:
            continue

        dept = data.get("department", json_file.stem)
        status = data.get("status", "?")
        ts = data.get("timestamp", "?")
        model = data.get("model", "?")
        duration = data.get("duration_seconds", "?")

        md = f"""# Council: {dept}
- Status: {status}
- Timestamp: {ts}
- Model: {model}
- Duration: {duration}s
"""
        out_path = RAW_DIR / "councils" / f"{json_file.stem}.md"
        out_path.write_text(md)
        count += 1

    return count


def ingest_political():
    """Ingest political alpha knowledge."""
    count = 0
    if not POL_ROOT.exists():
        return count

    # Scientific results
    sci_dir = POL_ROOT / "data" / "scientific-results"
    if sci_dir.exists():
        for md_file in sci_dir.glob("*.md"):
            content = md_file.read_text(errors="replace")
            if len(content) > 100:
                out_path = RAW_DIR / "political" / md_file.name
                out_path.write_text(content)
                count += 1

    # Arena results summary
    arena_file = POL_ROOT / "data" / "arena" / "arena-results.json"
    if arena_file.exists():
        try:
            data = json.loads(arena_file.read_text())
            meta = data.get("meta", {})
            lb = data.get("leaderboard", [])[:10]

            md = f"""# Political Alpha Arena Results
- Rounds: {meta.get('rounds', '?')}
- Signals simulated: {meta.get('signals_simulated', '?')}
- Model Brier: {meta.get('model_brier', '?')}

## Top 10 Strategies
"""
            for s in lb:
                md += f"- **{s.get('name', '?')}**: ROI {s.get('roi_pct', 0):.1f}%, Sharpe {s.get('sharpe', 0):.4f}, WR {s.get('win_rate', 0):.1%}\n"

            out_path = RAW_DIR / "political" / "arena-results-summary.md"
            out_path.write_text(md)
            count += 1
        except:
            pass

    return count


def show_stats():
    """Show current vault statistics."""
    total = 0
    for subdir in RAW_DIR.iterdir():
        if subdir.is_dir():
            files = list(subdir.glob("*.md"))
            total += len(files)
            total_size = sum(f.stat().st_size for f in files)
            print(f"  {subdir.name:20s}: {len(files):3d} files, {total_size/1024:.1f} KB")

    wiki_files = list((VAULT_ROOT / "wiki").rglob("*.md"))
    print(f"\n  {'wiki (compiled)':20s}: {len(wiki_files):3d} articles")
    print(f"  {'TOTAL raw':20s}: {total:3d} files")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Obsidian Vault Ingest")
    parser.add_argument("--source", help="Single source to ingest")
    parser.add_argument("--stats", action="store_true", help="Show stats only")
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    print("═══════════════════════════════════════════════════")
    print(" OBSIDIAN KNOWLEDGE VAULT — INGEST PIPELINE")
    print("═══════════════════════════════════════════════════")
    print(f" {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    ensure_dirs()

    sources = {
        "agent-memory": ingest_agent_memory,
        "research": ingest_research_scans,
        "experiments": ingest_experiments,
        "arena-docs": ingest_arena_docs,
        "karpathy": ingest_karpathy,
        "councils": ingest_councils,
        "political": ingest_political,
    }

    total = 0
    for name, func in sources.items():
        if args.source and args.source != name:
            continue
        count = func()
        total += count
        print(f"  ✓ {name:20s}: {count} files ingested")

    print(f"\n  TOTAL: {total} raw files ingested")
    print()
    show_stats()

    print("\n  Next: python3 research-vault/compile.py")
    print("═══════════════════════════════════════════════════")


if __name__ == "__main__":
    main()
