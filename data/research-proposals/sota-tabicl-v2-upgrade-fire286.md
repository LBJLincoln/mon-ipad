# TabICLv2: Better, Faster, Scalable Tabular Foundation Model (fire-286 EVEN)

**arXiv:** 2602.11139 (Feb 11, 2026)  
**Title:** "TabICLv2: A better, faster, scalable, and open tabular foundation model"  
**Authors:** Jingang Qu, David Holzmüller, Gaël Varoquaux, Marine Le Morvan (INRIA/Soda team)  
**Priority:** 137  
**Fire:** fire-286 EVEN  
**Link:** https://hf.co/papers/2602.11139

---

## Key Findings

TabICLv2 is the direct upgrade to TabICL (arXiv:2502.05564), which the Nomos42 Colab pipeline uses to achieve Brier 0.21139 (walkforward holdout) / 0.22169 (CV) on 186f NBA dataset. Three architectural pillars:

1. **Novel synthetic data generation engine** — higher pretraining diversity through improved coverage of real-world distribution shapes (skewed, bounded, heavy-tailed). The NBA feature engine (7246+ raw features, 4581 alive) represents a high-diversity distribution that benefits directly from richer pretraining diversity.

2. **Scalable softmax in attention** — enables generalization to million-scale datasets without prohibitive long-sequence pretraining. Current TabICL context=3072 is constrained; TabICLv2 can handle 11440+ games with larger context windows under ≤50GB GPU memory.

3. **Muon optimizer replaces AdamW** — better gradient geometry for tabular pretraining; faster convergence and stronger generalization on TALENT + TabArena benchmarks.

**Benchmark results:** TabICLv2 *without hyperparameter tuning* surpasses RealTabPFN-2.5 (the previous SOTA, which is hyperparameter-tuned + ensembled + fine-tuned on real data) on both TabArena and TALENT. This is a major leap over the TabICL version currently in Colab.

**Open weights + inference code:** github.com/soda-inria/tabicl (pip install tabicl --upgrade)

---

## Current Nomos42 Context

The team's Colab benchmark (colab/nba_evolution_gpu.ipynb):
- TabICL (arXiv:2502.05564, original): Brier **0.21139** walkforward holdout / **0.22169** CV on 186f features  
- Honest production expectation: **0.22054** isotonic-calibrated (due to window bias in holdout)
- NBA fleet best: **0.22012** (S15 RF-75f, fire-61 checkpoint)
- Gap TabICLv2 target: potentially 0.001-0.003 improvement → **sub-0.220** Brier realistic

The fire-236 (priority=110) research entry mentioned "TabICLv2 upgrade path" as Application 4 under ScoringBench. This entry gives TabICLv2 its own dedicated priority slot with full implementation plan.

---

## Applications

### Application 1: Direct Colab Upgrade (highest priority)
Upgrade `colab/nba_evolution_gpu.ipynb` from TabICL to TabICLv2:
```python
# Replace:
# !pip install tabicl==0.1.x
# from tabicl import TabICLClassifier
# clf = TabICLClassifier(context_size=3072, ...)

# With:
!pip install tabicl --upgrade  # installs TabICLv2
from tabicl import TabICLClassifier
clf = TabICLClassifier(
    context_size=8192,   # TabICLv2 can handle larger ctx
    temperature=1.0,
    n_ensembles=8        # TabICLv2 ensembling is efficient
)
```
Expected: Brier improvement from 0.22169 CV toward 0.220 or below. If CV drops below 0.22012 (fleet best), promotes to new oracle model at LBJLincoln26/nba-oracle-model.

### Application 2: Larger Training Set via Scalable Softmax
TabICL was limited to context_size=3072 due to memory. TabICLv2 scalable softmax enables:
```python
# Current: 3072 samples in context
# TabICLv2: up to ~50K samples efficiently
clf = TabICLClassifier(context_size=11440)  # ALL 11440 games
```
More training data = better generalization on validation set. Expected 0.001 additional Brier gain.

### Application 3: Multi-Metric Evaluation (connects to priority=110 ScoringBench)
Run TabICLv2 on all 6 proper scoring metrics simultaneously:
```python
from properscoring import brier_score_loss, crps_ensemble, crps_gaussian
# Evaluate: Brier + CRPS + CRLS + log-score + interval-score + calibration-error
# TabICLv2 has explicit distributional calibration — expected to outperform TabICL on CRPS/CRLS
```
Gate: TabICLv2 must also improve CRPS (not just Brier) before oracle promotion.

### Application 4: Feature Selection via TabICLv2 Importance
TabICLv2's attention mechanism provides implicit feature importance via attention scores:
```python
# Use TabICLv2 attention weights to identify top 186 features from 4581 alive engine cols
# Replace current "top-by-variance" selection with "top-by-TabICLv2-attention"
# Expected: better feature selection → further Brier improvement
```

### Application 5: Port to political_engine.py
Run TabICLv2 on POL feature engine (2400+ features). POL dataset is smaller (rare events), which aligns with TabICLv2's ICL strength at lower sample counts. TabICLv2's distributional calibration directly improves P4/P7 election probability estimates.

---

## Implementation Plan

**Phase 1 (Colab VM, ~2h):**
1. `!pip install tabicl --upgrade` in nba_evolution_gpu.ipynb
2. Replace TabICLClassifier with new params (context_size=8192, n_ensembles=8)
3. Run 3-way comparison: TabICLv1 vs TabICLv2 vs top GA model on 186f dataset
4. Record Brier + CRPS + CV scores

**Phase 2 (if Phase 1 improves by ≥1bp, VM ~1h):**
1. Run TabICLv2 with full context (context_size=11440) on T4 GPU
2. Save model to LBJLincoln26/nba-oracle-model if below fleet best 0.22012
3. Compare with current oracle model (arXiv:2502.05564 TabICL, Brier 0.22054)

**Phase 3 (political, VM ~1h):**
1. Run TabICLv2 on political feature set (top-200 from 2400+ features)
2. Compare vs P4 LGB-121f-0.2491 candidate on holdout
3. If TabICLv2 POL Brier < 0.2491: checkpoint as new POL oracle candidate

---

## Synergies with Existing Pipeline

| Priority | Paper | Synergy |
|----------|-------|---------|
| 110 | ScoringBench (arXiv:2603.29928) | TabICLv2 evaluation under CRPS+CRLS proper scoring rules |
| 114 | Calibration Set Reuse (arXiv:2506.19689) | E-conformal + Hoeffding wraps TabICLv2 predictions |
| 115 | TabFM Conditional Density (arXiv:2603.26611) | TabICLv2 as base model in 6-metric benchmark |
| 136 | Calibeating Bregman (arXiv:2605.17269) | U-calibeating audit on TabICLv2 before oracle promotion |

---

## Expected Impact

- **Brier improvement:** 0.001-0.003 (TabICLv2 → from 0.22169 CV toward ≤0.219 on NBA)
- **Context window:** 3072 → 8192+ samples; covers full 11440-game training set
- **Calibration:** Native distributional calibration (scalable softmax) improves CRPS/CRLS
- **Speed:** TabICLv2 is "markedly faster than RealTabPFN-2.5" — Colab sessions complete faster
- **Open weights:** No API cost, full control, offline inference

## Work-Queue Tag
vm-research-tabicl-v2-upgrade-fire286 (priority=137)
