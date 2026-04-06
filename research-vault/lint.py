#!/usr/bin/env python3
"""
Obsidian RAG Knowledge Vault — Linter
=======================================
Detects health issues in the research vault:
  - Orphaned articles (no backlinks from other files)
  - Stale content (older than N days with no updates)
  - Broken [[wiki links]] (referenced but nonexistent)
  - Empty/tiny files (< 100 words)
  - Uncategorized raw files (no topic match)

Usage:
  python3 lint.py                  # Full lint report
  python3 lint.py --fix            # Auto-fix what's possible (add missing links to index)
  python3 lint.py --json           # Output as JSON (for agent consumption)
  python3 lint.py --stale-days 14  # Custom stale threshold (default: 30)
"""

import os
import re
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

VAULT_ROOT = Path(__file__).parent
RAW_DIR = VAULT_ROOT / "raw"
WIKI_DIR = VAULT_ROOT / "wiki"
BACKLINKS_FILE = VAULT_ROOT / "backlinks.json"

# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_orphaned_articles(wiki_files: list[Path], backlinks: dict) -> list[dict]:
    """Find wiki articles that no other article links to."""
    issues = []

    # Collect all [[links]] from all wiki files
    all_links = set()
    for wf in wiki_files:
        content = wf.read_text(encoding="utf-8", errors="replace")
        links = re.findall(r"\[\[([^\]]+)\]\]", content)
        all_links.update(links)

    # Check each wiki file (except index.md)
    for wf in wiki_files:
        if wf.name == "index.md":
            continue
        stem = wf.stem
        rel = str(wf.relative_to(WIKI_DIR))

        # Check if this file's title or stem appears in any [[link]]
        title_match = False
        for link in all_links:
            if stem.lower() in link.lower() or link.lower() in stem.lower():
                title_match = True
                break

        # Also check if it's referenced in backlinks.json topics
        referenced_in_backlinks = False
        for topic_data in backlinks.get("topics", {}).values():
            if rel in str(topic_data.get("wiki_path", "")):
                referenced_in_backlinks = True
                break

        if not title_match and not referenced_in_backlinks:
            issues.append({
                "type": "orphaned",
                "severity": "warning",
                "file": rel,
                "message": f"Wiki article '{rel}' has no incoming links from other articles",
            })

    return issues


def check_stale_content(stale_days: int = 30) -> list[dict]:
    """Find files not updated in stale_days."""
    issues = []
    threshold = datetime.now(timezone.utc) - timedelta(days=stale_days)

    for md_path in sorted(RAW_DIR.rglob("*.md")):
        real_path = md_path.resolve()
        if not real_path.exists():
            continue

        mtime = datetime.fromtimestamp(real_path.stat().st_mtime, tz=timezone.utc)
        if mtime < threshold:
            age_days = (datetime.now(timezone.utc) - mtime).days
            rel = str(md_path.relative_to(VAULT_ROOT))
            issues.append({
                "type": "stale",
                "severity": "info",
                "file": rel,
                "message": f"'{rel}' last modified {age_days} days ago (threshold: {stale_days}d)",
                "last_modified": mtime.isoformat(),
                "age_days": age_days,
            })

    return issues


