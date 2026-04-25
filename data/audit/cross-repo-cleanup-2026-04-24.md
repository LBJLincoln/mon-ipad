# Cross-Repo Cleanup Audit — 2026-04-24

**Scope:** 5 Nomos42 repos on `/home/termius/` (mon-ipad, nomos-political-alpha, nomos-dashboard, rgwa, landing/marketing-not-found)
**Method:** `find -mtime`, `git ls-files`, cron refs (`crontab -l`), GH Actions refs (`.github/workflows/*.yml`), ref-graph via `grep -rl`.
**Time budget:** 15 min used. Report only — nothing deleted or modified.

---

## Summary

| Bucket | Items | Approx size freed |
|---|---|---|
| **P0 DELETE (obvious garbage)** | ~220 file-groups / 8 dirs | **~495 MB on `/home/termius/`**, ~105 MB inside git-tracked paths |
| **P1 CONSOLIDATE** | ~38 docs/scripts | negligible size; clarity win |
| **P2 CONSIDER** | ~15 surfaces | variable |
| **Security flag** | 1 file with tracked secret | must rotate |

**Headline actions (one-read approval):**
1. **Delete `migration-kit/04-credentials.env`** — git-tracked and contains a real `OPENROUTER_KEY_STANDARD` (sk-or-v1-ed01…). Rotate that key regardless.
2. **Delete `/home/termius/mon-ipad-worktrees/*`** (325 MB, both worktrees at 2026-04-19 HEAD, abandoned) — `git worktree remove`.
3. **Delete `/home/termius/rgwa`** (9.9 MB, ZOMBIE per CLAUDE.md, last real commit Apr 10; Apr 20 "commit" was a CI-only drive-by).
4. **Delete `scripts/councils/`, `scripts/departments/`, `council-spaces/`, `data/departments/`, `hf-agents/betting-monitor|karpathy-arena|political-monitor|predictions-monitor|quality-tracker|research-radar`** — all dept councils were DELETED from HF 2026-04-20 per memory; local code is now pure dead weight (~1.2 MB + clarity).
5. **Delete `vendor/oasis` (75 MB)** — referenced only by one research MD + a scout script (`scripts/arena/oasis_t3_swarm.py`); not invoked by any cron/GHA.
6. **Truncate `data/research-vault-cron.log` (1.6 MB)** — log dumped into `data/`, should be in `logs/`.
7. **Untrack POL `data/polymarket/`, `data/social/`, etc.** — 1168 files are `git ls-files`-tracked but also in `.gitignore` (ignore rules added after `git add`). Run `git rm -r --cached data/{polymarket,social,kalshi,signals,insider,donors,congressional,historical}` to stop bloating the POL repo's history going forward.

---

## A. Staleness (30+ days, abandoned)

### A.1 — `mon-ipad` top-level dirs

