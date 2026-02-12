#!/bin/bash
# Script de démarrage pour la prochaine session Kimi / Claude Code
# VM: Google Cloud (34.136.180.66)
# Date: 2026-02-12

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║         🚀 DÉMARRAGE SESSION SOTA 2026 - MCP & SKILLS           ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# 1. Vérifier les MCP
echo "📦 Vérification des MCP Servers..."
which neo4j-mcp > /dev/null && echo "  ✅ Neo4j MCP" || echo "  ❌ Neo4j MCP"
which n8n-mcp-server > /dev/null && echo "  ✅ n8n MCP" || echo "  ❌ n8n MCP"

# 2. Vérifier n8n
echo ""
echo "🔧 Vérification n8n..."
if docker ps | grep -q n8n_n8n_1; then
    echo "  ✅ n8n running: http://34.136.180.66:5678"
else
    echo "  🔄 Démarrage n8n..."
    cd ~/n8n && docker-compose up -d
fi

# 3. Exporter les variables
echo ""
echo "🔑 Export des credentials..."
export N8N_HOST="http://34.136.180.66:5678"
export N8N_API_KEY=""
export PINECONE_API_KEY="pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export OPENROUTER_API_KEY="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"
export COHERE_API_KEY="nqQv1HevJMecJrN00Hpjk5JFbOT3UtXJCTJRuIRu"
export JINA_API_KEY="jina_f1348176dc7a4f0da9996cfa6cfa6eecasLHpAw7iEXFqU6eHi9SQBuxqT0F"
export NEO4J_PASSWORD="jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak"
export SUPABASE_PASSWORD="udVECdcSnkMCAPiY"

echo "  ✅ Variables exportées"

# 4. Alias utiles
echo ""
echo "⚡ Alias disponibles:"
echo "  n8n-status    → Voir le status des conteneurs"
echo "  n8n-logs      → Voir les logs n8n"
echo "  mcp-status    → Vérifier les MCP"
echo "  skills-list   → Lister les skills CLI"
echo ""

alias n8n-status='cd ~/n8n && docker-compose ps'
alias n8n-logs='cd ~/n8n && docker-compose logs -f n8n'
alias mcp-status='bash ~/skills/mcp-manager.sh status'
alias skills-list='ls -la ~/skills/'

echo "══════════════════════════════════════════════════════════════════"
echo "  ✅ SESSION PRÊTE"
echo "══════════════════════════════════════════════════════════════════"
echo ""
echo "Rappels:"
echo "  • n8n URL: http://34.136.180.66:5678"
echo "  • n8n Login: admin / SotaRAG2026!"
echo "  • Générer API Key dans Settings > API"
echo "  • Puis importer les workflows depuis ~/mon-ipad/workflows/live/"
echo ""
echo "Pour commencer:"
echo "  cd /home/termius/mon-ipad && cat CLAUDE.md"
