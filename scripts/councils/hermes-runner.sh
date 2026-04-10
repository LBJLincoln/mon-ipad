#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# HERMES COUNCIL RUNNER — Real Claude Code CLI Agents per Department
# ═══════════════════════════════════════════════════════════════
# Replaces ALL old council systems:
#   - trading-floor-council-loop.sh (DEAD)
#   - department-council.sh (DEAD)
#   - monitor-only JSON councils (DEAD)
#
# Each department gets a real Claude Code CLI agent that:
#   1. Reads department program.md (mission, metrics, search space)
#   2. Scans current state (data files, git, HF spaces)
#   3. Proposes + executes ONE improvement (5 min budget)
#   4. Measures result
#   5. Keeps if better, reverts if worse
#   6. Commits with department-specific message
#
# Pattern from: Gemini PDF "Adapting Output for Claude Code CLI"
# Architecture from: Grok Proposal "NOMOS42: QUANT REALMS"
#
# Usage:
#   ./hermes-runner.sh                    # Run ALL departments
#   ./hermes-runner.sh d1                 # Run single department
#   ./hermes-runner.sh d1 d3 d7           # Run specific departments
#   ./hermes-runner.sh --status           # Show last run status
#
# Cron (every 4 hours, staggered):
#   0  2,10,18 * * * /home/lahargnedebartoli/mon-ipad/scripts/councils/hermes-runner.sh d1 d3 d7
#   0  4,12,20 * * * /home/lahargnedebartoli/mon-ipad/scripts/councils/hermes-runner.sh d2 d6 d9
#   0  6,14,22 * * * /home/lahargnedebartoli/mon-ipad/scripts/councils/hermes-runner.sh d4 d5 d8
# ═══════════════════════════════════════════════════════════════

set -uo pipefail

ROOT="/home/lahargnedebartoli/mon-ipad"
PROMPTS_DIR="${ROOT}/scripts/councils/prompts"
LOG_DIR="${ROOT}/logs/councils"
DATA_DIR="${ROOT}/data/departments"
TODAY=$(date -u +"%Y-%m-%d")
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

mkdir -p "${LOG_DIR}" "${DATA_DIR}"

# Load env
[[ -f "${ROOT}/.env.local" ]] && set -a && source "${ROOT}/.env.local" 2>/dev/null && set +a

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${CYAN}[HERMES]${NC} $(date -u +%H:%M:%S) $*"; }
ok()  { echo -e "${GREEN}[HERMES]${NC} $(date -u +%H:%M:%S) ✓ $*"; }
err() { echo -e "${RED}[HERMES]${NC} $(date -u +%H:%M:%S) ✗ $*"; }

# ═══════════════════════════════════════════════════════════════
# DEPARTMENT DEFINITIONS
# ═══════════════════════════════════════════════════════════════
declare -A DEPT_NAMES=(
    [d1]="research"
    [d2]="engineering"
    [d3]="evolution"
    [d4]="product"
    [d5]="business"
    [d6]="evaluation"
    [d7]="infra"
    [d8]="finance"
    [d9]="cross-repo"
)

declare -A DEPT_MODELS=(
    [d1]="claude-sonnet-4-6"
    [d2]="claude-sonnet-4-6"
    [d3]="claude-sonnet-4-6"
    [d4]="claude-sonnet-4-6"
    [d5]="claude-haiku-4-5-20251001"
    [d6]="claude-sonnet-4-6"
    [d7]="claude-haiku-4-5-20251001"
    [d8]="claude-haiku-4-5-20251001"
    [d9]="claude-sonnet-4-6"
)

declare -A DEPT_BUDGET=(
    [d1]="1.50"
    [d2]="2.00"
    [d3]="2.00"
    [d4]="1.50"
    [d5]="0.50"
    [d6]="1.50"
    [d7]="0.50"
    [d8]="0.50"
    [d9]="1.50"
)

declare -A DEPT_TURNS=(
    [d1]="50"
    [d2]="50"
    [d3]="50"
    [d4]="50"
    [d5]="25"
    [d6]="50"
    [d7]="30"
    [d8]="25"
    [d9]="50"
)

