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

    # Detect divergence type: old > 400 hardcode vs new semantic drift
    local fix_desc divergence_detail
    if grep -qF "or len(selected) > 400:" "${engine_mon}" 2>/dev/null; then
        # Old known issue still present
        fix_desc="Update mon-ipad/features/engine.py line ~7516: change \`> 400\` to \`> target_features\` (MAX_FEATURES=200 rule). Then re-run this script."
        divergence_detail="{\"type\": \"hardcode\", \"mon_ipad_line\": \"if len(selected) < 10 or len(selected) > 400:\", \"nomos_nba_agent_line\": \"if len(selected) < 10 or len(selected) > target_features:\", \"semantic_winner\": \"nomos_nba_agent\"}"
    elif [[ "${ok}" == "false" ]]; then
        # Semantic drift: nomos-nba-agent has newer improvements; mon-ipad needs to be updated
        fix_desc="Semantic drift detected (not the old > 400 issue). nomos-nba-agent is AHEAD: vig_dist55 calc (line ~6447), density calc using ISO date strings (line ~6497), default row values (line ~6722). Copy nomos-nba-agent engine.py to mon-ipad + hf-space, then push."
        divergence_detail="{\"type\": \"semantic_drift\", \"direction\": \"nomos-nba-agent is newer/canonical\", \"diff_locations\": [\"line ~6447: _vig_dist55 uses fair_home_prob dict lookup in nba-agent\", \"line ~6497: density uses ISO string comparison in nba-agent (more correct)\", \"line ~6722: default row neutral values differ\", \"line ~7517: comment only (trivial)\"]}"
    else
        fix_desc="No fix needed"
        divergence_detail="{}"
    fi

    mkdir -p "$(dirname "${parity_file}")"
    cat > "${parity_file}" <<PARITY_JSON
{
  "timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "ok": ${ok},
  "canonical": "nomos_nba_agent",
  "md5": {
    "mon_ipad":        "${md5_mon}",
    "hf_space":        "${md5_hf}",
    "nomos_nba_agent": "${md5_agent}"
  },
  "diverged_repos": ${diverged_repos},
  "fix_if_broken": "${fix_desc}",
  "divergence_detail": ${divergence_detail}
}
PARITY_JSON
}

check_engine_parity

# ─── ENGINE PARITY AUTO-FIX ──────────────────────────────────────────────────
# When the known > 400 → > target_features divergence is detected, apply the
# fix automatically, commit to mon-ipad, and re-run parity check to refresh
# engine-parity.json. Safe: grep guards the pattern before touching any file.
auto_fix_engine_parity() {
    local engine_mon="${ROOT}/features/engine.py"
    local engine_hf="${ROOT}/hf-space/features/engine.py"
    local fix_pat="or len(selected) > 400:"

    if ! grep -qF "${fix_pat}" "${engine_mon}" 2>/dev/null; then
        # Old > 400 hardcode is gone. Check if parity still broken (semantic drift).
        local md5_mon_cur md5_agent_cur
        md5_mon_cur=$(md5sum "${engine_mon}" 2>/dev/null | awk '{print $1}' || echo "missing")
        md5_agent_cur=$(md5sum "/home/termius/nomos-nba-agent/features/engine.py" 2>/dev/null | awk '{print $1}' || echo "missing")
        if [[ "${md5_mon_cur}" != "${md5_agent_cur}" ]]; then
            echo "[sync] auto_fix: > 400 already fixed BUT parity still broken (semantic drift). nomos-nba-agent is canonical — copy its engine.py to mon-ipad manually." >> "${LOG}"
        else
            echo "[sync] auto_fix: > 400 fixed and parity OK — no action needed" >> "${LOG}"
        fi
        return 0
    fi

    echo "[sync] auto_fix: patching > 400 → > target_features in mon-ipad + hf-space" >> "${LOG}"
    sed -i 's/or len(selected) > 400:/or len(selected) > target_features:/' \
        "${engine_mon}" "${engine_hf}"

    cd "${ROOT}"
    git add features/engine.py hf-space/features/engine.py 2>/dev/null || true
    if ! git diff --cached --quiet 2>/dev/null; then
        git commit -m "fix(engine): > 400 → > target_features — enforces MAX_FEATURES=200 cap (D9 auto-fix)" \
            --quiet 2>/dev/null || true
        echo "[sync] auto_fix: committed parity fix to mon-ipad" >> "${LOG}"
    else
        echo "[sync] auto_fix: sed ran but no staged diff — already clean" >> "${LOG}"
    fi

    # Refresh parity JSON after fix
    check_engine_parity

    # Write audit log so D9 can confirm auto_fix fired
    local fix_log="${ROOT}/data/departments/cross-repo/auto-fix-log.json"
    cat > "${fix_log}" <<FIX_LOG
{
  "timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "fix_applied": true,
  "pattern_replaced": "or len(selected) > 400:",
  "replacement": "or len(selected) > target_features:",
  "files_patched": [
    "features/engine.py",
    "hf-space/features/engine.py"
  ],
  "description": "MAX_FEATURES=200 enforcement — > 400 hardcode replaced with > target_features"
}
FIX_LOG
    echo "[sync] auto_fix: wrote audit log to data/departments/cross-repo/auto-fix-log.json" >> "${LOG}"
}

auto_fix_engine_parity
