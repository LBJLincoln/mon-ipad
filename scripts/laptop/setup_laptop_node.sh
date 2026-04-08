#!/bin/bash
# Laptop Compute Node Setup — Nomos42 NBA Quant AI
# Run this ONCE on the WSL Ubuntu to set up the evolution environment.
# Usage (from VM): ssh laptop 'C:\Windows\system32\wsl.exe -d Ubuntu -e bash /home/nomos/setup_laptop_node.sh'

set -e

echo "========================================="
echo " Nomos42 Laptop Compute Node — Setup"
echo "========================================="

WORK_DIR="/home/nomos/nomos42-evo"
mkdir -p "$WORK_DIR"

# System deps
echo "[1/5] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip python3-venv git curl > /dev/null 2>&1

# Python venv
echo "[2/5] Creating Python virtual environment..."
if [ ! -d "$WORK_DIR/venv" ]; then
    python3 -m venv "$WORK_DIR/venv"
fi
source "$WORK_DIR/venv/bin/activate"

# ML packages (CPU only — lightweight)
echo "[3/5] Installing ML packages (CPU only)..."
pip install --upgrade pip -q
pip install -q \
    numpy>=2.0 \
    scikit-learn>=1.5 \
    xgboost>=3.0 \
    lightgbm>=4.0 \
    catboost>=1.2 \
    nba_api>=1.4 \
    psycopg2-binary>=2.9 \
    requests>=2.31

echo "[4/5] Verifying installation..."
python3 -c "
import numpy as np
import sklearn
import xgboost
import lightgbm
import catboost
print(f'NumPy {np.__version__}')
print(f'scikit-learn {sklearn.__version__}')
print(f'XGBoost {xgboost.__version__}')
print(f'LightGBM {lightgbm.__version__}')
print(f'CatBoost {catboost.__version__}')
print('All ML packages OK!')
"

# Create directories
echo "[5/5] Creating work directories..."
mkdir -p "$WORK_DIR/data"
mkdir -p "$WORK_DIR/checkpoints"
mkdir -p "$WORK_DIR/results"
mkdir -p "$WORK_DIR/features"

echo ""
echo "========================================="
echo " Setup COMPLETE!"
echo " Work dir: $WORK_DIR"
echo " Activate: source $WORK_DIR/venv/bin/activate"
echo "========================================="
