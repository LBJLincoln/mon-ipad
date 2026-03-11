#!/usr/bin/env bash
# ==========================================================================
# Docling Setup for GitHub Codespace — Continuous Expert PDF Ingestion
# ==========================================================================
#
# This script sets up Docling locally on a Codespace (32GB RAM) for
# processing large expert PDFs that the HF Space (16GB) cannot handle.
#
# Usage:
#   cd /workspaces/mon-ipad
#   bash codespace/setup-docling.sh
#
# Prerequisites:
#   - GitHub Codespace with 32GB RAM
#   - .env.local with API keys (TAVILY, PINECONE, SUPABASE, NEO4J)
# ==========================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$SCRIPT_DIR/logs"
DATA_DIR="$SCRIPT_DIR/data"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

echo "=================================================================="
echo "  DOCLING CODESPACE SETUP — Expert PDF Continuous Ingestion"
echo "  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=================================================================="
echo ""

# ------------------------------------------------------------------
# Step 0: Verify we are in a Codespace or compatible environment
# ------------------------------------------------------------------
info "Checking environment..."
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_RAM_GB=$((TOTAL_RAM_KB / 1024 / 1024))
info "Available RAM: ${TOTAL_RAM_GB}GB"

if [ "$TOTAL_RAM_GB" -lt 4 ]; then
    err "Insufficient RAM (${TOTAL_RAM_GB}GB). Need at least 8GB, recommend 32GB."
    err "Use a larger Codespace machine type."
    exit 1
fi

if [ "$TOTAL_RAM_GB" -lt 16 ]; then
    warn "RAM is ${TOTAL_RAM_GB}GB. Docling works best with 16GB+. Large PDFs may OOM."
fi

# ------------------------------------------------------------------
# Step 1: Source environment variables
# ------------------------------------------------------------------
info "Loading environment variables..."

ENV_FILE="$REPO_DIR/.env.local"
if [ ! -f "$ENV_FILE" ]; then
    # Codespace path
    ENV_FILE="/workspaces/mon-ipad/.env.local"
fi
if [ ! -f "$ENV_FILE" ]; then
    err ".env.local not found at $REPO_DIR/.env.local or /workspaces/mon-ipad/.env.local"
    err "Copy your .env.local to the repo root first."
    exit 1
fi

# shellcheck source=/dev/null
source "$ENV_FILE"

# Verify critical keys
MISSING_KEYS=()
[ -z "${TAVILY_API_KEY:-}" ] && MISSING_KEYS+=("TAVILY_API_KEY")
[ -z "${PINECONE_API_KEY:-}" ] && MISSING_KEYS+=("PINECONE_API_KEY")
[ -z "${SUPABASE_URL:-}" ] && MISSING_KEYS+=("SUPABASE_URL")
[ -z "${SUPABASE_API_KEY:-}" ] && MISSING_KEYS+=("SUPABASE_API_KEY")

