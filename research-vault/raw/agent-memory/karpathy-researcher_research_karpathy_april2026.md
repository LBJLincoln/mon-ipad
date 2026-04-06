---
name: Karpathy April 2026 Research Summary
description: Comprehensive research on Karpathy's latest posts, tools, and architectures (Obsidian, LLM Council, AutoResearch, Agentic Engineering)
type: project
---

# Andrej Karpathy — April 2026 Research Summary

**Research Date:** 2026-04-04 | **Focus:** Obsidian workflow, LLM Council, AutoResearch, Agent Architectures, Vibe Coding → Agentic Engineering

---

## 1. OBSIDIAN WORKFLOW & LLM KNOWLEDGE BASES

### Overview
Karpathy has published a structured workflow for building LLM-powered personal knowledge bases using Obsidian and Markdown wikis. This is a post-RAG architecture that avoids traditional retrieval while maintaining semantic coherence at scale.

### Architecture: 3-Stage Compilation Pipeline

**Stage 1: Raw Ingest**
- Raw materials (papers, repos, articles, web content) dumped into `raw/` directory
- Obsidian Web Clipper converts web content to Markdown (.md)
- Images stored locally for LLM vision access
- No curation needed at ingest stage

**Stage 2: LLM Compilation**
- Agent reads raw files and writes structured wiki articles
- Output: summaries, concept articles, backlinks, interconnections
- Encyclopedia-style generation with semantic linking
- Acts as a "knowledge compiler" rather than indexer

**Stage 3: Health Checks & Active Maintenance**
- LLM performs "linting" passes on wiki
- Detects inconsistencies, missing data, lost connections
- Incremental updates keep wiki fresh
- Non-static, continuously improving structure

### Scale & Performance
- At 100 articles (~400K words): complex Q&A with minimal RAG dependency
- Auto-maintains indexes and summaries for efficient context retrieval
- Wiki remains manageable frontend via Obsidian

### Key Insight
This bypasses RAG's "hallucination trap" where the model fetches irrelevant documents. Instead, humans curate raw ingest; agents compile into high-signal wiki; queries hit the compiled wiki directly.

