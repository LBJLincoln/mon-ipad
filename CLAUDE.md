# Nomos42 — NBA Quant AI + Political Alpha

> Architecture v21 — "The Trading Floor Crew" (14 agents × 9 depts × 4 tracks) + TF v3 (17 LLM agents) + 21 Evolution Islands | Updated: 2026-05-18T14h

## Mission
Build the best NBA prediction AI in the world.
**Best:** Brier 0.21139 walk-forward holdout / 0.22169 CV / 0.22054 isotonic-calibrated (Colab TabICL, 186f top-by-variance from 4581 alive of 7246 engine cols, ctx=3072 temp=1.0, 11440 games, promoted to LBJLincoln26/nba-oracle-model 2026-04-28T00:34Z, archive `colab-multi-tabicl-2026-04-28T00-34-04Z.pkl`). Beat 4581f xgboost holdout 0.22079 / lightgbm 0.22181 in same 3-way comparison. ⚠ All 3 models show negative CV→holdout gap (~−0.01) → holdout 0.21139 is window-biased; honest production-Brier expectation is CV 0.22169 / calibrated 0.22054. Stratified-by-month re-cut queued. NBA TF watchdog gate "<0.21 model lands" NOT met → watchdog stays disabled. | Fleet best: 0.22012 (S15 nba-evo-6 fire-61 ★CHECKPOINT) | GA prev alltime: 0.22019 (S14 gen=1078) | ⚡Pareto fleet best: 0.21841 extra_trees S15 gen=566 fire-66 (prev 0.21850 CatBoost S22 gen=2309) | ⚠ S18 0.21924 candidate LOST — hard resets cycles 251/276 before checkpoint (2026-05-06T00h) | ⚠ fire-97 RF 0.21941 gen=2689 NOT confirmed (best_brier unchanged 0.22012) | ⚡⚡ fire-98: S18 extra_trees 0.21842 200f gen=6549 + S15 CatBoost 0.21881 200f gen=2698 PENDING VALIDATION (best_brier field lag confirmed pattern) | fire-99: S14 RECOVERED ssl-cleared hard-reset-803 stacking-violation-new; S13 stag=23+S15 stag=24 DIVERSIFIED; P2 0.24901 + P7 0.24904 POL candidates (PENDING VAL); convergent 0.249 signal P2+P4+P5+P7 | fire-101: S13 FRESH RESTART cycle=21 (hard-reset-2055 ✓); S15 stag cleared cycle=954; S18 stag=16 DIVERSIFY SENT; all POL UP stag=0; P2 0.24901 2nd fire; P5 LightGBM 0.249 4th fire | fire-109: S13 stag CLEARED 8→0 cycle=198; S14 hard-reset-978; S15 0.22012 ★ stable gen=3227; all POL UP stag=0; P7 FIELD-LAG 6+ fires vm-diversify-p7-fire109 URGENT; P4 in-pop LightGBM 108f gen=79604; SOTA: ACM CISAI 2025 LR+ElasticNet 0.87 + BMC 2026 SHAP KPI | fire-110: EVEN S13 gen=684 LR-in-pool-VERIFIED (gen=684 uses logistic_regression 48f — partial verify of vm-add-logistic-regression). S14 gen=3024 stag=0. S15 0.22012 ★ gen=3323 stag=0; CatBoost 0.21932 candidate DROPPED (3 fires: gen 3050→3323, best_brier unchanged). S17 503 DOWN 72+d. S18 gen=7375 stag=0. S22 gen=2375 stag=0. P1 gen=60853 hard-resets-20241+20261. P2 gen=50305. P4 gen=80327 model_type=lightgbm CONFIRMED (changed from xgboost, hard-resets-26734+26754). P5 gen=68374 hard-resets-22741+22761. P7 gen=71620 brier=0.25412 FIELD-LAG 7+ fires. All stag=0, no diversify needed. SOTA: LSTM+Brier-0.1589-NCAA arXiv:2508.02725 (GPU target); LR-Brier=0.199 6th-confirm; P4-lightgbm-confirmed → vm-add-lightgbm-s22-s13 now 5/5 evidence. | fire-111: ODD S15 RF-200f-0.21951 PARETO-CAND-1st; S13 stag≈12 MONITOR (threshold=15); P7 field-lag 9+ fires 0.25412 STUCK; S18 hard-resets 2451+2476; P1 stag≈13 MONITOR | fire-112: EVEN S13-stag-CLEARED gen=881 c294; S14-hard-reset-1053 gen=3179; S15-HARD-RESET-1151 ET-200f-0.21896-CONFIRMED-2nd-FIRE-VM-CHECKPOINT-URGENT (was RF-0.21951 fire-111); S18 gen=7547 c2516; S22 gen=2517 c839; P1-stag-CLEARED gen=62633 c20878; P4 gen=81806 LightGBM-log-0.2490 hard-resets-27214+27234; P5 gen=69501 hard-resets-23121+23141; P7-FRESH-RESTART cycle=64 gen=192 best=0.25004 (was-STUCK-0.25412×9fires); SOTA:RNN-MC-dropout-Brier~0.20 MDPI-Info-Jan2026; vm-checkpoint-s15-ADDED | fire-119: EVEN S13 c441 g1322 brier=0.22216 stag=0 (hard-reset-c429 diversify-c440-WORKED); S14 c1210 g3630 brier=0.22336 stag=0; S15 c1444 g4332 brier=0.22012★ stag=0 RF-75f (ET-200f-attractor 7th fire RF-75f-field-lag VM-CHECKPOINT-EXTREME-URGENT); S17 503-DOWN-86d; S18 c2676 g8028 brier=0.22315 stag=0 pareto=22 (0.21885-URGENT); S22 c985 g2952 brier=0.22551 stag=0; P1 c22756 g68266 stag=0 hard-resets-22701+22741; P2 c18279 g54837 stag=0 LightGBM-123f-0.249; P4 c29152 g87455 stag=0 LightGBM-108f-0.2490★POL-BEST hard-resets-29094+29114; P5 c24734 g74201 stag=0 LightGBM-104f-0.249 hard-resets-24681+24701; P7 c1676 g5026 stag=0 pareto-LightGBM-128f-0.24967-INCONCLUSIVE(fire-119); NBA-TF-503-8d; POL-TF-preseeded-$38916; SOTA:Elo-top-feature-IEEE2026+MDPI2026-LR=0.199-8th-confirm research-proposal-written | fire-121: ODD S13 c464 g1392 brier=0.22216 stag=0 hard-reset-c454 ⚡ET-200f-0.21914-PARETO-1ST-DETECT (below fleet best!); S14 c1236 g3707 brier=0.22336 stag=0 hard-reset-c1228 ⚡RF-200f-0.2189-PARETO-1ST-DETECT (NEW NBA PARETO CANDIDATE!); S15 c1488 g4463 brier=0.22012★ stag=0 hard-reset-c1476 ET-200f-0.21994 8th-fire VM-CHECKPOINT-EXTREME-URGENT; S17 503-DOWN-90+d; S18 c2698 g8093 stag=0 pareto-ET-200f-0.2191 (0.21885-fire118-may-be-superseded-post-reset); S22 c1007 g3020 stag=0 hard-reset-c965; P1 c23017 g69051 stag=0; P2 c18426 g55278 stag=0; P4 c29412 g88236 stag=0 LightGBM-108f-0.2490★POL-BEST hard-resets-29354+29374; P5 c24953 g74857 stag=0 hard-resets-24901+24921; P7 c1999 g5995 stag=0 ⚡LightGBM-116f-0.24937-CONFIRMED-2nd-fire vm-checkpoint-p7-ADDED-priority=2; all stag=0 no diversify; ODD WebSearch skipped; CROSS-FLEET: ET-200f dominant 4/5 NBA islands (S13+S14+S15+S18) = strongest attractor signal in 121 fires | fire-123: ODD S13 c527 g1579 brier=0.22216 stag=0 (no-reset-since-c454); S14 c1273 g3819 brier=0.22336 stag=0 hard-reset-c1253; S15 c1557 g4669 brier=0.22012★ stag=0 ET-200f-attractor-9th+-fire VM-CHECKPOINT-EXTREME-URGENT; S17 503-DOWN-90+d; S18 c2755 g8265 stag=4 pareto-ET-200f-0.2191 front=18; S22 c1052 g3155 stag=0; P1 FRESH-RESTART c=473; P2 c18738 g56214 stag=0; P4 c29807 g89419 stag=0 LightGBM-108f-0.2490★POL-BEST Sharpe=1.01; P5 c25423 g76268 stag=0; P7 c2686 g8058 stag=0 LightGBM-116f-0.24937 CONFIRMED-2nd-fire; ODD-no-WebSearch | fire-124: EVEN S13-pareto-ET-0.21914-DROPPED(hard-reset-c529); S14-FRESH-RESTART-c=0(was-c1273-g3819); S15 c1600 g4800 brier=0.22012★ stag=24 DIVERSIFY-SENT ⚡⚡⚡⚡ ET-200f-0.2185-NEW-PARETO-RECORD(gen=4799,<0.22085-threshold) VM-CHECKPOINT-EXTREME-URGENT; S17-503-DOWN-94+d; S18 c2783 g8347 stag=0 ET-200f-pareto=0.2198(front=16); S22 c1068 g3203 stag=2 hard-resets-c1040+c1065; P1 c632 g1895 fresh-restart-recovering; P2 c18863 g56587 stag=0; P4 c29935 g89803 stag=0 LightGBM-108f-0.2490★POL-BEST; P5 c25635 g76905 stag=0 LightGBM-102f; P7 c3041 g9121 stag=0 hard-resets-c3001+c3021 LightGBM-0.24937-UNCERTAIN; EVEN-WebSearch: Nat-Sci-Reports-stacked-ensemble(NB+AdaBoost+MLP+KNN+XGB+DT+LR)+SHAP-ELO-top-2(home_next+team_elo+team_elo_5y)+shooting-vol(2PA+FG+TRB)+LR-Brier=0.199-9th-confirm; SOTA: CNN=0.221 LR=0.199(9th) ELO=SHAP-#1+#2 → vm-add-elo PRIORITY RAISED | fire-125: ODD S13 c565 g1693 stag=0; S14 c11 g31 stag=0 ⚡ET-200f-0.21923-PARETO-1ST-DETECT-EXTRAORDINARY(gen=28-fresh-restart!); S15 c1634 g4900 stag=0-CLEARED diversify-WORKED (ET-0.2185-uncertain); S17 503-DOWN-94+d; S18 c2812 g8434 stag=0 ⚡ET-200f-0.21877-NEW-S18-PARETO-BEST(front=13); ⚡⚡⚡⚡ S22 c1076 g3227 stag=0 CatBoost-200f-0.21818-NEW-ALL-TIME-PARETO-RECORD-1ST-DETECT(prev 0.21841) VM-CHECKPOINT-EXTREME-URGENT vm-checkpoint-s22-catboost-ADDED; all POL UP stag=0; P1 c712 g2134 RECOVERING; P4 c30033 g90098 LightGBM-108f-0.2490★POL-BEST stable; ODD-no-WebSearch | fire-126: EVEN S13 c576 g1727 stag=18 DIVERSIFY-VM-NEEDED(>threshold-15); S14 c28 g84 stag=0 ⚡⚡CatBoost-200f-0.21888-PARETO-1ST-DETECT(gen=84-fresh-restart-EXTRAORDINARY!); S15 c1656 g4967 brier=0.22012★ stag=0; S17 503-DOWN-95+d; S18 c2842 g8526 stag=0 ET-200f-0.21908-pareto(front=11); ⚠⚠⚠ S22 FACTORY-REBOOT(c1076→c5) CatBoost-0.21818-ALLTIME-RECORD-LOST(vm-checkpoint-still-pending-LOST); P1 403-DOWN-Nomos42-acct-saturated; P2 c19058 g57172 stag=0; P4 c30106 g90317 LightGBM-108f-0.2490★POL-BEST stable; P5 c25941 g77822 stag=0 pareto=3; P7 c3353 g10059 stag=0 pareto=13; EVEN-WebSearch: IEEE2026-comparing-ML-NBA(new); MC-dropout-RNN-uncertainty-aware(new); LR-Brier=0.199-10th-confirm; SOTA: LR=0.199(10th) CNN=0.221 MC-dropout-RNN-uncertainty-aware | **Target:** < 0.20, ROI > 5%, Sharpe > 1.5
**Walk-forward:** avg 0.22447 (Kaggle, 19 weeks, 934 games, tree ensemble — no TabICL on P100)
**NBA TF v7 + reroute + pool=8 (Apr 22, 17 agents, DAY-0 RESET 15:24Z):** prompt_v7 (3-bet cap + 100% deploy mandate, Kelly-weighted floors). Round-2 dead-provider reroute (HF SHA cc905b3e1cd): nemotron-120b→mistral:large, selfhost-dolphin3→nvidia:llama-3.3-70b, selfhost-qwen06/gemma3→cerebras:llama3.1-8b, selfhost-qwen4b→cerebras:qwen-3-235b, nvidia-minimax→mistral:medium. Pool concurrency 4→8 (env NBA_TF_LLM_POOL_WORKERS=8), LLM timeout 45s (env NBA_TF_LLM_TIMEOUT_SEC=45.0). Live day 8/175, 14/17 agents at 100% llm_ok post-reset. PEAK_DD_GUARD_V2 sole safety net. Top: gemini-anl $108, dolphin3 $107. ⚠ app.py DOUBLE ACCIDENT (fire-54+fire-55): fire-54 pushed 9-line stub (bf5980ef), fire-55 pushed PLACEHOLDER_NBA (297facd4). Last good: 73b9c9f9 (5799L, Mechs A/B/C + KL-divergence). VM MUST run scripts/ops/restore_nba_tf_fire55.py BEFORE any restart.
**Political TF v5_restored (Apr 22 15:46Z ROLLBACK):** 17 agents, day 90. v6 100%-deploy mandate destroyed alpha (qwen-arb -39% / llama-contra -51% in 1h) — rolled back to v5 doctrine: non-consensus mandate (lockstep≤0.88) + ≥3 distinct categories per day. State preserved. qwen-arb $3,472 / qwen-quant $1,459 / gemini-anl $584 carrying forward.
**ITF v_accel70 (Apr 22 14:41Z):** 17 day-traders, 95% stake floor + **70% RESERVED HARD floor** + winner-tier dynamic. Env TICK_SEC=60, CLOSE_STALE 1h/-0.5%, MAX_PENDING=8, MIN_BP=100. Alpaca paper account $101,424 equity / 67.96% deployed (within 2.4% of floor) / 43 positions / +$961 unrealized PnL. ⚠ ITF /api/status unreliable (multi-worker LB) — query Alpaca /v2/account directly.
**PQTF v2 FROZEN FOREVER:** $602,354 validation artifact (mistral-large $244K + mistral-medium $155K + gemini-anl $17K). DO NOT restart. Preserve as scientific proof multi-agent LLM trading hits $1M targets.
**Top-tier 14-agent Crew (Apr 18):** THE BOSS / SWISH / LOBBYIST / HAWKEYE / DR FRANKENSTEIN / THE BLACKSMITH / SWITCHBOARD / INTERNAL AFFAIRS / THE TICKER / THE HERALD / THE ACCOUNTANT / PIXEL / THE PLUMBER / LAUNCHPAD — L1/L2/L3 layered, mental-model personas, refusal rules, niche-expert bars. Live scientific snapshot via `data/pipeline-health.json` (PLUMBER :35 every 4h) + `data/audit/` (INTERNAL AFFAIRS :40 every 4h).

