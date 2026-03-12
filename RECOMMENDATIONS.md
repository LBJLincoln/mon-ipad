# RECOMMANDATIONS UTILISATEUR — Toutes les demandes

> Compilé Session 105 (2026-03-12). Ce fichier centralise TOUTES les recommandations.
> Chaque session doit traiter au moins 1-2 items. Objectif: +10%/jour.

---

## A. TRAÇABILITÉ & QUESTIONS (PRIORITÉ HAUTE)

### A1. Table `question_source_map` dans Supabase
**Demande**: Chaque question eval doit être liée à son document d'origine (Supabase doc_id, Pinecone vector_id, URL source internet).
**Status**: ✗ NON FAIT
**Impact**: Sans ça, impossible de savoir quels documents produisent les bonnes/mauvaises réponses.
**Plan**:
1. Créer table Supabase: `question_id TEXT, source_type TEXT, source_id TEXT, source_url TEXT, source_metadata JSONB`
2. Modifier `generate-quant-questions.py` → injecter company_id + fiscal_year comme FK
3. Modifier `generate-graph-questions.py` → injecter Neo4j node_id
4. Modifier `expert-discovery.py` → déjà fait (source_hash), propager vers question_source_map
5. Modifier `generate-standard-questions.py` → lier aux datasets JSONL sources

### A2. Tracking de CHAQUE question à travers CHAQUE pipeline
**Demande**: Quand une question passe par standard/graph/quant/orchestrator, le résultat complet doit être relevé pour analyse.
**Status**: ✓ PARTIEL — eval_results tracke question_id + pipeline + sector + status + latency_ms + sources
**Manque**: La réponse complète (answer text) n'est pas stockée dans eval_results (seulement answer_preview tronqué)
**Plan**: Ajouter colonne `full_answer TEXT` dans eval_results

### A3. Origine internet des documents
**Demande**: Tracer l'URL source (Tavily, PDF) pour chaque document ingéré.
**Status**: ✓ PARTIEL — expert-discovery tracke URL+hash+domain. Tavily ingest tracke source dans Pinecone metadata.
**Manque**: Pas de table centralisée `document_registry` avec toutes les URLs sources.
**Plan**:
1. Créer/populer table `document_registry` (url, domain, sector, ingested_at, pinecone_ids[], supabase_doc_id)
2. Modifier tavily-mass-ingest.py et docling-s6-ingest.py pour écrire dans cette table

---

## B. ARCHITECTURE & AUTONOMIE (PRIORITÉ HAUTE)

### B1. Phases autonomes progressives
**Demande**: Chaque pipeline doit CONSTAMMENT tendre vers la phase supérieure (Stage 0→6).
**Status**: ✗ L'agentic loop fait 7 phases par cycle mais ne progresse pas (8 cycles stuck).
**Plan**:
1. Implémenter un "phase gate" automatique: si accuracy > seuil pendant 3 evals → promouvoir au stage suivant
2. Chaque stage a ses propres objectifs (voir technicals/PROGRESSION-PLAN.md)
3. Quand bloqué >3 cycles, escalader automatiquement (changer de stratégie, pas répéter)

### B2. 8 RAG pipelines (4×2 prod+test)
**Demande**: Chaque pipeline doit avoir un mirror identique pour tester sans affecter prod.
**Status**: ✗ NON FAIT
**Plan**:
1. S9 = staging (déjà séparé). Dupliquer les 4 workflows sur S9.
2. Script de promotion: S9→S1/S3/S5 quand tests passent.

### B3. Redis queue workers
**Demande**: Utiliser Upstash Redis pour queuer les tâches d'ingestion.
**Status**: ✗ NON FAIT — Creds Upstash existent, REST API fonctionne, mais pas de workers.
**Plan**: Créer `ops/redis-worker.py` qui consomme les jobs de la queue.

### B4. Codespace ALWAYS ALIVE avec Docling
**Demande**: Un Codespace GitHub permanent avec Docling installé pour traiter les PDFs 24/7.
**Status**: ✗ NON FAIT — Demandé depuis 1+ mois. codespace/setup-docling.sh existe mais pas de Codespace persistant.
**Alternative actuelle**: Docling S6 HF Space (CPU-basic, limité).

---

## C. ÉVALUATION & SCORING (PRIORITÉ MOYENNE)

### C1. Tests appropriés par pipeline
**Demande**: Chaque pipeline doit avoir ses propres tests adaptés (pas les mêmes questions pour tout).
**Status**: ✓ FAIT — generate-standard/graph/quant-questions.py séparés. eval-blast envoie à chaque pipeline.
**Amélioration**: Ajouter des tests spécifiques au type de réponse attendu:
- Standard: réponse textuelle avec citations sources
- Graph: réponse relationnelle avec entités liées
- Quant: réponse numérique exacte avec SQL
- Orchestrator: routage correct + réponse combinée

### C2. Scoring sémantique (pas keyword matching)
**Demande**: Le scoring actuel (keyword contains) génère trop de faux négatifs.
**Status**: ✗ eval-blast et mass-eval utilisent `expected_contains` (keyword match).
**Plan**:
1. Utiliser LLM judge (continuous-judge.py existe, pas intégré dans le scoring principal)
2. Score 1-5 par LLM au lieu de pass/fail binaire
3. Tracker le score dans eval_results

