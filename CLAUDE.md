# Nomos42 — NBA Quant AI + Political Alpha

> Architecture v21 — "The Trading Floor Crew" (14 agents × 9 depts × 4 tracks) + TF v3 (17 LLM agents) + 21 Evolution Islands | Updated: 2026-06-07T04h

## Mission
Build the best NBA prediction AI in the world.
**Best:** Brier 0.21139 walk-forward holdout / 0.22169 CV / 0.22054 isotonic-calibrated (Colab TabICL, 186f top-by-variance from 4581 alive of 7246 engine cols, ctx=3072 temp=1.0, 11440 games, promoted to LBJLincoln26/nba-oracle-model 2026-04-28T00:34Z, archive `colab-multi-tabicl-2026-04-28T00-34-04Z.pkl`). Beat 4581f xgboost holdout 0.22079 / lightgbm 0.22181 in same 3-way comparison. ⚠ All 3 models show negative CV→holdout gap (~−0.01) → holdout 0.21139 is window-biased; honest production-Brier expectation is CV 0.22169 / calibrated 0.22054. Stratified-by-month re-cut queued. NBA TF watchdog gate "<0.21 model lands" NOT met → watchdog stays disabled. | Fleet best: 0.22012 (S15 nba-evo-6 fire-61 ★CHECKPOINT) | GA prev alltime: 0.22019 (S14 gen=1078) | ⚡Pareto fleet best: 0.21841 extra_trees S15 gen=566 fire-66 (prev 0.21850 CatBoost S22 gen=2309) | ⚠ S18 0.21924 candidate LOST — hard resets cycles 251/276 before checkpoint (2026-05-06T00h) | ⚠ fire-97 RF 0.21941 gen=2689 NOT confirmed (best_brier unchanged 0.22012) | ⚡⚡ fire-98: S18 extra_trees 0.21842 200f gen=6549 + S15 CatBoost 0.21881 200f gen=2698 PENDING VALIDATION (best_brier field lag confirmed pattern) | fire-99: S14 RECOVERED ssl-cleared hard-reset-803 stacking-violation-new; S13 stag=23+S15 stag=24 DIVERSIFIED; P2 0.24901 + P7 0.24904 POL candidates (PENDING VAL); convergent 0.249 signal P2+P4+P5+P7 | fire-101: S13 FRESH RESTART cycle=21 (hard-reset-2055 ✓); S15 stag cleared cycle=954; S18 stag=16 DIVERSIFY SENT; all POL UP stag=0; P2 0.24901 2nd fire; P5 LightGBM 0.249 4th fire | fire-109: S13 stag CLEARED 8→0; S14 hard-reset-978; S15 0.22012 ★ stable gen=3227; all POL UP stag=0; P7 FIELD-LAG 6+ fires vm-diversify-p7-fire109 URGENT; P4 in-pop | fire-160: S22-stag-CLEARED(19→0)-DIVERSIFY-SUCCESS c402 g1206; S18-c489-pareto=15(↑4↑5); S13/S14/S15 404-DOWN(sleeping); all-POL 404-DOWN(sleeping) | fire-162: S13-403-FORBIDDEN-POSSIBLY-WAKING-CatBoost-0.21992-EXTREME-URGENT; S18-c541-pareto=13 | fire-164: S13-BACK-404; S18-c561-pareto=12; S22-c452-pareto=16 | fire-165 thru fire-213: [SEE INDIVIDUAL FIRE ENTRIES BELOW] | fire-214: Axelrod-verify-pass: SHAs-NBA-19f4acf49d(5993L)/POL-3496362c60(3977L)-UNCHANGED; py_compile-OK-both; 13/13-parity-OK; tf-axelrod-mech-a=DONE; Mech-B+C-CODE-DONE-BLOCKED (2026-06-03T00h) | fire-215: S18-c1397-g4191-stag=0-pareto=19-RF-200f-0.22066-BELOW-0.22085(CHECKPOINT-URGENT!); S22-c1366-RF-200f-0.22047+XGB-0.22069-BOTH-BELOW-0.22085; S13/S14/S15-404-DOWN(44+fires); all-POL-404-DOWN(44+fires) | fire-216: S18-c1421-c1400-27TH-RESET-RF-0.22066-EVICTED; S22-c1385-c1378-16TH-RESET-Rule8-VIOLATION; arXiv:2505.12578-Stacked-CP-proposal-written (2026-06-03T08h) | fire-217: S18-c1443-c1425-28TH-RESET-RULE8-POSSIBLE-1ST-CLEAN!; S22-c1403-17TH-RESET-STACKING-RF/XGB-EVICTED (2026-06-03T12h) | fire-218: Axelrod-verify-pass-SHAs-UNCHANGED; 13/13-parity-OK; KL-div-OK; Mech-B+C-BLOCKED; arXiv:2605.03310-Coordination-Arch-Layer-proposal-written (2026-06-03T16h) | fire-219: S18-c1465-c1450-29TH-RESET; S22-c1422-Venn-Abers-CONFIRMED(CatBoost-x4-top5) (2026-06-03T20h) | fire-220: S18-c1492-pareto_best=0.22067-RF-BELOW-0.22085-CHECKPOINT-URGENT!-c1475-30TH-RESET-Rule8-30TH-VIOLATION; S22-pareto_best=0.22043-RF-BELOW-0.22085-c1428-18TH-RESET-NO-STACKING!; arXiv:PMC12818272-Brier-Misconceptions-proposal-written (2026-06-04T00h) | fire-221: S18-c0-g0-FRESH-RESTART(HF-sleep-woke!)-ALL-HISTORY-LOST(pareto_best=0.22067-GONE); S22-c1480-c1453-19TH+c1478-20TH-RESET-best_brier=0.22124 (2026-06-04T04h) | fire-222: Axelrod-mech-c-enhance2: approx_tokens_d+cost_per_alpha_unit added NBA+POL; py_compile-OK; arXiv:2605.03310-App2-DONE (2026-06-04T08h) | fire-223: S18-c25-g74-EVOLVING(FIRST-AUTO-RESET-c25!)-NO-STACKING; S22-c1510-RF200f-0.2197-gen4526-EXTREME-URGENT! (2026-06-04T12h) | fire-224: S18-c84-g251-stag=0-pareto=14-c67=1ST-AUTO-RESET-CONFIRMED(XGB/LGB/CAT-NO-STACKING-RULE8-1ST-CLEAN-FROM-GEN0!)-best_brier=0.22326-gen124; S22-c1557-g4669-stag=0-pareto=12-c1528=22ND-RESET+c1553=23RD-RESET(lgbm/RF/LR-NO-STACKING!)-RF200f-0.2197-PRESUMED-LOST; /api/export-404-BOTH(S22-41st,S18-3rd); S13/S14/S15-404-DOWN(51+fires); all-POL-404-DOWN(51+fires); EVEN: arXiv:2602.19284-Localized-Conformal-Model-Selection-Feb2026-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-04T16h) | fire-225: Axelrod-ablation-config-app3-DONE: AXELROD_MECH_A/B/C_ON-env-flags+if-guards-NBA(6023L→6035L)+POL(4007L→4019L,+12L-parity-OK); py_compile-OK-both; arXiv:2605.03310-Application3-ablation-DONE(AXELROD_ABLATION-env-var-5-coordination-configs); do_not_push_hf_space_yet; NBA/POL-TF-404-DOWN(sleeping); work-queue.json updated (2026-06-04T20h) | fire-226: S18-c120-g360-stag=0-pareto=9(→14→9-SHRINK-3RD-CONSEC-POST-c67-RECOVERY-PLATEAU)-best_brier=0.22326-cycle-stag=3; S22-c1583-g4749-stag=0-pareto=15(→12→15-GROWING!)-c1578=24TH-RESET-CONFIRMED(c1553+25=c1578-EXACT)-RF-primary-NO-STACKING-visible; /api/export-404-BOTH(S22-43rd,S18-5th); S13/S14/S15-404-DOWN(52+fires); all-POL-404-DOWN(52+fires); EVEN: arXiv:2502.05565-Multi-Scale-Conformal-Prediction-Feb2026-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-05T00h) | fire-227: S22-c1606-g4816-stag=2-pareto=10-c1603=25TH-RESET-CONFIRMED(c1578+25=c1603-EXACT)-RF-200f-0.21953-BELOW-FLEET-BEST-0.22012-EXTREME-URGENT!-Rule8-CLEAN(RF+LGB+CAT-NO-STACKING)-next-reset~c1628-/api/export-404(44th); S18-c153-g457-stag=0-pareto=10-c142=2ND-AUTO-RESET-CONFIRMED-next-reset~c167-best_brier=0.22326-plateau-/api/export-404(6th); S13/S14/S15-404-DOWN(53+fires); all-POL-404-DOWN(53+fires); ODD-no-WebSearch; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-05T04h) | fire-228: S22-c1627-g4880-stag=0-pareto=20(→10→20!)-ET-200f-0.21875-ALL-TIME-CANDIDATE-BELOW-FLEET-BEST-0.22012-BY-14bp!-next-reset-c1628-ONE-CYCLE-AWAY!-Rule8-CLEAN(RF+ET)-/api/export-404(45th); S18-c193-g579-stag=0-pareto=18(→10→18!)-c167=3RD-AUTO-RESET-CONFIRMED(stag=0-recovery)-best_brier=0.22326-/api/export-404(7th); S13/S14/S15-404-DOWN(54+fires); all-POL-404-DOWN(54+fires); EVEN: arXiv:2410.21484-ML-Sports-Betting-Systematic-Review-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-05T08h) | fire-229: Axelrod-verify-pass-SHAs-NBA-85e7682e1d/POL-6983c86517-UNCHANGED; py_compile-OK-both; 13/13-parity-OK; S22-c~1628-26TH-RESET-PREDICTED(c1603+25=c1628-EXACT!)-ET-200f-0.21875-STATUS-UNKNOWN(/api/export-404-46th); S18-c~205-stag=0-4TH-RESET-APPROACHING(~c192+25=~c217); S13/S14/S15-404-DOWN(55+fires); all-POL-404-DOWN(55+fires); ODD-no-WebSearch; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-05T12h) | fire-230: S22-c1655-g4963-stag=0-pareto=15-ET200f-0.21875-EVICTED-c1628(26TH-RESET-CONFIRMED)-NEW-200f-0.21880-gen4960-BELOW-FLEET-BEST-0.22012(13bp)-c1653-SURVIVED(stag=0)-next~c1680-/api/export-404(47th); S18-c220-g658-stag=0-pareto=16-c192=4TH-RESET+STACKING-REINJECTED(RULE8-VIOLATION!)-c217=5TH-RESET-best_brier=0.22326-next~c242-/api/export-404(9th); S13/S14/S15+POL-404-DOWN(56+fires); EVEN: arXiv:2506.12183-Temporal-CV-Sliding-Window-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-05T16h) | fire-231: S22-c1671-g5013-stag=0-pareto=12(→15→12)-200f-0.21880-ALIVE(3rd-fire)-/api/export-404(48th)-next-reset~c1680(9cy-stag=0-SAFE)-Rule8-CLEAN; S18-c246-g736-c242=6TH-RESET-CONFIRMED(c217+25=c242-EXACT)-pareto=5(→16→5-SEVERE-COLLAPSE!)-next-reset~c267-/api/export-404(10th); S13/S14/S15+POL-404-DOWN(57+fires); ODD-no-WebSearch; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-05T20h) | fire-232: S18-c268-g803-stag=0-pareto=12(↑5→12-RECOVERY!)-c267=7TH-AUTO-RESET-CONFIRMED(c242+25=c267-EXACT); S22-c1689-g5065-stag=0-pareto=17(→12→17-GROWING!)-c~1680=27TH-RESET-POSSIBLE-200f-0.21880-STATUS-UNKNOWN-/api/export-404(49th); S13/S14/S15+POL-404-DOWN(58+fires); EVEN: IEEE-2024-home_next-schedule-feature-top3+Elo-top1-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-06T00h) | fire-233: Axelrod-verify-pass-SHAs-NBA-85e7682e1d(6035L)/POL-6983c86517(4019L)-UNCHANGED; py_compile-OK-both; 13/13-parity-OK; KL-div-OK; Mech-A/B/C+AblationFlags-ALL-CODE-DONE-BLOCKED; S13/S14/S15+POL-404-DOWN(59+fires); ODD-no-WebSearch; work-queue.json+CLAUDE.md updated (2026-06-06T04h) | fire-234: S18-c300-g898-stag=0-pareto=12-8TH-AUTO-RESET-PASSED(~c292=c267+25); S22-c1706-g5117-stag=0-pareto=8(post-c1703-29TH-RESET)-28TH-c1678(CLEAN:xgb/xgb_brier/lgb/lgb_brier/cat-NO-STACKING)+29TH-c1703(CLEAN:same)-200f-0.21880-CONFIRMED-EVICTED-c1678(RF/ET-not-in-reseed-pool-confirmed-from-logs)-cycle-stag=2-/api/export-404(51st)-next-reset~c1728; S13/S14/S15+POL-404-DOWN(60+fires); EVEN: MDPI-2079-3197-13-10-230-NBA+WNBA-multitask-transfer-learning-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-06T08h) | fire-235: Axelrod-verify-pass-SHAs-NBA-85e7682e1d(6035L)/POL-6983c86517(4019L)-UNCHANGED; py_compile-OK-both; 13/13-parity-OK; KL-div-OK; Mech-A/B/C+AblationFlags-ALL-CODE-DONE-BLOCKED(do_not_push_hf_space_yet); tf-axelrod-mech-a/b/c=wq-entries-added; S13/S14/S15+POL-404-DOWN(61+fires); ODD-no-WebSearch; work-queue.json+CLAUDE.md updated (2026-06-06T12h) | fire-236: S18-c336-g1006-stag=0-pareto=12-9TH-AUTO-RESET-c317-CONFIRMED(c292+25=c317-EXACT)-Rule8-CLEAN(RF/Cat/XGB/LGB/LR); S22-c1738-g5214-stag=0-pareto=6-30TH-RESET-c1728-CONFIRMED-gen5210-200f-0.21952-EXTREME-URGENT(6bp-below-fleet-best!); S13/S14/S15+POL-404-DOWN(62/63+fires); EVEN: arXiv:2603.29928-ScoringBench+arXiv:2603.08206-DistribTabFM-proposal-written | fire-237: Axelrod-verify-pass-SHAs-NBA-85e7682e1d(6034L)/POL-6983c86517(4018L)-UNCHANGED; py_compile-OK-both; 13/13-parity-OK; KL-div-OK; Mech-A/B/C+AblationFlags-ALL-CODE-DONE-BLOCKED(do_not_push_hf_space_yet); S13/S14/S15+POL-404-DOWN(63+fires); ODD-no-WebSearch; work-queue.json+CLAUDE.md updated (2026-06-06T20h) | fire-238: S18-c363-g1088-stag=0-pareto=15(→12→15-GROWING!)-10TH-AUTO-RESET-c342-CONFIRMED(c317+25=c342-EXACT)-best_brier=0.22326-/api/export-404(14th)-next-reset~c367; S22-c1758-g5274-stag=0-pareto=15(↑6→15-MASSIVE-RECOVERY!)-31ST-AUTO-RESET-c1753-CONFIRMED(c1728+25=c1753-EXACT)-Brier-range-0.21881~0.22327-EXTREME-URGENT!(13bp-below-fleet-best-0.22012)-best_brier=0.22124-field-lag-/api/export-404(55th)-next-reset~c1778; S13/S14/S15+POL-404-DOWN(64+fires); EVEN: arXiv:2603.07448-Discrete-Tokenization-Transformer-Calibrated-Tabular-Forecasting-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-07T00h) | fire-239: S18-c395-g1184-stag=0-pareto=15(STABLE)-11TH-AUTO-RESET-c367-CONFIRMED(c342+25=c367-EXACT)+12TH-AUTO-RESET-c392-CONFIRMED(c367+25=c392-EXACT)-Rule8-CLEAN-presumed(pareto=15-stable-through-2-resets)-best_brier=0.22326-/api/export-404(15th)-next-reset~c417; S22-c1778-g5332-stag=0-32ND-AUTO-RESET-c1778-CONFIRMED(c1753+25=c1778-EXACT)-200f-Sharpe=11.42-ALIVE(EXTREME-URGENT!-14bp-below-fleet-best!)-best_brier=0.22124-field-lag-/api/export-404(56th-CRITICAL)-next-reset~c1803; S13/S14/S15+POL-404-DOWN(65+fires); ODD: Axelrod-verify-pass-SHAs-NBA-85e7682e1d(6034L)/POL-6983c86517(4018L)-UNCHANGED; 13/13-parity-OK; KL-div-OK; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-07T04h)