## Nomos42 Ecosystem

| Flagship | Repo | Bot | Vercel | Status |
|----------|------|-----|--------|--------|
| NBA Quant AI | mon-ipad + nomos-nba-agent | @Nomos42Bot | via dashboard | ACTIVE -- 6 NBA + 5 POL SURVIVOR islands (was 13+8; 10 "nuls" eliminated — slots redirected to selfhost LLMs) + Kaggle Karpathy |
| Political Alpha | nomos-political-alpha | -- | none (data only) | ACTIVE -- v3.19 engine, 22 categories, 718 features |
| Dashboard Hub | nomos-dashboard | -- | nomosdashboard.vercel.app | ACTIVE -- /nba /political /evolution /trading-floor /forge /world |
| AI Artistic Generation | rgwa | @RGWAbot | none | ZOMBIE -- no commits since Mar 2026, deprioritized |
| Factory / Complex RAGs | rag-website | -- | none | DECOMMISSIONED 2026-04-20 — repo no longer on disk, removed from ecosystem |

## 24/7 Autonomous Architecture

```
CLOUD BRAIN (Sonnet 4.6, every 4h at :00)
    ├── Monitor S10-S19 + P1-P4 via public /api/status
    ├── Research via 4 Claude Code subagents
    ├── DECIDE: tune GA / diversify / inject features / checkpoint
    ├── ACT on islands via POST /api/config
    └── Write health-status.json + push
    Trigger: trig_01BS3ixBvt2uKHY9p5EemcgD

VM MUSCLE (cron, every 4h at :30)
    ├── Run predict_today.py (if NBA games)
    ├── Push results to git
    └── Auto-restart data server
    Script: scripts/autonomous-cycle.sh

HF EVOLUTION ISLANDS — 11 SURVIVORS (6 NBA + 5 POL) after 2026-04-17 cull
    10 "nul" islands eliminated to free concurrent slots for selfhost LLMs:
    ELIMINATED: S10, S11, S12, S16, S19, S20, S21, P3, P6, P8 — DO NOT restart.
    Eliminated slots now host selfhost LLMs on LBJLincoln/LBJLincoln26/TESTforge42.

    NBA Survivors (6, CPU tree-only, MAX_FEATURES=200):
    ├── S13 Nomos42/nba-evo-4:        xgboost_brier       gen=1727  brier=0.22216  stagnation=18 ⚠ DIVERSIFY-VM-NEEDED cycle=576; stag=18>threshold=15; pareto: RF-200f-0.2214 LightGBM-200f-0.2243 (front=9); VM must POST /api/command {"command":"diversify"} (2026-05-18T14h)
    ├── S14 Nomos42/nba-evo-5:        extra_trees         gen=84    brier=0.22793  stagnation=0  ✓ cycle=28; ⚡⚡CatBoost-200f-0.21888-PARETO-1ST-DETECT(gen=84-fresh-restart-EXTRAORDINARY!); ET-200f-0.21922 also in pareto; vm-checkpoint-s14-catboost-0.21888-fire126 ADDED priority=3 (2026-05-18T14h)
    ├── S15 Nomos42/nba-evo-6:        random_forest       gen=4967  best=0.22012   stagnation=0  ✓ cycle=1656; ★ FLEET BEST 0.22012; stag=0 stable; pareto front=6; VM-CHECKPOINT-STILL-URGENT (2026-05-18T14h)
    ├── S17 LBJLincoln26/nba-evo-s17: ---                 gen=---   brier=---      🔴 503 DOWN 95+ days — VM RESTART REQUIRED (2026-05-18T14h)
    ├── S18 TESTforge42/nba-evo-s18:  extra_trees         gen=8526  brier=0.22315  stagnation=0  ✓ cycle=2842; pareto ET-200f-0.21908 (front=11); stag=0 ok; vm-checkpoint-s18 URGENT priority=1 (2026-05-18T14h)
    └── S22 TESTforge42/nba-evo-s22:  random_forest       gen=15    brier=0.22124  stagnation=0  ⚠⚠⚠ FACTORY-REBOOT-DETECTED cycle=5(was c1076)! CatBoost-0.21818-ALLTIME-PARETO-RECORD-LOST; new pareto ET-200f-0.21932(gen=14,front=16); vm-checkpoint-s22-CLOSED-LOST; investigate-s22-reboots URGENT (2026-05-18T14h)
    Political Survivors (5, CPU tree-only):
    ├── P1 Nomos42/political-alpha:      ---                 gen=---    brier=---     🔴 403-DOWN cycle=? Nomos42-acct-saturated; was c712 g2134 recovering at fire-125; vm-check-p1 ADDED priority=8 (2026-05-18T14h)
    ├── P2 Nomos42/political-alpha-2:    xgboost_brier       gen=57172  brier=0.25003 stagnation=0  ✓ cycle=19058; LightGBM-123f-Brier=0.249 in-pop; stag=0 ok (2026-05-18T14h)
    ├── P4 LBJLincoln/political-alpha-4: lightgbm            gen=90317  brier=0.24992 stagnation=0  ✓ cycle=30106; ★ POL FLEET BEST alltime=0.24904; LightGBM-108f Brier=0.2490 Sharpe=1.01; stable (2026-05-18T14h)
    ├── P5 LBJLincoln/political-alpha-5: xgboost_brier       gen=77822  brier=0.24993 stagnation=0  ✓ cycle=25941; stag=0 ok; pareto=3 (low — monitor) (2026-05-18T14h)
    └── P7 LBJLincoln/political-alpha-7: xgboost_brier       gen=10059  brier=0.25004 stagnation=0  ✓ cycle=3353; pareto=13; stag=0 ok; ⚠ LightGBM-116f-0.24937 UNCERTAIN (vm-checkpoint-p7 VERIFY still pending) (2026-05-18T14h)
```