### C3. Objectifs finaux en tête par pipeline
**Demande**: Chaque pipeline doit avoir ses KPIs clairs, constamment visibles.
**Status**: ✓ PARTIEL — targets dans CLAUDE.md et PROGRESSION-PLAN.md
**Plan**: Les inclure dans STATUS.md (fait) et dans chaque cycle report de l'agentic loop.

### C4. Skills à convoquer et agents spécialisés
**Demande**: Les agents doivent faire du VRAI travail, pas juste monitorer.
**Status**: ✓ PARTIEL — agents-v2 (eval-blast, fixer, ingest-feed, regression) font du vrai travail.
**Amélioration**:
- Agent fixer devrait auto-déclencher des ingestions ciblées quand data gap détecté
- Agent regression devrait auto-rollback quand drop >10%
- Agentic loop devrait convoquer les skills Claude Code (/self-heal, /eval, /improve)

---

## D. DASHBOARD & MONITORING (PRIORITÉ MOYENNE)

### D1. Dashboard live auto-refresh
**Demande**: Un vrai dashboard constamment à jour, pas des snapshots statiques.
**Status**: ✗ Vercel = snapshot. GitHub Pages = snapshot. docs/dashboard.html = fetch local.
**Plan**:
1. Option A: Endpoint API sur la VM (python3 -m http.server sert health-status.json → dashboard le fetch)
2. Option B: Supabase Realtime → dashboard écoute les changements eval_results
3. Option C: GitHub Actions cron → update docs/status.json → GitHub Pages auto-deploy

### D2. Commander dashboard accessible
**Demande**: Le dashboard doit être facilement trouvable et fonctionnel.
**URLs actuelles**:
- GitHub Pages: https://lbjlincoln.github.io/rag-dashboard/docs/ (données statiques)
- Vercel: docs-8ie0wqarg-alexis-morets-projects.vercel.app (snapshot)
- VM local: http://34.136.180.66:8080 (health-status.json servi, mais pas de HTML)
**Plan**: Pousser docs/dashboard.html vers GitHub Pages avec un cron GitHub Actions pour mettre à jour status.json

### D3. Executive summary centralisé
**Demande**: Vue claire en un coup d'œil de tout le système.
**Status**: ✓ FAIT — STATUS.md créé (Session 105).

---

## E. INGESTION & DATA (PRIORITÉ HAUTE pour BTP)

### E1. Ingérer DTU/Eurocodes/CCTP pour BTP
**Demande**: BTP est à ~20% accuracy car DATA GAP massif.
**Status**: ✗ Tavily tourne mais ne trouve pas de DTU complets (paywall).
**Plan**:
1. Chercher des sources ouvertes: CSTB, Légifrance (codes construction)
2. Ingérer les Eurocodes disponibles en PDF
3. Cibler CCTP templates publics (marchés publics = BOAMP)

### E2. Continuous Tavily→Docling→Ingestion→Enrichment
**Status**: ✓ FAIT — continuous-ingest.py daemon tourne 24/7, 5 streams.

### E3. 100+ types de documents par secteur
**Status**: ✗ PARTIEL — ~20 types actuellement. Cible 100+.
**Plan**: Utiliser la liste dans technicals/data/sector-datasets.md pour prioriser.

---

## F. NETTOYAGE & MAINTENANCE (FAIT EN S105)

### F1. Supprimer/centraliser les docs obsolètes
**Status**: ✓ FAIT Session 105
- 2,582 → 928 fichiers
- 55M → 3.8M logs
- 4 docs supprimés, 3 archivés, monetisation archivée
- 7 docs essentiels identifiés
- STATUS.md = source unique de vérité

### F2. Docs > 3 jours = potentiellement obsolètes
**Règle**: Avec +10%/jour d'objectif, les docs de >3 jours doivent être revus ou supprimés.
**Plan**: STATUS.md mis à jour chaque session. Les autres docs sur demande.

---

## PRIORITÉ D'EXÉCUTION

| # | Action | Impact | Effort | Prochaine session |
|---|--------|--------|--------|-------------------|
| 1 | A1: question_source_map | HAUT | 2h | OUI |
| 2 | E1: DTU/Eurocodes BTP | HAUT | 3h | OUI |
| 3 | B1: Phase gates automatiques | HAUT | 2h | OUI |
| 4 | C2: Scoring sémantique | HAUT | 1h | OUI |
| 5 | D1: Dashboard live | MOYEN | 2h | Prochaine |
| 6 | A3: document_registry | MOYEN | 1h | Prochaine |
| 7 | B2: 8 pipelines prod+test | MOYEN | 3h | Suivante |
| 8 | B3: Redis workers | FAIBLE | 2h | Plus tard |
| 9 | B4: Codespace Docling | FAIBLE | 1h | Plus tard |
| 10 | C4: Agents auto-skill | FAIBLE | 2h | Plus tard |
