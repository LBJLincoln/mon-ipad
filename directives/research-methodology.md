# Research Methodology — Directive Centralisee pour Tous les Repos

> Last updated: 2026-02-25T11:30:00+00:00

---

## Principe Fondamental

**Toute recherche internet dans ce projet DOIT suivre cette methodologie.**
Ce fichier est la source de verite pour la facon dont les agents Claude Code
effectuent des recherches dans TOUS les repos (mon-ipad, rag-tests, rag-website,
rag-data-ingestion, rag-dashboard).

---

## 1. Sources Prioritaires (par ordre)

### Tier 1 — Papiers de recherche academiques (OBLIGATOIRE)
| Source | URL | Ce qu'on y cherche |
|--------|-----|-------------------|
| **arXiv** | arxiv.org | Papiers RAG, NLP, LLM, embeddings, retrieval — toujours la version la plus recente |
| **Semantic Scholar** | semanticscholar.org | Citations croisees, impact factor, papiers connexes |
| **ACL Anthology** | aclanthology.org | Conferences NLP (ACL, EMNLP, NAACL, EACL) |
| **NeurIPS / ICML / ICLR** | proceedings officiels | ML/AI foundations |
| **Google Scholar** | scholar.google.com | Meta-recherche, citations, trending papers |

**Regle** : Un papier cite DOIT avoir un identifiant (arXiv ID, DOI, ou lien conference).
Pas de "j'ai lu quelque part que..." — toujours une reference verifiable.

### Tier 2 — Blogs de recherche des labs majeurs (SUIVI CONSTANT)
| Lab | Blog/Research | Frequence de suivi | Focus |
|-----|--------------|-------------------|-------|
| **Anthropic** | anthropic.com/research | Hebdomadaire | Constitutional AI, RLHF, retrieval, safety |
| **OpenAI** | openai.com/research | Hebdomadaire | GPT, embeddings, file search, tool use |
| **Google DeepMind** | deepmind.google/research | Hebdomadaire | Gemini, PaLM, retrieval, multimodal |
| **xAI (Grok)** | x.ai/blog | Bi-hebdomadaire | Grok models, reasoning, real-time knowledge |
| **Meta AI (FAIR)** | ai.meta.com/research | Bi-hebdomadaire | Llama, open-source LLM, embeddings |
| **Jina AI** | jina.ai/news | Mensuel | Embeddings, reranking, late chunking |
| **Cohere** | cohere.com/research | Mensuel | Reranking, embed models, RAG |
| **Pinecone** | pinecone.io/learn | Mensuel | Vector DB, hybrid search, serverless |

### Tier 3 — Documentation technique officielle
| Service | Docs | Ce qu'on y cherche |
|---------|------|-------------------|
| n8n | docs.n8n.io | Workflows, queue mode, API, best practices |
| Pinecone | docs.pinecone.io | SDK, sparse vectors, namespaces, serverless |
| Neo4j | neo4j.com/docs | Cypher, graph algorithms, Aura |
| Supabase | supabase.com/docs | PostgreSQL, Edge Functions, RLS |
| Jina | docs.jina.ai | Embeddings API, reranking, late chunking |

### Tier 4 — Benchmarks et leaderboards
| Leaderboard | URL | Utilite |
|-------------|-----|---------|
| MTEB | huggingface.co/spaces/mteb/leaderboard | Embedding models ranking |
| Open LLM Leaderboard | huggingface.co/spaces/open-llm-leaderboard | LLM models ranking |
| RAGAS | ragas.io | RAG evaluation metrics |
| Chatbot Arena | lmarena.ai | LLM quality comparative |

---

## 2. Methodologie de Recherche

### Etape 1 : Formuler la question de recherche
```
MAUVAIS : "comment ameliorer le RAG"
BON    : "techniques SOTA 2025-2026 pour ameliorer la precision du retrieval
          dans un systeme RAG multi-pipeline avec embeddings Jina 1024-dim"
```

### Etape 2 : Rechercher sur arXiv + Semantic Scholar
```
Requetes types :
- "RAG retrieval augmented generation 2025 2026"
- "hybrid search sparse dense retrieval"
- "graph RAG entity disambiguation"
- "financial table question answering SQL generation"
- "late chunking contextual retrieval"
- "reranking cross-encoder 2026"
```