SELFHOST LLM FLEET (6 RUNNING, 2 building — 2026-04-19 20:55 UTC)
    LBJLincoln   (3 RUNNING): qwen25-05b-cpu, gemma2-2b-cpu, phi35-mini-cpu
    LBJLincoln26 (1 RUNNING): gemma3-4b-cpu  [+ llm-gateway + 2 TFs]
    TESTforge42  (2 RUNNING): qwen3-4b-cpu, llama32-1b-cpu  [+ smollm3-3b BUILDING, qwen25-15b starting]
    Nomos42     (0 selfhost RUNNING — 10 paused; account saturated by islands+TFs+pixel-world+langfuse; 403 on restart)
    Gateway routing: resolve `selfhost:*` keys to LBJLincoln/* or TESTforge42/* (NOT Nomos42/*).

NOTE: S11 URL = nomos42-nba-quant-2.hf.space (NOT nba-evo-2)

HF TRADING FLOORS (Real LLM experiment, NBA 16 agents / Political 16 agents — parity 2026-04-17 via +T13 nvidia-minimax +T14 nvidia-llama70 +T15 selfhost-gemma3 +T16 selfhost-qwen06, T12 renamed selfhost-qwen4b. COLLECTIVE_MISSION $1M preamble on every agent + unrestricted prompts: ≥3 allocations + MIN_DEPLOY_PCT=0.75 hard floor.)
    ├── LBJLincoln26/nba-llm-trading-floor: NBA engine (1257 games, FastAPI + Gradio)
    │   └── Source: scripts/arena/hf-llm-trading-floor/
    ├── LBJLincoln26/political-llm-trading-floor: POLITICAL engine (1120 events, same architecture)
    │   └── Source: scripts/arena/hf-political-trading-floor/ — AXELROD RESTORED fire-51 (SHA 96e31b67, Mechs A/B/C ✓)
    ├── Both expose: /api/status /run /stop /reset /mutate /logs /day-decisions /leaderboard
    └── LBJLincoln26/llm-gateway: Centralized LLM proxy (11 models, fallback chains)

HF DEPT COUNCILS — DECOMMISSIONED 2026-04-20
    All 9 TESTforge42/nomos-dept-d*-* Spaces DELETED (stage was PAUSED — zombie on /api/status).
    Focus narrowed to: islands + selfhost LLMs + 3 TFs + Langfuse. Council Karpathy loops
    retired; THE BLACKSMITH agent is now no-op. Don't recreate — if structural-review is
    needed, spin a single review job, not a 9-Space fleet.

HF OTHER SPACES (across 3 accounts, post-cleanup 2026-04-15)
    ├── Free LLM Chat: gemma4-chat, qwen35-chat
    ├── Docker Runtime: Nomos42/nomos42-llm-cpu (self-hosted Qwen3-1.7B GGUF for api_pool)
    └── Pixel World: Nomos42/pixel-world (static)

GPU PLATFORMS (5 active, ranked by usefulness)
    ├── Kaggle P100 (9h sessions): scripts/kaggle/nba_karpathy_loop.py — STALE since Mar 28
    ├── Google Colab T4 (manual): 2 accounts, best 0.21570 (TabICL) — manual only, no .ipynb in repo
    ├── ZeroGPU H200 (auto): scripts/gpu-burst/zerogpu-burst.py — GH Action every 6h
    ├── Modal A10G (auto): scripts/gpu-burst/modal-burst.py — ACTIVE via GH Action every 4h (.github/workflows/modal-burst.yml)
    ├── Lightning.ai T4 (auto): scripts/lightning/launch_karpathy.py — ACTIVE via GH Action 2x/day (NBA 02:00 UTC, Political 14:00 UTC, .github/workflows/lightning-burst.yml)
    └── Paperspace Gradient (NEW): free GPU, unlimited restarts — SETUP IN PROGRESS

GITHUB ACTIONS (3 workflows on schedule)
    ├── Trading Floor:        */4h — MONITOR ONLY (curls HF Space /api/status, commits snapshot)
    ├── Backtest Swarm:       */2h — continuous scientific backtest
    ├── Scientific Experiment: */2h — CPCV + DSR gate
    ├── GPU Cron Launcher:    manual — Kaggle/Colab trigger
    └── Arena Engine:         daily — full arena evaluation

