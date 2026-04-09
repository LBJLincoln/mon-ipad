#!/usr/bin/env python3
"""
Kaggle P100 GPU — Karpathy Autoresearch Launcher
=================================================
Copy this into a Kaggle notebook cell and run.

Session: 9h | GPU: P100 16GB | All 15 model types
Targets: moneyline + spread + total (3 targets)
Review agent: analyzes each 5-min iteration

Kaggle Secrets needed:
  - HF_TOKEN: HuggingFace token (for cloning feature engine)
  - DATABASE_URL: Supabase connection string (for game data)
"""

# Cell 1: Clone the autoresearch script
import os
os.system("pip install -q huggingface_hub")

from huggingface_hub import hf_hub_download
HF_TOKEN = os.environ.get("HF_TOKEN", "")

# Clone latest autoresearch from our repo
os.system(f"git clone --depth 1 https://user:{HF_TOKEN}@huggingface.co/spaces/Nomos42/nba-quant /kaggle/working/nba-quant-space")

# Cell 2: Run the autoresearch loop
import sys
sys.path.insert(0, "/kaggle/working")

# The main script auto-detects Kaggle platform
exec(open("/kaggle/working/nba-quant-space/scripts/gpu/karpathy_gpu_autoresearch.py").read())

# Or if script is uploaded directly:
# from karpathy_gpu_autoresearch import run_autoresearch
# run_autoresearch()