def check_broken_links() -> list[dict]:
    """Find [[wiki links]] that point to nonexistent files."""
    issues = []

    # Collect all wiki file stems for matching
    wiki_stems = set()
    for wf in WIKI_DIR.rglob("*.md"):
        wiki_stems.add(wf.stem.lower())

    # Build a set of known topic display names (these are valid link targets)
    known_topic_names = set()
    if BACKLINKS_FILE.exists():
        backlinks = json.loads(BACKLINKS_FILE.read_text())
        for topic_data in backlinks.get("topics", {}).values():
            known_topic_names.add(topic_data.get("name", "").lower())
    else:
        backlinks = {}

    # Scan all wiki files for [[links]]
    for wf in sorted(WIKI_DIR.rglob("*.md")):
        content = wf.read_text(encoding="utf-8", errors="replace")
        links = re.findall(r"\[\[([^\]]+)\]\]", content)
        rel = str(wf.relative_to(VAULT_ROOT))

        for link in links:
            # Normalize: convert to potential stem
            link_lower = link.lower()
            link_stem = link_lower.replace(" ", "-")

            # Check 1: wiki file stem match (fuzzy)
            found = False
            for ws in wiki_stems:
                if link_stem in ws or ws in link_stem:
                    found = True
                    break

            # Check 2: topic display name match
            if not found and link_lower in known_topic_names:
                found = True

            # Check 3: concept name in backlinks.json
            if not found and link in backlinks.get("concepts", {}):
                found = True

            # Check 4: partial match on topic names (e.g., "Karpathy" in "Karpathy Autoresearch...")
            if not found:
                link_words = set(link_lower.split())
                for tn in known_topic_names:
                    tn_words = set(tn.split())
                    if len(link_words & tn_words) >= 2:
                        found = True
                        break

            if not found:
                issues.append({
                    "type": "broken_link",
                    "severity": "warning",
                    "file": rel,
                    "message": f"Broken link [[{link}]] in '{rel}' — no matching wiki article or concept",
                    "link": link,
                })

    return issues


def check_empty_files() -> list[dict]:
    """Find files with less than 100 words."""
    issues = []

    for md_path in sorted(RAW_DIR.rglob("*.md")):
        real_path = md_path.resolve()
        if not real_path.exists():
            issues.append({
                "type": "dead_symlink",
                "severity": "error",
                "file": str(md_path.relative_to(VAULT_ROOT)),
                "message": f"Dead symlink: '{md_path}' -> target does not exist",
            })
            continue

        content = real_path.read_text(encoding="utf-8", errors="replace")
        wc = len(content.split())
        if wc < 100:
            rel = str(md_path.relative_to(VAULT_ROOT))
            issues.append({
                "type": "tiny_file",
                "severity": "info",
                "file": rel,
                "message": f"'{rel}' has only {wc} words (threshold: 100)",
                "word_count": wc,
            })

    return issues


def check_uncategorized(backlinks: dict) -> list[dict]:
    """Find raw files that didn't match any topic."""
    issues = []

    all_categorized = set()
    for topic_data in backlinks.get("topics", {}).values():
        all_categorized.update(topic_data.get("files", []))

    for md_path in sorted(RAW_DIR.rglob("*.md")):
        real_path = md_path.resolve()
        if not real_path.exists():
            continue
        rel = str(md_path.relative_to(RAW_DIR))
        if rel not in all_categorized:
            issues.append({
                "type": "uncategorized",
                "severity": "info",
                "file": f"raw/{rel}",
                "message": f"'raw/{rel}' did not match any topic — consider adding keywords or new topic",
            })

    return issues


