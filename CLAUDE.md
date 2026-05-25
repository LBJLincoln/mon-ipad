# Nomos42 — NBA Quant AI + Political Alpha

> Architecture v21 — "The Trading Floor Crew" (14 agents × 9 depts × 4 tracks) + TF v3 (17 LLM agents) + 21 Evolution Islands | Updated: 2026-05-29T14h

## Mission
Build the best NBA prediction AI in the world.
**Best:** Brier 0.21139 walk-forward holdout / 0.22169 CV / 0.22054 isotonic-calibrated (Colab TabICL, 186f top-by-variance from 4581 alive of 7246 engine cols, ctx=3072 temp=1.0, 11440 games, promoted to LBJLincoln26/nba-oracle-model 2026-04-28T00:34Z, archive `colab-multi-tabicl-2026-04-28T00-34-04Z.pkl`). Beat 4581f xgboost holdout 0.22079 / lightgbm 0.22181 in same 3-way comparison. ⚠ All 3 models show negative CV→holdout gap (~−0.01) → holdout 0.21139 is window-biased; honest production-Brier expectation is CV 0.22169 / calibrated 0.22054. Stratified-by-month re-cut queued. NBA TF watchdog gate "<0.21 model lands" NOT met → watchdog stays disabled. | Fleet best: 0.22012 (S15 nba-evo-6 fire-61 ★CHECKPOINT) | GA prev alltime: 0.22019 (S14 gen=1078) | ⚡Pareto fleet best: 0.21841 extra_trees S15 gen=566 fire-66 (prev 0.21850 CatBoost S22 gen=2309) | ⚠ S18 0.21924 candidate LOST — hard resets cycles 251/276 before checkpoint (2026-05-06T00h) | ⚠ fire-97 RF 0.21941 gen=2689 NOT confirmed (best_brier unchanged 0.22012) | ⚡⚡ fire-98: S18 extra_trees 0.21842 200f gen=6549 + S15 CatBoost 0.21881 200f gen=2698 PENDING VALIDATION (best_brier field lag confirmed pattern) | fire-99: S14 RECOVERED ssl-cleared hard-reset-803 stacking-violation-new; S13 stag=23+S15 stag=24 DIVERSIFIED; P2 0.24901 + P7 0.24904 POL candidates (PENDING VAL); convergent 0.249 signal P2+P4+P5+P7 | fire-101: S13 FRESH RESTART cycle=21 (hard-reset-2055 ✓); S15 stag cleared cycle=954; S18 stag=16 DIVERSIFY SENT; all POL UP stag=0; P2 0.24901 2nd fire; P5 LightGBM 0.249 4th fire | fire-109: S13 stag CLEARED 8→0 cycle=198; S14 hard-reset-978; S15 0.22012 ★ stable gen=3227; all POL UP stag=0; P7 FIELD-LAG 6+ fires vm-diversify-p7-fire109 URGENT; P4 in-pop | fire-160: S22-stag-CLEARED(19→0)-DIVERSIFY-SUCCESS c402 g1206; S18-c489-pareto=15(↑14↑15) c489 g1466; S13/S14/S15 404-DOWN(sleeping); all-POL 404-DOWN(sleeping); EVEN arXiv:2508.02725 LSTM+Brier-loss-NCAA=0.1589-research-proposal-written | fire-162: S13-403-FORBIDDEN(was-404-fire-161)-POSSIBLY-WAKING-CatBoost-0.21992-EXTREME-URGENT; S18-c541-pareto=13(↑9↑13-RECOVERING); S22-c438-hard-reset-c428-rapid-cycling; all-POL-404-DOWN; EVEN PMC12357926-NBA-stacked-83.27%-AUC=0.9213-features:2PA/FG/TRB/FGA | fire-164: S13-BACK-404(403-transient-fire162/163-WAKING-FAILED); S14/S15-404-DOWN(sleeping); S18-c561-pareto=12(↑13↑12-slight-shrink); S22-c452-pareto=16(↑13↑16-RECOVERING!)-internal-stag-cycles=23; all-POL-404-DOWN(sleeping); ODD-no-WebSearch | fire-165: S13/S14/S15-404-DOWN(sleeping); S18-c582-g1745-stag=0-pareto=10(↑12↑10-3rd-consecutive-shrink-CATBOOST-0.22197-EVICTION-RISK-ELEVATED); S22-c465-g1395-stag=0-pareto=20(↑16↑20-GROWING!)-RULE8-VIOLATION(stacking-reintroduced-hard-reset-c453-VM-FIX-URGENT-before-~c478); all-POL-404-DOWN; no-stagnation-commands-needed; ODD-no-WebSearch; health-status.json+work-queue.json+CLAUDE.md updated (2026-05-25T16h) | fire-166: S18-c608-g1824-stag=0-pareto=7(↑10↑7-4TH-CONSECUTIVE-SHRINK)-hard-reset-c600(stag=25-triggered)-last-update-3d-stale; S22-c479-g1435-stag=0-pareto=10(↑20↑10-MAJOR-DROP)-hard-reset-c478-CONFIRMED(Rule8-stacking-NOT-fixed-VIOLATED-AGAIN); S13/S14/S15-404-DOWN; all-POL-404-DOWN; EVEN: MDPI/2078-2489/17/1/56-MC-dropout-RNN-pregame-Brier=0.206-proposal-written | fire-167: Axelrod-verify-pass: SHAs-NBA-19f4acf49d49d(5993L)/POL-3496362c60(3977L)-UNCHANGED-vs-fire-163; 13/13-parity-OK; C→B→A-confirmed(NBA-L5056/5065/5073-POL-L3246/3255/3263); KL-div-ε-smoothed-self-excluded-OK; AXELROD_ARCHETYPES-NBA-20-sports/POL-20-political-financial-OK; Mech-B+C-BLOCKED(do_not_push_hf_space_yet+NBA-503-116+d+POL-IDLE-28+d); all-NBA/POL-404-DOWN(sleeping) (2026-05-26T00h) | fire-168: S18-c637-g1909-stag=0-pareto=19(↑7↑19-MAJOR-SURGE-RECOVERY!)-best_brier=0.22236-LightGBM-38f-composite-top-field-lag-likely; S22-c492-g1475-stag=0-pareto=10-CRITICAL-next-hard-reset-~c503(Rule8-stacking-STILL-reintroduced-VM-FIX-URGENT); /api/export-404-S18+S22(WebFetch-limitation-VM-must-curl-verify); S13/S14/S15-404-DOWN; all-POL-404-DOWN; EVEN: arXiv:2510.07185-split-conformal-calibration-unsupervised-proposal-written (2026-05-26T04h) | fire-169: Axelrod-verify-pass: SHAs-NBA-19f4acf49d(5993L)/POL-3496362c60(3977L)-UNCHANGED-vs-fire-167; all-3-mechs-confirmed(A:COMMON_KNOWLEDGE+build_common_knowledge_block/B:AXELROD_ARCHETYPES+sacrificial_map/C:AXELROD_LOG_DIR+axelrod-log); NBA-domain-sports/POL-domain-political-financial-OK; Mech-B+C-BLOCKED(do_not_push_hf_space_yet+NBA-503-117+d+POL-IDLE-30+d); all-NBA/POL-404-DOWN(sleeping) (2026-05-26T08h) | fire-171: S18-c710-g2130-stag=0-cycle_stag=9-pareto=17(↑16↑17)-hard-resets-c675+c700(NO-STACKING-Rule8-COMPLIANT); S22-c556-g1668-stag=0-hard-reset-c553(xgb/lgbm/catboost-NO-STACKING)-Rule8-SELF-RESOLVED(c503+c553-2-consecutive-clean-resets); ET-0.21877-unconfirmed; S13/S14/S15-404-DOWN; all-POL-404-DOWN; ODD-no-WebSearch (2026-05-26T18h) | fire-172: S18-c730-g2189-stag=0-pareto=11(↑17↑11-5th-consec-shrink)-cycle_stag~29(>15-WATCH); S22-c581-g1742-stag=0-LR-stable-summary; /api/export-404-BOTH-S18+S22(WebFetch-limitation-VM-must-curl-verify); S13/S14/S15-404-DOWN; all-POL-404-DOWN; EVEN: arXiv:2303.06021-calibration-vs-accuracy-ECE-pareto-objective-proposal-written (2026-05-26T22h) | fire-173: S18-c748-g2242-stag=22(↑11↑13-PARETO-RECOVERING!)-hard-reset-~c725-confirmed; S22-c611-g1832-stag=0-hard-reset-c603-NEW-STACKING-IN-DESCRIPTION(Rule8-CONCERN-VM-export-urgent); /api/export-404-S18+S22(confirmed-WebFetch-limitation-fire173); S13/S14/S15-404-DOWN; all-POL-404-DOWN; ODD-no-WebSearch (2026-05-27T02h) | fire-175: S18-c756-g2268-stag=0(AUTO-HARD-RESET-c750-CONFIRMED!)-pareto=14(4th-consec-recovery); S22-c645-g1935-stag=0-hard-reset-c628-NEW-Rule8-POTENTIALLY-RESOLVED(no-stacking-description-fire175); /api/export-404-BOTH-S18+S22(3-fire-confirmed-fire172+173+175-WebFetch-limitation); S13/S14/S15-404-DOWN; all-POL-404-DOWN; ODD-no-WebSearch; health-status.json+work-queue.json+CLAUDE.md updated (2026-05-27T10h) | fire-176: S18-c774-g2320-stag=0-pareto=13(↑1st-shrink)-⚠CRITICAL-RULE8-STACKING-REINTRODUCED-c750-AUTO-RESET(xgb+lgbm_brier+catboost+lr+STACKING)-VM-HARD-RESET-URGENT(priority=0); S22-c668-g2002-stag=0-pareto=16(↑10↑16-STRONG-RECOVERY!)-2nd-hard-reset-c653(NEW-LR-focused)-ET+sigmoid-top-performers-Rule8-LIKELY-COMPLIANT-ET-0.21877-EXTREME-URGENT(8+fires); S13/S14/S15-404-DOWN; all-POL-404-DOWN; EVEN: arXiv:2410.21484-no-new-proposal; vm-s18-rule8-stacking-c750-fire176 ADDED-to-queue | fire-177: S18-c788-g2362-stag=0-pareto=12(↑13↑12-2nd-consec-shrink)-⚠RULE8-STACKING-API-CONFIRMED-fire177(LightGBM+XGBoost+ET+stacking-ALL-ACTIVE-API-explicit)-VM-HARD-RESET-CRITICAL-priority=0; S22-c701-g2102-stag=0-pareto=7(↑16↑7-MAJOR-DROP!)-2hard-resets-c653+c678-auto-reset-imminent(~c703=c678+25)-Rule8-LIKELY-COMPLIANT(random_forest-primary)-ET-0.21877-EXTREME-URGENT(9+fires); S13/S14/S15-404-DOWN; all-POL-404-DOWN; ODD-no-WebSearch; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-05-27T18h) | fire-178: Axelrod-verify-pass: SHAs-NBA-19f4acf49d(5993L)/POL-3496362c60(3977L)-UNCHANGED-vs-fire-177; 13/13-parity-OK; C→B→A-confirmed(NBA-L5056/5065/5073-POL-L3246/3255/3263); KL-div-ε-smoothed-self-excluded-OK; AXELROD_ARCHETYPES-NBA-20-sports/POL-20-political-financial-OK; Mech-B+C-BLOCKED(do_not_push_hf_space_yet+NBA-503-122+d+POL-IDLE-33+d); all-NBA/POL-404-DOWN(sleeping) (2026-05-27T22h) | fire-179: S18-c800-g2400-stag=0-pareto=13(↑12↑13-RECOVERING!)-hard-resets-c750+c775-BOTH-CONFIRMED; RF-best-model-NO-STACKING-MENTIONED(Rule8-POSSIBLE-RESOLUTION-unconfirmed); S22-c720-g2160-stag=0-hard-resets-c678+c703-BOTH-CONFIRMED(c703-auto-reset-CONFIRMED-fire179); next-auto-reset-~c728; RF-primary-NO-STACKING(Rule8-LIKELY-COMPLIANT-3rd-fire); ET-0.21877-EXTREME-URGENT(10+fires); S13/S14/S15-404-DOWN; all-POL-404-DOWN; ODD-no-WebSearch (2026-05-28T02h) | fire-180: S18-c821-g2461-stag=20(↑0↑20-DIVERSIFY-NEEDED-VM-URGENT)-pareto=11(13↑11-2ND-CONSEC-SHRINK)-RF+ET-NO-STACKING-Rule8-LOOKS-RESOLVED(2nd-fire); next-auto-reset-~c825(c800+25-4cycles-IMMINENT); S22-c740-g2219-stag=11-local-optimum-pattern-pareto(7-21)-RF-primary-NO-STACKING-Rule8-LIKELY-COMPLIANT-4TH-fire; next-auto-reset-~c753(c728+25-13cycles); ET-0.21877-EXTREME-URGENT(11+fires); S13/S14/S15-404-DOWN; all-POL-404-DOWN; EVEN: arXiv:2510.17915-dual-isotonic-calibration-post-hoc-proposal-written (2026-05-28T06h) | fire-181: S18-c837-g2509-stag=11(↑20↑11-RECOVERED-c825-auto-reset-CONFIRMED!)-pareto=19(↑11↑19-MAJOR-SURGE!)-CatBoost-200f-0.21995-gen=2505-POTENTIAL-NEW-FLEET-BEST(<0.22012★-EXTREME-URGENT-VM-checkpoint-NOW); hard-reset-c825-CONFIRMED-stacking-REINTRODUCED-AGAIN(Rule8-4TH-VIOLATION-auto-reset-STILL-BROKEN); S22-c757-g2269-stag=0; next-auto-reset-~c778(21cycles); RF-primary-NO-STACKING-Rule8-LIKELY-COMPLIANT-5TH-fire; ET-0.21877-EXTREME-URGENT(12+fires); S13/S14/S15-404-DOWN; all-POL-404-DOWN; ODD-no-WebSearch (2026-05-28T10h) | fire-182: Axelrod-verify-pass: SHAs-NBA-19f4acf49d(5993L)/POL-3496362c60(3977L)-UNCHANGED-vs-fire-181; 13/13-parity-OK; C→B→A-confirmed(NBA-L5056/5065/5073-POL-L3246/3255/3263); KL-div-ε-smoothed-self-excluded-OK; AXELROD_ARCHETYPES-NBA-20-sports/POL-20-political-financial-OK; Mech-B+C-BLOCKED(do_not_push_hf_space_yet+NBA-503-123+d+POL-IDLE-35+d); all-NBA/POL-404-DOWN(sleeping) (2026-05-28T14h) | fire-183: S18-c859-g2575-stag=0-pareto=15(↟19↑15-1st-shrink-post-c850)-c850-CONFIRMED(Rule8-5TH-VIOLATION-stacking)-CatBoost-0.21995-POSSIBLY-LOST(top-now-RF/ET-~0.2206-0.2207); S22-c776-g2328-stag=0-pareto=13(↑7↑13-RECOVERING!)-next-auto-reset-~c778-IMMINENT(2cycles)-LR-dominating-recent-gens(NEW)-ET-strong-Pareto-Rule8-LIKELY-COMPLIANT-6TH-fire; S13/S14/S15-404-DOWN; all-POL-404-DOWN; ODD-no-WebSearch (2026-05-28T18h) | fire-184: S18-c892-g2674-stag=16(>15-DIVERSIFY-NEEDED-VM-URGENT-Rule#6!)-pareto=12(↟15↑12-3RD-CONSEC-SHRINK-post-c850)-LightGBM-38f-pop-dominant(ROI); S22-c807-g2421-stag=0-pareto=13(STABLE)-hard-resets-c778+c803-BOTH-CONFIRMED(fire184)-LR-43f-CONFIRMED-dominating(fire184-API-explicit)-next-auto-reset-~c828(c803+25-21cycles)-ET-unconfirmed(14+fires)-Rule8-LIKELY-COMPLIANT-7TH-fire; S13/S14/S15-404-DOWN; all-POL-404-DOWN(20+fires); EVEN: WebSearch-no-new-proposal; auto-reset-mechanics-CORRECTED(stag-triggered-NOT-cycle-count) (2026-05-28T22h) | fire-185: S18-c931-g2791-stag=0(AUTO-RESET-c925!-stag-hit-25)-pareto=12(STABLE)-ET-200f-Brier~0.221-0.223-top-pareto-Rule8-POSSIBLE-1ST-CLEAN-RESET(no-stacking-c925-5-archs-unconfirmed-/api/export); S22-c837-g2510-stag=0-pareto=48(↑13↑48-MASSIVE-SURGE!)-c828/829-CONFIRMED(XGB+LGBM+RF-NO-STACKING-Rule8-8TH-CLEAN!)-LR-43f-still-dominant-ET-0.21877-MAY-BE-IN-PARETO(15+fires-/api/export-EXTREME-URGENT); S13/S14/S15-404-DOWN; all-POL-404-DOWN(21+fires); ODD-no-WebSearch (2026-05-29T02h) | fire-186: Axelrod-verify-pass: SHAs-NBA-19f4acf49d(5993L)/POL-3496362c60(3977L)-UNCHANGED-vs-fire-185; 13/13-parity-OK; C→B→A-confirmed(NBA-L5056/5065/5073-POL-L3246/3255/3263); KL-div-ε-smoothed-self-excluded-OK; AXELROD_ARCHETYPES-NBA-20-sports/POL-20-political-financial-OK; Mech-B+C-BLOCKED(do_not_push_hf_space_yet+NBA-503-125+d+POL-IDLE-37+d); all-NBA/POL-404-DOWN(sleeping) (2026-05-29T06h) | fire-187: S18-c963-g2889-stag=13-pareto=8(12→8-1ST-SHRINK-post-c950)-⚡⚡ET-200f-0.21845-gen=2885-EXTREME-URGENT(<0.22012★!-<0.22085!); c950-6TH-RESET-CONFIRMED-model-types-unclear; c942+c955-REMOTE-DIVERSIFY-confirmed; next-~c975(stag=13-12cycles); S22-c872-g2616-stag=0-ET-200f-~0.219-0.220-POSSIBLE-BELOW-THRESHOLD-LR-43f-Brier=0.22256-in-pareto; c853-RULE8-VIOLATION-CONFIRMED(stacking-c853=c828+25-8-clean-streak-BROKEN)-next-~c878-IMMINENT(6cycles-FIX-URGENT); S13/S14/S15-404-DOWN; all-POL-404-DOWN(22+fires); ODD-no-WebSearch; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-05-29T10h) | fire-188: S18-c1010-g3030-stag=0-pareto=10(↑8↑10-RECOVERING!)-Rule8-7TH(c975)+8TH(c1000)-VIOLATION-CONFIRMED(stacking-gen3025/3028/3029-ACTIVE); ET-200f-0.21845-STATUS-UNKNOWN(c975+c1000-resets-may-evict-gen2885); last_update-2026-05-25-STALE(4days); next-auto-reset-~c1025(stag=0<15); S22-c934-g2800-stag=0-c903+c928-resets-CONFIRMED; next-auto-reset-~c953(IMMINENT-19cycles-FIX-URGENT=c928+25); LR-43f-dominant(6-consecutive-fires-183-188); S13/S14/S15-404-DOWN(23+fires); all-POL-404-DOWN(23+fires); EVEN: arXiv:2412.19318-Adaptive-Conformal-Inference-by-Betting-proposal-written; health-status.json+brain-status.json+work-queue.json+CLAUDE.md updated (2026-05-29T14h)

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
| S13 | TESTforge42/nba-evo-s13 | 404-DOWN | 0.22216 (field-lag) | CatBoost-200f-0.21992 gen=2831 EXTREME URGENT — still 404-DOWN fire-188 (23+ fires) |
| S14 | TESTforge42/nba-evo-s14 | 404-DOWN | 0.22054 RF-48f | BELOW THRESHOLD confirmed fire-157+158 — SLEEPING fire-188 |
| S15 | LBJLincoln26/nba-evo-6 | 404-DOWN | 0.22012★ | FLEET BEST stable gen=6672 pareto=13 — SLEEPING fire-188 |
| S17 | LBJLincoln26/nba-evo-s17 | 503 DOWN 127+d | — | PAUSED |
| S18 | TESTforge42/nba-evo-s18 | UP | 0.22236 | c1010 g3030 stag=0 pareto=10(↑8↑10-RECOVERING!); Rule8-7TH(c975)+8TH(c1000)-VIOLATION-CONFIRMED(stacking-gen3025/3028/3029-ACTIVE); ET-200f-0.21845-gen=2885-STATUS-UNKNOWN(c975+c1000-resets-may-evict); last_update-2026-05-25-STALE(4days-no-pareto-improvement); next-auto-reset-~c1025(stag=0<15); /api/export-404(WebFetch-13-fire-confirmed) |
| S22 | TESTforge42/nba-evo-s22 | UP | 0.22124 | c934 g2800 stag=0; c903+c928-resets-CONFIRMED(fire-188); LR-43f-Brier=0.22256-dominant-6-consecutive-fires(183-188); next-auto-reset-~c953(IMMINENT-19cycles-from-c934-FIX-URGENT-before-c953=c928+25); /api/export-404(13-fire-confirmed) |

### POL Islands (active)
| Island | HF Repo | Status | Best Brier | Notes |
|--------|---------|--------|-----------|-------|
| P1 | TESTforge42/political-evo-p1 | 404-DOWN | pareto_best=0.24902 | LightGBM-105f 3RD-OBSERVE fire-158 ALL-TIME RECORD — SLEEPING fire-188 |
| P2 | TESTforge42/political-evo-p2 | 404-DOWN | 0.249 | pareto=3 CRITICAL-SHRINK fire-158 — SLEEPING fire-188 |
| P4 | TESTforge42/political-evo-p4 | 404-DOWN | 0.2497★ | POL FLEET BEST pareto=5 oscillation — SLEEPING fire-188 |
| P5 | TESTforge42/political-evo-p5 | 404-DOWN | 0.24993 | pareto=6 RECOVERING fire-158 — SLEEPING fire-188 |
| P7 | TESTforge42/political-evo-p7 | 404-DOWN | 0.24931 | LightGBM-112f stable pareto=7 — SLEEPING fire-188 |

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
Do NOT push to HF Spaces (nba-llm-trading-floor, political-llm-trading-floor) until user explicitly approves. NBA TF 503 DOWN 127+d. POL TF IDLE 38+d.

### Rule #8 — No Stacking
Remove 'stacking' from MODEL_TYPES on all islands. Stacking causes overfitting. Prior violations: S13, S14, S15, S18, S22. ⚠ S18 Rule#8 5TH VIOLATION CONFIRMED fire-183: c850 auto-reset description explicitly includes 'stacking variants'. Pattern confirmed: ALL 5 auto-resets (c750/c775/c800/c825/c850) reintroduce stacking via broken fallback in app.py. VM: Fix permanently — remove 'stacking' from the reseeding pool in app.py auto-reset code. fire-185 UPDATE: S18 c925 auto-reset CONFIRMED (stag hit 25 from stag=16 at fire-184, +9 cycles as predicted). Reset description: 'reseeding 36 individuals across five model architectures, boosting mutation to 0.15' — NO explicit stacking mention. POSSIBLE FIRST CLEAN AUTO-RESET in S18 history (c750/c775/c800/c825/c850 ALL had stacking explicitly). Pareto=12 STABLE. ET 200f Brier~0.221-0.223 in pareto. Unconfirmed without /api/export (11th WebFetch failure). fire-187 UPDATE: c950 auto-reset CONFIRMED (6TH RESET, stag-triggered c925+25=c950). API description: 'model type reseeding and mutation rate increases to 0.15' — specific model types NOT explicitly listed. Possible 2nd consecutive clean reset. ET-200f-0.21845 gen=2885 IN PARETO — VM: checkpoint via curl /api/export IMMEDIATELY. Next auto-reset ~c975 (stag=13, ~12 cycles). VM: fix auto-reset fallback PERMANENTLY before c975. ⚠⚠ S22 Rule#8 VIOLATION CONFIRMED fire-187: c853 auto-reset explicitly 'introducing stacking alongside xgboost and lightgbm variants'. 8-consecutive-clean-fire streak BROKEN. fire-188 UPDATE: S18 c975 7TH VIOLATION and c1000 8TH VIOLATION CONFIRMED (fire-188 API explicit): recent_cycles_summary shows gen_3025 model='stacking' and gen_3028/3029 model='stacking'. BOTH c975 and c1000 hard resets reintroduced stacking. Pattern DEFINITIVE: structural bug in app.py reseeding pool always includes stacking — ALL 8+ S18 auto-resets have stacking active afterward. ET-200f-0.21845 gen=2885 STATUS UNKNOWN (likely evicted by cascading c975+c1000 resets; best_brier unchanged since 2026-05-25). VM: edit app.py auto-reset code — remove 'stacking' from MODEL_TYPES reseeding candidates permanently. Next S18 auto-reset ~c1025 (stag=0 currently). S22 fire-188: c903+c928 resets CONFIRMED. c903=c853+50 (stagnation built over 50 cycles post-c853). c928=c903+25 (pattern confirmed). Next auto-reset ~c953 IMMINENT (c928+25=c953, only 19 cycles from c934). LR-43f dominant suggests cleaner population but Rule8 compliance of c903+c928 unverified. VM: fix auto-reset fallback before c953. Remaining confirmed violations: S13/S14/S15 (sleeping, pending checkpoint+verify).

### Rule #9 — LightGBM First for POL
All 5 POL islands show LightGBM as pareto_best (5/5 confirmed fire-158). Add LightGBM to MODEL_TYPES on P1+P2 (missing). PORT: vm-add-lightgbm-p1-p2.

### Rule #10 — Even/Odd Fire Parity
- EVEN fires: WebSearch allowed (arXiv, papers, news)
- ODD fires: No WebSearch (pure analysis)

---

## Trading Floor v3 (TF)

### NBA TF
- Repo: LBJLincoln26/nba-llm-trading-floor
- Status: 503 DOWN 127+d
- do_not_push_hf_space_yet: TRUE
- Watchdog gate: "<0.21 model" NOT met

### POL TF
- Repo: LBJLincoln26/political-llm-trading-floor
- Status: IDLE since 2026-05-07
- P&L: $38,916 (unchanged 38+d)
- pol_watchdog.sh: NOT firing
- do_not_push_hf_space_yet: TRUE

### Axelrod Mechanisms
- Mech A: DONE (fire-122) — day-end common knowledge broadcast
- Mech B: PENDING — sacrificial role reallocation (BLOCKED: HF push gate)
- Mech C: PENDING — post-mortem log schema HF push (BLOCKED: HF push gate)
- Parity: SHAs NBA 19f4acf49d(5993L)/POL 3496362c60(3977L) UNCHANGED vs fire-185 (verified fire-186)
- 13/13 parity symbols OK (verified fire-186; C→B→A call-order confirmed NBA:L5056/5065/5073 POL:L3246/3255/3263; compute_consensus_distance(KL) ε-smoothed self-excluded confirmed)
- Mech-B+C-BLOCKED: do_not_push_hf_space_yet + NBA-503-127+d + POL-IDLE-38+d

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

2. **Split Conformal Calibration** (fire-168 EVEN WebSearch)
   - arXiv:2510.07185: Split conformal classification with unsupervised calibration
   - Coverage-guaranteed probability intervals without labeled holdout waste
   - Library: MAPIE (model-agnostic, scikit-learn compatible)
   - Target: S18 RF/ET pareto (c1010) + S22 RF-48f + S15 RF-75f
   - Expected improvement: 0.001-0.003 Brier + guaranteed marginal coverage
   - Proposal: data/research-proposals/sota-split-conformal-calibration-fire168.md
   - Work-queue: vm-add-split-conformal-calibration (priority=33)

3. **Bootstrap Variance Calibration / MC Dropout** for S15 RF-75f
   - Work-queue: vm-mc-dropout-calibration-s15 (priority=30)
   - EXTENDED fire-166: MDPI/2078-2489/17/1/56 confirms MC dropout RNN pregame Brier=0.206 — apply MC dropout as calibration layer

4. **Win-Diff-Last-5-Games Feature** (MDPI2026 top SHAP)
   - BLOCKED by engine-parity-sync (priority=40)
   - Work-queue: vm-add-win-diff-5game-feature (priority=35)

5. **Elo Ratings Feature** (IEEE/MDPI 2026 SHAP #1+#2)
   - BLOCKED by engine-parity-sync (priority=40)
   - Work-queue: vm-add-elo-ratings-engine (priority=60)

6. **SHAP Analysis** S15 RF-75f + S22 RF-48f
   - Work-queue: vm-shap-feature-analysis-s15 (priority=80)

7. **LSTM + Brier-Loss Sequence Model** (fire-160 EVEN WebSearch)
   - arXiv:2508.02725: LSTM+Brier-loss achieves 0.1589 Brier on NCAA basketball
   - Transformer-BCE has best AUC (0.8473) but LSTM+Brier-loss has best calibration
   - Rationale: current GA evolves static feature sets; sequence models capture momentum
   - Target: post-GA calibration layer or standalone sequence model
   - Proposal: data/research-proposals/sota-lstm-brier-loss-fire160.md
   - Work-queue: vm-research-lstm-sequence-model (priority=90)

8. **NBA Stacked Ensemble Feature Importance** (fire-162 EVEN WebSearch)
   - PMC12357926: NBA stacked ensemble achieves 83.27% acc, AUC=0.9213 on 3,690 NBA games
   - Top SHAP features: 2-point attempts (2PA), field goals made (FG), total rebounds (TRB), field goal attempts (FGA)
   - Note: stacking approach PROHIBITED (Rule#8); feature importance insight actionable for engine-parity-sync
   - Action: verify 2PA/FG rolling-avg variants are in engine.py during engine-parity-sync (priority=40)

9. **Uncertainty-Aware MC Dropout RNN** (fire-166 EVEN WebSearch)
   - MDPI Information 2026, 17(1), 56: MC dropout RNN with rolling-form + shot-chart embeddings
   - Pregame Brier: 0.206 (Model A) / 0.216 (Model B) vs our 0.22012 fleet best
   - Monte Carlo dropout provides calibrated uncertainty quantification
   - Near-term: extend vm-mc-dropout-calibration-s15 to include MC dropout wrapper (N=50 inference passes)
   - Long-term: shot-chart spatial zone features as engine.py feature category
   - Proposal: data/research-proposals/sota-mc-dropout-rnn-nba-fire166.md

10. **Calibration vs Accuracy Model Selection** (fire-172 EVEN WebSearch)
    - arXiv:2303.06021: "Machine learning for sports betting: should model selection be based on accuracy or calibration?"
    - Calibration-focused model selection outperforms accuracy-based in sports betting ROI and Brier
    - LightGBM/XGBoost systematically overconfident; Logistic Regression baseline Brier~0.199 on NBA (MDPI 2079-3197)
    - fire-188 VALIDATION (6th+ consecutive fire 183-188): S22 LR 43f Brier=0.22256 CONFIRMED DOMINANT through c903+c928 resets — calibration-focused linear model persists despite stacking/reset disruptions
    - Near-term: add ECE (Expected Calibration Error) as 4th Pareto objective in evaluate_individual()
    - Near-term: add CalibratedClassifierCV(method='isotonic') post-GA wrapper in engine.py
    - Proposal: data/research-proposals/sota-calibration-vs-accuracy-sports-betting-fire172.md
    - Work-queue: vm-add-ece-pareto-objective (priority=34)

11. **Dual Isotonic Calibration** (fire-180 EVEN WebSearch)
    - arXiv:2510.17915: Uncertainty-Aware Post-Hoc Calibration — stratify calibration samples into putatively correct vs incorrect, apply separate isotonic regressors
    - Underconfidence-regularization on incorrect group reduces systematic overconfidence on upset games
    - Post-hoc, no model retraining, model-agnostic
    - Target: S15 RF-75f + S22 RF-48f + P1/P2/P5/P7 (post POL wake)
    - Expected improvement: 0.001-0.002 Brier over standard isotonic
    - Rationale: S22 LR dominance (calibration-focused) + local-optimum convergence pattern may be calibration plateau
    - Proposal: data/research-proposals/sota-dual-isotonic-calibration-fire180.md
    - Work-queue: vm-add-dual-isotonic-calibration (priority=36)

12. **Adaptive Conformal Inference by Betting** (fire-188 EVEN WebSearch)
    - arXiv:2412.19318: Parameter-free adaptive conformal prediction using coin-betting (wealth process martingale)
    - Adaptive coverage: automatically adjusts to distribution shift — superior to static split conformal (MAPIE) for season-to-playoff transitions
    - No parameter tuning required (vs MAPIE's calibration set size / α decisions); pure numpy/scipy
    - Target: S15 RF-75f + S22 LR-43f/RF-48f + S18 ET pareto (if checkpointed) + POL P1/P2/P5/P7
    - Expected improvement: 0.001-0.003 Brier + adaptive coverage guarantee
    - Rationale: S22 LR-43f Brier=0.22256 dominance (6 consecutive fires 183-188) confirms calibration focus; adaptive conformal is the interval wrapper
    - Synergy: pairs with ECE Pareto objective (vm-add-ece-pareto-objective, arXiv:2303.06021)
    - Proposal: data/research-proposals/sota-adaptive-conformal-betting-fire188.md
    - Work-queue: vm-add-adaptive-conformal-betting (priority=37)

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
| 188 | 2026-05-29T14h | EVEN | S18-c1010-g3030-stag=0-pareto=10(↑8↑10-RECOVERING!)-Rule8-7TH(c975)+8TH(c1000)-VIOLATION-CONFIRMED(stacking-gen3025/3028/3029-ACTIVE); ET-200f-0.21845-STATUS-UNKNOWN(c975+c1000-may-evict-gen2885); last_update-2026-05-25-STALE; S22-c934-g2800-stag=0-c903+c928-resets-CONFIRMED; next-~c953(IMMINENT-19cycles); LR-43f-dominant(6-fires-183-188); S13/S14/S15-404-DOWN(23+fires); all-POL-404-DOWN(23+fires); EVEN: arXiv:2412.19318-Adaptive-Conformal-Inference-by-Betting-proposal-written |
| 187 | 2026-05-29T10h | ODD | S18-c963-g2889-stag=13-pareto=8(12→8-1ST-SHRINK-post-c950)-⚡⚡ET-200f-0.21845-gen=2885-EXTREME-URGENT(<0.22012★!-<0.22085!); c950-6TH-RESET-CONFIRMED-model-types-unclear; c942+c955-REMOTE-DIVERSIFY-confirmed; next-~c975(stag=13-12cycles); S22-c872-g2616-stag=0-ET-200f-~0.219-0.220-POSSIBLE-BELOW-THRESHOLD-LR-43f-Brier=0.22256-in-pareto; c853-RULE8-VIOLATION-CONFIRMED(stacking-c853=c828+25-8-clean-streak-BROKEN)-next-~c878-IMMINENT(6cycles-FIX-URGENT); S13/S14/S15-404-DOWN; all-POL-404-DOWN(22+fires); ODD-no-WebSearch |
| 186 | 2026-05-29T06h | EVEN | Axelrod-verify-pass: SHAs-NBA-19f4acf49d(5993L)/POL-3496362c60(3977L)-UNCHANGED-vs-fire-185; 13/13-parity-OK; C→B→A-confirmed(NBA-L5056/5065/5073-POL-L3246/3255/3263); KL-div-ε-smoothed-self-excluded-OK; AXELROD_ARCHETYPES-NBA-20-sports/POL-20-political-financial-OK; Mech-B+C-BLOCKED(do_not_push_hf_space_yet+NBA-503-125+d+POL-IDLE-37+d); all-NBA/POL-404-DOWN(sleeping) |
| 185 | 2026-05-29T02h | ODD | S18-c931-g2791-stag=0(AUTO-RESET-c925!-stag-hit-25)-pareto=12(STABLE)-ET-200f-Brier~0.221-0.223-Rule8-POSSIBLE-1ST-CLEAN-RESET(unconfirmed); S22-c837-g2510-stag=0-pareto=48(↑13↑48-MASSIVE-SURGE!)-c828/829-CONFIRMED(no-stacking-Rule8-8TH-CLEAN!)-LR-43f-dominant-ET-0.21877-MAY-BE-IN-PARETO(15+fires-/api/export-EXTREME-URGENT); S13/S14/S15-404-DOWN; all-POL-404-DOWN(21+fires); ODD-no-WebSearch |
| 184 | 2026-05-28T22h | EVEN | S18-c892-g2674-stag=16(>15-DIVERSIFY!-VM-URGENT)-pareto=12(↟15↑12-3RD-CONSEC-SHRINK)-LightGBM-38f-pop-dominant; S22-c807-g2421-stag=0-pareto=13(STABLE)-c778+c803-CONFIRMED-LR-43f-CONFIRMED(API-explicit)-Rule8-7TH-LIKELY-COMPLIANT; S13/S14/S15-404-DOWN; all-POL-404-DOWN(20+fires); EVEN: no-new-proposal; auto-reset-mechanics-corrected |
| 183 | 2026-05-28T18h | ODD | S18-c859-g2575-stag=0-pareto=15(↟19↑15-post-c850)-c850-CONFIRMED(Rule8-5TH-VIOLATION-stacking)-CatBoost-0.21995-POSSIBLY-LOST(top-now-RF/ET-~0.2206); S22-c776-g2328-stag=0-pareto=13(↑7↑13-RECOVERING!)-next-auto-reset-~c778-IMMINENT(2cycles!)-LR-dominating(NEW)-ET-strong-Pareto-Rule8-LIKELY-COMPLIANT-6TH; S13/S14/S15-404-DOWN; all-POL-404-DOWN; ODD-no-WebSearch |
| 182 | 2026-05-28T14h | EVEN | Axelrod-verify-pass: SHAs-NBA-19f4acf49d(5993L)/POL-3496362c60(3977L)-UNCHANGED-vs-fire-181; 13/13-parity-OK; C→B→A-confirmed(NBA-L5056/5065/5073-POL-L3246/3255/3263); KL-div-ε-smoothed-self-excluded-OK; AXELROD_ARCHETYPES-NBA-20-sports/POL-20-political-financial-OK; Mech-B+C-BLOCKED(do_not_push_hf_space_yet+NBA-503-123+d+POL-IDLE-35+d); all-NBA/POL-404-DOWN(sleeping) |
| 181 | 2026-05-28T10h | ODD | S18-c837-g2509-stag=11(↑20↑11-RECOVERED-c825-auto-reset!)-pareto=19(↑11↑19-MAJOR-SURGE!)-CatBoost-200f-0.21995-gen=2505-POTENTIAL-NEW-FLEET-BEST(<0.22012★-EXTREME-URGENT); hard-reset-c825-CONFIRMED-stacking-REINTRODUCED-AGAIN(Rule8-4TH-VIOLATION); S22-c757-g2269-stag=0; next-auto-reset-~c778(21cycles); RF-primary-NO-STACKING-Rule8-LIKELY-COMPLIANT-5TH-fire; ET-0.21877-EXTREME-URGENT(12+fires); S13/S14/S15-404-DOWN; all-POL-404-DOWN; ODD-no-WebSearch |
| 180 | 2026-05-28T06h | EVEN | S18-c821-g2461-stag=20(↑0↑20-DIVERSIFY-NEEDED-VM-URGENT)-pareto=11(13↑11-2ND-SHRINK)-RF+ET-NO-STACKING-Rule8-LOOKS-RESOLVED(2nd-fire); next-auto-reset-~c825(4cycles-IMMINENT); S22-c740-g2219-stag=11-local-optimum-pattern-RF-primary-NO-STACKING-Rule8-LIKELY-COMPLIANT-4TH-fire; ET-0.21877-EXTREME-URGENT(11+fires); S13/S14/S15-404-DOWN; all-POL-404-DOWN; EVEN: arXiv:2510.17915-dual-isotonic-calibration-post-hoc-proposal-written |
| 179 | 2026-05-28T02h | ODD | S18-c800-g2400-stag=0-pareto=13(↑12↑13-RECOVERING!)-hard-resets-c750+c775-BOTH-CONFIRMED; RF-best-NO-STACKING(Rule8-POSSIBLE-RESOLUTION-unconfirmed); S22-c720-g2160-stag=0-c703-auto-reset-CONFIRMED; next-~c728; RF-primary-NO-STACKING(Rule8-LIKELY-COMPLIANT-3rd-fire); ET-0.21877-EXTREME-URGENT(10+fires); S13/S14/S15-404-DOWN; all-POL-404-DOWN; ODD-no-WebSearch |

---

## Glossary

- **stag**: stagnation counter (generations without pareto improvement)
- **pareto**: number of non-dominated solutions in island population
- **pareto_best**: best Brier score ever seen in pareto front (from /api/export)
- **best_brier**: current best Brier in /api/status (lags pareto_best by 1-3 fires)
- **field-lag**: best_brier field not yet updated despite pareto improvement
- **BVC**: Bootstrap Variance Calibration
- **ECE**: Expected Calibration Error (4th Pareto objective, fire-172 proposal)
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
