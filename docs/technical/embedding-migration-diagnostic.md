# Diagnostic Complet - Migration Embeddings & Dimensions

**Date:** 2026-02-12  
**Statut:** 🔴 CRITIQUE - Migration non effectuée  
**Auteur:** Claude Code

---

## 📊 État Actuel des Embeddings

### Pinecone Index: sota-rag

| Métrique | Valeur | Statut |
|----------|--------|--------|
| **Dimension** | 1536 | ❌ Legacy (OpenAI) |
| **Total vecteurs** | 10,411 | ✅ |
| **Namespaces** | 12 | ✅ |
| **Modèle** | text-embedding-3-small (supposé) | ❌ Non confirmé |

### Namespaces détaillés

| Namespace | Vecteurs | Dataset Phase |
|-----------|----------|---------------|
| (default) | 639 | Phase 1 |
| benchmark-asqa | 948 | Phase 1+ |
| benchmark-finqa | 500 | **Phase 2** |
| benchmark-frames | 824 | Phase 1+ |
| benchmark-hotpotqa | 1,000 | Phase 1+2 |
| benchmark-msmarco | 1,000 | Phase 1+2 |
| benchmark-narrativeqa | 1,000 | Phase 1+ |
| benchmark-natural_questions | 1,000 | Phase 1+ |
| benchmark-popqa | 1,000 | Phase 1+ |
| benchmark-pubmedqa | 500 | **Phase 2** |
| benchmark-squad_v2 | 1,000 | Phase 1+ |
| benchmark-triviaqa | 1,000 | Phase 1+ |

---

## 🔴 Problèmes Identifiés

### 1. Mismatch de Dimensions (CRITIQUE)

```
┌─────────────────────────────────────────────────────────────┐
│  PROBLÈME DE DIMENSION                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Requête utilisateur                                        │
│       ↓                                                     │
│  HyDE Generator (LLM)                                       │
│       ↓                                                     │
│  Embedding Generator                                        │
│       ↓                                                     │
│  ┌─────────────────────┐    ┌──────────────────────────┐   │
│  │ Modèle actuel n8n   │    │ Index Pinecone           │   │
│  │ - Jina: 1024d       │ VS │ - OpenAI legacy: 1536d   │   │
│  │ - Cohere: 1024d     │    │                          │   │
│  └─────────────────────┘    └──────────────────────────┘   │
│       ↓                                    ↓                │
│  EMBEDDING 1024d                    VECTEURS 1536d          │
│                                                             │
│  RÉSULTAT: AUCUN MATCH ou scores < 0.1                      │
└─────────────────────────────────────────────────────────────┘
```

### 2. Conséquences sur les Workflows

| Workflow | Impact | Symptôme observé |
|----------|--------|------------------|
| **Standard RAG** | 🔴 Critique | "No item to return" - Pinecone retourne 0 résultats |
| **Graph RAG** | 🔴 Critique | Documents retrieved hors sujet (score < 0.4) |
| **Quantitative** | 🟡 Mineur | Utilise Supabase SQL, pas d'impact direct |
| **Orchestrator** | 🔴 Critique | Routage vers Standard échoue silencieusement |

### 3. Exécution Graph RAG analysée (ID#19305)

**Question:** "What disease is caused by mosquitoes?"

**Résultat Pinecone HyDE Search:**
```json
{
  "matches": [
    {
      "id": "climate-00018-1a18d37c-chunk-0",
      "score": 0.346,
      "content": "Climate Claim: Climate change affects human health..."
    },
    {
      "id": "msmarco-00004-14493533-chunk-0",
      "score": 0.315,
      "content": "Query: how do vaccines work..."
    }
  ]
}
```

**🔴 PROBLÈME:** Les documents retournés sont sur le changement climatique et les vaccins, alors que la question porte sur les moustiques et les maladies !

---

## 🎯 Configuration Attendue

### Cible: Cohere embed-english-v3.0

| Paramètre | Actuel | Cible | Action |
|-----------|--------|-------|--------|
| **Modèle** | OpenAI (?) / Jina | Cohere embed-english-v3.0 | Migrer |
| **Dimensions** | 1536 | 1024 | Recréer index |
| **Index name** | sota-rag | sota-rag-cohere-1024 | Nouvel index |
| **n8n var** | EMBEDDING_MODEL | cohere/embed-english-v3.0 | Mettre à jour |

### Alternative: Jina AI

| Paramètre | Valeur |
|-----------|--------|
| **Modèle** | jina-embeddings-v3 |
| **Dimensions** | 1024 |
| **Limite gratuite** | 10M tokens/mois |
| **Avantage** | Déjà utilisé dans MCP server |

---

## 📋 Scripts de Migration Disponibles

### Option 1: Migration Cohere (Recommandée)

