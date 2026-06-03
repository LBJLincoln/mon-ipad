# Nomos42 — NBA Quant AI + Political Alpha

> Architecture v21 — "The Trading Floor Crew" (14 agents × 9 depts × 4 tracks) + TF v3 (17 LLM agents) + 21 Evolution Islands | Updated: 2026-06-03T08h

## Mission
Build the best NBA prediction AI in the world.
**Best:** Brier 0.21139 walk-forward holdout / 0.22169 CV / 0.22054 isotonic-calibrated (Colab TabICL, 186f top-by-variance from 4581 alive of 7246 engine cols, ctx=3072 temp=1.0, 11440 games, promoted to LBJLincoln26/nba-oracle-model 2026-04-28T00:34Z, archive `colab-multi-tabicl-2026-04-28T00-34-04Z.pkl`). Beat 4581f xgboost holdout 0.22079 / lightgbm 0.22181 in same 3-way comparison. ⚠ All 3 models show negative CV→holdout gap (~−0.01) → holdout 0.21139 is window-biased; honest production-Brier expectation is CV 0.22169 / calibrated 0.22054. Stratified-by-month re-cut queued. NBA TF watchdog gate "<0.21 model lands" NOT met → watchdog stays disabled. | Fleet best: 0.22012 (S15 nba-evo-6 fire-61 ★CHECKPOINT) | GA prev alltime: 0.22019 (S14 gen=1078) | ⚡Pareto fleet best: 0.21841 extra_trees S15 gen=566 fire-66 (prev 0.21850 CatBoost S22 gen=2309) | ⚠ S18 0.21924 candidate LOST — hard resets cycles 251/276 before checkpoint (2026-05-06T00h) | ⚠ fire-97 RF 0.21941 gen=2689 NOT confirmed (best_brier unchanged 0.22012) | ⚡⚡ fire-98: S18 extra_trees 0.21842 200f gen=6549 + S15 CatBoost 0.21881 200f gen=2698 PENDING VALIDATION (best_brier field lag confirmed pattern) | fire-99: S14 RECOVERED ssl-cleared hard-reset-803 stacking-violation-new; S13 stag=23+S15 stag=24 DIVERSIFIED; P2 0.24901 + P7 0.24904 POL candidates (PENDING VAL); convergent 0.249 signal P2+P4+P5+P7 | fire-101: S13 FRESH RESTART cycle=21 (hard-reset-2055 ✓); S15 stag cleared cycle=954; S18 stag=16 DIVERSIFY SENT; all POL UP stag=0; P2 0.24901 2nd fire; P5 LightGBM 0.249 4th fire | fire-109: S13 stag CLEARED 8→0; S14 hard-reset-978; S15 0.22012 ★ stable gen=3227; all POL UP stag=0; P7 FIELD-LAG 6+ fires vm-diversify-p7-fire109 URGENT; P4 in-pop | fire-160: S22-stag-CLEARED(19→0)-DIVERSIFY-SUCCESS c402 g1206; S18-c489-pareto=15(↑4↑5); S13/S14/S15 404-DOWN(sleeping); all-POL 404-DOWN(sleeping) | fire-162: S13-403-FORBIDDEN-POSSIBLY-WAKING-CatBoost-0.21992-EXTREME-URGENT; S18-c541-pareto=13 | fire-164: S13-BACK-404; S18-c561-pareto=12; S22-c452-pareto=16 | fire-165 thru fire-213: [SEE INDIVIDUAL FIRE ENTRIES BELOW] | fire-214: Axelrod-verify-pass: SHAs-NBA-19f4acf49d(5993L)/POL-3496362c60(3977L)-UNCHANGED; py_compile-OK-both; 13/13-parity-OK; tf-axelrod-mech-a=DONE; Mech-B+C-CODE-DONE-BLOCKED (2026-06-03T00h) | fire-215: S18-c1397-g4191-stag=0-pareto=19-RF-200f-0.22066-BELOW-0.22085(CHECKPOINT-URGENT!); S22-c1366-RF-200f-0.22047+XGB-0.22069-BOTH-BELOW-0.22085; S13/S14/S15-404-DOWN(44+fires); all-POL-404-DOWN(44+fires) | fire-216: S18-c1421-c1400-27TH-RESET-RF-0.22066-EVICTED; S22-c1385-c1378-16TH-RESET-Rule8-VIOLATION; arXiv:2505.12578-Stacked-CP-proposal-written (2026-06-03T08h) | fire-217: S18-c1443-c1425-28TH-RESET-RULE8-POSSIBLE-1ST-CLEAN!; S22-c1403-17TH-RESET-STACKING-RF/XGB-EVICTED (2026-06-03T12h) | fire-218: Axelrod-verify-pass-SHAs-UNCHANGED; 13/13-parity-OK; KL-div-OK; Mech-B+C-BLOCKED; arXiv:2605.03310-Coordination-Arch-Layer-proposal-written (2026-06-03T16h) | fire-219: S18-c1465-c1450-29TH-RESET; S22-c1422-Venn-Abers-CONFIRMED(CatBoost-x4-top5) (2026-06-03T20h) | fire-220: S18-c1492-pareto_best=0.22067-RF-BELOW-0.22085-CHECKPOINT-URGENT!-c1475-30TH-RESET-Rule8-30TH-VIOLATION; S22-pareto_best=0.22043-RF-BELOW-0.22085-c1428-18TH-RESET-NO-STACKING!; arXiv:PMC12818272-Brier-Misconceptions-proposal-written (2026-06-04T00h) | fire-221: S18-c0-g0-FRESH-RESTART(HF-sleep-woke!)-ALL-HISTORY-LOST(pareto_best=0.22067-GONE); S22-c1480-c1453-19TH+c1478-20TH-RESET-best_brier=0.22124 (2026-06-04T04h) | fire-222: Axelrod-mech-c-enhance2: approx_tokens_d+cost_per_alpha_unit added NBA+POL; py_compile-OK; arXiv:2605.03310-App2-DONE (2026-06-04T08h) | fire-223: S18-c25-g74-EVOLVING(FIRST-AUTO-RESET-c25!)-NO-STACKING; S22-c1510-RF200f-0.2197-gen4526-EXTREME-URGENT! (2026-06-04T12h) | fire-224: S18-c84-g251-stag=0-pareto=14-c67=1ST-AUTO-RESET-CONFIRMED(XGB/LGB/CAT-NO-STACKING-RULE8-1ST-CLEAN-FROM-GEN0!)-best_brier=0.22326-gen124; S22-c1557-g4669-stag=0-pareto=12-c1528=22ND-RESET+c1553=23RD-RESET(lgbm/RF/LR-NO-STACKING!)-RF200f-0.2197-PRESUMED-LOST; /api/export-404-BOTH(S22-41st,S18-3rd); S13/S14/S15-404-DOWN(51+fires); all-POL-404-DOWN(51+fires); EVEN: arXiv:2602.19284-Localized-Conformal-Model-Selection-Feb2026-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-04T16h) | fire-225: Axelrod-ablation-config-app3-DONE: AXELROD_MECH_A/B/C_ON-env-flags+if-guards-NBA(6023L→6035L)+POL(4007L→4019L,+12L-parity-OK); py_compile-OK-both; arXiv:2605.03310-Application3-ablation-DONE(AXELROD_ABLATION-env-var-5-coordination-configs); do_not_push_hf_space_yet; NBA/POL-TF-404-DOWN(sleeping); work-queue.json updated (2026-06-04T20h) | fire-226: S18-c120-g360-stag=0-pareto=9(→14→9-SHRINK-3RD-CONSEC-POST-c67-RECOVERY-PLATEAU)-best_brier=0.22326-cycle-stag=3; S22-c1583-g4749-stag=0-pareto=15(→12→15-GROWING!)-c1578=24TH-RESET-CONFIRMED(c1553+25=c1578-EXACT)-RF-primary-NO-STACKING-visible; /api/export-404-BOTH(S22-43rd,S18-5th); S13/S14/S15+POL-404-DOWN(52+fires); EVEN: arXiv:2502.05565-Multi-Scale-Conformal-Prediction-Feb2026-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-05T00h) | fire-227: S22-c1606-g4816-stag=2-pareto=10-c1603=25TH-RESET-CONFIRMED(c1578+25=c1603-EXACT)-RF-200f-0.21953-BELOW-FLEET-BEST-0.22012-EXTREME-URGENT!-Rule8-CLEAN(RF+LGB+CAT-NO-STACKING)-next-reset~c1628-/api/export-404(44th); S18-c153-g457-stag=0-pareto=10-c142=2ND-AUTO-RESET-CONFIRMED-next-reset~c167-best_brier=0.22326-plateau-/api/export-404(6th); S13/S14/S15-404-DOWN(53+fires); all-POL-404-DOWN(53+fires); ODD-no-WebSearch; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-05T04h) | fire-228: S22-c1627-g4880-stag=0-pareto=20(→10→20!)-ET-200f-0.21875-ALL-TIME-CANDIDATE-BELOW-FLEET-BEST-0.22012-BY-14bp!-next-reset-c1628-ONE-CYCLE-AWAY!-Rule8-CLEAN(RF+ET)-/api/export-404(45th); S18-c193-g579-stag=0-pareto=18(→10→18!)-c167=3RD-AUTO-RESET-CONFIRMED(stag=0-recovery)-best_brier=0.22326-/api/export-404(7th); S13/S14/S15-404-DOWN(54+fires); all-POL-404-DOWN(54+fires); EVEN: arXiv:2410.21484-ML-Sports-Betting-Systematic-Review-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-05T08h) | fire-229: Axelrod-verify-pass-SHAs-NBA-85e7682e1d/POL-6983c86517-UNCHANGED; py_compile-OK-both; 13/13-parity-OK; S22-c~1628-26TH-RESET-PREDICTED(c1603+25=c1628-EXACT!)-ET-200f-0.21875-STATUS-UNKNOWN(/api/export-404-46th); S18-c~205-stag=0-4TH-RESET-APPROACHING(~c192+25=~c217); S13/S14/S15-404-DOWN(55+fires); all-POL-404-DOWN(55+fires); ODD-no-WebSearch; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-05T12h) | fire-230: S22-c1655-g4963-stag=0-pareto=15-ET200f-EVICTED-c1628(26TH-RESET-CONFIRMED)-NEW-200f-0.21880-gen4960-BELOW-FLEET-BEST-0.22012(13bp)-c1653-SURVIVED(stag=0)-next~c1680-/api/export-404(47th); S18-c220-g658-stag=0-pareto=16-c192=4TH-RESET+STACKING-REINJECTED(RULE8-VIOLATION!)-c217=5TH-RESET-best_brier=0.22326-next~c242-/api/export-404(9th); S13/S14/S15+POL-404-DOWN(56+fires); EVEN: arXiv:2506.12183-Temporal-CV-Sliding-Window-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-05T16h) | fire-231: S22-c1671-g5013-stag=0-pareto=12(→15→12)-200f-0.21880-gen=4960-ALL-TIME-CANDIDATE-alive(3rd-fire)-/api/export-404(48th)-next-reset~c1680(9cy-stag=0-SAFE)-Rule8-CLEAN; S18-c246-g736-c242=6TH-RESET-CONFIRMED(c217+25=c242-EXACT)-pareto=5(→16→5-SEVERE-COLLAPSE!)-next-reset~c267-/api/export-404(10th); S13/S14/S15+POL-404-DOWN(57+fires); ODD-no-WebSearch; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-05T20h) | fire-232: S18-c268-g803-stag=0-pareto=12(↑5→12-RECOVERY!)-c267=7TH-AUTO-RESET-CONFIRMED(c242+25=c267-EXACT); S22-c1689-g5065-stag=0-pareto=17(→12→17-GROWING!)-c~1680=27TH-RESET-POSSIBLE-200f-0.21880-STATUS-UNKNOWN-/api/export-404(49th); S13/S14/S15+POL-404-DOWN(58+fires); EVEN: IEEE-2024-home_next-schedule-feature-top3+Elo-top1-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-06T00h) | fire-233: Axelrod-verify-pass-SHAs-NBA-85e7682e1d(6035L)/POL-6983c86517(4019L)-UNCHANGED; py_compile-OK-both; 13/13-parity-OK; KL-div-OK; Mech-A/B/C+AblationFlags-ALL-CODE-DONE-BLOCKED; S13/S14/S15+POL-404-DOWN(59+fires); ODD-no-WebSearch; work-queue.json+CLAUDE.md updated (2026-06-06T04h) | fire-234: S18-c300-g898-stag=0-pareto=12-8TH-AUTO-RESET-PASSED(~c292=c267+25); S22-c1706-g5117-stag=0-pareto=8(post-c1703-29TH-RESET)-28TH-c1678(CLEAN:xgb/xgb_brier/lgb/lgb_brier/cat-NO-STACKING)+29TH-c1703(CLEAN:same)-200f-0.21880-CONFIRMED-EVICTED-c1678(RF/ET-not-in-reseed-pool-confirmed-from-logs)-cycle-stag=2-/api/export-404(51st)-next-reset~c1728; S13/S14/S15+POL-404-DOWN(60+fires); EVEN: MDPI-2079-3197-13-10-230-NBA+WNBA-multitask-transfer-learning-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-06T08h) | fire-235: Axelrod-verify-pass-SHAs-NBA-85e7682e1d(6035L)/POL-6983c86517(4019L)-UNCHANGED; py_compile-OK-both; 13/13-parity-OK; KL-div-OK; Mech-A/B/C+AblationFlags-ALL-CODE-DONE-BLOCKED(do_not_push_hf_space_yet); tf-axelrod-mech-a/b/c=wq-entries-added; S13/S14/S15+POL-404-DOWN(61+fires); ODD-no-WebSearch; work-queue.json+CLAUDE.md updated (2026-06-06T12h) | fire-236: S18-c336-g1006-stag=0-pareto=12-9TH-AUTO-RESET-c317-CONFIRMED(c292+25=c317-EXACT)-Rule8-CLEAN(RF/Cat/XGB/LGB/LR); S22-c1738-g5214-stag=0-pareto=6-30TH-RESET-c1728-CONFIRMED-gen5210-200f-0.21952-EXTREME-URGENT(6bp-below-fleet-best!); S13/S14/S15+POL-404-DOWN(62/63+fires); EVEN: arXiv:2603.29928-ScoringBench+arXiv:2603.08206-DistribTabFM-proposal-written | fire-237: Axelrod-verify-pass-SHAs-NBA-85e7682e1d(6035L)/POL-6983c86517(4019L)-UNCHANGED; py_compile-OK-both; 13/13-parity-OK; KL-div-OK; Mech-A/B/C+AblationFlags-ALL-CODE-DONE-BLOCKED(do_not_push_hf_space_yet); S13/S14/S15+POL-404-DOWN(63+fires); ODD-no-WebSearch; work-queue.json+CLAUDE.md updated (2026-06-06T20h) | fire-238: S18-c363-g1088-stag=0-pareto=15(→12→15-GROWING!)-10TH-AUTO-RESET-c342-CONFIRMED(c317+25=c342-EXACT)-best_brier=0.22326-/api/export-404(14th)-next-reset~c367; S22-c1758-g5274-stag=0-pareto=15(↑6→15-MASSIVE-RECOVERY!)-31ST-AUTO-RESET-c1753-CONFIRMED(c1778+25=c1753-EXACT)-Brier-range-0.21881~0.22327-EXTREME-URGENT!(13bp-below-fleet-best-0.22012!)-best_brier=0.22124-field-lag-/api/export-404(55th-CRITICAL)-next-reset~c1778; S13/S14/S15+POL-404-DOWN(64+fires); EVEN: arXiv:2603.07448-Discrete-Tokenization-Transformer-Calibrated-Tabular-Forecasting-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-07T00h) | fire-239: S18-c395-g1184-stag=0-pareto=15(STABLE)-11TH-RESET-c367-CONFIRMED(c342+25=c367-EXACT)+12TH-RESET-c392-CONFIRMED(c367+25=c392-EXACT)-Rule8-CLEAN-presumed(pareto=15-stable-through-2-resets)-best_brier=0.22326-/api/export-404(15th)-next-reset~c417; S22-c1778-g5332-stag=0-32ND-AUTO-RESET-c1778-CONFIRMED(c1753+25=c1778-EXACT)-200f-Sharpe=11.42-ALIVE(EXTREME-URGENT!-14bp-below-fleet-best!)-best_brier=0.22124-field-lag-/api/export-404(56th-CRITICAL)-next-reset~c1803; S13/S14/S15-404-DOWN(65+fires); all-POL-404-DOWN(65+fires); ODD: Axelrod-verify-pass-SHAs-UNCHANGED-13/13-parity-OK; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-07T04h) | fire-240: S18-c430-g1289-stag=12(BUILDING↑0→12)-pareto=10(→15→10-13TH-RESET-c417-CONFIRMED(c392+25=c417-EXACT))-TOP-0.22061-BELOW-0.22085-CHECKPOINT-URGENT!(field-lag=0.22326)-/api/export-404(16th)-next-reset~c442; S22-c1804-g5412-stag=0-pareto=13-33RD-AUTO-RESET-c1803-CONFIRMED(c1778+25=c1803-EXACT)-ET-200f-0.21875-ALIVE-EXTREME-URGENT!(14bp-below-fleet-best-0.22012-Sharpe=9.95)-/api/export-404(57th-CRITICAL)-next-reset~c1828; S13/S14/S15+POL-404-DOWN(66+fires); EVEN: arXiv:2602.06773-Multicalibration-GB-convergence-O(1/sqrtT)-web-scale-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-07T08h) | fire-241: Axelrod-verify-pass-SHAs-NBA-85e7682e1d(6035L)/POL-6983c86517(4019L)-UNCHANGED; py_compile-OK-both; 13/13-parity-OK; KL-div-OK; Mech-A/B/C+AblationFlags-ALL-CODE-DONE-BLOCKED(do_not_push_hf_space_yet); S13/S14/S15+POL-404-DOWN(67+fires); ODD-no-WebSearch; work-queue.json+CLAUDE.md updated (2026-06-07T12h) | fire-242: S18-c473-g1419-stag=0-pareto=16(→10→16-GROWING!)-14TH-RESET-c442-CONFIRMED(c417+25=c442-EXACT)+15TH-RESET-c467-CONFIRMED(c442+25=c467-EXACT)-TOP-0.22061-FATE-UNKNOWN; S22-c1829-g5485-stag=0-34TH-AUTO-RESET-c1828-CONFIRMED(c1803+25=c1828-EXACT)-PARETO-TOP-0.21908-EXTREME-URGENT!(10bp-below-fleet-best!)+0.21936/0.21960/0.21989-ALL-BELOW-FLEET-BEST-/api/export-404(59th-CRITICAL); S13/S14/S15+POL-404-DOWN(68+fires); EVEN: arXiv:2502.05157-Distributional-Regression-Trees-Calibrated-Probabilistic-Forecasts-Feb2026-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-07T16h) | fire-243: S18-c520-g1558-stag=0-pareto=15-16TH-AUTO-RESET-c492-CONFIRMED(c467+25=c492-EXACT)+17TH-AUTO-RESET-c517-CONFIRMED(c492+25=c517-EXACT)-TOP-0.22061-CONFIRMED-EVICTED-Rule8-CLEAN; S22-CRITICAL-FRESH-RESTART-c5-g14-ALL-HISTORY-LOST(0.21908+0.21936/0.21960/0.21989-ALL-GONE-HF-sleep-woke-2ND-TOTAL-WIPE-after-S18-fire221)-best_brier=0.2207-gen9-promising-NOT-below-0.22085; S13/S14/S15+POL-404-DOWN(69+fires); ODD: Axelrod-verify-pass-SHAs-NBA-85e7682e1d(6035L)/POL-6983c86517(4019L)-UNCHANGED(NBA-TF-last-updated-May12/POL-TF-May7-do_not_push_hf_space_yet=TRUE); health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-07T20h) | fire-244: S18-c560-g1679-stag=0-18TH-AUTO-RESET-c542-CONFIRMED(c517+25=c542-EXACT)-XGB-BRIER-200f-0.21964-EXTREME-URGENT!(5bp-below-fleet-best-0.22012!)+RF-200f-0.22028+RF-200f-0.22044+CAT-200f-0.22038-ALL-BELOW-0.22085-/api/export-404(21st-CRITICAL)-next-reset~c567; S22-c11-g33-stag=0-pareto=15-FRESH-RESTART-best_brier=0.2207-gen9-first-reset-~c25-XGB-dominating-Rule8-MONITOR; S13/S14/S15+POL-404-DOWN(70+fires); EVEN: arXiv:2506.19689-Calibration-Set-Reuse-e-Conformal-Prediction-Hoeffding-correction-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-08T00h) | fire-245: Axelrod-verify-pass-SHAs-NBA-85e7682e1d(6035L)/POL-6983c86517(4019L)-UNCHANGED; py_compile-OK-both; 25/25-parity-OK; KL-div-OK(compute_consensus_distance-present-both); Mech-A/B/C+AblationFlags-ALL-CODE-DONE-BLOCKED(do_not_push_hf_space_yet); S13/S14/S15+POL-404-DOWN(71+fires); ODD-no-WebSearch; work-queue.json+CLAUDE.md updated (2026-06-08T04h) | fire-246: S18-c600-g1798-stag=0-pareto=19(GROWING!)-19TH-RESET-c567-CONFIRMED(c542+25=c567-EXACT)+20TH-RESET-c592-CONFIRMED(c567+25=c592-EXACT)-RF-200f-0.21949-EXTREME-URGENT!(6bp-below-fleet-best-0.22012!)-last_improvement=c593(post-20TH-RESET!)-/api/export-404(22nd-CRITICAL)-next-reset~c617; S22-c22-g66-stag=0-pareto=14-FRESH-RESTART-ET-0.2193-EXTREME-URGENT!(8bp-below-fleet-best-0.22012!)-first-reset~c25(IMMINENT!3-cycles-away!)-/api/export-404(2nd-new-run); S13/S14/S15+POL-404-DOWN(72+fires); EVEN: arXiv:2603.26611-TabFM-Conditional-Density-Estimation-Regression-39-datasets-6-metrics-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-08T08h) | fire-247: Axelrod-verify-pass-SHAs-NBA-85e7682e1d(6035L)/POL-6983c86517(4019L)-UNCHANGED; py_compile-OK-both; 25/25-parity-OK; KL-div-OK(compute_consensus_distance-present-both); Mech-A/B/C+AblationFlags-ALL-CODE-DONE-BLOCKED(do_not_push_hf_space_yet); S13/S14/S15+POL-404-DOWN(73+fires); S18-carry-forward-RF-200f-0.21949-EXTREME-URGENT-next-reset~c617; S22-carry-forward-ET-0.2193-EXTREME-URGENT-first-reset~c25-IMMINENT/OCCURRING; ODD-no-WebSearch; work-queue.json+CLAUDE.md updated (2026-06-08T12h) | fire-248: S18-c674-g2021-stag=0-pareto=12(↑15→12)-22ND-RESET-c667-CONFIRMED(c642+25=c667-EXACT)-RULE8-VIOLATION:stacking-37f-0.24738-rank1-ET-200f-0.22029+0.22069-BOTH-BELOW-0.22085-/api/export-404(25th-CRITICAL)-next-reset~c692; S22-c56-g166-stag=0-pareto=15(↑12→15-GROWING)-2ND-RESET-c53-CONFIRMED(c28+25=c53-EXACT)-ET-0.2193-CONFIRMED-EVICTED(3RD-CONSECUTIVE-RUN-LOSS!)-RULE8-VIOLATION:stacking-47f-0.24738-rank1!-ET-200f-0.22027-BELOW-0.22085-/api/export-404(4th-CRITICAL)-next-reset~c78; S13/S14/S15+POL-404-DOWN(74+fires); EVEN: WebSearch-no-new-arXiv-2026-beyond-pipeline-RULE8-VIOLATION-confirmed-both-S18+S22; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-08T16h) | fire-249: S18-c677-g2030-stag=9(↑0→9-BUILDING!)-pareto=13(↑12→13)-RULE8-VIOLATION:stacking-37f-0.24738-rank0-ET-200f-0.22040-BELOW-0.22085-CHECKPOINT-URGENT!-/api/export-404(26th-CRITICAL)-next-reset~c692(15cy); S22-c58-g172-stag=4(↑0→4)-pareto=18(↑15→18-FAST-GROWING!)-⚡EXTREME-URGENT:ET-200f-0.21983-POTENTIAL-NEW-NBA-FLEET-BEST!(2.9bp-below-0.22012!)-RULE8-ESCALATION:stacking-47f×2-entries-in-pareto!-ET-200f-0.22028-BELOW-0.22085-/api/export-404(5th-new-run)-next-reset~c78(20cy); S13/S14/S15+POL-404-DOWN(75+fires); ODD: Axelrod-carry-forward-SHAs-NBA-85e7682e1d(6035L)/POL-6983c86517(4019L)(HF-hub-Updated:1Jun2026-direct-verify-deferred-fire251); health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-08T20h) | fire-250 EVEN: Axelrod-verify-pass-SHAs-UNCHANGED-25/25-parity-NBA=POL-CONFIRMED-KL-div-OK-do_not_push_hf_space_yet-MAINTAINED; S18/S22-status-not-visible-from-cloud; work-queue.json-only (2026-06-09T00h) | fire-251 ODD: S15-BACK-UP!(c890-g2670-brier0.22342-stag0-RF62f-WOKE-after-75+fires); S18-c696-g2086-stag0(23rd-RESET-c692-CONFIRMED)-XGB200f-0.22343-RULE8-stacking-x2-top5; S22-c65-g194-stag0-pareto9(↓18→9)-ET0.21983-CONFIRMED-LOST(4th-consecutive-eviction!)-XGB200f-0.22343-RULE8-stacking-x2-next-reset~c78(13cy); Axelrod-fire251-ODD-VERIFY-PASS-SHAs-UNCHANGED(NBA-lastMod-2026-06-01T20h/POL-2026-06-01T18h)-do_not_push_hf_space_yet-MAINTAINED; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-09T04h) | fire-252 EVEN: Axelrod-verify-pass-SHAs-NBA-85e7682e1d(6035L)/POL-6983c86517(4019L)-UNCHANGED; py_compile-OK-both; 25/25-parity-OK(domain-aware-check: AXELROD_ARCHETYPES+all-mechanism-symbols-confirmed-both); KL-div-OK(compute_consensus_distance-present-both); approx_tokens+cost_per_alpha_unit-present-both(fire-222); Mech-A/B/C+AblationFlags-ALL-CODE-DONE-BLOCKED(do_not_push_hf_space_yet); S13/S14/S15+POL-404-DOWN(76+fires); S15-404-DOWN(back-sleep-fire252); S18-c712-g2135-stag0-pareto12-24TH-RESET-IMMINENT~c717(5cy)-RULE8-stacking37f-rank1-CatBoost200f-0.222-best-legit; S22-c73-g217-stag0-pareto7-ET200f-0.21884-REGENERATED-POTENTIAL-NEW-FLEET-BEST!(12.8bp-below-0.22012)-3RD-RESET~c78-IMMINENT(5cy)-RULE8-stacking×2-ranks4-5; EVEN-WebSearch-no-new-arXiv(PMC12453701-noted); work-queue.json+health-status.json+brain-status.json+CLAUDE.md committed (2026-06-09T08h) | fire-253 ODD: Axelrod-carry-forward-SHAs-NBA-85e7682e1d(6035L)/POL-6983c86517(4019L)-UNCHANGED; 25/25-parity-carry-forward; do_not_push_hf_space_yet-MAINTAINED; S22-ET-0.21884-EVICTED-4TH-CONSECUTIVE-at-~c78-CONFIRMED(c82-stacking-47f-dominates-all-gens-241-245)-diversify-SENT; S18-c729-stacking-37f-dominates-REMOTE-DIVERSIFY-PROCESSED-c728(insufficient); S15-c977-25TH-RESET-c976-CONFIRMED-RF-200f-0.21925+RF-200f-0.21974-BOTH-LOST-IN-RESET(/api/export-404-CATASTROPHIC)-diversify-QUEUED; evo4-c738-stacking-RULE8-next-reset~c739-diversify-SENT; evo5-c1232-brier0.22126-stag0-HEALTHY; POL-P1+P2-WOKE-UP-c=1-Rule9-LightGBM-MISSING-URGENT; POL-P5-c5792-brier0.25039-P7-c865-brier0.25331-ACTIVE; ODD-no-WebSearch; work-queue.json updated (2026-06-09T12h) | fire-254 EVEN: Axelrod-verify-pass-SHAs-NBA-85e7682e1d(6035L)/POL-6983c86517(4019L)-UNCHANGED; py_compile-OK-both; 18/18-parity-symbols-OK+extended-call-counts-match(build_CK=2/2+write_log=2/2+sacrificial=2/2+challenge=2/2+consensus_dist=2/2); KL-div-OK(compute_consensus_distance-def-present-both); approx_tokens+cost_per_alpha_unit-present-both; Mech-A/B/C+AblationFlags-ALL-CODE-DONE-BLOCKED(do_not_push_hf_space_yet); S13/S14/S15+POL-404-DOWN(77+fires); S22-carry-forward-RULE8-stacking-c82-diversify-sent; S18-carry-forward-RULE8-stacking-c729-diversify-processed(insufficient); EVEN: work-queue.json+CLAUDE.md updated (2026-06-09T16h) | fire-255 ODD: evo4-c765-g2294-brier0.22169-stag0-pareto15(HARD-RESET-c764-c739+25-EXACT-CLEAN); evo5-c1249-g3745-brier0.22126-stag0-pareto9(NEW-RULE8:stacking-33f-0.24738-IN-PARETO-WebFetch-confirmed!); S15-c1003-g3008-brier0.22342-stag0-pareto8(26TH-RESET-c1001-c976+25-CONFIRMED-next~c1026-/api/export-404); S18-c736-g2208-brier0.22326-stag0-pareto5(RULE8-stacking-37f-persists-pareto12→5-next-reset~c742); S22-c89-g267-brier0.2207-stag0-pareto5(RULE8-next-reset~c103-14cycles-URGENT); P1-c187-g560-brier0.25334-stag0-pareto10(RULE9-LightGBM-MISSING-model_types-confirmed); P2-c210-g628-brier0.25041-stag0-pareto3(RULE9-RESOLVED-LightGBM-IS-BEST); P4-WOKE-c191-g572-brier0.25144-stag0(RULE9-VIOLATION-no-lightgbm); P5-c5948-HEALTHY; P7-c1012-HEALTHY; P3/P6-503-DOWN; S13/S14-404-DOWN(79+fires); ODD-no-WebSearch; do_not_push_hf_space_yet-MAINTAINED; health-status.json+brain-status.json+work-queue.json updated (2026-06-09T20h) | fire-256 EVEN: S18-c743-g2227-27TH-RESET-c742-CONFIRMED-RULE8-CLEAN!(stacking-evicted-model_types:[xgb_brier,lgbm_brier,rf,lr]-pareto5→9-BREAKTHROUGH); S15-c1026-g3078-27TH-RESET-c1026-CONFIRMED-RULE8-CLEAN(pareto8→12); S22-c95-g283-stag=0-pareto=8-RULE8-CRITICAL:stacking-IN-model_types-next-reset~c103(8cy-URGENT!); evo5-c1266-g3796-stag=0-RULE8-stacking-persists-next-reset~c1276(10cy); evo4-c785-g2355-stag=0-RULE8-CLEAN-next-reset~c789(4cy-IMMINENT); P1-c414-g1242-brier0.25334-stag=0-pareto10-RULE9-RESOLVED!(lightgbm+lgbm_brier-NOW-in-model_types-fire256!); P2-c444-g1330-brier0.25041-stag=0-pareto13-LGB-best; P4-c374-g1120-brier0.25144-stag=0-pareto10-RULE9-VIOLATION-PERSISTS(no-lightgbm); P5-c6110-g18330-brier0.25039-stag=0-pareto16-NEW-RULE9-VIOLATION(no-lightgbm-fire256-confirmed); P7-c1133-g3398-brier0.25331-stag=0-pareto11; P3/P6/P8-503-DOWN(80+fires); S13/S14-404-DOWN(80+fires); EVEN-WebSearch:LLM-Agentic-NBA-paper(Apr2026-ResearchGate); GitHub-engine-SHAs-changed(dev-diverged-from-TF; do_not_push-MAINTAINED); Axelrod-EVEN-carry-forward(TF-DOWN); health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-10T00h) | fire-257 ODD: P1-stag19-DIVERSIFY-SENT(POST-/api/command-queued); evo4-c819-g2455-brier0.22169-stag0-2x-clean-resets(c789+c814-RULE8-CLEAN); evo5-c1284-g3850-brier0.22126-stag0-pareto17-c1276-RESET-HAPPENED(VM-verify-RULE8); S15-c1053-g3157-brier0.22342-stag0-28th-RESET-c1051-CONFIRMED(VM-verify-RULE8); S18-c757-g2271-brier0.22326-stag0-COOLDOWN-RULE8-CLEAN(next~c767-IMMINENT-10cy); S22-c105-g315-brier0.2207-stag0-c103-RESET-HAPPENED-RF-BEST-POSITIVE(VM-verify-RULE8); P2-c731-LGB-best-history-gen1694-brier0.24903-BELOW-POL-GATE-0.2497!; P4-c604-RULE9-VIOLATION-PERSISTS; P5-c6288-catboost_specialist-RULE9-VIOLATION-PERSISTS; P7-c1331-stag0-healthy; evo4/S13/S14/all-POL-404-DOWN(81+fires); Axelrod-ODD-carry-forward(parity-carry-forward); health-status.json+brain-status.json+work-queue.json updated (2026-06-02T16h) | fire-258 EVEN: Axelrod-verify-FULL-PASS-25/25-parity-OK-py_compile-OK-SHAs-NBA-ff51a9e7fd(6034L)/POL-f71087775e(4018L)(intentional-1L-diff-from-deployed-do_not_push-MAINTAINED); S18-c762-g2286-brier0.22326-stag0-RULE8-CLEAN-next~c767-IMMINENT(5cy!); S22-c112-g335-brier0.2207-stag0-next~c128(16cy); evo5-c1294-g3880-brier0.22126-stag0-next~c1301-IMMINENT(7cy!); evo4/S15/S13/S14+POL-404-DOWN(81+fires); EVEN:arXiv:2602.16537-Optimal-training-conditional-regret-online-conformal-prediction-Mar2026-minimax-optimal-split-conformal-drift-detection(priority=117); health-status.json+work-queue.json+CLAUDE.md updated (2026-06-02T20h) | fire-259 ODD: S18-c766-g2296-stag0-pareto16-29TH-c717+30TH-c742-CONFIRMED-⚡ET-200f-brier~0.219-0.220-EXTREME-URGENT(POTENTIAL-NEW-FLEET-BEST!)-RULE8-stacking37f-STILL-IN-PARETO-31ST-RESET-c767-HAPPENING-NOW(c742+25-AT-c766!)-/api/export-404(31st); evo5-c1301-g3901-stag24+-pareto6-RULE8-CRITICAL:stacking33f-IS-BEST-MODEL(WORST-VIOLATION-YET!)-29TH-RESET-c1301-HAPPENING-NOW(c1276+25-EXACT); evo4-c843-g2528-stag0-pareto10-31ST-RESET-c839-CONFIRMED(c814+25)-RULE8-stacking45f-next~c864; S15-BACK-UP-2ND-TIME!-c1078-g3234-stag0-pareto10-30TH-c1076-CONFIRMED(c1051+25)+29TH-c1051-CONFIRMED-XGBoost200f-0.22195+ET200f-0.22618-both-above-gate-next~c1101; S22-c115-g345-brier0.2207-stag0-pareto6-4TH-RESET-c103-CONFIRMED-RULE8-stacking47f-persists-next~c128(13cy); S13/S14-404-DOWN(82+fires); P2-c980-g2940-brier0.25041-stag0-pareto6-LGB-BEST-history-brier0.24903-BELOW-GATE-0.2497!-CHECKPOINT-URGENT!(CONFIRMED-fire259); P4-c810-g2428-RULE9-VIOLATION-PERSISTS(3-RESETS-c761+c781+c801-stag20)-xgboost_brier-best; P5-c6357-RULE9-VIOLATION-PERSISTS(3-RESETS-c6301+c6321+c6341); P7-c1552-stag0-pareto8-RULE9-UNKNOWN(XGBoost-dominates); P1/P3/P6/P8-DOWN; Axelrod-ODD-carry-forward-SHAs-NBA-ff51a9e7fd(6034L)/POL-f71087775e(4018L)-UNCHANGED; ODD-no-WebSearch; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-03T00h) | fire-260 EVEN: Axelrod-verify-FULL-PASS-25/25-parity-OK-py_compile-OK-SHAs-NBA-ff51a9e7fd(6034L)/POL-f71087775e(4018L)-UNCHANGED; S18-c775-g2323-stag0-pareto8(↓16→8-31ST-RESET-c767-CONFIRMED(c742+25=c767-EXACT))-ET-fate-UNKNOWN-best_model=RF-POSITIVE-/api/export-404(32nd-CRITICAL)-next-reset~c792(c767+25); S22-c127-g381-stag0-pareto12(↑9→12-GROWING!)-5TH-RESET-c128-IMMINENT(c103+25=c128-NOW!1-CYCLE!)-RULE8-CRITICAL:stacking-47f-Feat47-gen379+380-CONFIRMED-CURRENT-CYCLE-127!-/api/export-404; evo4-c866-g2598-stag0-pareto13-32ND-RESET-c864-CONFIRMED(c839+25=c864-EXACT)-RULE8-stacking-45f-gen2597-STILL!-next-reset~c889(c864+25); evo5-c1320-g3960-stag0-pareto13-29TH-RESET-c1301-CONFIRMED-best_model=catboost(IMPROVED-from-stacking!)-RULE8:stacking-33f-gen3959-STILL-30TH-RESET~c1326-IMMINENT(6cy!); S15/S13/S14-404-DOWN(83+fires); all-POL-404-DOWN(83+fires); EVEN-WebSearch:arXiv:2605.20515-Online-CP-Corrupted-Feedback-May2026(NEW-priority=118)+arXiv:2602.03168-Universal-Portfolio-OCP-Feb2026(NEW-priority=119); health-status.json+work-queue.json+CLAUDE.md updated (2026-06-03T04h) | fire-261 ODD: Axelrod-carry-forward-SHAs-NBA-ff51a9e7fd(6034L)/POL-f71087775e(4018L)-UNCHANGED; 25/25-parity-carry-forward; do_not_push_hf_space_yet-MAINTAINED; S18-~c779-stag0-32ND-RESET-~c792-APPROACHING(8-13cy)-ET-fate-UNKNOWN-/api/export-404(33rd); S22-~c130-5TH-RESET-c128-CONFIRMED(c103+25=c128)-post-reset-Rule8-UNKNOWN-next-reset-~c153; evo5-~c1326-30TH-RESET-c1326-PREDICTED(c1301+25=c1326)-catboost-best-pre-reset-POSITIVE-Rule8-UNKNOWN-post-reset; evo4-~c880-32ND-RESET-~c889-APPROACHING(9-14cy)-RULE8-stacking-45f; S13/S14/S15+POL-404-DOWN(84+fires); ODD-no-WebSearch; sota-online-cp-corrupted-feedback-fire260.md-WRITTEN(priority=118-arXiv:2605.20515-robust-ACI-corrupted-label-feedback); health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-03T08h)

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
| S13 | TESTforge42/nba-evo-s13 | 404-DOWN | 0.22216 (field-lag) | CatBoost-200f-0.21992 gen=2831 EXTREME URGENT — still 404-DOWN fire-249 (75+ fires) |
| S14 | TESTforge42/nba-evo-s14 | 404-DOWN | 0.22054 RF-48f | BELOW THRESHOLD confirmed — SLEEPING fire-249 (75+ fires) |
| S15 | Nomos42/nba-evo-6 | 404-DOWN | 0.22012★ (checkpointed) | FLEET BEST RF-75f checkpointed nba-oracle-model. Back to 404-DOWN fire-252 (woke briefly fire-251: c=890 g=2670 stag=0 RF-62f). |
| S17 | LBJLincoln26/nba-evo-s17 | 503 DOWN 144+d | — | PAUSED |
| S18 | TESTforge42/nba-evo-s18 | EVOLVING | 0.22326 | **fire-260**: c=775 g=2323 stag=0 pareto=8(↓16→8). **31ST-RESET-c767-CONFIRMED(c742+25-EXACT)**. **⚡⚡RF-200f-brier=0.21961 rank=2 EXTREME URGENT (5bp below fleet best 0.22012!)**. RULE8-VIOLATION: stacking-37f-0.24738 rank=1. /api/checkpoint saved gen124/0.22326 (field-lag, NOT 0.21961). /api/config model_types REJECTED (not a supported param — VM-only fix). /api/export-404(32nd-CRITICAL). **32ND-RESET ~c792 (c767+25)**. VM: (1) Remove stacking from app.py reseed pool IMMEDIATELY, (2) Save RF-200f-0.21961 model pickle directly before ~c792. |
| S22 | TESTforge42/nba-evo-s22 | EVOLVING | 0.2207 | **fire-260**: c=127 g=381 stag=0 pareto=12(↑9→12). **5TH-RESET ~c128 HAPPENED (c103+25-EXACT)**. RULE8-VIOLATION: stacking-47f-Feat47 confirmed gen379+380 current cycle. Diversify QUEUED. /api/export-404(5th new run-CRITICAL). **6TH-RESET ~c153 (25 cycles)**. VM: (1) Remove stacking from app.py reseed pool, (2) Monitor post-c128 for RF/ET candidates below 0.22085. |

