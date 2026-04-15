# Autonomous AI Organization Benchmark — April 14, 2026
Generated: 2026-04-14 | Analyst: D1-Research subagent

---

## 1. Benchmark Targets — What They Actually Are

### "Paperclip" — What the User Means vs What Exists

**User mental model:** Paperclip-maximizer-style: propose change → measure → keep/revert, infinite loop.

**What nomos42 actually built** (source: `scripts/councils/paperclip-runner.sh`):
- Wraps `hermes-runner.sh` with pre/post Brier measurement and `git revert` if regression
- Architecture is correct: snapshot → run → measure → verdict → ledger append
- **CRITICAL FLAW documented in the script's own comments (line 89-96):**
  > "HONEST NOTE: this currently uses brier_proxy.py --json (baseline_cv mode) which is a CONSTANT function of data/proxy/holdout.json. As long as the council doesn't regenerate that holdout file, delta will always be 0 and Paperclip will always verdict=no_op."
- **Result:** The keep/revert gate is structurally sound but effectively a no-op on every iteration because the Brier signal doesn't move. The runner functions only as a crash gate.
- **Number of agents:** 1 Claude Code CLI agent per dept run, sequential, up to 9
- **Feedback loop:** Exists on paper. Dead in practice because brier_proxy output is constant between backtest refreshes (every 4h).

**External reference — "Paperclip" as a concept in 2026:**
No canonical external project uses this exact name. The closest SOTA analogue is CORAL (arXiv:2604.01658, Apr 3 2026, MIT+NUS): autonomous multi-agent evolution with persistent shared memory, heartbeat-based agent health management, and isolated evaluator separation. CORAL is the real version of what paperclip-runner.sh aspires to be.

---

### Runway AI (runway.ml / runwayml.com)

**What it actually is:** A video generation AI company ($5.3B valuation, Feb 2026, Series E $315M). Their "agent organization" is internal product engineering, not a published autonomous AI research loop.

**What they published in 2026:**
- GWM-1: General World Model for real-time interactive avatars and robotics simulation
- Characters API: real-time video agent API (agents with faces and voices)
- Python SDK for robotics world models (action-conditioned video generation)

**Relevance to nomos42:** Zero. Runway does not publish agent org architecture. The user's reference to "Runway AI's internal agent organization" is based on speculation or misremembering. There is no public paper, repo, or architecture document describing how Runway organizes its internal AI agents for self-improvement.

**Verdict:** Not a benchmark target. Cannot compare.

---

### Mirofish = camel-ai/oasis (vendored at vendor/oasis/)

**What OASIS actually is** (arXiv:2411.11581, CAMEL-AI):
- Social media simulation at scale: up to 1M agents on Reddit/Twitter-like platforms
- Agents model: post, react, follow, spread information, form group polarization
- Architecture: Redis-backed event bus, PettingZoo-style environment interface, async agent execution
- Use case: studying misinformation, group dynamics, social phenomena — NOT prediction improvement loops

**Current state of vendor/oasis/ in nomos42:**
- Full git checkout present (shallow clone from camel-ai/oasis main)
- Contains: Reddit + Twitter simulation environments, emall product data, group polarization datasets
- Contains: Docker compose, Python env, documentation
- **NOT integrated into any running process.** No cron, no import, no call from any nbafacing script.
- Per memory note from Apr 12 session: "OASIS wired" — this means the vendoring was done, but the actual integration (using OASIS social signal data as a feature) was never completed.

**2026 update status:** Last OASIS release updated camel-ai to 0.2.78 and a HuggingFace dataset link. No major architectural update since Dec 2025.

**Relevance to nomos42:** The concept (social dynamics → market signals) is valid. The implementation is a dead vendored dependency. Zero active use.

---

### Devin 2.0 / Cognition Labs

**What it is:** AI software engineer. Single agent, long-horizon coding tasks.
- SWE-bench Verified: 13.86% originally; leading systems now >75% by early 2026
- Architecture: sandboxed compute, SWE-grep for codebase search, shell+editor+browser
- In late 2025: rebuilt on Claude Sonnet 4.5

**Organizational model:** One agent, one task at a time. No department councils. No evolution islands. No cross-agent feedback.

**vs nomos42:** Devin does not self-improve its own architecture. It's a product for human-directed tasks. Not comparable to an autonomous org that improves its own prediction model.

---

### CrewAI 2.0 (dominant framework as of Jan 2026, ~70% of AI workflow builds)

