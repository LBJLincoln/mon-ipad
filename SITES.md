# NOMOS42 — All Sites & Access Points

> Last updated: 2026-03-13

---

## Live Sites (Vercel)

| Site | URL | Description |
|------|-----|-------------|
| **Expert Sectoriel** | [nomos42.vercel.app](https://nomos42.vercel.app) | Chatbot IA expert 4 secteurs (Finance, BTP, Juridique, Industrie) |
| **Satellite OSINT** | [nomos42.vercel.app/satellite](https://nomos42.vercel.app/satellite) | Dashboard spy satellite — globe 3D, CRT shaders, data feeds live |
| **Marketplace M&A** | [nomos42.vercel.app/marketplace](https://nomos42.vercel.app/marketplace) | Marketplace agents & entreprises — encheres, valorisation IA |
| **Business Factory** | [nomos42.vercel.app/factory](https://nomos42.vercel.app/factory) | Automated Business Factory — Idea-to-Exit pipeline |
| **Nomos Vault** | [nomos42.vercel.app/vault](https://nomos42.vercel.app/vault) | Secrets & credentials SOC dashboard — key rotation, audit log |
| **Knowledge Graph** | [nomos42.vercel.app/graph](https://nomos42.vercel.app/graph) | Brain 3D interactif — 72K nodes Neo4j, force-directed, filtres secteur |
| **Dashboard** | [nomos42.vercel.app/dashboard](https://nomos42.vercel.app/dashboard) | Dashboard qualite RAG — metriques live, eval stream |

---

## Infrastructure

| Service | URL | Role |
|---------|-----|------|
| **Lightning Agent** | [GPU T4](https://8000-01kkj0hqg9fq7twz8065b3e94m.cloudspaces.litng.ai/) | Agent IA autonome sur GPU NVIDIA T4 |
| **Lightning Terminal** | [Terminal](https://lightning.ai/lahargnedebartoli/inference-optimization-project/studios/inference-devbox/terminal?fullScreen=true) | SSH terminal Lightning.ai |
| **S1** (n8n engine) | [HF Space](https://lbjlincoln-nomos-rag-engine.hf.space) | 4 pipelines RAG + Auto-Healer |
| **S3** (n8n engine) | [HF Space](https://lbjlincoln-nomos-rag-engine-3.hf.space) | Load balance pipelines |
| **S5** (n8n engine) | [HF Space](https://lbjlincoln-nomos-rag-engine-5.hf.space) | Load balance pipelines |
| **S7** (LiteLLM) | [HF Space](https://lbjlincoln-nomos-rag-engine-7.hf.space) | Proxy LLM 9 modeles, 13 providers |
| **S9** (Ingest) | [HF Space](https://lbjlincoln-nomos-rag-engine-9.hf.space) | Ingestion V4.0 + Enrichment V4.0 |
| **S11** (engine) | [HF Space](https://nomos42-nomos-engine-11.hf.space) | Standard + Orchestrator |
| **OpenClaw** | [HF Space](https://nomos42-nomos-worker-2.hf.space) | Agent IA ops — Telegram bot |
| **Embeddings** | [HF Space](https://lbjlincoln-nomos-embeddings-api.hf.space) | Jina v3 self-hosted (1024 dims) |
| **Docling** | [HF Space](https://lbjlincoln-nomos-docling-api.hf.space) | Document parser PDF/complex |

---

## Telegram

| Bot | Handle | Role |
|-----|--------|------|
| **Nomos Agent** | [@Nomos42Bot](https://t.me/Nomos42Bot) | Assistant IA conversationnel — commandes shell, RAG queries, status |
| **Channel** | [@Nomos42](https://t.me/Nomos42) | Channel officiel |

---

## Databases

| Service | Content | Capacity |
|---------|---------|----------|
| **Pinecone** (E5) | ~82,892 vectors sectoriels | 100K max |
| **Pinecone** (Jina) | ~12,536 vectors | 100K max |
| **Neo4j Aura** | ~72K nodes + 143K relations | 200K/400K |
| **Supabase** | 43K docs, 225 financials, 29K eval questions | 500MB |

---

## Repos GitHub

| Repo | URL | Role |
|------|-----|------|
| **mon-ipad** | [github.com/LBJLincoln/mon-ipad](https://github.com/LBJLincoln/mon-ipad) | Tour de controle |
| **rag-website** | [github.com/LBJLincoln/rag-website](https://github.com/LBJLincoln/rag-website) | Site Next.js (6 pages) |
| **rag-data-ingestion** | [github.com/LBJLincoln/rag-data-ingestion](https://github.com/LBJLincoln/rag-data-ingestion) | Moteur ingestion |
| **rag-dashboard** | [github.com/LBJLincoln/rag-dashboard](https://github.com/LBJLincoln/rag-dashboard) | Dashboard metriques |

---

## Accuracy Targets

| Secteur | Current | Target | Gap |
|---------|---------|--------|-----|
| Finance | 85.2% | 90% | -4.8% |
| Industrie | 80.4% | 85% | -4.6% |
| Juridique | 78.8% | 90% | -11.2% |
| BTP | 73.7% | 85% | -11.3% |

---

## Inspiration

- **WorldView** by Bilawal Sidhu — [Article](https://www.spatialintelligence.ai/p/i-built-a-spy-satellite-simulator) | [SpatialOS](https://www.spatialos.co)
- Stack: CesiumJS + Google 3D Tiles + satellite.js + WebGL shaders (CRT/NVG/FLIR)
- Built with 8 AI agents in parallel (Claude, Gemini, Codex)
