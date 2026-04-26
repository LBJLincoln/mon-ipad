#!/bin/bash
# Keepalive for HF Spaces — prevents auto-sleep on free tier
# Called by cron: */30 * * * *
# 22 active spaces: 6 NBA + 5 Political + 3 TF/Gateway + 7 CPU LLM + 1 Langfuse (4 HF accounts)
# Updated 2026-04-26: removed 10 eliminated islands (S10/S11/S12/S16/S19/S20/S21/P3/P6/P8)
# Those slots are now reserved for selfhost LLMs — do NOT re-add them.

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
# hf_space_id format: "owner/repo-name" e.g. "LBJLincoln/political-alpha-4"
# Tries all available HF tokens in order until one returns 200 from restart API.
# NOTE: restart requires a token with write access to the space owner account.
#   Nomos42 spaces → HF_TOKEN_LLM  |  LBJLincoln → HF_TOKEN  |  LBJLincoln26 → HF_TOKEN_NBA
#
# BUG FIX (cycle 82): was only restarting on 503. Added 502/404/000 (timeout).
# P3/P4 were returning timeout/404 and NEVER got restarted. Fixed.
pingorg_or_restart() {
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
        # 2026-04-19: PAUSED Spaces reject plain ?factory_reboot=false with 403.
        # Try factory_reboot=true first (handles both SLEEPING and PAUSED stages).
        for tok in "${HF_TOKEN_LLM:-}" "${HF_TOKEN:-}" "${HF_TOKEN_NBA:-}" "${HF_TOKEN_COUNCILS:-}"; do
            [ -z "$tok" ] && continue
            restart_resp=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
                "https://huggingface.co/api/spaces/${space_id}/restart?factory=true" \
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

# Alias to match original function name used throughout
ping_or_restart() { pingorg_or_restart "$@"; }

# ── NBA Evolution Islands SURVIVORS (6) ──────────────────────────────────────
# ELIMINATED (DO NOT ADD BACK): S10/nba-quant, S11/nba-quant-2, S12/nba-evo-3
#   S16/nba-evo-s16, S19/nba-evo-s19, S20/nba-evo-s20, S21/nba-evo-s21
#   Those HF slots are now used by selfhost LLMs.
ping_or_restart "S13 (xgboost)"   https://nomos42-nba-evo-4.hf.space/          "Nomos42/nba-evo-4"
ping_or_restart "S14 (rf)"        https://nomos42-nba-evo-5.hf.space/          "Nomos42/nba-evo-5"
ping_or_restart "S15 (et200f)"    https://nomos42-nba-evo-6.hf.space/          "Nomos42/nba-evo-6"
ping_or_restart "S17 (xgboost)"   https://lbjlincoln26-nba-evo-s17.hf.space/   "LBJLincoln26/nba-evo-s17"
ping_or_restart "S18 (et)"        https://testforge42-nba-evo-s18.hf.space/    "TESTforge42/nba-evo-s18"
ping_or_restart "S22 (et)"        https://testforge42-nba-evo-s22.hf.space/    "TESTforge42/nba-evo-s22"

# ── Political Alpha SURVIVORS (5) ────────────────────────────────────────────
# ELIMINATED (DO NOT ADD BACK): P3/political-alpha-3, P6/political-alpha-6, P8/political-alpha-8
ping_or_restart "P1 (catboost)"   https://nomos42-political-alpha.hf.space/    "Nomos42/political-alpha"
ping_or_restart "P2 (lightgbm)"   https://nomos42-political-alpha-2.hf.space/  "Nomos42/political-alpha-2"
ping_or_restart "P4 (xgb_brier)"  https://lbjlincoln-political-alpha-4.hf.space/ "LBJLincoln/political-alpha-4"
ping_or_restart "P5 (catboost)"   https://lbjlincoln-political-alpha-5.hf.space/ "LBJLincoln/political-alpha-5"
ping_or_restart "P7 (logistic)"   https://lbjlincoln-political-alpha-7.hf.space/ "LBJLincoln/political-alpha-7"

# ── Trading Floors + LLM Gateway (LBJLincoln26) ──────────────────────────────
ping_or_restart "TF-NBA"       https://lbjlincoln26-nba-llm-trading-floor.hf.space/        "LBJLincoln26/nba-llm-trading-floor"
ping_or_restart "TF-Political" https://lbjlincoln26-political-llm-trading-floor.hf.space/  "LBJLincoln26/political-llm-trading-floor"
ping_or_restart "GW (gateway)" https://lbjlincoln26-llm-gateway.hf.space/                  "LBJLincoln26/llm-gateway"

# ── v2.9 (Apr 17): TF experiment auto-resume ──────────────────────────────
# Space may return 200 (UI alive) but experiment loop `running=false` (crashed, completed,
# or never started post-restart). Ping /api/status — if running=false, POST /api/run.
pingorg_or_resume_experiment() {
    local label="$1"
    local base_url="$2"
    local status_json
    status_json=$(curl -s --max-time 10 "${base_url}/api/status" 2>/dev/null)
    [ -z "$status_json" ] && { echo "$label exp-status: no response"; return; }
    local running
    running=$(echo "$status_json" | grep -oE '"running"[[:space:]]*:[[:space:]]*(true|false)' | head -1 | grep -oE 'true|false')
    [ -z "$running" ] && running="unknown"
    local calls
    calls=$(echo "$status_json" | grep -oE '"(total_llm_calls|llm_calls)"[[:space:]]*:[[:space:]]*[0-9]+' | head -1 | grep -oE '[0-9]+$')
    echo "  $label experiment: running=$running calls=${calls:-0}"
    if [ "$running" = "false" ]; then
        echo "  [RESUME] $label experiment stopped — POSTing /api/run..."
        resume_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST --max-time 15 \
            -H "Content-Type: application/json" -d '{}' "${base_url}/api/run" 2>/dev/null)
        echo "  [RESUME] $label /api/run → $resume_code"
    fi
}

