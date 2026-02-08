# Dashboard Rewrite Specification

> Ce document est le brief complet pour réécrire `docs/index.html`.
> La session précédente a déjà mis à jour CLAUDE.md et STATUS.md avec les bons chemins.
> Il reste à réécrire le dashboard.

## Ce qui a été fait

1. **CLAUDE.md** — Réécrit avec les bons chemins (`eval/`, `db/`, `workflows/`, `datasets/`), protocole d'itération en 7 étapes, phase gates
2. **STATUS.md** — Réécrit avec file map correct et protocole d'itération
3. **Analyse complète du repo** — Structure, data.json, tous les fichiers vérifiés
4. **Push effectué** sur `claude/analyze-optimize-dashboard-Bovgt`

## Ce qui reste à faire

**Réécrire `docs/index.html`** — Passer de 8 onglets basiques à 10 onglets optimisés pour le cycle d'itération rapide Phase 1.

---

## Problèmes du dashboard actuel (8 tabs, 1450 lignes)

1. **Pas de Command Center** — Aucune vue d'ensemble à-un-coup-d'oeil
2. **Pas de Phase Tracker** — CLAUDE.md mentionne 5 phases mais le dashboard ne les montre pas
3. **Pas d'Error Analysis** — `error_type` capturé dans data.json mais jamais visualisé
4. **Pas d'AI Insights** — L'onglet "Agentic API" est statique, pas dynamique
5. **Pas de burndown** vers les targets de phase
6. **Pas de distribution F1** — F1 montré par cellule mais pas d'histogramme
7. **Pas de suivi des blockers** — Blockers critiques invisibles
8. **Onglets dans le mauvais ordre** — Test Matrix en premier au lieu d'un Command Center

---

## Architecture data.json (v2) — Champs disponibles

```
data.json = {
  meta: { version, generated_at, status, phase, total_unique_questions, total_test_runs, total_iterations, total_cost_usd }
  iterations[]: { id, number, timestamp_start, timestamp_end, label, description, changes_applied[],
                  results_summary: { [pipeline]: { tested, correct, errors, accuracy_pct, avg_latency_ms, p95_latency_ms, avg_f1 } },
                  total_tested, total_correct, overall_accuracy_pct,
                  questions[]: { id, rag_type, correct, f1, latency_ms, answer, expected, match_type, error, error_type, timestamp } }
  question_registry: { [qid]: { id, question, expected, expected_detail, rag_type, category, entities[], tables[],
                                 runs[]: { iteration_id, iteration_number, correct, f1, latency_ms, match_type, error, error_type, answer, timestamp },
                                 total_runs, pass_count, pass_rate, current_status, last_tested, best_f1, trend } }
  pipelines: { [name]: { endpoint, target_accuracy, trend[]: { iteration_id, iteration_number, accuracy_pct, tested, errors, avg_latency_ms } } }
  workflow_changes[]: { timestamp, description, change_type, files_changed[], affected_pipelines[], before_metrics, after_metrics }
  databases: { pinecone: { total_vectors, namespaces:{} }, neo4j: { total_nodes, ... }, supabase: { total_rows, ... } }
  db_snapshots[]: { snapshot_id, timestamp, trigger, pinecone_vectors, neo4j_nodes, neo4j_relationships, supabase_rows }
  execution_logs[]: { timestamp, question_id, rag_type, correct, f1, latency_ms, error_type, error_preview, answer_preview }
  quick_tests[]: { timestamp, pipeline, query, status, latency_ms, response_preview, error, trigger }
  workflow_versions: { [pipeline]: { version, hash, timestamp, snapshot_file, name, webhook, summary: { total_nodes, node_types, models_used, node_names }, diff_from_previous } }
  workflow_history[]: { timestamp, pipeline, version, hash, diff_summary, snapshot_file }
  history[]: { timestamp, event, standard, graph, quantitative, orchestrator, total_tested }
}
```

---

## Spec des 10 onglets

### Tab 1: COMMAND CENTER (default, nouveau)
**But**: Vue d'ensemble immédiate pour savoir où on en est et quoi faire.

