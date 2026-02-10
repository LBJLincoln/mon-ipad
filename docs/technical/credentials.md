# Credentials & Clés API

> **Ce fichier DOIT être mis à jour** après chaque rotation de clé ou changement de service.
> Dernière mise à jour : 2026-02-10

---

## Variables d'environnement (copier-coller)

```bash
export SUPABASE_PASSWORD="udVECdcSnkMCAPiY"
export SUPABASE_API_KEY="sb_publishable_xUcuBcYYUO2G9Mkq_McdeQ_ocFjgonm"
export PINECONE_API_KEY="pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export NEO4J_PASSWORD="jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak"
export OPENROUTER_API_KEY="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"
export N8N_API_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"
export N8N_HOST="https://amoret.app.n8n.cloud"
export JINA_API_KEY="jina_f1348176dc7a4f0da9996cfa6cfa6eecasLHpAw7iEXFqU6eHi9SQBuxqT0F"
```

---

## Détail par service

### n8n
- **Host actuel** : `https://amoret.app.n8n.cloud` (cloud payant)
- **Host futur** : `http://<oracle-vm-ip>:5678` (self-hosted gratuit)
- **API Key** : JWT, expire le 2026-02-21 (`exp: 1771628400`)
- **Action requise** : Régénérer avant expiration

### Pinecone
- **Index** : `sota-rag`
- **Host** : `https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io`
- **Plan** : Free (serverless)
- **Dimensions** : 1024 (Jina/Cohere)

### Supabase
- **Project** : accès via n8n uniquement (proxy 403 direct)
- **Password** : `udVECdcSnkMCAPiY`
- **API Key** : `sb_publishable_xUcuBcYYUO2G9Mkq_McdeQ_ocFjgonm`
- **Note** : Avec n8n self-hosted, accès direct possible

### Neo4j
- **Instance** : accès via n8n uniquement (proxy 403 direct)
- **Password** : `jV_zGdxbu-emQZM-ZSQux19pTZ5QLKejR2IHSzsbVak`
- **Note** : Avec n8n self-hosted, accès direct possible

### OpenRouter
- **API Key** : `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`
- **Alt key (MCP)** : `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`
- **Rate limit** : 20 req/min, 1000 req/day (avec $10+ crédit)

### Jina AI
- **API Key** : `jina_f1348176dc7a4f0da9996cfa6cfa6eecasLHpAw7iEXFqU6eHi9SQBuxqT0F`
- **Modèle** : `jina-embeddings-v3` (1024-dim)
- **Limite** : 10M tokens/mois (gratuit)

---

## Après migration n8n self-hosted

Mettre à jour :
- [ ] `N8N_HOST` → `http://<oracle-vm-ip>:5678`
- [ ] `N8N_API_KEY` → Nouvelle clé générée sur l'instance self-hosted
- [ ] Workflow IDs → Nouveaux IDs après import
- [ ] Webhook URLs → Nouveaux paths
- [ ] `.claude/settings.json` → Nouveaux endpoints MCP
- [ ] `docs/technical/n8n-endpoints.md` → Nouveaux IDs et URLs
- [ ] `eval/quick-test.py` → Nouveaux endpoints webhook