| Path | Last touched | Purpose | Action | Priority |
|---|---|---|---|---|
| `scripts/councils/` (9 files + prompts dir) | 2026-04-15 | Ran 9 dept councils — **DECOMMISSIONED 2026-04-20** per CLAUDE.md | DELETE | **P0** |
| `scripts/departments/` (13 subdirs: betting/business/…/trading_floor, `guardian-orchestrator.py` 45 KB) | 2026-04-12 | Dept Karpathy loops — same decomm | DELETE | **P0** |
| `council-spaces/` (`deploy-all.py` + `template/`) | 2026-04-16 | Deployed 9 HF Spaces that are now deleted | DELETE | **P0** |
| `data/departments/` (8 files) | stale | Council state blobs (`council-latest.json` from 2026-04-13) | DELETE | **P0** |
| `hf-agents/` (8 subdirs, 24 files) | 2026-03-31 → 2026-04-15 | HF Spaces for monitors (betting/fleet/island/karpathy/political/predictions/quality/research-radar) — not in any cron/GHA | DELETE | **P1** (check each Space is actually gone on HF Hub first) |
| `hf-spaces/nomos-obs/` | 2026-04-01 | Single orphan "observability" Space — no refs | DELETE | **P1** |
| `hf-brain/` (own `.git`, last commit 2026-04-04) | 2026-04-04 | Old HF brain Space clone; no refs | DELETE | **P0** |
| `nba-quant-space/` (own `.git`, 11 MB, last commit 2026-04-17) | 2026-04-17 | Parity clone of the NBA Space; real source is `scripts/arena/hf-llm-trading-floor/` (production) or `hf-space/features/engine.py` (engine parity). Nested-git confuses tooling | ARCHIVE then DELETE | **P1** |
| `brev-launchable/` (3 files, Apr 17) | 2026-04-17 | Brev template configs — not referenced | KEEP (small, may revive) or DELETE | P2 |
| `directives/NBA-COMPUTE-RULES.md` | Apr 15 | Single file — supersedes Rule 1 in `CLAUDE.md` | CONSOLIDATE into `CLAUDE.md` | P1 |
| `ops/nba-pilot.py` | stale | Single-file dir, not referenced | DELETE | P1 |
| `papers/axelrod-llm-2026/` (4 stub mds) | 2026-04-18 | Paper draft, only referenced from its own dir | KEEP | — |
| `migration-kit/` (220 files, 1.1 MB, 2026-04-20) | 2026-04-20 | One-shot migration guide to new laptop | ARCHIVE outside repo | **P0** (security below) |

### A.2 — `nomos-political-alpha`

| Path | Last touched | Action | Priority |
|---|---|---|---|
| `logs/agents/` | active (27 MB) | TRUNCATE/ROTATE — `logs/*.log` already gitignored at root but this dir is tracked | P1 |
| `models/` (64 KB) | 2026-03-28 | Old training checkpoints | KEEP (small) | — |
| Everything else is fresh (last commit 2026-04-21) | — | — | — |

### A.3 — `rgwa` (ZOMBIE per CLAUDE.md)

- Real content last touched 2026-04-10 (`CLAUDE.md`), Apr 15 (`.env.local.example`), April 20 "commit" was just `.github/workflows/check.yml` from LAUNCHPAD.
- No `src/` directory, only `data/` (5 subdirs, empty-ish) and `scripts/` (clients/councils/departments/forge/generation/quality/telegram).
- Not referenced by any cron or GHA in mon-ipad (searched for `rgwa`: only hits in `CLAUDE.md` table + `data/ops/cross-repo-improvements-2026-04-20.md`).
- Telegram bot `rgwa_bot.py` PID file present but no active cron.
- **Recommendation:** `DELETE` full directory. Preserve via final `git bundle create` to `~/archive/` if sentimental.
- **Priority:** **P0**

### A.4 — landing/marketing

Not found. No `nomos42-landing` or similar on disk. N/A.

---

## B. Documentation duplication

### B.1 — Root `.md` files (`mon-ipad/`)

| File | Size | Last | Status |
|---|---|---|---|
| `CLAUDE.md` | 25 KB | 2026-04-24 | **KEEP** (canonical) |
| `OPERATIONS.md` | 16 KB | 2026-04-15 | **CONSOLIDATE** — contents overlap ≥60% with `CLAUDE.md`'s architecture/cron sections. Merge delta into `CLAUDE.md`, then DELETE. | P1 |
| `DESIGN.md` | 7 KB | 2026-04-10 | CONSOLIDATE into `docs/` as `docs/DESIGN.md`. | P1 |
| `MONETIZATION.md` | 3 KB | 2026-04-14 | CONSOLIDATE into `docs/business/` (already has `one-pager.md`, `comm-decks.md`). | P1 |
| `ULTRAPLAN-COMMANDS.md` | 5 KB | 2026-04-15 | CONSOLIDATE into `docs/`. | P1 |

### B.2 — `docs/` (35 files, 417 KB total)

All fresh-ish but **`docs/archive/`** (6 files, 100 KB, last touched 2026-04-20) is explicitly archival:

