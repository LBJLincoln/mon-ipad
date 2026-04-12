#!/usr/bin/env python3
"""
NOMOS42 Research Digest Generator
Reads arxiv-scan-*.json and github-scan-*.json from last 7 days
Generates a weekly Markdown digest
"""

import json
import os
from pathlib import Path
import glob
from datetime import datetime, timedelta
from collections import Counter

_ROOT = Path(__file__).resolve().parent.parent.parent
RESEARCH_DIR = str(_ROOT / "data" / "research")
TODAY = datetime.utcnow().strftime("%Y-%m-%d")
WEEK_AGO = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")


def load_json_files(pattern):
    """Load all JSON files matching pattern from last 7 days."""
    files = sorted(glob.glob(os.path.join(RESEARCH_DIR, pattern)))
    results = []
    for f in files:
        # Extract date from filename (e.g., arxiv-scan-2026-03-31.json)
        basename = os.path.basename(f)
        try:
            # Find date pattern in filename
            parts = basename.replace(".json", "").split("-")
            # Date is the last 3 parts (YYYY-MM-DD)
            if len(parts) >= 3:
                file_date = "-".join(parts[-3:])
                if file_date >= WEEK_AGO:
                    try:
                        with open(f) as fh:
                            data = json.load(fh)
                            data["_source_file"] = basename
                            results.append(data)
                    except (json.JSONDecodeError, IOError):
                        continue
        except (ValueError, IndexError):
            continue
    return results


def extract_papers(scans):
    """Extract all unique papers from scan results."""
    seen_urls = set()
    papers = []
    for scan in scans:
        for paper in scan.get("papers", []):
            url = paper.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                papers.append(paper)
    return papers


def extract_repos(scans):
    """Extract all unique repos from scan results."""
    seen_names = set()
    repos = []
    for scan in scans:
        for repo in scan.get("repos", []):
            name = repo.get("name", "")
            if name and name not in seen_names:
                seen_names.add(name)
                repos.append(repo)
    return repos


def extract_topics(papers, repos):
    """Extract trending topics from papers and repos."""
    words = Counter()
    stopwords = {
        "the", "a", "an", "and", "or", "of", "in", "to", "for", "with",
        "on", "is", "are", "was", "were", "be", "been", "has", "have",
        "that", "this", "from", "by", "at", "as", "it", "we", "our",
        "can", "its", "not", "but", "which", "their", "more", "also",
        "than", "using", "based", "show", "results", "paper", "method",
        "approach", "proposed", "model", "data", "learning", "prediction",
    }

    for paper in papers:
        title_words = paper.get("title", "").lower().split()
        for w in title_words:
            w = w.strip(".,;:()[]{}\"'")
            if len(w) > 3 and w not in stopwords:
                words[w] += 1

    for repo in repos:
        for topic in repo.get("topics", []):
            words[topic] += 2  # Topics are more signal

    return words.most_common(15)


