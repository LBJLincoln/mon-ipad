# Stack Technique Complète

## Infrastructure

### Terminal (iPad)
| Option | Avantage | Limitation |
|--------|----------|------------|
| **Termius** | SSH natif iPad, clés SSH | Pas de VM, besoin d'un serveur distant |
| **Google Cloud Shell** | Free, 5GB stockage, Debian | Sessions de 60min max, pas de sudo complet |
| **Oracle Cloud Free** | VM ARM toujours gratuite, 24GB RAM | Setup initial plus long |

**Recommandation** : Oracle Cloud Free Tier (VM ARM Ampere A1, 4 OCPU, 24GB RAM, toujours gratuit) + Termius pour le SSH.

### n8n
| Option | Coût | Avantage |
|--------|------|----------|
| **n8n Cloud** (actuel) | ~20EUR/mois | Zero maintenance |
| **n8n self-hosted sur Oracle** | $0 | Gratuit, plus de contrôle, accès DB direct |
| **n8n sur Railway/Render** | $0 (free tier) | Simple, mais limites de compute |

**Migration recommandée** : n8n self-hosted sur Oracle Cloud Free Tier (Docker).
Voir `docs/migration/n8n-self-hosted.md` pour le guide complet.

---

## Services & Bases de Données

### Pinecone (Vector DB)
- **Plan** : Free tier (index serverless)
- **Host** : `https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io`
- **Capacité** : 10,411 vecteurs, 12 namespaces
- **Dimensions** : 1024 (Jina/Cohere) configurable
- **Accès** : DIRECT depuis Claude Code et n8n

### Neo4j (Graph DB)
- **Instance** : Via n8n (accès direct bloqué depuis Claude Code proxy)
- **Contenu** : 4,884 entités, 21,625 relations
- **Accès** : Via n8n Graph RAG pipeline uniquement
- **Note** : Avec n8n self-hosted, accès direct possible

### Supabase (SQL DB)
- **Plan** : Free tier
- **Contenu** : 538 lignes, tables financières
- **Accès** : Via n8n Quantitative pipeline uniquement
- **Note** : Avec n8n self-hosted, accès direct possible

### Redis (Cache)
- **Usage** : Cache optionnel pour n8n self-hosted
- **Plan** : Redis Cloud free (30MB) ou local sur Oracle VM

---

## LLM & Embeddings

### LLM (gratuit via OpenRouter)
| Modèle | Usage | Coût |
|--------|-------|------|
| `arcee-ai/trinity-large-preview:free` | Tous les nœuds LLM n8n | $0 |
| `google/gemma-3-27b-it:free` | Alternative rapide | $0 |
| `deepseek/deepseek-chat-v3-0324:free` | Fort en SQL | $0 |
| `qwen/qwen3-coder:free` | Spécialiste SQL | $0 |

### Embeddings (gratuit)
| Provider | Modèle | Dimensions | Limite gratuite |
|----------|--------|------------|-----------------|
| **Jina AI** | jina-embeddings-v3 | 1024 | 10M tokens/mois |
| **Cohere** | embed-v4.0 | 1024 | 10K calls/mois |
| **HuggingFace** | sentence-transformers | 768-1024 | Illimité (local) |

---

## Outils de Développement

### Claude Code (Max Plan)
- **Terminal** : `claude` CLI dans Termius/GCloud/Oracle
- **Web** : claude.ai/code sessions
- **MCP Servers** : Configurés dans `.claude/settings.json`

### GitHub
- **Repo** : `LBJLincoln/mon-ipad`
- **Branches** : `main` + branches `claude/*` pour features
- **Actions** : Eval auto, dashboard deploy, error monitoring
- **Pages** : Dashboard déployé sur GitHub Pages

### MCP Servers Disponibles
Voir `docs/technical/mcp-setup.md` pour la config détaillée.

| Serveur | Outils | Status |
|---------|--------|--------|
| jina-embeddings | embed, pinecone CRUD, n8n API | Actif |
| n8n-manager (à configurer) | workflow CRUD, execution fetch | Prévu |
| supabase (à configurer) | SQL queries directes | Prévu (si self-hosted) |
| neo4j (à configurer) | Cypher queries directes | Prévu (si self-hosted) |

---

## Workflow n8n

| Pipeline | Workflow ID | Webhook |
|----------|-------------|---------|
| Standard | `LnTqRX4LZlI009Ks-3Jnp` | `/webhook/rag-multi-index-v3` |
| Graph | `95x2BBAbJlLWZtWEJn6rb` | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` |
| Quantitative | `LjUz8fxQZ03G9IsU` | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` |
| Orchestrator | `FZxkpldDbgV8AD_cg7IWG` | `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` |

**Note** : Ces IDs changeront après migration vers n8n self-hosted. Mettre à jour `docs/technical/credentials.md` après migration.
