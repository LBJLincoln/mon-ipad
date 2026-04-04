#!/bin/bash
# Deploy evolution worker to the laptop
# Usage: bash scripts/laptop/deploy_to_laptop.sh

set -e

LAPTOP="laptop"  # SSH alias from ~/.ssh/config
WSL_CMD='C:\Windows\system32\wsl.exe'
WSL_USER="nomos"
WORK_DIR="/home/nomos/nomos42-evo"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================="
echo " Deploying Laptop Evolution Worker"
echo "========================================="

# Step 1: Create directory structure via Windows SSH -> WSL
echo "[1/4] Creating directories on laptop WSL..."
ssh -o ConnectTimeout=20 "$LAPTOP" "$WSL_CMD -d Ubuntu -e mkdir -p $WORK_DIR/features $WORK_DIR/data $WORK_DIR/checkpoints $WORK_DIR/results"

# Step 2: Copy files to Windows temp, then move to WSL
echo "[2/4] Copying scripts to laptop..."
# Upload to Windows user dir first (scp works with Windows OpenSSH)
scp -o ConnectTimeout=20 "$SCRIPT_DIR/setup_laptop_node.sh" "$LAPTOP:C:/Users/aurel/setup_laptop_node.sh"
scp -o ConnectTimeout=20 "$SCRIPT_DIR/laptop_evolution_worker.py" "$LAPTOP:C:/Users/aurel/laptop_evolution_worker.py"

# Step 3: Move from Windows to WSL
echo "[3/4] Moving files into WSL..."
ssh -o ConnectTimeout=20 "$LAPTOP" "$WSL_CMD -d Ubuntu -e bash -c \"cp /mnt/c/Users/aurel/setup_laptop_node.sh $WORK_DIR/ && cp /mnt/c/Users/aurel/laptop_evolution_worker.py $WORK_DIR/ && chmod +x $WORK_DIR/setup_laptop_node.sh\""

# Step 4: Copy feature engine from this repo
echo "[4/4] Copying feature engine..."
FEATURE_ENGINE="$(cd "$(dirname "$0")"/../../hf-space/features && pwd)/engine.py"
if [ -f "$FEATURE_ENGINE" ]; then
    scp -o ConnectTimeout=20 "$FEATURE_ENGINE" "$LAPTOP:C:/Users/aurel/engine.py"
    ssh -o ConnectTimeout=20 "$LAPTOP" "$WSL_CMD -d Ubuntu -e bash -c \"cp /mnt/c/Users/aurel/engine.py $WORK_DIR/features/engine.py\""
    # Also copy __init__.py if it exists
    INIT_FILE="$(dirname "$FEATURE_ENGINE")/__init__.py"
    if [ -f "$INIT_FILE" ]; then
        scp -o ConnectTimeout=20 "$INIT_FILE" "$LAPTOP:C:/Users/aurel/features_init.py"
        ssh -o ConnectTimeout=20 "$LAPTOP" "$WSL_CMD -d Ubuntu -e bash -c \"cp /mnt/c/Users/aurel/features_init.py $WORK_DIR/features/__init__.py\""
    else
        ssh -o ConnectTimeout=20 "$LAPTOP" "$WSL_CMD -d Ubuntu -e bash -c \"touch $WORK_DIR/features/__init__.py\""
    fi
    echo "Feature engine copied."
else
    echo "WARNING: Feature engine not found at $FEATURE_ENGINE"
    echo "Worker will try to clone from HF Space at runtime."
fi

echo ""
echo "========================================="
echo " Deployment COMPLETE!"
echo ""
echo " Next steps (on laptop):"
echo " 1. Run setup:  ssh laptop \"$WSL_CMD -d Ubuntu -e bash $WORK_DIR/setup_laptop_node.sh\""
echo " 2. Set env:    ssh laptop \"$WSL_CMD -d Ubuntu -e bash -c 'echo export HF_TOKEN=xxx >> ~/.bashrc'\""
echo " 3. Start:      ssh laptop \"$WSL_CMD -d Ubuntu -e bash -c 'source $WORK_DIR/venv/bin/activate && python3 $WORK_DIR/laptop_evolution_worker.py'\""
echo "========================================="
