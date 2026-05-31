# SOTA Research Proposal — Discrete Tokenization for Calibrated Tabular Transformers

**Source**: arXiv:2603.07448 (March 8, 2026) — "Discrete Tokenization Unlocks Transformers for Calibrated Tabular Forecasting"  
**Fire**: 238 (EVEN)  
**Priority**: 111  
**Work-queue ID**: vm-research-discrete-tokenization-fire238

## Key Finding
Gradient boosting (XGBoost/LightGBM/CatBoost) dominates Transformers on tabular benchmarks because continuous embedding spaces fail to capture discrete feature distributions. This paper proposes a **discretized vocabulary tokenizer** with Gaussian smoothing that:
1. Bridges the performance gap between Transformers and gradient boosting on tabular data
2. Produces **calibrated PDFs** natively — no post-hoc isotonic/Venn-Abers calibration needed
3. Outperforms tuned gradient boosting on Brier and CRPS metrics

## Relevance to Nomos42
S22 fire-238 Brier range 0.21881~0.22327 with XGB/LGB/CAT-only gene pool — proves non-RF models can compete at 200f. Discrete tokenization Transformer is the natural next step: native probabilistic calibration + tabular-optimized architecture, extending the XGB/LGB/CAT exploration direction.

Connects directly to:
- fire-236 ScoringBench (arXiv:2603.29928): CRPS/CRLS proper scoring rules
- fire-236 DistribTabFM (arXiv:2603.08206): distributional tabular FM evaluation
- fire-224 localized CP (arXiv:2602.19284): calibrated predictions at multiple scales

## Applications

### App 1: New MODEL_TYPE — `discrete_transformer`
- Add to evolution islands alongside XGB/LGB/CAT
- Config: vocab_size=256, gaussian_smoothing_sigma=0.1, n_layers=6, d_model=256
- Evaluate on 9,551 NBA games at 48f, 75f, 200f feature counts
- Expected: enters Pareto front by generation 300-500

### App 2: ScoringBench Evaluation (extends fire-236)
- Evaluate discrete Transformer vs TabICLv2 vs XGB/LGB/CAT on NBA 186f using:
  - Brier (current optimization target)
  - CRPS (fire-236 App2 candidate)
  - CRLS (fire-236 App3 candidate)
- Expected: discrete Transformer wins CRPS; XGB/LGB/CAT wins pure Brier

### App 3: Direct Brier-Loss Training
- Replace post-hoc calibration (isotonic/Venn-Abers) with native Brier-loss training objective
- Ties to arXiv:2603.08206: fine-tune with scoring-rule-specific objective
- Expected: 0.001-0.002 Brier improvement vs post-hoc calibration

### App 4: Political Engine Port
- Add `discrete_transformer` to political_engine.py MODEL_TYPES
- State-level calibration: discrete tokenization handles sparse political features (binary incumbency, party ID) better than continuous embeddings
- Analog to App 1 for NBA

## Expected Improvement
- NBA: 0.001-0.003 Brier (calibrated PDF + gradient boosting parity on tabular)
- POL: 0.002-0.005 Brier (sparser feature space benefits more from discretization)
- Synergy with CRPS/CRLS objectives (fire-236): 0.002-0.004 combined

## Implementation Notes
- Library: `tab-transformer-pytorch` or HuggingFace tabular models
- Discretization: quantile binning with vocab_size=256 (each feature mapped to 1 of 256 bins)
- Gaussian smoothing: sigma=0.1 prevents overfitting to bin boundaries
- Training: Brier loss (not cross-entropy) for native probabilistic calibration
- Feature engineering: apply same 186f feature set from oracle-model (top-by-variance from 4581 alive engine cols)

## Dependencies
- Builds on: fire-236 ScoringBench (arXiv:2603.29928) + DistribTabFM (arXiv:2603.08206)
- Enables: direct Brier-loss training (replaces post-hoc calibration on all islands)
- Blocks: nothing (additive new MODEL_TYPE)

## Work Queue
- Item: `vm-research-discrete-tokenization-fire238`
- Priority: 111 (highest research priority; ScoringBench fire-236 = 110)
- Owner: local-vm
