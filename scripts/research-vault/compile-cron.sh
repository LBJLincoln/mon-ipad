#!/usr/bin/env bash
# Obsidian / NotebookLM-style research vault compile loop.
#
# Runs every 2h via cron — ingests fresh research notes from each repo's raw/
# directory, then compiles the wiki/ articles + backlinks.json so that future
# Claude Code sessions can RAG against the latest paper-derived knowledge.
#
# CRON entry (installed 2026-04-07):
#   23 */2 * * * /home/termius/mon-ipad/scripts/research-vault/compile-cron.sh
#
# Why a wrapper script and not a direct cron line: compile.py needs PWD set
# to research-vault/ AND we want to log + commit + push the diff so other VMs
# (laptop, brother's PC) pick up the new wiki/ on their next pull.

set -uo pipefail

ROOT="/home/termius/mon-ipad"
VAULT="$ROOT/research-vault"
LOG="$ROOT/data/research-vault-cron.log"

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

mkdir -p "$(dirname "$LOG")"
log "compile-cron start"

if [[ ! -d "$VAULT" ]]; then
  log "ERR research-vault/ missing — run scripts/vendor/clone-vendor.sh-equivalent for vault"
  exit 1
fi

cd "$VAULT" || { log "ERR cd $VAULT"; exit 2; }

# Stage 1 — pull any new raw/ notes from upstream (no-op for now, kept for future)
# Stage 2 — ingest fresh files into the canonical store
if [[ -f ingest.py ]]; then
  python3 ingest.py >>"$LOG" 2>&1 || log "WARN ingest.py exit=$?"
fi

# Stage 3 — recompile wiki/ + backlinks.json
if [[ -f compile.py ]]; then
  python3 compile.py >>"$LOG" 2>&1 || { log "ERR compile.py exit=$?"; exit 3; }
else
  log "ERR research-vault/compile.py missing"
  exit 4
fi

# Stage 4 — lint (warn-only)
if [[ -f lint.py ]]; then
  python3 lint.py >>"$LOG" 2>&1 || log "WARN lint.py reported issues"
fi

# Stage 5 — commit + push changes (silent on no-op)
cd "$ROOT" || exit 0
if ! git diff --quiet -- research-vault/ 2>/dev/null; then
  git add research-vault/wiki/ research-vault/backlinks.json 2>/dev/null || true
  git commit -m "research-vault: $(date -u +%Y-%m-%dT%H:%MZ) compile" >>"$LOG" 2>&1 || true
  git push origin main >>"$LOG" 2>&1 || log "WARN push failed (will retry next run)"
fi

log "compile-cron done"
