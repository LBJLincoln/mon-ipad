# NOMOS42 — GStack, Superpowers & Paperclip Audit
> Installed 2026-03-30 | Coordination status: 2026-03-31

## What Was Installed

### GStack (12 slash commands)
Production-grade deployment and operations skills.

| Command | Purpose | Coordinated with agents? |
|---------|---------|------------------------|
| `/gstack-ship` | Deploy to production | NO — generic, not wired to HF subtree push |
| `/gstack-qa` | Quality assurance | NO — generic, not connected to our test suite |
| `/gstack-review` | Code review | YES — works with any PR |
| `/gstack-browse` | Browse codebase | YES — works with all repos |
| `/gstack-canary` | Canary deployment | NO — no canary infra set up |
| `/gstack-careful` | Careful mode | YES — generic safety mode |
| `/gstack-guard` | Security guard | NO — not connected to our secrets |
| `/gstack-cso` | Chief Security Officer | NO — generic |
| `/gstack-investigate` | Deep investigation | YES — works with any codebase |
| `/gstack-learn` | Learn from codebase | YES — works with all repos |
| `/gstack-plan-eng-review` | Engineering review plan | YES — works with any PR |
| `/gstack-retro` | Retrospective | NO — not connected to our metrics |

**Verdict**: GStack commands are **generic CLI skills**, not agent-specific. They work as Claude Code slash commands but are NOT integrated with our agent ecosystem. They don't know about HF Spaces, evolution, Brier scores, or our specific infrastructure.

### Superpowers (8 slash commands)
Planning and execution methodology skills.

| Command | Purpose | Coordinated? |
|---------|---------|-------------|
| `/sp-brainstorm` | Structured brainstorming | YES — generic, useful |
| `/sp-write-plan` | Write implementation plan | YES — generic, useful |
| `/sp-execute-plan` | Execute a plan step by step | YES — generic, useful |
| `/sp-test-driven-development` | TDD workflow | YES — works with any tests |
| `/sp-subagent-driven-development` | Multi-agent parallel work | YES — this IS our pattern |
| `/sp-dispatching-parallel-agents` | Launch parallel agents | YES — core to our workflow |
| `/sp-systematic-debugging` | Debug methodically | YES — generic, useful |
| `/sp-verification-before-completion` | Verify before shipping | YES — generic, useful |

**Verdict**: Superpowers are **methodology skills**, not agent-specific. They enhance HOW Claude Code works but don't add domain knowledge about our systems. `/sp-subagent-driven-development` and `/sp-dispatching-parallel-agents` are the most relevant since they match our multi-agent architecture.

### Paperclip HF Space (Nomos42/nomos42-paperclip)
| Metric | Value |
|--------|-------|
| Status | EXISTS but likely PAUSED/ERROR |
| Purpose | UNKNOWN — name suggests "paperclip maximizer" concept |
| Coordinated | NO — not connected to any agent |

### Nomos42-infra-brain HF Space
| Metric | Value |
|--------|-------|
| Status | EXISTS — unclear if running |
| Purpose | Earlier version of brain? Or infra monitoring? |
| Coordinated | PARTIALLY — superseded by nomos42-brain |

## Coordination Gaps

### What's NOT connected:
1. **GStack commands don't know about HF subtree deployment** — `/gstack-ship` should know to run `git subtree split --prefix=hf-space` for HF deploys
2. **No skill for monitoring** — should have `/monitor-fleet` that checks all spaces
3. **Arena results not surfaced** — no skill to display latest arena rankings
4. **Forge bot not connected to Forge agents** — @Forge42Bot exists but F0-F6 agents don't exist as code
5. **Research proposals not flowing** — R1-R4 output to Supabase but E1 doesn't auto-read them

### What SHOULD be integrated:
1. Custom `/deploy-hf` skill that wraps our subtree push workflow
2. Custom `/fleet-status` skill that polls all services (like fleet-monitor space but in CLI)
3. Custom `/forge-intake` skill that runs F0 Strategy Definer
4. Modify `/gstack-ship` to understand our deployment targets (HF, Vercel, VM)
5. Add `/political-signals` skill for on-demand signal checking

## Recommendations

| Priority | Action | Effort |
|----------|--------|--------|
| P1 | Leave GStack/Superpowers as-is (generic tools, useful) | 0 |
| P1 | Pause or delete paperclip + infra-brain spaces (unused) | 5min |
| P2 | Create custom `/deploy-hf` skill | 30min |
| P2 | Create custom `/fleet-status` skill | 30min |
| P3 | Wire Forge bot to actual agent code | 4h |
| P3 | Auto-pipe research proposals to feature engineering | 2h |
