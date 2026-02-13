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
export COHERE_API_KEY="nqQv1HevJMecJrN00Hpjk5JFbOT3UtXJCTJRuIRu"
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
- **Dimensions** : 1536 (verifie le 2026-02-10, pas 1024 comme prevu)
- **Vecteurs** : 10,411 dans 12 namespaces

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

---

## Workflow IDs n8n (13 workflows actifs)

### Pipelines RAG
| Pipeline | n8n ID | Webhook |
|----------|--------|---------|
| Standard RAG V3.4 | `IgQeo5svGlIAPkBc` | `/webhook/rag-multi-index-v3` |
| Graph RAG V3.3 | `95x2BBAbJlLWZtWEJn6rb` | `/webhook/ff622742-6d71-4e91-af71-b5c666088717` |
| Quantitative V2.0 | `E19NZG9WfM7FNsxr` | `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` |
| Orchestrator V10.1 | `ALd4gOEqiKL5KR1p` | `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` |

### Ingestion/Enrichment
| Workflow | n8n ID |
|----------|--------|
| Ingestion V3.1 | `nh1D4Up0wBZhuQbp` |
| Enrichissement V3.1 | `ORa01sX4xI0iRCJ8` |
| Feedback V3.1 | `iVsj6dq8UpX5Dk7c` |
| Benchmark V3.0 | `qUm28nhq62SxVWHe` |

### Benchmark/Support
| Workflow | n8n ID |
|----------|--------|
| Dataset Ingestion Pipeline | `L8irkzSrfLlgt2Bt` |
| Monitoring & Alerting | `8a72LTsYvsH2X79d` |
| Orchestrator Tester | `7UMkzbjkkYZAUzPD` |
| RAG Batch Tester | `QCHKdqnTIEwEN1Ng` |
| SQL Executor Utility | `3O2xcKuloLnZB5dH` |

---

## Apres migration n8n self-hosted

Mettre a jour :
- [ ] `N8N_HOST` -> `http://<oracle-vm-ip>:5678`
- [ ] `N8N_API_KEY` -> Nouvelle cle generee sur l'instance self-hosted
- [ ] Workflow IDs -> Nouveaux IDs apres import
- [ ] Webhook URLs -> Nouveaux paths
- [ ] `.claude/settings.json` -> Nouveaux endpoints MCP
- [ ] `docs/technical/n8n-endpoints.md` -> Nouveaux IDs et URLs
- [ ] `eval/quick-test.py` -> Nouveaux endpoints webhook
- [ ] Ce fichier (`docs/technical/credentials.md`) -> Tout mettre a jour

### Script d'auto-setup
```bash
bash scripts/n8n-oracle-setup.sh
```
Ce script configure Docker, n8n, Redis et le firewall sur une VM Oracle.
Les credentials n8n doivent ensuite etre configurees dans l'UI n8n (voir `docs/migration/n8n-self-hosted.md`).
