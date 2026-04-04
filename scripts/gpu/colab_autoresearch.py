#!/usr/bin/env python3
"""
Google Colab T4 GPU — Karpathy Autoresearch Launcher
=====================================================
Copy this into a Colab notebook cell and run.

Session: 12h | GPU: T4 16GB | All 15 model types
Targets: moneyline + spread + total (3 targets)
Review agent: analyzes each 5-min iteration

Colab Secrets needed (via Colab sidebar):
  - HF_TOKEN: HuggingFace token
  - DATABASE_URL: Supabase connection string
"""

# Cell 1: Setup
import os

# Mount Google Drive for persistent checkpoints
from google.colab import drive
drive.mount('/content/drive')

# Set environment from Colab secrets
try:
    from google.colab import userdata
    os.environ["HF_TOKEN"] = userdata.get("HF_TOKEN")
    os.environ["DATABASE_URL"] = userdata.get("DATABASE_URL")
except Exception:
    print("Set HF_TOKEN and DATABASE_URL in Colab secrets sidebar")

HF_TOKEN = os.environ.get("HF_TOKEN", "")

# Clone feature engine
os.system(f"git clone --depth 1 https://user:{HF_TOKEN}@huggingface.co/spaces/Nomos42/nba-quant /content/nba-quant-space")

# Cell 2: Run autoresearch
import sys
sys.path.insert(0, "/content/nba-quant-space")
sys.path.insert(0, "/content/nba-quant-space/scripts/gpu")

from karpathy_gpu_autoresearch import run_autoresearch
run_autoresearch()
