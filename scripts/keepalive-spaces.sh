#!/bin/bash
# Keepalive for HF Spaces — prevents auto-sleep on free tier
# Called by cron: */30 * * * *
# 7 active evolution islands — all on Nomos42 account

TS=$(date -u +"%Y-%m-%d %H:%M UTC")
echo "=== Keepalive $TS ==="

# Load HF tokens from env file
if [ -f "/home/termius/mon-ipad/.env.local" ]; then
    source /home/termius/mon-ipad/.env.local 2>/dev/null
fi

# ── Helper: ping space + restart via HF API if 503 ────────────────────────────
# Usage: ping_or_restart <label> <url> <hf_space_id>
# hf_space_id format: "owner/repo-name" e.g. "Nomos42/political-alpha-3"
# Tries all available HF tokens in order until one returns 200 from restart API.
# NOTE: restart requires a token with write access to the space owner account.
#   Nomos42 spaces need the Nomos42 account token (HF_TOKEN_3).
#   If all tokens return 403, the tokens may need to be refreshed in .env.local.
ping_or_restart() {
    local label="$1"
    local url="$2"
    local space_id="$3"

    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null)
    echo "$label: $code"

    if [ "$code" = "503" ] && [ -n "$space_id" ]; then
        echo "  [RESTART] $label returned 503 — triggering HF restart..."
        # Try all tokens in order: HF_TOKEN_3 (Nomos42), HF_TOKEN (LBJLincoln), HF_TOKEN_2
        for tok in "${HF_TOKEN_3}" "${HF_TOKEN}" "${HF_TOKEN_2}"; do
            [ -z "$tok" ] && continue
            restart_resp=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
                "https://huggingface.co/api/spaces/${space_id}/restart" \
                -H "Authorization: Bearer ${tok}" \
                --max-time 15 2>/dev/null)
            echo "  [RESTART] $label restart API: $restart_resp"
            if [ "$restart_resp" = "200" ] || [ "$restart_resp" = "204" ]; then
                echo "  [RESTART] $label restart triggered successfully"
                break
            fi
        done
    fi
}

# NBA Evolution Islands (6) — hosted under Nomos42 account
ping_or_restart "S10 (exploit)"     https://nomos42-nba-quant.hf.space/    "Nomos42/nba-quant"
ping_or_restart "S11 (explore)"     https://nomos42-nba-quant-2.hf.space/  "Nomos42/nba-quant-2"
ping_or_restart "S12 (extra_trees)" https://nomos42-nba-evo-3.hf.space/    "Nomos42/nba-evo-3"
ping_or_restart "S13 (catboost)"    https://nomos42-nba-evo-4.hf.space/    "Nomos42/nba-evo-4"
ping_or_restart "S14 (lightgbm)"    https://nomos42-nba-evo-5.hf.space/    "Nomos42/nba-evo-5"
ping_or_restart "S15 (wide)"        https://nomos42-nba-evo-6.hf.space/    "Nomos42/nba-evo-6"

# Political Alpha Evolution (4 islands) — hosted under Nomos42 account
ping_or_restart "P1 (exploit)"  https://nomos42-political-alpha.hf.space/   "Nomos42/political-alpha"
ping_or_restart "P2 (explore)"  https://nomos42-political-alpha-2.hf.space/ "Nomos42/political-alpha-2"
ping_or_restart "P3 (catboost)" https://nomos42-political-alpha-3.hf.space/ "Nomos42/political-alpha-3"
ping_or_restart "P4 (wide)"     https://nomos42-political-alpha-4.hf.space/ "Nomos42/political-alpha-4"
