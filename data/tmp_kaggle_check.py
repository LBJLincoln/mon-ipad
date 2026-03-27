#!/usr/bin/env python3
"""Quick Kaggle status check."""
import subprocess

# List kernels
r = subprocess.run(["kaggle", "kernels", "list", "--mine"], capture_output=True, text=True)
print("=== LIST KERNELS ===")
print("STDOUT:", r.stdout[:800])
print("STDERR:", r.stderr[:400])
print("RC:", r.returncode)
print()

# Check specific kernel status
r2 = subprocess.run(["kaggle", "kernels", "status", "alexismoret6/nba-quant-gpu-v2"], capture_output=True, text=True)
print("=== KERNEL STATUS ===")
print("STDOUT:", r2.stdout[:400])
print("STDERR:", r2.stderr[:400])
print("RC:", r2.returncode)
