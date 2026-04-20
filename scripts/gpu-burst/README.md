# GPU Burst Scripts

Short, intense GPU sessions following the Karpathy autoresearch pattern.
Each script is self-contained and designed for a specific GPU platform.

> Updated 2026-04-20 after the 2026-04-17 cull — 11 evolution islands remain
> (6 NBA + 5 POL). Eliminated (DO NOT re-reference): S10, S11, S12, S16, S19, S20, S21, P3, P6, P8.

## Pattern

Every burst script follows the same 7-step pattern:

1. **Clone/Pull** -- Get latest code from a surviving HF Space (feature engine + data)
2. **Seed** -- Load best configs from all 6 NBA survivor islands (S13/S14/S15/S17/S18/S22)
3. **Evolve** -- Run genetic algorithm with GPU-accelerated tree models
4. **Measure** -- Walk-forward Brier score (NBA) or signal accuracy (Political)
5. **Push if improved** -- Commit result to GitHub + update HF Space config
6. **Discard if not** -- Log failure, no side effects
7. **Shutdown** -- Exit immediately when time budget is reached

## Scripts

### colab-nba-burst.py (Colab T4, 30 min)
```
# In Google Colab:
# 1. Enable GPU runtime (T4)
# 2. Add secrets: HF_TOKEN, GITHUB_TOKEN
# 3. Upload and run:
!python colab-nba-burst.py
```
- Seeds from 6 HF islands
- GPU-accelerated XGBoost, CatBoost, LightGBM
- CPU fallback for ExtraTrees, RandomForest
- 30 min evolution burst
- Pushes to GitHub + updates S10 if improved

### kaggle-nba-burst.py (Kaggle P100, 30 min)
```
# In Kaggle notebook:
# 1. Enable GPU (P100)
# 2. Add secrets: HF_TOKEN, GITHUB_TOKEN
# 3. Enable internet
# 4. Paste as cell or upload as utility script
```
- Same evolution engine as Colab
- Kaggle-specific paths (/kaggle/working/)
- Auto-loads secrets from Kaggle UserSecretsClient
- Saves results to Kaggle output (persists after session)

### lightning-burst.py (Lightning AI T4/A10G, 10 min)
```
# In Lightning AI Studio:
export BURST_MODE=nba          # or "political"
export HF_TOKEN=your_token
export GITHUB_TOKEN=your_token
python lightning-burst.py
```
- Dual mode: NBA (Brier) or Political (signal accuracy)
- Set mode via BURST_MODE env var
- Smaller population (20) for 10 min burst
- Auto-detects GPU availability

### modal-burst.py (Modal A10G/A100, 10 min)
```
# From local machine:
modal run scripts/gpu-burst/modal-burst.py                # A10G, 10 min
modal run scripts/gpu-burst/modal-burst.py --gpu a100     # A100
modal run scripts/gpu-burst/modal-burst.py --timeout 300  # 5 min
modal run scripts/gpu-burst/modal-burst.py::check_status  # Check results
```
- Serverless GPU -- no idle cost
- Persistent Volume for feature cache (survives between runs)
- A10G: ~$0.18/burst | A100: ~$0.62/burst
- Build cache once, reuse across sessions

## Required Secrets

| Secret | Used By | Purpose |
|--------|---------|---------|
| HF_TOKEN | All | Clone HF Space (feature engine + data) |
| GITHUB_TOKEN | All | Push results to GitHub repo |
| DATABASE_URL | All (optional) | Load game data from Supabase if no local JSON |
| TELEGRAM_BOT_TOKEN | All (optional) | Send alerts on improvement |
| ADMIN_TELEGRAM_ID | All (optional) | Telegram chat for alerts |

## HF Evolution Islands — NBA Survivors (6, post-2026-04-17 cull)

| Island | URL | Specialization | Best Brier |
|--------|-----|----------------|------------|
| S13 | nomos42-nba-evo-4.hf.space | CatBoost specialist | 0.22749 |
| S14 | nomos42-nba-evo-5.hf.space | LightGBM specialist | 0.22186 |
| S15 | nomos42-nba-evo-6.hf.space | Wide search (pop=50) | 0.22418 |
| S17 | lbjlincoln26-nba-evo-s17.hf.space | Ensemble (LBJLincoln26) | 0.22340 |
| S18 | testforge42-nba-evo-s18.hf.space | CatBoost spec (TESTforge42) | 0.22114 |
| S22 | testforge42-nba-evo-s22.hf.space | Venn-Abers fusion — **FLEET BEST** | 0.22073 |

## HF Evolution Islands — Political Survivors (5)

| Island | URL | Specialization | Best Brier |
|--------|-----|----------------|------------|
| P1 | nomos42-political-alpha.hf.space | XGBoost | 0.24996 |
| P2 | nomos42-political-alpha-2.hf.space | LightGBM | 0.25223 |
| P4 | lbjlincoln-political-alpha-4.hf.space | Logistic | 0.25146 |
| P5 | lbjlincoln-political-alpha-5.hf.space | CatBoost | 0.25347 |
| P7 | lbjlincoln-political-alpha-7.hf.space | Gradient boost — **POL BEST** | 0.24987 |

**Eliminated 2026-04-17 (DO NOT restart, slots repurposed for selfhost LLMs):**
S10, S11, S12, S16, S19, S20, S21, P3, P6, P8.

## Evolution Engine

All scripts share the same core genetic algorithm:

- **Population**: 20-30 individuals (feature mask + model type + hyperparams)
- **Selection**: Tournament with 20% elite preservation
- **Crossover**: Uniform (0.80 rate) on feature masks + HP inheritance
- **Mutation**: Feature flips (0.09 rate) + HP perturbation (20%) + model swap (25%)
- **Evaluation**: Walk-forward 2-fold TimeSeriesSplit, Brier score
- **Diversity**: Auto-injection when top-10 becomes monoculture (>70% same model)
- **Adaptive mutation**: Increases on stagnation (15+ iters), decreases on improvement
- **Feature cap**: MAX_FEATURES=200 enforced in init/mutate/crossover

## Models (GPU-accelerated)

| Model | GPU | Typical Speed |
|-------|-----|--------------|
| XGBoost | CUDA hist | Fast |
| XGBoost (Brier obj) | CUDA hist | Fast |
| CatBoost | GPU | Medium |
| LightGBM | GPU | Medium |
| ExtraTrees | CPU (n_jobs=-1) | Medium |
| RandomForest | CPU (n_jobs=-1) | Medium |

## Cost Estimates

| Platform | GPU | Time | Cost |
|----------|-----|------|------|
| Colab | T4 | 30 min | Free |
| Kaggle | P100 | 30 min | Free (30h/week quota) |
| Lightning | T4 | 10 min | Free tier |
| Lightning | A10G | 10 min | ~$0.20 |
| Modal | A10G | 10 min | ~$0.18 |
| Modal | A100 | 10 min | ~$0.62 |

## Flow

```
HF Islands (6 NBA survivors: S13/S14/S15/S17/S18/S22)
    |
    v (seed best configs)
GPU Burst Script
    |
    ├── Evolve population (genetic algorithm)
    ├── Walk-forward Brier evaluation
    ├── Adaptive mutation + diversity injection
    |
    v
Improved?
    ├── YES -> Push to GitHub + Update HF Space + Telegram alert
    └── NO  -> Log failure, discard, exit
```