### POL Islands (active)
| Island | HF Repo | Status | Best Brier | Notes |
|--------|---------|--------|-----------|-------|
| P1 | TESTforge42/political-evo-p1 | 404-DOWN | pareto_best=0.24902 | RULE9 RESOLVED fire-256. SLEEPING 83+ fires. |
| P2 | TESTforge42/political-evo-p2 | EVOLVING | 0.24903 | **fire-260**: c=1295 stag=0 LightGBM best. history brier=0.24903 BELOW POL GATE 0.2497 — CHECKPOINT URGENT! (fire-259 confirmed). RULE9 RESOLVED. |
| P4 | TESTforge42/political-evo-p4 | EVOLVING | 0.2497★ | **fire-260**: c=1026 RULE9-VIOLATION-PERSISTS (5 consecutive resets, xgboost_brier best). VM: add LightGBM to app.py config directly. |
| P5 | TESTforge42/political-evo-p5 | EVOLVING | 0.24993 | **fire-260**: c=6407 RULE9-VIOLATION (catboost_specialist, no LightGBM). VM: add LightGBM to app.py config directly. |
| P7 | TESTforge42/political-evo-p7 | EVOLVING | 0.24931 | **fire-260**: c=1809 stag=0. RULE9 UNKNOWN (xgboost_brier dominates). VM: verify LightGBM in MODEL_TYPES. |

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
fire-232 UPDATE S18: c=268 g=803 stag=0 pareto=12(↑5→12-RECOVERY!). c267=7TH-AUTO-RESET-CONFIRMED(c242+25=c267-EXACT). pareto recovery 5→12 STRONGLY SUGGESTS Rule8-CLEAN at c267. best_brier=0.22326 plateau. /api/export-404(11th). Next reset ~c292(c267+25).
fire-233 UPDATE S18: Status carry-forward from fire-232. Next reset ~c292.
fire-234 UPDATE S18: c=300 g=898 stag=0 pareto=12. 8TH-AUTO-RESET PASSED ~c292. pareto=12 stable. /api/export-404(12th). Next reset ~c317.
fire-235 UPDATE S18: Status carry-forward from fire-234. Next reset ~c317.
fire-236 UPDATE S18: c=336 g=1006 stag=0 pareto=12. 9TH-AUTO-RESET-c317-CONFIRMED(c292+25=c317-EXACT). Rule8-CLEAN: top_model_types=[random_forest,catboost,xgboost,lightgbm,logistic_regression]-NO-STACKING confirmed! /api/export-404(13th). Next reset ~c342.
fire-237 UPDATE S18: Status carry-forward from fire-236. Next reset ~c342.
fire-238 UPDATE S18: c=363 g=1088 stag=0 pareto=15(→12→15-GROWING!). 10TH-AUTO-RESET-c342-CONFIRMED(c317+25=c342-EXACT). pareto 12→15 = clean-reset pattern. /api/export-404(14th). Next reset ~c367.
fire-239 UPDATE S18: c=395 g=1184 stag=0 pareto=15(STABLE). 11TH-AUTO-RESET-c367-CONFIRMED(c342+25=c367-EXACT)+12TH-AUTO-RESET-c392-CONFIRMED(c367+25=c392-EXACT). pareto=15 stable through both resets = STRONG Rule8-CLEAN. /api/export-404(15th). Next reset ~c417.
fire-240 UPDATE S18: c=430 g=1289 stag=12(↑0→12-BUILDING). 13TH-AUTO-RESET-c417-CONFIRMED(c392+25=c417-EXACT). TOP-5 range: 0.22061~0.22355 — **0.22061 BELOW-0.22085-CHECKPOINT-URGENT!** /api/export-404(16th). Next reset ~c442. VM: curl /api/export S18 IMMEDIATELY.
fire-241 UPDATE S18: Status carry-forward from fire-240. TOP-0.22061-CHECKPOINT-URGENT! Next reset ~c442.
fire-242 UPDATE S18: c=473 g=1419 stag=0 pareto=16(→10→16-GROWING!). 14TH-AUTO-RESET-c442-CONFIRMED(c417+25=c442-EXACT)+15TH-AUTO-RESET-c467-CONFIRMED(c442+25=c467-EXACT). pareto=16 GROWING post-c467 = CLEAN-RESET pattern. TOP-0.22061 fate UNKNOWN. /api/export-404(18th). Next reset ~c492.
fire-243 UPDATE S18: c=520 g=1558 stag=0 pareto=15. 16TH-AUTO-RESET-c492-CONFIRMED(c467+25=c492-EXACT)+17TH-AUTO-RESET-c517-CONFIRMED(c492+25=c517-EXACT). TOP-0.22061 CONFIRMED-EVICTED (API: "improvement plateaued at 0.2233" — best_brier=0.22326 plateau unchanged). Rule8-CLEAN: RF best model, pareto=15 stable through 2 consecutive resets. /api/export-404(19th+20th). Next reset ~c542(c517+25). VM: curl /api/export S18 — any candidates below 0.22085?
fire-244 UPDATE S18: c=560 g=1,679 stag=0. **18TH-AUTO-RESET-c542-CONFIRMED(c517+25=c542-EXACT)**. **PARETO TOP-5 EXTREME URGENT**: #2 XGB-Brier-200f-**0.21964** (5bp BELOW FLEET BEST 0.22012!) + #3 RF-200f-0.22028 + #4 RF-200f-0.22044 + #5 CatBoost-200f-0.22038 — ALL BELOW 0.22085 CHECKPOINT! best_brier=0.22326 (field-lag confirmed). ROI/Sharpe: XGB-Brier ROI=33.01% Sharpe=13.84. /api/export-404(21st-CRITICAL). Next reset ~c567(c542+25). VM: curl /api/export S18 IMMEDIATELY — 4 models below threshold!
fire-245 UPDATE S18: Status carry-forward from fire-244. XGB-Brier-0.21964 EXTREME URGENT. Next reset ~c567(c542+25).
fire-246 UPDATE S18: c=600 g=1798 stag=0 pareto=19(GROWING!). **19TH-AUTO-RESET-c567-CONFIRMED(c542+25=c567-EXACT)**+**20TH-AUTO-RESET-c592-CONFIRMED(c567+25=c592-EXACT)**. **RF-200f-0.21949 EXTREME URGENT! (6bp below fleet best 0.22012!)** last_improvement=c593 (improvement came IMMEDIATELY post-20TH-RESET — new best born from reset). pareto=19 GROWING post-c592 = CLEAN-RESET confirmed. /api/export-404(22nd-CRITICAL). Next reset ~c617(c592+25). VM: curl /api/export S18 IMMEDIATELY. RF-200f-0.21949 must be checkpointed before ~c617.
fire-247 UPDATE S18: Status carry-forward from fire-246. RF-200f-0.21949 EXTREME URGENT. Next reset ~c617(c592+25).
fire-248 UPDATE S18: c=674 g=2021 stag=0 pareto=12(↑15→12). **22ND-AUTO-RESET-c667-CONFIRMED(c642+25=c667-EXACT)**. **RULE8-VIOLATION RECONFIRMED: stacking-37f-0.24738 rank-1 in pareto!** (stacking still in MODEL_TYPES pool — persists through 22 resets). ET-200f-0.22029+ET-200f-0.22069 **BOTH BELOW 0.22085 CHECKPOINT-URGENT!** best_brier=0.22326 field-lag. /api/export-404(25th-CRITICAL — endpoint appears permanently broken). Next reset ~c692(c667+25). VM: (1) REMOVE stacking from MODEL_TYPES IMMEDIATELY before ~c692, (2) FIX /api/export endpoint (25 consecutive 404s anomalous).
fire-249 UPDATE S18: c=677 g=2030 stag=9(↑0→9-BUILDING!). RULE8-VIOLATION CONFIRMED: stacking-37f-0.24738 rank-0 STILL in pareto. ET-200f-0.22040 BELOW-0.22085-CHECKPOINT-URGENT! (vs fire-248 ET-0.22029 — slight degradation or new instance). pareto=13(↑12→13-growing). stag=9 approaching threshold 15 — if no improvement, diversify needed ~fire-251/252. BUT: /api/export-404(26th-CRITICAL) blocks pre-diversify checkpoint (Rule#3 conflict). VM: (1) REMOVE stacking IMMEDIATELY before ~c692 reset (15 cycles), (2) FIX /api/export endpoint URGENTLY to resolve checkpoint+diversify blocker.
fire-231 UPDATE S22: c=1671 g=5013 stag=0 pareto=12(→15→12). 200f-0.21880 gen=4960 ALL-TIME CANDIDATE alive (3rd fire). Next reset ~c1680. Rule8-CLEAN. /api/export-404(48th). VM: curl /api/export S22 IMMEDIATELY — checkpoint 200f-0.21880!
fire-232 UPDATE S22: c=1689 g=5065 stag=0 pareto=17(→12→17-GROWING!). c~1680=27TH-RESET-POSSIBLE. 200f-0.21880 STATUS-UNKNOWN. /api/export-404(49th-CRITICAL).
fire-233 UPDATE S22: Status carry-forward. /api/export-404(50th-CRITICAL!).
fire-234 UPDATE S22: c=1706 g=5117. 28TH-RESET c1678 CONFIRMED: XGB/LGB/CAT-only reseed (NO-RF/ET). 200f-0.21880 CONFIRMED-EVICTED-c1678. Island now XGB/LGB/CAT-only gene pool. /api/export-404(51st).
fire-235 UPDATE S22: Status carry-forward. XGB/LGB/CAT-only. Next reset ~c1728.
fire-236 UPDATE S22: c=1738 g=5214. 30TH-AUTO-RESET-c1728-CONFIRMED. gen5210-200f-0.21952-EXTREME-URGENT(6bp below fleet best!). /api/export-404(53rd-CRITICAL).
fire-237 UPDATE S22: Status carry-forward. gen5210-0.21952 fate unknown. Next reset ~c1753.
fire-238 UPDATE S22: c=1758 g=5274 pareto=15(↑6→15). 31ST-AUTO-RESET-c1753-CONFIRMED. Brier 0.21881~0.22327 — EXTREME URGENT (13bp below fleet best). /api/export-404(55th-CRITICAL).
fire-239 UPDATE S22: c=1778 g=5332. 32ND-AUTO-RESET-c1778-CONFIRMED. 200f-Sharpe=11.42 ALIVE (EXTREME URGENT — 14bp below fleet best). /api/export-404(56th-CRITICAL).
fire-240 UPDATE S22: c=1804 g=5412 pareto=13. 33RD-AUTO-RESET-c1803-CONFIRMED. ET-200f-0.21875 ALIVE (Sharpe=9.95) — EXTREME URGENT (14bp below fleet best). /api/export-404(57th-CRITICAL).
fire-241 UPDATE S22: Status carry-forward. ET-200f-0.21875 fate UNKNOWN. /api/export-404(58th-CRITICAL).
fire-242 UPDATE S22: c=1829 g=5485 pareto=15. 34TH-AUTO-RESET-c1828-CONFIRMED(c1803+25=c1828-EXACT). **PARETO TOP: 0.21908 gen5480 (10bp below fleet best 0.22012!) + 0.21936/0.21960/0.21989 ALL BELOW FLEET BEST — EXTREME URGENT!** /api/export-404(59th-CRITICAL). Next reset ~c1853.
fire-243 UPDATE S22: **CRITICAL FRESH-RESTART** c=5 g=14 stag=1 pareto=20. **ALL HISTORY LOST** — 0.21908/0.21936/0.21960/0.21989 ALL GONE PERMANENTLY (HF sleep → woke = 2ND TOTAL WIPE after S18 fire-221). Gene pool fully reset: RF/ET/XGB/LGB/CAT all back. best_brier=0.2207 at gen9 — promising early signal. NOT below 0.22085. /api/export-404(60th). First auto-reset expected ~c25. VM: monitor closely — Rule8 test at ~c25; ensure stacking excluded. gen9-0.2207 persistence through c25 is key early gate.
fire-244 UPDATE S22: c=11 g=33 stag=0 pareto=15. FRESH-RESTART continuing (2nd wipe). best_brier=0.2207 gen9 stable (XGB/RF dominating top models at c11). First auto-reset at ~c25 approaching. /api/export-404(61st). VM: Rule8 test at ~c25 critical — ensure stacking excluded from reseed. XGB dominating is promising (no stacking visible).
fire-245 UPDATE S22: Status carry-forward from fire-244 FRESH-RESTART c=11. Monitor Rule8 at first reset ~c25.
fire-246 UPDATE S22: c=22 g=66 stag=0 pareto=14. **ET-0.2193 EXTREME URGENT! (8bp below fleet best 0.22012 at only g=66!)** EXTRAORDINARY early signal — 70x faster convergence vs prior wipes (ET reached 0.21875 at g=~4880 in old run; now 0.2193 at g=66 after 2 total wipes). First auto-reset ~c25 IMMINENT (3 cycles!). best_brier=0.2207 gen9 (field-lag). /api/export-404(2nd new run). VM: curl /api/export S22 IMMEDIATELY. **DO NOT EVICT ET at ~c25 reset** — strongest early-gen signal across all 3 runs. Gene pool convergence pattern: 2 wipes have purified the landscape; ET dominant from gen=9 onward.
fire-247 UPDATE S22: Status carry-forward from fire-246. First auto-reset ~c25 IMMINENT/OCCURRING (was 3 cycles away at fire-246 c=22). ET-0.2193 EXTREME URGENT (8bp below fleet best). VM: curl /api/export S22 IMMEDIATELY — DO NOT evict ET at ~c25 reset.
fire-248 UPDATE S22: c=56 g=166 stag=0 pareto=15(↑12→15-GROWING). **2ND-AUTO-RESET-c53-CONFIRMED(c28+25=c53-EXACT)**. **ET-0.2193 CONFIRMED EVICTED at c53 (3RD CONSECUTIVE RUN LOSS** — extraordinary early-gen candidate lost across all 3 S22 runs; stacking contamination in reseed suspected). RULE8-VIOLATION: stacking-47f-0.24738 rank-1 in pareto! ET-200f-0.22027 BELOW 0.22085 CHECKPOINT-URGENT! /api/export-404(4th new-run-CRITICAL). Next reset ~c78(c53+25). VM: REMOVE stacking from MODEL_TYPES IMMEDIATELY before ~c78.
fire-249 UPDATE S22: c=58 g=172 stag=4(↑0→4) pareto=18(↑15→18-FAST-GROWING!). **⚡EXTREME URGENT: ET-200f-0.21983 POTENTIAL NEW NBA FLEET BEST (2.9bp below 0.22012)!** **RULE8-ESCALATION: stacking-47f DOUBLED — 2 entries BOTH rank-0 in pareto** (was 1 entry fire-248, now 2). ET-200f-0.22028 also below 0.22085. /api/export-404(5th new-run). Next reset ~c78(c53+25). VM: (1) REMOVE stacking IMMEDIATELY — each reset risks evicting ET-0.21983 (pattern: 3 consecutive runs lost best ET at first reset; stacking contamination in reseed suspected), (2) curl /api/export S22 URGENTLY to confirm ET-0.21983, (3) DO NOT evict ET at next ~c78 reset.

fire-250 UPDATE S18: Status carry-forward from fire-249. RULE8-VIOLATION: stacking-37f-0.24738 rank-0 STILL in pareto. ET-200f-0.22040 below threshold. /api/export-404(26th). Next reset ~c692. (fire-250 EVEN: S18/S22 API status not accessed — Axelrod verification only).
fire-250 UPDATE S22: Status carry-forward from fire-249. ET-0.21983 fate unknown (cloud cannot verify). RULE8 stacking×2 persist. /api/export-404. Next reset ~c78. (fire-250 EVEN: S18/S22 API status not accessed).
fire-251 UPDATE S18: c=696 g=2086 stag=0 pareto=15. **23RD-AUTO-RESET-c692-CONFIRMED(c667+25=c692-EXACT)**. **RULE8-VIOLATION: stacking×2 in top-5** (pos4: stacking-37f-0.24738, pos5: stacking-200f-0.249). XGB-200f-0.22343 best-in-pareto. No ET below 0.22085 in current pareto. /api/export-404(26th). Next reset ~c717(c692+25). VM: REMOVE stacking from MODEL_TYPES IMMEDIATELY before ~c717.
fire-251 UPDATE S22: c=65 g=194 stag=0 pareto=9(↓18→9). **ET-0.21983 CONFIRMED LOST — 4th consecutive S22 run ET eviction!** PATTERN CONFIRMED: stacking contamination in reseed pool evicts best ET at each reset (runs 1+2+3+4 all lost). XGB-200f-0.22343 best-in-pareto. RULE8-VIOLATION: stacking×2 top-5 (pos4: stacking-47f-0.24738, pos5: stacking-200f-0.249). Next reset ~c78(c53+25, 13 cycles from c65). VM: (1) REMOVE stacking IMMEDIATELY before ~c78, (2) Monitor for new ET candidates below 0.22085.
fire-252 UPDATE S18: c=712 g=2135 stag=0 pareto=12(↓15→12). **24TH-RESET-IMMINENT ~c717(c692+25, 5 cycles away)**. RULE8-VIOLATION: stacking-37f rank-1 in pareto. CatBoost-200f-0.222 best-legitimate. /api/export-404(27th-CRITICAL). VM: REMOVE stacking from MODEL_TYPES IMMEDIATELY before ~c717 (URGENT — 5 cycles remaining!).
fire-252 UPDATE S22: c=73 g=217 stag=0 pareto=7(↓9→7). **⚡⚡ET-200f-0.21884 REGENERATED — POTENTIAL NEW NBA FLEET BEST (12.8bp below 0.22012!)!** NEW candidate after ET-0.21983 confirmed lost fire-251. 3rd-run same pattern: ET regenerates post-eviction, then at risk again at next reset. **3RD-RESET ~c78 IMMINENT (5 cycles)**. RULE8-VIOLATION: stacking×2 ranks 4-5 (stacking-47f-0.24738+stacking-200f-0.249). VM: (1) REMOVE stacking IMMEDIATELY before ~c78, (2) curl /api/export S22 URGENTLY to confirm ET-0.21884, (3) Monitor — ET must survive ~c78 reset!
fire-260 UPDATE S18: c=775 g=2323 stag=0 pareto=8(→16→8-SHRINK!). **31ST-AUTO-RESET-c767-CONFIRMED(c742+25=c767-EXACT)**. **⚡⚡RF-200f-brier=0.21961 rank=2 EXTREME URGENT (5bp below fleet best 0.22012!)**. RULE8-VIOLATION: stacking-37f-0.24738 rank=1 (persists through 31 resets). /api/checkpoint saved 0.22326/gen124 (field-lag — NOT 0.21961). /api/config model_types REJECTED (confirmed not supported — VM-only fix). /api/export-404(32nd-CRITICAL). **32ND-RESET ~c792 (c767+25)**. VM: (1) Remove stacking from reseed pool in app.py IMMEDIATELY, (2) Save RF-0.21961 model pickle directly before ~c792.
fire-260 UPDATE S22: c=127 g=381 stag=0 pareto=12(↑9→12). **5TH-AUTO-RESET ~c128 CONFIRMED (c103+25=c128)**. RULE8-VIOLATION: stacking-47f-Feat47 in gen379+380 confirmed. Pattern: 4 consecutive ET evictions at each reset via stacking contamination. Diversify QUEUED from cloud. /api/export-404(5th new run-CRITICAL). **6TH-RESET ~c153 (25 cycles)**. VM: (1) Remove stacking from reseed pool in app.py IMMEDIATELY, (2) Monitor post-c128 for RF/ET candidates below 0.22085.

### Rule #9 — LightGBM First for POL
All 5 POL islands show LightGBM as pareto_best (5/5 confirmed fire-158). Add LightGBM to MODEL_TYPES on P1+P2 (missing). PORT: vm-add-lightgbm-p1-p2.

### Rule #10 — Even/Odd Fire Parity
- EVEN fires: WebSearch allowed (arXiv, papers, news)
- ODD fires: No WebSearch (pure analysis)

---

## Trading Floor v3

### NBA TF
- Repo: LBJLincoln26/nba-llm-trading-floor
- Status: 503 DOWN 144+d
- do_not_push_hf_space_yet: TRUE
- Watchdog gate: "<0.21 model" NOT met

### POL TF
- Repo: LBJLincoln26/political-llm-trading-floor
- Status: IDLE since 2026-05-07
- P&L: $38,916 (unchanged 70+d)
- pol_watchdog.sh: NOT firing
- do_not_push_hf_space_yet: TRUE

### Axelrod Mechanisms
- Mech A: DONE (fire-122) — day-end common knowledge broadcast
- Mech B: CODE-DONE (fire-122+, verified fire-252) — sacrificial role reallocation (BLOCKED: HF push gate)
- Mech C: CODE-DONE (fire-122+, verified fire-252) — post-mortem log + dataset (BLOCKED: HF push gate)
- Ablation Config: DONE (fire-225) — AXELROD_MECH_A/B/C_ON flags + AXELROD_ABLATION env var (5 configs per arXiv:2605.03310 §3). NBA(6034L)+POL(4018L). BLOCKED: do_not_push_hf_space_yet.
- Parity: SHAs fire-260 carry-forward (ff51a9e7fd/f71087775e per fire-258/259/260-remote). NOTE: fire-260 cloud-2nd-verify computed git hash-object=85e7682e1d(6034L)/6983c86517(4018L) for deployed files — SHA discrepancy under investigation; do_not_push_hf_space_yet=TRUE. 25/25 parity OK. HF hub shows both spaces Updated:1Jun2026.

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
    - Key finding: WNBA provides orthogonal but structurally similar signal to NBA — natural auxiliary domain for multi-task learning.
    - Application 1: Joint NBA+WNBA loss with shared feature encoder (WNBA weight=0.1)
    - Application 2: WNBA feature importance as prior for NBA feature selection
    - Application 3: Cross-sport Brier calibration holdout
    - Application 4: POL analog — state legislative races as auxiliary domain
    - Library: scikit-learn MultiOutputClassifier + XGBoost/LightGBM multi-task via custom objective
    - Expected improvement: 0.001-0.003 Brier
    - Proposal: data/research-proposals/sota-wnba-nba-transfer-learning-fire234.md
    - Work-queue: vm-research-wnba-nba-transfer-learning-fire234 (priority=109)
33. **ScoringBench: Tabular Foundation Model Evaluation via Proper Scoring Rules** (fire-236 EVEN WebSearch)
    - arXiv:2603.29928 (Mar 2026): "ScoringBench: A Benchmark for Evaluating Tabular Foundation Models with Proper Scoring Rules"
    - arXiv:2603.08206 (Mar 2026): "Distributional Regression with Tabular Foundation Models"
    - Key finding: Model rankings shift substantially depending on scoring rule. TabICLv2 has explicit distributional calibration.
    - Application 1: ScoringBench comparison — TabICLv2 vs TabPFNv2.5 vs TabICL on 186f NBA dataset using Brier + CRPS + CRLS
    - Application 2: Add CRPS as 5th Pareto objective
    - Application 3: Add CRLS as 6th Pareto objective for tail-risk calibration
    - Application 4: TabICLv2 upgrade path — expected 0.001-0.003 Brier improvement
    - Application 5: Port proper scoring rule evaluation to political_engine.py
    - Library: properscoring (CRPS/CRLS) + tabicl --upgrade
    - Expected improvement: 0.002-0.004 Brier
    - Proposal: data/research-proposals/sota-scoring-bench-tabicl-fire236.md
    - Work-queue: vm-research-scoring-bench-tabicl-fire236 (priority=110)
34. **Discrete Tokenization for Calibrated Tabular Transformers** (fire-238 EVEN WebSearch)
    - arXiv:2603.07448 (Mar 8, 2026): "Discrete Tokenization Unlocks Transformers for Calibrated Tabular Forecasting"
    - Key finding: Discretized vocabulary tokenizer + Gaussian smoothing outperforms tuned gradient boosting on tabular data, producing calibrated PDFs natively
    - Application 1: Add `discrete_transformer` as new MODEL_TYPE candidate on evolution islands
    - Application 2: ScoringBench evaluation (extends fire-236)
    - Application 3: Calibrated PDF → direct Brier-loss training objective
    - Application 4: Port to political_engine.py
    - Library: HuggingFace tabular transformers + discretized vocabulary tokenizer
    - Expected improvement: 0.001-0.003 Brier
    - Proposal: data/research-proposals/sota-discrete-tokenization-transformer-fire238.md
    - Work-queue: vm-research-discrete-tokenization-fire238 (priority=111)
35. **Multicalibration Gradient Boosting Convergence** (fire-240 EVEN WebSearch)
    - arXiv:2602.06773 (Feb 2026): "On the Convergence of Multicalibration Gradient Boosting"
    - Key finding: Multicalibration GB produces approximately multicalibrated predictors with O(1/√T) convergence rate; ensures calibration holds across many overlapping subgroups simultaneously
    - Application 1: Replace post-hoc isotonic calibration with multicalibration GB on pareto models
    - Application 2: Add `multicalibration_error_max` as Pareto objective — subgroups: team_tier × venue × back_to_back × season_phase × fatigue_index
    - Application 3: NBA subgroup calibration audit on S15 RF-75f
    - Application 4: Port to political_engine.py — subgroups: state_type × incumbency × competitive_tier × cycle_type
    - Library: fairlearn ExponentiatedGradient or custom multicalibration GB implementation
    - Expected improvement: 0.001-0.003 Brier
    - Proposal: data/research-proposals/sota-multicalibration-gradient-boosting-fire240.md
    - Work-queue: vm-research-multicalibration-gb-fire240 (priority=112)
36. **Distributional Regression Trees for Calibrated Non-Parametric Probabilistic Forecasts** (fire-242 EVEN WebSearch)
    - arXiv:2502.05157 (Feb 2026): "Efficient Distributional Regression Trees Learning Algorithms for Calibrated Non-Parametric Probabilistic Forecasts"
    - Key finding: DRT outputs full predictive distributions natively with O(n log n) efficiency and distribution-free coverage guarantee. Direct distributional generalization of RF/ET — natural successor to S22 ET candidates.
    - Application 1: Add `distributional_regression_tree` as new MODEL_TYPE on evolution islands (ExtraTreesQuantileRegressor from quantile-forest library)
    - Application 2: Replace post-hoc isotonic/Venn-Abers calibration with native DRT distribution output
    - Application 3: Add `distribution_calibration_error` as new Pareto objective
    - Application 4: Brier-loss native training — DRT with proper scoring rule split criterion
    - Application 5: Port to political_engine.py for calibrated state-level predictions
    - Library: quantile-forest (ExtraTreesQuantileRegressor)
    - Expected improvement: 0.001-0.003 Brier
    - Proposal: data/research-proposals/sota-distributional-regression-trees-fire242.md
    - Work-queue: vm-research-distributional-regression-trees-fire242 (priority=113)
37. **Calibration Set Reuse for Multiple Conformal Predictions** (fire-244 EVEN WebSearch)
    - arXiv:2506.19689 (Jun 2026, AISTATS): "When Can We Reuse a Calibration Set for Multiple Conformal Predictions?"
    - Key finding: E-conformal prediction + Hoeffding's inequality enables single calibration set reuse across multiple predictions with maintained distribution-free coverage guarantee. Reduces calibration overhead from O(k×n) to O(n) for k Pareto models. Formula: α_corrected = α + sqrt(log(k/δ) / (2×n_cal))
    - Application 1: Reuse single calibration split across all k Pareto models in engine.py
    - Application 2: Calibration set reuse across temporal CV folds (complements fire-230 sliding-window CV)
    - Application 3: Shared calibration set for NBA+POL when engine parity achieved (Rule #2)
    - Application 4: Add `hoeffding_coverage_gap` as calibration quality metric to /api/export
    - Application 5: Port to political_engine.py for rare-event political calibration
    - Library: crepes/nonconformist + custom Hoeffding correction wrapper (~50 lines)
    - Expected improvement: 0.001-0.002 Brier
    - Proposal: data/research-proposals/sota-conformal-calibration-reuse-fire244.md
    - Work-queue: vm-research-conformal-calibration-reuse-fire244 (priority=114)
38. **Tabular Foundation Models for Conditional Density Estimation** (fire-246 EVEN WebSearch)
    - arXiv:2603.26611 (Mar 2026): "Benchmarking Tabular Foundation Models for Conditional Density Estimation in Regression"
    - Key finding: TabPFN and TabICL benchmarked on 39 real-world datasets using 6 proper scoring metrics (Brier, CRPS, CRLS, log-score, interval score, calibration error); model rankings shift substantially by scoring rule — winner-by-Brier may lose on CRPS/CRLS. Current fleet uses only Brier as primary objective — 5 metrics missing.
    - Application 1: Add all 6 proper scoring metrics to /api/export (Brier+CRPS+CRLS+log_score+interval_score+calibration_error)
    - Application 2: Multi-metric Pareto frontier: Brier+CRPS+CRLS+calibration_error simultaneously — eliminates Brier-overfit candidates
    - Application 3: Validate S18 RF-200f-0.21949 and S22 ET-0.2193 under CRPS/CRLS before fleet-best claim
    - Application 4: TabICLv2 re-evaluation on 186f NBA dataset with all 6 metrics (upgrade path from fire-236)
    - Application 5: Port full scoring suite to political_engine.py — rare-event political races benefit from CRLS tail calibration
    - Library: properscoring (CRPS/CRLS) + netcal/calibration-uncertainty + tabicl --upgrade
    - Expected improvement: 0.001-0.003 Brier + more honest multi-metric pareto ranking
    - Proposal: data/research-proposals/sota-tabular-fm-density-estimation-fire246.md
    - Work-queue: vm-research-tabular-fm-density-estimation-fire246 (priority=115)
39. **fire-248 EVEN WebSearch** — No new arXiv 2026 paper found beyond those already in pipeline. Search results returned known papers: arXiv:2508.02725 (LSTM NCAA, priority=90), arXiv:2410.21484 (ML Sports Betting, priority=107), MDPI 2079-3197/13/10/230 (WNBA, priority=109). Key finding this fire: RULE8 VIOLATION confirmed on both S18 (stacking-37f rank-1) and S22 (stacking-47f rank-1) — stacking contamination across both active islands despite 22+ resets.
40. **Online Conformal Prediction under Corrupted Feedback** (fire-260 EVEN WebSearch)
    - arXiv:2605.20515 (May 2026): "Online Conformal Prediction under Corrupted Feedback"
    - Key finding: Corrupted label feedback degrades coverage guarantees; robust ACI variant maintains validity even when α-fraction of labels are adversarially corrupted.
    - Application 1: Use robust ACI for NBA pareto models — label noise from late score corrections, data errors
    - Application 2: Add `corrupted_feedback_coverage` metric to /api/export
    - Application 3: Port to political_engine.py — election night reporting errors are a form of corrupted feedback
    - Library: MAPIE robust ACI + custom corruption-detection wrapper
    - Expected improvement: 0.001-0.002 Brier under noisy label regimes
    - Work-queue: vm-research-online-cp-corrupted-feedback-fire260 (priority=118)
41. **Universal Portfolio Meets Online Conformal Prediction** (fire-260 EVEN WebSearch)
    - arXiv:2602.03168 (Feb 2026): "Universal Portfolio Meets Online Conformal Prediction"
    - Key finding: Integrates universal portfolio theory (Cover 1991) with online CP — achieves log-optimal wealth growth while maintaining coverage guarantees; applies directly to multi-model Pareto fusion betting.
    - Application 1: Replace rank-fusion in predict_today.py with log-optimal universal portfolio weights over Pareto models
    - Application 2: Add `universal_portfolio_weight` per model to /api/export
    - Application 3: Kelly sizing bounded by CP coverage guarantee (dual objective: wealth + calibration)
    - Application 4: Port to political_engine.py for POL alpha betting
    - Library: universal-portfolios (Python) + nonconformist (CP)
    - Expected improvement: 0.002-0.004 Brier + improved ROI/Sharpe from better model weighting
    - Work-queue: vm-research-universal-portfolio-ocp-fire260 (priority=119)
42. **Shift-Robust Calibrated Prediction for NBA Distribution Shift** (fire-260 EVEN WebSearch — 2nd paper)
    - arXiv:2603.06733 (Mar 2026): "Calibrated Credit Intelligence: Shift-Robust and Fair Risk Scoring with Bayesian Uncertainty and Gradient Boosting"
    - Key finding: 3-layer calibration pipeline (Bayesian neural risk scorer + fairness-constrained GB + shift-aware fusion) reduces calibration error by ~15-30% under temporal distribution shift vs. static isotonic calibration.
    - Application 1: Shift-aware multi-island fusion in predict_today.py (weight islands by inverse KL-div from current game distribution)
    - Application 2: Add shift_calibration_metrics to /api/export (early/mid/playoffs/back-to-back ECE + drift_magnitude)
    - Application 3: Bayesian ensemble uncertainty bands for S18/S22 ET/RF candidates
    - Application 4: Port shift-aware calibration to political_engine.py (election_type × incumbency_status subgroups)
    - Library: scikit-learn calibration + skshift (drift detection: MMD or KL divergence)
    - Expected improvement: 0.001-0.002 Brier (especially late-season predictions)
    - Proposal: data/research-proposals/sota-shift-robust-calibration-fire260.md
    - Work-queue: vm-research-shift-robust-calibration-fire260 (priority=120)

---

## Political Alpha Pipeline

### Data Crons (BLOCKED)
- fetch_political_data.py: NOT running
- insider_tracker.py: NOT running
- pol_watchdog.sh: NOT firing → POL TF IDLE
- Rotation A+D BLOCKED
- FEC/SEC features: BLOCKED (vm-fec-sec-political-features priority=61)

### MODEL_TYPES Status
| Island | Current (fire-260) | Status |
|--------|---------|--------|
| P1 | extra_trees, xgboost_brier, lightgbm_brier, lightgbm | ✅ RULE9 RESOLVED fire-256 — SLEEPING |
| P2 | lightgbm is best (xgboost, lightgbm, catboost, xgboost_brier) | ✅ RESOLVED fire-255 — EVOLVING |
| P4 | xgboost, xgboost_brier, logistic_regression, random_forest | ⚠️ VIOLATION PERSISTS — NO lightgbm (5 resets failed) |
| P5 | xgboost, xgboost_brier, catboost_specialist | ⚠️ VIOLATION PERSISTS fire-260 — NO lightgbm (5 resets) |
| P7 | xgboost, xgboost_brier (confirmed) | ⚠️ UNKNOWN fire-260 — verify LightGBM presence |

---

## Fire Log (last 10)

| Fire | Time | Parity | Key Events |
|------|------|--------|------------|
| 261 | 2026-06-03T08h | ODD | Axelrod-carry-forward-SHAs-NBA-ff51a9e7fd(6034L)/POL-f71087775e(4018L)-UNCHANGED; 25/25-parity-carry-forward; do_not_push_hf_space_yet-MAINTAINED; S18-~c779-stag0-32ND-RESET-~c792-APPROACHING(8-13cy)-ET-fate-UNKNOWN-/api/export-404(33rd); S22-~c130-5TH-RESET-c128-CONFIRMED(c103+25=c128)-post-reset-Rule8-UNKNOWN-next-reset-~c153; evo5-~c1326-30TH-RESET-c1326-PREDICTED(c1301+25=c1326)-catboost-pre-reset-POSITIVE-Rule8-UNKNOWN-post-reset; evo4-~c880-32ND-RESET-~c889-APPROACHING-RULE8-stacking-45f; S13/S14/S15+POL-404-DOWN(84+fires); ODD-no-WebSearch; sota-online-cp-corrupted-feedback-fire260.md-WRITTEN(priority=118); health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-06-03T08h) |
| 260 | 2026-06-03T04h | EVEN | Axelrod-verify-FULL-PASS-25/25-parity-OK-py_compile-OK-SHAs-NBA-ff51a9e7fd(6034L)/POL-f71087775e(4018L)-UNCHANGED; S18-c775-g2323-stag0-pareto8(↓16→8-31ST-RESET-c767-CONFIRMED(c742+25=c767-EXACT))-ET-fate-UNKNOWN-best_model=RF-POSITIVE-/api/export-404(32nd-CRITICAL)-next-reset~c792(c767+25); S22-c127-g381-stag0-pareto12(↑9→12-GROWING!)-5TH-RESET-c128-IMMINENT(c103+25=c128-NOW!1-CYCLE!)-RULE8-CRITICAL:stacking-47f-Feat47-gen379+380-CONFIRMED-CURRENT-CYCLE-127!-/api/export-404; evo4-c866-g2598-stag0-pareto13-32ND-RESET-c864-CONFIRMED(c839+25=c864-EXACT)-RULE8-stacking-45f-gen2597-STILL!-next-reset~c889(c864+25); evo5-c1320-g3960-stag0-pareto13-29TH-RESET-c1301-CONFIRMED-best_model=catboost(IMPROVED-from-stacking!)-RULE8:stacking-33f-gen3959-STILL-30TH-RESET~c1326-IMMINENT(6cy!); S15/S13/S14-404-DOWN(83+fires); all-POL-404-DOWN(83+fires); EVEN-WebSearch:arXiv:2605.20515-Online-CP-Corrupted-Feedback-May2026(NEW-priority=118)+arXiv:2602.03168-Universal-Portfolio-OCP-Feb2026(NEW-priority=119); health-status.json+work-queue.json+CLAUDE.md updated (2026-06-03T04h) |
| 259 | 2026-06-03T00h | ODD | S18-c766-g2296-stag0-pareto16-29TH-c717+30TH-c742-CONFIRMED-⚡ET-200f-brier~0.219-0.220-EXTREME-URGENT(POTENTIAL-FLEET-BEST!)-RULE8-stacking37f-31ST-RESET-c767-HAPPENING-NOW(c742+25-AT-c766!)-/api/export-404(31st); evo5-c1301-g3901-stag24+-pareto6-RULE8-CRITICAL:stacking33f-IS-BEST-MODEL-29TH-RESET-c1301-NOW; evo4-c843-31ST-RESET-c839-CONFIRMED(c814+25)-RULE8-stacking45f; S15-BACK-UP-2ND-TIME!-c1078-g3234-stag0-30TH-c1076-CONFIRMED(c1051+25)-XGBoost200f-0.22195-above-gate; S22-c115-g345-brier0.2207-stag0-pareto6-4TH-c103-CONFIRMED-RULE8-stacking47f-next~c128; P2-c980-brier0.24903-HISTORY-BELOW-GATE-0.2497!-CHECKPOINT-URGENT!(CONFIRMED); P4-c810-RULE9-3-RESETS(c761+c781+c801); P5-c6357-RULE9-PERSISTS; P7-c1552-RULE9-UNKNOWN; ODD-no-WebSearch; Axelrod-carry-forward-SHAs-UNCHANGED; all-JSONs+CLAUDE.md updated (2026-06-03T00h) |
| 258 | 2026-06-02T20h | EVEN | Axelrod-verify-FULL-PASS-25/25-parity-OK-py_compile-OK-SHAs-NBA-ff51a9e7fd(6034L)/POL-f71087775e(4018L)(intentional-1L-diff-deployed-do_not_push-MAINTAINED); S18-c762-RULE8-CLEAN-next~c767-IMMINENT(5cy!); S22-c112-stag0-next~c128(16cy); evo5-c1294-stag0-next~c1301-IMMINENT(7cy!); evo4/S15/S13/S14+POL-404-DOWN(81+fires); EVEN:arXiv:2602.16537-optimal-training-conditional-regret-online-conformal-prediction-Mar2026(priority=117); health-status.json+work-queue.json+CLAUDE.md updated (2026-06-02T20h) |
| 257 | 2026-06-02T16h | ODD | P1-stag19-DIVERSIFY-SENT; evo4-c819-2x-clean-resets(c789+c814-RULE8-CLEAN); evo5-c1284-pareto17-c1276-RESET-HAPPENED(VM-verify-RULE8); S15-c1053-28th-RESET-c1051-CONFIRMED(VM-verify-RULE8); S18-c757-COOLDOWN-RULE8-CLEAN(next~c767-IMMINENT-10cy); S22-c105-c103-RESET-RF-BEST-POSITIVE; P2-LGB-best-history-brier0.24903-BELOW-POL-GATE!; P4-c604-RULE9-VIOLATION-PERSISTS; P5-c6288-RULE9-VIOLATION-PERSISTS; Axelrod-ODD-carry-forward; health-status.json+work-queue.json updated (2026-06-02T16h) |
| 256 | 2026-06-10T00h | EVEN | S18-c743-27TH-RESET-c742-CONFIRMED-RULE8-CLEAN!(stacking-evicted-pareto5→9); S15-c1026-27TH-RESET-c1026-CONFIRMED-RULE8-CLEAN-pareto8→12; S22-c95-stacking-CRITICAL-next~c103(8cy-URGENT!); evo5-c1266-stacking-next~c1276(10cy); P1-c414-RULE9-RESOLVED!(lightgbm-NOW-IN-model_types); P4-c374-RULE9-VIOLATION-PERSISTS; P5-c6110-NEW-RULE9-VIOLATION(no-lightgbm); EVEN-WebSearch:LLM-Agentic-NBA-paper(Apr2026-ResearchGate); GitHub-engine-SHAs-diverged(dev-ahead-of-TF; do_not_push-MAINTAINED); Axelrod-EVEN-carry-forward(TF-DOWN); all-JSONs+CLAUDE.md updated (2026-06-10T00h) |
| 255 | 2026-06-09T20h | ODD | evo4-c765-g2294-brier0.22169-stag0-pareto15(HARD-RESET-c764-CLEAN); evo5-c1249-g3745-brier0.22126-stag0-pareto9(NEW-RULE8:stacking-33f-0.24738-IN-PARETO); S15-c1003-g3008-brier0.22342-stag0-pareto8(26TH-RESET-c1001-next~c1026); S18-c736-g2208-brier0.22326-stag0-pareto5(RULE8-stacking-37f-persists-pareto12→5-next-reset~c742); S22-c89-g267-brier0.2207-stag0-pareto5(RULE8-next-reset~c103-14cycles-URGENT); P1-c187-RULE9-VIOLATION(no-lightgbm); P2-c210-RULE9-RESOLVED!(LGB-best); P4-WOKE-c191-RULE9-VIOLATION; P5-c5948-HEALTHY; P7-c1012-HEALTHY; P3/P6-503-DOWN; ODD-no-WebSearch |
| 254 | 2026-06-09T16h | EVEN | Axelrod-verify-pass-SHAs-NBA-85e7682e1d(6035L)/POL-6983c86517(4019L)-UNCHANGED(direct-verify); 18/18-parity-OK; do_not_push-MAINTAINED; S18-RULE8-stacking-37f; S22-RULE8-stacking-47f; S13/S14-404-DOWN(77+fires) |
| 253 | 2026-06-09T12h | ODD | S22-ET-0.21884-EVICTED-4TH-CONSEC; S18-c729-stacking-37f-diversify-insufficient; S15-25TH-RESET-c976-RF-200f-0.21925(8.7bp-below-fleet!)-LOST; POL-P1+P2-WOKE-c=1-fresh; S19/P3/P6-503-DOWN |
| 252 | 2026-06-09T08h | EVEN | S15-404-DOWN(back-sleep); S18-c712-24TH-RESET-IMMINENT~c717(5cy)-RULE8-stacking37f-rank1; S22-c73-ET200f-0.21884-REGENERATED-POTENTIAL-NEW-FLEET-BEST!(12.8bp↓)-3RD-RESET~c78-IMMINENT-RULE8-stacking×2; Axelrod-verify-pass-SHAs-UNCHANGED; EVEN-WebSearch-no-new-arXiv; all-JSONs+CLAUDE.md-committed |
| 251 | 2026-06-09T04h | ODD | S15-BACK-UP!(WOKE-after-75+fires)-c890-g2670-brier0.22342-stag=0-RF62f; S18-c696-g2086-stag=0(23rd-RESET-c692-CONFIRMED)-pareto=15-XGB200f-0.22343-RULE8-stacking-x2-top5; S22-c65-g194-stag=0-pareto=9(↓18→9)-ET0.21983-CONFIRMED-LOST(4th-consec-eviction!)-RULE8-stacking-x2-top5-next-reset~c78; S13/S14+POL-404-DOWN(75+fires); ODD: Axelrod-verify-pass-SHAs-UNCHANGED; do_not_push_hf_space_yet-MAINTAINED |

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
- **DRT**: Distributional Regression Trees — native calibrated PDF output from tree ensembles (fire-242)
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