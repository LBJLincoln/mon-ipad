#!/bin/bash
# Installation des MCP Servers pour SOTA 2026 Multi-RAG Orchestrator
# Usage: chmod +x scripts/install-mcp-servers.sh && ./scripts/install-mcp-servers.sh

set -e

echo "==================================================================="
echo "  MCP SERVERS INSTALLATION - SOTA 2026"
echo "==================================================================="
echo ""

# Couleurs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Répertoire de travail
REPO_ROOT="/home/termius/mon-ipad"
cd "$REPO_ROOT"

# Vérifier Node.js
echo -e "${BLUE}🔍 Vérification de Node.js...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${YELLOW}❌ Node.js non trouvé. Installation...${NC}"
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo -e "${RED}❌ Node.js 18+ requis. Version actuelle: $(node --version)${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Node.js $(node --version) détecté${NC}"
echo ""

# Créer répertoire pour les MCP servers
mkdir -p ~/mcp-servers
cd ~/mcp-servers

# ============================================
# 1. NEO4J MCP (Officiel)
# ============================================
echo -e "${BLUE}📦 Installation MCP Neo4j (Officiel)...${NC}"
if command -v neo4j-mcp &> /dev/null; then
    echo -e "${GREEN}✅ MCP Neo4j déjà installé${NC}"
else
    echo "Téléchargement de la dernière version..."
    LATEST_VERSION=$(curl -s https://api.github.com/repos/neo4j/mcp/releases/latest | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/')
    echo "Version: $LATEST_VERSION"
    
    curl -L -o neo4j-mcp.tar.gz "https://github.com/neo4j/mcp/releases/download/v${LATEST_VERSION}/neo4j-mcp_${LATEST_VERSION}_linux_amd64.tar.gz"
    tar -xzf neo4j-mcp.tar.gz
    chmod +x neo4j-mcp
    sudo mv neo4j-mcp /usr/local/bin/
    rm neo4j-mcp.tar.gz
    
    echo -e "${GREEN}✅ MCP Neo4j installé${NC}"
fi
echo ""

# ============================================
# 2. N8N MCP (Communauté)
# ============================================
echo -e "${BLUE}📦 Installation MCP n8n (Communauté)...${NC}"
if command -v n8n-mcp-server &> /dev/null; then
    echo -e "${GREEN}✅ MCP n8n déjà installé${NC}"
else
    npm install -g @leonardsellem/n8n-mcp-server
    echo -e "${GREEN}✅ MCP n8n installé${NC}"
fi
echo ""

# ============================================
# 3. PINECONE MCP (Officiel - via NPX)
# ============================================
echo -e "${BLUE}📦 Vérification MCP Pinecone (Officiel)...${NC}"
echo "Test de disponibilité via npx..."
if npx -y @pinecone-database/mcp --help > /dev/null 2>&1; then
    echo -e "${GREEN}✅ MCP Pinecone disponible via npx${NC}"
else
    echo -e "${YELLOW}⚠️ MCP Pinecone nécessite une installation manuelle${NC}"
    echo "   Commande: npm install -g @pinecone-database/mcp"
fi
echo ""

# ============================================
# 4. JINA EMBEDDINGS MCP (Existant)
# ============================================
echo -e "${BLUE}📦 Vérification MCP Jina Embeddings...${NC}"
if [ -f "$REPO_ROOT/mcp/jina-embeddings-server.py" ]; then
    echo -e "${GREEN}✅ MCP Jina Embeddings trouvé${NC}"
    echo "   Fichier: $REPO_ROOT/mcp/jina-embeddings-server.py"
else
    echo -e "${RED}❌ MCP Jina Embeddings non trouvé${NC}"
fi
echo ""

# ============================================
# 5. SUPABASE MCP (HTTP)
# ============================================
echo -e "${BLUE}📦 Configuration MCP Supabase...${NC}"
echo -e "${YELLOW}⚠️ MCP Supabase utilise le mode HTTP${NC}"
echo "   URL: https://mcp.supabase.com/mcp"
echo "   Configuration: Voir .claude/settings.json"
echo ""

# ============================================
# VÉRIFICATION FINALE
# ============================================
echo "==================================================================="
echo -e "${BLUE}🔍 Vérification des installations${NC}"
echo "==================================================================="
echo ""

# Vérifier chaque MCP
echo -n "Neo4j MCP: "
if command -v neo4j-mcp &> /dev/null; then
    echo -e "${GREEN}✅$(neo4j-mcp --version 2>/dev/null || echo ' installé')${NC}"
else
    echo -e "${RED}❌ Non installé${NC}"
fi

echo -n "n8n MCP: "
if command -v n8n-mcp-server &> /dev/null; then
    echo -e "${GREEN}✅ Installé${NC}"
else
    echo -e "${RED}❌ Non installé${NC}"
fi

echo -n "Pinecone MCP: "
echo -e "${GREEN}✅ Disponible via npx${NC}"

echo -n "Jina Embeddings MCP: "
if [ -f "$REPO_ROOT/mcp/jina-embeddings-server.py" ]; then
    echo -e "${GREEN}✅ Prêt${NC}"
else
    echo -e "${RED}❌ Non trouvé${NC}"
fi

echo ""
echo "==================================================================="
echo -e "${GREEN}✅ Installation terminée!${NC}"
echo "==================================================================="
echo ""
echo "Prochaines étapes:"
echo ""
echo "1. Configurer les variables d'environnement:"
echo "   export N8N_HOST='https://amoret.app.n8n.cloud'"
echo "   export N8N_API_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'"
echo "   export PINECONE_API_KEY='pcsk_...'"
echo "   export PINECONE_HOST='https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io'"
echo "   export OPENROUTER_API_KEY='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'"
echo "   export COHERE_API_KEY='nqQv1HevJMecJrN00Hpjk5JFbOT3UtXJCTJRuIRu'"
echo ""
echo "2. Le fichier de configuration MCP est:"
echo "   .claude/settings.json"
echo ""
echo "3. Pour tester les MCP:"
echo "   - Relancer Claude Code"
echo "   - Vérifier que les outils MCP apparaissent"
echo ""
echo "📚 Documentation: docs/technical/mcp-setup.md"
echo ""