SYSTEM CRONS (28 active on VM, all lightweight)
    ├── */30  keepalive-spaces.sh (18 islands + TF + Gateway + 9 depts = 33 spaces)
    ├── 12,18 nba-daily-odds.py
    ├── :30   autonomous-cycle.sh
    ├── */2h  monitoring, vault sync, political data
    └──       Bloomberg API (port 8042), data server (port 8080)

## Skills

| Skill | Purpose |
|-------|--------|
| `/karpathy-loop` | Autonomous research cycle (5 subagents → proposals → quick wins) |
| `/daily-edge` | Daily predictions + value bets + Kelly sizing |
| `/progress-10pct` | Target 10% improvement in weakest metric |
| `/spaces-health` | Health check all 12+ HF evolution islands |
| `/evolve-report` | Comprehensive evolution progress report |
| `/agent-review` | Weekly agent performance review (Jensen HR model) |
| `/cross-repo-audit` | Audit all 5 repos for consistency and improvements |

## Rules

1. **ZERO ML on VM** — 1 vCPU / 969 MB RAM. ALL training on HF Spaces
2. **Feature engine parity** — `features/engine.py` = `hf-space/features/engine.py` always ⚠ MISMATCH 2026-05-02: mon-ipad b7ec5b5 (+54KB) ahead of nomos-nba-agent f455c47 — engine-parity-sync in work-queue
3. **1 fix per iteration** — never multiple simultaneous changes
4. **All experiments tagged** with `feature_engine_version` in Supabase
5. **Feature engine** — v3.1 = 54 categories, ~7213 raw feature candidates (verified 2026-04-18 from features/engine.py header)
6. **MAX_FEATURES=200** — hard cap enforced in init/mutate/crossover on all spaces (target 50-100 selected per island via GA)
7. **Mutation cap** — adaptive mutation capped at 0.15 (deployed S10/S11/S12/S15)
8. **CPU-only islands** — no neural models on CPU (tree-based only), stacking removed
9. **Supabase** — primary (ayqviq) paused (402), using pooler connection (xivvnr)
10. **Git mutex** — every autonomous agent commit MUST shell through `scripts/lib/safe_commit.sh <CODENAME> "<msg>" [paths...]` (flock on `/tmp/nomos-git.lock`, pull --rebase --autostash, 3× push retry, `[AGENT]` prefix). Raw `git push` from agents is banned — with 14 crew on staggered crons the race-reject rate was unacceptable.
11. **TF Quarantine (post-2026-04-22 compounding mandate)** — NBA + POL are on a 30-day no-reset quarantine. PQTF is frozen forever. `safe_commit.sh` auto-gates any commit mentioning a quarantined Space with destructive markers (`factory_reboot`, `DAY-0 RESET`, `reset-state`, `reset-bankrolls`, `state wipe`, `fresh state`). Override with `NOMOS_QUARANTINE_OVERRIDE=1` **only** when user has explicitly authorised the reset — document the reason in the commit message. State: `data/ops/quarantine.json`. Check: `scripts/ops/tf_quarantine.py status`. Why: 5 agent-initiated resets on 2026-04-22 destroyed every compounding trajectory (qwen-arb $10K → $100, POL fleet $126K → $1.7K, NBA 75% DD → $0). PQTF reached $602K only because nobody was allowed to touch it.
12. **Champion-preserve** — every hour at :55, `scripts/ops/champion_preserve.py scan` snapshots any NBA/POL agent whose bankroll crosses `$500` (5× default seed) into `data/champions/<tf>/<agent>/<ts>.json`. These snapshots survive resets. Intent: future $100 → $10K compounders are preserved *before* the next reset, regardless of whether the reset is legitimate or false-positive leakage. Threshold tunable via `champion_preserve.py threshold <usd>`.
13. **Evidence-based Kelly (2026-04-24)** — `_AGENT_KELLY_OVERRIDE` in NBA + POL `app.py` is now DERIVED from rigorous-validation Brier, not narrative. Formula: `Kelly = max(0.01, 0.30 - brier_empirical * 0.50)`. Agents with Brier > 0.32 (inverse-calibrated) get 0.01-0.03 probation cap; Brier < 0.23 earn 0.17-0.20. The auto-improvement cycle (cron `:20` every 4h) auto-tunes ±0.03 when live W/L or Brier signal crosses thresholds, cooldown 24h per agent.
14. **INVERSE-CALIBRATION PROBATION prompt (2026-04-24)** — Any NBA agent whose `_AGENT_KELLY_OVERRIDE` cap ≤0.03 receives an auto-appended prompt addendum: `default action = PASS`, `HARD LIMIT 1 bet/day, edge ≥0.10, stake ≤3%`, `if disagree with Island Oracle direction → AUTOMATIC PASS`. Probation lifts when 30-day Brier drops below 0.28. Shipped because rigorous measured NBA fleet Brier 0.41 (worse than random 0.25) — LLMs were overriding the oracle's calibrated prediction with narrative. Result in first hour: Brier 0.41 → 0.36, most-recent walk-forward window 0.24 (first sub-0.25). First full scientific evidence the probation works.