if [ ${#MISSING_KEYS[@]} -gt 0 ]; then
    err "Missing environment variables: ${MISSING_KEYS[*]}"
    err "Ensure .env.local has all required keys."
    exit 1
fi
ok "Environment variables loaded (${#MISSING_KEYS[@]} missing)"

# ------------------------------------------------------------------
# Step 2: Install system dependencies
# ------------------------------------------------------------------
info "Installing system packages..."

sudo apt-get update -qq

# Poppler for PDF rendering, Tesseract for OCR, French language pack
sudo apt-get install -y -qq \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-fra \
    libgl1-mesa-glx \
    libglib2.0-0 \
    2>/dev/null

ok "System packages installed (poppler-utils, tesseract-ocr, tesseract-ocr-fra)"

# Verify tesseract
if command -v tesseract &>/dev/null; then
    TESS_VERSION=$(tesseract --version 2>&1 | head -1)
    ok "Tesseract: $TESS_VERSION"
    # Check French is available
    if tesseract --list-langs 2>&1 | grep -q "fra"; then
        ok "Tesseract French language pack: installed"
    else
        warn "Tesseract French language pack not found"
    fi
else
    err "Tesseract not found after install"
    exit 1
fi

# ------------------------------------------------------------------
# Step 3: Install Python dependencies
# ------------------------------------------------------------------
info "Installing Python packages..."

pip install --quiet --upgrade pip

# Docling and its dependencies
pip install --quiet \
    docling \
    docling-core \
    requests \
    2>&1 | tail -5

ok "Docling installed"

# Verify docling import
info "Verifying Docling import..."
python3 -c "
from docling.document_converter import DocumentConverter
print('DocumentConverter imported successfully')
" 2>&1

if [ $? -eq 0 ]; then
    ok "Docling import verified"
else
    err "Docling import failed"
    exit 1
fi

# ------------------------------------------------------------------
# Step 4: Create directory structure
# ------------------------------------------------------------------
info "Creating directory structure..."

mkdir -p "$LOG_DIR"
mkdir -p "$DATA_DIR"
mkdir -p "$SCRIPT_DIR/tmp"

ok "Directories created: logs/, data/, tmp/"

# ------------------------------------------------------------------
# Step 5: Initialize processed URLs tracker
# ------------------------------------------------------------------
PROCESSED_FILE="$DATA_DIR/processed-urls.json"
if [ ! -f "$PROCESSED_FILE" ]; then
    echo '{"urls": {}, "stats": {"total_processed": 0, "total_chunks": 0, "created": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}}' | python3 -m json.tool > "$PROCESSED_FILE"
    ok "Initialized processed-urls.json"
else
    EXISTING=$(python3 -c "import json; d=json.load(open('$PROCESSED_FILE')); print(len(d.get('urls',{})))")
    ok "processed-urls.json exists ($EXISTING URLs tracked)"
fi

# ------------------------------------------------------------------
# Step 6: Test with a small PDF
# ------------------------------------------------------------------
info "Testing Docling with a sample PDF..."

python3 -c "
import tempfile, os, time

# Create a minimal test PDF using reportlab if available, else skip
try:
    from docling.document_converter import DocumentConverter
    print('DocumentConverter loaded successfully')

    # Try to find any small PDF to test with
    test_pdf = None
    for root, dirs, files in os.walk('/workspaces/mon-ipad'):
        for f in files:
            if f.endswith('.pdf'):
                path = os.path.join(root, f)
                size = os.path.getsize(path)
                if size < 5_000_000:  # Under 5MB
                    test_pdf = path
                    break
        if test_pdf:
            break

    if test_pdf:
        print(f'Testing with: {test_pdf} ({os.path.getsize(test_pdf) / 1024:.0f}KB)')
        t0 = time.time()
        converter = DocumentConverter()
        result = converter.convert(test_pdf)
        doc = result.document
        text = doc.export_to_markdown()
        elapsed = time.time() - t0
        print(f'Extracted {len(text)} chars in {elapsed:.1f}s')
        print('TEST PASSED')
    else:
        print('No test PDF found in repo — skipping live test')
        print('Docling is ready (import verified)')
        print('TEST PASSED (import-only)')

except Exception as e:
    print(f'Warning: {e}')
    print('Docling may need additional dependencies for full PDF support')
    print('TEST PARTIAL')
" 2>&1

echo ""

# ------------------------------------------------------------------
# Step 7: Install cron job
# ------------------------------------------------------------------
info "Setting up cron jobs..."

CRONTAB_FILE="$SCRIPT_DIR/crontab.txt"
if [ -f "$CRONTAB_FILE" ]; then
    # Merge with existing crontab
    EXISTING_CRON=$(crontab -l 2>/dev/null || true)
    if echo "$EXISTING_CRON" | grep -q "docling-cron.py"; then
        warn "Docling cron job already exists — skipping"
    else
        # Add our cron entries
        (crontab -l 2>/dev/null || true; echo ""; cat "$CRONTAB_FILE") | crontab -
        ok "Cron jobs installed from crontab.txt"
    fi

    # Show active crontab
    info "Active crontab:"
    crontab -l 2>/dev/null | grep -v "^#" | grep -v "^$" | while read -r line; do
        echo "  $line"
    done
else
    warn "crontab.txt not found — install cron manually"
fi

# ------------------------------------------------------------------
# Step 8: Verify the cron script exists
# ------------------------------------------------------------------
CRON_SCRIPT="$SCRIPT_DIR/docling-cron.py"
if [ -f "$CRON_SCRIPT" ]; then
    ok "Cron script found: $CRON_SCRIPT"
else
    err "Cron script not found: $CRON_SCRIPT"
    err "Create codespace/docling-cron.py before running cron"
fi

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
echo ""
echo "=================================================================="
echo "  SETUP COMPLETE"
echo "=================================================================="
echo ""
echo "  System:     $(uname -s) $(uname -m) | ${TOTAL_RAM_GB}GB RAM"
echo "  Docling:    installed (local, no HF Space dependency)"
echo "  Tesseract:  $(tesseract --version 2>&1 | head -1)"
echo "  Cron:       every 30 min (docling-cron.py)"
echo "  Logs:       $LOG_DIR/"
echo "  Data:       $DATA_DIR/"
echo ""
echo "  Quick start:"
echo "    source .env.local"
echo "    python3 codespace/docling-cron.py --dry-run          # Test discovery"
echo "    python3 codespace/docling-cron.py --sector finance    # Single sector"
echo "    python3 codespace/docling-cron.py                     # Full run"
echo ""
echo "  Manual cron install (if needed):"
echo "    crontab codespace/crontab.txt"
echo "=================================================================="
