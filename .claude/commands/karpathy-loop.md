---
name: karpathy-loop
description: Run REAL Karpathy iteration loop — mutate config → train → measure metric → keep if better
---

Run a REAL Karpathy iteration loop. This is NOT internet research — it trains actual models and measures real metrics.

Arguments: $ARGUMENTS (optional: "nba", "political", "all", or "nba --iterations 50")

Pattern: mutate 1 config param → train model → measure Brier score → keep only if improved → repeat

## Steps

1. **Determine domain** from $ARGUMENTS (default: "all" = NBA + Political):
   - `nba` → run NBA iteration loop
   - `political` → run Political iteration loop
   - `all` → run both sequentially

2. **Check platform availability** (in order):
   - Kaggle: `python3 scripts/kaggle-live-status.py 2>/dev/null` → check if kernel is idle
   - Modal: `modal app list 2>/dev/null` → check if Modal is configured
   - CPU (VM fallback): always available — uses subsampled data (4000 games, ~50MB RAM)

3. **Run the REAL iteration loop**:
   ```bash
   # NBA (CPU fallback — always works on VM)
   cd /home/termius/mon-ipad
   bash scripts/karpathy/run_karpathy.sh nba --iterations 30

   # Political
   bash scripts/karpathy/run_karpathy.sh political --iterations 30
   ```

   If Kaggle is available, prefer launching the GPU kernel instead:
   ```bash
   bash scripts/kaggle-gpu-evolution.sh
   ```

4. **Read results**:
   ```bash
   # Check if Brier improved
   cat data/karpathy/nba-best-config.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Best Brier: {d.get(\"best_score\",\"?\")}')"
   cat data/karpathy/nba-history.json | python3 -c "import json,sys; h=json.load(sys.stdin); print(f'Iterations: {len(h)}, improvements: {sum(1 for x in h if x.get(\"improved\"))}')"
   ```

5. **Report results** — output structured summary:
   ```
   ## Karpathy Loop — Real Iteration Results

   **Domain**: NBA / Political / Both
   **Platform**: CPU (VM) / Kaggle GPU / Modal GPU
   **Iterations**: N completed
   **Best Brier**: X.XXXXX (previous: X.XXXXX, delta: -0.XXXXX)
   **Improvements**: N/M iterations improved
   **Config changes**: [list of mutations that helped]

   ### What worked:
   - mutation_type → Brier delta

   ### What didn't:
   - mutation_type → reverted
   ```

## What this loop does (per iteration):
1. Load best config from `data/karpathy/{domain}-best-config.json`
2. Mutate exactly ONE parameter (model type, n_estimators, max_depth, feature selection, etc.)
3. Train a real sklearn model on real NBA/political data
4. Measure Brier score on holdout set
5. If Brier improved → save new config, log improvement
6. If not → discard mutation, log failure
7. Send Telegram alert on new all-time best

## Constraints
- REAL training happens — this uses CPU/RAM
- CPU mode: 4000-game subsample + 200-game holdout = ~50MB RAM (fits on VM)
- Each iteration: ~30-60 seconds on CPU
- 30 iterations ≈ 15-30 minutes
- For GPU mode, use Kaggle or Modal (not VM)

## Key files:
- `scripts/karpathy/karpathy_utils.py` — mutation, evaluation, logging
- `scripts/karpathy/nba_iterate.py` — NBA iteration loop
- `scripts/karpathy/political_iterate.py` — Political iteration loop
- `scripts/karpathy/run_karpathy.sh` — runner script
- `data/karpathy/nba-best-config.json` — current best NBA config
- `data/karpathy/nba-history.json` — iteration history