# ── Per-department write allowlist (Cycle 14 Tier 4 — REAL shipper enforcement) ──
# Each dept may only commit files under these prefixes. Anything else in the
# working tree post-run is reported as `rejected_files` and dropped. This is
# what makes councils into shippers instead of advisors writing JSON status.
declare -A DEPT_WRITE_SCOPE=(
    [d1]="data/departments/research/ data/research-proposals/ research-vault/"
    [d2]="data/departments/engineering/ features/ scripts/arena/ hf-space/features/ nba-quant-space/features/"
    [d3]="data/departments/evolution/ data/karpathy/ scripts/evolution/ scripts/councils/sync-island-config.sh"
    [d4]="data/departments/product/ scripts/bloomberg/ scripts/forge/"
    [d5]="data/departments/business/ data/business/"
    [d6]="data/departments/evaluation/ scripts/calibration.py scripts/calibration_fit.py scripts/monitoring/auto_pav_refit.sh data/calibration/ data/nba-agent/calibration-map.json"
    [d7]="data/departments/infra/ scripts/monitoring/ scripts/infra/ scripts/cron/"
    [d8]="data/departments/finance/ data/finance/"
    [d9]="data/departments/cross-repo/ scripts/councils/sync-to-sister-repos.sh"
)

# ═══════════════════════════════════════════════════════════════
# RUN ONE DEPARTMENT
# ═══════════════════════════════════════════════════════════════
run_department() {
    local dept_id="$1"
    local dept_name="${DEPT_NAMES[$dept_id]}"
    local model="${DEPT_MODELS[$dept_id]}"
    local budget="${DEPT_BUDGET[$dept_id]}"
    local max_turns="${DEPT_TURNS[$dept_id]}"
    local prompt_file="${PROMPTS_DIR}/${dept_id}-${dept_name}.md"
    local log_file="${LOG_DIR}/${dept_id}-${dept_name}-${TODAY}.log"
    local result_file="${DATA_DIR}/council-${dept_name}-latest.json"

    log "═══ ${dept_id^^}: ${dept_name^^} ═══"
    log "Model: ${model} | Budget: \$${budget} | Max turns: ${max_turns}"

    # Check prompt file exists
    if [[ ! -f "${prompt_file}" ]]; then
        err "Missing prompt file: ${prompt_file}"
        return 1
    fi

    # Read the prompt
    local prompt
    prompt=$(cat "${prompt_file}")

    # Inject current state into prompt
    local state_inject=""

    # Add department program.md if exists
    local program_file="${ROOT}/scripts/departments/${dept_name}/program.md"
    if [[ -f "${program_file}" ]]; then
        state_inject="${state_inject}\n\n## Current Program\n$(cat "${program_file}")"
    fi

    # Add latest metrics if exists
    local metrics_file="${DATA_DIR}/${dept_name}/karpathy-output.json"
    if [[ -f "${metrics_file}" ]]; then
        state_inject="${state_inject}\n\n## Latest Metrics\n$(cat "${metrics_file}")"
    fi

    # Inject relevant wiki knowledge from Obsidian vault
    local wiki_index="${ROOT}/research-vault/wiki/index.md"
    if [[ -f "${wiki_index}" ]]; then
        state_inject="${state_inject}\n\n## Knowledge Vault (Karpathy KB)\n$(head -60 "${wiki_index}")"
    fi
    # Inject department-relevant wiki article
    local wiki_map_d1="${ROOT}/research-vault/wiki/concepts/nba-prediction.md"
    local wiki_map_d2="${ROOT}/research-vault/wiki/concepts/feature-engineering.md"
    local wiki_map_d3="${ROOT}/research-vault/wiki/architectures/evolution.md"
    local wiki_map_d4="${ROOT}/research-vault/wiki/architectures/infrastructure.md"
    local wiki_map_d5="${ROOT}/research-vault/wiki/techniques/betting-strategy.md"
    local wiki_map_d6="${ROOT}/research-vault/wiki/techniques/calibration.md"
    local wiki_map_d7="${ROOT}/research-vault/wiki/architectures/infrastructure.md"
    local wiki_map_d8="${ROOT}/research-vault/wiki/techniques/betting-strategy.md"
    local wiki_map_d9="${ROOT}/research-vault/wiki/architectures/karpathy-patterns.md"
    local wiki_var="wiki_map_${dept_id}"
    local dept_wiki="${!wiki_var:-}"
    if [[ -n "${dept_wiki}" && -f "${dept_wiki}" ]]; then
        # First 100 lines of relevant wiki article
        state_inject="${state_inject}\n\n## Relevant Research (from vault)\n$(head -100 "${dept_wiki}")"
    fi

    local full_prompt="${prompt}${state_inject}"

    # Run Claude Code CLI agent
    log "Launching Claude Code agent..."
    local start_time=$(date +%s)

    # Snapshot pre-run HEAD + dirty file list so we can verify the agent
    # actually shipped a real commit AND only report NEWLY touched out-of-scope
    # files as rejected (not pre-existing dirty state).
    local pre_sha
    pre_sha=$(cd "${ROOT}" && git rev-parse HEAD 2>/dev/null || echo "unknown")
    local pre_dirty_snapshot
    pre_dirty_snapshot=$(cd "${ROOT}" && git status --porcelain 2>/dev/null | awk '{print $2}' | sort -u)

    claude -p "${full_prompt}" \
        --model "${model}" \
        --output-format json \
        --max-turns "${max_turns}" \
        --max-budget-usd "${budget}" \
        --add-dir "${ROOT}" \
        --allowed-tools "Read,Edit,Write,Bash,Grep,Glob" \
        --dangerously-skip-permissions \
        >> "${log_file}" 2>&1

    local exit_code=$?
    local end_time=$(date +%s)
    local duration=$(( end_time - start_time ))

    # Log result
    local status="success"
    [[ $exit_code -ne 0 ]] && status="failed"

    # ── Stall-streak / no-op penalty metric (Cycle 14 Tier 4) ──
    # Read the agent's self-reported ship status from its karpathy-output.json.
    # If the agent shipped a change → reset streak. If it emitted no_op/failed
    # or didn't write a status → increment the streak. Append an append-only
    # row to data/departments/<dept>/metrics.jsonl so the dashboard can
    # surface which councils are churning without shipping.
    local agent_status="unknown"
    local agent_reason=""
    local agent_claimed_sha=""
    local karpathy_file="${DATA_DIR}/${dept_name}/karpathy-output.json"
    if [[ -f "${karpathy_file}" ]]; then
        agent_status=$(python3 -c "import json,sys; d=json.load(open('${karpathy_file}')); print(d.get('status','unknown'))" 2>/dev/null || echo "unknown")
        agent_reason=$(python3 -c "import json; d=json.load(open('${karpathy_file}')); print(d.get('reason_if_no_op','') or d.get('action',''))" 2>/dev/null || echo "")
        # Normalise empty/null/None to empty string so the hallucination check
        # below doesn't treat 'None' as a real sha claim.
        agent_claimed_sha=$(python3 -c "import json; d=json.load(open('${karpathy_file}')); v=d.get('commit_sha',''); print(v if v not in (None,'','None','null') else '')" 2>/dev/null || echo "")
    fi

    # ── Stage allowlisted edits + detect rejected files (Audit Edit 1) ──
    cd "${ROOT}"
    local rejected_files=""
    local scope="${DEPT_WRITE_SCOPE[$dept_id]:-data/departments/${dept_name}/}"
    # Compute NEWLY dirty files (current dirty MINUS pre-run dirty snapshot).
    # Anything new and OUTSIDE the dept's scope = rejected scope creep.
    local all_dirty
    all_dirty=$(git status --porcelain 2>/dev/null | awk '{print $2}' | sort -u)
    local new_dirty
    new_dirty=$(comm -23 <(echo "${all_dirty}") <(echo "${pre_dirty_snapshot}") 2>/dev/null || echo "${all_dirty}")
    if [[ -n "${new_dirty}" ]]; then
        for f in ${new_dirty}; do
            local in_scope=0
            for prefix in ${scope}; do
                if [[ "${f}" == ${prefix}* ]]; then
                    in_scope=1
                    break
                fi
            done
            if [[ ${in_scope} -eq 0 ]]; then
                rejected_files="${rejected_files}${f} "
            fi
        done
    fi
    # Stage only the in-scope files (tolerate non-existent paths)
    for prefix in ${scope}; do
        if [[ -e "${prefix}" || -d "${prefix}" ]]; then
            git add "${prefix}" 2>/dev/null || true
        fi
    done
    git add "${result_file}" 2>/dev/null || true

    # ── Verify ship: was anything REAL staged (not just status metadata)? (Audit Edit 2) ──
    # A "real ship" is anything in the dept's allowlist EXCEPT pure status/metadata files.
    # Status files (karpathy-output.json, metrics.jsonl, council-*.json) are written every
    # iteration regardless of whether the agent shipped a real change, so they don't count.
    local staged_in_scope
    staged_in_scope=$(git diff --cached --name-only 2>/dev/null \
        | grep -v "^data/departments/${dept_name}/council-" \
        | grep -v "^data/departments/${dept_name}/karpathy-output.json$" \
        | grep -v "^data/departments/${dept_name}/metrics.jsonl$" \
        | grep -v "^${result_file#${ROOT}/}$" || true)

    # Commit only if there's something real (not just the result_file metadata)
    local real_sha=""
    if [[ -n "$(git diff --cached --name-only 2>/dev/null)" ]]; then
        if git commit -m "council: ${dept_id^^} ${dept_name} Hermes iteration (${TIMESTAMP})" >> "${log_file}" 2>&1; then
            real_sha=$(git rev-parse HEAD 2>/dev/null || echo "")
        fi
    fi

    # Determine the verified ship status (Audit Edit 2 — hallucination detector)
    local verified_status="${agent_status}"
    if [[ "${agent_status}" == "shipped" ]]; then
        if [[ -z "${staged_in_scope}" ]]; then
            # Agent claimed shipped but no real files in scope changed → hallucinated
            verified_status="hallucinated"
        elif [[ -n "${agent_claimed_sha}" && -n "${real_sha}" && "${agent_claimed_sha}" != "${real_sha}" ]]; then
            # Agent invented a sha that doesn't match reality → hallucinated
            verified_status="hallucinated"
        fi
    fi

    # ── Stall-streak / no-op penalty metric (Cycle 14 Tier 4) ──
    # Read the agent's self-reported ship status, then DOWNGRADE based on
    # post-commit verification. Hallucinated and unknown both count as stalls.
    local metrics_file="${DATA_DIR}/${dept_name}/metrics.jsonl"
    mkdir -p "$(dirname "${metrics_file}")"
    local prev_streak=0
    if [[ -f "${metrics_file}" ]]; then
        prev_streak=$(tail -1 "${metrics_file}" 2>/dev/null | python3 -c "import json,sys; d=json.loads(sys.stdin.read() or '{}'); print(d.get('stall_streak',0))" 2>/dev/null || echo 0)
    fi
    local new_streak=0
    if [[ "${verified_status}" == "shipped" ]]; then
        new_streak=0
    else
        new_streak=$(( prev_streak + 1 ))
    fi

    python3 - "${metrics_file}" "${dept_id}" "${dept_name}" "${TIMESTAMP}" \
        "${agent_status}" "${verified_status}" "${new_streak}" "${duration}" "${exit_code}" "${agent_reason}" "${real_sha}" "${rejected_files}" <<'PYEOF'
import json, sys
(metrics_file, dept_id, dept_name, ts, agent_status, verified_status,
 new_streak, duration, exit_code, reason, real_sha, rejected_files) = sys.argv[1:]
row = {
    "timestamp": ts,
    "dept_id": dept_id,
    "dept_name": dept_name,
    "agent_status": agent_status,
    "verified_status": verified_status,
    "stall_streak": int(new_streak),
    "duration_seconds": int(duration),
    "exit_code": int(exit_code),
    "reason": reason,
    "real_sha": real_sha,
    "rejected_files": [f for f in rejected_files.split() if f],
}
with open(metrics_file, "a") as f:
    f.write(json.dumps(row) + "\n")
PYEOF

    # Write council result (now with verified_status, real_sha, rejected_files)
    python3 - "${result_file}" "${dept_name}" "${dept_id}" "${TIMESTAMP}" \
        "${model}" "${budget}" "${max_turns}" "${duration}" "${exit_code}" \
        "${status}" "${agent_status}" "${verified_status}" "${new_streak}" \
        "${log_file}" "${pre_sha}" "${real_sha}" "${rejected_files}" "${agent_claimed_sha}" <<'PYEOJ'
import json, sys
(out, dept_name, dept_id, ts, model, budget, max_turns, duration, exit_code,
 status, agent_status, verified_status, stall_streak, log_file,
 pre_sha, real_sha, rejected_files, agent_claimed_sha) = sys.argv[1:]
data = {
    "department": dept_name,
    "dept_id": dept_id,
    "timestamp": ts,
    "model": model,
    "budget_usd": float(budget),
    "max_turns": int(max_turns),
    "duration_seconds": int(duration),
    "exit_code": int(exit_code),
    "status": status,
    "agent_status": agent_status,
    "verified_status": verified_status,
    "stall_streak": int(stall_streak),
    "log_file": log_file,
    "pre_sha": pre_sha,
    "real_sha": real_sha,
    "agent_claimed_sha": agent_claimed_sha,
    "rejected_files": [f for f in rejected_files.split() if f],
}
with open(out, "w") as f:
    json.dump(data, f, indent=2)
PYEOJ

    if [[ $exit_code -eq 0 ]]; then
        if [[ "${verified_status}" == "shipped" ]]; then
            ok "${dept_name} SHIPPED in ${duration}s — sha=${real_sha:0:8}"
        elif [[ "${verified_status}" == "hallucinated" ]]; then
            err "${dept_name} HALLUCINATED in ${duration}s — claimed=${agent_claimed_sha:0:8} real=${real_sha:0:8}"
        else
            log "${dept_name} no-op in ${duration}s — streak=${new_streak}"
        fi
        if [[ -n "${rejected_files}" ]]; then
            err "${dept_name} rejected out-of-scope edits: ${rejected_files}"
        fi
    else
        err "${dept_name} FAILED (exit ${exit_code}) after ${duration}s"
    fi

    return $exit_code
}

