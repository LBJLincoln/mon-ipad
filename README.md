# Nomos AI — Tour de Controle

> Infrastructure IA multi-sectorielle. 4 pipelines RAG, 9 pages web, 7 repos, 15+ daemons.

## Sites Live

| Page | Lien | Description |
|------|------|-------------|
| **La Forge** | [nomos42.vercel.app/factory](https://nomos42.vercel.app/factory) | Generateur d'entreprise IA (7 agents) |
| **NBA Expert** | [nomos42.vercel.app/nba](https://nomos42.vercel.app/nba) | Agent IA expert NBA — Paris, Analytics, GOAT |
| **Casino** | [nomos42.vercel.app/casino](https://nomos42.vercel.app/casino) | Jeux Atari addictifs (Breakout, Crash, Snake) |
| **Dashboard** | [nomos42.vercel.app/dashboard](https://nomos42.vercel.app/dashboard) | Metriques live |
| **Marketplace** | [nomos42.vercel.app/marketplace](https://nomos42.vercel.app/marketplace) | Marketplace agents IA |
| **Valorisation** | [nomos42.vercel.app/valorisation](https://nomos42.vercel.app/valorisation) | Estimateur de valeur |
| **Vault** | [nomos42.vercel.app/vault](https://nomos42.vercel.app/vault) | Coffre-fort documents |
| **Graph** | [nomos42.vercel.app/graph](https://nomos42.vercel.app/graph) | Visualisation knowledge graph |
| **Satellite** | [nomos42.vercel.app/satellite](https://nomos42.vercel.app/satellite) | Vue satellite |

## Repos

| Repo | Role | Status |
|------|------|--------|
| [**mon-ipad**](https://github.com/LBJLincoln/mon-ipad) | Tour de controle, eval, ops | ACTIF |
| [**rag-website**](https://github.com/LBJLincoln/rag-website) | Site Next.js (9 pages) | ACTIF |
| [**nomos-nba-agent**](https://github.com/LBJLincoln/nomos-nba-agent) | Agent IA NBA autonome | ACTIF |
| [**nomos-casino**](https://github.com/LBJLincoln/nomos-casino) | Jeux Atari + tests autonomes | ACTIF |
| [**nomos-forge-tests**](https://github.com/LBJLincoln/nomos-forge-tests) | Tests autonomes Factory | ACTIF |
| [**rag-data-ingestion**](https://github.com/LBJLincoln/rag-data-ingestion) | Moteur ingestion | ACTIF |
| [**rag-dashboard**](https://github.com/LBJLincoln/rag-dashboard) | Dashboard metriques | ACTIF |

## Stack

- **LLM**: LiteLLM S7 (13 providers, automatic fallback)
- **Embeddings**: Self-hosted Jina v3 (1024 dims)
- **Vector DB**: Pinecone (82K+ vectors)
- **Graph DB**: Neo4j Aura (72K nodes)
- **SQL**: Supabase (43K docs)
- **Compute**: 9 HF Spaces
- **Deploy**: Vercel + GCP VM

---

*Built with Claude Code (Opus 4.6)*