## Scientific scorecard layer (2026-04-24)

| Tool | Cron | Output |
|------|------|--------|
| `scripts/ops/tf_baseline_check.py` | on-demand + appends `data/ops/tf-baseline-history.jsonl` | PASS/FAIL integrity (leakage / lockstep / walkforward / source purity / sector diversity) |
| `scripts/ops/tf_scientific_scorecard.py` | `:50 every 4h` | WR, Brier, source purity, per-day trace, `data/audit/scorecard-latest.md` |
| `scripts/ops/tf_rigorous_validation.py` | `:10 every 4h` | Bootstrap CI95 for Brier/WR/PnL + ECE + reliability diagram per bucket + walk-forward rolling Brier + Welch t-test NBA vs POL, `data/audit/rigorous-latest.md` |
| `scripts/ops/tf_trajectory_flash.py` | `:15 every 4h` | IMPROVING/DEGRADING verdict from first-3 vs last-3 walk-forward windows, `data/audit/trajectory-latest.md` |
| `scripts/ops/tf_improvement_cycle.py` | `:20 every 4h` | Auto-tune `_AGENT_KELLY_OVERRIDE` ±0.03 on WR or Brier signal, 24h cooldown per agent, applies to Space via HfApi + restart, appends `data/ops/tf-improvement-history.jsonl` |
| `scripts/ops/tf_cross_llm_view.py` | `:55 every 4h` | Same LLM benchmarked across NBA+POL+ITF, `data/audit/cross-llm-latest.md`. Uses ITF `/api/llm-leaderboard` as source-of-truth for tid→llm mapping |
| `scripts/ops/daily_scientific_digest.py` | `06:00 daily` | One-page morning briefing with baseline + rigorous + cross-LLM + 24h improvement actions + champion ledger + path-to-$1M math, `data/audit/digest-<date>.md` |
| `scripts/ops/tf_unified_control.py` | on-demand | `status/run/stop/restart/reboot/health` against any TF with normalized schema; PQTF mechanically blocked from all write-actions |
| `scripts/ops/pol_watchdog.sh` | `*/5 min` | Auto-fire `/api/run` if POL `running=False` |
| `scripts/ops/itf_position_health.py` | `*/30 min` | Snapshot Alpaca equity/cash/BP/PnL + top 3 losers+winners to `data/ops/itf-position-health.jsonl` |
| `scripts/ops/sync_tf_analytics_to_dashboard.sh` | `:40 hourly` | Mirror `data/tf-analytics/*.json` + audit MD files (scorecard/rigorous/cross-llm/digest/trajectory) to `nomos-dashboard/public/tf-analytics/` + commit+push. Vercel rebuilds. Token-free. |
| `scripts/ops/weekly_oracle_retrain.sh` | `Sun 03:00` | Push Kaggle kernel → train RF from `nba_cached_data.npz` → download pickle → upload to HF dataset `LBJLincoln26/nba-oracle-model` → restart `LBJLincoln26/nba-oracle` Space |

