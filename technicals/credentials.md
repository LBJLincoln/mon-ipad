# Credentials & Cles API

> **Ce fichier DOIT etre mis a jour** apres chaque rotation de cle ou changement de service.
> Derniere mise a jour : 2026-02-13 (post-migration Docker)

---

## Variables d'environnement (copier-coller)

```bash
# n8n Docker self-hosted (Google Cloud VM 34.136.180.66)
export N8N_HOST="http://34.136.180.66:5678"
export N8N_API_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2M2ZhN2FjNS1lOTJkLTQ2MjAtOGZkYS05Zjg0MWI1Y2VjZjYiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiNzc0NzYyNmItNTNjYi00ZDU0LTkxYmItYjZkYmE1NjdmZGVmIiwiaWF0IjoxNzcwOTM4NDExfQ.77sRd0mK_ShypXUibu4GpKbyKFXTzCE9mLa7940nUAw"

# LLM & Embeddings
export OPENROUTER_API_KEY="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"
export JINA_API_KEY="jina_f1348176dc7a4f0da9996cfa6cfa6eecasLHpAw7iEXFqU6eHi9SQBuxqT0F"
export COHERE_API_KEY="nqQv1HevJMecJrN00Hpjk5JFbOT3UtXJCTJRuIRu"

# Databases
export PINECONE_API_KEY="pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export NEO4J_PASSWORD="jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak"
export SUPABASE_PASSWORD="udVECdcSnkMCAPiY"
export SUPABASE_API_KEY="sb_publishable_xUcuBcYYUO2G9Mkq_McdeQ_ocFjgonm"
export SUPABASE_URL="https://ayqviqmxifzmhphiqfmj.supabase.co"
```

---

## Detail par service

### n8n — Docker self-hosted (migre le 2026-02-12)
- **Host** : `http://34.136.180.66:5678` (Google Cloud VM)
- **API Key** : JWT Docker (generee 2026-02-12, pas d'expiration)
- **MCP natif** : `http://34.136.180.66:5678/mcp-server/http` (token MCP separe)
- **UI** : `http://34.136.180.66:5678` (admin / SotaRAG2026!)
- **PostgreSQL** : `localhost:5432` (n8n / n8n_password_secure_2026)
- **Redis** : `localhost:6379` (pas de mot de passe)
- **Variables** : `$env.VAR_NAME` (pas `$vars` — free tier)

### Pinecone
- **Index** : `sota-rag`
- **Host** : `https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io`
- **Plan** : Free (serverless)
- **Dimensions** : 1536 (verifie le 2026-02-10)
- **Vecteurs** : 10,411 dans 12 namespaces

### Supabase
- **Project ref** : `ayqviqmxifzmhphiqfmj`
- **URL** : `https://ayqviqmxifzmhphiqfmj.supabase.co`
- **Password** : `udVECdcSnkMCAPiY`
- **API Key** : `sb_publishable_xUcuBcYYUO2G9Mkq_McdeQ_ocFjgonm`
- **Acces** : DIRECT (plus de proxy 403 depuis la migration Docker)

### Neo4j
- **URI** : `bolt://localhost:7687` (Docker VM)
- **URL API** : `https://38c949a2.databases.neo4j.io/db/neo4j/query/v2`
- **Password** : `jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak`
- **Acces** : DIRECT (plus de proxy 403 depuis la migration Docker)

### OpenRouter
- **API Key** : `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` (post-docker)
- **Rate limit** : 20 req/min, 1000 req/day (avec $10+ credit)

### Jina AI
- **API Key** : `jina_f1348176dc7a4f0da9996cfa6cfa6eecasLHpAw7iEXFqU6eHi9SQBuxqT0F`
- **Modele** : `jina-embeddings-v3` (1024-dim)
- **Limite** : 10M tokens/mois (gratuit)

### Cohere
- **API Key** : `nqQv1HevJMecJrN00Hpjk5JFbOT3UtXJCTJRuIRu`
- **Embeddings** : `embed-english-v3.0` (1024-dim)
- **Reranker** : `rerank-multilingual-v3.0`

### Unstructured.io
- **API URL** : `https://api.unstructuredapp.io/general/v0/general`
- **API Key** : Non configure (credential n8n a creer manuellement)

---

## Workflow IDs Docker (13 workflows actifs)

### Pipelines RAG (4)
| Pipeline | Docker ID | Webhook |
|----------|-----------|---------|
| Standard RAG V3.4 | `M12n4cmiVBoBusUe` | `/webhook/rag-multi-index-v3` |
| Graph RAG V3.3 | `Vxm4TDdOLdb7j3Jy` | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` |
| Quantitative V2.0 | `nQnAJyT06NTbEQ3y` | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` |
| Orchestrator V10.1 | `P1no6VZkNtnRdlBi` | `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` |

### Workflows Support (9)
| Workflow | Docker ID |
|----------|-----------|
| Ingestion V3.1 | `6lPMHEYyWh1v34ro` |
| Enrichissement V3.1 | `KXnQKuKw8ZUbyZUl` |
| Feedback V3.1 | `cMlr32Qq7Sgy6Xq8` |
| Benchmark V3.0 | `tygzgU4i67FU6vm2` |
| Dataset Ingestion Pipeline | `S4FFbvx9Mn7DRkgk` |
| Monitoring & Alerting | `xFAcxnFS5ISnlytH` |
| Orchestrator Tester | `R0HRiLQmL3FoCNKg` |
| RAG Batch Tester | `k7jHXRTypXAQOreJ` |
| SQL Executor Utility | `Dq83aCiXCfymsgCV` |

> Mapping complet en JSON : `n8n/docker-workflow-ids.json`

---

## Checklist post-migration (mise a jour 2026-02-13)

- [x] `N8N_HOST` → `http://34.136.180.66:5678`
- [x] `N8N_API_KEY` → Nouvelle cle Docker JWT
- [x] Workflow IDs → Nouveaux IDs Docker (13 workflows)
- [x] Webhook URLs → Paths identiques (verifies)
- [x] `.claude/settings.json` → MCP natif n8n + Supabase project ref
- [x] `directives/n8n-endpoints.md` → Nouveaux IDs et config
- [x] `eval/*.py` → Defaults Docker
- [x] `scripts/*.py` → Defaults Docker
- [x] `n8n/sync.py` → Docker IDs + host
- [x] Ce fichier (`technicals/credentials.md`) → Tout mis a jour
- [ ] Credentials n8n pour Supabase → A creer dans l'UI n8n
- [ ] Credentials n8n pour Redis → A configurer si necessaire
- [ ] Credentials n8n pour Unstructured.io → A creer dans l'UI n8n
