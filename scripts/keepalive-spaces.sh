#!/bin/bash
# Keepalive for HF Spaces — prevents auto-sleep on free tier
# Called by cron: */30 * * * *
# 33 active spaces: 10 NBA + 8 Political + 2 TF/Gateway + 9 Dept Councils + 2 TESTforge42 (4 HF accounts)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TS=$(date -u +"%Y-%m-%d %H:%M UTC")
echo "=== Keepalive $TS ==="

# Load HF tokens from env file
if [ -f "${ROOT}/.env.local" ]; then
    source "${ROOT}/.env.local" 2>/dev/null
fi

# ── Helper: ping space + restart via HF API if non-healthy ───────────────────
# Usage: ping_or_restart <label> <url> <hf_space_id>
# hf_space_id format: "owner/repo-name" e.g. "LBJLincoln/political-alpha-3"
# Tries all available HF tokens in order until one returns 200 from restart API.
# NOTE: restart requires a token with write access to the space owner account.
#   Nomos42 spaces → HF_TOKEN_LLM  |  LBJLincoln → HF_TOKEN  |  LBJLincoln26 → HF_TOKEN_NBA
#
# BUG FIX (cycle 82): was only restarting on 503. Added 502/404/000 (timeout).
# P3/P4 were returning timeout/404 and NEVER got restarted. Fixed.
ping_or_restart() {
    local label="$1"
    local url="$2"
    local space_id="$3"

    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 12 "$url" 2>/dev/null)
    [ -z "$code" ] && code="000"  # empty = timeout/DNS failure
    echo "$label: $code"

    # Restart triggers: 503 (sleeping), 502 (crashed), 000 (timeout), 404 (paused)
    # No restart: 200 (OK), 301/302 (redirect = healthy), 429 (rate limit — wait)
    local should_restart=0
    case "$code" in
        200|301|302|429) should_restart=0 ;;
        *)               should_restart=1 ;;
    esac

    if [ "$should_restart" = "1" ] && [ -n "$space_id" ]; then
        echo "  [RESTART] $label returned $code — triggering HF restart..."
        for tok in "${HF_TOKEN_LLM:-}" "${HF_TOKEN:-}" "${HF_TOKEN_NBA:-}" "${HF_TOKEN_COUNCILS:-}"; do
            [ -z "$tok" ] && continue
            restart_resp=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
                "https://huggingface.co/api/spaces/${space_id}/restart" \
                -H "Authorization: Bearer ${tok}" \
                --max-time 15 2>/dev/null)
            echo "  [RESTART] $label restart API → $restart_resp (tok: ${tok:0:10}...)"
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
ping_or_restart "P5 (catboost)"   https://lbjlincoln-political-alpha-5.hf.space/ "LBJLincoln/political-alpha-5"
ping_or_restart "P6 (extra_trees)" https://lbjlincoln-political-alpha-6.hf.space/ "LBJLincoln/political-alpha-6"
ping_or_restart "P7 (grad_boost)" https://lbjlincoln-political-alpha-7.hf.space/ "LBJLincoln/political-alpha-7"
ping_or_restart "P8 (ensemble)"   https://lbjlincoln-political-alpha-8.hf.space/ "LBJLincoln/political-alpha-8"

# Trading Floor + LLM Gateway (LBJLincoln26 account)
ping_or_restart "TF (trading)"  https://lbjlincoln26-nba-llm-trading-floor.hf.space/ "LBJLincoln26/nba-llm-trading-floor"
ping_or_restart "GW (gateway)"  https://lbjlincoln26-llm-gateway.hf.space/            "LBJLincoln26/llm-gateway"

# Department Council Spaces (9) — all consolidated on TESTforge42 (2026-04-15 Option B migration)
# TESTforge42: D1, D2, D3, D4, D5, D6, D7, D8, D9
ping_or_restart "D1 (research)"     https://testforge42-nomos-dept-d1-research.hf.space/     "TESTforge42/nomos-dept-d1-research"
ping_or_restart "D2 (engineering)"  https://testforge42-nomos-dept-d2-engineering.hf.space/   "TESTforge42/nomos-dept-d2-engineering"
ping_or_restart "D3 (evolution)"    https://testforge42-nomos-dept-d3-evolution.hf.space/   "TESTforge42/nomos-dept-d3-evolution"
ping_or_restart "D4 (product)"      https://testforge42-nomos-dept-d4-product.hf.space/     "TESTforge42/nomos-dept-d4-product"
ping_or_restart "D5 (business)"     https://testforge42-nomos-dept-d5-business.hf.space/         "TESTforge42/nomos-dept-d5-business"
ping_or_restart "D6 (evaluation)"   https://testforge42-nomos-dept-d6-evaluation.hf.space/       "TESTforge42/nomos-dept-d6-evaluation"
ping_or_restart "D7 (infra)"        https://testforge42-nomos-dept-d7-infra.hf.space/        "TESTforge42/nomos-dept-d7-infra"
ping_or_restart "D8 (finance)"      https://testforge42-nomos-dept-d8-finance.hf.space/      "TESTforge42/nomos-dept-d8-finance"
ping_or_restart "D9 (cross-repo)"   https://testforge42-nomos-dept-d9-cross-repo.hf.space/   "TESTforge42/nomos-dept-d9-cross-repo"
