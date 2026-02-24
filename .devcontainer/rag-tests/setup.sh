#!/bin/bash
# rag-tests Codespace bootstrap
# Supports 2 modes:
#   1. HF Space (default) — uses remote HF Space n8n
#   2. Local Docker — starts n8n + 3 workers via docker-compose
# Auto-launches 1000q eval after setup (unattended)
set -uo pipefail

echo "=== Nomos AI — rag-tests Codespace Setup ==="

REPO_ROOT="/workspaces/${localWorkspaceFolderBasename:-.}"
N8N_HOST="${N8N_HOST:-https://lbjlincoln-nomos-rag-engine.hf.space}"
EVAL_MODE="${EVAL_MODE:-hf-space}"  # hf-space or local-docker

# --- 1. Check n8n target ---
echo "[1/7] Checking n8n target (mode: ${EVAL_MODE})..."
if [ "$EVAL_MODE" = "local-docker" ]; then
  echo "  Starting local n8n Docker stack..."
  if [ -f "${REPO_ROOT}/.devcontainer/rag-tests/docker-compose.yml" ] && which docker >/dev/null 2>&1; then
    docker compose -f "${REPO_ROOT}/.devcontainer/rag-tests/docker-compose.yml" up -d 2>&1 | tail -5
    echo "  Waiting for local n8n..."
    for i in $(seq 1 60); do
      if curl -sf http://localhost:5678/healthz > /dev/null 2>&1; then
        echo "  Local n8n healthy after $((i*3))s"
        N8N_HOST="http://localhost:5678"
        break
      fi
      sleep 3
    done
    # Import workflows from n8n/live/
    echo "  Importing workflows..."
    for wf in "${REPO_ROOT}/n8n/live/"*.json; do
      [ -f "$wf" ] || continue
      # Strip credentials for clean import
      python3 -c "
import json
with open('$wf') as f: d = json.load(f)
for n in d.get('nodes',[]): n.pop('credentials',None)
for k in ['shared','tags','activeVersion','activeVersionId','versionId','versionCounter','triggerCount','pinData','meta','staticData']: d.pop(k,None)
d['active'] = False
with open('/tmp/$(basename $wf)', 'w') as f: json.dump(d, f)
" 2>/dev/null && docker exec -i $(docker ps -q -f name=n8n-1 2>/dev/null || echo "none") n8n import:workflow --input="/tmp/$(basename $wf)" 2>/dev/null && echo "    OK: $(basename $wf)" || echo "    SKIP: $(basename $wf)"
    done
  else
    echo "  WARN: Docker not available — falling back to HF Space"
    EVAL_MODE="hf-space"
    N8N_HOST="https://lbjlincoln-nomos-rag-engine.hf.space"
  fi
else
  echo "  Using HF Space: ${N8N_HOST}"
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "${N8N_HOST}/healthz" --max-time 15 2>/dev/null || echo "000")
  if [ "$CODE" = "200" ]; then
    echo "  HF Space reachable (HTTP 200)"
  else
    echo "  WARN: HF Space returned HTTP $CODE"
  fi
fi
export N8N_HOST

# --- 2. Install Python deps ---
echo "[2/7] Installing Python dependencies..."
pip install -q requests python-dotenv numpy 2>/dev/null || true

# --- 3. Verify eval scripts ---
echo "[3/7] Verifying eval scripts..."
for script in eval/quick-test.py eval/iterative-eval.py eval/run-eval-parallel.py eval/run-eval.py eval/live-writer.py; do
  if [ -f "${REPO_ROOT}/${script}" ]; then
    echo "  OK: ${script}"
  else
    echo "  MISSING: ${script}"
  fi
done

# --- 4. Verify datasets ---
echo "[4/7] Checking datasets..."
dataset_count=$(find "${REPO_ROOT}/datasets" -name "*.json" 2>/dev/null | wc -l)
echo "  Found ${dataset_count} dataset files"

# --- 5. Install Claude Code CLI ---
echo "[5/7] Installing Claude Code CLI..."
npm install -g @anthropic-ai/claude-code 2>/dev/null && echo "  claude installed" || echo "  WARN: claude install failed"

# --- 6. Check environment ---
echo "[6/7] Checking environment variables..."
python3 -c "
import os
required = ['N8N_HOST', 'OPENROUTER_API_KEY', 'JINA_API_KEY', 'PINECONE_API_KEY']
optional = ['NEO4J_URI', 'SUPABASE_PASSWORD', 'COHERE_API_KEY']
for key in required:
    val = os.environ.get(key, '')
    status = 'OK' if val else 'MISSING (required!)'
    print(f'  {key}: {status}')
for key in optional:
    val = os.environ.get(key, '')
    status = 'OK' if val else 'optional'
    print(f'  {key}: {status}')
" 2>/dev/null || true

# --- 7. Auto-launch eval (unattended mode) ---
echo "[7/7] Auto-launch evaluation..."
if [ "${AUTO_EVAL:-true}" = "true" ]; then
  echo "  Launching 1000q eval in background (auto-stop on 10 consecutive failures)..."
  cd "${REPO_ROOT}"
  source .env.local 2>/dev/null || true
  export N8N_HOST
  nohup python3 eval/run-eval-parallel.py \
    --dataset phase-2 \
    --all-parallel \
    --workers 4 \
    --batch-size 1 \
    --max "${MAX_QUESTIONS:-1000}" \
    --early-stop 10 \
    --reset \
    --label "codespace-$(hostname)-$(date +%Y%m%d-%H%M)" \
    > /tmp/eval-run.log 2>&1 &
  echo $! > /tmp/eval-run.pid
  echo "  Eval PID: $(cat /tmp/eval-run.pid)"
  echo "  Log: /tmp/eval-run.log"
  echo "  Auto-stop: 10 consecutive failures per pipeline"
else
  echo "  AUTO_EVAL=false — skipping auto-launch"
  echo "  Run manually: python3 eval/run-eval-parallel.py --dataset phase-2 --all-parallel --workers 4"
fi

echo ""
echo "=== Setup complete ==="
echo "  N8N target: ${N8N_HOST}"
echo "  Mode:       ${EVAL_MODE}"
echo "  Eval:       $([ -f /tmp/eval-run.pid ] && echo 'RUNNING (PID '$(cat /tmp/eval-run.pid)')' || echo 'NOT STARTED')"
echo ""
echo "Monitor: tail -f /tmp/eval-run.log"
echo "Stop:    kill \$(cat /tmp/eval-run.pid)"
