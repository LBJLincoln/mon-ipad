#!/usr/bin/env python3
"""Check status of all Kaggle kernels."""
import subprocess

slugs = [
    "alexismoret6/nba-quant-gpu-v2-tabicl",
    "alexismoret6/nba-quant-gpu-evolution-v2",
    "alexismoret6/notebooka4ab689b97",
    "alexismoret6/notebookcecf15f786",
    "alexismoret6/nba-quant-gpu-v2",
]

for slug in slugs:
    r = subprocess.run(["kaggle", "kernels", "status", slug], capture_output=True, text=True)
    status = r.stdout.strip() if r.returncode == 0 else f"ERROR: {r.stdout.strip()}"
    print(f"{slug}: {status}")
