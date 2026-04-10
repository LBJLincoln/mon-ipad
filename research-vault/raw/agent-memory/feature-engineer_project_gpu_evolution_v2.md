---
name: gpu_evolution_v2_integration
description: Gemini-optimized GPU evolution script integrated at scripts/gpu_evolution_v2.py (2026-04-03)
type: project
---

Created `scripts/gpu_evolution_v2.py` (1017 lines) merging Gemini's uploaded script with `modal_tabicl_evolution.py` and `colab/nba_evolution_gpu.py`.

**Why:** The uploaded Gemini script had the right GA structure (POP=80, ELITE=8, 5-fold walk-forward, auto GPU detection) but was missing all imports, data loading, and the state persistence setup section. The existing Colab script depended on `evolution/genetic_loop_v3.py` (complex orchestration layer). The new file is fully self-contained.

**Key design decisions:**
- Self-contained: no dependency on `evolution/genetic_loop_v3` -- can run standalone on Colab/Modal/Kaggle
- Data loading cascade: GitHub clone → Supabase (DATABASE_URL) → local files
- `colab_setup()` helper installs deps + warms TabICL/TabPFN checkpoints before evolution
- `MAX_FEATURES=200` enforced in `Individual._enforce_cap()` + `evaluate()`
- `MUT_CEILING=0.15` (matches deployed islands S10/S11/S12/S15)
- `PURGE_GAP=5` rows purged from training tail to prevent leakage
- GC + `torch.cuda.empty_cache()` called after each full generation (not per fold)
- 30% TabICL bias on new children; 10% TabPFN if available
- State saved every generation to `/content/evolution_state.json`
- Best result written immediately to `best_gpu_v2_features.json` on each improvement

**How to apply:** When asked to run GPU evolution, point to this file. The original `modal_tabicl_evolution.py` remains for the Modal starmap path. The uploaded `.txt` file is NOT deleted per user instruction.

**Source files read:**
- `/home/lahargnedebartoli/mon-ipad/modigs gemini optimisation runtime gpu colab lahartgende bartoli.txt`
- `/home/lahargnedebartoli/mon-ipad/scripts/modal_tabicl_evolution.py`
- `/home/lahargnedebartoli/nomos-nba-agent/colab/nba_evolution_gpu.py`
