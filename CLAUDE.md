# Nomos42 — NBA Quant AI + Political Alpha

> Architecture v21 — "The Trading Floor Crew" (14 agents × 9 depts × 4 tracks) + TF v3 (17 LLM agents) + 21 Evolution Islands | Updated: 2026-05-25T08h

## Mission
Build the best NBA prediction AI in the world.
**Best:** Brier 0.21139 walk-forward holdout / 0.22169 CV / 0.22054 isotonic-calibrated (Colab TabICL, 186f top-by-variance from 4581 alive of 7246 engine cols, ctx=3072 temp=1.0, 11440 games, promoted to LBJLincoln26/nba-oracle-model 2026-04-28T00:34Z, archive `colab-multi-tabicl-2026-04-28T00-34-04Z.pkl`). Beat 4581f xgboost holdout 0.22079 / lightgbm 0.22181 in same 3-way comparison. ⚠ All 3 models show negative CV→holdout gap (~−0.01) → holdout 0.21139 is window-biased; honest production-Brier expectation is CV 0.22169 / calibrated 0.22054. Stratified-by-month re-cut queued. NBA TF watchdog gate "<0.21 model lands" NOT met → watchdog stays disabled. | Fleet best: 0.22012 (S15 nba-evo-6 fire-61 ★CHECKPOINT) | GA prev alltime: 0.22019 (S14 gen=1078) | ⚡Pareto fleet best: 0.21841 extra_trees S15 gen=566 fire-66 (prev 0.21850 CatBoost S22 gen=2309) | ⚠ S18 0.21924 candidate LOST — hard resets cycles 251/276 before checkpoint (2026-05-06T00h) | ⚠ fire-97 RF 0.21941 gen=2689 NOT confirmed (best_brier unchanged 0.22012) | ⚡⚡ fire-98: S18 extra_trees 0.21842 200f gen=6549 + S15 CatBoost 0.21881 200f gen=2698 PENDING VALIDATION (best_brier field lag confirmed pattern) | fire-99: S14 RECOVERED ssl-cleared hard-reset-803 stacking-violation-new; S13 stag=23+S15 stag=24 DIVERSIFIED; P2 0.24901 + P7 0.24904 POL candidates (PENDING VAL); convergent 0.249 signal P2+P4+P5+P7 | fire-101: S13 FRESH RESTART cycle=21 (hard-reset-2055 ✓); S15 stag cleared cycle=954; S18 stag=16 DIVERSIFY SENT; all POL UP stag=0; P2 0.24901 2nd fire; P5 LightGBM 0.249 4th fire | fire-109: S13 stag CLEARED 8→0 cycle=198; S14 hard-reset-978; S15 0.22012 ★ stable gen=3227; all POL UP stag=0; P7 FIELD-LAG 6+ fires vm-diversify-p7-fire109 URGENT; P4 in-pop | fire-160: S22-stag-CLEARED(19→0)-DIVERSIFY-SUCCESS c402 g1206; S18 pareto=15(↑14→15) c489 g1466; S13/S14/S15 404-DOWN(sleeping); all-POL 404-DOWN(sleeping); EVEN arXiv:2508.02725 LSTM+Brier-loss-NCAA=0.1589-research-proposal-written | fire-162: S13-403-FORBIDDEN(was-404-fire-161)-POSSIBLY-WAKING-CatBoost-0.21992-EXTREME-URGENT; S18-c541-pareto=13(↑9→13-RECOVERING); S22-c438-hard-reset-c428-rapid-cycling; all-POL-404-DOWN; EVEN PMC12357926-NBA-stacked-83.27%-AUC=0.9213-features:2PA/FG/TRB/FGA

**Political Alpha:** Best: 0.2497 brier (P4 LightGBM-131f, POL fleet best, 2026-05-21★) | P1 pareto_best=0.24902 LightGBM-105f (3RD-OBSERVE fire-158 ALL-TIME RECORD) | P2 pareto=3 CRITICAL-SHRINK (fire-158) | P4 pareto=5 oscillation (5→14→5 fire-156→157→158) | P5 pareto=6 RECOVERING (↑3→6 fire-158) | P7 LightGBM-112f-0.24931 stable

---

