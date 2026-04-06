---
name: project_march2026_findings
description: Top repo-scout findings from three broad March 2026 scans (NBA-specific + AI ecosystem + political alpha)
type: project
---

Four scans completed. Scan 1: 2026-03-25 NBA/tabular ML focus. Scan 2: 2026-03-25 AI agents/GPU/ML framework focus. Scan 3: 2026-03-26 comprehensive (NBA + calibration + EA + political alpha). Scan 4: 2026-03-26 deep dive (calibration libs, Mitra, shap-hypetune, nba_api 1.11.3, betting APIs, soccer stacking).

**Why:** User requested full ecosystem coverage: NBA models, GBDT innovations, genetic algorithms, calibration, TabICL/TabPFN, Kelly, odds APIs, HF Spaces, agent frameworks, political signal detection.

## NEW FINDINGS (Scan 4, 2026-03-26 — not in prior scans)

1. **venn-abers March 8 2026 sklearn-compat update** — VennAbersCalibrator now has BaseEstimator/ClassifierMixin/RegressorMixin. Fully Pipeline-compatible. pip install venn-abers (195 stars, MIT). Drop-in for CalibratedClassifierCV(method='isotonic'). Finite-sample calibration guarantees. 2h, -0.004 Brier. Supabase: inserted as proposal.

2. **shap-hypetune BorutaShap for GA seeding** — SHAP + Boruta + RFE feature selection for XGBoost/LightGBM. Run on Colab against 6149 features, use mask to seed island populations. 583 stars. pip install shap-hypetune. 6h, -0.002 Brier indirect (faster GA convergence). Supabase: inserted.

3. **Mitra (Amazon, AutoGluon 1.4)** — autogluon/mitra-classifier on HuggingFace. Mixed synthetic priors (causal + tree). 2D attention. SOTA on <5k samples / <100 features — exactly our subsample eval window. CPU+GPU. pip install 'autogluon.tabular[mitra]'. 3h, -0.003 Brier. Supabase: inserted.

4. **nba_api 1.11.3 (Feb 20 2026)** — LeagueHustleStatsPlayer endpoint: contested_shots, deflections, charges_drawn, screen_assists, loose_balls, box_outs. Cat38 candidates. 4h to integrate as Cat38. Supabase: inserted as BALLDONTLIE hustle stats proposal update.

5. **SoccerPredictor domain decomposition** — separate home-win / away-win specialized models + Ridge meta-learner (updated March 2026). Dynamic ELO K-factor. 6h to test, -0.002 Brier. Supabase: inserted.

## NEW FINDINGS (Scan 3, 2026-03-26 — not in prior scans)

1. **AF-NSGA-II (MDPI Jan 5 2026)** — Adaptive NSGA-II for high-dimensional feature selection. Sparse 3-filter initialization + adaptive crossover switching (geometric/non-geometric based on Hamming similarity). Directly addresses our population health issue (>60% compute on dead individuals). Implement in genetic_loop_v3.py, deploy to S15. 6h, -0.003 Brier.

2. **KernelICL (arXiv Feb 2026)** — ICL is mathematically equivalent to kernel regression. Makes TabICL/TabPFN predictions interpretable as weighted averages of training labels. Use as diagnostic for NBA regime detection — which games historically influence each prediction. Matches opaque model performance on 55 TALENT datasets.

3. **Distributional Regression Scoring Rules paper (arXiv Mar 2026, 2603.08206)** — Different proper scoring rules (CRPS, CRLS, interval score) induce different model rankings. Fine-tuning TabPFN-2.5 with CRLS consistently improves probabilistic metrics. Action: change XGBoost eval_metric from logloss to Brier explicitly; test CRLS fine-tuning of TabPFN-2.5 on Colab. -0.003 Brier expected.

4. **Polymarket insider tracker (GitHub Jan 4 2026)** — DBSCAN wallet clustering + event correlation (1-4h before announcements). 86 commits, actively developed. CNN confirmed March 24 2026: $1M trader, 93% win rate on unannounced Iran military ops. Validate concept for nomos-political-alpha.

## Top 5 Actionable Items (highest ROI, updated Scan 3)

1. **TabICLv2 execution on Colab** — Colab T4: TabICLClassifier(n_estimators=8) on 63-feature subset. Fold-4 = 0.21222 already validated. Execute now. 4h, -0.004 Brier. (~0.21467 target)

2. **AF-NSGA-II adaptive crossover** — implement in genetic_loop_v3.py: hamming_similarity > 0.90 triggers block-swap crossover; sparse_init() for new islands. 6h, -0.003 Brier. Deploy to S15 first.

