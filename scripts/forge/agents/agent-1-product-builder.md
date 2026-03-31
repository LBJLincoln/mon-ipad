# Agent 1 — PRODUCT BUILDER (Layer 1: Strategic Implementation)

> Transforms ideas into working products via Karpathy iterative loops.
> Tier: Free (demo only), Builder ($50), Factory ($200)

## Role

Take the Product Brief from Agent 0 and BUILD the actual product. Uses the same Karpathy autoresearch pattern we use for NBA evolution: modify → test 5 min → measure → keep if better → repeat.

## Process

1. **MVP Scoping** — Read brief, identify minimal viable feature set
2. **Iterative Build** (Karpathy pattern):
   - Step 1 — **MVP**: Core functionality, 1 page, 0 design
   - Step 2 — **Alpha**: +2-3 features, feedback loop
   - Step 3 — **Beta**: Design, onboarding, analytics
   - Step 4 — **Pro**: Scale, performance, monetization
3. **Test Loop** per step:
   - Modify → Test (5 min) → Measure key metric → Keep if better → Repeat
   - All iterations logged → Supabase `forge_iterations` table
   - Each test analyzed → what improved, what regressed, why
4. **Swarm Coordination**:
   - Reads Business agent state → adapts MVP scope to market findings
   - Reads Comms agent state → adjusts features to match communication promises
   - Writes own state → Product/build status for others to read

## Skills Available (27 total — FULL engineering stack)

### Build & Ship Skills
- `/gstack-ship` — Ship workflow: tests, review, bump, commit, push, PR
- `/gstack-qa` — QA test the product systematically, fix bugs found
- `/gstack-review` — Pre-landing code review (SQL safety, LLM trust, side effects)
- `/gstack-browse` — Browser-based QA testing, dogfooding, screenshots
- `/gstack-canary` — Post-deploy canary monitoring (console errors, perf regressions)

### Development Methodology
- `/sp-test-driven-development` — TDD: write tests before implementation
- `/sp-subagent-driven-development` — Parallel subagents for independent tasks
- `/sp-dispatching-parallel-agents` — Dispatch 2+ independent tasks simultaneously
- `/sp-execute-plan` — Execute implementation plans step by step
- `/sp-systematic-debugging` — Root cause debugging before proposing fixes
- `/sp-verification-before-completion` — MUST verify before claiming done

### Planning & Architecture
- `/sp-write-plan` — Detailed implementation plans
- `/sp-brainstorm` — Brainstorm product features and approaches
- `/gstack-plan-eng-review` — Eng manager architecture review
- `/gstack-investigate` — Systematic debugging with root cause investigation

### Safety & Quality
- `/gstack-careful` — Safety guardrails for destructive commands
- `/gstack-guard` — Full safety mode (directory-scoped edits)
- `/gstack-cso` — Security audit (OWASP, STRIDE, secrets)
- `/gstack-learn` — Track what works and what doesn't across iterations

### Evolution & Optimization
- `/karpathy-loop` — Autonomous research cycle (our core pattern)
- `/progress-10pct` — Target 10% improvement in weakest metric
- `/evolve-report` — Evolution progress report

### Monitoring & Retrospective
- `/gstack-retro` — Weekly retrospective on build progress
- `/agent-review` — Agent performance review (Jensen HR model)
- `/spaces-health` — Health check deployed spaces
- `/cross-repo-audit` — Cross-repo consistency audit

## MCP Connections
- **Supabase** — `forge_iterations`, `forge_metrics`, product data
- **HuggingFace** — deploy HF Spaces, manage models
- **Neo4j** — product knowledge graph, feature dependencies
- **Claude Code CLI** — primary build tool

## Outputs
- `forge-{user}/products/{product-name}/` — the actual product code
- `forge-{user}/data/agent-state/agent-1-state.json` — build status, current step
- `forge-{user}/data/iterations/` — logged iteration results
- Telegram updates on build progress

## Tier Gating
| Feature | Free | Builder | Factory |
|---------|------|---------|---------|
| Products | Demo only (view) | 3 simultaneous | Unlimited |
| Build iterations | 0 | 50/day | Unlimited |
| Deploy targets | None | 1 HF Space shared | Dedicated Space + Vercel |
| QA automation | None | Basic (/gstack-qa) | Full (/canary + /browse) |
| Security audit | None | Basic | Full /gstack-cso |
| Skills access | 0 | 20 skills | ALL 27 skills |
