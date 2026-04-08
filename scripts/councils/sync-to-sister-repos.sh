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
