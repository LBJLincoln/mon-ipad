# NBA QUANT AI — COMPUTE RULES

> **Last updated:** 2026-03-16
> **Applies to:** ALL repos (mon-ipad, nomos-nba-agent, rag-website, rag-dashboard)

## RULE #1: ZERO ML ON VM

The VM (`34.136.180.66`) has **1 vCPU / 969 MB RAM / 30 GB disk**.

**It CANNOT and MUST NOT run any ML workload.** Every time we try, OOM kills the process.

### What RUNS on VM (ONLY these):
| Process | Script | RAM | Purpose |
|---------|--------|-----|---------|
| nba-data-server | `scripts/nba-data-server.py` | ~12 MB | Serve JSON to Vercel website |
| nba-quant-daemon | `ops/nba-quant-daemon.py` | ~20 MB | Lightweight orchestration only |
| Claude Code | Termius session | ~100 MB | Pilotage, git, deployment |
| System monitoring | `ops/monitor.py` | ~15 MB | Health checks |

### What RUNS on HF Spaces (ALL ML):
| Process | Space | RAM Avail | Purpose |
|---------|-------|-----------|---------|
| Karpathy training loop | nomos-nba-quant (S10) | 16 GB | Full model training, Optuna, calibration |
| Parallel training | nomos-nba-quant-2 (S11) | 16 GB | Second parallel training instance |
| Backtest | S10 or S11 | 16 GB | Walk-forward backtesting |
| OddsHarvester | TBD (needs Playwright) | 16 GB | Live odds scraping |

### What SHOULD run on Lightning AI / Google Colab (GPU):
| Process | Platform | Purpose |
|---------|----------|---------|
| LSTM/Neural models | Lightning AI | GPU-accelerated deep learning |
| Large Optuna search | Google Colab | 100+ trial hyperparameter search |
| MC Dropout ensemble | Colab Pro | Uncertainty-aware predictions |

## RULE #2: ALL SPACES = FULL CREDENTIALS

Every HF Space MUST have ALL 101 env vars from `.env.local` set as secrets.

Script to sync:
```python
from huggingface_hub import HfApi
import os

api = HfApi(token=os.environ['HF_TOKEN'])

with open('.env.local') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'): continue
        if line.startswith('export '): line = line[7:]
        if '=' in line:
            k, v = line.split('=', 1)
            api.add_space_secret('LBJLincoln/SPACE_NAME', k.strip(), v.strip().strip("'\""))
```

## RULE #3: DEPLOY SCRIPT

To update a Space's code:
```python
from huggingface_hub import HfApi
api = HfApi(token=os.environ['HF_TOKEN'])
api.upload_file(path_or_fileobj='app.py', path_in_repo='app.py',
                repo_id='LBJLincoln/nomos-nba-quant', repo_type='space')
```

## NBA HF Spaces
| Space | URL | Secrets | Status |
|-------|-----|---------|--------|
| nomos-nba-quant | lbjlincoln-nomos-nba-quant.hf.space | 101/101 | REBUILDING |
| nomos-nba-quant-2 | lbjlincoln-nomos-nba-quant-2.hf.space | 101/101 | BUILDING |

## HF Accounts
| Account | Token | Write Access |
|---------|-------|-------------|
| LBJLincoln | HF_TOKEN | Full (create spaces, upload, secrets) |
| lbjlincoln26 | HF_TOKEN_2 | Read-only (needs write token upgrade) |