**Architecture:**
- Hierarchical: Manager Agent (GPT-5 class) + Worker Agents (cheaper models)
- Manager delegates, validates quality, sends back for revision
- Native: short-term, long-term, entity memory
- "Flows": deterministic backbone with LLM intelligence at decision nodes only

**vs nomos42 councils:** CrewAI's hierarchical model matches nomos42's Guardian Orchestrator concept but nomos42 does not run a live Guardian that reads all 9 council outputs and reallocates tasks. The Guardian is referenced in CLAUDE.md but has no active cron or script.

---

### CORAL (arXiv:2604.01658, MIT + NUS, Apr 3 2026) — Closest Real Analogue

**What it does:**
- Replaces fixed scaffolding (hardcoded mutation/crossover rules) with agents that decide what to explore
- Agents run persistently, reflect on prior attempts, share knowledge via persistent memory
- Heartbeat-based intervention: health monitoring kills/restarts stuck agents
- Isolated workspaces per agent, separate evaluator process, resource management

**This is what nomos42's Paperclip loop SHOULD be doing.**

---

### AutoGPT / AI Scientist v2 (2026 status)

**AI Scientist v2 (Sakana AI):** Fully automated: hypothesis → code → run → analyze → write paper. Publicly available. Targets ML subfield research. No sports-domain deployment known.

**AutoGPT:** Largely superseded by CrewAI/LangGraph for production use. Still exists as open-source but not a benchmark leader.

---

## 2. Key Academic Papers — April 2026 (Last 60 Days)

### Paper 1: CORAL (arXiv:2604.01658)
**Authors:** A. Qu, H. Zheng, Z. Zhou, Y. Yan et al. (MIT + NUS)
**Date:** April 3, 2026
**TL;DR:** First framework for autonomous multi-agent evolution on open-ended problems — agents explore, reflect, and collaborate through shared persistent memory with heartbeat-based health management and isolated evaluators.
**Steal for nomos42:** Replace paperclip-runner.sh's constant-Brier no-op with CORAL's pattern: each council writes findings to a shared persistent memory store, a separate evaluator process computes Brier delta on a rolling 50-game holdout (not re-read from static file), and the heartbeat kills stalled councils.

---

### Paper 2: Self-Optimizing Multi-Agent Systems for Deep Research (arXiv:2604.02988)
**Authors:** Arthur Câmara, Vincent Slot, Jakub Zavrel (Zeta Alpha, Amsterdam)
**Date:** April 3, 2026
**TL;DR:** Orchestrator + parallel worker agents that optimize their own prompts via self-play, matching or beating hand-engineered expert systems for complex research retrieval tasks.
**Steal for nomos42:** D1 Research council should run two prompt variants per cycle and keep the one that produces a higher-quality proposal (measured by whether D2 subsequently ships the feature). This is prompt-level Paperclip that doesn't require Brier eval.

---

### Paper 3: Deep Researcher Agent (arXiv:2604.05854)
**Authors:** Xiangyue Zhang (University of Tokyo)
**Date:** April 7, 2026
**TL;DR:** Leader-Worker architecture for 24/7 ML experimentation with zero-cost monitoring (log file reads only during training, no LLM API calls), two-tier constant-size memory.
**Steal for nomos42:** The zero-cost monitoring pattern maps exactly to watching HF Space logs via curl /api/status without burning Claude API budget. Implement: D3 Evolution monitors island logs cheaply, escalates to Claude only when generation plateau is detected (stall_streak > 5).

---

### Paper 4: AgentRxiv (arXiv:2503.18102)
**Authors:** Samuel Schmidgall, Michael Moor (Johns Hopkins)
**Date:** March 23, 2025 (still actively cited in Apr 2026)
**TL;DR:** LLM agent labs upload reports to a shared preprint server; agents that access prior research achieve 11.4% relative improvement vs isolated agents (MATH-500: 70.2% → 78.2%).
**Steal for nomos42:** The research-vault/ Obsidian KB already exists. Wire D1 to READ the last 10 research entries before proposing a new technique. Currently D1 ignores prior cycles. AgentRxiv pattern: each D1 output = a "paper" that future D1 runs must cite and not duplicate.

---

