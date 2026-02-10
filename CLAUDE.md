# Multi-RAG Orchestrator — SOTA 2026

## Session Start — LIRE EN PREMIER

```bash
cat docs/status.json                    # Metriques live, blockers, prochaine action
cat context/session-state.md            # Ce qui a ete fait, ce qui reste
```

Puis : identifier le pipeline avec le plus gros gap -> analyser node-par-node -> fixer dans n8n -> verifier -> sync GitHub.

---

## Structure du Repo

```
mon-ipad/
├── CLAUDE.md                          <- CE FICHIER (lire en premier)
├── context/                           <- CONTEXTE SESSION
│   ├── objective.md                   # Objectif final + situation actuelle
│   ├── stack.md                       # Stack technique complete
│   ├── workflow-process.md            # Processus d'iteration standard
│   └── session-state.md              # Etat de la derniere session (a mettre a jour)
├── docs/
│   ├── technical/                     <- DOCS TECHNIQUES (a maintenir a jour)
│   │   ├── n8n-endpoints.md           # Endpoints n8n, patterns API, pieges
│   │   ├── python-techniques.md       # Limites Python, contournements
│   │   ├── credentials.md             # Toutes les cles API (a actualiser)
│   │   ├── n8n-skills.md              # Noeuds communautaires, repos GitHub
│   │   └── mcp-setup.md              # Configuration MCP servers
│   ├── migration/                     <- GUIDE MIGRATION
│   │   └── n8n-self-hosted.md         # Cloud -> self-hosted Oracle
│   ├── architecture.md                # Architecture detaillee
│   ├── status.json                    # Status compact auto-genere
│   ├── data.json                      # Donnees d'eval completes
│   ├── index.html                     # Dashboard
│   └── knowledge-base.json            # Patterns d'erreurs connus
├── eval/                              <- SCRIPTS D'EVALUATION
│   ├── quick-test.py                  # Test 1-5 questions (smoke test)
│   ├── fast-iter.py                   # Test 10q/pipeline
│   ├── iterative-eval.py             # Progressif 5->10->50
│   ├── run-eval-parallel.py           # Full 200q
│   ├── node-analyzer.py              # Analyse granulaire node-par-node
│   ├── live-writer.py                # Ecriture resultats -> data.json
│   └── generate_status.py            # Regenere status.json
├── workflows/
│   ├── live/                          # Workflows actifs (sync depuis n8n)
│   ├── validated/                     # Workflows ayant passe 5/5 (archives)
│   ├── snapshots/                     # Backups horodates
│   └── sync.py                       # Sync n8n -> GitHub
├── mcp/                              # Serveurs MCP
├── datasets/                          # Questions par phase
├── db/                               # Schemas & scripts de peuplement
├── scripts/                          # Scripts utilitaires
│   ├── session-start.py              # Setup automatique de session
│   └── session-end.py               # Sauvegarde fin de session
├── phases/overview.md                # Strategie 5 phases
└── logs/                             # Traces d'execution
```

---

## Credentials (copier-coller rapide)

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

## Commandes Essentielles

| Action | Commande |
|--------|---------|
| **Status live** | `cat docs/status.json` |
| **Setup session** | `python3 scripts/session-start.py` |
| **Test 1q** | `python3 eval/quick-test.py --questions 1 --pipeline <cible>` |
| **Test 5q** | `python3 eval/quick-test.py --questions 5` |
| **Test 10q** | `python3 eval/fast-iter.py --label "..." --questions 10` |
| **Analyse node-par-node** | `python3 eval/node-analyzer.py --pipeline <cible> --last 5` |
| **Analyse execution** | `python3 eval/node-analyzer.py --execution-id <ID>` |
| **Eval progressive** | `python3 eval/iterative-eval.py --label "..."` |
| **Full eval 200q** | `python3 eval/run-eval-parallel.py --reset --label "..."` |
| **Phase 2 eval** | `python3 eval/run-eval-parallel.py --dataset phase-2 --reset --label "..."` |
| **Sync workflows** | `python3 workflows/sync.py` |
| **Regenerer status** | `python3 eval/generate_status.py` |
| **Phase gates** | `python3 eval/phase_gates.py` |
| **Fin de session** | `python3 scripts/session-end.py` |

---

## Processus d'Iteration (OBLIGATOIRE)

### Boucle : 1/1 -> 5/5 -> 10/10