| File | Last | Action |
|---|---|---|
| `docs/archive/FORGE-FACTORY-ARCHITECTURE.md` | Mar 31 | DELETE (Factory decommissioned) |
| `docs/archive/KARPATHY_LLM_COUNCIL_IMPLEMENTATION.md` | Apr 7 | DELETE (councils dead) |
| `docs/archive/PIERRE-SETUP.md` | Apr 7 | KEEP (still one `nomos-pierre` repo on disk, 2.2 MB) |
| `docs/archive/PILOT.md` | Apr 7 | DELETE (superseded) |
| `docs/archive/EXEC_1M_ROAD.md` | Apr 20 | KEEP — recent |
| `docs/archive/EXEC_RUNWAY_MAY1.md` | Apr 20 | KEEP — recent (forward-looking) |
| `docs/archive/ARCHIVE.md` | Apr 16 | KEEP (index) |

All of `docs/social-media/` (13 files, 84 KB) last touched 2026-04-02 / 2026-04-07 — no refs from any script or other md. **Flag as P2 archive.**

### B.3 — CLAUDE.md duplicates

- `./CLAUDE.md` (25 KB, flagship, 2026-04-24)
- `./nomos-political-alpha/CLAUDE.md` (6.8 KB, **this is a clone of the POL repo nested in mon-ipad** — `nomos-political-alpha/` appears BOTH as a sibling at `/home/termius/nomos-political-alpha/` AND nested inside mon-ipad at `/home/termius/mon-ipad/nomos-political-alpha/`). The nested copy is 260 KB total and has no `.git/` — it's a partial working copy. **CONSOLIDATE: delete `mon-ipad/nomos-political-alpha/`**, use the real sibling repo.
- **Priority:** **P0** (confusion risk — two copies of same mission-critical engine).

### B.4 — ROSTER / architecture files

- Only one `ROSTER.md` (`.claude/agents/ROSTER.md`). No dup.
- Architecture MDs scattered in `research-vault/raw/agent-memory/`, `migration-kit/termius-export/claude-memory/` (4 versions: v2/v13/v14/user-ideas). **Delete v2/v13 in migration-kit** (superseded by current `CLAUDE.md`).

### B.5 — Orphan agent memories

`.claude/agent-memory/` has 30 agent dirs; `.claude/agents/` has 15 agents. **18 memory dirs have no matching agent definition** (dead agents from pre-v3 Crew reorg):

```
evolution-optimizer, feature-engineer, karpathy-researcher, market-analyst,
nba-brain, nomos-alpha, nomos-audit, nomos-brain, nomos-forge, nomos-hoops,
nomos-lab, nomos-llm, nomos-pay, nomos-scout, nomos-tape, nomos-wire,
repo-scout, research-analyst
```

**Action:** ARCHIVE (move to `.claude/agent-memory/_deprecated/`) — persona memory might contain useful experiments. **Priority: P1.**

---

## C. Dead scripts

Running ref-graph (grep across repo + cron + GHA workflow files), the following 40 Python scripts have **no references anywhere** and are >7d old:

### C.1 — NOREF scripts in `scripts/`

```
scripts/build_proxy_holdout.py
scripts/real_political_backtest.py
scripts/real_trading_floor_backtest.py
scripts/real_season_backtest.py
scripts/youtube_feature_extractor.py
scripts/fetch_euro_odds.py
scripts/fetch_injury_reports.py
scripts/gpu/refresh_pqtf_cache.py           # PQTF FROZEN FOREVER
scripts/sync/aggregate-health.py
scripts/sync/guardian-cross-pollinate.py
scripts/arena/agent_registry.py
scripts/arena/data_agents.py
scripts/arena/llm_agents.py
scripts/arena/dmad_profiles.py
scripts/arena/audit_trail.py
scripts/arena/build_player_prop_edges.py
scripts/arena/political_cpcv_gate.py
scripts/arena/monitor-hf-experiment.py
scripts/arena/darwin_weights.py
scripts/arena/backfill_games_2025_26.py
scripts/research-vault/generate-graph.py
scripts/research-vault/wiki-builder.py
scripts/research-vault/obsidian-ingest.py
scripts/agents/research-scanner.py
scripts/gpu-burst/feature-cache-sync.py
scripts/gpu-burst/nvidia-nim-serve.py
scripts/reports/scientific_digest.py
scripts/councils/monitor-tf-d6.py
scripts/councils/monitor-gpu-d7.py
scripts/analysis/langfuse_rerun_analysis.py
scripts/analysis/langfuse_24h_summary.py
scripts/ops/tf_baseline_check.py            # modified THIS session; keep
scripts/audit/forensic_bet_audit_2026_04_24.py   # dated today; keep
scripts/monitoring/onnx-export.py
scripts/monitoring/experiment-tracker.py
scripts/monitoring/wandb-logger.py
scripts/forge/f1_product_builder.py         # Factory decommissioned
scripts/forge/f0_strategy_definer.py        # Factory decommissioned
scripts/forge/optimization_patches.py       # Factory decommissioned
scripts/forge/agent-status.py               # Factory decommissioned
```