# ═══════════════════════════════════════════════════════════════
# STATUS MODE
# ═══════════════════════════════════════════════════════════════
show_status() {
    echo ""
    echo "═══ HERMES COUNCIL STATUS ═══"
    echo ""
    printf "%-4s %-12s %-8s %-20s %-6s\n" "ID" "Department" "Status" "Last Run" "Secs"
    printf "%-4s %-12s %-8s %-20s %-6s\n" "---" "----------" "------" "--------" "----"

    for dept_id in d1 d2 d3 d4 d5 d6 d7 d8 d9; do
        local dept_name="${DEPT_NAMES[$dept_id]}"
        local result_file="${DATA_DIR}/council-${dept_name}-latest.json"

        if [[ -f "${result_file}" ]]; then
            local status=$(python3 -c "import json; d=json.load(open('${result_file}')); print(d.get('status','?'))" 2>/dev/null || echo "?")
            local ts=$(python3 -c "import json; d=json.load(open('${result_file}')); print(d.get('timestamp','?')[:19])" 2>/dev/null || echo "?")
            local dur=$(python3 -c "import json; d=json.load(open('${result_file}')); print(d.get('duration_seconds','?'))" 2>/dev/null || echo "?")
            printf "%-4s %-12s %-8s %-20s %-6s\n" "${dept_id}" "${dept_name}" "${status}" "${ts}" "${dur}"
        else
            printf "%-4s %-12s %-8s %-20s %-6s\n" "${dept_id}" "${dept_name}" "NEVER" "-" "-"
        fi
    done
    echo ""
}

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
if [[ "${1:-}" == "--status" ]]; then
    show_status
    exit 0
