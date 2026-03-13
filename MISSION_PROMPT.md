# MISSION: NOMOS SATELLITE INTELLIGENCE & BUSINESS FACTORY

> Adapte a l'infrastructure Nomos reelle — 2026-03-13

---

## 1. VISION & ESTHETIQUE (TARGET: "SPY SATELLITE SIMULATOR")

- **Interface UI**: Dashboard ultra-futuriste utilisant **Cesium** pour le globe 3D, **WebGL** pour les shaders (CRT, Vision Nocturne, FLIR thermique) et **satellite.js** pour simuler des orbites de scan de donnees.
- **Transparence OSINT**: Chaque entite (agent ou entreprise) visualisee comme une cible satellite. Le zoom revele les preuves d'execution en temps reel.
- **Frontend**: Deploye sur **rag-website** (Next.js) ou sur un HF Space dedie (static Docker).

---

## 2. STACK TECHNIQUE (INFRASTRUCTURE REELLE NOMOS)

### Compute & Orchestration (3 tiers)

**Tier 1 — Actif maintenant :**
| Composant | Role | URL |
|-----------|------|-----|
| **VM GCP** (34.136.180.66) | Tour de controle, Claude Code, pilotage | SSH via Termius |
| **OpenClaw** (Worker-2) | Agent IA ops, Telegram bot, API REST | `nomos42-nomos-worker-2.hf.space` |
| **S1/S3/S5** (n8n engines) | 4 pipelines RAG (Standard, Graph, Quant, Orch) | `lbjlincoln-nomos-rag-engine*.hf.space` |
| **S9** (n8n ingest) | Ingestion V4.0 + Enrichment V4.0 (30+ nodes) | `lbjlincoln-nomos-rag-engine-9.hf.space` |
| **S7** (LiteLLM proxy) | 9 modeles, 13-provider fallback, rotation auto | `lbjlincoln-nomos-rag-engine-7.hf.space` |
| **S11** (Nomos42 engine) | Standard + Orchestrator (load balance) | `nomos42-nomos-engine-11.hf.space` |

**Tier 2 — Lightning.ai GPU (ACTIF) :**
| Composant | Role | URL |
|-----------|------|-----|
| **Lightning.ai T4** | GPU NVIDIA T4 — compute lourd, inference locale, fine-tuning | `8000-01kkj0hqg9fq7twz8065b3e94m.cloudspaces.litng.ai` |
| **Bridge FastAPI** | Tunnel port 8000 Lightning → OpenClaw HF | A deployer sur Lightning |
| **Autoresearch GPU** | Karpathy reasoning loop en mode GPU-accelere | A migrer depuis VM (CPU) |

> Lightning.ai est le upgrade compute pour : fine-tuning modeles locaux, autoresearch intensif, embeddings batch rapides.
> **Port 8000** expose via HTTPS — FastAPI bridge a deployer pour connecter a OpenClaw.

**Tier 3 — Scale futur :**
- Modal / RunPod / Vast.ai pour GPU on-demand si Lightning insuffisant
- HF Spaces GPU (A10G, L40) si budget disponible

### Intelligence
| Composant | Role | Localisation |
|-----------|------|-------------|
| **LiteLLM S7** | Proxy LLM unique — `smart` / `fast` / `default` model groups | HF Space S7 |
| **OpenClaw LLM** | OpenRouter direct — 9 modeles, fallback chain | HF Space Worker-2 |
| **Autoresearch** (Karpathy) | Reasoning loop pour etude de marche autonome | `/home/termius/autoresearch/` |
| **Eval system** | Eval blast (50Q/cycle), regression, improver | VM GCP daemons |

### Data (Sector-Only)
| Service | Contenu | Capacite |
|---------|---------|----------|
| **Pinecone** (E5 primary) | ~82,892 vectors sectoriels | 100K max |
| **Pinecone** (Jina secondary) | ~12,536 vectors | 100K max |
| **Neo4j Aura** | ~72K nodes (Entity, SectorDoc, Law, Org) + 143K rels | 200K/400K |
| **Supabase** | 43K docs, 225 financials, 29K+ eval questions | 500MB |
| **Docling S6** | Parsing PDF/documents complexes | HF Space |
| **`document_registry`** | Registre central (23 cols: hash, quality, provenance) | Supabase |

### Daemons actifs (VM GCP)
| Process | Cycle | Role |
|---------|-------|------|
| `ingest-pipeline.py` | 1800s | Tavily research → n8n S9 ingestion |
| `ingest-enrich-chain.py` | 900s | Enrichment docs non-enrichis via n8n S9 |
| `eval-blast.py` | 1800s | 50Q eval continu, toutes pipelines |
| `agent-improver.py` | 3600s | Detecte secteur faible, ingere donnees ciblees |
| `agent-regression.py` | 900s | Garde contre regressions |
| `monitor.py` | 300s | Health check infra, alertes |

---

## 3. PILIERS BUSINESS (DEVELOPPEMENT PRIORITAIRE)

### A. MARKETPLACE D'AGENTS & D'ENTREPRISES (M&A IA)

**Concept**: Plateforme de vente/encheres d'entreprises (IA-natives ou reelles) et d'agents specialises.

**Module Valuator (Due Diligence):**
- **Valeur Idee**: Analyse de rarete via autoresearch (Karpathy reasoning loop) + Tavily mass search.
- **Valeur Execution**: Preuve de travail extraite des logs n8n, metriques eval-blast, `data/metrics/execution_log.json`.
- **Revenus Reels**: Analyse transparente des flux financiers via `sector_financial_tables` (3,876 tables, 225 companies).
- **Scoring**: Calcul automatique base sur `document_registry.quality_score` + Neo4j entity graph density.

