# Etat de Session

> Ce fichier est mis a jour a chaque fin de session Claude Code.
> Lire `docs/status.json` pour les metriques live.

---

## Derniere session

- **Date** : 2026-02-10
- **Ce qui a ete fait** :
  - Restructuration complete du repo (context/, docs/technical/, scripts/)
  - Nettoyage massif : suppression workflows/improved/, source/, helpers/, deploy/
  - Suppression de tous les fichiers de patches (apply.py, agentic-loop.py, GH Actions)
  - Import des 13 workflows n8n dans workflows/live/ (RAG + ingestion + enrichment + benchmark)
  - Verification : workflows live correspondent aux tests reussis 12:21-13:13 UTC
  - Verification BDD Phase 2 : Neo4j (19,788 nodes), Supabase (538 rows), Pinecone (10,411 vecteurs) — TOUT PRET
  - Guide migration Oracle + script auto-setup cree
  - Roadmap restructure en 3 phases (A: RAG iteration, B: SOTA analysis, C: ingestion/enrichment)

- **Ce qui reste a faire** :
  1. **Phase A** : Iteration RAG pipelines (1/1 -> 5/5 -> 10/10 -> 200q)
     - Standard : pas teste, probablement casse → PRIORITE #1
     - Quantitative : erreur Init node (validation `query` field), pipeline passe par Error Handler
     - Orchestrator : pas teste recemment
     - Graph : 76.5% (OK, ne pas toucher sauf regression)
  2. **Migration** : Creer VM Oracle, lancer `scripts/n8n-oracle-setup.sh`
  3. **Phase B** : Analyse SOTA 2026 (papiers de recherche)
  4. **Phase C** : Pipelines ingestion/enrichment

---

## Pipeline Status

| Pipeline | Dernier test | Score | 10/10 atteint ? |
|----------|-------------|-------|-----------------|
| Standard | Pas teste | 0% | Non |
| Graph | 17q | 76.5% | Non (mais passe la gate Phase 1) |
| Quantitative | 8q | 0% (6 erreurs) | Non |
| Orchestrator | Exec reussies 13:01-13:04 UTC | A verifier | Non |

---

## BDD Phase 2 — PRETES

| BDD | Status | Details |
|-----|--------|---------|
| Pinecone | PRET | 10,411 vecteurs, 12 namespaces, dim 1536 |
| Neo4j | PRET | 19,788 nodes, 21,625 relations (4,884 Phase 2) |
| Supabase | PRET | 538 lignes (450 Phase 2: finqa + tatqa + convfinqa) |
| Dataset | PRET | datasets/phase-2/hf-1000.json (1,000 questions) |

---

## Blockers connus

- Supabase/Neo4j pas accessibles directement (proxy 403) → passer par n8n
- Quantitative pipeline : Init node valide `query` field mais erreur en aval
- Standard pipeline : non teste depuis migration embeddings 1536d
- Pinecone dimension = 1536 (pas 1024 comme dans certains docs)

---

## Notes pour la prochaine session

- Commencer par `python3 scripts/session-start.py`
- Priorite : Standard > Quantitative > Orchestrator
- Graph est OK, ne pas toucher sauf regression
- BDD Phase 2 pretes, pas besoin de re-peupler
- Processus : `context/workflow-process.md`