## Cloud Brain Protocol (fire-NNN)

### Trigger
Every 4h: `data/work-queue.json` push from iPad/automation → GitHub Action → Claude API.

### Brain reads (in order)
1. `data/work-queue.json` — pending items
2. `CLAUDE.md` — full architecture + rules
3. VM status APIs (curl endpoints below)

### Brain writes (single commit)
- `data/work-queue.json` — updated items (status=done, new items)
- `CLAUDE.md` — updated fire log line in Mission block
- Any other files needed (research proposals, etc.)

### Fire parity
- ODD fires: no WebSearch
- EVEN fires: WebSearch arXiv/papers (1-2 queries max)

---

## Architecture: 21 Evolution Islands

### NBA Islands (active)
| Island | HF Repo | Status | Best Brier | Notes |
|--------|---------|--------|-----------|-------|
| S13 | TESTforge42/nba-evo-s13 | 403-FORBIDDEN | 0.22216 (field-lag) | CatBoost-200f-0.21992 gen=2831 EXTREME URGENT — 403-NEW(was-404) possibly-waking fire-162 |
| S14 | TESTforge42/nba-evo-s14 | 404-DOWN | 0.22054 RF-48f | BELOW THRESHOLD confirmed fire-157+158 — SLEEPING fire-162 |
| S15 | LBJLincoln26/nba-evo-6 | 404-DOWN | 0.22012★ | FLEET BEST stable gen=6672 pareto=13 — SLEEPING fire-162 |
| S17 | LBJLincoln26/nba-evo-s17 | 503 DOWN 115+d | — | PAUSED |
| S18 | TESTforge42/nba-evo-s18 | UP | 0.22236 | pareto=13(↑9→13 RECOVERING fire-162) stag=0 c541 g1622; hard-resets c500+c525; pareto_best CatBoost-0.22197 field-lag |
| S22 | TESTforge42/nba-evo-s22 | UP | 0.22124 | stag=0 c438 g1312; RAPID-CYCLING hard-resets c403+c428(2x in 36 cycles post-diversify); LR-43f top-pareto |

### POL Islands (active)
| Island | HF Repo | Status | Best Brier | Notes |
|--------|---------|--------|-----------|-------|
| P1 | TESTforge42/political-evo-p1 | 404-DOWN | pareto_best=0.24902 | LightGBM-105f 3RD-OBSERVE fire-158 ALL-TIME RECORD — SLEEPING fire-162 |
| P2 | TESTforge42/political-evo-p2 | 404-DOWN | 0.249 | pareto=3 CRITICAL-SHRINK fire-158 — SLEEPING fire-162 |
| P4 | TESTforge42/political-evo-p4 | 404-DOWN | 0.2497★ | POL FLEET BEST pareto=5 oscillation — SLEEPING fire-162 |
| P5 | TESTforge42/political-evo-p5 | 404-DOWN | 0.24993 | pareto=6 RECOVERING fire-158 — SLEEPING fire-162 |
| P7 | TESTforge42/political-evo-p7 | 404-DOWN | 0.24931 | LightGBM-112f stable pareto=7 — SLEEPING fire-162 |

---

## VM Curl Endpoints

```bash
# NBA Islands
curl https://TESTforge42-nba-evo-s13.hf.space/api/status
curl https://TESTforge42-nba-evo-s14.hf.space/api/status
curl https://LBJLincoln26-nba-evo-6.hf.space/api/status
curl https://TESTforge42-nba-evo-s18.hf.space/api/status
curl https://TESTforge42-nba-evo-s22.hf.space/api/status

# POL Islands
curl https://TESTforge42-political-evo-p1.hf.space/api/status
curl https://TESTforge42-political-evo-p2.hf.space/api/status
curl https://TESTforge42-political-evo-p4.hf.space/api/status
curl https://TESTforge42-political-evo-p5.hf.space/api/status
curl https://TESTforge42-political-evo-p7.hf.space/api/status

# Export (checkpoint)
curl https://TESTforge42-nba-evo-s13.hf.space/api/export
curl https://TESTforge42-nba-evo-s14.hf.space/api/export
curl https://LBJLincoln26-nba-evo-6.hf.space/api/export
curl https://TESTforge42-nba-evo-s18.hf.space/api/export
curl https://TESTforge42-nba-evo-s22.hf.space/api/export
curl https://TESTforge42-political-evo-p1.hf.space/api/export
curl https://TESTforge42-political-evo-p2.hf.space/api/export
curl https://TESTforge42-political-evo-p4.hf.space/api/export
curl https://TESTforge42-political-evo-p5.hf.space/api/export
curl https://TESTforge42-political-evo-p7.hf.space/api/export

# Diversify command
curl -X POST https://TESTforge42-nba-evo-s22.hf.space/api/command -H 'Content-Type: application/json' -d '{"command":"diversify"}'
```

