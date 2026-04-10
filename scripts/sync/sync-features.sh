#!/usr/bin/env bash
# =============================================================================
# sync-features.sh — Feature Engine Parity Sync
#
# Ensures features/engine.py is identical across:
#   - nomos-nba-agent/features/engine.py        (SOURCE OF TRUTH)
#   - nomos-nba-agent/hf-space/features/engine.py
#   - mon-ipad/features/engine.py
#   - mon-ipad/hf-space/features/engine.py
#
# Rule: nomos-nba-agent/features/engine.py is the canonical source.
# All other copies must match it exactly.
#
# Usage:
#   /home/lahargnedebartoli/mon-ipad/scripts/sync/sync-features.sh
#   /home/lahargnedebartoli/mon-ipad/scripts/sync/sync-features.sh --check-only
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SOURCE="/home/lahargnedebartoli/nomos-nba-agent/features/engine.py"

TARGETS=(
    "/home/lahargnedebartoli/nomos-nba-agent/hf-space/features/engine.py"
    "/home/lahargnedebartoli/mon-ipad/features/engine.py"
    "/home/lahargnedebartoli/mon-ipad/hf-space/features/engine.py"
)

TARGET_LABELS=(
    "nomos-nba-agent/hf-space/features/engine.py"
    "mon-ipad/features/engine.py"
    "mon-ipad/hf-space/features/engine.py"
)

CHECK_ONLY=false
for arg in "$@"; do
    case "$arg" in
        --check-only) CHECK_ONLY=true ;;
        --help|-h)
            echo "Usage: $0 [--check-only]"
            echo "  --check-only   Report mismatches without copying"
            exit 0
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Verify source exists
# ---------------------------------------------------------------------------
if [ ! -f "$SOURCE" ]; then
    echo "FATAL: Source file not found: ${SOURCE}"
    echo "Cannot sync feature engine without canonical source."
    exit 1
fi

SOURCE_MD5=$(md5sum "$SOURCE" | awk '{print $1}')
SOURCE_LINES=$(wc -l < "$SOURCE")
SOURCE_SIZE=$(stat -c%s "$SOURCE" 2>/dev/null || stat -f%z "$SOURCE" 2>/dev/null)

echo "========================================"
echo "Feature Engine Parity Sync"
echo "========================================"
echo "Source: ${SOURCE}"
echo "  MD5:   ${SOURCE_MD5}"
echo "  Lines: ${SOURCE_LINES}"
echo "  Size:  ${SOURCE_SIZE} bytes"
echo "========================================"
echo ""

MISMATCHES=0
SYNCED=0
MISSING=0

for i in "${!TARGETS[@]}"; do
    target="${TARGETS[$i]}"
    label="${TARGET_LABELS[$i]}"

    if [ ! -f "$target" ]; then
        echo "MISSING: ${label}"
        echo "  Path:  ${target}"
        ((MISSING++))

        if $CHECK_ONLY; then
            echo "  Action: [CHECK ONLY] Would create directory and copy"
        else
            # Ensure target directory exists
            target_dir=$(dirname "$target")
            mkdir -p "$target_dir"
            cp "$SOURCE" "$target"
            echo "  Action: CREATED (copied from source)"
            ((SYNCED++))
        fi
        echo ""
        continue
    fi

    TARGET_MD5=$(md5sum "$target" | awk '{print $1}')

    if [ "$SOURCE_MD5" = "$TARGET_MD5" ]; then
        echo "OK:      ${label}"
        echo "  MD5:   ${TARGET_MD5} (matches)"
    else
        TARGET_LINES=$(wc -l < "$target")
        echo "MISMATCH: ${label}"
        echo "  Source MD5:  ${SOURCE_MD5} (${SOURCE_LINES} lines)"
        echo "  Target MD5:  ${TARGET_MD5} (${TARGET_LINES} lines)"

        # Show a brief diff summary
        diff_count=$(diff "$SOURCE" "$target" | grep -c "^[<>]" || true)
        echo "  Diff lines:  ${diff_count}"

        ((MISMATCHES++))

        if $CHECK_ONLY; then
            echo "  Action: [CHECK ONLY] Would overwrite with source"
        else
            cp "$SOURCE" "$target"
            NEW_MD5=$(md5sum "$target" | awk '{print $1}')
            echo "  Action: SYNCED (overwrote with source, new MD5: ${NEW_MD5})"
            ((SYNCED++))
        fi
    fi
    echo ""
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "========================================"
echo "SUMMARY"
echo "========================================"
echo "Source:     ${SOURCE}"
echo "Targets:   ${#TARGETS[@]}"
echo "Matches:   $((${#TARGETS[@]} - MISMATCHES - MISSING))"
echo "Mismatches: ${MISMATCHES}"
echo "Missing:   ${MISSING}"
echo "Synced:    ${SYNCED}"

if [ "$MISMATCHES" -gt 0 ] || [ "$MISSING" -gt 0 ]; then
    if $CHECK_ONLY; then
        echo "STATUS: PARITY BROKEN (run without --check-only to fix)"
        exit 1
    else
        echo "STATUS: PARITY RESTORED"
        exit 0
    fi
else
    echo "STATUS: ALL COPIES IN SYNC"
    exit 0
fi
