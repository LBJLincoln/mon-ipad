#!/bin/bash
# Keepalive for HF Spaces — prevents auto-sleep on free tier
# Called by cron: */30 * * * *
# Only 2 active spaces: S10 (evolution) + S11 (experiments)

curl -s -o /dev/null -w "S10: %{http_code}\n" https://lbjlincoln-nomos-nba-quant.hf.space/ 2>/dev/null
curl -s -o /dev/null -w "S11: %{http_code}\n" https://lbjlincoln-nomos-nba-quant-2.hf.space/ 2>/dev/null
