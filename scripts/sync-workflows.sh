#!/bin/bash
# =============================================================================
# Nomos AI — Workflow Sync (run from mon-ipad VM)
# Exports latest workflow JSONs from VM n8n and ensures satellites have them
# =============================================================================
set -euo pipefail

N8N_HOST="${N8N_HOST:-https://lbjlincoln-nomos-rag-engine.hf.space}"
LIVE_DIR="/home/termius/mon-ipad/n8n/live"
SNAPSHOT_DIR="/home/termius/mon-ipad/snapshot/current"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'

echo -e "${BLUE}=== Nomos AI — Workflow Sync ===${NC}"

# --- 1. Export from n8n API ---
echo -e "${BLUE}[1/4] Exporting workflows from n8n (${N8N_HOST})...${NC}"

# Load API key
if [ -f /home/termius/mon-ipad/.env.local ]; then
  source /home/termius/mon-ipad/.env.local
fi

API_KEY="${N8N_API_KEY:-}"
if [ -z "$API_KEY" ]; then
  echo -e "${RED}ERROR: N8N_API_KEY not set${NC}"
  exit 1
fi

# Workflow mapping: name -> filename
declare -A WORKFLOWS=(
  ["TmgyRP20N4JFd9CB"]="standard.json"
  ["6257AfT1l4FMC6lY"]="graph.json"
  ["e465W7V9Q8uK6zJE"]="quantitative.json"
  ["aGsYnJY9nNCaTM82"]="orchestrator.json"
  ["15sUKy5lGL4rYW0L"]="ingestion.json"
  ["9V2UTVRbf4OJXPto"]="enrichment.json"
  ["F70g14jMxIGCZnFz"]="feedback.json"
  ["LKZO1QQY9jvBltP0"]="benchmark.json"
)

exported=0
for wf_id in "${!WORKFLOWS[@]}"; do
  filename="${WORKFLOWS[$wf_id]}"
  output="${LIVE_DIR}/${filename}"

  result=$(curl -sf "${N8N_HOST}/api/v1/workflows/${wf_id}" \
    -H "X-N8N-API-KEY: ${API_KEY}" 2>/dev/null)

  if [ -n "$result" ]; then
    echo "$result" > "$output"
    echo -e "  ${GREEN}Exported: ${filename}${NC} (${wf_id})"
    exported=$((exported + 1))
  else
    echo -e "  ${YELLOW}SKIP: ${filename} (${wf_id}) — not found or API error${NC}"
  fi
done
echo "  Exported: ${exported}/${#WORKFLOWS[@]} workflows"

# --- 2. Copy to snapshot/current ---
echo -e "${BLUE}[2/4] Updating snapshot/current...${NC}"
for pipeline in standard graph quantitative orchestrator; do
  if [ -f "${LIVE_DIR}/${pipeline}.json" ]; then
    cp "${LIVE_DIR}/${pipeline}.json" "${SNAPSHOT_DIR}/${pipeline}.json"
    echo -e "  ${GREEN}Synced: ${pipeline}.json${NC}"
  fi
done

# --- 3. Show workflow versions ---
echo -e "${BLUE}[3/4] Workflow versions:${NC}"
for filename in standard.json graph.json quantitative.json orchestrator.json ingestion.json enrichment.json; do
  if [ -f "${LIVE_DIR}/${filename}" ]; then
    size=$(stat -c%s "${LIVE_DIR}/${filename}" 2>/dev/null || echo "?")
    modified=$(stat -c%y "${LIVE_DIR}/${filename}" 2>/dev/null | cut -d. -f1 || echo "?")
    echo "  ${filename}: ${size} bytes (${modified})"
  fi
done

# --- 4. Show which repos need which workflows ---
echo -e "${BLUE}[4/4] Workflow distribution:${NC}"
echo "  rag-website:        standard, graph, quantitative, orchestrator + feedback, benchmark"
echo "  rag-tests:          (uses VM n8n directly — no local workflows)"
echo "  rag-data-ingestion: ingestion, enrichment"
echo "  rag-dashboard:      (no workflows — read-only)"
echo ""
echo -e "${GREEN}Sync complete.${NC} Push to repos with: bash scripts/deploy-codespaces.sh push-all"
