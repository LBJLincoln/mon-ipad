---
name: karpathy-loop
description: Run REAL Karpathy iteration loop — mutate config → train → measure metric → keep if better
---

Run one full Karpathy autoresearch iteration: SCAN → PROPOSE → EXECUTE → EVALUATE → LOG.

**Domain argument**: `$ARGUMENTS` — one of: `nba` (default), `political`, `betting`, `calibration`

This skill runs a SINGLE, SELF-CONTAINED, MEASURABLE iteration. It trains a real model, compares Brier before vs after, and keeps or reverts based on hard evidence. No bullshit "research" without measurement.

---

## STEP 0 — Parse domain and set paths

Parse `$ARGUMENTS`:
- If empty or `nba` → `DOMAIN=nba`, config=`data/karpathy/nba-best-config.json`, history=`data/karpathy/nba-history.json`, script=`scripts/karpathy/nba_iterate.py`, METRIC=Brier, TARGET=0.20
- If `political` → `DOMAIN=political`, config=`data/karpathy/political-best-config.json`, history=`data/karpathy/political-history.json`, script=`scripts/karpathy/political_iterate.py`, METRIC=Brier, TARGET=0.20
- If `betting` → treat as `nba` but focus mutation proposals on bet sizing / Kelly params
- If `calibration` → treat as `nba` but focus mutation proposals on calibration / ECE

All paths are relative to `/home/termius/mon-ipad`.

---

## PHASE 1 — SCAN (read state, no training yet)

Run these in parallel:

**1a. Read current best config** (exclude feature_indices for display):
```bash
cd /home/termius/mon-ipad
python3 -c "
import json
from pathlib import Path
cfg = json.loads(Path('data/karpathy/nba-best-config.json').read_text())
display = {k: v for k, v in cfg.items() if k != 'feature_indices'}
print(json.dumps(display, indent=2))
"
```
Replace `nba-best-config.json` with the domain-appropriate file.

**1b. Read last 10 iterations from history**:
```bash
cd /home/termius/mon-ipad
python3 -c "
import json
from pathlib import Path
h = json.loads(Path('data/karpathy/nba-history.json').read_text())
last10 = h[-10:]
for x in last10:
    kept = {k: v for k, v in x.items() if k in ['iteration','brier','improved','mutation','model_type','n_features','timestamp']}
    print(json.dumps(kept))
"
```

**1c. Read last 5 entries from iteration-log.jsonl** (rich log with reasoning):
```bash
cd /home/termius/mon-ipad
tail -5 data/karpathy/iteration-log.jsonl 2>/dev/null || echo "No iteration log yet"
```

**1d. Get current live Brier proxy**:
```bash
cd /home/termius/mon-ipad
python3 scripts/brier_proxy.py --json 2>/dev/null
```

**1e. Check no-improvement streak** (count consecutive non-improved at end of history):
```bash
cd /home/termius/mon-ipad
python3 -c "
import json
from pathlib import Path
h = json.loads(Path('data/karpathy/nba-history.json').read_text())
streak = 0
for x in reversed(h):
    if not x.get('improved'):
        streak += 1
    else:
        break
total = len(h)
improved = sum(1 for x in h if x.get('improved'))
best = min((x.get('brier', 1.0) for x in h), default=1.0)
print(f'Total iterations: {total}')
print(f'Total improved: {improved}')
print(f'Best Brier in history: {best:.5f}')
print(f'No-improve streak (recent): {streak}')
"
```

After running the SCAN, analyze the results and note:
- Current best Brier in config
- What has been tried recently (last 10 mutations)
- No-improvement streak length
- Whether we're in a local minimum (streak >= 5)

---

## PHASE 2 — PROPOSE one mutation

Based on the SCAN results, propose exactly ONE mutation. Use this decision logic:

**If no-improve streak >= 5 (stuck in local minimum):**
- Prefer high-diversity moves: `change_model` (try a different model type entirely), or `swap_features` with large N (15-20), or `change_max_depth` with large delta
- If `gradient_boosting` is current model: try `extra_trees` or `lightgbm`
- If `extra_trees`: try `gradient_boosting` (slowest but often best)

**If betting domain:**
- Propose a Kelly fraction adjustment: look at `data/arena/cpcv-gated-strategies.json` for current Kelly params
- Propose reducing Kelly if drawdown > 15% or increasing if Sharpe > 1.5
- Mutation: edit `scripts/arena/cpcv_gate.py` kelly_fraction parameter

**If calibration domain:**
- Read `data/monitoring/drift-calibration.json`
- Propose: isotonic calibration, Platt scaling, temperature scaling
- Target metric: ECE (Expected Calibration Error) not just Brier

**Standard mutation selection (no-improve streak < 5):**
- If last 3 mutations were all feature mutations → switch to hyperparameter mutation
- If last 3 mutations were hyperparameter → try a feature mutation
- Prefer mutations NOT seen in last 10 iterations

