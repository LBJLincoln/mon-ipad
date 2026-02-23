#!/bin/bash
# push-directives.sh — Pousse les CLAUDE.md spécifiques vers chaque repo satellite
# Usage: bash scripts/push-directives.sh [repo] [--dry-run]
# Exemple: bash scripts/push-directives.sh rag-tests
# Exemple: bash scripts/push-directives.sh (tous les repos)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
DIRECTIVES_DIR="$REPO_ROOT/directives/repos"
DRY_RUN=false

# Parse args
TARGET_REPO=""
for arg in "$@"; do
    if [[ "$arg" == "--dry-run" ]]; then
        DRY_RUN=true
    elif [[ "$arg" != "" && "$arg" != --* ]]; then
        TARGET_REPO="$arg"
    fi
done

echo "=== push-directives.sh ==="
echo "Source: $DIRECTIVES_DIR"
echo "Dry run: $DRY_RUN"
echo ""

# Mapping : repo-name → directive-file
declare -A REPOS
REPOS["rag-tests"]="rag-tests.md"
REPOS["rag-website"]="rag-website.md"
REPOS["rag-dashboard"]="rag-dashboard.md"
REPOS["rag-data-ingestion"]="rag-data-ingestion.md"
REPOS["rag-pme-connectors"]="rag-pme-connectors.md"

push_directive() {
    local repo="$1"
    local directive_file="$DIRECTIVES_DIR/${REPOS[$repo]}"
    local tmpdir="/tmp/push-directive-$repo"

    echo "--- Pushing to $repo ---"

    if [[ ! -f "$directive_file" ]]; then
        echo "  ❌ Fichier manquant : $directive_file"
        return 1
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "  [DRY RUN] Would push $directive_file → $repo/CLAUDE.md"
        return 0
    fi

    # Clone le repo satellite en tmp
    rm -rf "$tmpdir"
    git clone "$(git -C "$REPO_ROOT" remote get-url "$repo")" "$tmpdir" --depth=1 --quiet

    # Copier le CLAUDE.md
    cp "$directive_file" "$tmpdir/CLAUDE.md"

    # Commit si changement
    cd "$tmpdir"
    if git diff --quiet HEAD CLAUDE.md 2>/dev/null && git ls-files --error-unmatch CLAUDE.md 2>/dev/null; then
        echo "  ✓ Pas de changement dans $repo/CLAUDE.md"
    else
        git add CLAUDE.md
        git commit -m "chore(directives): MAJ CLAUDE.md depuis mon-ipad/directives/repos/$repo.md

Piloté depuis la tour de contrôle mon-ipad.
Co-Authored-By: Claude Code <noreply@anthropic.com>"
        git push origin main --quiet
        echo "  ✓ Poussé vers $repo/CLAUDE.md"
    fi

    # Nettoyage
    cd "$REPO_ROOT"
    rm -rf "$tmpdir"
}

# Exécution
if [[ -n "$TARGET_REPO" ]]; then
    if [[ -z "${REPOS[$TARGET_REPO]}" ]]; then
        echo "❌ Repo inconnu : $TARGET_REPO"
        echo "Repos disponibles : ${!REPOS[@]}"
        exit 1
    fi
    push_directive "$TARGET_REPO"
else
    echo "Pushing vers tous les repos satellites..."
    echo ""
    for repo in rag-tests rag-website rag-dashboard rag-data-ingestion rag-pme-connectors; do
        push_directive "$repo"
        echo ""
    done
fi

echo "=== Terminé ==="