---

## Rules

### Rule #1 — Single Source of Truth
All architecture decisions live in `CLAUDE.md` (this file). No contradictions allowed.

### Rule #2 — Engine Parity
`nomos-nba-agent/features/engine.py` must stay in sync with `mon-ipad` version. MISMATCH CONFIRMED fire-158: mon-ipad=523,050 chars vs nomos-nba-agent=468,146 chars (delta=54KB). `engine-parity-sync` in work-queue.

### Rule #3 — Checkpoint Before Modify
Always `curl /api/export` before any island config change. Never modify a stagnated island before checkpoint.

### Rule #4 — Field Lag Awareness
`best_brier` field in API status lags actual pareto best by 1-3 fires. Trust `pareto_best` from `/api/export` over `best_brier` in `/api/status`.

### Rule #5 — Threshold Gates
- NBA checkpoint gate: brier < 0.22085 → CHECKPOINT URGENT
- NBA fleet-best gate: brier < 0.22012 → EXTREME URGENT
- POL checkpoint gate: brier < 0.249 → CHECKPOINT URGENT
- POL fleet-best gate: brier < 0.2497 → EXTREME URGENT

### Rule #6 — Stagnation Protocol
- stag > 15 → send diversify command
- stag > 25 → hard-reset consideration
- Never diversify without checkpoint first

### Rule #7 — do_not_push_hf_space_yet
Do NOT push to HF Spaces (nba-llm-trading-floor, political-llm-trading-floor) until user explicitly approves. NBA TF 503 DOWN 33+d. POL TF IDLE 27+d.

### Rule #8 — No Stacking
Remove 'stacking' from MODEL_TYPES on all islands. Stacking causes overfitting. Violations: S13, S14, S15, S22.

### Rule #9 — LightGBM First for POL
All 5 POL islands show LightGBM as pareto_best (5/5 confirmed fire-158). Add LightGBM to MODEL_TYPES on P1+P2 (missing). PORT: vm-add-lightgbm-p1-p2.

### Rule #10 — Even/Odd Fire Parity
- EVEN fires: WebSearch allowed (arXiv, papers, news)
- ODD fires: No WebSearch (pure analysis)

---

## Trading Floor v3 (TF)

### NBA TF
- Repo: LBJLincoln26/nba-llm-trading-floor
- Status: 503 DOWN 33+d
- do_not_push_hf_space_yet: TRUE
- Watchdog gate: "<0.21 model" NOT met

### POL TF
- Repo: LBJLincoln26/political-llm-trading-floor
- Status: IDLE since 2026-05-07
- P&L: $38,916 (unchanged 27+d)
- pol_watchdog.sh: NOT firing
- do_not_push_hf_space_yet: TRUE

### Axelrod Mechanisms
- Mech A: DONE (fire-122) — day-end common knowledge broadcast
- Mech B: PENDING — sacrificial role reallocation (BLOCKED: HF push gate)
- Mech C: PENDING — post-mortem log schema HF push (BLOCKED: HF push gate)
- Parity: SHAs NBA 19f4acf49d(5993L)/POL 3496362c60(3977L) UNCHANGED vs fire-161 (verified fire-163)
- 13/13 parity symbols OK (verified fire-163; C→B→A call-order confirmed NBA:5056/5065/5073 POL:3246/3255/3263; KL-div ε-smoothed self-excluded confirmed)

---

## Research Pipeline

