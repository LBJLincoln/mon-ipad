#!/usr/bin/env python3
"""
Obsidian RAG Knowledge Vault — Compiler
========================================
Reads all .md files in raw/, groups by topic, generates wiki/ articles
with cross-references, and builds backlinks.json concept graph.

Based on Karpathy's LLM Knowledge Base pattern (March 2026):
  Stage 1: Raw Ingest (raw/)
  Stage 2: LLM Compilation (this script -> wiki/)
  Stage 3: Health Checks (lint.py)

Usage:
  python3 compile.py                  # Full compile (keyword extraction)
  python3 compile.py --claude         # Use Claude CLI for synthesis
  python3 compile.py --topic betting  # Compile single topic
  python3 compile.py --dry-run        # Show what would be generated
"""

import os
import re
import json
import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

VAULT_ROOT = Path(__file__).parent
RAW_DIR = VAULT_ROOT / "raw"
WIKI_DIR = VAULT_ROOT / "wiki"
BACKLINKS_FILE = VAULT_ROOT / "backlinks.json"

# ---------------------------------------------------------------------------
# Topic taxonomy: keyword patterns -> topic slug -> display name
# ---------------------------------------------------------------------------
TOPICS = {
    "nba-prediction": {
        "name": "NBA Prediction & ML Models",
        "wiki_dir": "concepts",
        "keywords": [
            r"\bbrier\b", r"\bnba\b", r"\bprediction\b", r"\bwin prob",
            r"\bgame outcome", r"\bmodel accuracy", r"\btree.?model",
            r"\bextra.?trees?\b", r"\bcatboost\b", r"\blightgbm\b",
            r"\bxgboost\b", r"\brandom forest", r"\btabicl\b", r"\btabpfn\b",
            r"\bensemble\b", r"\bstacking\b",
        ],
    },
    "calibration": {
        "name": "Calibration & Probability Scoring",
        "wiki_dir": "techniques",
        "keywords": [
            r"\bcalibration\b", r"\bplatt.?scal", r"\bisotonic",
            r"\bvenn.?abers?\b", r"\btemperature.?scal", r"\bece\b",
            r"\bmce\b", r"\breliability diagram", r"\boverconfiden",
            r"\bunderconfiden", r"\bprobability clip",
        ],
    },
    "feature-engineering": {
        "name": "Feature Engineering & Selection",
        "wiki_dir": "concepts",
        "keywords": [
            r"\bfeature.?engineer", r"\bfeature.?select", r"\bshap\b",
            r"\bpermutation import", r"\bshot.?chart", r"\bspatial",
            r"\bplayer.?level", r"\belo\b", r"\bmomentum\b",
            r"\brest.?day", r"\bfatigue\b", r"\bcat\d{2}\b",
            r"\bmax.?features?\b", r"\bengine\b.*v\d",
        ],
    },
    "evolution": {
        "name": "Genetic Algorithm & Evolution",
        "wiki_dir": "architectures",
        "keywords": [
            r"\bgenetic.?algo", r"\bevolution\b", r"\bmutation\b",
            r"\bcrossover\b", r"\bfitness\b", r"\bpopulation\b",
            r"\bisland\b", r"\bgeneration\b", r"\bpareto\b",
            r"\bdiversity\b", r"\belitism\b", r"\bmulti.?island",
            r"\bstagnation\b",
        ],
    },
    "betting-strategy": {
        "name": "Betting Strategy & Bankroll",
        "wiki_dir": "techniques",
        "keywords": [
            r"\bkelly\b", r"\bbankroll\b", r"\broi\b", r"\bsharpe\b",
            r"\bvalue.?bet", r"\bedge\b", r"\bodds\b", r"\bspread\b",
            r"\bover.?under", r"\bprop.?bet", r"\bmarket.?efficien",
            r"\bbookmaker", r"\bdraftking", r"\bfanduel", r"\bbet365",
            r"\bbetting.?market",
        ],
    },
    "political-alpha": {
        "name": "Political Alpha & Prediction Markets",
        "wiki_dir": "concepts",
        "keywords": [
            r"\bpolitical\b", r"\betf\b", r"\bindex fund", r"\bstock\b",
            r"\btrump\b", r"\binsider", r"\bsovereign", r"\bpolicy\b",
            r"\belection\b", r"\bpolymarket\b", r"\bprediction market",
            r"\bfec\b", r"\bsec\b",
        ],
    },
    "karpathy-patterns": {
        "name": "Karpathy Autoresearch & Agent Patterns",
        "wiki_dir": "architectures",
        "keywords": [
            r"\bkarpathy\b", r"\bautoresearch\b", r"\bvibe.?cod",
            r"\bagentic.?engineer", r"\bnanochat\b", r"\bllm.?council",
            r"\bobsidian\b", r"\bknowledge.?base", r"\bcompil.*wiki",
            r"\bprogram\.md\b", r"\btrain\.py\b",
        ],
    },
    "infrastructure": {
        "name": "Infrastructure & Compute",
        "wiki_dir": "architectures",
        "keywords": [
            r"\bhf.?space", r"\bhugging.?face", r"\bkaggle\b",
            r"\bcolab\b", r"\bgpu\b", r"\bmodal\b", r"\blightning\b",
            r"\bzerogpu\b", r"\bcron\b", r"\bvercel\b", r"\btailscale\b",
            r"\bdeploy\b", r"\bspace\b.*s1[0-5]",
        ],
    },
    "trading-floor": {
        "name": "Trading Floor & AI Competition",
        "wiki_dir": "architectures",
        "keywords": [
            r"\btrading.?floor", r"\btrader\b", r"\bgemini\b.*trad",
            r"\bgrok\b.*trad", r"\bcodex\b.*trad", r"\bopenrouter\b.*trad",
            r"\bclaude\b.*trad", r"\barena\b", r"\bconfrontation\b",
            r"\bseason\b.*\d{4}", r"\bstrateg.*bet",
        ],
    },
    "data-sources": {
        "name": "Data Sources & APIs",
        "wiki_dir": "concepts",
        "keywords": [
            r"\bnba.?api\b", r"\bthe.?odds.?api\b", r"\barxiv\b",
            r"\bgithub.?scan", r"\bsupabase\b", r"\bdata.?source",
            r"\bscraping\b", r"\bfirecrawl\b", r"\bweb.?clip",
            r"\bplay.?by.?play\b", r"\bbox.?score",
        ],
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_md_file(path: Path) -> str:
    """Read a markdown file, resolving symlinks."""
    real = path.resolve()
    if not real.exists():
        return ""
    try:
        return real.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def extract_title(content: str) -> str:
    """Extract first H1 or H2 heading as title."""
    for line in content.split("\n"):
        m = re.match(r"^#{1,2}\s+(.+)", line)
        if m:
            return m.group(1).strip()
    return ""


def extract_frontmatter(content: str) -> dict:
    """Extract YAML-like frontmatter between --- delimiters."""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = {}
    for line in parts[1].strip().split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


def score_topic(content: str, keywords: list[str]) -> int:
    """Count how many keyword patterns match in content (case-insensitive)."""
    text_lower = content.lower()
    score = 0
    for kw in keywords:
        matches = re.findall(kw, text_lower)
        score += len(matches)
    return score


def classify_file(content: str) -> list[tuple[str, int]]:
    """Return list of (topic_slug, score) sorted by score descending."""
    scores = []
    for slug, info in TOPICS.items():
        s = score_topic(content, info["keywords"])
        if s > 0:
            scores.append((slug, s))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def extract_concepts(content: str) -> list[str]:
    """Extract key concepts mentioned in content using topic keywords."""
    found = set()
    text_lower = content.lower()
    # Map specific terms to concept names
    concept_patterns = {
        "Brier Score": [r"\bbrier\b"],
        "Calibration": [r"\bcalibration\b", r"\bcalibrat"],
        "Feature Engineering": [r"\bfeature.?engineer"],
        "Feature Selection": [r"\bfeature.?select", r"\bmax.?features?\b"],
        "Genetic Algorithm": [r"\bgenetic.?algo", r"\bga\b.*evolut"],
        "Kelly Criterion": [r"\bkelly\b"],
        "Tree Models": [r"\bextra.?trees?\b", r"\bcatboost\b", r"\blightgbm\b", r"\bxgboost\b"],
        "Ensemble Methods": [r"\bensemble\b", r"\bstacking\b"],
        "Platt Scaling": [r"\bplatt.?scal"],
        "Isotonic Regression": [r"\bisotonic"],
        "Venn-ABERS": [r"\bvenn.?abers?\b"],
        "Temperature Scaling": [r"\btemperature.?scal"],
        "SHAP": [r"\bshap\b"],
        "Elo Rating": [r"\belo\b.*rating", r"\belo\b.*inject"],
        "Mutation Operators": [r"\bmutation\b.*rate", r"\bmutation\b.*cap"],
        "Crossover": [r"\bcrossover\b"],
        "Multi-Island Evolution": [r"\bmulti.?island", r"\bisland\b.*evolut"],
        "Karpathy Loop": [r"\bkarpathy\b.*loop", r"\bautoresearch\b"],
        "LLM Council": [r"\bllm.?council"],
        "Trading Floor": [r"\btrading.?floor"],
        "Political Alpha": [r"\bpolitical.?alpha"],
        "Value Betting": [r"\bvalue.?bet"],
        "Shot Chart": [r"\bshot.?chart"],
        "TabICL": [r"\btabicl\b"],
        "Walk-Forward": [r"\bwalk.?forward"],
        "Bankroll Management": [r"\bbankroll\b"],
        "HF Spaces": [r"\bhf.?space", r"\bhugging.?face.*space"],
    }
    for concept, patterns in concept_patterns.items():
        for p in patterns:
            if re.search(p, text_lower):
                found.add(concept)
                break
    return sorted(found)


def md5_content(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------

def collect_raw_files() -> list[dict]:
    """Collect all raw markdown files with metadata."""
    files = []
    for md_path in sorted(RAW_DIR.rglob("*.md")):
        content = read_md_file(md_path)
        if not content or len(content) < 50:
            continue
        rel = md_path.relative_to(RAW_DIR)
        fm = extract_frontmatter(content)
        title = fm.get("name", "") or fm.get("description", "") or extract_title(content)
        topics = classify_file(content)
        concepts = extract_concepts(content)

        files.append({
            "path": str(rel),
            "abs_path": str(md_path.resolve()),
            "title": title or str(rel.stem),
            "frontmatter": fm,
            "topics": topics,
            "primary_topic": topics[0][0] if topics else "uncategorized",
            "concepts": concepts,
            "word_count": len(content.split()),
            "content_hash": md5_content(content),
            "content": content,
        })
    return files


def group_by_topic(files: list[dict]) -> dict[str, list[dict]]:
    """Group files by their primary topic. Files can appear in secondary topics too."""
    groups = defaultdict(list)
    for f in files:
        # Add to primary topic
        groups[f["primary_topic"]].append(f)
        # Also add to secondary topics (score > 3)
        for slug, score in f["topics"][1:]:
            if score >= 3:
                groups[slug].append(f)
    return dict(groups)


def synthesize_topic_article(topic_slug: str, topic_info: dict, files: list[dict], use_claude: bool = False) -> str:
    """Generate a wiki article for a topic from its raw files."""

    if use_claude:
        return _synthesize_with_claude(topic_slug, topic_info, files)

    # Keyword-based synthesis (no LLM needed)
    name = topic_info["name"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Collect all unique concepts across files
    all_concepts = set()
    for f in files:
        all_concepts.update(f["concepts"])

    # Build article
    lines = [
        f"# {name}",
        "",
        f"> Auto-compiled from {len(files)} raw sources on {now}",
        "",
        "## Overview",
        "",
    ]

    # Generate overview from file titles
    lines.append(f"This topic covers {len(files)} research files spanning {name.lower()}.")
    if all_concepts:
        lines.append(f"Key concepts: {', '.join(sorted(all_concepts)[:15])}.")
    lines.append("")

    # Source summary
    lines.append("## Sources")
    lines.append("")
    for f in sorted(files, key=lambda x: x["word_count"], reverse=True):
        title = f["title"][:80]
        wc = f["word_count"]
        path = f["path"]
        lines.append(f"- **{title}** ({wc} words) -- `raw/{path}`")
    lines.append("")

    # Key findings — extract headings from raw files
    lines.append("## Key Findings")
    lines.append("")
    seen_headings = set()
    for f in files:
        for line in f["content"].split("\n"):
            m = re.match(r"^#{2,3}\s+(.+)", line)
            if m:
                heading = m.group(1).strip()
                if heading.lower() not in seen_headings and len(heading) > 5:
                    seen_headings.add(heading.lower())
                    lines.append(f"- {heading} (from `{f['path']}`)")
                    if len(seen_headings) >= 20:
                        break
        if len(seen_headings) >= 20:
            break
    lines.append("")

    # Cross-references
    related_topics = set()
    for f in files:
        for slug, score in f["topics"]:
            if slug != topic_slug and score >= 2:
                related_topics.add(slug)

    if related_topics:
        lines.append("## Related Topics")
        lines.append("")
        for slug in sorted(related_topics):
            if slug in TOPICS:
                wiki_dir = TOPICS[slug]["wiki_dir"]
                lines.append(f"- [[{TOPICS[slug]['name']}]] -- `wiki/{wiki_dir}/{slug}.md`")
        lines.append("")

    # Concept index
    if all_concepts:
        lines.append("## Concepts Index")
        lines.append("")
        for c in sorted(all_concepts):
            lines.append(f"- [[{c}]]")
        lines.append("")

    return "\n".join(lines)


def _synthesize_with_claude(topic_slug: str, topic_info: dict, files: list[dict]) -> str:
    """Use Claude CLI to synthesize a wiki article."""
    # Build context from raw files (truncate each to ~500 words to fit in prompt)
    context_parts = []
    for f in files[:10]:  # Max 10 files per topic
        truncated = " ".join(f["content"].split()[:500])
        context_parts.append(f"### Source: {f['title']}\n{truncated}\n")
    context = "\n---\n".join(context_parts)

    prompt = f"""You are a technical wiki compiler for an NBA prediction AI project (Nomos42).

Synthesize the following {len(files)} research sources into a single wiki article for the topic: "{topic_info['name']}".

Rules:
- Write 300-800 words of synthesized knowledge
- Use Markdown with ## headings
- Include [[backlinks]] to related concepts (double-bracket notation)
- Start with a 1-sentence TL;DR
- Focus on actionable knowledge for NBA prediction improvement
- NO hallucination: only synthesize what the sources contain
- End with a "## Sources" section listing the raw files

Sources:
{context}

Write the wiki article now:"""

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0 and len(result.stdout.strip()) > 100:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fall back to keyword synthesis
    return synthesize_topic_article(topic_slug, topic_info, files, use_claude=False)


def build_backlinks(files: list[dict], topic_groups: dict) -> dict:
    """Build backlinks.json — concept graph for agent navigation."""
    graph = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total_raw_files": len(files),
            "total_topics": len(topic_groups),
            "total_concepts": 0,
        },
        "topics": {},
        "concepts": {},
        "files": {},
    }

    # Topic -> files mapping
    for slug, group_files in topic_groups.items():
        if slug not in TOPICS:
            continue
        info = TOPICS[slug]
        graph["topics"][slug] = {
            "name": info["name"],
            "wiki_path": f"wiki/{info['wiki_dir']}/{slug}.md",
            "file_count": len(group_files),
            "files": [f["path"] for f in group_files],
        }

    # Concept -> files + topics mapping
    concept_map = defaultdict(lambda: {"files": [], "topics": set()})
    for f in files:
        for c in f["concepts"]:
            concept_map[c]["files"].append(f["path"])
            concept_map[c]["topics"].add(f["primary_topic"])

    for concept, data in concept_map.items():
        graph["concepts"][concept] = {
            "files": sorted(set(data["files"])),
            "topics": sorted(data["topics"]),
            "mention_count": len(data["files"]),
        }

    graph["stats"]["total_concepts"] = len(concept_map)

    # File -> topics + concepts mapping
    for f in files:
        graph["files"][f["path"]] = {
            "title": f["title"],
            "primary_topic": f["primary_topic"],
            "all_topics": [t[0] for t in f["topics"][:3]],
            "concepts": f["concepts"],
            "word_count": f["word_count"],
        }

    return graph


def generate_index(topic_groups: dict, files: list[dict], backlinks: dict) -> str:
    """Generate wiki/index.md — table of contents and knowledge state overview."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    stats = backlinks["stats"]

    lines = [
        "# Nomos42 Research Vault — Knowledge Index",
        "",
        f"> Last compiled: {now}",
        f"> Raw sources: {stats['total_raw_files']} files | "
        f"Topics: {stats['total_topics']} | "
        f"Concepts: {stats['total_concepts']}",
        "",
        "## How to Use This Vault",
        "",
        "This is a Markdown-first knowledge base (Karpathy LLM KB pattern).",
        "- **raw/** contains unprocessed research materials (symlinked from agent memory + data/)",
        "- **wiki/** contains synthesized articles grouped by topic",
        "- **backlinks.json** maps concepts to files for agent navigation",
        "- Run `python3 compile.py` to recompile after adding new raw materials",
        "- Run `python3 lint.py` to check for stale/orphaned content",
        "",
        "## Topic Articles",
        "",
    ]

    for slug in sorted(topic_groups.keys()):
        if slug not in TOPICS:
            continue
        info = TOPICS[slug]
        count = len(topic_groups[slug])
        wiki_dir = info["wiki_dir"]
        lines.append(f"### [[{info['name']}]]")
        lines.append(f"- Wiki: `wiki/{wiki_dir}/{slug}.md`")
        lines.append(f"- Sources: {count} raw files")
        lines.append("")

    # Top concepts by mention count
    lines.append("## Top Concepts (by mention frequency)")
    lines.append("")
    concept_items = sorted(
        backlinks["concepts"].items(),
        key=lambda x: x[1]["mention_count"],
        reverse=True,
    )
    for concept, data in concept_items[:25]:
        topics_str = ", ".join(data["topics"][:3])
        lines.append(f"- **[[{concept}]]** -- {data['mention_count']} mentions across {topics_str}")
    lines.append("")

    # Raw file inventory
    lines.append("## Raw Source Inventory")
    lines.append("")
    lines.append(f"| Source Directory | Files | Total Words |")
    lines.append(f"|-----------------|-------|-------------|")
    dir_stats = defaultdict(lambda: {"count": 0, "words": 0})
    for f in files:
        d = str(Path(f["path"]).parts[0]) if "/" in f["path"] else "root"
        dir_stats[d]["count"] += 1
        dir_stats[d]["words"] += f["word_count"]
    for d, s in sorted(dir_stats.items()):
        lines.append(f"| `raw/{d}/` | {s['count']} | {s['words']:,} |")
    lines.append("")

    lines.append("---")
    lines.append(f"*Generated by compile.py on {now}*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Compile research vault raw/ -> wiki/")
    parser.add_argument("--claude", action="store_true", help="Use Claude CLI for synthesis")
    parser.add_argument("--topic", type=str, help="Compile single topic (slug)")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without writing")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    print(f"[compile] Scanning {RAW_DIR} for raw materials...")
    files = collect_raw_files()
    print(f"[compile] Found {len(files)} raw files")

    if not files:
        print("[compile] No raw files found. Add .md files to raw/ and re-run.")
        sys.exit(1)

    # Group by topic
    topic_groups = group_by_topic(files)
    print(f"[compile] Classified into {len(topic_groups)} topics:")
    for slug, group in sorted(topic_groups.items()):
        name = TOPICS.get(slug, {}).get("name", slug)
        print(f"  - {name}: {len(group)} files")

    if args.dry_run:
        print("\n[dry-run] Would generate these wiki articles:")
        for slug in sorted(topic_groups.keys()):
            if slug in TOPICS:
                info = TOPICS[slug]
                print(f"  wiki/{info['wiki_dir']}/{slug}.md")
        print(f"  wiki/index.md")
        print(f"  backlinks.json")
        return

    # Filter to single topic if requested
    if args.topic:
        if args.topic not in topic_groups:
            print(f"[error] Topic '{args.topic}' not found. Available: {list(topic_groups.keys())}")
            sys.exit(1)
        topic_groups = {args.topic: topic_groups[args.topic]}

    # Ensure wiki subdirs exist
    for subdir in ["concepts", "techniques", "architectures", "learnings"]:
        (WIKI_DIR / subdir).mkdir(parents=True, exist_ok=True)

    # Compile each topic
    for slug, group_files in sorted(topic_groups.items()):
        if slug not in TOPICS:
            continue
        info = TOPICS[slug]
        wiki_dir = info["wiki_dir"]
        out_path = WIKI_DIR / wiki_dir / f"{slug}.md"

        print(f"[compile] Generating {out_path.relative_to(VAULT_ROOT)}...")
        article = synthesize_topic_article(slug, info, group_files, use_claude=args.claude)
        out_path.write_text(article, encoding="utf-8")

        if args.verbose:
            print(f"  -> {len(article)} chars, {len(group_files)} sources")

    # Build backlinks
    print(f"[compile] Building backlinks.json...")
    backlinks = build_backlinks(files, topic_groups)
    BACKLINKS_FILE.write_text(json.dumps(backlinks, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  -> {backlinks['stats']['total_concepts']} concepts, "
          f"{backlinks['stats']['total_topics']} topics")

    # Generate index
    print(f"[compile] Generating wiki/index.md...")
    index_content = generate_index(topic_groups, files, backlinks)
    (WIKI_DIR / "index.md").write_text(index_content, encoding="utf-8")

    print(f"\n[compile] Done. Wiki articles in {WIKI_DIR.relative_to(VAULT_ROOT)}/")
    print(f"  Total: {len(topic_groups)} topic articles + index + backlinks.json")


if __name__ == "__main__":
    main()
