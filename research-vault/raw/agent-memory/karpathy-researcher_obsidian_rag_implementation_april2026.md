---
name: Obsidian RAG Pattern — Implementation Guide for NBA Quant
description: Karpathy's April 2026 LLM Knowledge Base architecture using Obsidian. Why it's not implemented yet, and how to deploy for Nomos42 research memory.
type: project
---

# Obsidian RAG Pattern — Why & How to Implement (April 2026)

**Research Date:** 2026-04-05  
**Status:** NOT YET IMPLEMENTED in Nomos42  
**Effort to Deploy:** 2-3 days (1-2 day core, rest: testing + agent iteration)  
**Expected Brier Impact:** +0.0005 to +0.002 (research velocity → better feature discovery)

---

## TLDR: What Is Obsidian RAG?

Karpathy released an LLM Knowledge Base architecture (March 2026) that replaces traditional RAG (vector databases, semantic search) with a **three-stage compilation pipeline** that turns raw research materials into a living, AI-maintained Markdown wiki.

**Why Not Traditional RAG?**
- Vector DBs are noisy (retrieve wrong papers, hallucinate connections)
- Scaling RAG past 1M tokens requires complex re-ranking
- Query latency adds overhead to agent loops

**Karpathy's Solution:**
- Stage 1: **Raw Ingest** — Dump papers, repos, web content into `raw/` folder as Markdown
- Stage 2: **LLM Compilation** — Agent reads raw files, writes structured wiki articles with backlinks
- Stage 3: **Active Maintenance** — LLM "lints" wiki quarterly, detects inconsistencies, updates connections

**Result:** Semantic coherence scales without vector overhead; agents reason over 400K-word structured text efficiently.

---

## Architecture: 3 Stages + File Structure

### Stage 1: Raw Ingest
```
vault/
├── raw/                          # All unprocessed materials
│   ├── papers/
│   │   ├── 2024-calibration-ml.md      (web clip or PDF → markdown)
│   │   ├── 2024-nba-ml-survey.md
│   │   └── 2025-tabular-llms.md
│   ├── repos/
│   │   ├── TabICL-github-summary.md
│   │   ├── TabPFN-features.md
│   │   └── CatBoost-docs-extract.md
│   ├── articles/
│   │   ├── Feature-engineering-practice.md
│   │   └── NBA-analytics-trends-2026.md
│   └── datasets/
│       ├── NBA-dataset-schema.md
│       └── Betting-markets-overview.md

├── wiki/                         # COMPILED knowledge base (agents write here)
│   ├── index.md                  # Auto-generated table of contents
│   ├── concepts/
│   │   ├── Calibration.md        (synthesized from raw/)
│   │   ├── Feature-Engineering.md
│   │   ├── Tree-Models.md
│   │   └── Tabular-LLMs.md
│   ├── techniques/
│   │   ├── Venn-ABERS.md
│   │   ├── Platt-Scaling.md
│   │   ├── Brier-Optimization.md
│   │   └── Mutation-Operators.md
│   ├── architectures/
│   │   ├── Genetic-Algorithm-Patterns.md
│   │   ├── Multi-Island-Evolution.md
│   │   └── Ensemble-Methods.md
│   └── backlinks.json            # Machine-readable connection graph

├── health/                       # Linting results & maintenance logs
│   ├── last-lint-2026-04-05.json
│   └── consistency-issues.md

└── .obsidian/
    ├── plugins.json              # Web Clipper, Obsidian Skills
    └── vault.json
```

### Stage 2: LLM Compilation

**Agent Job:** Read all `raw/*.md` files, synthesize into wiki articles

**Example Flow:**
```
Input (raw/papers/):
  - 3 calibration papers
  - 5 NBA ML repos
  - 2 feature engineering guides

Agent Task:
  Read all 10 files
  → Identify common concepts: "calibration", "feature selection", "tree ensemble"
  → Write wiki/concepts/Calibration.md (500 words, cross-referenced)
  → Write wiki/techniques/Venn-ABERS.md (with links back to Calibration.md)
  → Update wiki/index.md with new articles
  → Generate backlinks.json (machine-readable concept graph)

Output Quality:
  ✓ No hallucinations (synthesizes only what raw/ contains)
  ✓ Semantic linking (backlinks prevent orphaned ideas)
  ✓ Human-readable (Markdown, not vectors)
  ✓ Agentable (Claude can edit/update directly)
```

### Stage 3: Active Maintenance (Health Checks)

**Agent Job:** Run linting passes quarterly or after major updates

**Checks:**
- Missing cross-references (article mentions "Brier score" but no link to `wiki/concepts/Calibration.md`)
- Outdated info (paper from 2023 now superseded by 2025 research)
- Orphaned articles (no backlinks, dead ends)
- Inconsistencies (article A says "Venn-ABERS needs 1K calibration samples", article B says "100 samples")

