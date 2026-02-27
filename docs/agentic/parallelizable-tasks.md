# Parallelizable Tasks — Kimi vs Claude Assignment

> Last updated: 2026-02-27T17:00:00+00:00
> 
> This document categorizes all current backlog items by who should handle them and why.

---

## EXECUTIVE SUMMARY

| Category | Count | Handler | Risk Level |
|----------|-------|---------|------------|
| **Parallelizable (Kimi)** | 18 tasks | Kimi CLI (Sonnet-level subagents) | Low — isolated, non-blocking |
| **Sequential (Claude)** | 14 tasks | Claude Opus 4.6 | High — critical path, dependencies |
| **Hybrid** | 4 tasks | Kimi → Claude review | Medium — parallel then consolidate |

---

## PARALLELIZABLE TASKS (Kimi)

> **Rationale**: These tasks are isolated, don't affect critical production paths, and have clear success criteria. Kimi can run multiple in parallel safely.

### Documentation & Governance (6 tasks)

| # | Task | Rationale | Success Criteria |
|---|------|-----------|------------------|
| K1 | Create `directives/repos/rag-pme-connectors.md` | Missing directive file; standalone doc | File exists, synced from CLAUDE.md |
| K2 | Create `directives/repos/rag-pme-usecases.md` | Missing directive file; standalone doc | File exists, synced from CLAUDE.md |
| K3 | Create template CLAUDE.md for new repos | Template creation; no production impact | Template in `templates/CLAUDE.md.template` |
| K4 | Add CODE_OF_CONDUCT.md to public repos | Community doc; doesn't affect code | Files committed to rag-dashboard |
| K5 | Document dataset download process (14 benchmarks) | Documentation only; reference material | Section in `technicals/data/datasets-master.md` |
| K6 | Create API documentation for webhooks | Reference docs; no functional change | `docs/api/webhooks.md` with all endpoints |

### Repository Hygiene (4 tasks)

| # | Task | Rationale | Success Criteria |
|---|------|-----------|------------------|
| K7 | Weekly git gc cron job for all repos | Maintenance; doesn't block development | Script in `scripts/cron-git-gc.sh` |
| K8 | Logs rotation policy (delete >30 days) | Cleanup; pure maintenance | Script deletes old logs, commits weekly |
| K9 | Node_modules cleanup for website repos | Disk hygiene; non-critical | Script `scripts/cleanup-node-modules.sh` |
| K10 | Compress old outputs (gzip sessions >30d) | Storage optimization; safe | Archive script + cron entry |

### CI/CD & Automation (5 tasks)

| # | Task | Rationale | Success Criteria |
|---|------|-----------|------------------|
| K11 | Add GitHub Actions linting for eval scripts | Code quality; doesn't block | `.github/workflows/lint-eval.yml` passes |
| K12 | Add pre-commit hooks (black, ruff, prettier) | Code formatting; non-blocking | `.pre-commit-config.yaml` in each repo |
| K13 | Add Dependabot for all repos | Security automation; independent | `dependabot.yml` in each repo |
| K14 | Create `scripts/bulk-status.sh` (git status all repos) | Visibility utility; standalone | Script outputs status table |
| K15 | Create `scripts/bulk-pull.sh` (fetch all repos) | Sync utility; standalone | Script syncs all 7 repos |

### Testing Infrastructure (3 tasks)

| # | Task | Rationale | Success Criteria |
|---|------|-----------|------------------|
| K16 | Add pytest unit tests for quick-test.py | Testing infra; isolated | `tests/test_quick_test.py` with 5+ tests |
| K17 | Document expected Codespace setup in rag-tests | Documentation; reference | Section in `rag-tests/README.md` |
| K18 | Add dry-run mode for ingestion | Safety feature; independent | `--dry-run` flag works in `trigger-ingestion.py` |

---

## SEQUENTIAL TASKS (Claude)

> **Rationale**: These tasks are on the critical path, have dependencies on other tasks, affect production infrastructure, or require complex debugging coordination. Must be done one at a time by Claude Opus.

### Pipeline Fixes (Critical Path) — 5 tasks

| # | Task | Rationale | Dependency Chain |
|------|------|-----------|------------------|
| C1 | **Fix Quantitative pipeline degradation** (92% → 6%) | Core pipeline broken; blocks Phase 2 | Must fix before eval continues |
| C2 | **Fix Orchestrator empty body issue** | Meta-pipeline broken; affects all routing | Depends on C1 (need working sub-pipelines) |
| C3 | **Fix Data Ingestion V4.0** (Redis removal) | Critical infra; breaks document ingestion | Blocks all new data ingestion |
| C4 | **Fix Multi-Canal Gateway** | Production connector; affects user notifications | Lower priority than C1-C3 |
| C5 | **Restore credentials on HF Spaces #2-10** | Security-critical; affects all pipelines | Must verify each space individually |

### Architecture & Infrastructure — 4 tasks

