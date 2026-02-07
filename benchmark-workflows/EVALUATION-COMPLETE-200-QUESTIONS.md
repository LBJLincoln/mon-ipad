# Evaluation Complète — 200 Questions sur 4 Moteurs RAG
**Date:** 2026-02-07
**Tenant:** benchmark
**Durée totale:** ~46 minutes

---

## Résumé Exécutif

| Moteur RAG | Questions | Correct (brut) | Correct (réévalué) | Latence moy. |
|---|---|---|---|---|
| **Quantitative RAG (WF4)** | 50 | 8 (16%) | **35 (70%)** | 6,103ms |
| **Graph RAG (WF2)** | 50 | 6 (12%) | **~5-10 (10-20%)** | 4,848ms |
| **Standard RAG (WF5)** | 50 | 19 (38%) | **~25 (50%)** | 5,514ms |
| **Orchestrator (V10.1)** | 50 | 0 (0%) | **0 (0%)** | 31,139ms |
| **TOTAL** | **200** | 33 (16.5%) | **~65-70 (32-35%)** | — |

> **Note:** Le score "brut" était faussé par un bug dans l'extracteur de nombres (extrayait l'année "2023" au lieu du montant financier). La réévaluation montre un taux réel bien supérieur, surtout pour le Quantitative RAG.

---

## 1. Quantitative RAG (WF4) — 70% après réévaluation