### Paper 5: Agentic Variation Operators / AVO (referenced in self-evolving survey)
**Context:** Self-evolving AI agents survey (arXiv:2508.07407, plus 2026 updates)
**TL;DR:** Replace fixed mutation/crossover operators in evolutionary search with autonomous coding agents that consult the lineage, a knowledge base, and execution feedback before proposing the next variant.
**Steal for nomos42:** D3 Evolution currently sends generic "mutate features" prompts to HF spaces. AVO-style: D3 reads the last 5 generations of each island, identifies which feature category improved Brier, and proposes a targeted mutation in that specific category rather than random perturbation.

---

### Paper 6: Prediction Arena (arXiv:2604.07355, referenced in CLAUDE.md)
**TL;DR:** 1-bet-per-agent tournament validates that structurally distinct agent reasoning (DMAD anti-groupthink) outperforms consensus averaging.
**Steal for nomos42:** The Trading Floor v3's 10 agents currently have personality parameters but no mechanism to enforce reasoning diversity. Implement DMAD: before each agent bets, show it the aggregate consensus and instruct it to argue the opposite case first, then decide.

---

### Paper 7: EvoAgentX / Awesome Self-Evolving Agents Survey (GitHub + arXiv)
**Date:** Active through April 2026
**TL;DR:** Comprehensive taxonomy of self-evolving agent systems; key gap = most systems evolve prompts/weights but not their own organizational topology (which departments exist, who talks to whom).
**Steal for nomos42:** The Guardian Orchestrator v3 (referenced in CLAUDE.md) should exist as a real running agent, not just documentation. It reads all 9 council outputs, reallocates $budget per dept based on stall_streak and verified_status, and can spin up a temporary D10 if two councils have complementary findings.

---

## 3. Brutal Audit — What Nomos42 ACTUALLY Does Right Now

### Council Freshness (Apr 14, 2026)

| Dept | Last Run | Status | Stall Streak | Real Verdict |
|------|----------|--------|--------------|--------------|
| D1 Research | 2026-04-12T00:03Z | dns_failure | 13 | STALE (48h) — 13-streak means it has NOT shipped anything real in 13 consecutive runs |
| D2 Engineering | 2026-04-12T01:00Z | failed | 13 | STALE (48h) — exit_code=1, zero real_sha, 13-streak |
| D3 Evolution | 2026-04-14T12:39Z | FRESH | 0 | FRESH — but this is analyze-trading-floor.py output, not hermes-runner |
| D4 Product | 2026-04-10T14:00Z | failed | 10 | STALE (4 days) |
| D5 Business | 2026-04-10T14:00Z | failed/no_op | 9 | STALE (4 days) |
| D6 Evaluation | 2026-04-14T12:39Z | FRESH | n/a | FRESH — also analyze-trading-floor.py output |
| D7 Infra | 2026-04-12T00:00Z | hallucinated | 2 | STALE (48h) — agent claimed sha edf9ad8e but verified=hallucinated |
| D8 Finance | 2026-04-10T14:00Z | hallucinated | 8 | STALE (4 days) — claimed sha but verified=hallucinated |
| D9 Cross-Repo | 2026-04-12T01:00Z | shipped | 0 | STALE (48h) — did ship, but rejected 3 out-of-scope files |

**Fresh councils today:** 2 out of 9 (D3 + D6) — and both are from analyze-trading-floor.py, not hermes-runner. hermes-runner has not produced a fresh council output for ANY department today.

---

### Question (a): Do councils READ live experiment outputs and WRITE config back?

**NO.** Answered definitively:

- **D3 Evolution council-latest.json** (fresh, Apr 14): Contains keyword correlation analysis from Trading Floor logs (pace=62.5% win rate, net rating=58.3%). Verdict: "Seed D2 Engineering to add features for top keywords." This is a TEXT RECOMMENDATION, not a config write. No HF Space received a mutation instruction from this output.

- **D6 Evaluation council-latest.json** (fresh, Apr 14): Contains per-agent calibration (qwen-quant=well-calibrated, mistral-ministral=overconfident gap=0.299). Verdict: "tighten prompt edge-computation instructions." Again TEXT, not action. No agent prompt was updated.

- **smart-council.py** does have an `--execute` flag that can call HF Space `/api/mutate`. But it is NOT called from any active cron. The crons run `hermes-runner.sh` → `paperclip-runner.sh`, not `smart-council.py`.

- **hermes-runner.sh** dept scope for D3 includes `scripts/councils/sync-island-config.sh`. That script CAN push configs to HF Spaces. But D3 has been in dns_failure/failed state and has not run in hermes context in 48h+.