**Verify each before delete** — `tf_baseline_check.py` is in the current `git status` and `forensic_bet_audit_2026_04_24.py` is dated today (audit-in-progress artifacts).

**Action:** DELETE all except the two above.
**Priority:** **P0** for the Factory/council/PQTF-cache ones (7 files); **P1** for the rest.

### C.2 — Suspicious script subdirs

| Dir | Files | Evidence |
|---|---|---|
| `scripts/laptop/` | 8 shell scripts (2026-04-07) | Local-laptop setup, one-shot; no cron or GHA ref | DELETE — P1 |
| `scripts/opencode/` | 6 files (`config.yaml`, 4 agent shells) | `install-crons.sh` suggests it was supposed to install crons but no trace in current crontab | DELETE — P1 |
| `scripts/patches/` | empty (only `__pycache__`) | Dir contents evacuated; only pyc remains | DELETE — P0 |
| `scripts/empire/build_master.py` | 1 file | Referenced by cron (`data/empire/MASTER_DATA.json` regen) | KEEP |
| `scripts/gemma4/` | 2 files | `gemma4-cross-repo-helper.py` is in GHA `gemma4-cross-repo-helper.yml` schedule | KEEP |
| `scripts/forge/` | 13 files | Mixed: `free-models-integration.py` used by HAWKEYE; `f0/f1/optimization/agent-status` are Factory-era (dead) | PARTIAL DELETE — P1 |
| `scripts/vendor/` | — | not present (only `vendor/` at repo root) | N/A |

---

## D. Data-dir bloat

### D.1 — Append-only JSON log dirs (>50 files)

| Path | Files | Size | Example | Action |
|---|---|---|---|---|
| `data/arena/council/` | 215 `council-iter-*.json` | 1.7 MB | last iter 573 @ Apr 7 | **DELETE all 215** — councils dead | **P0** |
| `data/arena/axelrod-log/` | many | 2.2 MB | cron still writes (`pull-axelrod-log.sh`) | TRUNCATE >14d | P1 |
| `data/arena/traders/` | 497 files | 28 MB | per-agent state dumps; pre-v5 agents | DELETE agents not in current 17-agent roster | P1 |
| `data/monitor/` | 559 files | 6.6 MB | `cycle-*.json` cron dumps (every 5 min since 2026-04-22) | TRUNCATE >24h old (keep latest only) | P1 |
| `data/audit/` | 71 files | 460 KB | 4-hourly audits; `data/audit/cron.log` is tracked | KEEP last 7d, archive rest | P2 |
| `data/ops/` | 25 files + many `*.jsonl` | 18 MB | mixed: operational json + append-only jsonl | Rotate `*.jsonl` >30d old | P1 |
| `data/karpathy/` | 12 files | 66 MB | Few large ML artifacts | CONFIRM each is needed; possibly `.gitignore` | P2 |
| `data/ops/dispatch-log.jsonl` | 1 file | 18 MB subset | Append-only operational log | ROTATE weekly | P1 |

### D.2 — Misplaced log files

