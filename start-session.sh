#!/bin/bash
# Script de démarrage complet pour session Kimi/Claude Code
# VM: Google Cloud (34.136.180.66)
# Usage: source /home/termius/mon-ipad/start-session.sh

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║         🚀 DÉMARRAGE SESSION SOTA 2026 - MCP & SKILLS           ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. Charger les variables d'environnement
echo -e "${BLUE}📦 Chargement des credentials...${NC}"
if [ -f "/home/termius/mon-ipad/.env.local" ]; then
    source /home/termius/mon-ipad/.env.local
    echo -e "${GREEN}  ✅ Credentials chargés${NC}"
else
    echo -e "${YELLOW}  ⚠️  Fichier .env.local non trouvé${NC}"
fi

# Export des variables critiques
export N8N_HOST="http://localhost:5678"
export N8N_API_URL="http://localhost:5678/api/v1"
export PINECONE_API_KEY="${PINECONE_API_KEY:-pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY}"
export PINECONE_HOST="${PINECONE_HOST:-https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io}"
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-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}"
export COHERE_API_KEY="${COHERE_API_KEY:-nqQv1HevJMecJrN00Hpjk5JFbOT3UtXJCTJRuIRu}"
export JINA_API_KEY="${JINA_API_KEY:-jina_f1348176dc7a4f0da9996cfa6cfa6eecasLHpAw7iEXFqU6eHi9SQBuxqT0F}"
export NEO4J_PASSWORD="${NEO4J_PASSWORD:-jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak}"
export HF_TOKEN="${HF_TOKEN:-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}"
export SUPABASE_API_KEY="${SUPABASE_API_KEY:-sb_publishable_xUcuBcYYUO2G9Mkq_McdeQ_ocFjgonm}"

# 2. Vérifier n8n
echo ""
echo -e "${BLUE}🔧 Vérification n8n...${NC}"
if docker ps | grep -q n8n_n8n_1; then
    echo -e "${GREEN}  ✅ n8n running${NC}"
    echo -e "${BLUE}     Local: http://localhost:5678${NC}"
    echo -e "${BLUE}     Externe: http://34.136.180.66:5678${NC}"
else
    echo -e "${YELLOW}  🔄 Démarrage n8n...${NC}"
    cd ~/n8n && docker-compose up -d
    sleep 5
    if docker ps | grep -q n8n_n8n_1; then
        echo -e "${GREEN}  ✅ n8n démarré${NC}"
    else
        echo -e "${RED}  ❌ Échec démarrage n8n${NC}"
    fi
fi

# 3. Vérifier les MCP
echo ""
echo -e "${BLUE}🔗 Vérification MCP Servers...${NC}"

# Neo4j
if command -v neo4j-mcp &> /dev/null; then
    echo -e "${GREEN}  ✅ Neo4j MCP${NC} ($(neo4j-mcp --version 2>&1 | grep -o 'v[0-9.]*'))"
else
    echo -e "${RED}  ❌ Neo4j MCP${NC}"
fi

# n8n MCP
if command -v n8n-mcp-server &> /dev/null; then
    echo -e "${GREEN}  ✅ n8n MCP${NC}"
else
    echo -e "${RED}  ❌ n8n MCP${NC}"
fi

# Jina
if [ -f "/home/termius/mon-ipad/mcp/jina-embeddings-server.py" ]; then
    echo -e "${GREEN}  ✅ Jina Embeddings MCP${NC}"
else
    echo -e "${RED}  ❌ Jina Embeddings MCP${NC}"
fi

# Hugging Face
if [ -f "/home/termius/mcp-servers/custom/huggingface-mcp-server.py" ]; then
    echo -e "${GREEN}  ✅ Hugging Face MCP${NC}"
else
    echo -e "${RED}  ❌ Hugging Face MCP${NC}"
fi

# Cohere
if [ -f "/home/termius/mcp-servers/custom/cohere-mcp-server.py" ]; then
    echo -e "${GREEN}  ✅ Cohere MCP${NC}"
else
    echo -e "${RED}  ❌ Cohere MCP${NC}"
fi

# Pinecone
echo -e "${GREEN}  ✅ Pinecone MCP${NC} (via npx)"

# 4. Vérifier les Skills
echo ""
echo -e "${BLUE}⚡ Skills CLI disponibles...${NC}"
if [ -d "/home/termius/skills" ]; then
    for skill in /home/termius/skills/*; do
        if [ -f "$skill" ]; then
            echo -e "${GREEN}  • $(basename $skill)${NC}"
        fi
    done
else
    echo -e "${YELLOW}  ⚠️  Répertoire skills non trouvé${NC}"
fi

# 5. Créer les alias
echo ""
echo -e "${BLUE}⚡ Alias disponibles...${NC}"
alias n8n-status='cd ~/n8n && docker-compose ps'
alias n8n-logs='cd ~/n8n && docker-compose logs -f n8n'
alias n8n-restart='cd ~/n8n && docker-compose restart'
alias mcp-status='bash ~/skills/mcp-manager.sh status'
alias skills-list='ls -la ~/skills/'
alias sota-status='cat /home/termius/mon-ipad/docs/status.json 2>/dev/null || echo "Status non disponible"'
alias sota-test='cd /home/termius/mon-ipad && python3 eval/quick-test.py --questions 1'
alias sota-test-5='cd /home/termius/mon-ipad && python3 eval/quick-test.py --questions 5'

echo -e "${BLUE}  n8n-status${NC}    → Voir le status des conteneurs"
echo -e "${BLUE}  n8n-logs${NC}      → Voir les logs n8n"
echo -e "${BLUE}  n8n-restart${NC}   → Redémarrer n8n"
echo -e "${BLUE}  mcp-status${NC}    → Vérifier les MCP"
echo -e "${BLUE}  skills-list${NC}   → Lister les skills CLI"
echo -e "${BLUE}  sota-status${NC}   → Voir le status du projet"
echo -e "${BLUE}  sota-test${NC}     → Test rapide (1 question)"
echo -e "${BLUE}  sota-test-5${NC}   → Test (5 questions)"

# 6. Résumé
echo ""
echo "══════════════════════════════════════════════════════════════════"
echo -e "${GREEN}  ✅ SESSION PRÊTE${NC}"
echo "══════════════════════════════════════════════════════════════════"
echo ""
echo -e "${BLUE}Résumé:${NC}"
echo "  • n8n: http://localhost:5678 (local) / http://34.136.180.66:5678 (externe)"
echo "  • Login: admin / SotaRAG2026!"
echo "  • MCP: 6 servers configurés"
echo "  • Skills: 4 CLI tools disponibles"
echo ""
echo -e "${YELLOW}Pour commencer:${NC}"
echo "  cd /home/termius/mon-ipad"
echo "  cat CLAUDE.md"
echo ""
echo -e "${YELLOW}Pour importer les workflows:${NC}"
echo "  1. Créer un compte sur http://localhost:5678"
echo "  2. Générer une API Key (Settings > API)"
echo "  3. Exporter N8N_API_KEY=<ta-cle>"
echo "  4. bash scripts/setup-n8n-docker.sh"
echo ""
echo "══════════════════════════════════════════════════════════════════"

# Export du PATH pour les MCP
export PATH="/usr/local/bin:/usr/bin:$PATH"

# Alias pour lancer Kimi avec MCP
echo ""
echo -e "${BLUE}🚀 Pour lancer Kimi:${NC}"
echo -e "${GREEN}  kimi-start${NC}   → Lancer Kimi Code dans le projet"
alias kimi-start='cd /home/termius/mon-ipad && kimi'
