#!/bin/bash
# check-staleness.sh — Scanne les fichiers directives/ et technicals/ pour dates obsoletes
# Usage: bash scripts/check-staleness.sh
# Alerte si un fichier n'a pas de "Last updated:" ou si la date > 48h

STALE_THRESHOLD_HOURS=48
export TZ="Europe/Paris"
CURRENT_EPOCH=$(date +%s)
STALE_COUNT=0
MISSING_COUNT=0
OK_COUNT=0

echo "=== Anti-Staleness Scanner ==="
echo "Threshold: ${STALE_THRESHOLD_HOURS}h"
echo "Scanning: directives/*.md, technicals/*.md"
echo ""

for dir in directives technicals; do
    if [ ! -d "$dir" ]; then
        echo "WARN: Directory $dir not found"
        continue
    fi

    for file in "$dir"/*.md; do
        [ -f "$file" ] || continue

        # Extract "Last updated: YYYY-MM-DDTHH:MM:SSZ" line
        LAST_UPDATED=$(grep -m1 "Last updated:" "$file" | grep -oP '\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})')

        if [ -z "$LAST_UPDATED" ]; then
            echo "MISSING  $file — no 'Last updated:' timestamp found"
            MISSING_COUNT=$((MISSING_COUNT + 1))
            continue
        fi

        # Parse the date
        FILE_EPOCH=$(date -d "$LAST_UPDATED" +%s 2>/dev/null)
        if [ -z "$FILE_EPOCH" ]; then
            echo "PARSE_ERR  $file — could not parse date: $LAST_UPDATED"
            MISSING_COUNT=$((MISSING_COUNT + 1))
            continue
        fi

        # Calculate age in hours
        AGE_SECONDS=$((CURRENT_EPOCH - FILE_EPOCH))
        AGE_HOURS=$((AGE_SECONDS / 3600))

        if [ "$AGE_HOURS" -gt "$STALE_THRESHOLD_HOURS" ]; then
            echo "STALE    $file — ${AGE_HOURS}h old (updated: $LAST_UPDATED)"
            STALE_COUNT=$((STALE_COUNT + 1))
        else
            echo "OK       $file — ${AGE_HOURS}h old"
            OK_COUNT=$((OK_COUNT + 1))
        fi
    done
done

# Also scan subdirectories (directives/repos/)
for file in directives/repos/*.md; do
    [ -f "$file" ] || continue

    LAST_UPDATED=$(grep -m1 "Last updated:" "$file" | grep -oP '\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})')

    if [ -z "$LAST_UPDATED" ]; then
        echo "MISSING  $file — no 'Last updated:' timestamp found"
        MISSING_COUNT=$((MISSING_COUNT + 1))
        continue
    fi

    FILE_EPOCH=$(date -d "$LAST_UPDATED" +%s 2>/dev/null)
    if [ -z "$FILE_EPOCH" ]; then
        echo "PARSE_ERR  $file — could not parse date: $LAST_UPDATED"
        MISSING_COUNT=$((MISSING_COUNT + 1))
        continue
    fi

    AGE_SECONDS=$((CURRENT_EPOCH - FILE_EPOCH))
    AGE_HOURS=$((AGE_SECONDS / 3600))

    if [ "$AGE_HOURS" -gt "$STALE_THRESHOLD_HOURS" ]; then
        echo "STALE    $file — ${AGE_HOURS}h old (updated: $LAST_UPDATED)"
        STALE_COUNT=$((STALE_COUNT + 1))
    else
        echo "OK       $file — ${AGE_HOURS}h old"
        OK_COUNT=$((OK_COUNT + 1))
    fi
done

echo ""
echo "=== Summary ==="
echo "OK:      $OK_COUNT files"
echo "STALE:   $STALE_COUNT files (>${STALE_THRESHOLD_HOURS}h)"
echo "MISSING: $MISSING_COUNT files (no timestamp)"
echo ""

if [ "$STALE_COUNT" -gt 0 ] || [ "$MISSING_COUNT" -gt 0 ]; then
    echo "ACTION REQUIRED: Update stale/missing files before proceeding."
    exit 1
else
    echo "All files are fresh."
    exit 0
fi