**Conclusion:** The system has the plumbing for bidirectional council-to-island config writes. That plumbing has never fired in the last 4 days based on council timestamps.

---

### Question (b): Is there a real feedback loop (observe → mutate → re-run → measure)?

**PARTIALLY.** The loop exists architecturally but has two broken links:

1. **Observation works**: analyze-trading-floor.py reads HF Space /api/day-decisions and produces calibration + rationale keyword data. This fired today.

2. **Mutation is broken**: The D3 output contains "seed D2 to add features" as text. D2 is stale (48h, stall_streak=13). The text recommendation goes nowhere.

3. **Re-run gap**: Even if D2 ran, it would need to deploy a feature to all 8 HF Spaces and trigger a new evaluation cycle. HF Space evaluations are autonomous (continuous evolution). But D2 has no mechanism to trigger a re-evaluation; it can only edit `features/engine.py` and push via subtree.

4. **Measurement gap**: brier_proxy returns 0.1909 (constant) regardless of what councils do. The Paperclip ledger will record delta=0 for every council run. There is no signal.

**Actual feedback loop that IS working:** The 8 evolution islands run autonomous genetic evolution internally. They do NOT receive council directives. They improve from random mutation, not council insight.

---

### Question (c): How many of 9 councils produce FRESH data today (Apr 14)?

**2 out of 9.** D3 and D6 both show timestamp 2026-04-14T12:39Z — both generated by `analyze-trading-floor.py`, which is a lightweight Python script (no Claude CLI), not a hermes council. The other 7 departments have not run hermes-runner in 48+ hours.

The gap is almost certainly the DNS/Tailscale issue documented in hermes-runner.sh (EAI_AGAIN on GCP). The stall_streak=13 on D1 and D2 is catastrophic — 13 consecutive failures.

---

### Question (d): Does anything adjust evolution-island mutation rates, feature weights, or trader personalities based on council findings?

**NO.** Based on what runs today:

- **Evolution islands (S10-S17):** Mutate autonomously based on their internal GA. No external config has been pushed in the 48h window visible from council timestamps. `sync-island-config.sh` may have run manually at some point but is not active.

- **Trader personalities:** The 10 LLM agents (Gemini, Qwen, Llama, etc.) on the Trading Floor have fixed personality descriptions in their prompts. D6's calibration output identifies mistral-ministral as badly calibrated (win_rate=0.396, confidence=0.695, gap=0.299). No script updates that agent's prompt or risk parameter.

- **Feature weights:** D1 Research (stall_streak=13) has not proposed a feature in 13 iterations. D2 Engineering (stall_streak=13) has not deployed one. The feature engine (v3.1-54cat, 7213 raw features, MAX_FEATURES=200) is unchanged.

---

### The Core Gap in One Sentence

Nomos42 has instrumentation that produces rich real-time observations (calibration, keyword correlations, island Brier) but no actuator that converts those observations into live system mutations. The councils are a read-only analytics layer pretending to be a closed-loop control system.

---

## 4. Gap List — What to Build

Ranked by (Impact × Feasibility). Time estimates assume VM + HF Space only (no new infra).

---

### SHIP THIS WEEK (High Impact, Low Effort)

**W1: Wire analyze-trading-floor.py → HF Space /api/mutate**
- D6 already knows mistral-ministral has calibration_gap=0.299. Add 10 lines: if gap > 0.20, POST to /api/mutate with `{"agent_id": "...", "risk_factor": risk - 0.1}`.
- This closes the observe→actuate loop for trader calibration.
- Effort: 2 hours. Impact: potentially kills the worst trader (mistral-ministral is actively destroying capital).

**W2: Fix brier_proxy to use rolling 50-game holdout (not static file)**
- The single highest-leverage infrastructure fix (self-documented in paperclip-runner.sh line 96).
- Without this, Paperclip's keep/revert gate is permanently disabled.
- Effort: 3 hours. Impact: enables all 9 councils to have a real improvement signal.

