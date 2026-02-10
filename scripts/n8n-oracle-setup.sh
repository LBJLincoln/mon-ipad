#!/bin/bash
# =============================================================
# n8n Self-Hosted Auto-Setup Script
# Run this on your Oracle Cloud Free Tier VM
# =============================================================
# Usage: bash scripts/n8n-oracle-setup.sh
# Prerequisites: SSH access to Oracle VM, Ubuntu 22.04+
# =============================================================

set -e

echo "=========================================="
echo "  n8n Self-Hosted Setup — Oracle Cloud"
echo "=========================================="

# --- 1. Install Docker ---
echo ""
echo "[1/6] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "Docker installed. You may need to log out and back in."
else
    echo "Docker already installed: $(docker --version)"
fi

# --- 2. Install docker-compose ---
echo ""
echo "[2/6] Installing docker-compose..."
if ! command -v docker-compose &> /dev/null; then
    sudo apt-get install -y docker-compose
    echo "docker-compose installed."
else
    echo "docker-compose already installed."
fi

# --- 3. Open firewall ports ---
echo ""
echo "[3/6] Configuring firewall..."
sudo iptables -I INPUT -p tcp --dport 5678 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || true
if command -v netfilter-persistent &> /dev/null; then
    sudo netfilter-persistent save
fi
echo "Firewall configured (ports 80, 443, 5678)."

# --- 4. Create n8n directory and docker-compose ---
echo ""
echo "[4/6] Creating n8n configuration..."
mkdir -p ~/n8n
cat > ~/n8n/docker-compose.yml << 'COMPOSE_EOF'
version: '3'
services:
  n8n:
    image: n8nio/n8n:latest
    restart: always
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=SotaRAG2026!
      - N8N_HOST=0.0.0.0
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - N8N_ENCRYPTION_KEY=sota-rag-2026-encryption-key-change-me
      - EXECUTIONS_DATA_SAVE_ON_ERROR=all
      - EXECUTIONS_DATA_SAVE_ON_SUCCESS=all
      - EXECUTIONS_DATA_SAVE_ON_PROGRESS=true
      - EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS=true
      - N8N_METRICS=true
    volumes:
      - ./data:/home/node/.n8n
      - ./files:/files

  redis:
    image: redis:alpine
    restart: always
    ports:
      - "6379:6379"
    volumes:
      - ./redis-data:/data
    command: redis-server --maxmemory 100mb --maxmemory-policy allkeys-lru

COMPOSE_EOF

echo "docker-compose.yml created at ~/n8n/"

# --- 5. Start n8n ---
echo ""
echo "[5/6] Starting n8n..."
cd ~/n8n
docker-compose up -d
sleep 5

# Check if running
if docker-compose ps | grep -q "Up"; then
    echo "n8n is running!"
else
    echo "WARNING: n8n may not have started correctly. Check: docker-compose logs -f"
fi

# --- 6. Import workflows ---
echo ""
echo "[6/6] Setup complete!"
echo ""
echo "=========================================="
echo "  NEXT STEPS"
echo "=========================================="
echo ""
echo "1. Access n8n at: http://$(hostname -I | awk '{print $1}'):5678"
echo "   Login: admin / SotaRAG2026!"
echo ""
echo "2. Generate an API key in n8n:"
echo "   Settings > API > Create API Key"
echo ""
echo "3. Import workflows from the repo:"
echo "   export N8N_HOST=http://localhost:5678"
echo "   export N8N_API_KEY=<your-new-api-key>"
echo ""
echo "   # Import each workflow:"
echo "   for wf in ~/mon-ipad/workflows/live/*.json; do"
echo "     curl -s -X POST \$N8N_HOST/api/v1/workflows \\"
echo "       -H \"X-N8N-API-KEY: \$N8N_API_KEY\" \\"
echo "       -H \"Content-Type: application/json\" \\"
echo "       -d @\"\$wf\""
echo "   done"
echo ""
echo "4. Configure credentials in n8n UI:"
echo "   - OpenRouter: Header Auth (Authorization: Bearer sk-or-v1-...)"
echo "   - Pinecone: API Key"
echo "   - Neo4j: Bolt URL + password"
echo "   - Supabase: URL + API key"
echo "   - Jina: API Key"
echo ""
echo "5. Update the repo credentials:"
echo "   - docs/technical/credentials.md"
echo "   - .claude/settings.json"
echo "   - CLAUDE.md"
echo ""
echo "6. Test:"
echo "   python3 eval/quick-test.py --questions 1"
echo ""
echo "=========================================="
