#!/bin/bash
# Keepalive for HF Spaces — prevents auto-sleep on free tier
# Called by cron: */30 * * * *
# 6 active evolution islands — all on Nomos42 account

# Nomos42 account (S10-S13 migrated 2026-03-26)
curl -s -o /dev/null -w "S10 (exploit): %{http_code}\n" https://nomos42-nba-quant.hf.space/ 2>/dev/null
curl -s -o /dev/null -w "S11 (explore): %{http_code}\n" https://nomos42-nba-quant-2.hf.space/ 2>/dev/null
curl -s -o /dev/null -w "S12 (extra_trees): %{http_code}\n" https://nomos42-nba-evo-3.hf.space/ 2>/dev/null
curl -s -o /dev/null -w "S13 (catboost): %{http_code}\n" https://nomos42-nba-evo-4.hf.space/ 2>/dev/null
curl -s -o /dev/null -w "S14 (lightgbm): %{http_code}\n" https://nomos42-nba-evo-5.hf.space/ 2>/dev/null
curl -s -o /dev/null -w "S15 (wide): %{http_code}\n" https://nomos42-nba-evo-6.hf.space/ 2>/dev/null