**W3: Set D1 to READ research-vault/ last 10 entries before proposing**
- Add 5 lines to the D1 prompt: load last 10 entries from research-vault/wiki/*.md, extract technique names, prepend "DO NOT re-propose: [list]".
- Eliminates duplicate proposal waste. AgentRxiv pattern: 11.4% improvement from this alone.
- Effort: 1 hour. Impact: moderate (D1 currently stalled, so first fix DNS).

**W4: DNS health check cron before hermes-runner fires**
- stall_streak=13 on D1+D2 is almost certainly DNS. Add a 30-second pre-flight: `curl -s --max-time 5 https://api.anthropic.com/`. If it fails, skip the council run and send Telegram alert.
- Effort: 30 minutes. Impact: stops accumulating false stall streaks.

---

### SHIP THIS MONTH (High Impact, Moderate Effort)

**M1: Real Guardian Orchestrator (CORAL pattern)**
- A lightweight Python script (not Claude CLI) runs every 4h: reads all 9 council-*-latest.json files, computes dept health score (verified_status, stall_streak, brier_delta), reallocates budget — double budget for the dept with best recent Brier contribution, halve for stall_streak > 5.
- POST updated budgets to hermes-runner's DEPT_BUDGET environment before next run.
- Effort: 1 day. This is the single most architecturally significant gap vs SOTA (CORAL, CrewAI hierarchical).

**M2: D3 AVO-Style Targeted Mutation**
- Instead of generic "mutate features" prompt, D3 reads the last 5 evolution island generation logs, identifies which feature category (e.g. "rest_differential", "net_rating") improved Brier, and sends a targeted HF Space config mutation for that specific category.
- Currently: random search. AVO pattern: informed search. Expected Brier improvement: -0.002 to -0.004.
- Effort: 2 days.

**M3: DMAD Anti-Groupthink for Trading Floor**
- Before each of the 10 LLM agents bets, show it the aggregate sentiment of the other 9 agents and instruct it to argue the opposing case first, then decide.
- Prediction Arena (arXiv:2604.07355) validates this increases collective accuracy.
- Effort: 1 day (modify Trading Floor app.py prompt construction).

**M4: AgentRxiv-Style Research Memory for D1**
- Each D1 council output is tagged with a paper ID and written to research-vault/papers/. Future D1 runs fetch the last 10 papers and must reference at least 2.
- Closes the "islands of research" problem where D1 rediscovers the same techniques.
- Effort: 2 days.

---

### RESEARCH-HEAVY (High Impact, High Effort — Month 2+)

**R1: Real Evaluator Separation (CORAL safeguard)**
- Currently brier_proxy.py runs in the same process as the council. A council that modifies features/engine.py could (in theory) corrupt the evaluator's data path. Separate: evaluator runs as an independent process with read-only access to a frozen holdout set, communicates results via a file lock.
- Effort: 3 days. Required before brier_proxy can be trusted as a keep/revert signal.

**R2: OASIS Social Signal Integration**
- vendor/oasis/ is already there. Wire a lightweight "social sentiment scraper" (Twitter/Reddit keyword monitoring via OASIS's real_world_prop_data structure) → feature Cat55 ("social sentiment") → feature engine.
- This is the one genuinely novel alpha source not in any of the 8 evolution islands today.
- Effort: 1 week. Expected Brier delta: unknown, likely small (-0.001 to -0.002).

**R3: Self-Play Prompt Optimization (arXiv:2604.02988 pattern)**
- D1 runs two prompt variants per cycle. After 10 cycles, compare proposal acceptance rate (did D2 ship it?) between variants. Keep winning variant.
- This is meta-learning: the research pipeline learns which research framing leads to shipped improvements.
- Effort: 1 week infrastructure + 10 cycles (weeks of runtime) to see signal.

---

## Summary Scoreboard

| Dimension | Runway | CORAL | CrewAI | nomos42 Claim | nomos42 Reality |
|-----------|--------|-------|--------|---------------|-----------------|
| Agents | N/A (product) | Persistent async agents | Manager + Workers | 9 councils + 10 TF + 12 islands | 2 fresh councils today; 7 stale |
| Feedback loop | N/A | Full: shared memory → heartbeat → eval | Manager revision loop | Paperclip keep/revert | No-op (constant brier) |
| Actuation | N/A | Direct: agent modifies workspace | Manager delegates | D3→HF mutate | Zero actuation in 48h |
| Self-improvement | N/A | Yes, open-ended | Limited (prompt revision) | Claimed | Not demonstrated |
| Evaluation isolation | N/A | Yes (isolated evaluator) | No | brier_proxy | Same process, constant output |

**Bottom line:** Nomos42's organizational architecture is more sophisticated on paper than most public implementations. The gap to CORAL is one broken actuator wire (observe → mutate is disconnected) and one broken evaluator (constant Brier output). Fix W1 + W2 and nomos42 is genuinely competitive with April 2026 SOTA. Leave them broken and it remains an analytics dashboard with no closed loop.