**Agent Negociateur**: IA experte (OpenClaw via Telegram + API REST) capable de gerer les encheres et discussions de rachat. Deja cable sur OpenRouter 9 modeles avec fallback chain.

**Implementation concrete:**
1. Pipeline n8n "Valuator" sur S9 — webhook `/webhook/valuator`
2. Supabase table `marketplace_listings` (assets, valuations, bids)
3. Neo4j graph "ownership" (qui possede quoi, liens M&A)
4. OpenClaw commande `/valuate <entity>` via Telegram

### B. AUTOMATED BUSINESS FACTORY (ABF)

**Concept**: Creation d'entreprise "Idea-to-Exit" 100% automatisee.

**Workflow (adapte a notre infra):**
1. **Validation humaine** via OpenClaw Telegram (`/create-business <idea>`) ou API REST.
2. **Etude de marche autonome** via `autoresearch` reasoning loop → resultats dans `document_registry`.
3. **Deploiement agents**: n8n workflows parametriques (1 workflow = 1 agent) sur Spaces libres (S2, S4, Worker-2).
4. **Monitoring**: eval-blast continu + OpenClaw health checks toutes les 5min + Telegram alertes admin.
5. **Data pipeline**: Ingestion sectorielle automatique (Tavily → n8n S9 → Pinecone + Neo4j + Supabase).

**Agents ABF (deployes comme workflows n8n):**
| Agent | Role | Space |
|-------|------|-------|
| Market Research | Autoresearch + Tavily → rapport | S9 |
| Content Agent | Generation contenu expert → ingestion | S1/S3/S5 |
| Sales Agent | Leads via eval questions + responses | OpenClaw |
| Analytics Agent | Metriques via eval-blast + execution_log | VM daemon |

### C. EXPERT SECTORIEL (PRODUIT PRINCIPAL — EN COURS)

**Status actuel — 4 secteurs operationnels:**
| Secteur | Accuracy | Vectors | Docs | Target |
|---------|----------|---------|------|--------|
| Finance | 85.2% | ~25K | 2,150 | 90% |
| Industrie | 80.4% | ~20K | 1,015 | 85% |
| Juridique | 78.8% | ~20K | 2,500 | 90% |
| BTP | 73.7% | ~17K | 1,844 | 85% |

**Ce produit tourne deja** — 6 daemons continus, 4 pipelines RAG, auto-improvement actif.
La Marketplace et l'ABF se construisent PAR-DESSUS cette base solide.

---

## 4. MODULE DE VALORISATION & TRANSPARENCE

Chaque actif doit avoir une "Signature Thermique" en WebGL :
- **Bleu/Froid**: Idee pure, pas d'execution (`document_registry.processing_status = 'pending'`).
- **Orange/Chaud**: Execution prouvee (`processing_status = 'completed'`, `quality_score > 0.7`).
- **Blanc/Fusion**: Revenus reels + traction marche (`sector_financial_tables` avec chiffres confirmes).

**Data sources pour le heatmap:**
- `document_registry` — provenance, qualite, hash de chaque document
- `data/metrics/execution_log.json` — 1,414+ executions pipeline tracees
- `data/eval/blast-*.json` — resultats eval continus (12+ snapshots)
- Neo4j entity density — densite du graphe autour de chaque entite
- Pinecone vector count par namespace — volume de donnees par secteur

---

## 5. INSTRUCTIONS OPERATIONNELLES

### Phase 1 : Fondations (FAIT)
- [x] OpenClaw deploye sur HF Space Worker-2 (Telegram + API REST + 14 Spaces cables)
- [x] LiteLLM S7 comme proxy unique pour toutes les pipelines RAG
- [x] `document_registry` table Supabase (23 colonnes, hash, quality, provenance)
- [x] Autoresearch clone sur VM (`/home/termius/autoresearch/`)
- [x] 6 daemons continus (ingest, enrich, eval, improve, regression, monitor)

### Phase 2 : Integration Autoresearch → Nomos (A FAIRE)
1. **Config autoresearch**: Modifier `autoresearch/train.py` pour utiliser LiteLLM S7 (`https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions`, `Bearer sk-litellm-nomos-2026`) au lieu d'OpenAI direct.
2. **Output → document_registry**: Les decouvertes de recherche sont inserees dans `document_registry` avec `source_type='autoresearch'`.
3. **Output → ingestion**: Les URLs decouvertes sont envoyees au daemon `ingest-pipeline.py` pour vectorisation automatique.

### Phase 3 : Marketplace (A CONSTRUIRE)
1. Creer table Supabase `marketplace_listings` (id, type, title, description, valuation_score, owner, status, bids JSONB).
2. Workflow n8n "Valuator" sur S9 — entity analysis pipeline.
3. OpenClaw commande `/valuate` + `/list` + `/bid`.
4. Frontend Cesium/WebGL globe sur rag-website ou HF Space dedie.

### Phase 4 : ABF (A CONSTRUIRE)
1. Commande OpenClaw `/create-business <idea>` → lance autoresearch + cree entry marketplace.
2. Workflow n8n "ABF Orchestrator" — coordonne Market Research + Content + Sales agents.
3. Monitoring via eval-blast + OpenClaw Telegram alertes.

### En attente
- `COMMANDS_EXT.md` — details d'implementation des agents specifiques (fourni par l'utilisateur).
