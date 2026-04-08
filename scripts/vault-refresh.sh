#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# OBSIDIAN KNOWLEDGE VAULT — Automated Refresh
# ═══════════════════════════════════════════════════════════════
# Runs ingest → compile → lint pipeline.
# Cron: every 4 hours alongside Hermes councils.
#
#   0 1,5,9,13,17,21 * * * /home/termius/mon-ipad/scripts/vault-refresh.sh
# ═══════════════════════════════════════════════════════════════
set -uo pipefail

ROOT="/home/termius/mon-ipad"
VAULT="${ROOT}/research-vault"
LOG="${ROOT}/logs/vault-refresh.log"
mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1" | tee -a "$LOG"; }

log "═══ VAULT REFRESH START ═══"

# Stage 1: Ingest (raw sources → raw/)
log "Stage 1: Ingest..."
python3 "${VAULT}/ingest.py" >> "$LOG" 2>&1
INGEST_RC=$?
[[ $INGEST_RC -eq 0 ]] && log "  ✓ Ingest OK" || log "  ✗ Ingest FAILED (rc=$INGEST_RC)"

# Stage 2: Compile (raw/ → wiki/)
log "Stage 2: Compile..."
python3 "${VAULT}/compile.py" >> "$LOG" 2>&1
COMPILE_RC=$?
[[ $COMPILE_RC -eq 0 ]] && log "  ✓ Compile OK" || log "  ✗ Compile FAILED (rc=$COMPILE_RC)"

# Stage 3: Lint (health check)
log "Stage 3: Lint..."
LINT_OUT=$(python3 "${VAULT}/lint.py" --json 2>/dev/null)
LINT_RC=$?
ERRORS=$(echo "$LINT_OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('errors',0))" 2>/dev/null || echo "?")
WARNINGS=$(echo "$LINT_OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('warnings',0))" 2>/dev/null || echo "?")
log "  Lint: ${ERRORS} errors, ${WARNINGS} warnings (rc=$LINT_RC)"

# Stage 4: Git commit if changes
cd "$ROOT"
VAULT_CHANGES=$(git status --porcelain -- research-vault/ 2>/dev/null | wc -l)
if [[ $VAULT_CHANGES -gt 0 ]]; then
    git add research-vault/wiki/ research-vault/backlinks.json research-vault/raw/ 2>/dev/null
    git commit -m "vault: refresh $(date -u +%Y-%m-%d) — $(find ${VAULT}/raw -name '*.md' | wc -l) raw, $(find ${VAULT}/wiki -name '*.md' | wc -l) wiki articles" 2>/dev/null
    log "  ✓ Git committed vault changes"
else
    log "  ○ No vault changes to commit"
fi

log "═══ VAULT REFRESH DONE ═══"
