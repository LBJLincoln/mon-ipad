#!/bin/bash
# ============================================================
# Deploy evolution worker to the laptop (native Ubuntu)
# ============================================================
# Usage:
#   bash scripts/laptop/deploy_to_laptop.sh
#
# Env overrides:
#   LAPTOP=laptop          SSH alias (configured in ~/.ssh/config)
#                          or user@ip if no alias is set
#   WORK_DIR=/home/nomos/nomos42-evo
# ============================================================
set -euo pipefail

LAPTOP="${LAPTOP:-laptop}"
WORK_DIR="${WORK_DIR:-/home/nomos/nomos42-evo}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================="
echo " Deploying Laptop Evolution Worker"
echo " Target: $LAPTOP:$WORK_DIR"
echo "========================================="

# Step 1: Create directory structure
echo "[1/4] Creating directories on laptop..."
ssh -o ConnectTimeout=20 "$LAPTOP" \
    "mkdir -p $WORK_DIR/features $WORK_DIR/data $WORK_DIR/checkpoints $WORK_DIR/results"

# Step 2: Copy scripts directly (no Windows hop)
echo "[2/4] Copying worker scripts..."
scp -o ConnectTimeout=20 \
    "$SCRIPT_DIR/setup_laptop_node.sh" \
    "$SCRIPT_DIR/laptop_evolution_worker.py" \
    "$LAPTOP:$WORK_DIR/"

ssh -o ConnectTimeout=20 "$LAPTOP" "chmod +x $WORK_DIR/setup_laptop_node.sh"

# Step 3: Copy feature engine from this repo
echo "[3/4] Copying feature engine..."
FEATURE_ENGINE="$(cd "$SCRIPT_DIR"/../../hf-space/features 2>/dev/null && pwd)/engine.py"
if [ -f "$FEATURE_ENGINE" ]; then
    scp -o ConnectTimeout=20 "$FEATURE_ENGINE" "$LAPTOP:$WORK_DIR/features/engine.py"
    INIT_FILE="$(dirname "$FEATURE_ENGINE")/__init__.py"
    if [ -f "$INIT_FILE" ]; then
        scp -o ConnectTimeout=20 "$INIT_FILE" "$LAPTOP:$WORK_DIR/features/__init__.py"
    else
        ssh -o ConnectTimeout=20 "$LAPTOP" "touch $WORK_DIR/features/__init__.py"
    fi
    echo "Feature engine copied."
else
    echo "WARNING: Feature engine not found at $FEATURE_ENGINE"
    echo "Worker will try to clone from HF Space at runtime."
fi

# Step 4: Verify
echo "[4/4] Verifying..."
ssh -o ConnectTimeout=20 "$LAPTOP" "ls -la $WORK_DIR/ | head -20"

echo ""
echo "========================================="
echo " Deployment COMPLETE!"
echo ""
echo " Next steps:"
echo " 1. Run setup:  ssh $LAPTOP 'bash $WORK_DIR/setup_laptop_node.sh'"
echo " 2. Set env:    ssh $LAPTOP 'echo export HF_TOKEN=xxx >> ~/.bashrc'"
echo " 3. Start:      ssh $LAPTOP 'source $WORK_DIR/venv/bin/activate && python3 $WORK_DIR/laptop_evolution_worker.py'"
echo "========================================="
