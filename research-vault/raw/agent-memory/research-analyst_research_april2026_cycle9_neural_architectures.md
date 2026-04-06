---
name: Research Cycle 9 — Neural Architectures Deep Sweep April 2026
description: April 3 2026 cycle 9: TabICLv2, discrete tokenization transformer (arXiv:2603.07448), MLP meta-learner stacking, Brier loss objective, LSTM Brier loss, GNN/TFT verdict (skip)
type: project
---

# Research Cycle 9 — April 3 2026
## Focus: Neural network architectures for NBA prediction — which beat tree-based on CPU vs GPU

## KEY VERDICT
Feature engineering still dominates for Brier improvement, but two architectural wins are immediately deployable:
1. MLP meta-learner for stacking (CPU, 2h effort, -0.003 Brier)
2. Brier loss objective for XGBoost/LightGBM (CPU, 2h effort, -0.002 Brier)
And one GPU-only breakthrough to watch: discrete tokenization transformer (arXiv:2603.07448, March 8 2026)

## Architecture Rankings (by Impact/Effort ratio)

### DEPLOY NOW (CPU-viable, HF Spaces)
1. **MLP Meta-Learner** (-0.003 Brier, 2h): Replace LR meta-learner with MLPClassifier(50,50) in StackingClassifier. NBA paper (Scientific Reports Aug 2025) validated 1.3% AUC gain.
2. **Brier Loss Objective** (-0.002 Brier, 2h): Custom XGBoost/LGBM gradient/hessian for Brier. grad=2*(p-y), hess=2. Habib (arXiv:2508.02725) = Brier 0.1589 best-ever basketball.

### GPU PATHS (Kaggle/Colab)
3. **TabICLv2** (-0.004 Brier, 3h): arXiv:2602.11139 Feb 2026. Beats tuned trees on 80% datasets. pip install tabicl --upgrade. Our ATR was 0.2157 with v1 + 110f — v2 + 200f should improve.
4. **Discrete Tokenization Transformer** (-0.005 Brier, 20h): arXiv:2603.07448 March 8 2026. 10.8% over tuned XGBoost on 600K-entity tabular forecasting. Calibration KS=0.0045. No code yet — watch for release.
5. **LSTM with Brier Loss** (-0.003 Brier, 12h): Habib 2025 template. 2-layer LSTM on team game sequences. GPU only.

### SKIP
- FT-Transformer: superseded by TabICLv2, GPU-only, marginal gain
- SAINT: same as FT-Transformer situation
- NODE: 2019 vintage, GPU-only (8-10x slower on CPU), beaten by CatBoost
- TFT: wrong problem framing (multi-horizon regression vs binary classification)
- GNN: best result 71.54% acc (Brier ~0.225) — BELOW our fleet's 0.22182

## Key Papers Found
- arXiv:2603.07448 (March 2026): Discrete Tokenization Transformer — 10.8% over XGBoost, calibrated PDFs, KS=0.0045. WATCH FOR CODE.
- arXiv:2602.11139 (Feb 2026): TabICLv2 — new SOTA, 80% win rate vs tuned trees, CPU offload_mode='auto'
- Scientific Reports Aug 2025: NBA stacking with MLP meta-learner — 83.27% acc, AUC 0.9213
- arXiv:2506.21387 (June 2025): Early stopping for TabICL — 1.3-2.2x speedup, no accuracy loss
- TabPFN-2.5 distillation engine: train on GPU, distill to CPU-fast MLP (proprietary PriorLabs enterprise)

## Hardware Reality Check
- HF Spaces free CPU: 2 cores, 16 GB RAM — TabICL CPU inference ~5-15 min per eval at 5K samples × 200 features
- TabPFN-2.5 CPU: only feasible for <=1000 samples (too slow otherwise)
- NODE CPU: 8-10x slower than GPU — completely infeasible for HF Spaces
- FT-Transformer CPU: 200 features = 40K attention elements — borderline feasible but very slow

## Projected Trajectory
- Week 1 (MLP meta + Brier loss on CPU): Brier ~0.219
- Next Kaggle (TabICLv2 200f): ATR ~0.213-0.215
- After shot-charts + 5y-Elo: ~0.210-0.212
- After discrete tokenizer (when code releases): ~0.205-0.208
- Breaking 0.200: requires ALL of TabICLv2 + shot-charts + discrete tokenizer

**Why:** The Montrucchio 0.199 benchmark was achieved with XGBoost + shot-chart CNN features, not exotic neural architectures. Architecture alone is not the gap.
**How to apply:** Prioritize the 2 CPU-deployable wins immediately, then monitor arXiv:2603.07448 for code. Do NOT waste effort on GNN/TFT/NODE.