### Etape 3 : Croiser avec les blogs des labs
Verifier si Anthropic, OpenAI, Google ou xAI ont publie quelque chose de pertinent
dans les 3 derniers mois sur le sujet.

### Etape 4 : Documenter avec references
```markdown
## Technique : [Nom]
- **Papier** : [Titre] (arXiv:XXXX.XXXXX, [Auteurs], [Date])
- **Lab** : [Anthropic/OpenAI/Google/Meta/...]
- **Impact estime** : [+X% accuracy / -Xs latency / ...]
- **Cout** : $0 (gratuit) / $X/mois
- **Faisabilite** : HIGH/MEDIUM/LOW
- **Implementation** : [Description concrete dans notre stack]
```

### Etape 5 : Valider la gratuite
**REGLE ABSOLUE** : Toute technique proposee DOIT etre implementable a $0.
Si un papier propose une technique necessitant un modele payant, chercher
l'equivalent open-source/gratuit :
- GPT-4 → Llama 70B (gratuit via OpenRouter)
- Claude → Gemma 27B (gratuit via OpenRouter)
- Cohere Embed v3 → Jina Embeddings v3 (gratuit 1M tokens/mois)
- OpenAI Embeddings → Jina ou multilingual-e5-large (gratuit)

---

## 3. Suivi Continu des Labs (OBLIGATOIRE)

### Check-list de suivi (a chaque session de recherche)
- [ ] Anthropic Research : nouveau papier ou blog post ?
- [ ] OpenAI Research : nouveau modele, technique, ou API ?
- [ ] Google DeepMind : Gemini update, nouveau benchmark ?
- [ ] xAI (Grok) : nouveau modele Grok, technique de reasoning ?
- [ ] Meta AI : nouveau Llama, technique open-source ?
- [ ] Jina AI : nouveau embedding model, late chunking update ?

### Alertes automatiques (a implementer)
Idealement, configurer un workflow n8n qui :
1. Scrape les flux RSS des blogs ci-dessus
2. Filtre par mots-cles (RAG, retrieval, embedding, chunking, reranking)
3. Notifie via webhook si un nouveau papier pertinent est publie

---

## 4. Ce qui est INTERDIT

1. **Pas de sources non-academiques** comme seule reference (blog random, tutorial Medium)
2. **Pas de techniques non-verifiees** — tout doit avoir un papier ou un benchmark
3. **Pas de solutions payantes** sans alternative gratuite documentee
4. **Pas de "j'ai entendu dire"** — reference ou rien
5. **Pas de papiers avant 2024** sauf classiques fondateurs (Attention Is All You Need, etc.)

---

## 5. Application par Repo

| Repo | Quand rechercher | Quoi rechercher |
|------|-----------------|-----------------|
| **mon-ipad** | A chaque session | SOTA RAG, infrastructure, benchmarks |
| **rag-tests** | Avant chaque fix pipeline | Technique specifique au pipeline en echec |
| **rag-website** | Avant ajout secteur | UX/RAG chatbot, sector-specific RAG |
| **rag-data-ingestion** | Avant chaque ingestion | Chunking SOTA, enrichment techniques |
| **rag-dashboard** | Rarement | Dataviz best practices |

---

## 6. Template de Recherche (a copier)

```markdown
# Recherche : [Sujet]
Date : YYYY-MM-DD
Repo : [mon-ipad/rag-tests/...]

## Question de recherche
[Question precise]

## Sources consultees
1. arXiv : [requete] → [X resultats pertinents]
2. Semantic Scholar : [requete] → [X resultats]
3. [Lab] Blog : [URL] → [pertinent/non pertinent]

## Papiers retenus
### [Papier 1]
- arXiv : XXXX.XXXXX
- Auteurs : [...]
- Date : [...]
- Technique : [...]
- Impact estime : [...]
- Gratuit : OUI/NON (si NON, alternative gratuite : [...])

## Recommandation
[Action concrete a implementer]

## References
- [1] [Citation complete]
- [2] [Citation complete]
```

---

*Ce fichier est la directive centrale de recherche. Il doit etre pousse vers tous les repos
satellites via `scripts/push-directives.sh` (a adapter pour inclure ce fichier).*