**Sources:**
- [Andrej Karpathy LLM Knowledge Bases: Building AI-Powered Wikis in Obsidian (2026 Guide)](https://a2a-mcp.org/blog/andrej-karpathy-llm-knowledge-bases-obsidian-wiki)
- [Building Personal Knowledge Bases with LLMs: The Karpathy Method](https://howaiworks.ai/blog/andrej-karpathy-llm-knowledge-bases)
- [Karpathy shares 'LLM Knowledge Base' architecture that bypasses RAG](https://venturebeat.com/data/karpathy-shares-llm-knowledge-base-architecture-that-bypasses-rag-with-an)

---

## 2. LLM COUNCIL: MULTI-LLM CONSENSUS & ORCHESTRATION

### What It Is
LLM Council is Karpathy's "vibe code" reference architecture for multi-LLM orchestration. It's a few hundred lines of Python/JavaScript that defines **the missing orchestration middleware** between applications and volatile LLM markets.

**Released:** March 2026 as a weekend project  
**Status:** Open-source, rapidly adopted by platform teams evaluating multi-LLM strategies

### Three-Stage Deliberation Process

**Stage 1: Parallel Individual Responses**
- User query sent to all council members simultaneously
- Models: GPT-5.1, Claude Sonnet 4.5, Gemini 3 Pro, Grok 4 (configurable)
- All responses returned in parallel tabs for side-by-side review

**Stage 2: Anonymized Peer Review** ← **The Key Innovation**
- Each model evaluates *other* responses without knowing the source
- Prevents brand bias (e.g., "Claude is always good")
- Models rank submissions on accuracy, insight, completeness
- Anonymous voting prevents bandwagon effects

**Stage 3: Chairman Synthesis**
- Designated model (often Claude Opus 4.6) synthesizes all responses
- Incorporates peer rankings and insights
- Produces final comprehensive answer
- Context aware of alternatives considered

### Technical Architecture
- **Backend:** FastAPI (Python 3.10+, async requests to OpenRouter API)
- **Frontend:** React + Vite (tabbed interface, real-time updates)
- **Persistence:** JSON files in `data/conversations/`
- **Implementation:** ~500-800 lines total

### Why This Matters (April 2026 Context)
LLM Council is not just a demo—it's a reference architecture. Platform teams increasingly face this decision:
- Which LLM to bet on for critical tasks?
- How to reduce single-model hallucination risk?
- How to integrate multiple models in production?

Karpathy's council pattern answers: **structured deliberation + anonymized peer review = robust consensus.**

The fact that this came from a "vibe code" weekend project suggests LLMs can now architect sophisticated systems quickly.

**Sources:**
- [GitHub - karpathy/llm-council: LLM Council works together to answer your hardest questions](https://github.com/karpathy/llm-council)
- [Andrej Karpathy's LLM COUNCIL | Fully Explained](https://medium.com/@nisarg.nargund/andrej-karpathys-llm-council-fully-explained-5251bdc9a95f)
- [A weekend 'vibe code' hack by Andrej Karpathy quietly sketches the missing layer of enterprise AI orchestration](https://venturebeat.com/ai/a-weekend-vibe-code-hack-by-andrej-karpathy-quietly-sketches-the-missing)
- [GitHub All-Stars #10: llm-council – AI Consensus mechanism](https://virtuslab.com/blog/ai/llm-council)

---

## 3. AUTORESEARCH: AUTONOMOUS ML EXPERIMENT LOOP

### Release
**Date:** March 6-8, 2026  
**Form:** Open-source Python + train.py architecture  
**Community Response:** 21,000+ GitHub stars in 48 hours, 8.6M views on announcement

### Core Pattern: The Karpathy Loop

**What It Does:**
Agent reads `program.md` (baseline instructions) and `train.py` (single training file), proposes a modification with reasoning, applies the change, runs exactly 5-minute training, evaluates result against baseline, keeps if improved or reverts if not, commits to git, repeats.

**Key Metrics:**
- Training time: Fixed 5 minutes (wall-clock, excluding startup/compilation)
- Experiment rate: ~12 experiments/hour
- Overnight yield: ~100 experiments (user sleeps, agent works)
- Scale: Single GPU (H100, P100, T4)

### Design Philosophy

**Three Essential Files:**

1. **prepare.py** — Fixed dataset prep, utilities. Humans don't touch.
2. **train.py** — The single file agents modify. Full LLM training loop (630 lines). Agents can adjust:
   - Model architecture (layer count, dim, attention heads)
   - Optimizer settings (Muon + AdamW blending)
   - Hyperparameters (learning rate, batch size, warmup)
   - Training dynamics (gradient accumulation, loss scaling)
3. **program.md** — Human-authored baseline instructions. Tells agent what to research.

### Constraint-Driven Design
- **Single metric:** `val_bpb` (validation bits per byte, lower is better)
- **Fixed time:** 5 minutes per experiment (ensures reproducibility)
- **Single file:** `train.py` (reduces scope, easier for agent to reason about)
- **Single GPU:** Minimal resource footprint

These constraints make the agent's search space *meaningful* instead of overwhelming.

### Real-World Results

**Karpathy's Own Sessions:**
- Session 1: `val_bpb` 0.9979 → 0.9773 (89 experiments, 2 days on H100)
- Session 2: `val_bpb` 0.9979 → 0.9697 (126 experiments)

**External Validation:**
- Shopify CEO Tobi Lütke ran autoresearch on templating engine → **53% faster rendering** (37 experiments overnight)
- Lütke: "19% performance gain from 93 automated commits"

### Architectural Significance

This is not a toy. The Karpathy Loop demonstrates that:
1. **Agents can do real research** (not just chat) when given tight constraints
2. **5-minute experiments** are granular enough to enable ~100 trials overnight
3. **Git-based feedback** (keep/revert) is simpler and more reliable than score thresholds
4. **Single-file scope** keeps agent reasoning tractable

### Next Steps in Ecosystem
- Multi-agent variants: one agent proposes hypotheses, another runs experiments, a third evaluates
- Scaling from nanochat → larger models
- Cross-repo autoresearch (multiple codebases optimizing simultaneously)

**Sources:**
- [GitHub - karpathy/autoresearch: AI agents running research on single-GPU nanochat training automatically](https://github.com/karpathy/autoresearch)
- [Andrej Karpathy Open-Sources 'Autoresearch': A 630-Line Python Tool](https://www.marktechpost.com/2026/03/08/andrej-karpathy-open-sources-autoresearch-a-630-line-python-tool-letting-ai-agents-run-autonomous-ml-experiments-on-single-gpus/)
- ['The Karpathy Loop': 700 experiments, 2 days, and a glimpse of where AI is heading](https://fortune.com/2026/03/17/andrej-karpathy-loop-autonomous-ai-agents-future/)
- [Karpathy Autoresearch: Complete 2026 Guide](https://o-mega.ai/articles/karpathy-autoresearch-complete-2026-guide)

---

## 4. VIBE CODING → AGENTIC ENGINEERING (Paradigm Shift)

### Timeline

**February 2025:** Karpathy coins term "vibe coding"
- Definition: "Fully give in to the vibes, embrace exponentials, forget that code even exists"
- Enabled by Claude Cursor Composer + Sonnet, SuperWhisper voice
- Coding workflow: ~80% agent, ~20% human edits/touchups

**April 2026:** Karpathy declares vibe coding "passé"
- New term: **"Agentic Engineering"**
- Why the shift? Because vibe coding was casual/experimental language; agentic engineering is production reality

### Agentic Engineering (April 2026 Definition)

**Core Pattern:**
Developers shift from writing code (primary) to orchestrating agents who write code (primary), with human oversight (secondary).

**Workflow:**
1. Describe what program should do in plain English
2. Agent interprets spec and writes/tests/deploys code
3. Human reviews, approves, or redirects agent
4. Agent iterates until acceptance

**Key Differences from Vibe Coding:**
- Vibe coding: chaotic, experimental, "forget code exists"
- Agentic engineering: structured, supervised, human-in-loop at gates
- Agentic engineering: proven to work in production (Karpathy/Lütke examples)

### Implications

**For This Project (Nomos42):**
- Your "Karpathy loop" is already agentic engineering
- Your autonomous-cycle.sh + 6 HF spaces exemplify this pattern
- Department Forge (D1-D11) councils are multi-agent orchestration

**For Industry (April 2026):**
- No longer need to know how to code to ship software
- Plain English → software is now standard expectation
- Developers are increasingly knowledge/vision architects, not keystroke specialists

**Sources:**
- [Andrej Karpathy on X: "There's a new kind of coding I call 'vibe coding'"](https://x.com/karpathy/status/1886192184808149383?lang=en)
- [The End of Vibe Coding: Andrej Karpathy's Shift to 'Agentic Engineering' in 2026](https://buttondown.com/verified/archive/the-end-of-vibe-coding-andrej-karpathys-shift-to-/)
- [Vibe coding is passé. Karpathy has a new name for the future of software](https://thenewstack.io/vibe-coding-is-passe/)
- ['Vibe coding' may offer insight into our AI future](https://news.harvard.edu/gazette/story/2026/04/vibe-coding-may-offer-insight-into-our-ai-future/)

---

## 5. AGENT ARCHITECTURES & MULTI-AGENT ORCHESTRATION

### Karpathy's Emerging Multi-Agent Pattern

**Single-Agent Baseline (AutoResearch):**
- One agent modifies train.py
- Experiments measure single metric
- Simple feedback loop

**Multi-Agent Evolution (Emerging in Early 2026):**
Three specialized roles:
1. **Hypothesis Agent:** Proposes experiments based on prior results + domain knowledge
2. **Executor Agent:** Runs experiments, collects metrics, manages GPU/logging
3. **Evaluator/Synthesizer:** Reviews results, decides what to keep, updates shared knowledge

### Knowledge Base Multi-Agent Swarm (Karpathy's Latest)

**Problem:** Single agent compiling wiki → hallucinations compound  
**Solution:** "Compound Loop" with quality gates

**Architecture:**
1. **Raw Agents** (multiple): dump outputs to `raw/` directory
2. **Compiler Agent:** organizes raw outputs into draft articles
3. **Hermes Quality Gate:** independent validator scores drafts on truthfulness
4. **Live Wiki:** only verified articles promoted to main knowledge base
5. **Feedback Loop:** agents see live wiki, improve future outputs

**Key Feature:** Quality gate prevents "hallucination infection" where one error cascades through swarm.

### Why This Matters

Karpathy is tackling the **multi-agent alignment problem:** how to coordinate multiple agents without one agent's mistake poisoning the collective output.

His solution: structured workflows + independent validators + gated promotion.

**Sources:**
- [Karpathy's AgentHub: A Practical Guide to Building Your First AI Agent Swarm](https://alirezarezvani.medium.com/karpathys-agenthub-a-practical-guide-to-building-your-first-ai-agent-swarm-13ed56a2007b)
- [Autoresearch - Andrej Karpathy Just Released Autonomous AI Agents That Run Research Overnight](https://www.leaplytics.de/andrej-karpathy-just-released-autonomous-ai-agents-that-run-research-overnight-heres-what-it-means-for-enterprise-ai)
- [Andrej Karpathy: The AI Workflow Shift Explained 2026](https://www.the-ai-corner.com/p/andrej-karpathy-ai-workflow-shift-agentic-era-2026)

---

## 6. OTHER PROJECTS & RESEARCH

### HN Time Capsule Project
- **Concept:** Use LLMs to analyze decade-old Hacker News posts with 10-year hindsight
- **Method:** Fetch HN frontpage from exactly 10 years ago, LLM awards "Most prescient" and "Most wrong" to commenters
- **Output:** HTML report of what happened, how predictions aged
- **Repo:** `karpathy/hn-time-capsule`
- **Status:** Ongoing research into LLM evaluation of past predictions

**Sources:**
- [Auto-grading decade-old Hacker News discussions with hindsight](https://karpathy.bearblog.dev/auto-grade-hn/)
- [GitHub - karpathy/hn-time-capsule](https://github.com/karpathy/hn-time-capsule)

### Nanochat Repo
- Full-stack ChatGPT clone training/inference from scratch
- Described as "among the most unhinged [repos] I've written"
- Single-file, minimal implementation
- Foundation for autoresearch pattern

---

## 7. KEY QUOTES & MINDSET SHIFTS

### "I've never felt this much behind as a programmer" (Dec 2025)
Karpathy's honest assessment that programmer productivity is being transformed. The "sparse bits between" reference suggests agents do 90% of work, humans do 10%.

### "Vibe code is passé" (April 2026)
Signals maturation: from experimental term to production reality. Agentic engineering is now the default expectation.

### On Multi-Agent Challenges (Apr 2026)
"It will take a decade to work through the issues with agents." — Karpathy acknowledges that despite rapid progress, production multi-agent systems still face fundamental challenges in alignment, quality control, and reliability.

---

## 8. IMPLICATIONS FOR NOMOS42 KARPATHY RESEARCH CYCLE

### What We're Doing Right (Aligned with Karpathy's Latest)
1. **Autonomous Karpathy Loop** ✓ — autonomou-cycle.sh runs modify→test→measure→keep/revert exactly as described
2. **Multi-Agent Architecture** ✓ — 6 HF islands + 5 trading floor agents embody multi-agent orchestration
3. **Constraint-Driven Evolution** ✓ — MAX_FEATURES=200, fixed mutation cap, single metric (Brier score)
4. **Department Forge** ✓ — D1-D11 councils parallel Karpathy's specialized agent roles

### What We Can Adopt From April 2026 Research

1. **LLM Knowledge Base (Obsidian + Markdown Wiki)**
   - Current: Scattered research_cycle*.md files
   - Future: Compile raw research into unified wiki with backlinks, auto-maintained by agents
   - Effort: Low (Python script to auto-generate wiki from MEMORY.md + research files)

2. **LLM Council for Trading Floor**
   - Current: 5 traders vote; best strategy wins
   - Future: Add Stage 2 anonymized peer review (traders evaluate other traders' strategies without knowing source)
   - Add Stage 3 synthesis where Claude Opus synthesizes all strategies
   - Effort: Medium (refactor trading-floor-v4.py to 3-stage consensus)

3. **Multi-Agent Quality Gate for Evolution**
   - Current: 6 islands evolve independently → best wins
   - Future: Hermes-style validator (Claude Opus) audits each generation, flags overfitting
   - Effort: Medium (add validation layer to evolution loop)

4. **Agentic Engineering Mindset**
   - Shift: Stop thinking "write code"; start thinking "describe desired behavior, agents implement"
   - Applied: Use Claude Code + plaintext specs instead of manual engineering
   - Impact: Faster iteration cycles, fewer bugs (agent-generated code often cleaner)

---

## 9. TWITTER ACTIVITY (Limited April 2026 Data)

Karpathy tweets less frequently about specific April 2026 events (search results truncated). However, his X account shows ongoing engagement with:
- Autonomous agent discussions
- Vibe coding evolution
- Community responses to autoresearch
- Obsidian/knowledge base architecture discussions

**Note:** Specific April 2026 tweets are not fully indexed yet; use [@karpathy](https://x.com/karpathy) direct for latest.

---

## 10. RESEARCH RECOMMENDATIONS FOR NOMOS42

### Immediate (This Week)
1. Adopt **LLM Council pattern** for trading floor (Stage 2 anonymized review)
2. Extract Obsidian wiki structure for research memory (auto-compile from MEMORY.md)
3. Add Hermes quality gate to 6-island evolution (simple validation pass post-gen)

### Short-term (This Month)
1. Implement multi-agent hypothesis generation → executor → evaluator split
2. Study Karpathy's HN Time Capsule for calibration insights (how past predictions aged)
3. Test "agentic engineering" mindset on next feature: describe in English → Claude generates code

### Medium-term (Q2 2026)
1. Scale autoresearch from single metric (Brier) to multi-metric (Brier + ROI + Sharpe, Pareto frontier)
2. Build knowledge base wiki auto-compiled from arena/docs/ + research papers
3. Implement compound loop quality control (Hermes validator for all generated features, strategies)

---

## Summary: Karpathy April 2026 Landscape

Andrej Karpathy is publishing 3 major conceptual frameworks in Mar-Apr 2026:

| Framework | Release | Purpose | Relevance to Nomos42 |
|-----------|---------|---------|----------------------|
| **Obsidian LLM KB** | Mar 2026 | Post-RAG knowledge compil | Adopt for research memory org |
| **LLM Council** | Mar 2026 | Multi-LLM consensus | Upgrade trading floor voting |
| **AutoResearch** | Mar 2026 | Autonomous agent loop | Validation: we're doing this already ✓ |
| **Agentic Engineering** | Apr 2026 | Paradigm shift: agents code | Adopt mindset for velocity |
| **Multi-Agent Quality Gates** | Apr 2026 | Compound loops + validators | Add to evolution + strategy generation |

**Bottom Line:** Karpathy's April 2026 work validates Nomos42's autonomous architecture choices while offering 3-4 concrete upgrades (council, wiki, quality gates) that could improve Brier by 0.001-0.002.

