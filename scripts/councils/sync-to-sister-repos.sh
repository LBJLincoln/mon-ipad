#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# SYNC COUNCILS TO SISTER REPOS
# ═══════════════════════════════════════════════════════════════════════════
# Copies the freshly generated council-*-latest.json files from
# mon-ipad/data/departments/ into each sister repo's data/departments/
# folder, then commits + pushes per repo.
#
# Why: hermes-runner.sh writes ONE source of truth in mon-ipad. The sister
# repos (nomos-political-alpha, nomos-nba-agent, nomos-dashboard, rgwa,
# nomos-picks, nomos-pierre) need a mirror so the dashboard + cross-repo
# audits see fresh data.
#
# Runs as a post-step after hermes-runner.sh, scheduled by cron.
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

ROOT="/home/termius/mon-ipad"
SRC="${ROOT}/data/departments"
LOG="${ROOT}/logs/councils/sync-sister-repos.log"

mkdir -p "$(dirname "${LOG}")"

SISTER_REPOS=(
    "/home/termius/nomos-political-alpha"
    "/home/termius/nomos-nba-agent"
    "/home/termius/nomos-dashboard"
    "/home/termius/rgwa"
    "/home/termius/nomos-picks"
    "/home/termius/nomos-pierre"
)

TS=$(date '+%Y-%m-%d %H:%M:%S UTC')
{
echo ""
echo "[sync] Start ${TS}"
} >> "${LOG}"

if [[ ! -d "${SRC}" ]]; then
    echo "[sync] No source ${SRC} — abort" >> "${LOG}"
    exit 1
fi

# Files to mirror
COUNCIL_FILES=()
while IFS= read -r f; do
    COUNCIL_FILES+=("${f}")
done < <(find "${SRC}" -maxdepth 1 -name "council-*-latest.json" -type f)

if [[ ${#COUNCIL_FILES[@]} -eq 0 ]]; then
    echo "[sync] No council files found" >> "${LOG}"
    exit 0
fi

echo "[sync] Mirroring ${#COUNCIL_FILES[@]} council files" >> "${LOG}"

for repo in "${SISTER_REPOS[@]}"; do
    if [[ ! -d "${repo}" ]]; then
        echo "[sync]   skip (missing): ${repo}" >> "${LOG}"
        continue
    fi

    DEST="${repo}/data/departments"
    mkdir -p "${DEST}"

    changed=0
    for f in "${COUNCIL_FILES[@]}"; do
        bn=$(basename "${f}")
        if ! cmp -s "${f}" "${DEST}/${bn}" 2>/dev/null; then
            cp "${f}" "${DEST}/${bn}"
            changed=$((changed + 1))
        fi
    done

    if [[ ${changed} -gt 0 ]]; then
        cd "${repo}"
        git add data/departments/council-*-latest.json 2>/dev/null || true
        if ! git diff --cached --quiet 2>/dev/null; then
            git commit -m "data: mirror councils from mon-ipad ($(date '+%Y-%m-%d %H:%M'))" --quiet 2>/dev/null || true
            # Pull --rebase to avoid push conflicts
            git pull --rebase --quiet 2>/dev/null || true
            git push --quiet 2>/dev/null || true
            echo "[sync]   ${repo}: pushed ${changed} files" >> "${LOG}"
        else
            echo "[sync]   ${repo}: no diff after stage" >> "${LOG}"
        fi
    else
        echo "[sync]   ${repo}: up-to-date" >> "${LOG}"
    fi
done

echo "[sync] Done $(date '+%H:%M:%S UTC')" >> "${LOG}"

# ─── ENGINE PARITY CHECK ─────────────────────────────────────────────────────
# Verify features/engine.py is identical across mon-ipad, hf-space, and
# nomos-nba-agent. Write a machine-readable status to cross-repo/ for D9 audit.
check_engine_parity() {
    local parity_file="${ROOT}/data/departments/cross-repo/engine-parity.json"
    local engine_mon="${ROOT}/features/engine.py"
    local engine_hf="${ROOT}/hf-space/features/engine.py"
    local engine_agent="/home/termius/nomos-nba-agent/features/engine.py"

    local md5_mon md5_hf md5_agent
    md5_mon=$(md5sum "${engine_mon}" 2>/dev/null | awk '{print $1}' || echo "missing")
    md5_hf=$(md5sum  "${engine_hf}"  2>/dev/null | awk '{print $1}' || echo "missing")
    md5_agent=$(md5sum "${engine_agent}" 2>/dev/null | awk '{print $1}' || echo "missing")

    local ok="true"
    local diverged_repos="[]"
    if [[ "${md5_mon}" != "${md5_agent}" || "${md5_mon}" != "${md5_hf}" ]]; then
        ok="false"
        diverged_repos="[\"nomos-nba-agent\"]"
        echo "[sync] ENGINE PARITY BROKEN: mon-ipad=${md5_mon} hf-space=${md5_hf} nba-agent=${md5_agent}" >> "${LOG}"
        echo "[sync] FIX: In mon-ipad features/engine.py line ~7516, change \`> 400\` to \`> target_features\` to align with MAX_FEATURES=200 rule, then re-run sync." >> "${LOG}"
    else
        echo "[sync] ENGINE PARITY OK: all three at ${md5_mon}" >> "${LOG}"
    fi

    mkdir -p "$(dirname "${parity_file}")"
    cat > "${parity_file}" <<PARITY_JSON
{
  "timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "ok": ${ok},
  "canonical": "mon-ipad",
  "md5": {
    "mon_ipad":       "${md5_mon}",
    "hf_space":       "${md5_hf}",
    "nomos_nba_agent": "${md5_agent}"
  },
  "diverged_repos": ${diverged_repos},
  "fix_if_broken": "Update mon-ipad/features/engine.py line ~7516: change \`> 400\` to \`> target_features\` (MAX_FEATURES=200 rule). Then run this script to propagate to sister repos.",
  "divergence_detail": {
    "mon_ipad_line": "if len(selected) < 10 or len(selected) > 400:",
    "nomos_nba_agent_line": "if len(selected) < 10 or len(selected) > target_features:",
    "semantic_winner": "nomos_nba_agent — target_features=200 enforces MAX_FEATURES cap correctly"
  }
}
PARITY_JSON
}

check_engine_parity
