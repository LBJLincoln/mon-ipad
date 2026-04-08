#!/usr/bin/env python3
"""
Lightning.ai H200 GPU — Karpathy Autoresearch Launcher
=======================================================
Run in Lightning AI studio.

Session: 22h | GPU: H200 80GB | All 15 model types
Targets: moneyline + spread + total (3 targets)
Review agent: analyzes each 5-min iteration

Lightning environment variables:
  - HF_TOKEN: set in studio secrets
  - DATABASE_URL: set in studio secrets
"""

import os, sys

# Lightning AI studio paths
WORK = "/teamspace/studios/nba-quant-gpu"
os.makedirs(WORK, exist_ok=True)

HF_TOKEN = os.environ.get("HF_TOKEN", "")

# Clone feature engine
REPO = f"{WORK}/nba-quant-space"
if not os.path.exists(REPO):
    os.system(f"git clone --depth 1 https://user:{HF_TOKEN}@huggingface.co/spaces/Nomos42/nba-quant {REPO}")

sys.path.insert(0, REPO)
sys.path.insert(0, f"{REPO}/scripts/gpu")

from karpathy_gpu_autoresearch import run_autoresearch
run_autoresearch()
