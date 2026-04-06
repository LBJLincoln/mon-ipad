---
name: Karpathy Autoresearch Pattern — 5-Minute GPU Iterate Loop
description: Complete technical specification of Karpathy's autonomous research pattern (agent + code + metric + loop), with exact code patterns and design principles for adaptation to NBA/political prediction evolution
type: reference
---

# Karpathy Autoresearch Pattern: 5-Minute GPU Iterate Loop

**Source:** https://github.com/karpathy/autoresearch (Official Karpathy repo, March 2026)
**Pattern:** AI agent autonomously experiments on single GPU, 100 experiments overnight
**Metric:** val_bpb (validation bits per byte), lower is better
**Scale:** 12 experiments/hour, ~100/night on single H100

---

## Three-File Architecture (CRITICAL)

### 1. `train.py` — THE MODIFIABLE FILE
- Contains: Full GPT model + optimizer (Muon + AdamW) + training loop
- Everything is fair game: architecture, hyperparams, batch size, optimizer choices
- **ONLY FILE** agent modifies
- Stripped down from nanochat, ~300 lines
- No evaluation logic inside
- Focuses on training trajectory, not metric scoring

**Pattern:**
```python
# train.py — agent modifies this
import torch
from prepare import evaluate_bpb, get_dataloader, get_tokenizer, get_model

model = get_model()
optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4)

for step in range(max_steps):
    X, Y = next(train_loader)
    logits = model(X)
    loss = F.cross_entropy(logits.reshape(-1, vocab_size), Y.reshape(-1))
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    optimizer.step()
    optimizer.zero_grad()

    # Checkpoint for eval
    if step == final_step:
        torch.save(model.state_dict(), 'ckpt.pt')

# Agent CAN modify:
# - model depth, width, attention heads
# - learning rate, schedule, warmup
# - batch size, gradient accumulation
# - optimizer type (Muon vs AdamW vs hybrid)
# - activation functions, layer norms
```

### 2. `prepare.py` — IMMUTABLE EVALUATION HARNESS
- Contains: Data prep, tokenizer, dataloader, evaluation function
- **READ-ONLY** — agent cannot touch this
- Ensures all improvements are genuine, not eval gaming
- Checksum validation prevents tampering

**Key function:**
```python
def evaluate_bpb(model, tokenizer, batch_size):
    """
    Compute val_bpb = total_nats / (log(2) * total_bytes)
    Lower is better. Vocab-size-independent.
    """
    model.eval()
    total_nats = 0.0
    total_bytes = 0.0

    for X, Y in get_val_dataloader(batch_size):
        logits = model(X)
        # Compute cross-entropy in nats (natural log)
        loss = F.cross_entropy(logits.reshape(-1, vocab_size), Y.reshape(-1))
        total_nats += loss.item() * X.shape[0]
        total_bytes += count_utf8_bytes(X, tokenizer)

    val_bpb = total_nats / (math.log(2) * total_bytes)
    return val_bpb
```

### 3. `program.md` — AGENT INSTRUCTIONS (HUMAN EDITABLE)
- Written in natural language (Markdown)
- Defines research strategy, goals, constraints
- Agent reads this at loop startup
- Human iterates on this to improve agent's direction

**Example structure:**
```markdown
# Research Program: Optimize LLM Training for Speed

## Goal
Minimize val_bpb on OpenWebText using single H100 GPU, 5-minute budget.

## Constraints
- Only modify train.py
- val_bpb MUST improve to commit change
- No external libraries beyond PyTorch

## Strategy (Priority Order)
1. Optimizer tuning: test Muon, AdamW, hybrid schedules
2. Architecture: test depths 12-24, widths 512-2048
3. Attention: test multi-head variants, flash attention
4. Data loading: test batch sizes 32-512, gradient accumulation

## Prior Near-Misses
- Depth 20 was close (0.247 bpb) but too slow
- Flash attention gave 2% speedup, consider combining with schedules

## Research Questions
- Does layer norm placement matter?
- Can we beat xformers with pure PyTorch?
```

---

## The Autonomous Loop (CORE PATTERN)

### Cycle Structure: Hypothesis → Modify → Measure → Decide → Loop

```
START
  |
  v
READ program.md + current train.py
  |
  v
AGENT FORMS HYPOTHESIS
  (e.g., "Depth 18 with warmup might beat depth 20")
  |
  v
EDIT train.py (single change, minimal diff)
  |
  v
RUN TRAINING (wall-clock 5 minutes, no timeout variation)
  |
  v
CALL evaluate_bpb() → measure val_bpb
  |
  v
COMPARE new_val_bpb vs baseline_val_bpb
  |
  ├─ IMPROVED? (lower val_bpb)
  │   └─> git commit "Hypothesis X: improved to Y"
  │       └─> NEW BASELINE = this checkpoint
  │           └─> LOOP (back to AGENT FORMS HYPOTHESIS)
  │
  └─ NOT IMPROVED? (same or worse val_bpb)
      └─> git reset --hard baseline
          └─> DISCARD CHANGE
              └─> LOOP (back to AGENT FORMS HYPOTHESIS)
```