def generate_digest():
    """Generate the weekly research digest."""
    # Load all scan types
    arxiv_nba = load_json_files("arxiv-scan-*.json")
    arxiv_cal = load_json_files("arxiv-calibration-scan-*.json")
    github_nba = load_json_files("github-scan-*.json")
    github_bet = load_json_files("github-betting-scan-*.json")

    all_papers = extract_papers(arxiv_nba + arxiv_cal)
    all_repos = extract_repos(github_nba + github_bet)
    topics = extract_topics(all_papers, all_repos)

    # Separate breakthroughs
    breakthroughs = [p for p in all_papers if p.get("has_breakthrough_brier")]
    notable_repos = [r for r in all_repos if r.get("is_notable")]

    # Sort papers by date (newest first)
    all_papers.sort(key=lambda p: p.get("published", ""), reverse=True)

    # Sort repos by stars
    all_repos.sort(key=lambda r: r.get("stars", 0), reverse=True)

    # Count scan days
    scan_dates = set()
    for scan in arxiv_nba + arxiv_cal + github_nba + github_bet:
        scan_dates.add(scan.get("scan_date", ""))
    scan_dates.discard("")

    # Build Markdown
    lines = []
    lines.append(f"# Nomos42 Weekly Research Digest")
    lines.append(f"")
    lines.append(f"**Period:** {WEEK_AGO} to {TODAY}")
    lines.append(f"**Scans completed:** {len(scan_dates)} days")
    lines.append(f"**Papers found:** {len(all_papers)} | **Repos found:** {len(all_repos)}")
    lines.append(f"")

    # Breakthroughs section
    if breakthroughs:
        lines.append(f"## BREAKTHROUGHS (Brier < 0.20)")
        lines.append(f"")
        for p in breakthroughs:
            scores = ", ".join(f"{s:.4f}" for s in p.get("brier_scores", []) if s < 0.20)
            lines.append(f"### {p['title'][:100]}")
            lines.append(f"- **Brier scores:** {scores}")
            lines.append(f"- **Authors:** {', '.join(p.get('authors', [])[:3])}")
            lines.append(f"- **Published:** {p.get('published', 'N/A')[:10]}")
            lines.append(f"- **URL:** {p.get('url', 'N/A')}")
            lines.append(f"- **Summary:** {p.get('summary', 'N/A')[:300]}")
            lines.append(f"")
    else:
        lines.append(f"## Breakthroughs")
        lines.append(f"")
        lines.append(f"No papers with Brier < 0.20 detected this week.")
        lines.append(f"")

    # Top papers
    lines.append(f"## Top Papers")
    lines.append(f"")
    if all_papers:
        for i, p in enumerate(all_papers[:10], 1):
            authors = ", ".join(p.get("authors", [])[:2])
            if len(p.get("authors", [])) > 2:
                authors += " et al."
            lines.append(f"{i}. **{p['title'][:120]}**")
            lines.append(f"   - {authors} ({p.get('published', 'N/A')[:10]})")
            lines.append(f"   - {p.get('url', '')}")
            lines.append(f"")
    else:
        lines.append(f"No papers found this week.")
        lines.append(f"")

    # Notable repos
    lines.append(f"## Notable Repos")
    lines.append(f"")
    if notable_repos:
        for r in notable_repos:
            lines.append(f"- **[{r['name']}]({r['url']})** -- {r.get('stars', 0)} stars, {r.get('language', 'N/A')}")
            if r.get("description"):
                lines.append(f"  {r['description'][:150]}")
            lines.append(f"")
    else:
        lines.append(f"No notable repos (>50 stars, active this week) detected.")
        lines.append(f"")

    # All repos
    lines.append(f"## All Repos Tracked")
    lines.append(f"")
    if all_repos:
        lines.append(f"| Repo | Stars | Language | Active |")
        lines.append(f"|------|-------|----------|--------|")
        for r in all_repos[:20]:
            active = "Yes" if r.get("recently_active") else "No"
            lines.append(f"| [{r['name']}]({r['url']}) | {r.get('stars', 0)} | {r.get('language', '-')} | {active} |")
        lines.append(f"")
    else:
        lines.append(f"No repos found this week.")
        lines.append(f"")

    # Trending topics
    lines.append(f"## Trending Topics")
    lines.append(f"")
    if topics:
        for topic, count in topics:
            lines.append(f"- `{topic}` ({count})")
        lines.append(f"")
    else:
        lines.append(f"No trending topics detected.")
        lines.append(f"")

    # Our position
    lines.append(f"## Nomos42 Position")
    lines.append(f"")
    lines.append(f"- **Current ATR:** Brier 0.21570 (Colab TabICL, 110f)")
    lines.append(f"- **Published SOTA:** Brier 0.199 (Montrucchio 2026)")
    lines.append(f"- **Gap:** 0.0167")
    lines.append(f"- **Target:** Brier < 0.20, ROI > 5%, Sharpe > 1.5")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"*Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} by research-digest.py*")

    digest_text = "\n".join(lines)

    # Write digest
    digest_path = os.path.join(RESEARCH_DIR, f"weekly-digest-{TODAY}.md")
    with open(digest_path, "w") as f:
        f.write(digest_text)

    print(f"[DIGEST] Written to {digest_path}")
    print(f"[DIGEST] {len(all_papers)} papers, {len(all_repos)} repos, {len(breakthroughs)} breakthroughs")

    return digest_path


if __name__ == "__main__":
    generate_digest()