### Points forts
- **35/50 réponses numériquement correctes** (après fix de l'évaluateur)
- Les requêtes sur `balance_sheet`, `products`, `employees` fonctionnent très bien
- Les requêtes FY sur une seule entreprise/année fonctionnent parfaitement
- Le SQL généré est syntaxiquement correct dans ~90% des cas
- Le self-healing (SQL repair) fonctionne pour les erreurs simples

### Problèmes identifiés

#### P1 — Double-comptage FY + Quarters (6 questions, 12%)
La table `financials` contient des lignes FY ET Q1-Q4. Les requêtes `SUM()` sans filtre `period = 'FY'` additionnent FY + Q1+Q2+Q3+Q4, donnant exactement 2x le bon résultat.

**Exemple:** TechVision revenue 2023 → SQL retourne $13.49B au lieu de $6.745B

**Fix appliqué:** Ajout de `_IMPORTANT_NOTE` dans le Schema Context Builder pour expliquer la sémantique de la colonne `period`. **Déployé pendant le benchmark** — les questions 25-50 bénéficient partiellement du fix.

**Fix recommandé supplémentaire:**
```sql
-- Option 1: Vue SQL qui ne retourne que les périodes FY
CREATE VIEW financials_fy AS
SELECT * FROM financials WHERE period = 'FY';

-- Option 2: Ajouter une contrainte dans le prompt SQL
-- "Pour les totaux annuels, utiliser TOUJOURS period = 'FY'"
```

#### P2 — HTTP 500 sur requêtes employees/products (5 questions, 10%)
Certaines tables (employees, products) provoquent des erreurs 500. Possible cause : le SQL généré ne gère pas correctement les types de données ou les JOINs.

**Fix recommandé:** Ajouter des exemples de requêtes types dans le Schema Context Builder pour chaque table.

#### P3 — Requêtes de calcul (growth %, comparaisons) échouent
Le LLM SQL génère parfois des calculs complexes incorrects (ex: "217%" au lieu de "58.7%").

**Fix recommandé:** Ajouter des exemples de calcul de croissance dans le prompt système.

---

## 2. Graph RAG (WF2) — 10-20%

### Points forts
- Les entités directes sont trouvées (Einstein, Fleming, Marie Curie)
- Les réponses sont factuellement correctes quand le contexte est trouvé
- La synthèse LLM enrichit correctement au-delà du graph brut

### Problème majeur — Neo4j traversal insuffisant

**~80% des réponses disent "context does not contain information"**

Les entités existent dans Neo4j (vérifiable via les scripts de population) mais le pipeline Graph RAG ne les retrouve pas. L'analyse pointe vers :

#### P1 — HyDE Entity Extraction ne match pas les noms Neo4j
L'étape HyDE extrait des entités du texte de la question, mais les noms extraits ne correspondent pas exactement aux noms dans Neo4j.

**Exemple:** Question "Where did Alan Turing study?" → HyDE extrait peut-être "Turing" mais Neo4j cherche `name = "Alan Turing"`.

**Fix recommandé:**
```javascript
// Dans le Neo4j Query Builder, ajouter un fuzzy match:
MATCH (n:Entity)
WHERE n.name =~ '(?i).*' + $entity_name + '.*'
  AND (n.tenant_id = $tenant_id OR n.tenant_id IS NULL)
```

#### P2 — Pinecone namespace vide pour les entités curées
Les embeddings Pinecone proviennent de datasets HuggingFace (squad_v2, hotpotqa, etc.) mais les questions portent sur des entités curées (Einstein, Tesla, etc.) qui ne sont PAS dans ces datasets.

**Fix recommandé:**
1. Créer des embeddings pour chaque entité Neo4j + ses relations
2. Ingérer ces embeddings dans Pinecone avec un namespace dédié (ex: `benchmark-entities`)
3. Le Graph RAG devrait chercher aussi dans ce namespace

#### P3 — Community Summaries sous-exploitées
Les community summaries contiennent exactement les informations attendues ("Marie Curie pioneered radioactivity research in Paris and won Nobel Prizes in Physics and Chemistry") mais le pipeline ne les retrouve apparemment pas.

**Fix recommandé:** Vérifier que la requête `WHERE entity_names && ARRAY[...]::text[]` utilise bien les noms extraits. Ajouter un fallback sur `ILIKE` si le match exact échoue.

---

## 3. Standard RAG (WF5) — ~50%

### Points forts
- **Factual questions: 54% correct** — bonnes performances sur les questions directes
- Le pipeline Pinecone + BM25 hybride retrouve bien les documents pertinents
- Les réponses sont bien sourcées (citations [1], [2], etc.)
- Latence moyenne de 5.5s — acceptable

### Problèmes identifiés

#### P1 — Definitions: seulement 24%
Les questions "What is X?" retournent souvent "context does not contain information" car les datasets ingérés (squad_v2, triviaqa) ne contiennent pas forcément de définitions pour tous les termes.

**Fix recommandé:**
1. Ingérer des datasets encyclopédiques (Wikipedia, etc.) dans Pinecone
2. Ajouter un fallback LLM knowledge quand le contexte est insuffisant
3. Augmenter le `top_k` de 10 à 20 pour les questions définitionnelles

#### P2 — Namespace selection
Le runner utilise un namespace fixe par question, mais le Standard RAG devrait pouvoir chercher dans TOUS les namespaces.

**Fix recommandé:** Utiliser un meta-namespace ou chercher dans les 5 namespaces les plus pertinents en parallèle.

---

## 4. Orchestrator (V10.1) — 0% (CRITIQUE)

### Problème: Réponses vides systématiques

Les 50 questions retournent HTTP 200 mais avec un corps vide. Le workflow V10.1 s'exécute (confirmé par les latences de 10-70s) mais ne retourne pas de résultat au webhook.

### Diagnostic probable

L'orchestrateur exécute ses sous-workflows (routing → RAG engine → synthesis) mais le **noeud de réponse final ne renvoie pas au webhook**. Possible causes :

1. **Timeout du webhook Respond** : le workflow interne met trop de temps et le webhook expire avant la réponse
2. **Erreur dans le Response Aggregator** : le noeud qui combine les réponses des sous-workflows crash silencieusement
3. **Format de payload incompatible** : le webhook attend un format différent de celui envoyé

### Fix recommandé (prioritaire)

```javascript
// 1. Vérifier que le webhook a un "Respond to Webhook" node correctement connecté
// 2. Ajouter un timeout handler qui retourne une réponse partielle
// 3. Tester manuellement via curl:
curl -s -X POST "https://amoret.app.n8n.cloud/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0" \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "tenant_id": "benchmark"}' | head -c 500
```

### Action immédiate
1. Ouvrir le workflow V10.1 dans l'éditeur n8n
2. Vérifier les connexions entre le dernier noeud et le "Respond to Webhook"
3. Ajouter des logs/OTEL sur chaque noeud pour identifier où le flux se perd
4. Tester avec une question simple en mode debug

---

## 5. Plan d'Amélioration — Priorités

### Sprint 1 — Quick Wins (impact immédiat)

| # | Action | Impact attendu | Effort |
|---|---|---|---|
| 1 | **Fix Orchestrator webhook response** | Orch 0% → 40-60% | Moyen |
| 2 | **Créer vue `financials_fy`** + exemples SQL | Quant 70% → 80%+ | Faible |
| 3 | **Neo4j fuzzy matching** dans WF2 | Graph 10% → 30%+ | Faible |
| 4 | **Ingérer entités Neo4j dans Pinecone** | Graph 30% → 50%+ | Moyen |

### Sprint 2 — Améliorations structurelles

| # | Action | Impact attendu | Effort |
|---|---|---|---|
| 5 | Ajouter exemples de requêtes SQL dans le prompt | Quant 80% → 90%+ | Faible |
| 6 | Fallback LLM knowledge pour Standard RAG | Std 50% → 65%+ | Moyen |
| 7 | Multi-namespace search pour Standard RAG | Std 65% → 75%+ | Moyen |
| 8 | Community summaries entity matching fix | Graph 50% → 65%+ | Moyen |

### Sprint 3 — Optimisations avancées

| # | Action | Impact attendu | Effort |
|---|---|---|---|
| 9 | Reranker fine-tuning pour Graph RAG | +5-10% | Élevé |
| 10 | SQL generation few-shot examples | +5-10% Quant | Moyen |
| 11 | Orchestrator parallel execution | -30% latence | Élevé |
| 12 | Embeddings enrichis avec metadata | +10% overall | Élevé |

---

## 6. Métriques de Référence (Baseline)

Ces résultats servent de **baseline** pour mesurer les améliorations futures :

```
BASELINE 2026-02-07 (200 questions)
├── Quantitative RAG:  70% accuracy, 6.1s avg latency
├── Graph RAG:         10% accuracy, 4.8s avg latency
├── Standard RAG:      38% accuracy (50% réévalué), 5.5s avg latency
├── Orchestrator:       0% accuracy (réponses vides), 31s avg latency
└── Overall:           ~35% accuracy (réévalué)
```

### Objectifs cibles
- **Phase 1 (2 semaines):** Quant 85%, Graph 40%, Standard 65%, Orchestrator 50%
- **Phase 2 (1 mois):** Quant 90%, Graph 60%, Standard 75%, Orchestrator 70%
- **Phase 3 (2 mois):** Quant 95%, Graph 75%, Standard 85%, Orchestrator 85%

---

## 7. Corrections Déjà Appliquées

1. **Schema Context Builder (WF4):** Ajout de sample values pour company_name, period, etc.
2. **Prepare SQL Request (WF4):** Ajout de consignes d'utilisation des valeurs exactes
3. **Response Formatter (WF4):** Détection des résultats NULL sur agrégations → status `DATA_NOT_FOUND`
4. **Schema Context Builder (WF4):** Ajout note explicative sur la colonne `period` (FY vs Q1-Q4)
5. **Déploiement:** Workflows WF2 et WF4 redéployés sur n8n cloud

---

## Fichiers de Résultats

- `benchmark-50x2-results.json` — 50 Quantitative + 50 Graph RAG
- `benchmark-standard-orchestrator-results.json` — 50 Standard + 50 Orchestrator
- `benchmark-50x2-questions.json` — Questions Graph + Quant
- `benchmark-standard-orchestrator-questions.json` — Questions Standard + Orchestrator
- `verify-sql-results.md` — Analyse initiale du bug TechVision