**Action:** Agent writes issue ticket or updates wiki directly (with human approval)

---

## Why We Haven't Implemented This Yet (Diagnosis)

1. **Raw materials scattered:**
   - `data/departments/council-*.json` (evolution metrics)
   - `data/arena/docs/*.md` (arena season docs)
   - Memory files in `~/.claude/agent-memory/` (Forge, cycling, GPU strategies)
   - GitHub issues + Telegram messages (unstructured)

2. **No compilation layer:**
   - We read/update memory files manually
   - No agent automatically synthesizes "what have we learned about feature engineering?"
   - Each department loop invents own patterns instead of building on shared wiki

3. **No maintenance discipline:**
   - Memory files get stale (last updated Apr 3, now Apr 5)
   - Contradictions creep in (old strategy in one file, new in another)
   - No automated health checks

4. **Knowledge silos:**
   - D3 (Evolution) doesn't see what D1 (Research) discovered
   - Trading Floor agents don't see feature engineering insights
   - NBA quant + Political Alpha evolved separately despite shared ML foundations

---

## Implementation Plan for Nomos42

### Phase 1: Ingest (1 day)

**Goal:** Collect all raw research into `vault/raw/`

```bash
# Create vault structure
mkdir -p /home/lahargnedebartoli/mon-ipad/research-vault/{raw,wiki,health}
mkdir -p /home/lahargnedebartoli/mon-ipad/research-vault/raw/{papers,repos,articles,logs}
mkdir -p /home/lahargnedebartoli/mon-ipad/research-vault/wiki/{concepts,techniques,architectures,learnings}

# Ingest existing materials
cp /home/lahargnedebartoli/mon-ipad/.claude/agent-memory/karpathy-researcher/*.md \
   /home/lahargnedebartoli/mon-ipad/research-vault/raw/articles/

cp /home/lahargnedebartoli/mon-ipad/data/arena/docs/*.md \
   /home/lahargnedebartoli/mon-ipad/research-vault/raw/articles/

# Create metadata for each raw file
# (script: scripts/vault/ingest-to-vault.py)
```

**Output:** `vault/raw/` populated with 30-50 markdown files, all tagged with source + date

### Phase 2: Compilation Agent (1 day)

**Agent Job:** Synthesize raw/ into wiki/

```python
# scripts/vault/compile-vault.py

class VaultCompiler:
    def __init__(self, vault_root):
        self.vault = vault_root
        self.raw_files = load_all_markdown(f"{vault_root}/raw/")
        
    def compile_concepts(self):
        """Extract concepts from raw files, write to wiki/concepts/"""
        concepts = extract_concepts(self.raw_files)
        # concepts = ["Calibration", "Feature Engineering", "Mutation", ...]
        
        for concept in concepts:
            content = synthesize_concept(concept, self.raw_files)
            write_article(f"{self.vault}/wiki/concepts/{concept}.md", content)
            
    def compile_techniques(self):
        """Extract techniques (Venn-ABERS, mutation ops, etc)"""
        # Similar pattern
        
    def build_backlinks(self):
        """Generate machine-readable concept graph"""
        graph = build_connection_graph(self.vault)
        write_json(f"{self.vault}/backlinks.json", graph)
        
    def compile_all(self):
        self.compile_concepts()
        self.compile_techniques()
        self.build_backlinks()
```

**Triggers:**
- Cron: Run after each department council cycle (D1 Research new papers → compile)
- Manual: `./scripts/vault/compile-vault.py --full` (rebuild entire wiki)

**Output:** `wiki/concepts/`, `wiki/techniques/` populated; backlinks.json machine-readable

### Phase 3: Integration with Agent Loop (1 day)

**Modify Department Councils to use wiki:**

```bash
# scripts/councils/department-council.sh (D1 Research example)

# Before: Agent reads scattered memory files
# After: Agent reads wiki/index.md + wiki/concepts/* + raw/papers/*

RESEARCH_CONTEXT=$(cat /home/lahargnedebartoli/mon-ipad/research-vault/wiki/index.md \
                    /home/lahargnedebartoli/mon-ipad/research-vault/wiki/concepts/*.md)

claude code --task "Find gaps in $RESEARCH_CONTEXT. Propose 3 new experiments." \
  --files "research-vault/raw/papers:ro" \
  --output "proposals.json"
```

**Benefits:**
- Agent sees all prior research (no reinventing wheel)
- Proposals backed by structured knowledge
- Better quality Brier improvements (fewer duplicate efforts)

### Phase 4: Health Checks (Optional, but high ROI)

**Quarterly linting pass:**

