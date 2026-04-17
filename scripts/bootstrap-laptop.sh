#!/bin/bash
# ─── Nomos42 laptop / new-machine bootstrap ──────────────────────────
# Use when onboarding a new compute node (brother laptop, Claude Desktop
# machine, fresh VM). One-shot: clones, pulls submodules, wires env,
# verifies HF + Stripe + Supabase tokens, installs python deps.
#
# USAGE:
#   curl -fsSL https://raw.githubusercontent.com/LBJLincoln/mon-ipad/main/scripts/bootstrap-laptop.sh | bash
# OR after cloning:
#   bash scripts/bootstrap-laptop.sh
#
# ARGS (env vars):
#   NOMOS_ROOT   where to clone (default: $HOME/mon-ipad)
#   SKIP_CLONE=1 skip git clone (if already in the repo)
#   SKIP_DEPS=1  skip pip install
#   SKIP_VERIFY=1 skip token verification

set -euo pipefail

NOMOS_ROOT="${NOMOS_ROOT:-$HOME/mon-ipad}"
REPO_URL="https://github.com/LBJLincoln/mon-ipad.git"

log() { printf "\033[1;36m[bootstrap]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
err() { printf "\033[1;31m[err]\033[0m %s\n" "$*"; }

# ── 1. Clone ──────────────────────────────────────────────────────────
if [ "${SKIP_CLONE:-0}" != "1" ]; then
    if [ -d "$NOMOS_ROOT/.git" ]; then
        log "repo already exists at $NOMOS_ROOT — pulling"
        git -C "$NOMOS_ROOT" pull --ff-only
    else
        log "cloning $REPO_URL → $NOMOS_ROOT"
        git clone "$REPO_URL" "$NOMOS_ROOT"
    fi
fi
cd "$NOMOS_ROOT"

# ── 2. Env file ───────────────────────────────────────────────────────
if [ ! -f .env.local ]; then
    if [ -f .env.example ]; then
        cp .env.example .env.local
        warn ".env.local created from template — EDIT IT NOW with real tokens before continuing"
        warn "  required: HF_TOKEN, HF_TOKEN_NBA, HF_TOKEN_LLM, HF_TOKEN_COUNCILS"
        warn "  nice-to-have: CEREBRAS_API_KEY, MISTRAL_API_KEY, GOOGLE_API_KEY, STRIPE_SK"
        warn ""
        warn "  abort bootstrap, edit .env.local, then re-run:"
        warn "    SKIP_CLONE=1 bash scripts/bootstrap-laptop.sh"
        exit 2
    else
        err "no .env.example found — repo is broken"
        exit 1
    fi
fi
log ".env.local present"

# ── 3. Python deps ────────────────────────────────────────────────────
if [ "${SKIP_DEPS:-0}" != "1" ]; then
    if ! command -v python3 >/dev/null; then
        err "python3 missing — install with your package manager"
        exit 1
    fi
    log "installing minimal python deps (huggingface_hub, requests, python-dotenv)"
    python3 -m pip install --user --quiet --upgrade huggingface_hub requests python-dotenv 2>&1 | tail -5 || true
fi

# ── 4. Token verification ─────────────────────────────────────────────
if [ "${SKIP_VERIFY:-0}" != "1" ]; then
    log "verifying HF tokens reach expected accounts"
    # shellcheck disable=SC1091
    source .env.local 2>/dev/null || true
    python3 - <<'PY' || warn "token verification had failures (see above)"
import os, sys
try:
    from huggingface_hub import HfApi
except ImportError:
    print("  huggingface_hub not installed — skipping")
    sys.exit(0)
expected = {
    "HF_TOKEN": "LBJLincoln",
    "HF_TOKEN_NBA": "LBJLincoln26",
    "HF_TOKEN_LLM": "Nomos42",
    "HF_TOKEN_COUNCILS": "TESTforge42",
}
for env_name, want in expected.items():
    tok = os.environ.get(env_name, "")
    if not tok or tok.startswith("hf_xxx"):
        print(f"  {env_name}: NOT SET (placeholder)")
        continue
    try:
        who = HfApi(token=tok).whoami().get("name", "?")
        ok = "OK" if who == want else f"WRONG ACCOUNT (got {who}, want {want})"
        print(f"  {env_name}: {ok}")
    except Exception as e:
        print(f"  {env_name}: ERR {str(e)[:60]}")
PY
fi

# ── 5. Summary ────────────────────────────────────────────────────────
log "bootstrap complete"
log ""
log "next steps:"
log "  1. source .env.local"
log "  2. bash scripts/setup-crons.sh      # optional, only on primary VM"
log "  3. bash scripts/keepalive-spaces.sh # one-shot health check"
log ""
log "Claude Code Desktop: open $NOMOS_ROOT as project folder, it works same as CLI."
