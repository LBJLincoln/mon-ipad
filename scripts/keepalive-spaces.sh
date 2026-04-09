#!/bin/bash
# Keepalive for HF Spaces — prevents auto-sleep on free tier
# Called by cron: */30 * * * *
# 25 active spaces: 10 NBA + 4 Political + 9 Department Councils + 1 Pixel World (4 HF accounts)

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
        for tok in "${HF_TOKEN_3}" "${HF_TOKEN}" "${HF_TOKEN_2}" "${HF_TOKEN_FORGE:-}"; do
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

# NBA Evolution Islands S16-S19 (new — LBJLincoln26 + TESTforge42)
ping_or_restart "S16 (gradient)" https://lbjlincoln26-nba-evo-s16.hf.space/ "LBJLincoln26/nba-evo-s16"
ping_or_restart "S17 (ensemble)" https://lbjlincoln26-nba-evo-s17.hf.space/ "LBJLincoln26/nba-evo-s17"
ping_or_restart "S18 (cat_brier)" https://testforge42-nba-evo-s18.hf.space/ "TESTforge42/nba-evo-s18"
ping_or_restart "S19 (ultra_wide)" https://testforge42-nba-evo-s19.hf.space/ "TESTforge42/nba-evo-s19"

# Political Alpha Evolution (4 islands) — Nomos42 + LBJLincoln accounts
ping_or_restart "P1 (exploit)"  https://nomos42-political-alpha.hf.space/   "Nomos42/political-alpha"
ping_or_restart "P2 (explore)"  https://nomos42-political-alpha-2.hf.space/ "Nomos42/political-alpha-2"
ping_or_restart "P3 (political3)" https://lbjlincoln-political-alpha-3.hf.space/ "LBJLincoln/political-alpha-3"
ping_or_restart "P4 (political4)" https://lbjlincoln-political-alpha-4.hf.space/ "LBJLincoln/political-alpha-4"

# Department Council Spaces (9) — across 4 HF accounts
# LBJLincoln: D1, D2 | LBJLincoln26: D3, D4 | Nomos42: D5, D6 | TESTforge42: D7, D8, D9
ping_or_restart "D1 (research)"     https://lbjlincoln-nomos-dept-d1-research.hf.space/     "LBJLincoln/nomos-dept-d1-research"
ping_or_restart "D2 (engineering)"  https://lbjlincoln-nomos-dept-d2-engineering.hf.space/   "LBJLincoln/nomos-dept-d2-engineering"
ping_or_restart "D3 (evolution)"    https://lbjlincoln26-nomos-dept-d3-evolution.hf.space/   "LBJLincoln26/nomos-dept-d3-evolution"
ping_or_restart "D4 (product)"      https://lbjlincoln26-nomos-dept-d4-product.hf.space/     "LBJLincoln26/nomos-dept-d4-product"
ping_or_restart "D5 (business)"     https://nomos42-nomos-dept-d5-business.hf.space/         "Nomos42/nomos-dept-d5-business"
ping_or_restart "D6 (evaluation)"   https://nomos42-nomos-dept-d6-evaluation.hf.space/       "Nomos42/nomos-dept-d6-evaluation"
ping_or_restart "D7 (infra)"        https://testforge42-nomos-dept-d7-infra.hf.space/        "TESTforge42/nomos-dept-d7-infra"
ping_or_restart "D8 (finance)"      https://testforge42-nomos-dept-d8-finance.hf.space/      "TESTforge42/nomos-dept-d8-finance"
ping_or_restart "D9 (cross-repo)"   https://testforge42-nomos-dept-d9-cross-repo.hf.space/   "TESTforge42/nomos-dept-d9-cross-repo"