```python
# scripts/vault/lint-vault.py

def lint_vault():
    issues = []
    
    # Check 1: Orphaned articles
    orphans = find_articles_without_backlinks()
    issues.extend([f"Orphaned: {article}" for article in orphans])
    
    # Check 2: Broken links (article mentions "Venn-ABERS" but no link)
    broken = find_mentioned_but_not_linked_concepts()
    issues.extend(broken)
    
    # Check 3: Stale content (last updated >90 days ago)
    stale = find_articles_older_than_days(90)
    issues.extend([f"Stale: {article}" for article in stale])
    
    # Check 4: Contradictions (scan for conflicting claims)
    contradictions = find_semantic_contradictions()
    issues.extend(contradictions)
    
    # Write issues
    write_markdown(f"vault/health/issues-{date.today()}.md", issues)
    return len(issues)
```

---

## Open-Source Tools & Integration

| Tool | Purpose | Integration |
|------|---------|-----------|
| **Obsidian Vault** | Local knowledge base editor | `research-vault/` directory |
| **Obsidian Web Clipper** | Convert web articles to Markdown | Manual for now, automate with Firecrawl |
| **Obsidian Skills** (MCP) | AI agent Obsidian integration | Use Claude Code with `--mcp obsidian` |
| **Claude Code** | Compilation + linting agent | Driver for compile-vault.py, lint-vault.py |
| **Firecrawl API** | Auto-fetch & convert web papers | Future: automation layer for raw ingest |
| **json2graph** | Visualize backlinks.json | Future: /evolution dashboard widget |

---

## Expected Impact

### Research Velocity
- **Before:** Agent re-reads 10 scattered memory files per cycle → slow context building
- **After:** Agent reads 1 structured wiki → focused proposals → fewer redundant experiments

**Brier Improvement:** +0.0005 to +0.001 (better feature discovery cadence)

### Knowledge Reuse
- **Before:** D1 discovers "circular feature interaction patterns" → doesn't propagate to D3 Evolution
- **After:** Wiki article "Interaction-Patterns.md" auto-linked in concept graph → all depts benefit

**Brier Improvement:** +0.0005 to +0.001 (cross-pollination of insights)

### Calibration
- **Before:** Calibration research scattered (memory file, paper excerpts, old tweets)
- **After:** wiki/concepts/Calibration.md + wiki/techniques/Venn-ABERS.md + wiki/techniques/Platt-Scaling.md
  - All linked together
  - Agent can see tradeoffs between methods
  - Faster to prototype improvements

**Brier Improvement:** +0.001 to +0.002 (faster calibration iteration)

**Total:** -0.0015 to -0.004 Brier (cumulative)

---

## Why Everyone Talks About It (But Hasn't Deployed)

1. **Hype vs. Implementation:** Karpathy published the concept (March 2026); it sounds awesome. But it's not a library or framework — it's a **pattern** requiring custom scaffolding per project.

2. **Seeming Overkill:** "We don't have 100K articles yet. Why build a wiki?" — But once you have 30+ research files + 5 depts + 6 islands evolving, scattered memory becomes a liability.

3. **Obsidian Not Default:** Obsidian is $10/user/month (syncing). Many teams use Notion (RAG-friendly) or GitHub wikis (version-controlled). Karpathy's pattern assumes local Obsidian vault.

4. **No Turn-Key Tool:** Unlike RAG (Vector DB + LangChain), there's no "Obsidian RAG library." You build compile-vault.py from scratch.

5. **Perceived Complexity:** "Three stages + backlinks + health checks" sounds heavy. In reality, Stage 1 (ingest) is a copy, Stage 2 (compile) is ~100 lines of Python, Stage 3 (lint) is optional.

---

## Recommendation

**Deploy NOW because:**

1. ✓ We have the raw materials (30+ research files, scattered across dirs)
2. ✓ We have the agents (Claude Code Deployment can drive compilation + linting)
3. ✓ We have incentive (cross-dept knowledge reuse → -0.002 Brier improvement)
4. ✓ We have time (2-3 days of implementation; ROI in 1 week as research quality improves)

**Not deploying means:**
- D1 Research → duplicates D6 Evaluation discoveries
- Trading Floor agents → don't see feature engineering insights
- Karpathy Loop → slower convergence (agents reinvent patterns)

---

## Next Steps

1. **Create vault structure** (30 min, scripts/vault/init-vault.sh)
2. **Move raw materials** (1 hour, scripts/vault/ingest-to-vault.py)
3. **Write compile agent** (4 hours, scripts/vault/compile-vault.py)
4. **Integrate with D1 Research loop** (2 hours, modify department-council.sh)
5. **Deploy health checks** (2 hours, scripts/vault/lint-vault.py) — *optional for v1*

**Total: 2-3 days. Expected ROI: -0.002 to -0.004 Brier.**

Deployment target: **April 7, 2026** (Tuesday).

