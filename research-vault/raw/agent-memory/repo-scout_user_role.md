---
name: user_role
description: User is a quant sports AI founder building NBA game prediction system with genetic evolution
type: user
---

User runs a quantitative hedge fund focused on NBA game prediction. The system uses:
- Genetic evolution (NSGA-II) to evolve XGBoost/LightGBM/CatBoost/extra_trees models
- 6000+ features across 35 categories in a custom NBAFeatureEngine
- 6 HF Spaces as "evolution islands" running 24/7
- Supabase (PostgreSQL) for experiment tracking
- Google Colab T4 GPU for neural model training
- A Cloud Brain (Sonnet 4.6, every 4h) + VM Muscle architecture

Current best: Brier 0.21867 (experiment #734, extra_trees, 142 features, gen 104)
Target: Brier < 0.20, ROI > 5%, Sharpe > 1.5

User wants the repo-scout to search BROADLY across all domains (agents, ML, tools, NBA)
and be brutally specific about what to steal and how.

ZERO ML on VM — 1 vCPU / 969 MB RAM. Everything on HF Spaces or Colab.
