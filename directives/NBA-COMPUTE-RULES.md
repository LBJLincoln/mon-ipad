# NBA QUANT AI — COMPUTE RULES

> **Last updated:** 2026-03-25
> **Applies to:** ALL repos (mon-ipad, nomos-nba-agent)

## RULE #1: ZERO ML ON VM

The VM (`34.136.180.66`) has **1 vCPU / 969 MB RAM / 30 GB disk**.

**It CANNOT and MUST NOT run any ML workload.** Every time we try, OOM kills the process.

### What RUNS on VM (ONLY these):
| Process | Script | RAM | Purpose |
|---------|--------|-----|---------|
| nba-data-server | `scripts/nba-data-server.py` | ~12 MB | Serve JSON to Vercel website |
| Claude Code | Termius session | ~100 MB | Pilotage, git, deployment |
| Crons | keepalive, odds, autonomous-cycle | ~15 MB | Scheduling |

### What RUNS on HF Spaces (ALL ML):
| Space | Role | Config | Status |
|-------|------|--------|--------|
| S10 nomos-nba-quant | Exploitation | mut=0.09, cx=0.80, pop=60, feat=63 | EVOLVING |
| S11 nomos-nba-quant-2 | Exploration | mut=0.15, pop=60, feat=80 | EVOLVING |
| S12 nba-evo-3 | Extra-trees specialist | mut=0.08, pop=60, feat=60 | EVOLVING |
| S13 nba-evo-4 | CatBoost specialist | mut=0.10, pop=60, feat=66 | EVOLVING |
| S14 nba-evo-5 | LightGBM specialist | mut=0.08, pop=60, feat=55 | EVOLVING |
| S15 nba-evo-6 | Wide search | mut=0.18, pop=50, feat=80 | EVOLVING |

### What SHOULD run on GPU (Colab / Lightning.ai):
| Process | Platform | Purpose |
|---------|----------|---------|
| TabICLv2 eval | Google Colab T4 | Transformer tabular model evaluation |
| Neural evolution | Lightning.ai T4 | GPU-accelerated deep learning (after Apr 1) |

## RULE #2: FEATURE ENGINE PARITY

**Engine version:** v3.1-46cat = 46 categories, 6253 raw features
- `features/engine.py` = `hf-space/features/engine.py` ALWAYS
- `deploy_island.py` checks parity before deploying

## RULE #3: EVOLUTION CONSTRAINTS (2026-03-25)

- **MAX_FEATURES=200** — hard cap enforced in init/mutate/crossover
- **Mutation cap**: adaptive mutation capped at 0.15 (was 0.25)
  - Deployed: S10, S11, S12, S15
  - Still on old cap: S13, S14
- **CPU-only models**: tree-based only (random_forest, extra_trees, xgboost, lightgbm, catboost)
  - Neural models removed (brier=0.28 penalty on CPU)
  - Stacking removed (200 gens, best=0.24738 — 10% worse)
- **xgboost_brier**: objective signature fixed for XGBoost >=2.0: `(y_true, y_pred)`

## RULE #4: DEPLOY SCRIPT

To update a Space's code:
```bash
python3 hf-space/deploy_island.py SPACE_NAME ROLE HF_TOKEN
```

## RULE #5: SUPABASE STATUS

- Primary (ayqviq...) — **PAUSED** (returns 402)
- Secondary (xivvnr...) — DNS issues
- **Active**: pooler connection for queries
- All experiments tagged with `feature_engine_version`

## HF Accounts
| Account | Token | Spaces |
|---------|-------|--------|
| Nomos42 | HF_TOKEN_3 | S10, S11, S12, S13, S14, S15 (all 6 NBA islands) |
| LBJLincoln | HF_TOKEN | LBJLincoln spaces (auxiliary) |
| LBJLincoln26 | HF_TOKEN_2 | LBJLincoln26 spaces (secondary) |
