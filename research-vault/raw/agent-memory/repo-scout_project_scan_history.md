---
name: project_scan_history
description: History of repo-scout scans — what was covered, what was actioned
type: project
---

## Scan 1: 2026-03-24 (NBA-focused)
- Scope: NBA prediction, sports betting, tabular ML, calibration
- Key finds: TabICLv2 (arXiv:2602.11139), DeepShot EWMA features, NBA_AI pipeline, RLM features, Walsh & Joshi profit-calibration paper
- File: /home/lahargnedebartoli/nomos-nba-agent/data/results/repo-scout.json (original version)

## Scan 2: 2026-03-25 (Broad all-domain scan)
- Scope: AI agents, GPU optimization, tabular ML/foundation models, calibration, Claude Code ecosystem, developer tools, NBA/sports
- New repos found: ComposioHQ/agent-orchestrator, dsifry/metaswarm, ogham-mcp/ogham-mcp, balldontlie-api/mcp, odds-api-io/odds-api-python, anthropics/claude-agent-sdk-demos, LLMFE, TabPFN 2.6, MAPIE v1.3.0
- Key upgrade: Scan expanded to cover ALL domains per user request
- File: /home/lahargnedebartoli/nomos-nba-agent/data/results/repo-scout.json (v2, comprehensive merge)
- Supabase inserts: proposed via research_proposals table

**How to apply:** Run next scan in ~2 weeks to catch April 2026 releases. Prioritize checking: tabicl releases, TabPFN 2.6 docs, ogham-mcp adoption, LLMFE code quality after community feedback.

## Scan 3: 2026-03-26 (Anthropic official ecosystem)
- Scope: anthropics/* repos, Claude Code v2.1.84 hooks, Agent SDK, subagent patterns
- New features found: CwdChanged/FileChanged/StopFailure/PostCompact/TaskCreated hooks, initialPrompt frontmatter, isolation: worktree, background: true, persistent memory
- Key repos: claude-code, claude-agent-sdk-python (v0.1.50), claude-agent-sdk-demos, skills, claude-plugins-official, claude-code-action
- File: /home/lahargnedebartoli/nomos-nba-agent/data/results/claude-code-scout-2026-03-26.json
- Supabase inserts: 5 proposals (hooks, SDK orchestration, initialPrompt, HTTP hooks, subagent memory)
- Memory: project_claude_code_ecosystem.md

**How to apply:** Implement FileChanged + StopFailure + PostCompact hooks first (2h). Then initialPrompt for nba-brain agent (3h). Then formalize .claude/agents/*.md for all 4 Karpathy subagents (4h).