### Key Timing Constraints

- **Training window:** Exactly 5 minutes (wall clock)
  - Does NOT include startup, compilation, data loading
  - Agent has fixed budget regardless of GPU type
  - Means smaller experiments, higher iteration velocity

- **Evaluation:** ~30 seconds on H100
  - val_bpb computed on held-out validation split
  - Must complete before next hypothesis

- **Expected rate:** 12 experiments/hour, ~100/night

### Git-Based Ratcheting Mechanism

```bash
# Start of experiment
git add -A
git commit -m "Baseline: depth 20, val_bpb=0.2450"

# Agent makes change
# Edits train.py directly

# Run experiment
python train.py  # 5 minutes
new_bpb = evaluate_bpb()

# Decision
if new_bpb < baseline_bpb:
    git add train.py
    git commit -m "Improved: depth 18+warmup, val_bpb=0.2413"
    baseline_bpb = new_bpb
else:
    git reset --hard HEAD  # Revert to last commit
    # try again with different hypothesis
```

---

## Critical Success Requirements (3 Rules)

### 1. Single, Unambiguous Metric
- **Must be a number**
- **Lower is better** (or clearly defined direction)
- **Computed automatically** (no human judgment)
- **Vocab-size-independent** (fair comparison across architectures)

Examples:
- ✓ val_bpb (bits per byte) — lower is better
- ✓ Brier score — lower is better
- ✓ AUROC — higher is better
- ✗ "Model quality" (vague)
- ✗ "Feels faster" (subjective)

### 2. Automated Evaluation
- No human in loop between experiments
- Scoring runs programmatically
- Results logged/committed to git
- Enables overnight autonomous runs

### 3. Single Modifiable File
- Agent edits ONE file per round (e.g., train.py, SKILL.md, features.yaml)
- Everything else is read-only
- Makes diffs clear, changes reviewable
- Keeps scope manageable

---

## Exact Code Patterns for Adaptation

### Pattern 1: Time Budget Wrapper
```python
import time
import signal

def timeout_handler(signum, frame):
    raise TimeoutError("Budget exceeded")

def run_with_budget(budget_seconds=300):
    """Run training with exact time budget (5 min = 300 sec)"""
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(budget_seconds)

    try:
        # Train loop — can be interrupted
        for step in range(max_steps):
            batch = next(dataloader)
            loss = forward_backward(batch)
            optimizer.step()
            # Will be killed by SIGALRM after 300 sec
    except TimeoutError:
        # Normal termination, checkpoint current model
        torch.save(model.state_dict(), 'final_ckpt.pt')
```

### Pattern 2: Metric Tracking & Comparison
```python
import json

def track_experiment(hypothesis_name, new_val_bpb):
    """Log result and compare to baseline"""
    with open('baseline.json', 'r') as f:
        baseline_data = json.load(f)

    baseline_bpb = baseline_data['val_bpb']
    improved = new_val_bpb < baseline_bpb
    delta = new_val_bpb - baseline_bpb

    result = {
        'hypothesis': hypothesis_name,
        'new_val_bpb': new_val_bpb,
        'baseline_bpb': baseline_bpb,
        'improved': improved,
        'delta': delta,
        'timestamp': datetime.now().isoformat()
    }

    with open('experiments.jsonl', 'a') as f:
        f.write(json.dumps(result) + '\n')

    return improved

if __name__ == '__main__':
    # Train...
    model = load_last_checkpoint()
    val_bpb = evaluate_bpb(model)

    if track_experiment('hypothesis_X', val_bpb)['improved']:
        # Save as new baseline
        torch.save(model.state_dict(), 'best_ckpt.pt')
        with open('baseline.json', 'w') as f:
            json.dump({'val_bpb': val_bpb}, f)
```

### Pattern 3: Checkpoint Resume
```python
import os

def get_or_create_model():
    """Load from best checkpoint, or initialize"""
    best_ckpt = 'best_ckpt.pt'
    if os.path.exists(best_ckpt):
        model = GPT()
        model.load_state_dict(torch.load(best_ckpt))
        print(f"Resumed from {best_ckpt}")
    else:
        model = GPT()
        print("Initialized fresh model")
    return model

model = get_or_create_model()
optimizer = torch.optim.AdamW(model.parameters())
# Train for 5 minutes, checkpoint again
```

