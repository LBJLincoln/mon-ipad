#!/usr/bin/env python3
"""
Nomos42 autoDream — Memory Consolidation
=========================================
Inspired by Claude Code's internal autoDream service.
Consolidates memory files, prunes stale entries, maintains MEMORY.md index.

Pattern:
  1. Orient — read current memory directory
  2. Gather signal — find new info from recent sessions/data
  3. Consolidate — merge, update, deduplicate
  4. Prune — remove stale, cap MEMORY.md at 200 lines / 25KB

Run: daily via cron (0 5 * * *)
"""

import os, json, re
from pathlib import Path
from datetime import datetime, timezone

MEMORY_DIR = Path('/home/termius/.claude/projects/-home-termius-mon-ipad/memory')
MEMORY_INDEX = MEMORY_DIR / 'MEMORY.md'
MAX_LINES = 200
MAX_BYTES = 25_000
LOCK_FILE = MEMORY_DIR / '.dream.lock'


def read_memory_index():
    """Read and parse MEMORY.md"""
    if not MEMORY_INDEX.exists():
        return '', []
    content = MEMORY_INDEX.read_text()
    lines = content.split('\n')
    return content, lines


def list_memory_files():
    """List all .md memory files (excluding MEMORY.md)"""
    files = []
    for f in MEMORY_DIR.glob('*.md'):
        if f.name == 'MEMORY.md':
            continue
        files.append(f)
    return sorted(files)


def parse_frontmatter(filepath):
    """Parse YAML-ish frontmatter from memory file"""
    content = filepath.read_text()
    if not content.startswith('---'):
        return {'name': filepath.stem, 'type': 'unknown', 'description': ''}, content

    parts = content.split('---', 2)
    if len(parts) < 3:
        return {'name': filepath.stem, 'type': 'unknown', 'description': ''}, content

    meta = {}
    for line in parts[1].strip().split('\n'):
        if ':' in line:
            key, val = line.split(':', 1)
            meta[key.strip()] = val.strip()

    return meta, parts[2].strip()


def check_stale_references(index_content, memory_files):
    """Find references in MEMORY.md that point to non-existent files"""
    file_names = {f.name for f in memory_files}
    stale = []

    for line in index_content.split('\n'):
        # Find markdown links like [Title](filename.md)
        matches = re.findall(r'\[.*?\]\(([\w\-_.]+\.md)\)', line)
        for ref in matches:
            if ref not in file_names:
                stale.append(ref)

    return stale


def check_index_health(content, lines):
    """Check MEMORY.md health"""
    issues = []
    byte_count = len(content.encode('utf-8'))
    line_count = len(lines)

    if line_count > MAX_LINES:
        issues.append(f'Over line limit: {line_count}/{MAX_LINES}')
    if byte_count > MAX_BYTES:
        issues.append(f'Over byte limit: {byte_count}/{MAX_BYTES}')

    # Check for long lines (>200 chars)
    long_lines = [(i+1, len(l)) for i, l in enumerate(lines) if len(l) > 200]
    if long_lines:
        issues.append(f'{len(long_lines)} lines over 200 chars')

    return {
        'line_count': line_count,
        'byte_count': byte_count,
        'long_lines': len(long_lines),
        'issues': issues,
    }


def consolidation_report():
    """Generate a consolidation report (non-destructive)"""
    content, lines = read_memory_index()
    memory_files = list_memory_files()
    health = check_index_health(content, lines)
    stale = check_stale_references(content, memory_files)

    # Find orphan files (not referenced in MEMORY.md)
    referenced = set()
    for line in lines:
        matches = re.findall(r'\[.*?\]\(([\w\-_.]+\.md)\)', line)
        referenced.update(matches)

    orphans = [f.name for f in memory_files if f.name not in referenced]

    # Categorize files by type
    by_type = {}
    for f in memory_files:
        meta, _ = parse_frontmatter(f)
        ftype = meta.get('type', 'unknown')
        by_type.setdefault(ftype, []).append(f.name)

    report = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'health': health,
        'total_files': len(memory_files),
        'by_type': {k: len(v) for k, v in by_type.items()},
        'stale_references': stale,
        'orphan_files': orphans,
        'action_needed': len(health['issues']) > 0 or len(stale) > 0 or len(orphans) > 0,
    }

    return report


def main():
    """Run autoDream consolidation check"""
    print('[autoDream] Starting memory consolidation check...')

    report = consolidation_report()

    print(f'[autoDream] Memory files: {report["total_files"]}')
    print(f'[autoDream] Index health: {report["health"]["line_count"]} lines, {report["health"]["byte_count"]} bytes')

    if report['health']['issues']:
        print(f'[autoDream] ISSUES: {", ".join(report["health"]["issues"])}')

    if report['stale_references']:
        print(f'[autoDream] STALE refs: {report["stale_references"]}')

    if report['orphan_files']:
        print(f'[autoDream] ORPHAN files: {report["orphan_files"]}')

    if not report['action_needed']:
        print('[autoDream] Memory is healthy. No action needed.')

    # Save report
    report_file = Path('/home/termius/mon-ipad/data/auto-dream-report.json')
    report_file.write_text(json.dumps(report, indent=2))
    print(f'[autoDream] Report saved to {report_file}')

    # Output JSON for guardian
    print(json.dumps(report))


if __name__ == '__main__':
    main()