def check_backlinks_freshness() -> list[dict]:
    """Check if backlinks.json is stale relative to raw files."""
    issues = []

    if not BACKLINKS_FILE.exists():
        issues.append({
            "type": "missing_backlinks",
            "severity": "error",
            "file": "backlinks.json",
            "message": "backlinks.json does not exist — run compile.py first",
        })
        return issues

    bl_mtime = datetime.fromtimestamp(BACKLINKS_FILE.stat().st_mtime, tz=timezone.utc)

    # Check if any raw file is newer than backlinks.json
    newest_raw = None
    newest_raw_path = None
    for md_path in RAW_DIR.rglob("*.md"):
        real = md_path.resolve()
        if not real.exists():
            continue
        mtime = datetime.fromtimestamp(real.stat().st_mtime, tz=timezone.utc)
        if newest_raw is None or mtime > newest_raw:
            newest_raw = mtime
            newest_raw_path = str(md_path.relative_to(VAULT_ROOT))

    if newest_raw and newest_raw > bl_mtime:
        delta = (newest_raw - bl_mtime).total_seconds() / 3600
        issues.append({
            "type": "stale_backlinks",
            "severity": "warning",
            "file": "backlinks.json",
            "message": f"backlinks.json is {delta:.1f}h older than newest raw file ({newest_raw_path}). Re-run compile.py.",
        })

    return issues


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def format_report(all_issues: list[dict]) -> str:
    """Format issues into a readable Markdown report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    errors = [i for i in all_issues if i["severity"] == "error"]
    warnings = [i for i in all_issues if i["severity"] == "warning"]
    infos = [i for i in all_issues if i["severity"] == "info"]

    lines = [
        "# Research Vault Lint Report",
        "",
        f"> Generated: {now}",
        f"> Issues: {len(errors)} errors, {len(warnings)} warnings, {len(infos)} info",
        "",
    ]

    if not all_issues:
        lines.append("All clear. No issues found.")
        return "\n".join(lines)

    if errors:
        lines.append("## Errors")
        lines.append("")
        for i in errors:
            lines.append(f"- **{i['type']}**: {i['message']}")
        lines.append("")

    if warnings:
        lines.append("## Warnings")
        lines.append("")
        for i in warnings:
            lines.append(f"- **{i['type']}**: {i['message']}")
        lines.append("")

    if infos:
        lines.append("## Info")
        lines.append("")
        for i in infos:
            lines.append(f"- **{i['type']}**: {i['message']}")
        lines.append("")

    # Summary by type
    type_counts = defaultdict(int)
    for i in all_issues:
        type_counts[i["type"]] += 1

    lines.append("## Summary")
    lines.append("")
    lines.append("| Check | Count |")
    lines.append("|-------|-------|")
    for t, c in sorted(type_counts.items()):
        lines.append(f"| {t} | {c} |")
    lines.append("")

    lines.append("---")
    lines.append(f"*Run `python3 compile.py` to refresh wiki and backlinks.*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Lint the research vault for health issues")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--fix", action="store_true", help="Auto-fix where possible")
    parser.add_argument("--stale-days", type=int, default=30, help="Stale threshold in days (default: 30)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # When --json, send progress to stderr so stdout is clean JSON
    log = (lambda msg: print(msg, file=sys.stderr)) if args.json else print

    log(f"[lint] Scanning research vault at {VAULT_ROOT}...")

    # Load backlinks if available
    backlinks = {}
    if BACKLINKS_FILE.exists():
        backlinks = json.loads(BACKLINKS_FILE.read_text(encoding="utf-8"))

    # Collect wiki files
    wiki_files = list(WIKI_DIR.rglob("*.md"))

    # Run all checks
    all_issues = []

    log("[lint] Checking backlinks freshness...")
    all_issues.extend(check_backlinks_freshness())

    log("[lint] Checking for dead symlinks and tiny files...")
    all_issues.extend(check_empty_files())

    log(f"[lint] Checking for stale content (>{args.stale_days} days)...")
    all_issues.extend(check_stale_content(args.stale_days))

    if wiki_files:
        log("[lint] Checking for orphaned wiki articles...")
        all_issues.extend(check_orphaned_articles(wiki_files, backlinks))

        log("[lint] Checking for broken [[links]]...")
        all_issues.extend(check_broken_links())

    if backlinks:
        log("[lint] Checking for uncategorized raw files...")
        all_issues.extend(check_uncategorized(backlinks))

    # Output
    if args.json:
        output = {
            "generated": datetime.now(timezone.utc).isoformat(),
            "total_issues": len(all_issues),
            "errors": len([i for i in all_issues if i["severity"] == "error"]),
            "warnings": len([i for i in all_issues if i["severity"] == "warning"]),
            "info": len([i for i in all_issues if i["severity"] == "info"]),
            "issues": all_issues,
        }
        print(json.dumps(output, indent=2))
    else:
        report = format_report(all_issues)
        print(report)

    # Summary
    errors = len([i for i in all_issues if i["severity"] == "error"])
    warnings = len([i for i in all_issues if i["severity"] == "warning"])
    infos = len([i for i in all_issues if i["severity"] == "info"])
    log(f"\n[lint] Total: {errors} errors, {warnings} warnings, {infos} info")

    if errors > 0:
        sys.exit(1)
    return 0


if __name__ == "__main__":
    main()