| # | Task | Rationale | Why Sequential |
|------|------|-----------|----------------|
| C6 | **HF Space #2 full deployment** | Infrastructure split; affects routing | Must verify Space #1 stable first |
| C7 | **OpenRouter key rotation in n8n workflows** | Affects all LLM calls; rate-limit critical | One pipeline at a time to test |
| C8 | **LiteLLM proxy setup on VM** | Central routing change; affects all pipelines | Must test each pipeline after switch |
| C9 | **Implement n8n workflow auto-versioning** | Affects production deployment flow | Must maintain rollback capability |

### Evaluation & Metrics — 3 tasks

| # | Task | Rationale | Why Sequential |
|------|------|-----------|----------------|
| C10 | **Integrate RAGAS metrics** (faithfulness, recall) | Changes eval methodology; affects gates | Must validate on one pipeline first |
| C11 | **Component-level eval** (retriever-only testing) | New testing paradigm; needs validation | Requires baseline comparison |
| C12 | **Create 1000q test dataset for chatbot** | Test data creation; affects accuracy metrics | Must align with chatbot scope |

### Session Intelligence — 2 tasks

| # | Task | Rationale | Why Sequential |
|------|------|-----------|----------------|
| C13 | **Modify Session Analyzer agent** (fixes-library restrictor) | Changes core debugging process | Must test thoroughly before enabling |
| C14 | **CLAUDE.md massive cleanup** | Affects all agent behavior | Requires careful A/B testing |

---

## HYBRID TASKS (Kimi Draft → Claude Review)

> **Rationale**: These can be drafted in parallel by Kimi but require Claude review before deployment due to cross-cutting impact.

| # | Task | Kimi Scope | Claude Review |
|------|------|------------|---------------|
| H1 | Create `rag-chatbot-backend` repo setup | Scaffold repo, basic structure, README | Review architecture, approve n8n patterns |
| H2 | Standardize `.gitignore` across all 7 repos | Generate standard `.gitignore` files | Review exclusions, approve |
| H3 | VM Monitoring Agent 24/7 (RAM/disk/n8n) | Implement metrics collection daemon | Review thresholds, alert integration |
| H4 | Add E2E tests for website chatbots | Write Playwright test skeletons | Review test scenarios, approve selectors |

---

## PARALLELIZATION GUIDELINES

### Kimi Assignment Rules

```
✅ CAN parallelize:
- Documentation (any)
- Scripts/utilities (no production dependencies)
- Tests for existing functionality
- CI/CD templates
- Repository hygiene scripts
- Data preparation/formatting

❌ CANNOT parallelize:
- Fixes to broken production workflows
- Credential changes
- Infrastructure changes affecting >1 component
- Changes to eval methodology
- Changes affecting accuracy calculations
```

### Task Splitting Best Practices

| Pattern | Example |
|---------|---------|
| **By repo** | Kimi handles rag-pme-connectors, rag-pme-usecases, rag-dashboard docs in parallel |
| **By layer** | Kimi: frontend/docs; Claude: backend/workflows |
| **By phase** | Kimi: scaffold → Claude: integrate → Kimi: document |
| **By criticality** | Kimi: nice-to-haves; Claude: blockers |

### Coordination Protocol

```
1. Claude identifies tasks → marks in this doc
2. Kimi pulls parallelizable tasks → confirms scope
3. Kimi works in feature branches → pushes regularly
4. Claude reviews at session start/end → merges approved
5. Update this doc → mark completed, add new tasks
```

---

## CURRENT SPRINT ALLOCATION

### This Session (Current Focus)

**Claude (Sequential)**:
- C1: Fix Quantitative pipeline degradation ← ACTIVE
- C2: Fix Orchestrator empty body ← QUEUED

**Kimi (Parallel)**:
- K1, K2: Create missing directive files ← READY
- K11: GitHub Actions linting for eval scripts ← READY
- K14, K15: Bulk status/pull scripts ← READY

**Hybrid (Kimi Draft)**:
- H4: E2E test skeletons for chatbots ← PENDING

### Next Sprint (Queued)

**Claude**:
- C3: Data Ingestion V4.0 fix
- C5: Credential restore on HF Spaces
- C6: HF Space #2 deployment

**Kimi**:
- K7-K10: Repository hygiene scripts
- K16-K18: Testing infrastructure
- K3-K6: Remaining documentation

---

## ANTI-PATTERNS (What NOT to Do)

| Anti-Pattern | Why It Fails | Correct Approach |
|--------------|--------------|------------------|
| Kimi fixes production pipeline | No rollback safety, may miss edge cases | Claude only for production fixes |
| Claude writes documentation | Wastes Opus tokens on low-complexity work | Kimi drafts, Claude reviews |
| Parallel credential changes | Race conditions, sync issues | Sequential with verification |
| Kimi modifies eval scripts | Could silently break accuracy calc | Claude reviews all eval changes |
| Claude does file cleanup | Token waste on mechanical work | Kimi scripts, Claude approves |

---

## METRICS

| Metric | Target | Current |
|--------|--------|---------|
| Parallel tasks completed / session | 5+ | TBD |
| Sequential tasks completed / session | 2-3 | TBD |
| Kimi token efficiency vs Claude | 10:1 | Baseline |
| Production incidents from parallel tasks | 0 | 0 so far |

---

*Document maintained by: Claude Opus (sequential strategy) + Kimi (parallel execution)*
*Update frequency: After each sprint/session*
