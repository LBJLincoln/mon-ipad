#!/bin/bash
# Kaggle GPU Runner Trigger — runs every 6 hours via cron
# Pushes the kernel to start a new GPU training session (50 experiments)
LOG="/home/termius/mon-ipad/logs/kaggle-trigger.log"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Triggering Kaggle GPU runner..." >> "$LOG"
kaggle kernels push -p /tmp/kaggle-kernel >> "$LOG" 2>&1
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Status: $(kaggle kernels status alexismoret6/nba-quant-gpu-runner 2>&1)" >> "$LOG"
