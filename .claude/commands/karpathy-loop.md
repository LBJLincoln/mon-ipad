Run one Karpathy auto-research cycle: Claude Code agents research → extract proposals → evaluate → report.

Arguments: $ARGUMENTS (optional: "research-only", "eval-only", or target like "brier:0.20")

This is the autonomous improvement loop inspired by Karpathy's auto-research pattern.
It runs 4 Claude Code subagents in parallel, parses outputs, extracts actionable proposals, and generates next steps.

## Steps

1. **Run agent cycle** (skip if $ARGUMENTS = "eval-only"):
   Launch 4 Claude Code subagents **in parallel** using the Agent tool:
   - `research-analyst` (model: sonnet) — Search latest NBA quant papers, techniques
   - `market-analyst` (model: sonnet) — Fetch live odds, detect steam moves, CLV
   - `feature-engineer` (model: sonnet) — Analyze features, propose improvements
   - `evolution-optimizer` (model: sonnet) — Check S10/S11, diagnose GA health

   Each agent reads context from `/home/termius/nomos-nba-agent/data/results/` and writes its output JSON there.
   Agent definitions: `.claude/agents/*.md`

   **DO NOT** use `python3 agents/nba_crew.py` — that uses dead external LLMs.
   Use Claude Code's Agent tool with `model: "sonnet"` for all 4 agents.

2. **Read crew outputs** — parse all 4 JSON files:
   - `/home/termius/nomos-nba-agent/data/results/crew-research.json` — papers, techniques, feature ideas
   - `/home/termius/nomos-nba-agent/data/results/crew-market.json` — live odds, steam moves, CLV
   - `/home/termius/nomos-nba-agent/data/results/crew-features.json` — feature proposals
   - `/home/termius/nomos-nba-agent/data/results/crew-evolution.json` — GA diagnostics, parameter tuning
   - `/home/termius/nomos-nba-agent/data/results/crew-cycle-latest.json` — cycle status

3. **Extract proposals** — from all crew outputs, build a ranked list:
   - Each proposal: { technique, expected_brier_delta, effort_hours, category: feature|parameter|architecture }
   - Sort by expected_brier_delta / effort_hours (bang for buck)
   - Flag "quick wins" = effort < 2h AND expected delta > 0.005

4. **Check current state**:
   - Read latest evolution results: `ls -t /home/termius/nomos-nba-agent/data/results/evolution-*.json | head -1`
   - Current best Brier from Supabase: `SELECT MIN(brier_score) FROM nba_experiments WHERE brier_score IS NOT NULL`
   - Current feature engine version: `python3 -c "from features.engine import ENGINE_VERSION; print(ENGINE_VERSION)"` (run from nomos-nba-agent/)

5. **Log proposals to Supabase** (if table exists):
   For each top-5 proposal, INSERT into `research_proposals` table with status='proposed'.

6. **Generate report** — output a structured summary:
   ```
   ## Karpathy Loop — Cycle Report

   **Current Best**: Brier X.XXXX | ROI X.X% | Features: XX selected
   **Target**: Brier < 0.20 | ROI > 5% | Sharpe > 1.5
   **Gap**: X.XXXX Brier points to target

   ### Top Proposals (ranked by impact/effort)
   1. [QUICK WIN] technique — expected Δ Brier: -0.0XX, effort: Xh
   2. technique — expected Δ Brier: -0.0XX, effort: Xh
   3. technique — expected Δ Brier: -0.0XX, effort: Xh

   ### Market Intelligence
   - Steam moves detected: X
   - CLV opportunities: X
   - Sharp/square divergence: ...

   ### GA Health
   - Population diversity: ...
   - Stagnation risk: ...
   - Recommended parameter changes: ...

   ### Next Actions
   1. [AUTO] Quick win #1 can be implemented now
   2. [MANUAL] Submit GPU experiment for technique X on S10
   3. [RESEARCH] Need more data on technique Y
   ```

7. **Auto-implement quick wins** (if $ARGUMENTS != "research-only"):
   - If a proposal is purely a feature addition (new column in engine.py) AND effort < 1h:
     - Implement it in both `features/engine.py` AND `hf-space/features/engine.py`
     - Run engine parity check: `sha256sum features/engine.py hf-space/features/engine.py`
     - Commit with message: `feat: add [feature] from karpathy loop cycle`
   - NEVER auto-implement architecture changes or parameter sweeps
   - NEVER run ML on VM — if testing needed, note it for S10/Colab

## Constraints
- ZERO ML on VM (1 vCPU / 969 MB RAM)
- Feature engine changes must maintain parity (root = hf-space)
- All experiments must include feature_engine_version
- Use Claude Code (Sonnet subagents) for all research — NOT external LLMs
- 1 change per iteration — never batch multiple proposals
