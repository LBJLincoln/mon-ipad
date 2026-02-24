# Directive — rag-pme-connectors

> Last updated: 2026-02-25T00:20:00+01:00

## Rôle de ce repo

**ÉTAT RÉEL (audit Session 59b)** : Site vitrine/showcase Next.js 15 déployé sur Vercel + 1 chatbot RAG fonctionnel (proxy vers Orchestrator n8n).

### CE QUI EXISTE vs CE QUI EST ANNONCÉ
| Claim | Réalité | Status |
|-------|---------|--------|
| 15 connecteurs apps | **LANDING PAGE ONLY** — icônes/texte statiques dans `constants-pme.ts`, zéro code d'intégration | À CONSTRUIRE |
| Chatbot IA | **FONCTIONNEL** — proxy vers Orchestrator RAG via `/api/chat` | OK |
| OAuth flows | **INEXISTANT** — zéro flow OAuth, zéro SDK externe | À CONSTRUIRE |
| 3 workflows n8n PME | **PAS DANS CE REPO** — zéro JSON workflow | Dans mon-ipad |
| API routes connecteurs | **1 SEULE ROUTE** — `/api/chat` (proxy n8n) | À CONSTRUIRE |

### Priorité next session
1. Décider : construire les vraies intégrations OU reclassifier comme showcase-only
2. Si intégrations : ajouter SDKs (googleapis, @slack/web-api, stripe), OAuth routes, webhook handlers
3. Les 3 workflows PME n8n sont dans mon-ipad, pas ici

## Architecture PME Workflows

```
WhatsApp/Telegram → whatsapp-telegram-bridge → Multi-Canal Gateway → Intent Router
                                                    │          │          │
                                              query │    action│    report│
                                                    ▼          ▼          ▼
                                              Orchestrator  Action     Orchestrator
                                              V10.1 (RAG)  Executor   V10.1 (report)
                                                              │
                                                    ┌─────────┼─────────┬──────────┐
                                                    ▼         ▼         ▼          ▼
                                              Google Cal   Gmail   Google Drive  Fallback RAG
```

## Webhook Endpoints (HF Space)

| Workflow | Path | Method |
|----------|------|--------|
| Multi-Canal Gateway | `/webhook/pme-assistant-gateway` | POST |
| Action Executor | `/webhook/pme-action-executor` | POST |
| WhatsApp Bridge | `/webhook/whatsapp-incoming` | POST |

## Credentials Required

| Credential ID | Service | Status |
|--------------|---------|--------|
| `LLM_API_CREDENTIAL_ID` | OpenRouter (Llama 70B) | Configured |
| `TELEGRAM_BOT_CREDENTIAL` | Telegram Bot | Needs setup |
| `WHATSAPP_BEARER_AUTH` | WhatsApp Cloud API | Needs setup |
| `GOOGLE_CALENDAR_CREDENTIAL` | Calendar OAuth2 | Needs setup |
| `GMAIL_CREDENTIAL` | Gmail OAuth2 | Needs setup |
| `GOOGLE_DRIVE_CREDENTIAL` | Drive OAuth2 | Needs setup |

## Test Sans Credentials Externes

```bash
# API mode — fonctionne sans Telegram/WhatsApp/Google
curl -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/pme-assistant-gateway" \
  -H "Content-Type: application/json" \
  -d '{"query":"Quels sont les derniers documents dans le Drive?","channel":"api"}'
```

- Intent `query` → Orchestrator RAG (fonctionne)
- Intent `report` → Orchestrator report (fonctionne)
- Intent `action` → Action Executor → **nécessite Google credentials**

## Website PME Connectors

- **URL live**: https://nomos-pme-connectors-alexis-morets-projects.vercel.app
- **Framework**: Next.js 15
- **15 connecteurs**: WhatsApp, Telegram, Gmail, Outlook, Slack, Google Drive, OneDrive, Dropbox, Google Calendar, Notion, Trello, HubSpot, Salesforce, Stripe, QuickBooks
- **Chatbot**: MacBook-style interactive demo
- **Déploiement**: Push GitHub → Vercel auto-deploy

## Règles

1. Workflows PME dans `n8n/pme-connectors/` (master dans mon-ipad)
2. Tests PME indépendants de rag-tests
3. GOOGLE_API_KEY disponible dans .env.local sur la VM
4. Credential IDs doivent matcher les IDs dans fix-env-refs.py du HF Space
5. Modifier workflows sur HF Space, sync vers GitHub, jamais sur VM