| Path | Size | Notes | Action |
|---|---|---|---|
| `data/research-vault-cron.log` | 1.6 MB | cron stdout dumped in `data/` | MOVE to `logs/` + add to `.gitignore` | **P0** |

### D.3 — Top-level log dir

`logs/` = 8.1 MB, 56 files, already covered by `.gitignore` rule `logs/`. Not in git. **Fine.** Consider log-rotate for >30d files (agents/infra-agent-cron.log = 980 KB).

### D.4 — Secret-looking tracked files

- **`migration-kit/04-credentials.env`** — git-tracked, contains real `OPENROUTER_KEY_STANDARD`, `HF_TOKEN_LLM`, etc. 142 secret-looking lines. **DELETE from git history (`git rm --cached` at minimum) + ROTATE the `OPENROUTER_KEY_STANDARD` keyspace.** **Priority: P0 SECURITY.**
- `.env.local` is in `.gitignore`, not tracked — OK.

### D.5 — POL repo — tracked-but-gitignored data bloat (`/home/termius/nomos-political-alpha/`)

`.gitignore` has `data/polymarket/`, `data/social/`, `data/kalshi/`, etc., but **`git ls-files` still returns 1168 files** under those paths — added before the gitignore rule. Repo is 293 MB total.

```bash
git rm -r --cached data/polymarket data/social data/kalshi data/signals data/insider data/donors data/congressional data/historical
git commit -m "stop tracking append-only data caches"
```

Will shrink working-copy-checked-in size dramatically going forward (history size unchanged without `filter-repo`). **Priority: P1.**

---

## E. Decommissioned surfaces (per CLAUDE.md + MEMORY)

### E.1 — 9 dept councils DELETED 2026-04-20

Leftovers in `mon-ipad`:
| Leftover | Size | Action |
|---|---|---|
| `.claude/agents/the-blacksmith.md` | 2 KB | File self-declares NO-OP. **KEEP** per file's own instruction "preserved for future council revival" — but add a `.archived` suffix to remove from dispatch pool. | P2 |
| `data/empire/briefs/the_blacksmith.md` | — | DELETE | P1 |
| `scripts/councils/` | 128 KB | DELETE | **P0** |
| `scripts/departments/` | 200 KB | DELETE | **P0** |
| `council-spaces/` | 52 KB | DELETE | **P0** |
| `data/departments/` | 72 KB | DELETE | **P0** |
| `logs/councils/` | 780 KB | DELETE | **P0** |
| `scripts/councils/sync-to-sister-repos.sh` | 12 KB | **BUT this IS in crontab** — verify if still needed; likely vestigial | VERIFY then DELETE | P0 |

### E.2 — 10 eliminated "nul" islands (S10/S11/S12/S16/S19/S20/S21/P3/P6/P8)

Leftover refs (19 files, non-log). Mostly documented-as-eliminated (fine). Real stale refs to surgically remove:

| File | Action |
|---|---|
| `cross-repo-health.json` (static snapshot, 2026-04-15) | REGENERATE from current fleet; delete old | P1 |
| `scripts/evolution/island-targets.json` | Update to 11 survivors | P1 |
| `scripts/arena/hf-llm-gateway/app.py` | Check if routing table has dead islands | P2 |
| `OPERATIONS.md`, `scripts/agent-log.sh` | Update or delete per B.1 decision | P1 |
| `scripts/monitoring/tmux-dashboard.sh`, `scripts/monitoring/live-status.py` | Check if used; dashboards may still list dead islands | P2 |

### E.3 — rag-website (decommissioned 2026-04-20)

Grep shows leftover refs in only 2 files (both historical records):
- `CLAUDE.md` line "rag-website | -- | none | DECOMMISSIONED 2026-04-20" — **KEEP** (historical record)
- `data/ops/cross-repo-improvements-2026-04-20.md` — **KEEP** (dated audit report)

**No cleanup needed.**

### E.4 — Factory / nomos-pierre / nomos-picks