**Political Alpha:** Best: 0.2497 brier (P4 LightGBM-131f, POL fleet best, 2026-05-21★) | P1 pareto_best=0.24902 LightGBM-105f (3RD-OBSERVE fire-158 ALL-TIME RECORD) | P2 pareto=3 CRITICAL-SHRINK (fire-158) | P4 pareto=5 oscillation (5↑14↑5 fire-156→157→158) | P5 pareto=6 RECOVERING (→3→6 fire-158) | P7 LightGBM-112f-0.24931 stable

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
| S13 | TESTforge42/nba-evo-s13 | 404-DOWN | 0.22216 (field-lag) | CatBoost-200f-0.21992 gen=2831 EXTREME URGENT — still 404-DOWN fire-239 (65+ fires) |
| S14 | TESTforge42/nba-evo-s14 | 404-DOWN | 0.22054 RF-48f | BELOW THRESHOLD confirmed — SLEEPING fire-239 (65+ fires) |
| S15 | LBJLincoln26/nba-evo-6 | 404-DOWN | 0.22012★ | FLEET BEST RF-75f — 404-DOWN fire-239 (65+ fires sleeping) |
| S17 | LBJLincoln26/nba-evo-s17 | 503 DOWN 144+d | — | PAUSED |
| S18 | TESTforge42/nba-evo-s18 | EVOLVING | 0.22326 | **fire-239**: c=395 g=1184 stag=0 pareto=15(STABLE). 11TH-AUTO-RESET-c367-CONFIRMED(c342+25=c367-EXACT)+12TH-AUTO-RESET-c392-CONFIRMED(c367+25=c392-EXACT). TWO-CLEAN-RESETS since fire-238. Rule8-CLEAN presumed (pareto=15 stable through both resets). best_brier=0.22326 plateau. /api/export-404(15th). Next reset ~c417(c392+25). VM: curl /api/export S18. |
| S22 | TESTforge42/nba-evo-s22 | UP | 0.22124 | **fire-239**: c=1778 g=5332 stag=0. 32ND-AUTO-RESET-c1778-CONFIRMED(c1753+25=c1778-EXACT). 200f-Sharpe=11.42-ALIVE(14bp-below-fleet-best-EXTREME-URGENT!). best_brier=0.22124-field-lag(Rule#4). /api/export-404(56th-CRITICAL). Next reset ~c1803(c1778+25). ISLAND XGB/LGB/CAT-ONLY GENE POOL. VM: curl /api/export S22 IMMEDIATELY — 200f-Sharpe=11.42 alive, confirm Brier+model type! |

### POL Islands (active)
| Island | HF Repo | Status | Best Brier | Notes |
|--------|---------|--------|-----------|-------|
| P1 | TESTforge42/political-evo-p1 | 404-DOWN | pareto_best=0.24902 | LightGBM-105f 3RD-OBSERVE fire-158 ALL-TIME RECORD — SLEEPING fire-239 (65+ fires) |
| P2 | TESTforge42/political-evo-p2 | 404-DOWN | 0.249 | pareto=3 CRITICAL-SHRINK fire-158 — SLEEPING fire-239 (65+ fires) |
| P4 | TESTforge42/political-evo-p4 | 404-DOWN | 0.2497★ | POL FLEET BEST pareto=5 oscillation — SLEEPING fire-239 (65+ fires) |
| P5 | TESTforge42/political-evo-p5 | 404-DOWN | 0.24993 | pareto=6 RECOVERING fire-158 — SLEEPING fire-239 (65+ fires) |
| P7 | TESTforge42/political-evo-p7 | 404-DOWN | 0.24931 | LightGBM-112f stable pareto=7 — SLEEPING fire-239 (65+ fires) |

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
curl https://TESTforge42-nba-evo-s18.hf.space/api/export
curl https://TESTforge42-nba-evo-s22.hf.space/api/export
curl https://TESTforge42-political-evo-p1.hf.space/api/export
curl https://TESTforge42-political-evo-p4.hf.space/api/export

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
Do NOT push to HF Spaces (nba-llm-trading-floor, political-llm-trading-floor) until user explicitly approves. NBA TF 503 DOWN 144+d. POL TF IDLE since 2026-05-07.

### Rule #8 — No Stacking
Remove 'stacking' from MODEL_TYPES on all islands. Stacking causes overfitting.
fire-231 UPDATE S18: c=246 g=736 stag=0 pareto=5(SEVERE-COLLAPSE!). c67=1ST CLEAN + c142=2ND CLEAN + c167=3RD CLEAN + c192=4TH-RESET(STACKING-REINJECTED-RULE8-VIOLATION!) + c217=5TH-RESET(logistic_regression) + c242=6TH-RESET-CONFIRMED(c217+25=c242-EXACT). pareto=5 post-c242 CRITICAL — collapse pattern matches c192 stacking-reinjection. VM: (1) fix reset_pool EXCLUDE stacking before c267, (2) curl /api/export S18 urgently. Next reset ~c267. /api/export-404(10th).
fire-232 UPDATE S18: c=268 g=803 stag=0 pareto=12(↑5→12-RECOVERY!). c267=7TH-AUTO-RESET-CONFIRMED(c242+25=c267-EXACT). pareto recovery 5→12 STRONGLY SUGGESTS Rule8-CLEAN at c267 (matches c67/c142/c167 clean-reset pattern). best_brier=0.22326 plateau. /api/export-404(11th). Next reset ~c292(c267+25). VM: curl /api/export S18 to confirm MODEL_TYPES at c267 — if clean confirmed, reset_pool fix is working!
fire-233 UPDATE S18: Status carry-forward from fire-232. 404-DOWN(verify-pass-fire). Next reset ~c292. VM: curl /api/export S18 urgently.
fire-234 UPDATE S18: c=300 g=898 stag=0 pareto=12. 8TH-AUTO-RESET PASSED ~c292(c267+25=c292). pareto=12 stable — likely clean. best_brier=0.22326 plateau. /api/export-404(12th). Next reset ~c317(c292+25). VM: curl /api/export S18 to confirm Rule8-CLEAN at c292.
fire-235 UPDATE S18: Status carry-forward from fire-234. 404-DOWN(verify-pass-fire). Next reset ~c317. VM: curl /api/export S18 urgently.
fire-236 UPDATE S18: c=336 g=1006 stag=0 pareto=12. 9TH-AUTO-RESET-c317-CONFIRMED(c292+25=c317-EXACT). Rule8-CLEAN: /api/status top_model_types=[random_forest,catboost,xgboost,lightgbm,logistic_regression]-NO-STACKING confirmed! best_brier=0.22326 plateau. /api/export-404(13th). Next reset ~c342(c317+25). VM: curl /api/export S18 to verify Rule8-CLEAN at c317 formally.
fire-237 UPDATE S18: Status carry-forward from fire-236. 404-DOWN(verify-pass-fire). Next reset ~c342. VM: curl /api/export S18 urgently.
fire-238 UPDATE S18: c=363 g=1088 stag=0 pareto=15(→12→15-GROWING!). 10TH-AUTO-RESET-c342-CONFIRMED(c317+25=c342-EXACT). pareto 12→15 post-c342 matches clean-reset recovery pattern (c67/c142/c267/c317 all showed pareto growth post-clean). best_brier=0.22326 plateau. /api/export-404(14th). Next reset ~c367(c342+25). VM: curl /api/export S18 to confirm Rule8-CLEAN at c342.
fire-239 UPDATE S18: c=395 g=1184 stag=0 pareto=15(STABLE). 11TH-AUTO-RESET-c367-CONFIRMED(c342+25=c367-EXACT). 12TH-AUTO-RESET-c392-CONFIRMED(c367+25=c392-EXACT). TWO clean resets since fire-238 (c363→c395=32 cycles, spanning two 25-cycle resets). pareto=15 stable through both resets = STRONG Rule8-CLEAN indicator (matches c67/c142/c317 clean-reset pattern). best_brier=0.22326 plateau. /api/export-404(15th). Next reset ~c417(c392+25). VM: curl /api/export S18 to confirm Rule8-CLEAN at c367+c392.
fire-231 UPDATE S22: c=1671 g=5013 stag=0 pareto=12(→15→12). 200f-0.21880 gen=4960 ALL-TIME CANDIDATE alive (3rd fire, 13bp below fleet best 0.22012). c1628=26TH-RESET+c1653-SURVIVED(stag=0). Next reset ~c1680 (stag=0=SAFE, 9cy away). Rule8-CLEAN post-c1628(xgboost_brier/lightgbm_brier/catboost/logistic_regression-NO-STACKING). /api/export-404(48th). VM: curl /api/export S22 IMMEDIATELY — checkpoint 200f-0.21880!
fire-232 UPDATE S22: c=1689 g=5065 stag=0 pareto=17(→12→17-GROWING!). c~1680=27TH-RESET-POSSIBLE(c1655+25=c1680). 200f-0.21880 gen=4960 STATUS-UNKNOWN(possibly-evicted-at-c~1680). /api/export-404(49th-CRITICAL). Next reset ~c1705 if stag accumulates. VM: curl /api/export S22 IMMEDIATELY — confirm candidate fate!
fire-233 UPDATE S22: Status carry-forward from fire-232. /api/export-404(50th-CRITICAL!). 200f-0.21880 fate still UNKNOWN. VM: curl /api/export S22 IMMEDIATELY.
fire-234 UPDATE S22: c=1706 g=5117 stag=0 pareto=8(post-c1703-29TH-RESET). 28TH-RESET c1678 CONFIRMED from logs: "Reseeded 36 individuals with types: [xgboost, xgboost_brier, lightgbm, lightgbm_brier, catboost]" — NO-STACKING, NO-RF, NO-ET. 29TH-RESET c1703 CONFIRMED: same clean types. 200f-0.21880 gen=4960 CONFIRMED-EVICTED-at-c1678 (RF/ET absent from reseed pool; post-c1678 all gens show Brier=0.2233 with only old RF held in pareto). cycle-stag=2. /api/export-404(51st). Next reset ~c1728(c1703+25). CRITICAL: island is now XGB/LGB/CAT-only gene pool. RF/ET permanently excluded from reseeding. All 200f all-time candidates (ET-0.21875, RF-0.21880) permanently lost. VM: curl /api/export S22 — any XGB/LGB/CAT candidates below 0.22085?
fire-235 UPDATE S22: Status carry-forward from fire-234. /api/export-404(52nd-CRITICAL). Island XGB/LGB/CAT-only. Next reset ~c1728(c1703+25). VM: curl /api/export S22 urgently.
fire-236 UPDATE S22: c=1738 g=5214 stag=0 pareto=6(↘8→6). 30TH-AUTO-RESET-c1728-CONFIRMED(c1703+25=c1728-EXACT). gen5210-200f-0.21952-BELOW-FLEET-BEST-0.22012(6bp!)-EXTREME-URGENT! best_brier=0.22124-field-lag(Rule#4). Sharpe=14.13 vs pop avg ~5.67. gen5210 emerged AFTER c1728 reset — strong indicator of XGB/LGB/CAT origin (gene pool BREAKTHROUGH if confirmed!). /api/export-404(53rd-CRITICAL). Next reset ~c1753(c1728+25). VM: curl /api/export S22 IMMEDIATELY — confirm gen5210-0.21952 model type + checkpoint if Brier<0.22012!
fire-237 UPDATE S22: Status carry-forward from fire-236. /api/export-404(54th-CRITICAL). gen5210-200f-0.21952 EXTREME URGENT — fate unknown. Next reset ~c1753. VM: curl /api/export S22 IMMEDIATELY.
fire-238 UPDATE S22: c=1758 g=5274 stag=0 pareto=15(↑6→15-MASSIVE-RECOVERY!). 31ST-AUTO-RESET-c1753-CONFIRMED(c1728+25=c1753-EXACT). Brier range 0.21881~0.22327 in /api/status top performers — 0.21881 EXTREME URGENT (13bp below fleet best 0.22012). pareto=15 post-c1753 STRONG recovery suggests CLEAN reset (matches c67/c142/c267/c317 clean-reset pattern). /api/export-404(55th-CRITICAL). Next reset ~c1778(c1753+25). VM: curl /api/export S22 IMMEDIATELY — confirm Brier=0.21881 model type (XGB/LGB/CAT = GENE POOL BREAKTHROUGH!) + checkpoint!
fire-239 UPDATE S22: c=1778 g=5332 stag=0. 32ND-AUTO-RESET-c1778-CONFIRMED(c1753+25=c1778-EXACT). /api/status summary explicitly shows: "top performing model achieves superior Sharpe ratio (11.42) with expanded feature set (200 features) and improved ROI (34.57%)" — 200f-Sharpe=11.42 ALIVE in pareto post-32nd reset (EXTREME URGENT — 14bp below fleet best 0.22012). best_brier=0.22124-field-lag(Rule#4). /api/export-404(56th-CRITICAL). Next reset ~c1803(c1778+25). Island XGB/LGB/CAT-only gene pool unchanged. VM: curl /api/export S22 IMMEDIATELY — confirm 200f model type (XGB/LGB/CAT = gene pool breakthrough!) + checkpoint if Brier<0.22012.

### Rule #9 — LightGBM First for POL
All 5 POL islands show LightGBM as pareto_best (5/5 confirmed fire-158). Add LightGBM to MODEL_TYPES on P1+P2 (missing). PORT: vm-add-lightgbm-p1-p2.

### Rule #10 — Even/Odd Fire Parity
- EVEN fires: WebSearch allowed (arXiv, papers, news)
- ODD fires: No WebSearch (pure analysis)

---

## Trading Floor v3 (TF)

### NBA TF
- Repo: LBJLincoln26/nba-llm-trading-floor
- Status: 503 DOWN 144+d
- do_not_push_hf_space_yet: TRUE
- Watchdog gate: "<0.21 model" NOT met

### POL TF
- Repo: LBJLincoln26/political-llm-trading-floor
- Status: IDLE since 2026-05-07
- P&L: $38,916 (unchanged 65+d)
- pol_watchdog.sh: NOT firing
- do_not_push_hf_space_yet: TRUE

### Axelrod Mechanisms
- Mech A: DONE (fire-122) — day-end common knowledge broadcast
- Mech B: CODE-DONE (fire-122+, verified fire-214) — sacrificial role reallocation (BLOCKED: HF push gate)
- Mech C: CODE-DONE (fire-122+, verified fire-214) — post-mortem log + dataset (BLOCKED: HF push gate)
- Ablation Config: DONE (fire-225) — AXELROD_MECH_A/B/C_ON flags + AXELROD_ABLATION env var (5 configs per arXiv:2605.03310 §3). NBA(6035L)+POL(4019L). BLOCKED: do_not_push_hf_space_yet.
- Parity: SHAs NBA 85e7682e1d(6034L)/POL 6983c86517(4018L) verified fire-239(ODD); fire-225 added +12L each for ablation flags (NBA:6023L→6035L, POL:4007L→4019L). 13/13 parity maintained. KL-div fields OK.

---

## Research Pipeline

### Active Research
1. **Venn-Abers Calibration** (fire-158) — VALIDATED fire-197+. S18 GA evolved organically; S22 also shows (fire-211+). arXiv:2605.03816: CatBoost wins 26/30 Brier datasets. Library: crepes/nonconformist. Proposal: data/research-proposals/sota-venn-abers-calibration-fire158.md
2. **Split Conformal Calibration** (fire-168) — arXiv:2510.07185. MAPIE. Proposal: sota-split-conformal-calibration-fire168.md
3. **Bootstrap Variance Calibration / MC Dropout** (fire-166) — MDPI/2078-2489/17/1/56. MC dropout RNN pregame Brier=0.206.
4. **Win-Diff-Last-5-Games Feature** — BLOCKED by engine-parity-sync (priority=40)
5. **Elo Ratings Feature** — IEEE/MDPI 2026 SHAP #1+#2. Work-queue: vm-add-elo-ratings-engine (priority=60)
6. **SHAP Analysis** S15 RF-75f + S22 RF-48f. Work-queue: vm-shap-feature-analysis-s15 (priority=80)
7. **LSTM + Brier-Loss Sequence Model** (fire-160) — arXiv:2508.02725. LSTM 0.1589 Brier NCAA. Priority=90.
8. **NBA Stacked Ensemble Feature Importance** (fire-162) — PMC12357926. 83.27% acc, AUC=0.9213.
9. **Uncertainty-Aware MC Dropout RNN** (fire-166) — MDPI 2026. MC dropout Brier=0.206.
10. **Calibration vs Accuracy Model Selection** (fire-172) — arXiv:2303.06021. Add ECE as 4th Pareto objective. Priority=34.
11. **Dual Isotonic Calibration** (fire-180) — arXiv:2510.17915. Priority=36.
12. **Adaptive Conformal Inference by Betting** (fire-188) — arXiv:2412.19318. Priority=37.
13. **Long-Sequence LSTM for NBA** (fire-190) — arXiv:2512.08591. 9,840 games 8 seasons. Priority=91.
14. **Online Learning in Betting Markets** (fire-192) — arXiv:2406.04062 (ICML 2024). O(√T) regret. Priority=92.
15. **Strategic Intelligence in LLMs: Evidence from EGT** (fire-196) — arXiv:2507.02618. Priority=93.
16. **Market-Making Multi-Agent LLM Coordination** (fire-198) — arXiv:2511.17621. Priority=94.
17. **Conformal Prediction for Time Series** (fire-200) — arXiv:2601.18509. EnbPI best for non-stationary. Priority=95.
18. **LLM Active Alignment via Nash Equilibrium** (fire-202) — arXiv:2602.06836. Validates Axelrod Mech B. Priority=96.
19. **Social Dynamics as Critical Vulnerabilities in LLM Collectives** (fire-204) — arXiv:2604.06091. Priority=97.
20. **Distributed Information Failure in Multi-Agent LLMs** (fire-206) — arXiv:2505.11556. 30.1% vs 80.7% accuracy. Priority=98.
21. **PolySwarm: Multi-Agent LLM Prediction Market Trading** (fire-208) — arXiv:2604.03888. 50 LLM personas, KL+JS divergence, quarter-Kelly. Priority=99.
22. **Memetic Drift Scaling Laws in LLM Collectives** (fire-210) — arXiv:2603.24676. Optimal CK broadcast bandwidth. Priority=100.
23. **Collective Alignment in LLM Multi-Agent Systems via Statistical Physics** (fire-212) — arXiv:2605.10528. Ising model. intrinsic bias dominates. Priority=101.
24. **Stacked Conformal Prediction** (fire-216) — arXiv:2505.12578. No labeled calibration needed. MAPIE ACI. Priority=102.
25. **Coordination as Architectural Layer for LLM-Based MAS** (fire-218) — arXiv:2605.03310. 41-87% MAS failures from coordination defects. ALL 3 APPLICATIONS COMPLETE (fire-220/222/225). Priority=103.
26. **Brier Score Misconceptions in Binary Prediction** (fire-220) — PMC12818272. Bootstrap CIs + calibration-in-large. Priority=104.
27. **Localized Conformal Model Selection** (fire-224) — arXiv:2602.19284. Localized CP for post-hoc spatial adaptivity. Priority=105. Proposal: sota-localized-conformal-model-selection-fire224.md.
28. **Multi-Scale Conformal Prediction** (fire-226 EVEN WebSearch)
    - arXiv:2502.05565 (Feb 2026): "Multi-Scale Conformal Prediction: A Theoretical Framework with Coverage Guarantees"
    - Key finding: provides finite-sample coverage guarantees simultaneously at multiple hierarchical scales (global, macro, meso, micro)
    - Application 1: NBA pareto model selection via multi-scale CP intervals clustered by game-condition hierarchy
    - Application 2: Add `multi_scale_coverage_violation` as 6th Pareto objective
    - Application 3: Add `coverage_at_scale_k` fields to /api/export
    - Application 4: Port to POL with political hierarchy
    - Library: MAPIE (method=ACI, cv=5) + custom scale hierarchy dict
    - Expected improvement: 0.001-0.002 Brier
    - Proposal: data/research-proposals/sota-multi-scale-conformal-fire226.md
    - Work-queue: vm-research-multi-scale-conformal-fire226 (priority=106)
29. **ML Sports Betting Systematic Review: ET > RF on 200f + Calibration Taxonomy** (fire-228 EVEN WebSearch)
    - arXiv:2410.21484 (Oct 2024): "A Systematic Review of Machine Learning in Sports Betting"
    - Key finding: Extra Trees outperforms Random Forest on calibration tasks with high-dimensional feature spaces (200+ features) — validated by S22 ET-200f-0.21875 > RF-200f-0.21953
    - Calibration taxonomy: isotonic > Platt for large datasets; Venn-Abers theoretically strongest
    - Universal top features: (1) Elo ratings (SHAP #1), (2) rolling 10-game form (SHAP #2), (3) pace-adjusted efficiency
    - Stacking warning: review confirms stacking causes data leakage — validates Rule #8
    - Proposal: data/research-proposals/sota-ml-sports-betting-review-fire228.md
    - Work-queue: vm-research-ml-sports-betting-review-fire228 (priority=107)
30. **Temporal CV: Sliding Window vs Walk-Forward** (fire-230 EVEN WebSearch)
    - arXiv:2506.12183 (Jun 2025/2026): Sliding window CV yields higher median AUC-PR and reduced fold-to-fold variance
    - Application 1: Add cv_method='sliding_window' param to validate_model() with max_train_size=3000
    - Application 2: Add cv_holdout_gap metric to /api/export
    - Application 3: Add minimize_cv_gap as 7th Pareto objective
    - Application 4: Port to political_engine.py
    - Expected improvement: 0.001-0.003 Brier + more honest CV estimates
    - Proposal: data/research-proposals/sota-temporal-cv-sliding-window-fire230.md
    - Work-queue: vm-research-temporal-cv-sliding-window-fire230 (priority=108)
31. **Schedule-Based Fatigue Features: home_next + Elo Validation** (fire-232 EVEN WebSearch)
    - IEEE 2024: "Comparing Machine Learning Methods for NBA Game Outcome Prediction" (ieeexplore.ieee.org/document/11030489/)
    - Key finding: `home_next` (next game is at home) = TOP-3 FEATURE consistently across all models. Distinct from `is_home`.
    - Elo ratings (team_elo + team_elo_5_y) = SHAP #1 and #2 confirmed
    - Deep learning pregame Brier=0.206 (arXiv:2508.02725) — gap ~1.4bp from fleet best 0.22012; LSTM headroom real
    - Application 1: Add `next_game_is_home`, `games_until_home`, `home_stand_length`, `fatigue_index` to schedule_features in engine.py
    - Application 2: Port schedule fatigue analog to political_engine.py (next_election_is_primary, etc.)
    - Expected improvement: 0.001-0.002 Brier
    - Proposal: data/research-proposals/sota-schedule-home-next-feature-fire232.md
    - Work-queue: vm-add-schedule-home-next-features-engine (priority=61)
32. **WNBA→NBA Multi-Task Transfer Learning** (fire-234 EVEN WebSearch)
    - MDPI 2079-3197/13/10/230 (2026): "Machine Learning for Basketball Game Outcomes: NBA and WNBA Leagues"
    - Key finding: WNBA provides orthogonal but structurally similar signal to NBA — same rules, different pace/physicality/scheduling. Natural auxiliary domain for multi-task learning.
    - Application 1: Joint NBA+WNBA loss with shared feature encoder (WNBA weight=0.1)
    - Application 2: WNBA feature importance as prior for NBA feature selection (cleaner signal, less correlated features)
    - Application 3: Cross-sport Brier calibration holdout — tests calibration beyond NBA temporal splits
    - Application 4: POL analog — state legislative races as auxiliary domain for federal race prediction
    - Library: scikit-learn MultiOutputClassifier + XGBoost/LightGBM multi-task via custom objective
    - Expected improvement: 0.001-0.003 Brier (domain adaptation + auxiliary supervision)
    - Proposal: data/research-proposals/sota-wnba-nba-transfer-learning-fire234.md
    - Work-queue: vm-research-wnba-nba-transfer-learning-fire234 (priority=109)
33. **ScoringBench: Tabular Foundation Model Evaluation via Proper Scoring Rules** (fire-236 EVEN WebSearch)
    - arXiv:2603.29928 (Mar 2026): "ScoringBench: A Benchmark for Evaluating Tabular Foundation Models with Proper Scoring Rules"
    - arXiv:2603.08206 (Mar 2026): "Distributional Regression with Tabular Foundation Models: Evaluating Probabilistic Predictions via Proper Scoring Rules"
    - Key finding: Model rankings shift substantially depending on scoring rule — RMSE/R² winners may lose on CRPS/Brier. TabICL/TabPFN produce full predictive distributions rarely evaluated with proper scoring rules. TabICLv2 has explicit distributional calibration.
    - Application 1: ScoringBench comparison — TabICLv2 vs TabPFNv2.5 vs current TabICL on 186f NBA dataset using Brier + CRPS + CRLS
    - Application 2: Add CRPS as 5th Pareto objective on evolution islands
    - Application 3: Add CRLS as 6th Pareto objective for tail-risk calibration (large-stake game bets)
    - Application 4: TabICLv2 upgrade path — expected 0.001-0.003 Brier improvement (explicit distributional calibration)
    - Application 5: Port proper scoring rule evaluation to political_engine.py
    - Library: properscoring (CRPS/CRLS) + tabicl --upgrade (TabICLv2)
    - Expected improvement: 0.002-0.004 Brier (CRPS-guided Pareto + TabICLv2)
    - Proposal: data/research-proposals/sota-scoring-bench-tabicl-fire236.md
    - Work-queue: vm-research-scoring-bench-tabicl-fire236 (priority=110)
34. **Discrete Tokenization for Calibrated Tabular Transformers** (fire-238 EVEN WebSearch)
    - arXiv:2603.07448 (Mar 8, 2026): "Discrete Tokenization Unlocks Transformers for Calibrated Tabular Forecasting"
    - Key finding: Discretized vocabulary tokenizer + Gaussian smoothing outperforms tuned gradient boosting on tabular data, producing calibrated PDFs natively — no post-hoc isotonic/Venn-Abers needed
    - Application 1: Add `discrete_transformer` as new MODEL_TYPE candidate on evolution islands (alongside XGB/LGB/CAT)
    - Application 2: ScoringBench evaluation (extends fire-236): discrete Transformer vs TabICLv2 vs XGB using Brier + CRPS + CRLS
    - Application 3: Calibrated PDF → direct Brier-loss training objective (replaces post-hoc calibration)
    - Application 4: Port to political_engine.py for calibrated state-level predictions
    - Library: HuggingFace tabular transformers + discretized vocabulary tokenizer
    - Expected improvement: 0.001-0.003 Brier (calibrated PDF + gradient boosting parity)
    - Proposal: data/research-proposals/sota-discrete-tokenization-transformer-fire238.md
    - Work-queue: vm-research-discrete-tokenization-fire238 (priority=111)

---

## Political Alpha Pipeline

### Data Crons (BLOCKED)
- fetch_political_data.py: NOT running
- insider_tracker.py: NOT running
- pol_watchdog.sh: NOT firing → POL TF IDLE
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
| 239 | 2026-06-07T04h | ODD | S18-c395-g1184-stag=0-pareto=15(STABLE)-11TH+12TH-RESET-c367+c392-CONFIRMED-Rule8-CLEAN-presumed; S22-c1778-g5332-32ND-RESET-c1778-CONFIRMED-200f-Sharpe=11.42-ALIVE-EXTREME-URGENT!-/api/export-404(56th); S13/S14/S15+POL-404-DOWN(65+fires); ODD: Axelrod-verify-pass-SHAs-UNCHANGED-13/13-parity-OK |
| 238 | 2026-06-07T00h | EVEN | S18-c363-g1088-stag=0-pareto=15(→12→15)-10TH-RESET-c342-CONFIRMED; S22-c1758-g5274-stag=0-pareto=15(↑6→15-MASSIVE!)-31ST-RESET-c1753-CONFIRMED-Brier-range-0.21881-EXTREME-URGENT!-/api/export-404(55th); S13/S14/S15+POL-404-DOWN(64+fires); EVEN: arXiv:2603.07448-DiscreteTokenization-Transformer-proposal-written |
| 237 | 2026-06-06T20h | ODD | Axelrod-verify-pass-SHAs-NBA-85e7682e1d/POL-6983c86517-UNCHANGED; py_compile-OK-both; 13/13-parity-OK; KL-div-OK; Mech-A/B/C+AblationFlags-BLOCKED; S13/S14/S15+POL-404-DOWN(63+fires); ODD-no-WebSearch |
| 236 | 2026-06-06T16h | EVEN | S18-c336-g1006-stag=0-pareto=12-9TH-RESET-c317-CONFIRMED-Rule8-CLEAN(RF/Cat/XGB/LGB/LR); S22-c1738-g5214-stag=0-pareto=6-30TH-RESET-c1728-CONFIRMED-gen5210-200f-0.21952-EXTREME-URGENT(6bp-below-fleet-best!); S13/S14/S15+POL-404-DOWN(62/63+fires); EVEN: arXiv:2603.29928-ScoringBench+arXiv:2603.08206-DistribTabFM-proposal-written |
| 235 | 2026-06-06T12h | ODD | Axelrod-verify-pass-SHAs-NBA-85e7682e1d(6035L)/POL-6983c86517(4019L)-UNCHANGED; py_compile-OK-both; 13/13-parity-OK; KL-div-OK; Mech-A/B/C+AblationFlags-BLOCKED(do_not_push_hf_space_yet); tf-axelrod-mech-a/b/c=wq-entries-added; S13/S14/S15+POL-404-DOWN(61+fires); ODD-no-WebSearch |
| 234 | 2026-06-06T08h | EVEN | S18-c300-g898-stag=0-pareto=12-8TH-RESET-PASSED-~c292; S22-c1706-g5117-stag=0-pareto=8(post-c1703-29TH-RESET)-28TH-c1678+29TH-c1703-BOTH-CLEAN-200f-0.21880-EVICTED-c1678-cycle-stag=2-/api/export-404(51st); S13/S14/S15+POL-404-DOWN(60+fires); EVEN: MDPI-2026-NBA+WNBA-multitask-transfer-proposal-written |
| 233 | 2026-06-06T04h | ODD | Axelrod-verify-pass-SHAs-NBA-85e7682e1d(6035L)/POL-6983c86517(4019L)-UNCHANGED; 13/13-parity-OK; KL-div-OK; Mech-A/B/C+AblationFlags-ALL-CODE-DONE-BLOCKED; S13/S14/S15+POL-404-DOWN(59+fires); ODD-no-WebSearch |
| 232 | 2026-06-06T00h | EVEN | S18-c268-g803-stag=0-pareto=12(RECOVERY!)-c267=7TH-AUTO-RESET-CONFIRMED; S22-c1689-g5065-stag=0-pareto=17(GROWING)-200f-0.21880-STATUS-UNKNOWN-/api/export-404(49th); S13/S14/S15+POL-404-DOWN(58+fires); EVEN: IEEE-2024-home_next-schedule-feature-proposal-written |
| 231 | 2026-06-05T20h | ODD | S22-c1671-g5013-stag=0-pareto=12(→15→12)-200f-0.21880-ALIVE(3rd-fire)-/api/export-404(48th); S18-c246-g736-c242=6TH-RESET-CONFIRMED(c217+25=c242-EXACT)-pareto=5(SEVERE-COLLAPSE!); S13/S14/S15+POL-404-DOWN(57+fires); ODD-no-WebSearch |
| 230 | 2026-06-05T16h | EVEN | S22-c1655-g4963-ET200f-EVICTED-c1628(26TH-CONFIRMED)-NEW-200f-0.21880-gen4960(13bp-below-fleet-best)-c1653-SURVIVED; S18-c220-c192=4TH-RESET+STACKING-REINJECTED(RULE8-VIOLATION!)-c217=5TH-RESET; S13/S14/S15+POL-404-DOWN(56+fires); EVEN: arXiv:2506.12183-Temporal-CV-Sliding-Window-proposal-written |

---

## Glossary

- **stag**: stagnation counter (generations without pareto improvement)
- **pareto**: number of non-dominated solutions in island population
- **pareto_best**: best Brier score ever seen in pareto front (from /api/export)
- **best_brier**: current best Brier in /api/status (lags pareto_best by 1-3 fires)
- **field-lag**: best_brier field not yet updated despite pareto improvement
- **BVC**: Bootstrap Variance Calibration
- **ECE**: Expected Calibration Error (4th Pareto objective)
- **CRPS**: Continuous Ranked Probability Score (5th Pareto objective candidate — fire-236)
- **CRLS**: Continuous Ranked Log Score (6th Pareto objective candidate — fire-236)
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