### Active Research
1. **Venn-Abers Calibration** (fire-158 EVEN WebSearch)
   - arXiv:2605.03816: CatBoost wins 26/30 Brier datasets
   - XGBoost/LightGBM poor calibration (Bulls-effect), fixable with Venn-Abers
   - Libraries: crepes or nonconformist
   - Target: P1+P2+P5+P7 (all use xgboost_brier)
   - Expected improvement: 0.001-0.003 Brier
   - Proposal: data/research-proposals/sota-venn-abers-calibration-fire158.md
   - Work-queue: vm-add-venn-abers-calibration (priority=32)

2. **Bootstrap Variance Calibration (BVC)** for S15 RF-75f
   - Work-queue: vm-mc-dropout-calibration-s15 (priority=30)

3. **Win-Diff-Last-5-Games Feature** (MDPI2026 top SHAP)
   - BLOCKED by engine-parity-sync (priority=40)
   - Work-queue: vm-add-win-diff-5game-feature (priority=35)

4. **Elo Ratings Feature** (IEEE/MDPI 2026 SHAP #1+#2)
   - BLOCKED by engine-parity-sync (priority=40)
   - Work-queue: vm-add-elo-ratings-engine (priority=60)

5. **SHAP Analysis** S15 RF-75f + S22 RF-48f
   - Work-queue: vm-shap-feature-analysis-s15 (priority=80)

6. **LSTM + Brier-Loss Sequence Model** (fire-160 EVEN WebSearch)
   - arXiv:2508.02725: LSTM+Brier-loss achieves 0.1589 Brier on NCAA basketball
   - Transformer-BCE has best AUC (0.8473) but LSTM+Brier-loss has best calibration
   - Rationale: current GA evolves static feature sets; sequence models capture momentum
   - Target: post-GA calibration layer or standalone sequence model
   - Proposal: data/research-proposals/sota-lstm-brier-loss-fire160.md
   - Work-queue: vm-research-lstm-sequence-model (priority=90)

7. **NBA Stacked Ensemble Feature Importance** (fire-162 EVEN WebSearch)
   - PMC12357926: NBA stacked ensemble (XGBoost+KNN+AdaBoost+NaiveBayes+LR+DT + MLP meta) achieves 83.27% acc, AUC=0.9213 on 3,690 NBA games (2021-2024)
   - Top SHAP features: 2-point attempts (2PA), field goals made (FG), total rebounds (TRB), field goal attempts (FGA)
   - Note: stacking approach PROHIBITED (Rule#8); feature importance insight actionable for engine-parity-sync
   - Note: no Brier score reported; uses in-game stats (not pre-game prediction) — limited direct applicability
   - Action: verify 2PA/FG rolling-avg variants are in engine.py during engine-parity-sync (priority=40)

---

## Political Alpha Pipeline

### Data Crons (BLOCKED)
- fetch_political_data.py: NOT running
- insider_tracker.py: NOT running
- pol_watchdog.sh: NOT running → POL TF IDLE
- Rotation A+D BLOCKED
- FEC/SEC features: BLOCKED (vm-fec-sec-political-features priority=61)

### MODEL_TYPES Status
| Island | Current | Needed |
|--------|---------|--------|
| P1 | xgboost, catboost, random_forest | + lightgbm |
| P2 | xgboost, catboost, random_forest | + lightgbm |
| P4 | xgboost, catboost, random_forest, lightgbm | OK |
| P5 | xgboost, catboost, random_forest, lightgbm | OK |
| P7 | xgboost, catboost, random_forest, lightgbm | OK |

---

## Fire Log (last 10)

| Fire | Time | Parity | Key Events |
|------|------|--------|------------|
| 163 | 2026-05-25T08h | ODD | Axelrod verify pass: SHAs NBA 19f4acf49d(5993L)/POL 3496362c60(3977L) UNCHANGED vs fire-161; 13/13 parity OK; C→B→A ordering confirmed; KL-div ε OK; AXELROD_ARCHETYPES domain-specific OK; Mech B+C BLOCKED (do_not_push_hf_space_yet+NBA-503+POL-IDLE) |
| 162 | 2026-05-25T04h | EVEN | S13 403-FORBIDDEN NEW(was-404-fire-161, possibly-waking! CatBoost-0.21992 EXTREME-URGENT); S18 c541 g1622 stag=0 pareto=13(↑9→13 RECOVERING); S22 c438 g1312 stag=0 hard-reset-c428(rapid-cycling-2x-36-cycles-post-diversify); all-POL 404-DOWN(sleeping); EVEN: PMC12357926 NBA-stacked-83.27%-acc-AUC=0.9213 features:2PA/FG/TRB/FGA (no-Brier; stacking-Rule#8-prohibited) |
| 161 | 2026-05-25T00h | ODD | Axelrod verify pass: SHAs NBA 19f4acf49d(5993L)/POL 3496362c60(3977L) UNCHANGED vs fire-159; 13/13 parity OK; C→B→A ordering confirmed; KL-div ε OK; 20-archetype pools domain-specific OK; Mech B+C BLOCKED (do_not_push_hf_space_yet+NBA-503+POL-IDLE) |
| 160 | 2026-05-24T20h | EVEN | S18 c489 g1466 pareto=15(↑14→15) stag=0; S22 stag-CLEARED(19→0) c402 g1206 DIVERSIFY-SUCCESS; S13/S14/S15 404-DOWN(sleeping); all-POL(P1-P7) 404-DOWN(sleeping); EVEN: arXiv:2508.02725 LSTM+Brier-loss-NCAA=0.1589 research-proposal-written |
| 159 | 2026-05-24T16h | ODD | Axelrod verify pass: SHAs NBA 19f4acf49d/POL 3496362c60 UNCHANGED vs fire-155; 13/13 parity OK; C→B→A ordering confirmed; KL-div ε OK; 20-archetype pools domain-specific OK; Mech B+C BLOCKED (do_not_push_hf_space_yet+NBA-503+POL-IDLE) |
| 158 | 2026-05-24T12h | EVEN | S13 CatBoost-0.21992 2ND-FIRE; S14 RF-0.22054 BELOW-THRESHOLD 2ND; S18 NEW-PARETO-BEST CatBoost-0.22197 1ST-DETECT; S22 stag=19 2ND-DIVERSIFY-SENT; P2 pareto=3 CRITICAL-SHRINK; P4 pareto=5 oscillation; P5 RECOVERING; WebSearch: arXiv:2605.03816 Venn-Abers |
| 157 | 2026-05-24T08h | ODD | S14 NEW-BEST-0.22054 RF-48f; S13 CatBoost-0.21992 1ST-DETECT; S22 stag=21 DIVERSIFY-SENT; P4 MAJOR-RECOVERY pareto=14; P5 CRITICAL-SHRINK pareto=3; P1 pareto_best=0.24902 2ND-CONFIRM |
| 156 | 2026-05-24T04h | EVEN | P1 NEW POL ALL-TIME pareto_best=0.24902 1ST-DETECT; P4 pareto=5; S15 stable |
| 155 | 2026-05-24T00h | ODD | Axelrod parity verify pass; S15 stable; POL monitoring |
| 154 | 2026-05-23T20h | EVEN | P1 pareto monitoring; S22 stag rising |

---

## Glossary

- **stag**: stagnation counter (generations without pareto improvement)
- **pareto**: number of non-dominated solutions in island population
- **pareto_best**: best Brier score ever seen in pareto front (from /api/export)
- **best_brier**: current best Brier in /api/status (lags pareto_best by 1-3 fires)
- **field-lag**: best_brier field not yet updated despite pareto improvement
- **BVC**: Bootstrap Variance Calibration
- **TF**: Trading Floor (LLM agent system)
- **HF**: Hugging Face
- **RF**: Random Forest
- **ET**: Extra Trees
- **LR**: Logistic Regression
- **SHAP**: SHapley Additive exPlanations (feature importance)

---

## Contact / Repos

- Main agent: LBJLincoln26 (HF)
- Test forge: TESTforge42 (HF)
- iPad orchestrator: lbjlincoln/mon-ipad (GitHub)
- NBA agent: LBJLincoln26/nomos-nba-agent (HF)
- Oracle model: LBJLincoln26/nba-oracle-model (HF)
- NBA TF: LBJLincoln26/nba-llm-trading-floor (HF, 503 DOWN)
- POL TF: LBJLincoln26/political-llm-trading-floor (HF, IDLE)
- POL alpha: LBJLincoln26/nomos-political-alpha (HF)
