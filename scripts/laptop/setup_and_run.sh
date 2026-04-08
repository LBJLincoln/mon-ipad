#!/bin/bash
# Combined setup + start script for laptop evolution node
# Designed to run via nohup to survive SSH disconnects
# Usage: nohup bash /home/nomos/nomos42-evo/setup_and_run.sh > /home/nomos/nomos42-evo/setup.log 2>&1 &

WORK_DIR="/home/nomos/nomos42-evo"
LOG="$WORK_DIR/setup.log"

echo "$(date): Starting laptop node setup..." | tee -a "$LOG"

# Step 1: System deps
echo "$(date): [1/5] System deps..." | tee -a "$LOG"
sudo apt-get update -qq 2>&1 | tail -1
sudo apt-get install -y -qq python3-pip python3-venv git curl 2>&1 | tail -1

# Step 2: Venv
echo "$(date): [2/5] Python venv..." | tee -a "$LOG"
if [ ! -d "$WORK_DIR/venv" ]; then
    python3 -m venv "$WORK_DIR/venv"
fi
source "$WORK_DIR/venv/bin/activate"

# Step 3: ML packages
echo "$(date): [3/5] Installing ML packages..." | tee -a "$LOG"
pip install --upgrade pip -q 2>&1 | tail -1
pip install -q numpy scikit-learn xgboost lightgbm catboost nba_api psycopg2-binary requests 2>&1 | tail -5

# Step 4: Verify
echo "$(date): [4/5] Verifying..." | tee -a "$LOG"
python3 -c "
import numpy, sklearn, xgboost, lightgbm, catboost
print(f'numpy={numpy.__version__} sklearn={sklearn.__version__} xgb={xgboost.__version__} lgbm={lightgbm.__version__} cat={catboost.__version__}')
print('ALL OK')
" 2>&1 | tee -a "$LOG"

echo "$(date): [5/5] Setup complete!" | tee -a "$LOG"

# Step 5: Mark ready
touch "$WORK_DIR/.setup_done"
echo "READY" > "$WORK_DIR/.status"
