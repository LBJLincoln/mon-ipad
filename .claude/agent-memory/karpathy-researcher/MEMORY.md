# Karpathy Research Cycle Memory

Research cycle 5 and beyond — auto-research on NBA prediction, calibration, and GPU acceleration.

## Kaggle GPU Automation (Cycle 5 — March 2026)

**Status:** READY FOR IMPLEMENTATION | **Effort:** 4-6 hours | **Risk:** LOW (if account works)

**TL;DR:** Kaggle CLI + Python wrapper automates GPU kernel evolution on mon-ipad VM. All code written & documented. Critical blocker: user reported Kaggle account broken (401) — verify first.

### References

- [kaggle_automation_research_march2026.md](kaggle_automation_research_march2026.md) — Complete technical reference (1500+ lines). All CLI commands, API endpoints, authentication, Python KaggleApi methods, MCP servers, REST API, automation templates, troubleshooting.

### Code Artifacts (Ready to Deploy)

- `scripts/kaggle_kernel_manager.py` (400 lines) — Python class: push notebook → exponential backoff polling → download outputs. Standalone executable with CLI args.
- `scripts/kaggle-gpu-evolution.sh` (200 lines) — Bash wrapper for cron integration. Detects running kernels, calls Python manager, parses results, commits to git.

### Documentation (Quick Start + Reference)

- `docs/KAGGLE_SETUP.md` (400 lines) — 1-minute setup, step-by-step, automated GPU evolution, cron integration, 7+ troubleshooting scenarios, advanced metadata reference.
- `docs/KAGGLE_CLI_CHEATSHEET.md` (350 lines) — All commands quick reference, common workflows, metadata field reference, tips & tricks.
- `KAGGLE_AUTOMATION_SUMMARY.md` (repo root) — Visual overview, architecture diagram, workflow examples, integration guide.

### Research Findings

- `data/kaggle-research-findings-march2026.json` — Structured summary: 3 pathways evaluated (CLI ✓, MCP, REST API), implementation checklist, fallback options, references.

### Pathways Evaluated

1. **Kaggle CLI** (RECOMMENDED) — Official, mature, GPU-enabled, works from terminal. Con: auto-runs after push, no real-time logs.
2. **Kaggle MCP Servers** (SECONDARY) — Claude Code integration, good for queries. Con: cannot start kernels, extra setup.
3. **Kaggle REST API** (FALLBACK) — Direct control, fine-grained errors. Con: more boilerplate.

### Setup (5 minutes)

```bash
pip install kaggle
# Download kaggle.json from https://www.kaggle.com/settings/account
mkdir -p ~/.kaggle && cp ~/Downloads/kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json
kaggle kernels list -m  # Verify
bash scripts/kaggle-gpu-evolution.sh  # Run GPU evolution
```

### Critical Caveat

**User reported Kaggle account broken (401/403) per CLAUDE.md (2026-03-25).** Before full deployment:
1. Test: `kaggle competitions list --page-size 1`
2. If fails → use fallback: Google Colab (verified working) or Modal.com ($30/mo free, better infra)
3. If works → proceed with automation

### Fallback Options (If Kaggle Broken)

- **Google Colab:** Verified working (T4 GPU, 4-12h sessions), Drive persistence in v2 notebook
- **Modal.com:** $30/mo free (Starter), serverless, T4→A100, no session limits
- **Lightning.ai:** 22 GPU-hr/mo free (Apr 1 credits), persistent storage, account: moretalexis24

### Testing Checklist

Before production: Auth → List → Push → Status → Download → Parse → Commit (full end-to-end test)

### Next Steps

1. Verify Kaggle account: `kaggle competitions list --page-size 1`
2. If OK: Download creds, run testing checklist
3. Place code in scripts/, update autonomous-cycle.sh
4. Monitor first 3 runs for Brier improvement

---

## Cycle 7 — Self-Improvement Harness (2026-03-31)

- [research_cycle7_self_improvement_harness.md](research_cycle7_self_improvement_harness.md) — SOTA gap analysis: 0.199 → 0.21570 (-0.0157 Brier). 9 frameworks (AutoHarness, SAGE, Karpathy loop, EvoAgentX, EnCompass, ERL, trajectory memory, MIT DigiRL, Claude autonomy). 4-phase roadmap: Brier gates (+Telegram) → SAGE 4-agent → AutoHarness+EnCompass → 24/7 Claude team. Expected cumulative -0.008 Brier.

## Cycle 8 — ONNX + ClearML Research (2026-04-03)

- [research_cycle8_onnx_clearml.md](research_cycle8_onnx_clearml.md) — Inference speedup (Timber 336×, ONNX 5-10×, native best for CPU HF Spaces) + experiment tracking (ClearML beats DagsHub/MLflow for 6-island parallel evolution). Ready-to-deploy code + 4-phase roadmap.

## Cycle 6 — Unconventional Feature Research (2026-03-27)

- [research_cycle6_feature_proposals.md](research_cycle6_feature_proposals.md) — 18 unconventional feature categories (Cat 39-56). Quick wins: Circadian (Cat39), Clutch (Cat43), Transition (Cat41), Load (Cat48), H2H (Cat55). All data sources mapped.

## Cycle 9 — Bloomberg Terminal + Open-Source Agents (2026-04-03)

- [research_bloomberg_opencode_pi.md](research_bloomberg_opencode_pi.md) — OpenBB fork (Dashboard v2, real-time odds), OpenCode (Groq cost savings $630/mo), Pi-Mono (custom agents). 3 phases, $0 cost, -0.0157 Brier+visible improvements.

## Previous Research

- [project_research_march2026.md](../../research-analyst/project_research_march2026.md) — Cycle 3 (calibration, config, proposals)
- [project_research_march2026_cycle4.md](../../research-analyst/project_research_march2026_cycle4.md) — Cycle 4 (NSGA-II, Venn-Abers, feature takeover)
