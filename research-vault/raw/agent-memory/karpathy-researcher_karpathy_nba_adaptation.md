---
name: Karpathy Autoresearch Pattern — NBA Prediction Adaptation
description: Exact code template for adapting 5-minute GPU iterate loop to NBA genetic algorithm evolution with Brier score
type: reference
---

# Karpathy Autoresearch for NBA Prediction

**Goal:** Adapt Karpathy's "5-minute GPU iterate" pattern to NBA Quant AI evolution
**Metric:** Brier score (lower is better, 0.22041 current best)
**Loop rate:** 12-24 experiments/hour on Kaggle GPU
**Expected improvement:** 0.001-0.005 Brier per 100 experiments

---

## Three-File Architecture (NBA Version)

### 1. `evolve_train.py` — THE MODIFIABLE FILE
Agent modifies genetic algorithm hyperparameters, feature count, model types, mutation/crossover rates.

```python
# evolve_train.py — agent edits this
import numpy as np
import pandas as pd
from deap import base, creator, tools, algorithms
from xgboost import XGBClassifier
from catboost import CatBoostClassifier
import time

# CONFIGURATION — agent modifies these values
CONFIG = {
    'population_size': 60,      # agent tunes: 30-100
    'generations': 50,          # agent tunes: 20-100
    'mutation_rate': 0.09,      # agent tunes: 0.05-0.20
    'crossover_rate': 0.80,     # agent tunes: 0.60-0.95
    'max_features': 63,         # agent tunes: 40-150
    'model_type': 'xgboost',    # agent tunes: 'xgboost', 'catboost', 'lightgbm'
    'learning_rate': 0.1,       # agent tunes per model_type
}

def evaluate_individual(individual):
    """Fitness: negative Brier (we minimize)"""
    # individual = list of feature indices
    features = [i for i, selected in enumerate(individual) if selected][:CONFIG['max_features']]

    if len(features) == 0:
        return (1.0,)  # Worst fitness

    # Load data (cached)
    X_train = pd.read_csv('data/X_train.csv')
    y_train = pd.read_csv('data/y_train.csv').values.ravel()
    X_val = pd.read_csv('data/X_val.csv')
    y_val = pd.read_csv('data/y_val.csv').values.ravel()

    X_train_subset = X_train.iloc[:, features]
    X_val_subset = X_val.iloc[:, features]

    # Train model
    if CONFIG['model_type'] == 'xgboost':
        model = XGBClassifier(
            max_depth=6,
            learning_rate=CONFIG['learning_rate'],
            n_estimators=200,
            eval_metric='logloss'
        )
    else:
        model = CatBoostClassifier(
            depth=6,
            learning_rate=CONFIG['learning_rate'],
            iterations=200,
            verbose=0
        )

    model.fit(X_train_subset, y_train, eval_set=[(X_val_subset, y_val)], verbose=0)

    # Evaluate: Brier score
    y_pred_proba = model.predict_proba(X_val_subset)[:, 1]
    brier = np.mean((y_pred_proba - y_val) ** 2)

    return (brier,)  # Return as tuple for DEAP

def run_evolution():
    """5-minute evolution with early stopping"""
    creator.create("FitnessMin", base.Fitness, weights=(-1.0,))  # minimize
    creator.create("Individual", list, fitness=creator.FitnessMin)

    toolbox = base.Toolbox()
    toolbox.register("attr_bool", np.random.choice, [0, 1], p=[0.7, 0.3])
    toolbox.register("individual", tools.initRepeat, creator.Individual,
                     toolbox.attr_bool, n=200)  # 200 features total
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    toolbox.register("evaluate", evaluate_individual)
    toolbox.register("mate", tools.cxBlend, alpha=0.5)
    toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=0.2, indpb=CONFIG['mutation_rate'])
    toolbox.register("select", tools.selTournament, tournsize=3)

    pop = toolbox.population(n=CONFIG['population_size'])
    hof = tools.HallOfFame(1)

    start_time = time.time()
    budget_seconds = 300  # 5 minutes

    gen = 0
    while time.time() - start_time < budget_seconds:
        # Evaluate population
        fitnesses = list(map(toolbox.evaluate, pop))
        for ind, fit in zip(pop, fitnesses):
            ind.fitness.values = fit

        # Select + breed
        offspring = toolbox.select(pop, len(pop))
        offspring = [toolbox.clone(ind) for ind in offspring]

        for child1, child2 in zip(offspring[::2], offspring[1::2]):
            if np.random.random() < CONFIG['crossover_rate']:
                toolbox.mate(child1, child2)
                del child1.fitness.values
                del child2.fitness.values

        for mutant in offspring:
            if np.random.random() < CONFIG['mutation_rate']:
                toolbox.mutate(mutant)
                del mutant.fitness.values

        pop[:] = offspring
        hof.update(pop)

        gen += 1

    return hof[0], hof[0].fitness.values[0], gen

if __name__ == '__main__':
    best_ind, best_brier, generations = run_evolution()
    print(f"Best Brier: {best_brier:.6f}")
    print(f"Generations completed: {generations}")
    print(f"Config: {CONFIG}")

    # Save result for comparison
    import json
    with open('result.json', 'w') as f:
        json.dump({
            'brier': best_brier,
            'generations': generations,
            'config': CONFIG
        }, f)
```

