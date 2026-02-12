#!/bin/bash
# Script de configuration complète n8n Docker
# Importe les workflows et configure les credentials

set -e

N8N_HOST="http://localhost:5678"
N8N_USER="admin"
N8N_PASS="SotaRAG2026!"
WORKFLOWS_DIR="/home/termius/mon-ipad/workflows/live"
OUTPUT_FILE="/home/termius/mon-ipad/docs/n8n-docker-workflow-ids.json"

echo "══════════════════════════════════════════════════════════════════"
echo "  🔧 CONFIGURATION AUTOMATIQUE N8N DOCKER"
echo "══════════════════════════════════════════════════════════════════"
echo ""

# Attendre que n8n soit prêt
echo "1. Attente du démarrage d'n8n..."
for i in {1..30}; do
    if curl -s http://localhost:5678/health 2>/dev/null | grep -q "ok"; then
        echo "   ✅ n8n est prêt"
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

# Obtenir le token d'authentification
echo "2. Authentification..."
AUTH_RESPONSE=$(curl -s -X POST "http://localhost:5678/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$N8N_USER\",\"password\":\"$N8N_PASS\"}" 2>/dev/null || echo "{}")

# Si auth échoue, essayer sans auth (setup initial)
if echo "$AUTH_RESPONSE" | grep -q "token"; then
    TOKEN=$(echo "$AUTH_RESPONSE" | grep -o '"token":"[^"]*"' | cut -d'"' -f4)
    echo "   ✅ Authentifié"
else
    echo "   ⚠️  Auth par défaut, setup initial nécessaire"
    TOKEN=""
fi

# Créer API Key
echo "3. Création de l'API Key..."
if [ -n "$TOKEN" ]; then
    API_KEY_RESPONSE=$(curl -s -X POST "http://localhost:5678/api/v1/api-keys" \
      -H "Content-Type: application/json" \
      -H "Cookie: n8n-auth=$TOKEN" \
      -d '{"label":"SOTA-2026-CLI"}' 2>/dev/null || echo "{}")
    
    API_KEY=$(echo "$API_KEY_RESPONSE" | grep -o '"apiKey":"[^"]*"' | cut -d'"' -f4)
    
    if [ -n "$API_KEY" ]; then
        echo "   ✅ API Key créée: ${API_KEY:0:20}..."
        echo "   IMPORTANT: Sauvegarde cette clé !"
    else
        echo "   ⚠️  Impossible de créer l'API Key automatiquement"
        echo "      Crée-la manuellement: Settings > API > Create API Key"
        API_KEY=""
    fi
else
    API_KEY=""
fi

