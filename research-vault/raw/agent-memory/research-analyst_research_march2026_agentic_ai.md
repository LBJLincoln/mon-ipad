---
name: research_march2026_agentic_ai
description: Key findings from March 2026 research cycle covering Claude Code, multi-agent patterns, GPU compute, NBA prediction advances, and agent SDK landscape
type: project
---

Research completed: 2026-03-25
NBA research output: /home/lahargnedebartoli/nomos-nba-agent/data/results/crew-research.json
Agent SDK landscape: /home/lahargnedebartoli/mon-ipad/data/agent-sdk-landscape-march2026.md

## Top Actionable Findings

### 1. MLP Meta-Learner for Stacking (HIGH, -0.004 Brier)
He & Choi (Scientific Reports 2025) showed MLP (2x50 neurons) as meta-learner outperforms logistic regression in stacking ensembles for NBA prediction (83.27% accuracy, AUC 0.9213). Our Colab experiment already at Brier 0.2205 with logistic meta-learner — MLP should push to ~0.2165. Run on S12 or Colab.

### 2. SHAP-Guided Feature Pruning (HIGH, -0.003 Brier)
XGBoost + SHAP on experiment #734 (142 features) to identify which features are noise. Remove bottom 30% by mean |SHAP|. Key NBA features from literature: FG%, TRB, TOV, 2PA, ORB, 3PT% — check if our evolved set over-indexes on rolling variants. Takes ~15 min on Colab T4.

### 3. ROC-Regularized Isotonic Calibration (HIGH, -0.003 Brier)
Current calibration is STUB — all calibrated variants perform WORSE than uncalibrated. Berta et al. (ICML 2024, proceedings.mlr.press/v238/berta24a) proposes ROC-regularized isotonic regression to prevent overfitting. Fit on time-ordered held-out fold (20%). pip install netcal.

### 4. ZeroGPU H200 Upgrade (HIGH, -0.003 Brier via more evolution)
HF ZeroGPU now uses H200 (141GB HBM3e). Free tier for all users. Apply at huggingface.co/zero-gpu-explorers. PRO ($9/mo) = 25 min H200 daily. 30x faster than CPU — upgrade S14/S15 Nomos42 spaces. ZeroGPU is allocated only during compute, so keepalive pings don't consume quota.

### 5. Autonomous Brain Hooks (HIGH, Brier 0.0 but prevents regression)
3 critical missing hooks from 108h autonomous operation analysis (yurukusa, DEV Community):
- context-monitor: graduated warnings at 40%/30%/15% context remaining
- error-gate: block HF Space config pushes when error log has unresolved entries
- StopFailure: native Agent SDK hook (v0.1.50, released 2026-03-20) for rate limit logging

## Claude Code Architecture Advances (2026)

### Agent SDK v0.1.50 (March 20, 2026)
- tag and created_at fields in SDKSessionInfo
- get_session_info() function
- StopFailure hook: fires on API errors (rate limit, auth failure)
- ${CLAUDE_PLUGIN_DATA}: persistent plugin state across updates

### Skills Architecture
Progressive disclosure: SKILL.md metadata (always loaded) → core instructions (when relevant) → supplementary files (on-demand) → executable Python scripts. Keeps context lean. Works across Claude.ai, Code, Agent SDK. Complement to MCP (Skills = complex workflows; MCP = tool connectivity).

### Subagent Limits
Recommended: 3-4 subagents max. More wastes orchestration overhead. Our current 4-agent architecture (research, market, feature, evolution) is at the recommended limit.

### LangGraph + Claude Agent SDK Pattern
LangGraph as orchestration skeleton + Claude Agent SDK as execution engine inside nodes. Enables: parallel research+market analysis, durable checkpointing, human-in-the-loop interrupts, LangSmith observability. Would halve Karpathy cycle time via parallelization. LangGraph 2.2x faster than CrewAI benchmarks.

## GPU Compute Landscape 2026

- HF ZeroGPU H200: free tier, PRO $9/mo for 25 min/day
- Kaggle: 30 GPU-hours/week (but Kaggle account is BROKEN for our user — use Colab)
- Lightning AI: PyTorch Lightning team's platform, GPU studios
- Paperspace Gradient: free tier with basic GPU
- Colab T4: still best free option for our GPU needs

## NBA Model State of Art 2026

- Best academic accuracy: 83-93% via stacking ensembles with MLP meta-learner
- Key features: FG%, TRB, TOV, 2PA, ORB, 3PT%, Elo ratings
- Non-linear feature-accuracy: accuracy plateaus at 65-80% beyond 60 features (validates GA selection)
- Dynamic quarter-adaptation: 62%→78% accuracy improvement (high effort, high reward)
- No Brier scores in academic literature — hard to directly compare
- SHAP is the recommended interpretability tool for tree models in NBA prediction

## Steam Move / Market Alpha

- Steam move detection (opening vs current line movement) is high-alpha feature not in current engine
- Prediction markets (Kalshi, Polymarket, DraftKings Predictions) expose raw probability data — usable as feature
- 38 states now have DK Predictions as of 2026 — new liquidity venue for value bets

## Agent SDK Landscape (March 2026) — NEW

### Claude Agent SDK (Anthropic)
- RENAMED from Claude Code SDK — now covers non-coding workloads too
- Python: `pip install claude-agent-sdk` | TS: `npm install @anthropic-ai/claude-agent-sdk`
- GitHub: anthropics/claude-agent-sdk-python — 5.7k stars
- Key new: in-process MCP servers (no subprocess), StopFailure hook (v0.1.50), session resume
- Full docs at: https://platform.claude.com/docs/en/agent-sdk/overview

### Google ADK 2.0 Alpha (March 18, 2026)
- GitHub: google/adk-python — 18.6k stars, v1.27.4 stable
- 2.0 adds graph-based execution engine: routing, fan-out/fan-in, retry, state management
- Native A2A protocol support
- Less relevant (Gemini-optimized) but monitor — Vertex AI backend works with Agent SDK

### Framework Star Counts (March 2026)
- LangGraph: 44.6k stars — best for durable stateful production agents
- CrewAI: 45.9k stars, v1.10.1 — fastest time-to-production, native MCP+A2A
- OpenAI Agents SDK: 20.3k stars, v0.13.0 — provider-agnostic, 100+ LLMs
- PydanticAI: 15.4k stars — type-safe, production stable
- AutoGen: MAINTENANCE MODE — Microsoft replaced with Agent Framework (MAF)

### Browser Automation for Odds Scraping
- Browser-Use: 50k+ stars — full autonomous agent loop, Python, natural language goals
- Playwright MCP: drop into Claude Agent SDK via `mcp_servers={"playwright": {...}}`
- Stagehand v3: TypeScript, 44% faster via direct CDP, act/extract/observe primitives
- Recommendation: Playwright MCP for Agent SDK integration; Browser-Use for autonomous harvesting

### MCP New Features (March 2026)
- Tool Search: lazy loading, 85% token reduction (134k → 5k) when many tools loaded
- Elicitation: MCP servers can request structured input mid-task
- 1200+ servers at mcp-awesome.com; official registry at registry.modelcontextprotocol.io

### LangGraph + Agent SDK Pattern
Wrap LangGraph nodes around Claude Agent SDK `query()` calls for parallel execution + durable checkpointing. Benefits: 2.2x faster Karpathy cycle, rate-limit resilience, LangSmith observability.
