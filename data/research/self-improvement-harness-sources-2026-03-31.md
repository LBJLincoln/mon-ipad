# Self-Improvement Harness Research — Complete Sources (2026-03-31)

## Major Frameworks & Papers

### 1. AutoHarness: Automatic Code Harness Synthesis for LLM Agents
- **Authors:** Google DeepMind
- **ArXiv:** [2603.03329](https://arxiv.org/abs/2603.03329)
- **Date:** February 28, 2026
- **Key Innovation:** Auto-synthesize constraint code for LLM agents. Gemini-2.5-Flash outperforms Gemini-2.5-Pro.
- **Relevance to NBA:** Automatic feature constraint generation

---

### 2. SAGE: Multi-Agent Self-Evolution for LLM Reasoning
- **Authors:** University of Science and Technology of China (USTC)
- **ArXiv:** [2603.15255](https://arxiv.org/html/2603.15255)
- **Date:** March 10, 2026
- **Key Innovation:** 4-agent co-evolution (Challenger, Planner, Solver, Critic). +8.9% LiveCodeBench, +10.7% OlympiadBench
- **Relevance to NBA:** Multi-agent feature engineering loop

---

### 3. Experiential Reflective Learning for Self-Improving LLM Agents
- **Authors:** Multi-institution collaboration
- **ArXiv:** [2603.24639](https://arxiv.org/abs/2603.24639)
- **Date:** March 25, 2026
- **Key Innovation:** Learn heuristics from task trajectories, inject at test time
- **Relevance to NBA:** Trajectory-informed feature reuse

---

### 4. Trajectory-Informed Memory Generation for Self-Improving Agent Systems
- **Authors:** Agent Research Consortium
- **ArXiv:** [2603.10600](https://arxiv.org/abs/2603.10600)
- **Date:** March 11, 2026
- **Key Innovation:** Extract actionable learnings from execution trajectories
- **Relevance to NBA:** Memory-augmented feature selection

---

### 5. Self-Improving LLM Agents at Test-Time
- **Authors:** Multiple authors
- **ArXiv:** [2510.07841](https://arxiv.org/abs/2510.07841)
- **Key Innovation:** Test-time self-improvement for agent reasoning
- **Relevance to NBA:** Real-time agent adaptation

---

### 6. EvolveR: Self-Evolving LLM Agents through an Experience-Driven Lifecycle
- **Authors:** Agent Evolution Lab
- **ArXiv:** [2510.16079](https://arxiv.org/html/2510.16079v1)
- **Key Innovation:** Full experience lifecycle: online interaction → offline distillation → principle library
- **Relevance to NBA:** Experience-driven GA mutation

---

### 7. Multi-Agent Evolve: LLM Self-Improve through Co-evolution
- **ArXiv:** [2510.23595](https://arxiv.org/html/2510.23595v3)
- **Key Innovation:** Co-evolution of multiple agents for mutual improvement
- **Relevance to NBA:** Multi-agent GA populations

---

### 8. A Survey of Self-Evolving Agents: What, When, How, and Where to Evolve
- **ArXiv:** [2507.21046](https://arxiv.org/html/2507.21046v4)
- **Key Innovation:** Comprehensive taxonomy of 50+ self-evolving agents (2023-2026)
- **Relevance to NBA:** Find competing approaches, SOTA results

---

## MIT CSAIL Research

### DigiRL & EnCompass Framework
- **Institution:** MIT CSAIL
- **Date:** February 5, 2026
- **Resource:** [MIT CSAIL Announcement](https://www.csail.mit.edu/news/helping-ai-agents-search-get-best-results-out-large-language-models)
- **Key Innovation:** Search over LLM decision paths. +15-40% accuracy over non-searching
- **Relevance to NBA:** Path search for feature subsets

### Self-Improvement via Reinforcement Learning at Scale
- **Institution:** MIT CSAIL
- **Resource:** [Scale ML Talk](https://www.csail.mit.edu/event/scale-ml-self-improvement-llm-agents-through-reinforcement-learning-scale)
- **Key Innovation:** Autonomous RL for agent tasks
- **Relevance to NBA:** RL-based GA evolution

---

## Stanford Research

### CS329A: Self-Improving AI Agents
- **Institution:** Stanford HAI (Human-Centered AI)
- **Date:** January 2026 onward
- **Resource:** [Course Page](https://cs329a.stanford.edu/)
- **Curriculum:** Constitutional AI, verifiers, test-time compute, tool augmentation, memory systems
- **Relevance to NBA:** All directly applicable to feature engineering

---

## Anthropic Claude Research

### Claude Computer Use Agent & Long-Running Autonomy
- **Institution:** Anthropic
- **Date:** March 23, 2026
- **Resource:** [Long-Running Claude Research](https://www.anthropic.com/research/long-running-Claude)
- **Key Innovation:** 21.2 average tool calls, 50-100+ hour autonomous operations
- **Relevance to NBA:** 24/7 unattended GA evolution

### Claude Code Channels & Automation
- **Date:** March 2026
- **Key Innovation:** Always-on coding via Telegram/Discord, cron scheduling
- **Relevance to NBA:** Autonomous agent team orchestration

---

## Andrej Karpathy's AutoResearch (CRITICAL)

### The Karpathy Loop: Autonomous ML Optimization
- **Author:** Andrej Karpathy (formerly OpenAI, Tesla AI Director)
- **Date:** March 7, 2026
- **GitHub:** [karpathy/autoresearch](https://github.com/karpathy/autoresearch)
- **GitHub Stars:** 21,000+ (in first week)
- **Twitter Impressions:** 8.6M+
- **Key Innovation:** Tight loop: modify code → 5-min train → measure loss → commit if better → repeat
- **Results:** 700 experiments in 2 days, 20 optimizations discovered. Shopify CEO: 19% improvement overnight.
- **Relevance to NBA:** EXACT MATCH to our deployed Karpathy cycle. Already implemented in `scripts/kaggle/nba_karpathy_loop.py`
- **References:**
  - [Fortune: "The Karpathy Loop"](https://fortune.com/2026/03/17/andrej-karpathy-loop-autonomous-ai-agents-future/)
  - [NextBigFuture interview](https://www.nextbigfuture.com/2026/03/andrej-karpathy-on-code-agents-autoresearch-and-the-self-improvement-loopy-era-of-ai.html)
  - [Kingy AI guide](https://kingy.ai/ai/autoresearch-karpathys-minimal-agent-loop-for-autonomous-llm-experimentation/)
  - [Medium: Universal AutoResearch Skill](https://medium.com/@k.balu124/i-turned-andrej-karpathys-autoresearch-into-a-universal-skill-1cb3d44fc669)
  - [DataCamp Tutorial](https://www.datacamp.com/tutorial/guide-to-autoresearch)
  - [Alexey Danilin substack](https://alexeyondata.substack.com/p/karpathys-autoresearch-went-viral)

---

## Open-Source Frameworks

### EvoAgentX: Automated Framework for Evolving Agentic Workflows
- **GitHub:** [github.com/EvoAgentX/EvoAgentX](https://github.com/EvoAgentX/EvoAgentX)
- **Stars:** 3,200+
- **Status:** EMNLP 2025 Demo
- **Key Innovation:** WorkFlowGenerator auto-creates multi-agent workflows. 25+ built-in tools.
- **Relevance to NBA:** Adapt for feature engineering workflow generation

### Awesome-Self-Evolving-Agents Survey
- **GitHub:** [github.com/EvoAgentX/Awesome-Self-Evolving-Agents](https://github.com/EvoAgentX/Awesome-Self-Evolving-Agents)
- **Stars:** 5,400+
- **Status:** Comprehensive taxonomy (2023-2026)
- **Relevance to NBA:** Find competing approaches, SOTA benchmarks

### Self-Improving Coding Agent (SICA)
- **GitHub:** [github.com/MaximeRobeyns/self_improving_coding_agent](https://github.com/MaximeRobeyns/self_improving_coding_agent)
- **Stars:** 2,800+
- **Key Innovation:** 17% → 53% on SWE-Bench Verified via self-improvement
- **Relevance to NBA:** Error recovery patterns, self-correction

### Awesome-Agent-Papers
- **GitHub:** [github.com/luo-junyu/Awesome-Agent-Papers](https://github.com/luo-junyu/Awesome-Agent-Papers)
- **Stars:** 4,100+
- **Status:** Up-to-date survey of LLM Agent papers
- **Relevance to NBA:** Cross-reference for agent design patterns

### Awesome-Multi-Agent-Papers
- **GitHub:** [github.com/kyegomez/awesome-multi-agent-papers](https://github.com/kyegomez/awesome-multi-agent-papers)
- **Status:** Compilation of best multi-agent research
- **Relevance to NBA:** SAGE-style co-evolution papers

---

## Media & Blog Coverage

### Fortune: "The Karpathy Loop"
- **URL:** https://fortune.com/2026/03/17/andrej-karpathy-loop-autonomous-ai-agents-future/
- **Headline:** "700 experiments, 2 days, and a glimpse of where AI is heading"

### NextBigFuture: Karpathy on Code Agents
- **URL:** https://www.nextbigfuture.com/2026/03/andrej-karpathy-on-code-agents-autoresearch-and-the-self-improvement-loopy-era-of-ai.html
- **Topic:** AutoResearch, code agents, self-improvement loops

### StartupHub.ai: "Anthropic's Claude Masters Autonomous Coding"
- **URL:** https://www.startuphub.ai/ai-news/artificial-intelligence/2026/anthropic-s-claude-masters-autonomous-coding

### MarkTechPost: "Anthropic Introduces Code Review via Claude Code"
- **URL:** https://www.marktechpost.com/2026/03/09/anthropic-introduces-code-review-via-claude-code-to-automate-complex-security-research-using-advanced-agentic-multi-step-reasoning-loops/

---

## Conference Workshops

### ICLR 2026: Recursive Self-Improvement Workshop
- **Paper:** [Submitted OpenReview format](https://openreview.net/pdf?id=g9rEYVNn5T)
- **Topic:** Recursive self-improvement techniques for LLMs

### CVPR 2026 AI4Space Workshop
- **Paper:** GUIDE (Guided Updates for In-context Decision Evolution)
- **Resource:** [arXiv 2603.27306](https://arxiv.org/html/2603.27306)

---

## Data & Benchmarks

### Published SOTA (Montrucchio 2026)
- **Brier Score:** 0.199
- **Method:** Ensemble over 400+ hand-crafted features
- **Our Gap:** 0.21570 - 0.199 = 0.0157 Brier

### Our Current ATR (Colab TabICL)
- **Brier Score:** 0.21570 (March 27, 2026)
- **Model:** TabICL, 110 features, 15 iterations
- **Method:** GPU evolution on Google Colab T4

### Kaggle Walk-Forward Backtest
- **Brier:** 0.22447 (average across 19 weeks, 934 games)
- **Model:** Tree ensemble (extra_trees on P100)
- **Note:** TabICL incompatible with P100 CUDA

---

## Comprehensive Data Files

### Primary Research Data
- **File:** `/home/lahargnedebartoli/mon-ipad/data/research/self-improvement-harness-2026-03-31.json`
- **Contents:** 9 major frameworks, 4 open-source repos, 7 techniques, 4-phase roadmap, implementation checklist
- **Size:** ~15KB JSON

### Quick Wins Implementation Guide
- **File:** `/home/lahargnedebartoli/mon-ipad/data/research/self-improvement-harness-quick-wins-2026-03-31.md`
- **Contents:** 6 actionable quick wins (1h-1w each), combined -0.0085 Brier target
- **Implementation:** 1 week sprint plan

### Agent Memory
- **File:** `/home/lahargnedebartoli/mon-ipad/.claude/agent-memory/karpathy-researcher/research_cycle7_self_improvement_harness.md`
- **Contents:** Structured memory for future conversations

---

## Key Metrics

| Metric | Value | Source |
|--------|-------|--------|
| **Published SOTA Brier** | 0.199 | Montrucchio 2026 |
| **Our ATR Brier** | 0.21570 | Colab TabICL (Mar 27) |
| **Gap** | -0.0157 | Difference |
| **Target (Phase 1-4)** | 0.21485 → 0.20682 | -0.0088 cumulative |
| **Karpathy Loop Experiments/Day** | ~350 | Empirical (700 in 2 days) |
| **SAGE Improvements** | +8.9% to +10.7% | LiveCodeBench, OlympiadBench |
| **EnCompass Accuracy Boost** | +15-40% | Translation tasks |

---

## How This Research Applies to NBA Prediction

**Problem:** We're 0.0157 Brier away from published SOTA (0.199). Montrucchio achieved this via manual feature engineering + tournament selection. We can match via autonomous techniques.

**Solution:** Deploy self-improving harness from 4 frameworks:
1. **Karpathy Loop** (already deployed) — extend with Brier gates
2. **SAGE** — 4-agent co-evolution for feature generation
3. **AutoHarness** — auto-generate feature constraints
4. **EnCompass** — path search over feature subsets

**Expected Outcome:**
- Phase 1 (1 week): -0.001 Brier (Brier gates + takeover detection + Telegram)
- Phase 2 (2 weeks): -0.002-0.003 Brier (SAGE 4-agent pilot)
- Phase 3 (1 month): -0.002-0.004 Brier (AutoHarness + EnCompass)
- Phase 4 (ongoing): -0.003-0.008 Brier (24/7 Claude autonomy)
- **Total: -0.008-0.016 Brier** (reaching or beating SOTA)

---

Generated: 2026-03-31T23:59:59Z