- `/home/termius/nomos-pierre` (2.2 MB) and `/home/termius/nomos-picks` (2.6 MB) are on disk but not in CLAUDE.md ecosystem table and not scanned here. Flag for owner decision (P2).
- Factory artifacts in `mon-ipad` (`scripts/forge/f0_*.py`, `f1_*.py`, `optimization_patches.py`, `agent-status.py`) — DELETE per C.1.

### E.5 — PQTF FROZEN FOREVER

Active surfaces still referencing PQTF:
| Path | Action |
|---|---|
| `.github/workflows/tf-pqtf-reset.yml` | **DELETE workflow file** (PQTF must NOT be restarted per memory) | **P0** |
| `.github/workflows/deploy-tfs.yml` (has `pqtf` target) | Remove `pqtf` from target list | **P0** |
| `.github/workflows/tf-unstick.yml` (has pqtf) | Remove `pqtf` target | **P0** |
| `scripts/gpu/refresh_pqtf_cache.py` | DELETE (C.1) | P0 |
| `logs/tf-postmortem-pqtf.log` | KEEP (historical) | — |

**This is the single biggest accidental-restart risk in the repo.**

---

## F. `.github/workflows/` audit (mon-ipad)

22 workflow files. Classified by evidence:

| Workflow | Trigger | Script exists? | Status |
|---|---|---|---|
| `arena-engine.yml` | daily | `scripts/arena/arena-engine.py` yes | ACTIVE |
| `backtest-swarm.yml` | 2h | `scripts/arena/backtest_engine.py` yes | ACTIVE |
| `dashboard-qa.yml` | push + daily | `scripts/agents/dashboard_qa_client.py` yes | ACTIVE |
| `deploy-tfs.yml` | manual | has `pqtf` target | **TRIM pqtf** — P0 |
| `engine-parity-check.yml` | schedule | `scripts/check_engine_parity.py` yes | ACTIVE |
| `gemma4-cross-repo-helper.yml` | 6h | `scripts/gemma4/cross-repo-helper.py` yes | ACTIVE (but Phi-3.5 self-host often dead per memory; consider disable) | P2 |
| `gpu-cron-launcher.yml` | 6h | orchestrator | ACTIVE |
| `itf-ci.yml` | PR/push | test file | ACTIVE |
| `itf-tick.yml` | 15 min market hours | — | ACTIVE |
| `karpathy-tuning.yml` | 6h | `scripts/karpathy/nba_iterate.py` yes | ACTIVE |
| `lightning-burst.yml` | 2x/day | `scripts/lightning/launch_karpathy.py` yes | ACTIVE |
| `modal-burst.yml` | 4h | `scripts/gpu-burst/modal-burst.py` yes | ACTIVE |
| `paperspace-burst.yml` | 8h | `scripts/paperspace/launch_karpathy.py` yes | ACTIVE (memory says Paperspace "SETUP IN PROGRESS" — may be 0% success rate) | P2 |
| `pixel-qa.yml` | push to pixel-world | — | ACTIVE |
| `repo-inventory.yml` | daily | `scripts/inventory/repo-inventory.py` yes | ACTIVE |
| `scientific-experiment.yml` | 4h | `scripts/scientific-experiment.py` yes | ACTIVE |
| `tf-nba-reset.yml` | manual | — | ACTIVE |
| `tf-pol-reset.yml` | manual | — | ACTIVE |
| `tf-pqtf-reset.yml` | manual | — | **DELETE** (E.5) — **P0** |
| `tf-unstick.yml` | manual | has pqtf | **TRIM pqtf** | P0 |
| `trading-floor.yml` | manual | monitor-only | ACTIVE |
| `youtube-sentiment.yml` | 6h | `scripts/youtube_sentiment_precompute.py` yes | ACTIVE |

**Recommend:** `P0 DELETE tf-pqtf-reset.yml` + remove PQTF branches from `deploy-tfs.yml` and `tf-unstick.yml`. Run with `gh run list --workflow=<name>` to confirm >30d no-run for `paperspace-burst.yml` and `gemma4-cross-repo-helper.yml` before disabling.

