#!/bin/bash
set -e

echo "=== Nomos42 Paperclip Orchestrator ==="
echo "Starting Paperclip server on port ${PORT:-7860}..."

# Import company config if exists
if [ -f /app/data/company.json ]; then
    echo "Loading Nomos42 company config..."
fi

# Start Paperclip with HF Space port
cd /app
exec pnpm start --port ${PORT:-7860}