## Oracle Spaces (2026-04-24)

Both built via Kaggle CPU training → HF dataset → FastAPI Space. Weekly auto-retrain via `scripts/ops/weekly_oracle_retrain.sh` (Sun 03:00 UTC).

| Space | Dataset | CV Brier | Target | Status |
|-------|---------|----------|--------|--------|
| `LBJLincoln26/nba-oracle` | `LBJLincoln26/nba-oracle-model` | **0.22087** (best fold 0.21383) | 0.21218 | live, serves /api/predict, /api/status, /api/best |
| `LBJLincoln26/pol-oracle` | `LBJLincoln26/pol-oracle-model` | **0.23274** (best fold 0.22329) | 0.20239 | live |

Both return base-rate when called without features (TF clients only pass identifiers). Full RF prediction requires `{"games"/"events": [{"features": [N-dim vector]}]}`. Neither is yet the default `NBA_ORACLE_URL`/`POL_ORACLE_URL` — that would regress predictions without feature wire-up. Oracles are warm backups + retrain targets for the weekly cron.

## NBA betting surface (2026-04-24)

- 249 categories per game in `data/full-odds-2025-26.json` (162 alt_spread/alt_total, 28 team_total, 22 pp, 20 halves/quarters, 3 game props + ml/spread/total). Previously `[:8]` slicing in `_build_game_block` hid 200+ of them; now agents see all.
- Max 25 allocations/day + 8 parlays/day (was 10+3).
- Same game can appear in allocations under DIFFERENT categories (ml_home + spread_away + pp_points_star1_over valid together).
- Parlays: 2-6 legs, each pct 0.005-0.08.

## New Tools (Apr 4)

| Tool | Script | Purpose |
|------|--------|--------|
| Bloomberg Terminal | `scripts/bloomberg/nomos42-terminal.py` | Rich TUI: odds, predictions, fleet, bankroll |
| Bloomberg API | `scripts/bloomberg/bloomberg-api.py` | HTTP API on port 8042 (auto-restart cron) |
| Free Models | `scripts/forge/free-models-integration.py` | Qwen/Gemma/Mistral council advisors via HF API |
| ZeroGPU Burst | `scripts/gpu-burst/zerogpu-burst.py` | H200 GPU burst (15 min/day free, 3 accounts) |
| OpenCode Agents | `scripts/opencode/*.sh` | D1/D5/D7 automated agents (cron every 4-6h) |
| Laptop Monitor | `scripts/laptop/agent-monitor.py` | Cross-repo health via local Ollama |
| Cross-Repo Council | `scripts/councils/cross-repo-councils.sh` | Run dept councils across all 8 repos |

## Agent Directives (OBLIGATOIRE Overrides)

### Pre-Work
1. **STEP 0 RULE**: Before ANY structural refactor on a file >300 LOC, first remove dead props, unused exports, unused imports, debug logs. Commit cleanup separately.
2. **PHASED EXECUTION**: Never attempt multi-file refactors in single response. Max 5 files per phase. Complete phase → verify → approval → next phase.

### Code Quality
3. **SENIOR DEV OVERRIDE**: Override default "try simplest approach" for architecture work. Fix structural issues, not just symptoms. Ask: "What would a perfectionist senior dev reject in review?"
4. **FORCED VERIFICATION**: After every file modification, run verification before reporting success. Never claim "done" without checking the code compiles/runs.

### Context Management
5. **SUB-AGENT SWARMING**: Tasks touching >5 independent files MUST use parallel sub-agents (5-8 files each). Sequential processing of large tasks guarantees context decay.
6. **CONTEXT DECAY**: After 10+ messages, re-read any file before editing. Auto-compaction may have destroyed context.
7. **FILE READ BUDGET**: Files >500 LOC must be read in chunks with offset/limit. Never assume single read captured full file.
8. **TOOL RESULT BLINDNESS**: If search returns suspiciously few results, re-run with narrower scope. Assume truncation.

### Edit Safety
9. **EDIT INTEGRITY**: Re-read file before AND after every edit. Never batch >3 edits to same file without verification read.
10. **NO SEMANTIC SEARCH**: On rename/signature change, search separately for: direct calls, type refs, string literals, dynamic imports, re-exports, barrel files, test mocks.

