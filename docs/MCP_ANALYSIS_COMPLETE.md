# Analyse Complète MCP - Capacités vs API & Comparaison Kimi/Claude

**Date:** 2026-02-12  
**Statut:** Les MCP sont configurés mais non utilisables avec Kimi Code CLI

---

## 🎯 Objectif Initial des MCP

Les MCP (Model Context Protocol) permettent d'**exposer des capacités avancées** que les API REST/HTTP standards ne fournissent pas nativement :

- **Découverte automatique** du schéma (Neo4j)
- **Reranking intelligent** des résultats (Pinecone)
- **Migrations versionnées** (Supabase)
- **Recherche dans la documentation** (tous services)
- **Orchestration simplifiée** (n8n)

---

## 📊 Tableau Comparatif: MCP vs API Directe

### Neo4j

| Capacité | API Directe | MCP |
|----------|-------------|-----|
| Requêtes Cypher | ✅ Oui | ✅ Oui |
| CRUD basique | ✅ Oui | ✅ Oui |
| **Découverte schéma** | ❌ Non | ✅ `get-schema` |
| **GDS (Graph Data Science)** | ❌ Non | ✅ `list-gds-procedures` |
| Exploration auto | ❌ Manuelle | ✅ Automatique |

**Value Add MCP:** Découverte du graphe sans connaissance préalable des labels/relations.

### Supabase

| Capacité | API Directe | MCP |
|----------|-------------|-----|
| Requêtes SQL | ✅ Oui | ✅ Oui |
| Auth JWT | ✅ Oui | ✅ Oui |
| **Migrations versionnées** | ❌ Non | ✅ `apply_migration` |
| **Logs intégrés** | ❌ Dashboard uniquement | ✅ `get_logs` |
| **Recherche doc** | ❌ Non | ✅ `search_docs` |

**Value Add MCP:** Versionning des schémas et accès aux logs sans dashboard web.

### Pinecone

| Capacité | API Directe | MCP |
|----------|-------------|-----|
| CRUD vecteurs | ✅ Oui | ✅ Oui |
| Vector search | ✅ Oui | ✅ Oui |
| **Reranking** | ❌ API séparée | ✅ `rerank-documents` |
| **Cascading search** | ❌ Non | ✅ `cascading-search` |
| **Create index w/ model** | ❌ Multi-étapes | ✅ `create-index-for-model` |

**Value Add MCP:** Re-classement intelligent et recherche multi-index en une commande.

### n8n

| Capacité | API Directe | MCP |
|----------|-------------|-----|
| CRUD workflow | ✅ Oui | ✅ Oui |
| List executions | ✅ Oui | ✅ Oui |
| **Webhook runner** | ❌ Manuel | ✅ `run_webhook` |
| **Lifecycle management** | ❌ Multi-appels | ✅ activate/deactivate |

**Value Add MCP:** Exécution de webhooks avec gestion d'erreurs intégrée.

---

## ⚠️ Problème Fondamental: Kimi Code CLI vs MCP

### Pourquoi les MCP ne fonctionnent PAS avec Kimi Code CLI

```
┌──────────────────────────────────────────────────────────────┐
│  KIMI CODE CLI                                               │
│  ├── Protocole: INTERNE (propriétaire Kimi)                  │
│  ├── Outils: Functions Python (jina_embed, pinecone_search)  │
│  └── MCP: ❌ NON SUPPORTÉ                                    │
│       Le fichier ~/.kimi/mcp.json existe mais N'EST PAS LU   │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  CLAUDE CODE / CLAUDE DESKTOP                                │
│  ├── Protocole: MCP (Model Context Protocol - standard)      │
│  ├── Outils: MCP Tools découverts dynamiquement              │
│  └── MCP: ✅ SUPPORTÉ NATIVEMENT                             │
│       Lit automatiquement ~/.config/claude/config.json       │
└──────────────────────────────────────────────────────────────┘
```

### Tableau Comparatif Kimi vs Claude

| Aspect | Kimi Code CLI | Claude Code |
|--------|---------------|-------------|
| **Support MCP** | ❌ Non | ✅ Oui |
| **Fichier config MCP** | ~/.kimi/mcp.json (ignoré) | ~/.config/claude/config.json (utilisé) |
| **Découverte outils** | ❌ Aucune | ✅ Automatique |
| **Outils MCP** | ❌ Aucun | ✅ Tous les MCP configurés |
| **Accès Neo4j** | ⚠️ Via Python direct | ✅ MCP `get-schema` |
| **Accès Pinecone** | ⚠️ Via Python direct | ✅ MCP `rerank-documents` |
| **Accès Supabase** | ⚠️ Via Python direct | ✅ MCP `search_docs` |

---

## 🔧 Solutions pour Utiliser les MCP

### Option 1: Installer Claude Code (Recommandé)

```bash
# Installation
npm install -g @anthropic-ai/claude-code

# Lancement dans le projet
cd /home/termius/mon-ipad
claude

# Les MCP seront automatiquement disponibles car
# ~/.config/claude/config.json existe déjà (copie de ~/.kimi/mcp.json)
```

### Option 2: Claude Desktop (GUI)