pingorg_or_resume_experiment "TF-NBA"       "https://lbjlincoln26-nba-llm-trading-floor.hf.space"
pingorg_or_resume_experiment "TF-Political" "https://lbjlincoln26-political-llm-trading-floor.hf.space"

# ── CPU LLM backends (Nomos42) — 7 slots ────────────────────────────────────
ping_or_restart "LLM-Phi4mini"   https://nomos42-nomos42-llm-cpu.hf.space/    "Nomos42/nomos42-llm-cpu"
ping_or_restart "LLM-Qwen3-4B"   https://nomos42-qwen3-4b-cpu.hf.space/       "Nomos42/qwen3-4b-cpu"
ping_or_restart "LLM-SmolLM3"    https://nomos42-smollm3-3b-cpu.hf.space/     "Nomos42/smollm3-3b-cpu"
ping_or_restart "LLM-Qwen3-0.6B" https://nomos42-qwen25-05b-cpu.hf.space/     "Nomos42/qwen25-05b-cpu"
ping_or_restart "LLM-Dolphin3L3" https://nomos42-llama32-1b-cpu.hf.space/     "Nomos42/llama32-1b-cpu"
ping_or_restart "LLM-Gemma4-E2B" https://nomos42-gemma2-2b-cpu.hf.space/      "Nomos42/gemma2-2b-cpu"
ping_or_restart "LLM-CpuGemma4"  https://nomos42-nomos-cpu-gemma4.hf.space/   "Nomos42/nomos-cpu-gemma4"

# ── Observability ────────────────────────────────────────────────────────────
ping_or_restart "Langfuse"       https://nomos42-langfuse.hf.space/            "Nomos42/langfuse"

# Dept Councils (D1-D9) — DECOMMISSIONED 2026-04-20, Spaces deleted. DO NOT re-add.
