---
tags: [gpu, autoresearch, karpathy, modal, kaggle, colab, lightning, models, training]
date: 2026-04-04
aliases: [GPU Autoresearch, Karpathy GPU, ML Training, Model Training]
---

# 24 -- GPU Autoresearch System

> Real Karpathy autoresearch running on all GPU platforms with all 15 models, 3 targets, and a review agent.
> See also: [[16-Karpathy-Pattern]], [[11-GPU-Compute]], [[25-ML-Predictions]]

---

## 15 Model Types

| # | Model | Type | GPU | CPU | SOTA |
|---|-------|------|-----|-----|------|
| 1 | XGBoost | Tree | hist/CUDA | hist | Workhorse |
| 2 | XGBoost-Brier | Tree (custom obj) | hist/CUDA | hist | Best calibration |
| 3 | LightGBM | Tree | cuda_exp | cpu | Fast |
| 4 | CatBoost | Tree | native CUDA | cpu | Great on categorical |
| 5 | RandomForest | Bagging | n_jobs=-1 | n_jobs=-1 | Baseline |
| 6 | ExtraTrees | Bagging | n_jobs=-1 | n_jobs=-1 | S14 champion |
| 7 | LogisticRegression | Linear | - | cpu | Literature 0.199 |
| 8 | MLP | Neural | CUDA | - | Fast neural |
| 9 | LSTM | Seq Neural | CUDA | - | Temporal |
| 10 | Transformer | Attention | CUDA | - | State-of-art |
| 11 | FT-Transformer | Tab Attention | CUDA | - | SOTA tabular |
| 12 | TabNet | Attention Tab | CUDA | - | Feature selection |
| 13 | Deep Ensemble | 5× MLP | CUDA | - | Uncertainty |
| 14 | TabICL | In-context | CUDA | - | SOTA zero-shot |
| 15 | AutoGluon | AutoML | CUDA | cpu | Best ensemble |

## 3 Prediction Targets (not just moneyline!)

| Target | Type | y = | Metric | Informs |
|--------|------|-----|--------|---------|
| **moneyline** | Classification | 1 if home_score > away_score | Brier | 7 ML + parlays |
| **spread** | Regression | home_score - away_score | RMSE/30 | 9 spread + margin + alt lines |
| **total** | Regression | home_score + away_score | RMSE/50 | 10 totals + alt totals |

## GPU Platforms

| Platform | GPU | Hours | Script | Status |
|----------|-----|-------|--------|--------|
| [[22-Compute-Mesh#Modal\|Modal]] | T4/A10G/A100 | Serverless | `modal_autoresearch.py` | DEPLOYED (daily cron 6AM UTC) |
| [[22-Compute-Mesh#Kaggle\|Kaggle]] | P100 16GB | 9h/session | `kaggle_autoresearch.py` | READY (30h/week quota) |
| [[22-Compute-Mesh#Colab\|Colab]] | T4 16GB | 12h/session | `colab_autoresearch.py` | READY |
| [[22-Compute-Mesh#Lightning\|Lightning]] | T4/H200 | 22h/session | `lightning_autoresearch.py` | DEPLOYING |

## Review Agent

After each 5-min iteration, the **ReviewAgent** analyzes:
1. **Brier/RMSE delta** — did this iteration improve any target?
2. **Model type ranking** — which model types perform best?
3. **Feature count** — too few (underfitting) or too many (overfitting)?
4. **Stagnation detection** — 5+ iterations without improvement → boost mutation
5. **Diversity check** — too few model types → force diversification
6. **Auto-adjust config** — mutation rate, target features, diversity enforcement

Log: `WORK/review_agent_log.jsonl`

## Best Python ML Libraries

```
xgboost>=2.1        — GPU histogram, custom Brier objective
lightgbm>=4.5       — GPU cuda_exp backend
catboost>=1.2.7     — Native CUDA, no preprocessing needed
torch>=2.5          — MLP, LSTM, Transformer, FT-Transformer
pytorch-tabnet>=4.1 — Attention-based tabular neural net
tabicl>=0.3         — In-context learning (SOTA tabular)
autogluon>=1.2      — AutoML ensemble (heavy)
scikit-learn>=1.6   — RF, ExtraTrees, LogReg, calibration
optuna>=4.1         — Hyperparameter tuning
```

## Files

| File | LOC | Purpose |
|------|-----|---------|
| `scripts/gpu/karpathy_gpu_autoresearch.py` | 1075 | Main engine (all 15 models × 3 targets) |
| `scripts/gpu/modal_autoresearch.py` | 170 | Modal serverless deployment |
| `scripts/gpu/kaggle_autoresearch.py` | 60 | Kaggle P100 launcher |
| `scripts/gpu/colab_autoresearch.py` | 42 | Colab T4 launcher |
| `scripts/gpu/lightning_autoresearch.py` | 33 | Lightning AI launcher |

## Claude Code as RAG

This Obsidian vault IS the knowledge base. Claude Code reads these `.md` files directly — no vector DB needed. Karpathy's approach:
- Obsidian = structured knowledge graph via wikilinks
- Claude Code CLI = reads/writes files = natural RAG
- No separate embedding/retrieval pipeline
- Every conversation starts with context from `CLAUDE.md` + memory files
- Obsidian graph view shows relationships between concepts