3. **CRLS scoring objective** — change XGBoost eval_metric to Brier explicitly (30min). Test CRLS fine-tuning of TabPFN-2.5 on Colab (6h). -0.002 to -0.004 Brier.

4. **BALLDONTLIE hustle stats Cat38** — MCP server, /nba/v2/stats/advanced, add deflections/charges_drawn/screen_assists/contested_shots. 3h, -0.002 Brier.

5. **Prediction market implied probability** — extract NBA markets from Polymarket/Kalshi dataset. Feature: pred_mkt_home_win_prob + pred_mkt_vs_book_delta. 5h, -0.002 Brier.

## Prior Scan Top 3 (still valid, still not executed)

6. **MAPIE Venn-Abers calibration** — marked 'live' in Supabase but verify actual deployment. 3h, -0.005 to -0.008 Brier.
7. **BALLDONTLIE MCP + injury/market features** — same as #4 above but also includes injury reports as Cat39. 5h, -0.003 to -0.006 Brier.
8. **TabPFN-2.5 distillation** — Colab T4: fit TabPFN-2.5 on 63 features, distill to CatBoost, deploy to HF Spaces CPU. 8h, -0.003 Brier.

## Tabular ML State 2026 (updated)

- TabICLv2 checkpoint 2026-02-12: v2 update (regression added, better pretraining, faster)
- TabPFN-2.5: 87% win rate vs XGBoost on <100k samples
- TabArena top-6 not statistically different; diverse ensemble > GBDT-only confirmed
- TabM (Microsoft) appears in TabArena top-3 alongside LightGBM and RealMLP — investigate
- CRLS scoring rules: training objective matters beyond just model architecture
- AF-NSGA-II: adaptive crossover > standard crossover for high-dimensional FS

## Political Alpha (nomos-political-alpha context)

- CNN March 24 2026: $1M Polymarket trader, 93% win rate on Iran strikes
- Magamyman: $553k on Khamenei assassination prediction
- polymarket-insider-tracker (Jan 4 2026): DBSCAN + event correlation detection
- BETS OFF Act in Congress — regulatory risk, capture data now
- Techniques: fresh wallet detection, liquidity impact, sniper clusters, event correlation window

## Key Structural Discoveries (carried from Scan 1)

- **Ogham-MCP** — Supabase + pgvector shared memory for all 6 islands + Brain
- **BALLDONTLIE MCP** — 23 NBA tools, official, free tier adequate
- **Odds-API.io Python SDK** — 250+ bookmakers, line movement timestamps

## Agent Ecosystem State (carried from Scan 2)

- Claude Agent SDK v0.1.49-50: AgentDefinition with skills/memory/mcpServers, session tagging
- Google ADK v2.0.0a1: graph-based workflow runtime, native A2A
- vectorize-io/hindsight MCP: SOTA LongMemEval, retain/recall/reflect ops
- A2A protocol: 100+ enterprise support, bridges MCP with inter-agent comms

## Scan 4 Betting API Findings

- **The Odds API** — historical NBA odds (moneyline/spread/totals from 2020) on paid tier only (~$20/mo). Free tier: 500 credits/month current odds only. Historical is 10x credit cost.
- **BALLDONTLIE** — free tier, decades of historical stats + advanced metrics + PBP 2025+. Best free data source.
- **ShotQuality API** — paid only, computer vision shot difficulty metric. No open-source equivalent. Monitor only.
- **CLV (Closing Line Value)** — track open vs close odds delta as quality metric. Best long-term ROI predictor. Needs The Odds API paid tier. Defer until budget allows.

## Tabular ML State 2026 — Scan 4 Additions

- **TabPFN-2.5 distillation** — converts to compact MLP or tree ensemble for CPU deployment. Highest-value deferred action after Brier < 0.215.
- **AutoGluon 1.5.1** also available — GPU TreeSHAP 10x speedup.
- **Mitra CPU compatibility** — unlike TabICLv2 which needs GPU for speed, Mitra can run on CPU (slower but viable for HF Spaces if feature count <= 100).
- **TabArena top-3**: RealTabPFN-2.5, TabICLv2, Mitra — all now available via pip.

**How to apply:** Execute in order: (1) Venn-Abers calibration on Colab (2h, highest confidence), (2) Colab TabICLv2 stacking execution (already validated fold-4=0.21222), (3) Mitra as GPU_MODEL_TYPE (3h), (4) AF-NSGA-II in genetic_loop_v3 + S15 deploy, (5) CRLS eval_metric change, (6) Cat38 hustle stats via nba_api 1.11.3, (7) shap-hypetune BorutaShap offline GA seeding.