**Fichier:** `db/populate/migrate_to_cohere.py`

```bash
# Configuration requise
export PINECONE_API_KEY="pcsk_..."
export COHERE_API_KEY="votre_cle_cohere"
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"

# Dry run (prévisualisation)
python3 db/populate/migrate_to_cohere.py --dry-run

# Migration complète
cd /home/termius/mon-ipad
python3 db/populate/migrate_to_cohere.py

# Migration d'un seul namespace
python3 db/populate/migrate_to_cohere.py --namespace benchmark-triviaqa
```

**Processus:**
1. Liste tous les IDs de vecteurs (1536d)
2. Extrait le texte des métadonnées
3. Re-embed avec Cohere (1024d)
4. Upsert vers nouvel index

**Temps estimé:** ~2-3 heures pour 10,411 vecteurs

### Option 2: Setup Fresh (Alternative)

**Fichier:** `db/populate/setup_embeddings.py`

```bash
# Configuration
export PINECONE_API_KEY="pcsk_..."
export JINA_API_KEY="jina_..."  # ou COHERE_API_KEY
export N8N_API_KEY="eyJhb..."

# Créer nouvel index avec Jina
python3 db/populate/setup_embeddings.py --provider jina --phase 2

# Ou avec Cohere
python3 db/populate/setup_embeddings.py --provider openrouter --phase 2
```

---

## 🔧 Prochaines Étapes Concrètes

### ÉTAPE 1: Sauvegarde (CRITIQUE)
```bash
# Exporter les données actuelles
python3 -c "
import json
# Script d'export des métadonnées Pinecone
"
```

### ÉTAPE 2: Obtenir Clé Cohere
1. Aller sur https://cohere.com/
2. Créer un compte / se connecter
3. Générer une API key (gratuit: 10K calls/mois)
4. Ajouter à `docs/technical/credentials.md`

### ÉTAPE 3: Exécuter Migration
```bash
export COHERE_API_KEY="votre_nouvelle_cle"
export PINECONE_API_KEY="pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"

cd /home/termius/mon-ipad
python3 db/populate/migrate_to_cohere.py --dry-run

# Si OK:
python3 db/populate/migrate_to_cohere.py
```

### ÉTAPE 4: Mettre à jour n8n
```bash
# Via API n8n
export N8N_API_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
export N8N_HOST="https://amoret.app.n8n.cloud"

# Mettre à jour les variables
curl -X POST "${N8N_HOST}/api/v1/variables" \
  -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "EMBEDDING_MODEL",
    "value": "cohere/embed-english-v3.0"
  }'

curl -X POST "${N8N_HOST}/api/v1/variables" \
  -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "PINECONE_URL",
    "value": "https://sota-rag-cohere-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
  }'
```

### ÉTAPE 5: Tester
```bash
# Test 1: Vérifier dimension
python3 verify_pinecone_dims.py

# Test 2: Test pipeline Standard
curl -X POST "https://amoret.app.n8n.cloud/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the capital of Japan?"}'

# Test 3: Node analysis
python3 eval/node-analyzer.py --pipeline standard --last 3
```

---

## 📁 Fichiers de Référence

| Fichier | Description |
|---------|-------------|
| `db/populate/migrate_to_cohere.py` | Script de migration 1536d → 1024d |
| `db/populate/setup_embeddings.py` | Setup fresh avec Jina/Cohere |
| `verify_pinecone_dims.py` | Vérification des dimensions |
| `docs/technical/credentials.md` | Clés API (à mettre à jour) |
| `docs/technical/mcp-setup.md` | Configuration MCP servers |

---

## ⚠️ Risques et Mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Rate limit Cohere | Moyen | Migration lente | Batch size 96, pause 1s |
| Clé Cohere invalide | Faible | Migration échoue | Tester clé avant |
| Perte de données | Faible | Critique | Export métadonnées avant |
| Workflows cassés | Moyen | Haut | Tester chaque workflow post-migration |

---

## 📊 Timeline Estimée

| Tâche | Durée |
|-------|-------|
| Sauvegarde données | 15 min |
| Obtenir clé Cohere | 10 min |
| Migration (dry-run) | 20 min |
| Migration (full) | 2-3 heures |
| Update n8n variables | 10 min |
| Tests pipelines | 30 min |
| **TOTAL** | **~4 heures** |

---

## ✅ Checklist Pré-Migration

- [ ] Exporter métadonnées Pinecone
- [ ] Obtenir clé API Cohere
- [ ] Vérifier quota Cohere (10K calls/mois gratuit)
- [ ] Notifier équipe (maintenance 4h)
- [ ] Sauvegarder config n8n actuelle
- [ ] Prévoir rollback (garder index 1536d)

---

*Document créé automatiquement - Dernière mise à jour: 2026-02-12*
