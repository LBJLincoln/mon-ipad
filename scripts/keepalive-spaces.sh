#!/bin/bash
# Keepalive for HF Spaces — prevents auto-sleep on free tier
# Called by cron: */30 * * * *
# 7 active evolution islands — all on Nomos42 account

TS=$(date -u +"%Y-%m-%d %H:%M UTC")
echo "=== Keepalive $TS ==="

# NBA Evolution Islands (6)
curl -s -o /dev/null -w "S10 (exploit): %{http_code}\n" --max-time 10 https://nomos42-nba-quant.hf.space/ 2>/dev/null
curl -s -o /dev/null -w "S11 (explore): %{http_code}\n" --max-time 10 https://nomos42-nba-quant-2.hf.space/ 2>/dev/null
curl -s -o /dev/null -w "S12 (extra_trees): %{http_code}\n" --max-time 10 https://nomos42-nba-evo-3.hf.space/ 2>/dev/null
curl -s -o /dev/null -w "S13 (catboost): %{http_code}\n" --max-time 10 https://nomos42-nba-evo-4.hf.space/ 2>/dev/null
curl -s -o /dev/null -w "S14 (lightgbm): %{http_code}\n" --max-time 10 https://nomos42-nba-evo-5.hf.space/ 2>/dev/null
curl -s -o /dev/null -w "S15 (wide): %{http_code}\n" --max-time 10 https://nomos42-nba-evo-6.hf.space/ 2>/dev/null

# Political Alpha Evolution (4 islands)
curl -s -o /dev/null -w "P1 (exploit): %{http_code}\n" --max-time 10 https://nomos42-political-alpha.hf.space/ 2>/dev/null
curl -s -o /dev/null -w "P2 (explore): %{http_code}\n" --max-time 10 https://nomos42-political-alpha-2.hf.space/ 2>/dev/null
curl -s -o /dev/null -w "P3 (catboost): %{http_code}\n" --max-time 10 https://nomos42-political-alpha-3.hf.space/ 2>/dev/null
curl -s -o /dev/null -w "P4 (wide): %{http_code}\n" --max-time 10 https://nomos42-political-alpha-4.hf.space/ 2>/dev/null