### Pattern 4: Agent Decision Loop (Pseudocode)
```python
def agent_loop():
    """
    Autonomous agent: reads code → hypothesis → modify → measure → decide
    """
    while True:
        # Read state
        current_code = read_file('train.py')
        baseline = json.load(open('baseline.json'))
        history = load_jsonl('experiments.jsonl')

        # Agent forms hypothesis (via Claude/LLM)
        hypothesis = agent.query({
            'task': 'Optimize val_bpb on 5-min budget',
            'current_train_py': current_code,
            'baseline': baseline,
            'history': history[-10:],  # Last 10 experiments
            'program': read_file('program.md')
        })
        # hypothesis = {'change': 'depth: 20 → 18', 'reason': '...', 'code_diff': '...'}

        # Make change
        apply_diff(hypothesis['code_diff'], 'train.py')

        # Run & measure
        run_training(budget_sec=300)
        val_bpb = evaluate_bpb()

        # Decide
        if val_bpb < baseline['val_bpb']:
            # Keep it
            git_commit(f"Improved: {hypothesis['reason']}")
            update_baseline(val_bpb)
        else:
            # Discard
            git_reset_hard()
            log(f"Not improved: {hypothesis['reason']}")
```

---

## Metric Design: The val_bpb Approach

### Why val_bpb?
- **Vocabulary-size-independent**: Comparing depth 20 vs depth 18, different embedding dims—fair comparison
- **Information-theoretic**: Bits per byte captured by model's distribution
- **Single number**: 0.245 better than 0.250, clear comparison
- **Automated**: Computed from validation data, no subjectivity

### Formula
```
val_bpb = total_nats / (ln(2) * total_bytes)

where:
  total_nats = sum of cross-entropy losses (natural log)
  total_bytes = sum of UTF-8 byte lengths in validation set
  ln(2) = 0.693 (converts natural log to log₂)
```

### For NBA Prediction Adaptation
Replace val_bpb with **Brier score** (calibration metric, lower is better):
```python
def evaluate_brier(model, test_X, test_Y):
    """
    Brier = mean((predicted_prob - actual_label)^2)
    Lower is better.
    Vocab-size-independent analog: any architecture can be compared fairly.
    """
    predictions = model.predict_proba(test_X)  # shape (n, 2)
    home_probs = predictions[:, 1]
    brier = np.mean((home_probs - test_Y) ** 2)
    return brier
```

---

## Leaderboard & Benchmarking

### nanochat GPT-2 Speedrun Leaderboard
- **Metric:** Wall-clock time to reach GPT-2 (DCLM CORE score)
- **Best:** ~1.65 hours on 8×H100
- **Benchmark:** Reproduce GPT-2 (124M) on OpenWebText

**Adapted for NBA:**
- **Metric:** Wall-clock time to reach Brier < 0.22
- **Benchmark:** Beat S10 best (Brier 0.22041)
- **GPU:** H100 or equivalent
- **Budget:** 5 minutes per experiment

---

## Universal Applicability (Non-LLM Domains)

Karpathy explicitly states this pattern works for "anything you can score":

| Domain | File | Metric | Modifiable |
|--------|------|--------|-----------|
| LLM training | train.py | val_bpb | architecture, hyperparams |
| NBA prediction | features.py / GA_config.yaml | Brier score | feature selection, GA params |
| Political alpha | model_config.yaml | accuracy / ROI | tree depth, ensemble weights |
| Email templates | prompt.md | click-through rate | phrasing, structure |
| Website UX | layout.html | conversion rate | button placement, colors |

**Key insight:** The loop works whenever:
1. You can score output as a number
2. You can automate the scoring
3. You can modify one file/config

---

## Deployment on Kaggle GPU

### Kaggle Kernel + Autoresearch Pattern
```bash
# 1. Push train_nba.py to Kaggle (modified train.py equivalent)
kaggle kernels push -p kaggle/nba_evolution

# 2. Kernel auto-runs on Kaggle GPU (P100/T4)
# 3. After 5 min: output metrics to CSV
# 4. Download results, evaluate Brier
# 5. If improved: git commit, push new version
# 6. Loop repeats

# Expected: 24-30 experiments/day on free Kaggle (30hr/week)
```

---

## References

- **GitHub:** https://github.com/karpathy/autoresearch
- **nanochat:** https://github.com/karpathy/nanochat
- **Karpathy Profile:** https://github.com/karpathy
- **Blog Post:** http://karpathy.github.io/2026/02/12/microgpt/
- **Analysis:** [Karpathy Just Turned One GPU Into a Research Lab](https://garryslist.org/posts/karpathy-just-turned-one-gpu-into-a-research-lab-f55754a6)
- **Pattern Guide:** [autoresearch: Karpathy's Blueprint for Agents That Improve Themselves](https://www.mager.co/blog/2026-03-14-autoresearch-pattern/)

