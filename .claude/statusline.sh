#!/bin/bash
# NBA Quant AI — Claude Code status line
input=$(cat)
MODEL=$(echo "$input" | jq -r '.model.display_name // "?"')
PCT=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)
COST=$(echo "$input" | jq -r '.cost.total_cost_usd // 0')

# Context bar with color
if [ "$PCT" -ge 90 ]; then CLR='\033[31m'
elif [ "$PCT" -ge 70 ]; then CLR='\033[33m'
else CLR='\033[32m'; fi
RST='\033[0m'

FILLED=$((PCT / 10)); EMPTY=$((10 - FILLED))
BAR=""
for ((i=0; i<FILLED; i++)); do BAR+="█"; done
for ((i=0; i<EMPTY; i++)); do BAR+="░"; done

COST_FMT=$(printf '%.2f' "$COST")
echo -e "${CLR}${BAR}${RST} ${PCT}% | \$${COST_FMT} | ${MODEL} | 🏀 Nomos42"
