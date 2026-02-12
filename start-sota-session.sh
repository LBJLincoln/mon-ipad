#!/bin/bash
# start-sota-session.sh - Script de démarrage session SOTA 2026
# Usage: ./start-sota-session.sh

set -e

echo "🚀 Démarrage session SOTA 2026 - Phase 1 Iteration"
echo "=================================================="

# 1. Vérifier le répertoire
cd ~/mon-ipad 2>/dev/null || {
    echo "❌ Repo mon-ipad non trouvé. Clonage..."
    git clone https://github.com/LBJLincoln/mon-ipad.git ~/mon-ipad
    cd ~/mon-ipad
}

echo "📁 Repo: $(pwd)"

# 2. Mettre à jour le repo
echo "📥 Git pull..."
git pull origin main

# 3. Vérifier Node.js (requis pour MCP)
if ! command -v node &> /dev/null; then
    echo "❌ Node.js non installé. Installation..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi
echo "✅ Node.js: $(node --version)"

# 4. Créer le répertoire MCP
mkdir -p ~/.config/claude

# 5. Installer MCP Neo4j (binaire)
if ! command -v neo4j-mcp &> /dev/null; then
    echo "📦 Installation MCP Neo4j..."
    LATEST=$(curl -s https://api.github.com/repos/neo4j/mcp/releases/latest | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/')
    curl -L -o /tmp/neo4j-mcp.tar.gz "https://github.com/neo4j/mcp/releases/download/v${LATEST}/neo4j-mcp_${LATEST}_linux_amd64.tar.gz" 2>/dev/null
    tar -xzf /tmp/neo4j-mcp.tar.gz -C /tmp 2>/dev/null
    chmod +x /tmp/neo4j-mcp
    sudo mv /tmp/neo4j-mcp /usr/local/bin/ 2>/dev/null || mv /tmp/neo4j-mcp ~/bin/ 2>/dev/null || echo "⚠️  neo4j-mcp dans /tmp/neo4j-mcp"
    rm -f /tmp/neo4j-mcp.tar.gz
    echo "✅ MCP Neo4j installé"
else
    echo "✅ MCP Neo4j déjà présent"
fi

# 6. Installer MCP n8n
if ! command -v n8n-mcp-server &> /dev/null; then
    echo "📦 Installation MCP n8n..."
    npm install -g @leonardsellem/n8n-mcp-server 2>/dev/null || sudo npm install -g @leonardsellem/n8n-mcp-server
    echo "✅ MCP n8n installé"
else
    echo "✅ MCP n8n déjà présent"
fi

# 7. Créer la configuration MCP pour Claude
echo "⚙️  Configuration MCP servers..."

mkdir -p ~/.config/claude

# Récupérer les variables d'environnement ou utiliser des placeholders
NEO4J_PWD="${NEO4J_PASSWORD:-your_neo4j_password}"
N8N_KEY="${N8N_API_KEY:-your_n8n_api_key}"
PINECONE_KEY="${PINECONE_API_KEY:-your_pinecone_api_key}"

cat > ~/.config/claude/config.json << EOF
{
  "mcpServers": {
    "neo4j": {
      "command": "neo4j-mcp",
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "${NEO4J_PWD}",
        "NEO4J_DATABASE": "neo4j",
        "NEO4J_READ_ONLY": "false",
        "NEO4J_TELEMETRY": "true"
      }
    },
    "n8n": {
      "command": "n8n-mcp-server",
      "env": {
        "N8N_API_URL": "https://amoret.app.n8n.cloud/api/v1",
        "N8N_API_KEY": "${N8N_KEY}",
        "DEBUG": "false"
      }
    },
    "pinecone": {
      "command": "npx",
      "args": ["-y", "@pinecone-database/mcp"],
      "env": {
        "PINECONE_API_KEY": "${PINECONE_KEY}"
      }
    }
  }
}
EOF

echo "✅ Configuration MCP créée: ~/.config/claude/config.json"

# 8. Afficher le statut
echo ""
echo "=================================================="
echo "📊 STATUT DE LA SESSION"
echo "=================================================="

# Vérifier les variables d'environnement
echo "🔐 Variables d'environnement:"
[ -z "$SUPABASE_PASSWORD" ] && echo "  ⚠️  SUPABASE_PASSWORD: NON DÉFINI" || echo "  ✅ SUPABASE_PASSWORD: défini"
[ -z "$NEO4J_PASSWORD" ] && echo "  ⚠️  NEO4J_PASSWORD: NON DÉFINI" || echo "  ✅ NEO4J_PASSWORD: défini"
[ -z "$PINECONE_API_KEY" ] && echo "  ⚠️  PINECONE_API_KEY: NON DÉFINI" || echo "  ✅ PINECONE_API_KEY: défini"
[ -z "$N8N_API_KEY" ] && echo "  ⚠️  N8N_API_KEY: NON DÉFINI" || echo "  ✅ N8N_API_KEY: défini"
[ -z "$OPENROUTER_API_KEY" ] && echo "  ⚠️  OPENROUTER_API_KEY: NON DÉFINI" || echo "  ✅ OPENROUTER_API_KEY: défini"

echo ""
echo "📋 MCP Servers:"
command -v neo4j-mcp &> /dev/null && echo "  ✅ neo4j-mcp" || echo "  ⚠️  neo4j-mcp (dans /tmp si installé)"
command -v n8n-mcp-server &> /dev/null && echo "  ✅ n8n-mcp-server" || echo "  ⚠️  n8n-mcp-server"
echo "  ✅ pinecone-mcp (via npx)"

echo ""
echo "=================================================="
echo "🎯 COMMANDES POUR DÉMARRER"
echo "=================================================="
echo ""
echo "1. Vérifier le statut:"
echo "   cat docs/status.json"
echo ""
echo "2. Vérifier les gates Phase 1:"
echo "   python3 eval/phase_gates.py"
echo ""
echo "3. Lancer un test 1/1 (ex: Standard):"
echo "   python3 eval/quick-test.py --questions 1 --pipeline standard"
echo ""
echo "4. Analyse nodulaire (les 2 outils):"
echo "   python3 eval/node-analyzer.py --pipeline standard --last 5"
echo "   python3 analyze_n8n_executions.py --pipeline standard --limit 5"
echo ""
echo "=================================================="
echo ""
echo "✅ Session prête! Consulte docs/technical/mcp-setup.md pour plus d'infos."
echo ""
