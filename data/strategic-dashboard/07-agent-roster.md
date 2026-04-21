# 07 — AGENT ROSTER (14-crew + cadence)

Source: `.claude/agents/ROSTER.md`. Layered L1/L2/L3.

## L1 STRATEGIC (never does domain work)

| Agent | Cadence | Role |
|---|---|---|
| **THE BOSS** | every 4h at `:00` | One-screen status, dispatches L2+L3, go/no-go calls. Reads `data/pipeline-health.json` + `data/audit/`. |

## L2 APPLICATION (Karpathy autoresearch, SCAN→PROPOSE→EXECUTE→EVALUATE→KEEP/REVERT)

| Agent | Cadence | Scope | Domain |
|---|---|---|---|
| **HAWKEYE** | daily 06:00 UTC | arXiv/GitHub/X/Semantic Scholar/NeurIPS | external SOTA scout — writes proposals FRANKENSTEIN implements verbatim |
| **DR FRANKENSTEIN** | every 12h | `engine.py` NBA + `political_engine.py` POL | implements oldest proposal, sha256 parity repo↔HF |
| **THE BLACKSMITH** | decommissioned 2026-04-20 | (9 dept councils) | **no-op** — council Spaces deleted |
| **SWISH** | every 4h at `:10` | S10-S22 (6 survivors) | NBA island diagnosis + diversify + pareto-checkpoint + restart dead |
| **LOBBYIST** | every 4h at `:15` | P1-P8 (5 survivors) | POL island manager — non-sports edges (FEC/polling/sovereign) |
| **THE HERALD** | daily 18:00 UTC | @Nomos42Picks | paywall, ≤3 edges, Stripe conversion |
| **PIXEL** | on push `hf-pixel-world/**` | pixel-world, dashboard, TF Gradio | apex visual QA, Chrome automation, regression-GIF |
| **THE ACCOUNTANT** | daily | Stripe/Whop/LS + runway | strategist, not bookkeeper — GTM + pricing |
| **INTERNAL AFFAIRS** | every 4h at `:40` | both TFs | scientific-integrity audit (leakage, lockstep, WR outlier, walk-forward) |
| **LAUNCHPAD** | every 6h at `:45` | GH Actions, Vercel, HF, parity | CI/CD orchestrator, diagnoses only, does NOT deploy itself |

## L3 LOGISTICS

| Agent | Cadence | Scope |
|---|---|---|
| **SWITCHBOARD** | every 6h at `:20` | LLM gateway + TFs + pixel-world + langfuse — provider routing + fallback |
| **THE PLUMBER** | every 4h at `:35` | odds → predictions → TF state → CSV — writes `data/pipeline-health.json` |
| **THE TICKER** | every 30min | Bovada + The Odds API — steam moves, CLV, sharp/square divergence |

## Git mutex (MANDATORY for every autonomous commit)

```bash
scripts/lib/safe_commit.sh <CODENAME> "<msg>" [paths...]
```

`flock` on `/tmp/nomos-git.lock` (120s), `pull --rebase --autostash`, 3× push retry, `[AGENT]` prefix. **Raw `git push` from agents is BANNED.**

## Staggering rule

Every agent's cron is offset on a different `:MM` to avoid git-mutex contention with 14 concurrent crons.