# Importer les workflows
echo ""
echo "4. Import des workflows..."
if [ -n "$API_KEY" ]; then
    declare -A WORKFLOW_IDS
    
    for wf_file in "$WORKFLOWS_DIR"/*.json; do
        wf_name=$(basename "$wf_file" .json)
        echo -n "   → $wf_name: "
        
        # Importer le workflow
        RESPONSE=$(curl -s -X POST "$N8N_HOST/api/v1/workflows" \
          -H "X-N8N-API-KEY: $API_KEY" \
          -H "Content-Type: application/json" \
          -d @"$wf_file" 2>/dev/null || echo "{}")
        
        # Extraire l'ID
        WF_ID=$(echo "$RESPONSE" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
        
        if [ -n "$WF_ID" ]; then
            echo "✅ ID: $WF_ID"
            WORKFLOW_IDS["$wf_name"]="$WF_ID"
            
            # Activer le workflow
            curl -s -X POST "$N8N_HOST/api/v1/workflows/$WF_ID/activate" \
              -H "X-N8N-API-KEY: $API_KEY" > /dev/null 2>&1 || true
        else
            echo "❌ Échec"
        fi
    done
    
    # Sauvegarder les IDs
    echo ""
    echo "5. Sauvegarde des IDs..."
    echo "{" > "$OUTPUT_FILE"
    echo '  "host": "'$N8N_HOST'",' >> "$OUTPUT_FILE"
    echo '  "api_key": "'$API_KEY'",' >> "$OUTPUT_FILE"
    echo '  "workflows": {' >> "$OUTPUT_FILE"
    
    FIRST=true
    for name in "${!WORKFLOW_IDS[@]}"; do
        if [ "$FIRST" = true ]; then
            FIRST=false
        else
            echo "," >> "$OUTPUT_FILE"
        fi
        echo -n '    "'$name'": "'${WORKFLOW_IDS[$name]}'"' >> "$OUTPUT_FILE"
    done
    
    echo "" >> "$OUTPUT_FILE"
    echo "  }" >> "$OUTPUT_FILE"
    echo "}" >> "$OUTPUT_FILE"
    
    echo "   ✅ IDs sauvegardés dans: $OUTPUT_FILE"
    
else
    echo "   ⚠️  Pas d'API Key, import manuel nécessaire"
fi

# Créer credentials
echo ""
echo "6. Création des credentials..."
if [ -n "$API_KEY" ]; then
    # OpenRouter credential
    curl -s -X POST "$N8N_HOST/api/v1/credentials" \
      -H "X-N8N-API-KEY: $API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "name": "OpenRouter API",
        "type": "httpHeaderAuth",
        "data": {
          "name": "Authorization",
          "value": "Bearer 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"
        }
      }' > /dev/null 2>&1 && echo "   ✅ OpenRouter credential créée" || echo "   ⚠️  OpenRouter credential échouée"
    
    # Pinecone credential
    curl -s -X POST "$N8N_HOST/api/v1/credentials" \
      -H "X-N8N-API-KEY: $API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "name": "Pinecone API",
        "type": "pineconeApi",
        "data": {
          "apiKey": "pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"
        }
      }' > /dev/null 2>&1 && echo "   ✅ Pinecone credential créée" || echo "   ⚠️  Pinecone credential échouée"
    
    # Cohere credential
    curl -s -X POST "$N8N_HOST/api/v1/credentials" \
      -H "X-N8N-API-KEY: $API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "name": "Cohere API",
        "type": "cohereApi",
        "data": {
          "apiKey": "nqQv1HevJMecJrN00Hpjk5JFbOT3UtXJCTJRuIRu"
        }
      }' > /dev/null 2>&1 && echo "   ✅ Cohere credential créée" || echo "   ⚠️  Cohere credential échouée"
    
    # Variables n8n
    echo ""
    echo "7. Configuration des variables..."
    
    # EMBEDDING_MODEL
    curl -s -X POST "$N8N_HOST/api/v1/variables" \
      -H "X-N8N-API-KEY: $API_KEY" \
      -H "Content-Type: application/json" \
      -d '{"key":"EMBEDDING_MODEL","value":"jina-embeddings-v3"}' > /dev/null 2>&1 || true
    
    # EMBEDDING_DIM
    curl -s -X POST "$N8N_HOST/api/v1/variables" \
      -H "X-N8N-API-KEY: $API_KEY" \
      -H "Content-Type: application/json" \
      -d '{"key":"EMBEDDING_DIM","value":"1024"}' > /dev/null 2>&1 || true
    
    # OPENROUTER_API_KEY
    curl -s -X POST "$N8N_HOST/api/v1/variables" \
      -H "X-N8N-API-KEY: $API_KEY" \
      -H "Content-Type: application/json" \
      -d '{"key":"OPENROUTER_API_KEY","value":"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"}' > /dev/null 2>&1 || true
    
    # PINECONE_URL
    curl -s -X POST "$N8N_HOST/api/v1/variables" \
      -H "X-N8N-API-KEY: $API_KEY" \
      -H "Content-Type: application/json" \
      -d '{"key":"PINECONE_URL","value":"https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"}' > /dev/null 2>&1 || true
    
    echo "   ✅ Variables configurées"
fi

echo ""
echo "══════════════════════════════════════════════════════════════════"
echo "  ✅ CONFIGURATION TERMINÉE"
echo "══════════════════════════════════════════════════════════════════"
echo ""
echo "Résumé:"
echo "  • n8n URL: http://34.136.180.66:5678"
echo "  • Login: admin / SotaRAG2026!"
if [ -n "$API_KEY" ]; then
    echo "  • API Key: ${API_KEY:0:30}..."
    echo "  • IDs workflows: $OUTPUT_FILE"
fi
echo ""
echo "Prochaines étapes:"
echo "  1. Tester les workflows: python3 eval/quick-test.py --questions 1"
echo "  2. Vérifier les credentials dans l'UI n8n"
echo ""