**Mutation types available (from karpathy_utils.py):**
1. `change_model` — switch model type (random_forest / extra_trees / gradient_boosting / lightgbm)
2. `change_n_estimators` — delta ±25/50/100 (bounds: 50-500)
3. `change_max_depth` — delta ±1/2/3 (bounds: 4-30)
4. `change_min_samples_leaf` — delta ±1/2/3 (bounds: 1-20)
5. `change_max_features_ratio` — delta ±0.02/0.05/0.10 (bounds: 0.05-0.80)
6. `add_features` — add 5 random features
7. `remove_features` — remove 5 worst features
8. `swap_features` — swap N features (remove N, add N different ones)

**State your proposal explicitly** before executing:
```
PROPOSED MUTATION: [mutation_type]
Rationale: [1-2 sentences why this specific mutation now]
Expected direction: [increase/decrease which param by how much, or which model]
Measurable via: brier_proxy.py --json
```

---

## PHASE 3 — EXECUTE (5-minute max)

Run the iteration engine with a SMALL number of iterations (3-5) focused on the proposed mutation type. This keeps execution under 5 minutes on VM CPU.

```bash
cd /home/termius/mon-ipad

# Capture Brier BEFORE
BRIER_BEFORE=$(python3 scripts/brier_proxy.py --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['brier'])")
echo "Brier BEFORE: $BRIER_BEFORE"

# Run 5 iterations (each ~30-60s on CPU = ~3-5min total)
bash scripts/karpathy/run_karpathy.sh nba --iterations 5 2>&1 | tail -20

# Capture Brier AFTER
BRIER_AFTER=$(python3 -c "
import json
from pathlib import Path
cfg = json.loads(Path('data/karpathy/nba-best-config.json').read_text())
print(cfg.get('best_brier', 1.0))
")
echo "Brier AFTER (best config): $BRIER_AFTER"
```

Replace `nba` with `political` for the political domain.

**Important:** The iteration engine already implements mutate→evaluate→keep/revert internally. We are running it for a short burst and then checking if it found an improvement.

**For betting domain:** Instead of running the iteration engine, directly edit the config:
```bash
cd /home/termius/mon-ipad
# Show current Kelly config
cat data/arena/cpcv-gated-strategies.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(list(d.items())[:3], indent=2))"
```

**For calibration domain:** Run the calibration audit:
```bash
cd /home/termius/mon-ipad
python3 scripts/brier_proxy.py --compute --json 2>/dev/null || python3 scripts/brier_proxy.py --json
```

---

## PHASE 4 — EVALUATE

After execution, evaluate what happened:

**4a. Read the latest iteration results**:
```bash
cd /home/termius/mon-ipad
python3 -c "
import json
from pathlib import Path

# Read config
cfg = json.loads(Path('data/karpathy/nba-best-config.json').read_text())
display = {k: v for k, v in cfg.items() if k != 'feature_indices'}
print('BEST CONFIG NOW:')
print(json.dumps(display, indent=2))

# Read last 5 history entries
h = json.loads(Path('data/karpathy/nba-history.json').read_text())
print(f'\nLAST 5 ITERATIONS:')
for x in h[-5:]:
    print(f'  iter={x[\"iteration\"]}, brier={x[\"brier\"]:.5f}, improved={x[\"improved\"]}, mutation={x[\"mutation\"]}')
"
```

**4b. Decision logic:**

- If `best_brier` in config DECREASED (improved) compared to BRIER_BEFORE: **KEEP** — improvement found
- If `best_brier` unchanged or worse: **REVERT** — no improvement this session

Note: The iteration engine already reverts internally per-iteration. This EVALUATE step is about the overall session outcome.

**4c. If KEEP and significant improvement (delta > 0.001):**
Commit the updated config:
```bash
cd /home/termius/mon-ipad
git add data/karpathy/nba-best-config.json data/karpathy/nba-history.json
git commit -m "karpathy(nba): new best Brier $(python3 -c "import json; cfg=json.load(open('data/karpathy/nba-best-config.json')); print(f\"{cfg['best_brier']:.5f}\")")"
```

---

## PHASE 5 — LOG

Append one entry to `data/karpathy/iteration-log.jsonl`:

```bash
cd /home/termius/mon-ipad
python3 -c "
import json, sys
from pathlib import Path
from datetime import datetime, timezone

# Read current state
cfg = json.loads(Path('data/karpathy/nba-best-config.json').read_text())
h = json.loads(Path('data/karpathy/nba-history.json').read_text())

# Get last batch of iterations from this session
session_iters = [x for x in h[-5:]]
session_improved = [x for x in session_iters if x.get('improved')]

record = {
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'domain': 'nba',
    'session_iterations': len(session_iters),
    'session_improvements': len(session_improved),
    'mutation_tried': session_iters[-1]['mutation'] if session_iters else 'unknown',
    'metric_after': round(cfg.get('best_brier', 1.0), 6),
    'decision': 'KEEP' if session_improved else 'REVERT',
    'model_type': cfg.get('model_type', 'unknown'),
    'n_features': cfg.get('n_features', 0),
    'n_estimators': cfg.get('n_estimators', 0),
    'reasoning': 'Karpathy loop iteration — see nba-history.json for per-mutation detail'
}

log_path = Path('data/karpathy/iteration-log.jsonl')
log_path.parent.mkdir(parents=True, exist_ok=True)
with open(log_path, 'a') as f:
    f.write(json.dumps(record) + '\n')

print('Logged:', json.dumps(record, indent=2))
"
```

---

## PHASE 6 — REPORT

Output a structured summary:

```
## Karpathy Loop — [DOMAIN] — [TIMESTAMP]

**Phase**: SCAN → PROPOSE → EXECUTE → EVALUATE → LOG

### Metrics
| Metric | Value |
|--------|-------|
| Domain | nba / political / betting / calibration |
| Brier before | X.XXXXX |
| Brier after (best config) | X.XXXXX |
| Delta | ±0.XXXXX |
| Decision | KEEP / REVERT |
| Session iterations | N |
| Session improvements | N/M |

### Mutation tried
- **Type**: change_model / change_n_estimators / etc.
- **Description**: [exact mutation from history]
- **Rationale**: [why this was chosen]

### No-improve streak (before session)
N iterations without improvement → [if >= 5: "Local minimum suspected — used diversity move"]

### Config state
- Model: [model_type]
- Features: [n_features]
- n_estimators: [n]
- max_depth: [d]
- Best Brier ever: [best_brier]

### Next recommended mutation
Based on the outcome, suggest ONE specific next mutation to try in the next `/karpathy-loop` call.

### Target gap
Current best: X.XXXXX | Target: 0.20000 | Gap: 0.XXXXX
```

If the iteration produced a new all-time best (below 0.19097 for NBA), add:

```
NEW ALL-TIME BEST: X.XXXXX — commit pushed
```

---

## Constraints and rules

1. **ZERO ML training on VM beyond this skill** — The iteration engine already caps to CPU_TRAIN_GAMES=4000, CPU_VAL_GAMES=200. Never increase these on VM.
2. **5-minute execution cap** — Run max 5 iterations per call (`--iterations 5`). For longer runs, use Kaggle or GitHub Actions.
3. **One mutation at a time** — Never propose multi-param mutations. The engine does this internally.
4. **Measure before claiming** — Never say "this should help" without running brier_proxy.py before and after.
5. **Domain parity** — The `political` domain uses the same iteration engine and same evaluation framework. Just different data and config files.
6. **Feature indices are opaque** — Never display the full `feature_indices` array. It's up to 200 integers. Always strip it from display.
7. **MAX_FEATURES=200** — Hard cap. Never propose mutations that exceed 200 features.
8. **CPU-only on VM** — No neural models, no stacking, no CatBoost (requires GPU for speed). Allowed: random_forest, extra_trees, gradient_boosting, lightgbm.

---

## Key files reference

| File | Purpose |
|------|---------|
| `data/karpathy/nba-best-config.json` | Current best NBA model config |
| `data/karpathy/political-best-config.json` | Current best political model config |
| `data/karpathy/nba-history.json` | Per-iteration history (JSON array) |
| `data/karpathy/political-history.json` | Per-iteration history for political |
| `data/karpathy/iteration-log.jsonl` | Rich session log (JSONL, one record per `/karpathy-loop` call) |
| `scripts/karpathy/nba_iterate.py` | NBA iteration engine |
| `scripts/karpathy/political_iterate.py` | Political iteration engine |
| `scripts/karpathy/karpathy_utils.py` | Shared mutation/eval/logging utilities |
| `scripts/karpathy/run_karpathy.sh` | CLI runner for iteration engine |
| `scripts/brier_proxy.py` | Fast Brier proxy (reads live backtest data) |
| `data/arena/cpcv-gated-strategies.json` | CPCV-validated bet strategies (betting domain) |
| `data/monitoring/drift-calibration.json` | Calibration metrics (calibration domain) |

---

## Mutation type → when to use

| Mutation | Best when |
|----------|-----------|
| `change_model` | Stuck for 5+ iterations, current model saturated |
| `change_n_estimators` | Current model good but possibly underfitting (too few trees) or overfitting (too many) |
| `change_max_depth` | Model too complex (high variance) or too simple (high bias) |
| `change_min_samples_leaf` | Calibration is off, or model overfitting |
| `change_max_features_ratio` | Feature redundancy suspected, or diversity needed |
| `add_features` | Feature count < 50, or recent feature removals hurt performance |
| `remove_features` | Feature count > 150, noise suspected |
| `swap_features` | Stuck in local minimum, want diversity without changing count |