1. **Test 1/1** sur le pipeline prioritaire (plus gros gap)
2. **Si echec** : analyse node-par-node -> identifier le noeud casse -> fixer UN noeud dans n8n
3. **Test 5/5** : analyse granulaire de CHAQUE execution
4. **Si >= 3/5** : passer a 10/10
5. **Si < 3/5** : iterer (retour a l'analyse)
6. **Test 10/10** : si >= 7/10, pipeline valide
7. **Sync + commit** apres chaque fix reussi
8. **Quand tous les pipelines passent 10/10** : lancer full 200q

### Analyse granulaire OBLIGATOIRE (CHAQUE test)

Pour CHAQUE question testee, inspecter CHAQUE noeud :
```bash
python3 eval/node-analyzer.py --execution-id <ID>
```

Verifier pour chaque noeud :
- **Input** : quelles donnees entrent ?
- **Output** : quelles donnees sortent ?
- **Duree** : combien de temps ?
- **Erreur** : echec ? quel message ?
- **Transformation** : information perdue ou corrompue ?

Types de noeuds a verifier :
- **LLM** (Intent Analyzer, Answer Synthesis) : longueur prompt, verbosite, hallucination
- **Routing** (Query Router, Dynamic Switch) : decision correcte ?
- **Retrieval** (Pinecone, Neo4j, Supabase) : nb documents, scores, resultats vides ?
- **Handler** (Task Result Handler, Fallback) : determination succes/echec correcte ?
- **Builder** (Response Builder) : reponse finale fidele aux sous-reponses ?

### Avant TOUT fix :
1. Quel noeud exact cause le probleme ?
2. Qu'est-ce qu'il recoit en input ?
3. Qu'est-ce qu'il produit en output ?
4. Pourquoi c'est faux ?
5. Quel changement precis va corriger ca ?

Voir `context/workflow-process.md` pour le detail complet.

---

## Modification de Workflows (CRITIQUE)

**n8n est la source de verite. GitHub est la copie.**

1. **DIAGNOSTIQUER** -> `python3 eval/node-analyzer.py`
2. **FIXER dans n8n** -> API REST (voir `docs/technical/n8n-endpoints.md`) :
   ```python
   wf = n8n_api("GET", f"/api/v1/workflows/{WF_ID}")
   for node in wf["nodes"]:
       if node["name"] == "Target Node":
           node["parameters"]["jsCode"] = NEW_CODE
   n8n_api("POST", f"/api/v1/workflows/{WF_ID}/deactivate")
   n8n_api("PUT", f"/api/v1/workflows/{WF_ID}", clean_payload)
   n8n_api("POST", f"/api/v1/workflows/{WF_ID}/activate")
   ```
3. **VERIFIER** -> test 5q minimum
4. **SYNC** -> `python3 workflows/sync.py`
5. **ARCHIVER** -> copier vers `workflows/validated/` si 5/5 passe
6. **COMMIT** -> push vers GitHub

**JAMAIS** :
- Editer les JSON workflow directement dans le repo
- Utiliser apply.py (DEPRECATED, reference historique uniquement)
- Fixer plusieurs noeuds en meme temps
- Deployer sans verifier avec au moins 5 questions

---

## Architecture (bref)

4 workflows n8n RAG sur `amoret.app.n8n.cloud` :

| Pipeline | Webhook Path | DB |
|----------|-------------|-----|
| **Standard** (Pinecone vector) | `/webhook/rag-multi-index-v3` | Pinecone |
| **Graph** (Neo4j entity graph) | `/webhook/ff622742-...` | Neo4j + Supabase |
| **Quantitative** (Supabase SQL) | `/webhook/3e0f8010-...` | Supabase |
| **Orchestrator** (route vers les 3) | `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` | Meta |

Tous les LLMs : `arcee-ai/trinity-large-preview:free` via OpenRouter ($0).
Details complets : `docs/architecture.md`

---

## Acces

| Ressource | Acces | Note |
|-----------|-------|------|
| n8n Webhooks + REST API | DIRECT | `amoret.app.n8n.cloud` |
| GitHub, Pinecone | DIRECT | git + HTTPS API |
| Supabase, Neo4j | BLOQUE | Proxy 403 -> passer par n8n |

---

## Regles d'Or

1. **UN fix par iteration** — jamais plusieurs noeuds simultanement
2. **n8n = source de verite** — editer dans n8n, sync vers GitHub
3. **Analyse granulaire AVANT chaque fix** — pas de fix aveugle
4. **Verifier AVANT de sync** — 5/5 doit passer
5. **Commit + push apres chaque fix reussi**
6. **`docs/status.json` est auto-genere** — ne pas editer
7. **Si 3+ regressions -> REVERT immediat**
8. **Mettre a jour `docs/technical/` apres chaque decouverte**
9. **Mettre a jour `context/session-state.md` en fin de session**
10. **Toujours travailler depuis `main`**, merger les branches feature

---

## Fichiers a maintenir a jour

| Fichier | Quand le mettre a jour |
|---------|----------------------|
| `context/session-state.md` | Fin de chaque session |
| `docs/technical/credentials.md` | Rotation de cle, nouveau service |
| `docs/technical/n8n-endpoints.md` | Nouveau endpoint decouvert |
| `docs/technical/python-techniques.md` | Nouveau contournement trouve |
| `docs/status.json` | Auto-genere par `generate_status.py` |

---

## Phase Roadmap

Phase 1 (200q) -> Phase 2 (1,000q) -> Phase 3 (~10Kq) -> Phase 4 (~100Kq) -> Phase 5 (1M+q)

### Gate thresholds :
| Stage | Accuracy | Error Rate |
|-------|----------|-----------|
| 5 questions | >=60% | <=40% |
| 10 questions | >=65% | <=20% |
| 50 questions | pipeline target | <=10% |

### Phase 1 targets :
| Pipeline | Target |
|----------|--------|
| Standard | >=85% |
| Graph | >=70% |
| Quantitative | >=85% |
| Orchestrator | >=70% |
| **Overall** | **>=75%** |

Details : `phases/overview.md`