---

## Cross-repo bonus findings

### Nomos-dashboard (`/home/termius/nomos-dashboard`, 1.8 GB)

- `.next/` 607 MB + `node_modules/` 1.2 GB = 100% of bloat, both gitignored. **No action** (standard Next.js footprint).
- `tsconfig.tsbuildinfo` 2.1 MB exists locally but gitignored. Fine.
- Active (last commit 2026-04-24, cron-driven `tf-analytics` sync). KEEP as-is.

### Nomos-political-alpha (`/home/termius/nomos-political-alpha`, 293 MB)

- Real code = `scripts/`, `features/`, `hf-space/`, `ops/`. ~3 MB.
- 236 MB = `data/` bloat (1249 polymarket snapshots + 565 social-signal dumps). See D.5.
- 27 MB = `logs/agents/`. Rotate.

### `/home/termius/mon-ipad-worktrees/` (325 MB, 2 worktrees both at 2026-04-19)

Abandoned worktrees `gateway-fix` and `tf-experiments`. `git worktree remove` on each. **P0.**

### `/home/termius/nomos42-migration-20260410-195735.tar.gz` (3.5 MB, from April 10)

One-shot migration bundle. Either restore-and-delete, or move to cold storage. **P0** (just move out).

### `/home/termius/rgwa` (9.9 MB, ZOMBIE)

See A.3 — full delete. **P0.**

---

## Execution order if user approves

**Phase 0 — Security (within 1 hour):**
1. Rotate `OPENROUTER_KEY_STANDARD` at OpenRouter.
2. `git -C /home/termius/mon-ipad rm --cached migration-kit/04-credentials.env` + commit + push.
3. Consider `git filter-repo` to purge from history.

**Phase 1 — P0 deletions (estimated 10 min, ~495 MB freed):**
```
# outside repos
git -C /home/termius/mon-ipad worktree remove /home/termius/mon-ipad-worktrees/gateway-fix
git -C /home/termius/mon-ipad worktree remove /home/termius/mon-ipad-worktrees/tf-experiments
mv /home/termius/nomos42-migration-20260410-195735.tar.gz ~/archive/
rm -rf /home/termius/rgwa

# inside mon-ipad
cd /home/termius/mon-ipad
rm -rf scripts/councils scripts/departments council-spaces data/departments
rm -rf scripts/patches  # only __pycache__
rm -rf hf-brain hf-agents hf-spaces
rm -rf vendor/oasis vendor/TradingAgents
rm -rf nba-quant-space   # has own .git — verify HF Space is the real source of truth first
rm -rf nomos-political-alpha  # duplicate nested clone
rm scripts/arena/oasis_t3_swarm.py
rm scripts/gpu/refresh_pqtf_cache.py
rm scripts/forge/f0_strategy_definer.py scripts/forge/f1_product_builder.py scripts/forge/optimization_patches.py scripts/forge/agent-status.py
rm .github/workflows/tf-pqtf-reset.yml
rm data/arena/council/council-iter-*.json
truncate -s 0 data/research-vault-cron.log
mv data/research-vault-cron.log logs/
```

**Phase 2 — P1 consolidation:**
- Merge `OPERATIONS.md`, `DESIGN.md`, `MONETIZATION.md`, `ULTRAPLAN-COMMANDS.md` deltas into `CLAUDE.md` + `docs/` then delete originals.
- Move 18 orphan `agent-memory/` dirs to `.claude/agent-memory/_deprecated/`.
- POL: `git rm -r --cached data/{polymarket,social,kalshi,…}` and commit.
- Log rotate `data/monitor/cycle-*.json` >24h old.

**Phase 3 — P2 review:**
- `docs/social-media/*` — archive if no Q2 launch planned.
- Audit `paperspace-burst.yml` + `gemma4-cross-repo-helper.yml` for success rate.
- Decide on `/home/termius/nomos-pierre` and `/home/termius/nomos-picks`.

---

*Audit generated 2026-04-24 by cross-repo cleanup sweep. Report-only, no files modified.*