## MCP Servers

| Server | Purpose |
|--------|--------|
| Supabase | NBA data, experiments, research_proposals |
| Neo4j | Knowledge graph |
| HuggingFace | Space management |

## Telegram

| Bot | Repo | Purpose |
|-----|------|--------|
| @Nomos42Bot | mon-ipad | NBA Brain -- predictions, analysis, research |
| @RGWAbot | rgwa | AI Art Terminal -- generation, gallery, quality |

Channel: @Nomos42

## Department Forge Structure (v19)

| Dept | Name | Karpathy Loop | Metric | Max Run |
|------|------|---------------|--------|--------|
| D1 | RESEARCH | paper→extract→propose→measure | papers/week, techniques tested | 5 min |
| D2 | ENGINEERING | code→test→measure Brier→keep/revert | Brier delta, test pass rate | 5 min |
| D3 | EVOLUTION | mutate→eval→measure fitness→select | gen/hr, best Brier, diversity | 5 min |
| D4 | PRODUCT | build→test→ship→measure | features shipped, Brier delta | 5 min |
| D5 | BUSINESS | price→onboard→convert→optimize | MRR, conversion rate, ARPU | 5 min |
| D6 | EVALUATION | audit→identify→fix→verify | false positive rate, calibration | 5 min |
| D7 | INFRA | check→detect→fix→verify | uptime %, restart count | 5 min |
| D8 | FINANCE | track→report→reconcile→forecast | financial accuracy, burn rate | 5 min |
| D9 | CROSS-REPO | sync→audit→fix→verify | parity score, cross-repo health | 5 min |

Guardian Orchestrator v3: Analyzes ALL 9 department loops, allocates resources, cross-pollinates wins.

## Trading Floor v5 — 16 Real LLM Agents (NBA + Political, parity) — Apr 17, 2026

Every agent is a **real LLM API call** — no hash simulation, no mocks.
Each receives full game context (odds, standings, form, 100+ categories, 22 SOTA strategies)
and REASONS about what to bet. Full 2025-26 season (1257 games).

**COLLECTIVE_MISSION**: every system_prompt is prefixed with the collective preamble —
ONE of 16 LLM agents, SAME data seen by all, $1M season goal, ≥75% deploy / ≥3 allocations
EVERY day, full collab stack (morning council moderated by qwen-235B, Axelrod canon, pacts,
post-mortem log, sacrificial rotation, rogue triggers at <$25 or peer >$250K).

Architecture: TradingAgents (arXiv 2412.20138) + Prediction Arena (2604.07355) + DMAD anti-groupthink

### NBA Traders (16 AI Agents — all real LLM calls, parity with POL, verified live 2026-04-17)
| # | trader_id | Model | Provider | Personality | Risk |
|---|-----------|-------|----------|-------------|------|
| T1 | qwen-quant | Qwen 3 235B-A22B | Cerebras | quantitative | 0.55 |
| T2 | qwen-arb | Qwen 3 235B-A22B | Cerebras | arbitrage | 0.65 |
| T3 | llama-contra | Llama 3.1 8B | Cerebras | contrarian | 0.55 |
| T4 | gemini-anl | Gemini 3 Flash Preview | Google (key 2) | analytical | 0.55 |
| T5 | gemini-tact | Gemini 3 Flash Preview | Google (key 2) | tactical | 0.60 |
| T6 | mistral-large | mistral-large-latest | Mistral | ensemble | 0.50 |
| T7 | mistral-medium | mistral-medium-latest | Mistral | diversified | 0.45 |
| T8 | mistral-small | mistral-small-latest | Mistral | wide-coverage | 0.35 |
| T9 | mistral-nemo | open-mistral-nemo | Mistral | aggressive | 0.70 |
| T10 | mistral-ministral | ministral-8b-latest | Mistral | theoretical | 0.35 |
| T11 | nemotron-120b | NVIDIA Nemotron-3-Super-120B | OpenRouter (free) | chainthought | 0.55 |
| T12 | selfhost-qwen4b | Qwen3-4B (self-hosted CPU) | selfhost:qwen3-4b | disciplined | 0.40 |
| T13 | nvidia-minimax | MiniMax M2.7 (NVIDIA NIM) | NVIDIA NIM (key 1+2) | decisive | 0.58 |
| T14 | nvidia-llama70 | Llama 3.3 70B (NVIDIA NIM) | NVIDIA NIM (key 1+2) | swing | 0.50 |
| T15 | selfhost-gemma3 | Gemma-3-4B (self-hosted CPU) | selfhost:gemma-3-4b | analytical | 0.45 |
| T16 | selfhost-qwen06 | Qwen3-0.6B (self-hosted CPU) | selfhost:qwen3-0.6b | conservative | 0.30 |

### Providers (verified 2026-04-15)
| Provider | Status | Models in use | Notes |
|----------|--------|---------------|-------|
| Cerebras | WORKING | qwen-3-235b-a22b-instruct-2507, llama3.1-8b | Free, 30 RPM. Other models (gpt-oss-120b, zai-glm-4.7) listed but 404 on POST. |
| Google Gemini | WORKING (parser fixed) | gemini-3-flash-preview (key 2) | Free tier, 14 RPM. **MUST set thinkingBudget=0** or thinking eats all tokens. |
| Mistral | WORKING | large/medium/small/nemo/ministral-8b | Free tier, 20 RPM |
| OpenRouter | FREE-LIMITED | nemotron-3-super-120b:free | All other free models 429 across 3 keys |
| Self-Host (Nomos42/nomos42-llm-cpu) | WORKING | Phi-3.5 GGUF (CPU) | No quota, slow ~8s/call. |
| Kimi (Moonshot) | DEAD | — | KIMI_API_KEY 401 invalid |
| Gemini 2.5 Pro | DEAD | — | Key 2 forces thinking, key 3 API disabled |
| HF Inference | DEAD | — | Monthly credits exhausted |