### 2. `prepare_nba.py` — IMMUTABLE EVALUATION
Read-only. Agent cannot touch.

```python
# prepare_nba.py — LOCKED, agent cannot modify
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

def prepare_data():
    """Fixed data prep, one-time call"""
    # Load historical NBA games
    games = pd.read_csv('data/raw_games.csv')

    # Feature engineering (FIXED)
    X = games[['elo_diff', 'pace', 'home_trend', ...]].values
    y = games['home_win'].values

    # Split (FIXED)
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Standardize (FIXED)
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val = scaler.transform(X_val)

    # Save (one-time)
    pd.DataFrame(X_train).to_csv('data/X_train.csv', index=False)
    pd.DataFrame(X_val).to_csv('data/X_val.csv', index=False)
    pd.DataFrame(y_train).to_csv('data/y_train.csv', index=False, header=['target'])
    pd.DataFrame(y_val).to_csv('data/y_val.csv', index=False, header=['target'])

if __name__ == '__main__':
    prepare_data()
```

### 3. `program_nba.md` — AGENT INSTRUCTIONS

```markdown
# Research Program: Optimize NBA Prediction Brier Score

## Goal
Minimize Brier score on validation set using genetic algorithm, 5-minute budget per generation.

## Current Baseline
- Best Brier: 0.22041 (S10, xgboost, 63 features)
- Configuration: mut=0.09, cx=0.80, pop=60

## Constraints
- Only modify evolve_train.py CONFIG section
- Brier MUST improve to commit
- Max 150 features (hardware limit)
- 5-minute strict time budget

## Tuning Strategy (Priority)

### Phase 1: Mutation Rate (Days 1-2)
Test values: 0.05, 0.07, 0.09, 0.12, 0.15, 0.18, 0.20
Hypothesis: 0.10-0.12 might beat current 0.09

### Phase 2: Crossover Rate (Days 3-4)
Test values: 0.60, 0.70, 0.80, 0.85, 0.90
Current: 0.80. Test if 0.75 is optimum.

### Phase 3: Population Size (Days 5-6)
Test: 40, 50, 60, 80, 100
Hypothesis: larger pop might find better features

### Phase 4: Model Type (Days 7-8)
Test: xgboost, catboost, lightgbm with tuned hyperparams
Current: xgboost wins. Verify catboost isn't better.

### Phase 5: Learning Rate Tuning
Per model type. Test: 0.05, 0.1, 0.2

## Prior Experiments
- mut=0.15: 80% success rate improving
- mut=0.20: only 40% success (too aggressive)
- pop=100: 15% slower, no Brier benefit
- catboost: 0.2% worse than xgboost (consistent across runs)

## Red Flags / Stopping Points
- If Brier stays flat >20 runs: program may be stalled
- If any run takes >6 min: configuration is invalid
- If Brier jumps >0.01 worse: revert CONFIG to baseline

## Success Criteria
- Reach Brier < 0.219 (beat S10 by 0.001)
- Maintain <5 min per generation
- Document winning configuration
```

---

## The Autonomous Loop (NBA Version)

```
BASELINE (Brier 0.22041)
  |
  v
AGENT READS program_nba.md + evolve_train.py
  |
  v
HYPOTHESIS: "mutation 0.11 might beat 0.09, per Phase 1 testing"
  |
  v
EDIT evolve_train.py: mutation_rate = 0.11
  |
  v
RUN: python evolve_train.py (5 minutes max)
  └─> Runs 20-30 generations
  └─> Evaluates ~600 individuals
  └─> Outputs result.json: {'brier': 0.21995, 'generations': 25, 'config': {...}}
  |
  v
EVALUATE: new_brier (0.21995) vs baseline (0.22041)
  |
  ├─ IMPROVED? (0.21995 < 0.22041)
  │   └─> git commit "Phase 1-3: mut=0.11, improved to 0.21995"
  │       └─> UPDATE baseline to 0.21995
  │           └─> LOOP
  │
  └─ NOT IMPROVED?
      └─> git reset --hard
          └─> LOOP with different hypothesis
```

---

## Agent Decision Logic (Pseudocode)