fi

# Determine which departments to run
DEPTS_TO_RUN=()
if [[ $# -eq 0 ]]; then
    # Run all
    DEPTS_TO_RUN=(d1 d2 d3 d4 d5 d6 d7 d8 d9)
else
    DEPTS_TO_RUN=("$@")
fi

log "═══════════════════════════════════════════════"
log "HERMES COUNCIL RUNNER — ${TIMESTAMP}"
log "Departments: ${DEPTS_TO_RUN[*]}"
log "═══════════════════════════════════════════════"

SUCCESS=0
FAILED=0

for dept_id in "${DEPTS_TO_RUN[@]}"; do
    if [[ -z "${DEPT_NAMES[$dept_id]:-}" ]]; then
        err "Unknown department: ${dept_id}"
        ((FAILED++))
        continue
    fi

    if run_department "${dept_id}"; then
        ((SUCCESS++))
    else
        ((FAILED++))
    fi

    # Pause between departments (rate limiting)
    sleep 10
done

log ""
log "═══ RESULTS: ${SUCCESS} success, ${FAILED} failed ═══"

# Push if any commits were made
cd "${ROOT}"
if [[ $(git log --oneline -1 --format=%s 2>/dev/null) == council:* ]]; then
    log "Pushing council commits..."
    # Pull first to avoid conflicts from parallel writers
    git pull --rebase origin main 2>/dev/null || true
    git push origin main 2>/dev/null && ok "Pushed to origin" || err "Push failed"
fi

exit ${FAILED}
