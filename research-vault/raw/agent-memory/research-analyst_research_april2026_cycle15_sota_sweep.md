---
name: March-April 2026 SOTA Sweep (Cycle 15)
description: Apr 7 2026 cycle 15 — TabICLv2 (arXiv:2602.11139), Brier-loss training (arXiv:2508.02725), Kelly-Bayesian weighting (arXiv:2602.09982), SCoRE bet filter (arXiv:2603.24704), Shot-chart PCA-20 from Montrucchio MDPI 2026 (Brier 0.089), ScoringBench (arXiv:2603.29928), TabTune (arXiv:2511.02802)
type: project
---

## April 7 2026 — Cycle 15 Research: March-April 2026 SOTA Sweep

### Key Papers Found

**TabICLv2** (arXiv:2602.11139, Feb 11 2026, soda-inria)
- Beats RealTabPFN-2.5 (tuned+ensembled+fine-tuned) WITHOUT any hyperparameter tuning on TabArena + TALENT
- 10x faster than RealTabPFN-2.5. Scales to 1M rows under 50GB GPU.
- API: `TabICLClassifier(n_estimators=8, softmax_temperature=0.9)`. Install: `pip install tabicl`
- nanoTabICL repo (170 LOC) for CPU testing
- Expected: -0.004 Brier upgrade from TabICL v1 (3h effort, Kaggle P100)

**Montrucchio et al. MDPI 2026** (MDPI Information 17(1):56, Jan 2026)
- NBA-specific SOTA: Brier 0.089 on 2024 test season. AUC 0.95.
- Architecture: LSTM + CNN shot-chart PCA-20 embedding + MC Dropout
- PCA-20: nba_api shotzone data -> 2D heatmap -> sklearn PCA -> 20 dims (92.7% variance)
- 40 features/game (20 home + 20 away). Offline VM computation, no GPU.
- Market features (implied prob, spread, total, overround) in the model
- Confirms: exploitable edge in moneylines only, not spreads/totals

**Kelly-Bayesian Ensemble** (arXiv:2602.09982, Beuoy, Feb 10 2026)
- Kelly bankroll weighting beats log-loss AND Brier at distinguishing correct/incorrect models
- 98/110 scenarios after 5 rounds. Bankroll = Bayesian credibility proxy.
- Formula: `bankroll_i *= (p_i/p_market)^y * ((1-p_i)/(1-p_market))^(1-y)`
- Replace equal-weight ensemble with bankroll-proportional weights. VM-only, 4h.

**Brier-Loss Training** (arXiv:2508.02725, LSTM NCAA, Aug 2025)
- LSTM trained with Brier loss -> Brier 0.1589. Transformer with BCE -> 0.21+
- Direct lesson: switch LightGBM/CatBoost from binary_logloss to MSE-on-probs
- Applies to all 6 HF Spaces. 5h effort. No GPU needed.

**SCoRE Conformal Bet Filter** (arXiv:2603.24704, Mar 28 2026)
- e-values for selective prediction: e_i = p_predicted/p_market
- Abstain when e_i < threshold. Finite-sample guarantee.
- Distribution-free, no modeling assumptions. Better than 'edge > 5%' heuristic.
- Expected: +5-8% filtered ROI, Sharpe improvement toward 1.5 target.

**ScoringBench** (arXiv:2603.29928, Mar 28 2026)
- Benchmarks TabPFNv2.5 and TabICL under Brier, CRPS, CRLS on 49 datasets
- TabICL best Brier: 0.995. No paper has fine-tuned TabICLv2 with Brier loss yet (open experiment)
- Temperature tuning (softmax_temperature sweep [0.7-1.1]) is the practical calibration lever

**TabTune** (arXiv:2511.02802, Nov 2025, github.com/Lexsi-Labs/TabTune)
- Unified library for 7 tabular foundation models with built-in Brier/ECE evaluation
- Enables systematic fine-tuning sweep in one Kaggle session

### Priority Ranking vs Backlog

Backlog updates:
- Bayesian Kelly: SUPERSEDED — arXiv:2602.09982 is cleaner, 4h instead of 12h
- Shot-chart CNN: SCOPED DOWN — PCA-20 (20h) replaces full CNN (40h)  
- Obsidian RAG: SKIP — no new 2026 support

New finds ranked by delta/effort:
1. TabICLv2 upgrade: -0.004 Brier / 3h (BEST RATIO)
2. Brier-loss training obj: -0.002 Brier / 5h (all 6 spaces)
3. Kelly-bankroll weighting: -0.003 Brier / 4h (VM-only)
4. Shot-chart PCA-20 Cat50: -0.005 Brier / 20h (biggest gain)
5. SCoRE bet filter: 0 Brier / +5-8% ROI / 8h (Sharpe target)
6. TabTune sweep: -0.003 Brier / 8h (after #1)

**Why:** Cumulative math: 0.2157 - 0.004 - 0.002 - 0.003 - 0.005 - 0.003 = 0.1987 < 0.20 target
**How to apply:** Prioritize TabICLv2 first (biggest ROI on effort). Brier-loss obj second (zero GPU, applies everywhere). Kelly weighting third (VM-only). Shot-chart fourth (new data pipeline needed).