```python
def agent_loop_nba():
    while True:
        # Read current state
        history = load_jsonl('experiments.jsonl')  # all past experiments
        config = json.load(open('baseline.json'))  # current best CONFIG
        program = read_file('program_nba.md')

        # Query Claude to form hypothesis
        hypothesis = agent.query({
            'task': 'Optimize NBA Brier score, 5-min evolution budget',
            'program': program,
            'baseline_config': config,
            'baseline_brier': config['brier'],
            'history': history[-20:],  # Last 20 experiments
            'request': 'Suggest ONE parameter change to test next. Explain hypothesis.'
        })
        # Example response:
        # {
        #   'change': 'mutation_rate: 0.09 → 0.11',
        #   'reason': 'Phase 1 strategy. Current is conservative. Literature suggests 0.10-0.13 often optimal.',
        #   'expected_improvement': '+0.0005 Brier',
        #   'code_change': "CONFIG['mutation_rate'] = 0.11"
        # }

        # Apply change
        apply_change_to_evolve_train(hypothesis['code_change'])

        # Run evolution
        run_cmd('python evolve_train.py')
        result = json.load(open('result.json'))
        new_brier = result['brier']

        # Decide
        if new_brier < config['brier']:
            # Keep it
            git_commit(f"{hypothesis['reason']}")
            config['brier'] = new_brier
            config['config'] = result['config']
            json.dump(config, open('baseline.json', 'w'))
            log(f"IMPROVED: {hypothesis['change']} → Brier {new_brier:.6f}")
        else:
            # Discard
            git_reset_hard()
            log(f"Not improved: {hypothesis['change']} → Brier {new_brier:.6f}")

        # Log experiment
        experiments.append({
            'hypothesis': hypothesis,
            'result_brier': new_brier,
            'improved': new_brier < config['brier'],
            'timestamp': datetime.now().isoformat()
        })
        save_jsonl(experiments, 'experiments.jsonl')
```

---

## Metric: Why Brier Score?

### Definition
```
Brier = mean((predicted_prob - actual_label)^2)

For binary classification:
  - prediction ∈ [0, 1] (probability home team wins)
  - actual ∈ {0, 1} (did home team win?)
  - lower is better
  - 0.25 (random) is baseline
  - 0.20 is excellent
```

### Why it's perfect for this pattern:
- ✓ Single number (0.20041)
- ✓ Lower is better
- ✓ Computed automatically
- ✓ Fair comparison (any architecture)
- ✓ Matches your 10-year calibration research
- ✓ Already in Supabase as metric

---

## Expected Performance

### Overnight Run (Kaggle Free: 30 hr/week)
- Budget: 5 min per generation
- Rate: 12 generations/hour = 12 experiments/hour
- Overnight (8 hours): 96 experiments

### Expected Improvement Curve
```
Generation  Best Brier  Delta      Hypothesis
1           0.22041     baseline   Start
10          0.21998     -0.00043   mutation tuning
25          0.21925     -0.00116   crossover tuning
50          0.21847     -0.00194   population size
100         0.21750     -0.00291   model type test
...
Target      0.21500     -0.00541   (achievable?)
```

**Conservative estimate:** 0.001-0.005 improvement per 100 experiments

---

## Deployment on Kaggle Kernel

### Setup
```bash
# 1. Create Kaggle notebook with GPU
kaggle kernels init -c my-nba-evolution

# 2. Create kernel structure
mkdir -p kaggle/nba_evolution/{scripts,data}
cp evolve_train.py kaggle/nba_evolution/
cp prepare_nba.py kaggle/nba_evolution/
cp program_nba.md kaggle/nba_evolution/

# 3. Upload to Kaggle
kaggle kernels push -p kaggle/nba_evolution

# 4. Kernel runs on schedule, pulls baseline from git
```

### Loop Integration
```bash
# In autonomous-cycle.sh (runs every 4h)
if [[ "$KAGGLE_AVAILABLE" == "true" ]]; then
    # Check if new Brier improvement available from Kaggle
    kaggle kernels output Nomos42/nba-evolution -p /tmp/kaggle_out
    if [[ -f /tmp/kaggle_out/baseline.json ]]; then
        new_brier=$(jq '.brier' /tmp/kaggle_out/baseline.json)
        if [[ $(echo "$new_brier < $CURRENT_BRIER" | bc) -eq 1 ]]; then
            # Improved! Pull config, update HF Spaces
            cp /tmp/kaggle_out/* data/
            git add data/
            git commit -m "Kaggle evolution: improved to $new_brier"
            push_to_spaces
        fi
    fi
fi
```

---

## Comparison to Current Approach

| Aspect | Current (HF Spaces) | Karpathy Pattern (This) |
|--------|-------------------|------------------------|
| GPU | CPU-only (limited) | Single H100/T4 |
| Iteration rate | ~1 gen/10min | 12 gens/hour |
| Metric | implicit in code | explicit Brier |
| Decision logic | human-guided | autonomous agent |
| Overnight scale | ~50 gens | ~100 gens |
| Config tuning | manual | hypothesis-driven |
| Resume | robust | git-based |

---

## Next Steps

1. **Copy template:** Use `evolve_train.py` structure above
2. **Define prepare_nba.py:** Lock data prep, evaluation
3. **Write program_nba.md:** Guide agent research direction
4. **Test locally:** Run one evolution cycle, verify Brier computation
5. **Deploy to Kaggle:** Push kernel, enable GPU
6. **Monitor:** Watch baseline.json for improvements
7. **Iterate program.md:** As agent finds patterns, adjust strategy

