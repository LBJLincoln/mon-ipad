---
name: project_claude_code_ecosystem
description: Anthropic official repos, Claude Code v2.1.84 features, Agent SDK, hooks inventory — scanned 2026-03-26
type: project
---

## Scan: Anthropic Official Ecosystem (2026-03-26)

### Claude Code CLI - v2.1.84 (2026-03-26, daily releases)
Repo: https://github.com/anthropics/claude-code

**Key March 2026 hooks (new):**
- `CwdChanged` (v2.1.83) — fires on cd. Use with `$CLAUDE_ENV_FILE` + direnv for multi-repo Brain cycles.
- `FileChanged` (v2.1.83) — watches specific filenames. Use to auto-sync engine.py to HF Spaces.
- `StopFailure` (v2.1.78) — fires on API errors (rate_limit, billing_error, server_error). Use for Telegram alerts.
- `TaskCreated` (v2.1.84) — new task lifecycle event.
- `PostCompact` (v2.1.76) — fires after auto-compaction. Use to re-inject CLAUDE.md context.
- `initialPrompt` frontmatter (v2.1.83) — auto-submitted on `--agent` launch. Seeds Brain with /evolve-report output.
- `managed-settings.d/` (v2.1.83) — drop-in policy fragments for enterprise/team settings.
- `--bare` flag (v2.1.81) — skips hooks and plugin sync in scripted `-p` calls.

**Full hook event list (25 events as of v2.1.84):**
SessionStart, UserPromptSubmit, PreToolUse, PermissionRequest, PostToolUse, PostToolUseFailure, Notification, SubagentStart, SubagentStop, Stop, StopFailure, TeammateIdle, TaskCompleted, TaskCreated, InstructionsLoaded, ConfigChange, CwdChanged, FileChanged, WorktreeCreate, WorktreeRemove, PreCompact, PostCompact, Elicitation, ElicitationResult, SessionEnd

**Hook types:** command, http, prompt, agent

### Claude Agent SDK (Python) — v0.1.50
Repo: https://github.com/anthropics/claude-agent-sdk-python
Install: `pip install claude-agent-sdk`

Key capabilities:
- `query()` async generator — fire-and-forget
- `ClaudeSDKClient` — bidirectional, hooks in-process via HookMatcher callbacks
- `AgentDefinition(description, prompt, tools, model)` — define subagents in Python
- `permissionMode='acceptEdits'` — fully autonomous file editing
- Session persistence: `resume=session_id` passes context across 4h cycles
- `RateLimitEvent` typed message — detect rate limits for backoff
- `create_sdk_mcp_server()` — in-process MCP (no subprocess overhead)
- In 0.1.46: add_mcp_server()/remove_mcp_server() at runtime

### Subagent Frontmatter (as of v2.1.84)
Key fields for .claude/agents/*.md:
- `initialPrompt`: auto-submitted on --agent launch (commands/skills processed)
- `memory: project|user|local`: persistent memory dir, MEMORY.md injected at startup
- `isolation: worktree`: temp git worktree (safe experimentation, auto-cleanup)
- `background: true`: run concurrently with main session
- `effort: low|medium|high|max`: model effort override
- `model: haiku|sonnet|opus|inherit`: cost/quality tradeoff per agent
- `skills`: preload skill content (not inherit from parent)
- `mcpServers`: scope MCP server to this subagent only

### Other Official Repos
- https://github.com/anthropics/claude-code-action — GitHub CI/CD integration
- https://github.com/anthropics/skills — 103k stars, skill templates + DOCX/PDF manipulation
- https://github.com/anthropics/claude-plugins-official — plugin = json + mcp + commands + agents + skills
- https://github.com/anthropics/claude-agent-sdk-demos — 8 demos, research-agent shows parallel subagent synthesis

### Top Community Repos
- https://github.com/disler/claude-code-hooks-mastery — TTS, security, JSON audit logging
- https://github.com/hesreallyhim/awesome-claude-code — curated skills/hooks/orchestrators
- https://github.com/wshobson/agents — 112 agents, 72 plugins incl. MLOps/data-engineering
- https://github.com/disler/claude-code-hooks-multi-agent-observability — SubagentStart/Stop tracking

**Why:** Scheduled deep-dive on Anthropic ecosystem specifically. Previous scans covered NBA/tabular ML.
**How to apply:** Implement the 3 hooks (FileChanged/StopFailure/PostCompact) immediately (2h). Then formalize subagent definitions with initialPrompt + memory (1-2 days).