Contenu:
- **Phase Progress** — Barre "Phase 1: Baseline" avec % de complétion (calculé: combien de pipeline targets sont atteints)
- **4 Pipeline Gauges** — Jauges circulaires ou barres horizontales: accuracy actuelle vs target, couleur dynamique (rouge/jaune/vert)
- **Overall Accuracy** — Gros chiffre central avec delta vs itération précédente
- **Key Metrics Row** — 4 cards: Total questions, Pass rate, Error count, Avg latency
- **Blockers Panel** — Détection auto: si error_rate > 20% → blocker, si accuracy stagnante 2+ iters → plateau
- **Next Action** — Recommandation auto basée sur les données:
  - Pipeline avec le plus gros gap → "Focus: Orchestrator (-20.4pp)"
  - Type d'erreur dominant → "Fix: TIMEOUT (37 errors)"
  - Si plateau → "Plateau detected: try different approach"
- **Recent Activity** — 5 derniers workflow_changes + dernière itération

Sources données: `meta`, `iterations[-1]`, `iterations[-2]`, `pipelines`, `question_registry` (agrégé), `workflow_changes[-5:]`

### Tab 2: TEST MATRIX (existant, amélioré)
**But**: Grille Questions x Itérations avec heat map.

Améliorations:
- Heat map F1 gradient (pas juste vert/rouge, mais gradient d'intensité)
- Couleurs: F1=0 rouge foncé, F1=0.5 orange, F1=1.0 vert vif
- Colonnes d'itération avec header cliquable pour voir le résumé
- Compteurs en bas: X passing, Y failing, Z errors pour la sélection filtrée
- Garder les filtres existants (pipeline, status, search)

Sources: `iterations`, `question_registry`

### Tab 3: ITERATIONS (existant, amélioré)
**But**: Suivi temporel des itérations avec burndown vers targets.

Améliorations:
- **Burndown Chart** (nouveau) — Chart montrant le gap restant vers chaque target au fil des itérations
  - Lignes horizontales à 85% (standard), 70% (graph/orch), 85% (quant)
  - Courbes d'accuracy qui montent vers ces lignes
- **Velocity** — Calcul du gain moyen par itération, estimation du nombre d'itérations restantes
- **Iteration Comparison** — Garder tel quel (fixed/broken/improved/regressed)
- **Timeline** — Garder tel quel

Sources: `iterations`, `pipelines.trend`

### Tab 4: PIPELINES (existant, amélioré)
**But**: Deep-dive par pipeline.

Améliorations:
- **Error Type Breakdown** — Donut chart par pipeline: TIMEOUT vs NETWORK vs EMPTY_RESPONSE vs SQL_ERROR vs ENTITY_MISS
  - Données: parcourir `question_registry[*].runs[*].error_type`
- **F1 Distribution** — Histogramme des scores F1 par pipeline (bins: 0-0.1, 0.1-0.2, ..., 0.9-1.0)
  - Données: `question_registry[*].runs[*].f1` groupé par `rag_type`
- **Latency Percentiles** — P50, P75, P90, P95 par pipeline (pas juste avg)
- Garder: accuracy cards, accuracy chart, error rate chart, latency chart, category breakdown

Sources: `iterations`, `question_registry`, `pipelines`

### Tab 5: ERROR ANALYSIS (nouveau)
**But**: Comprendre et prioriser les erreurs.

Contenu:
- **Error Summary Cards** — 4 cards: Total errors, Error rate, Most common type, Most affected pipeline
- **Error Type Distribution** — Bar chart horizontal: TIMEOUT (X), NETWORK (Y), EMPTY_RESPONSE (Z), etc.
  - Données: compter `error_type` dans `question_registry[*].runs[*]` où `error` is not null
- **Error Timeline** — Scatter plot: timestamp vs error_type, coloré par pipeline
- **Most Erroring Questions** — Table: qid, question, pipeline, error count, error types, dernière erreur
  - Triée par nombre d'erreurs décroissant
- **Error Patterns** — Corrélation: quels questions erreur ensemble? (même itération)
- **Pipeline Error Heatmap** — Grille: pipeline x error_type, intensité = count

Sources: `question_registry` (runs avec error), `execution_logs`, `iterations`

### Tab 6: PHASE TRACKER (nouveau)
**But**: Roadmap 5 phases avec exit criteria live.

Contenu:
- **Phase Roadmap** — 5 étapes horizontales: Phase 1 (active, pulsating), Phase 2-5 (grisées)
  - Chaque phase: nom, nombre de questions, statut (locked/active/completed)
- **Current Phase Detail** — Phase 1 exit criteria checklist:
  - [x/✗] Standard ≥ 85% (actuel: 82.6%)
  - [x/✗] Graph ≥ 70% (actuel: 52.0%)
  - [x/✗] Quantitative ≥ 85% (actuel: 80.0%)
  - [x/✗] Orchestrator ≥ 70% (actuel: 49.6%)
  - [x/✗] Overall ≥ 75% (actuel: 67.7%)
  - [x/✗] Orchestrator P95 < 15s
  - [x/✗] Orchestrator error rate < 5%
  - [x/✗] 3 consecutive stable iterations
- **DB Readiness Gauges** — Pour la phase SUIVANTE (Phase 2):
  - Neo4j: "Entity ingestion needed" (❌)
  - Supabase: "Table data parsing needed" (❌)
  - Pinecone: "No change needed" (✅)
- **Phase Metrics Comparison** — Table: Phase targets vs current accuracy

Sources: `meta.phase`, `pipelines`, `iterations`, `databases`, hardcoded phase targets from CLAUDE.md

### Tab 7: QUESTIONS EXPLORER (existant, gardé tel quel)
Sources: `question_registry`

### Tab 8: SMOKE TESTS (existant, gardé tel quel)
Sources: `quick_tests`

### Tab 9: WORKFLOWS & CHANGES (existant, fusionné)
Fusion des anciens tabs "Workflows" et "Changes Log" en un seul.
Sources: `workflow_versions`, `workflow_history`, `workflow_changes`, `db_snapshots`

### Tab 10: AI INSIGHTS (nouveau, remplace "Agentic API" statique)
**But**: Analyse live + recommandations auto-générées + API schema.

Contenu:
- **Live Analysis** (calculé côté client):
  - "Biggest opportunity: Orchestrator (+20.4pp potential)"
  - "Most errors: TIMEOUT (37 occurrences, 72% of all errors)"
  - "Plateau alert: Quantitative unchanged across 2 iterations"
  - "Flaky questions: 17 questions with pass_rate between 0.3-0.7"
  - "Regression risk: 14 questions regressing"
- **Decision Matrix** — Tableau: pour chaque pipeline, accuracy, gap, error rate, recommended action
- **Iteration Protocol** — Affichage du cycle Step 0-7 de CLAUDE.md
- **API Schema** — Garder le schema docs existant
- **Decision Rules** — Garder les règles existantes

Sources: Tout `data.json`, calculs côté client

---

## Contraintes techniques

- **Single HTML file** — Tout dans `docs/index.html` (CSS + HTML + JS)
- **Chart.js 4.4.1** — CDN déjà importé, à garder
- **Auto-refresh 15s** — `setInterval(loadData, 15000)`
- **Dark theme** — Palette existante excellente, à garder:
  ```
  --bg:#0b0f15; --s1:#111720; --s2:#171d28; --s3:#1e2533; --bd:#2a3140;
  --tx:#dce4f0; --tx2:#7f8da0; --tx3:#4e5a6d; --ac:#4f8efa;
  --gn:#2dd47a; --rd:#f05555; --yl:#e8b820; --or:#f08030; --pp:#a060f0; --cy:#20c0d8
  ```
- **Pipeline colors**: standard=#4f8efa, graph=#a060f0, quantitative=#20c0d8, orchestrator=#f08030
- **Responsive** — Grid 4→2→1 colonnes
- **Pas de dépendances externes** sauf Chart.js et Google Fonts (Inter + JetBrains Mono)
- **Compatible data.json v2** — Toutes les clés listées ci-dessus

---

## Ordre de construction recommandé

1. Écrire le HTML structure (10 panels)
2. CSS (réutiliser ~90% de l'existant, ajouter styles pour gauges, roadmap, donut)
3. Tab 1 Command Center (le plus important, vue par défaut)
4. Tab 6 Phase Tracker
5. Tab 5 Error Analysis
6. Tab 10 AI Insights
7. Tabs 2-4 (Matrix, Iterations, Pipelines) — porter et améliorer l'existant
8. Tabs 7-9 — porter l'existant

---

## Prompt pour la prochaine session

```
Réécris docs/index.html en suivant exactement la spec dans DASHBOARD-SPEC.md.
Le dashboard doit avoir 10 onglets, être optimisé pour le cycle d'itération rapide
de Phase 1 (voir CLAUDE.md pour le protocole). Utilise les données de docs/data.json
(format v2, voir la spec pour la structure complète). Garde le dark theme existant,
Chart.js 4.4.1, auto-refresh 15s. Push sur la branche claude/analyze-optimize-dashboard-Bovgt
après chaque étape majeure.
```