### HF Space (HF-First Architecture)
PRIMARY engine: `LBJLincoln26/nba-llm-trading-floor` (FastAPI + Gradio, ~4-6h for full season)
Source: `scripts/arena/hf-llm-trading-floor/app.py` (~1450 lines)
Control: FastAPI endpoints (/api/status, /api/run, /api/stop, /api/mutate, /api/logs, /api/leaderboard)
LLM Gateway: `LBJLincoln26/llm-gateway` (centralized proxy, 11 models, fallback chains)
GH Action: `.github/workflows/trading-floor.yml` — MONITOR ONLY (curls /api/status, commits snapshot)

### Political Traders (10 AI Agents — subset of NBA, excludes T11 nemotron-120b and T12 gemma4-selfhost)
Trading: ETFs, index funds, real stocks based on political signals
Starting capital: $100,000 virtual | Daily rebalancing
<!-- TODO(fleet): add T11 + T12 for parity with NBA -->
**Political TF drift (2026-04-15):** `scripts/arena/hf-political-trading-floor/app.py` has 10 TRADERS (T1–T10 Cerebras/Google/Mistral). NBA has 12 (+T11 nemotron-120b, +T12 gemma4-selfhost). Parity requires patching political app.py and redeploying the Space.

## Browser + Hermes Agents (2026-04-20)

Owned by DR FRANKENSTEIN. Proposal: `data/research/hermes-browser-agents-2026-04-20.md`.

| Space | Account | Purpose | Client |
|-------|---------|---------|------|
| `LBJLincoln/nomos-browser-nba` | LBJLincoln | Scrape ESPN/bbref/VegasInsider NBA lines via `browser-use` 0.12.6 | `scripts/agents/nba_line_scraper_client.py` → `data/lines/YYYY-MM-DD.json` |
| `TESTforge42/nomos-browser-qa` | TESTforge42 | Pixel-world + dashboard visual QA (Playwright DOM + screenshot) | `scripts/agents/pixel_qa_client.py`; GH Action `.github/workflows/pixel-qa.yml` on push to `scripts/arena/hf-pixel-world/**` |
| `LBJLincoln26/nomos-hermes-agent` | LBJLincoln26 | `NousResearch/hermes-agent` CLI via FastAPI RPC (`/api/task`, `/api/skills`) | direct `POST /api/task` — binary shipped in image, 71 skills preloaded |

Secrets set: `GOOGLE_API_KEY` (all 3). Pending user add: `ANTHROPIC_API_KEY`, `BROWSERUSE_API_KEY`, `NOUS_API_KEY`, `OPENROUTER_API_KEY`. Source: `scripts/arena/hf-browser-nba/`, `hf-browser-qa/`, `hf-hermes-agent/`. Deploy: `HfApi.upload_folder` + `restart_space(factory_reboot=True)`. Nomos42 account NOT touched (saturated).

### Codespaces + local install (FRANKENSTEIN-2)

- **Codespaces/devcontainer**: `.devcontainer/post-create.sh` installs `browser-use==0.12.6`, `uv`, chromium, and Hermes upstream on every new codespace. Wired via `"postCreateCommand": "bash .devcontainer/post-create.sh"` in `devcontainer.json`. Port 7860 forwarded for local RPC testing. New secrets declared: `NOUS_API_KEY`, `BROWSERUSE_API_KEY`, plus `BROWSER_NBA_URL` / `BROWSER_QA_URL` / `HERMES_AGENT_URL` overrides.
- **VM local install**: `scripts/setup/install-browser-hermes.sh` — idempotent, passes `--break-system-packages`, detects existing `~/.local/bin/hermes`, timeouts the NousResearch installer at 15 min (its playwright step can hang on apt-lock). Use `--no-chromium` to skip the ~600MB chromium fetch on lean boxes.
- **Cross-repo clients**:
  - `scripts/agents/dashboard_qa_client.py` + `.github/workflows/dashboard-qa.yml` ping `TESTforge42/nomos-browser-qa` `/api/qa-dashboard` against `nomosdashboard.vercel.app` on push + daily 07:17 UTC. Mirror workflow `browser-qa.yml` lives in the `nomos-dashboard` repo for direct push-to-main gating.
  - `nomos-political-alpha/scripts/scrape_fec_edgar.py` — stub that probes `LBJLincoln/nomos-browser-nba` for `/api/scrape-fec`; exits 0 with `ENDPOINT_NOT_YET_DEPLOYED` until the endpoint is added, then emits `data/fec/YYYY-MM-DD.json`.
- **Client index + cron recipes**: `scripts/agents/README.md`.

## Delegation

| Task | Model | Mechanism |
|------|-------|----------|
| Analysis, decisions, pilotage | Opus 4.6 | Direct |
| 24/7 brain trigger | Sonnet 4.6 | Remote trigger |
| Batch execution, search | Sonnet 4.6 | Agent(model: "sonnet") |
| Codebase exploration | Haiku 4.5 | Agent(model: "haiku") |

## The Trading Floor Crew — 14 Agents × 9 Departments (v3, 2026-04-18)

```
L1 STRATEGIC:  Claude Code CLI + User (vision, milestones, decisions)
    └── THE BOSS (orchestrator, dispatches all 13 agents)

L2 APPLICATION:
    D1 Research:    HAWKEYE (daily recon) + DR FRANKENSTEIN (engine impl)
    D2 Engineering: THE BLACKSMITH (council Karpathy loops)
    D3 Evolution:   SWISH (NBA S10-S22) + LOBBYIST (Political P1-P8)
    D4 Product:     THE HERALD (Telegram publisher) + PIXEL (visual QA)
    D5 Business:    THE ACCOUNTANT (Stripe/Whop/LS revenue)
    D6 Evaluation:  INTERNAL AFFAIRS (scientific integrity audit)
    D9 Cross-Repo:  LAUNCHPAD (CI/CD + deploy orchestration)

L3 LOGISTICS:
    D7 Infra:       SWITCHBOARD (LLM gateway keepalive) + THE PLUMBER (data pipelines)
    D8 Finance:     THE TICKER (live odds, CLV, steam moves)
```

Agent roster: `.claude/agents/ROSTER.md` (v3 — full mapping with cron schedule)

Each department runs a Karpathy autoresearch loop:
- SCAN → PROPOSE → EXECUTE (5-min) → EVALUATE → KEEP/REVERT
- Council state: data/departments/council-<dept>.json
- Metrics log: data/departments/<dept>/metrics.jsonl
- Runner: scripts/councils/hermes-runner.sh <dept>

Shared infra: VM (control tower) + Laptop (local models) + HF Spaces (3 accounts) + GPU burst