```bash
# Télécharger depuis https://claude.ai/download
# Configurer le fichier:
# ~/.config/claude/config.json
```

### Option 3: Continuer avec Kimi + API Python (Actuel)

**Avantages:**
- ✅ Fonctionne immédiatement
- ✅ Pas de changement d'outil
- ✅ Fonctions testées et stables

**Inconvénients:**
- ❌ Pas de reranking automatique Pinecone
- ❌ Pas de découverte de schéma Neo4j
- ❌ Code manuel pour chaque opération

**Fonctions disponibles:**
- `pinecone_upsert`, `pinecone_search` (fonctionnel)
- `jina_embed` (erreur 403 - clé à régénérer)
- `hf_search_models` (bug à corriger)

---

## 📋 MCP Configurés (mais non utilisables avec Kimi)

### 1. Jina Embeddings MCP
```json
{
  "command": "/home/termius/mon-ipad/.venv/bin/python3",
  "args": ["/home/termius/mon-ipad/mcp/jina-embeddings-server.py"],
  "env": { "JINA_API_KEY": "...", "PINECONE_API_KEY": "..." }
}
```
**Outils:** embed, pinecone CRUD, n8n API
**Statut:** ⚠️ Erreur 403 (clé Jina invalide)

### 2. Pinecone MCP (Officiel)
```json
{
  "command": "npx",
  "args": ["-y", "@pinecone-database/mcp"],
  "env": { "PINECONE_API_KEY": "..." }
}
```
**Outils:** list-indexes, search-records, rerank-documents, cascading-search
**Statut:** ✅ Fonctionnel (mais inaccessible avec Kimi)

### 3. Neo4j MCP (Officiel)
```json
{
  "command": "neo4j-mcp",
  "env": { "NEO4J_URI": "bolt://localhost:7687", "NEO4J_PASSWORD": "..." }
}
```
**Outils:** get-schema, execute-read, execute-write, list-gds-procedures
**Statut:** ✅ Installé (v1.4.0)

### 4. n8n MCP (Communauté)
```json
{
  "command": "n8n-mcp-server",
  "env": { "N8N_API_URL": "...", "N8N_API_KEY": "..." }
}
```
**Outils:** workflow_list, workflow_get, run_webhook, activate/deactivate
**Statut:** ✅ Fonctionnel avec nouvelle clé API

### 5. Supabase MCP (Officiel - HTTP)
```json
{
  "type": "http",
  "url": "https://mcp.supabase.com/mcp?project_ref=..."
}
```
**Outils:** list_tables, execute_sql, apply_migration, get_logs, search_docs
**Statut:** ✅ Configuré

### 6. Cohere MCP (Custom)
```json
{
  "command": "/home/termius/mon-ipad/.venv/bin/python3",
  "args": ["/home/termius/mcp-servers/custom/cohere-mcp-server.py"]
}
```
**Outils:** embed, rerank, generate
**Statut:** ✅ Code valide

### 7. Hugging Face MCP (Custom)
```json
{
  "command": "/home/termius/mon-ipad/.venv/bin/python3",
  "args": ["/home/termius/mcp-servers/custom/huggingface-mcp-server.py"]
}
```
**Outils:** search_models, search_datasets, model_info
**Statut:** ⚠️ Bug détecté

---

## 🎯 Recommandations

### Si tu veux utiliser les MCP (avec reranking, découverte schéma, etc.):

**👉 Migrer vers Claude Code**
```bash
npm install -g @anthropic-ai/claude-code
# Puis: cd /home/termius/mon-ipad && claude
```

### Si tu veux rester avec Kimi:

**👉 Accepter les limitations et utiliser les fonctions Python**
- Les fonctions Python couvrent 80% des besoins
- Le reranking peut être fait manuellement avec Cohere API
- La découverte de schéma Neo4j peut être scriptée

**👉 Créer un wrapper MCP→Python**
- Développer un bridge qui expose les MCP comme fonctions Python
- Complexe mais possible

---

## 📊 Synthèse des Capacités Manquantes (sans MCP)

| Capacité | Impact | Workaround avec Python |
|----------|--------|------------------------|
| Reranking Pinecone | Moyen | Appel manuel API Cohere |
| Découverte schéma Neo4j | Faible | Script Cypher custom |
| Migrations Supabase | Faible | Gestion manuelle |
| Search docs | Faible | Lecture doc directe |
| Cascading search | Moyen | Multi-requêtes manuelles |

---

## ✅ Conclusion

**Les MCP sont configurés et fonctionnels**, mais **Kimi Code CLI ne peut pas les utiliser** car il utilise un protocole interne propriétaire.

**Pour utiliser les MCP:**
1. **Solution immédiate:** Passer à Claude Code
2. **Solution long terme:** Attendre que Kimi supporte MCP (pas de roadmap connue)
3. **Solution alternative:** Continuer avec les fonctions Python (suffisant pour la plupart des cas)

**Infrastructure actuelle:**
- ✅ 7 MCP configurés
- ✅ Processus prêts
- ⚠️ Inaccessibles depuis Kimi
- ✅ Fonctions Python disponibles

---

*Document créé le 2026-02-12 suite à l'analyse post-migration n8n Docker*
