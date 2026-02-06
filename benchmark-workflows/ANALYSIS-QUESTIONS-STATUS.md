# Analyse Complète des Questions de Test RAG

**Date**: 2026-02-06
**Auteur**: Analyse automatisée
**Objectif**: Inventaire complet des questions posées, restantes, et diagnostic qualité

---

## 1. INVENTAIRE DES DATASETS

### 1.1 Datasets ingérés dans Supabase (10 datasets — 28,053 questions)

| # | Dataset | Questions | Catégorie | RAG cible initial | Statut |
|---|---------|-----------|-----------|-------------------|--------|
| 1 | hotpotqa | 3,320 | multi_hop_qa | graph | En Supabase, 100% erreur |
| 2 | frames | 1,943 | rag_benchmark | standard | En Supabase, 100% erreur |
| 3 | squad_v2 | 2,600 | single_hop_qa | standard | 69 réponses, 2,451 erreurs |
| 4 | popqa | 2,250 | single_hop_qa | standard | En Supabase, 100% erreur |
| 5 | pubmedqa | 1,340 | domain_medical | standard | En Supabase, 100% erreur |
| 6 | triviaqa | 3,250 | single_hop_qa | standard | En Supabase, 100% erreur |
| 7 | finqa | 2,830 | domain_finance | quantitative | En Supabase, 100% erreur |
| 8 | msmarco | 5,250 | retrieval | standard | En Supabase, 100% erreur |
| 9 | narrativeqa | 2,750 | long_form_qa | standard | En Supabase, 100% erreur |
| 10 | asqa | 2,750 | long_form_qa | standard | En Supabase, 100% erreur |

**Total ingéré**: 28,283 entrées en Supabase
**Avec réponse réelle**: 69 (0.24%)
**Avec erreur**: 28,134 (99.5%)
**Erreur root**: `fetch is not defined` (corrigée depuis)

### 1.2 Dataset 1000 Questions Graph+Quantitative (Local)

| Dataset | Type RAG | Questions | Statut |
|---------|----------|-----------|--------|
| musique | graph | 200 | NON POSÉES |
| 2wikimultihopqa | graph | 300 | NON POSÉES |
| finqa | quantitative | 200 | NON POSÉES |
| tatqa | quantitative | 150 | NON POSÉES |
| convfinqa | quantitative | 100 | NON POSÉES |
| wikitablequestions | quantitative | 50 | NON POSÉES |

**Total**: 500 graph + 500 quantitative = **1,000 questions jamais envoyées au n8n**

---

## 2. QUESTIONS EFFECTIVEMENT POSÉES ET RÉPONSES OBTENUES

### 2.1 Benchmark initial (28,053 questions) — CATASTROPHIQUE

- **Résultat**: 100% d'échecs — erreur `fetch is not defined`
- **Cause**: Le node Code de n8n n'a pas accès à `fetch()` dans son sandbox
- **Correction**: Remplacé par `this.helpers.httpRequest()`
- **Aucune réponse valide** n'a été obtenue de ce run

### 2.2 Diagnostic 30 questions (post-fix)

| RAG Type | Questions | Avec réponse | Erreurs | Statut |
|----------|-----------|-------------|---------|--------|
| Standard | 10 | 10 (100%) | 0 | FONCTIONNE |
| Graph | 10 | 10 (100%) | 0 | FONCTIONNE* |
| Quantitative | 10 | 0 (0%) | 0 | BY DESIGN** |

*Les réponses Graph sont de qualité catastrophique (voir section 3)
**Le Quantitative RAG est un système Text-to-SQL — il rejette correctement les questions générales (squad_v2). Il a besoin de questions financières/tabulaires.

### 2.3 Benchmark Multi-RAG (13,648 questions lancées)

Le `run-full-benchmark-multirag.py` a lancé 13,648/15,648 questions (87.2%).

| Dataset | graph | quant | Total |
|---------|-------|-------|-------|
| frames | 824 | 824 | 1,648 |
| squad_v2 | 1,000 | 1,000 | 2,000 |
| popqa | 1,000 | 1,000 | 2,000 |
| pubmedqa | 500 | 500 | 1,000 |
| triviaqa | 1,000 | 1,000 | 2,000 |
| finqa | 500 | 500 | 1,000 |
| msmarco | 1,000 | 1,000 | 2,000 |
| narrativeqa | 500 | 500 | 1,000 |
| asqa | 500 | 500 | 1,000 |

**ATTENTION**: Ces 13,648 succès sont des "HTTP 200" mais **NE signifient PAS que les réponses sont correctes**. Le webhook renvoie un run_id et un statut. Les résultats réels sont écrits dans Supabase, et comme on le voit, seules 69 réponses ont été réellement stockées.

### 2.4 Résumé: Combien de questions ont été RÉELLEMENT répondues?

| Catégorie | Posées | Réponses valides | % |
|-----------|--------|------------------|---|
| Benchmark 28K (fetch bug) | 28,053 | 0 | 0% |
| Diagnostic 30q | 30 | 20 | 67% |
| Multi-RAG 13.6K | 13,648 | ~69 (Supabase) | 0.5% |
| 1000 Graph+Quant | 0 | 0 | N/A |

**TOTAL RÉPONSES VALIDES: ~69-89 sur 29,053+ questions lancées**

---

## 3. DIAGNOSTIC QUALITÉ DES RÉPONSES EXISTANTES

### 3.1 Standard RAG — FONCTIONNEL mais IMPARFAIT

Exemple (squad_v2, question "In what country is Normandy located?"):
- **Attendu**: "France"
- **Reçu**: "Normandy is located in northern France [1], [3]."
- **Verdict**: Correct mais verbeux, avec citations non demandées, et le modèle répond en français pour certaines questions anglaises

**Problèmes identifiés**:
1. Réponses en français au lieu d'anglais (le prompt du RAG workflow est en français)
2. Réponses trop longues/verbeuses (paragraphes au lieu de phrases concises)
3. accuracy=0 systématique car l'évaluation compare en exact match
4. L'évaluation est cassée (compare `"France"` à `"Normandy is located in northern France"` → 0)

### 3.2 Graph RAG — CATASTROPHIQUE

Exemple (squad_v2, "In what country is Normandy located?"):
- **Attendu**: "France"
- **Reçu**: "The Normans were a population of mixed Frankish and Scandinavian origin. They gave their name to Normandy, a region in northern France. | Normans Frankish Scandinavian Normandy France medieval Europe political military cultural. | Machine learning uses neural networks."
- **Verdict**: **GARBAGE** — concaténation de fragments de communauté Neo4j

**Problèmes identifiés**:
1. **Le Graph RAG renvoie des fragments de "community summaries" bruts**, pas des réponses
2. Les réponses sont des concaténations de 3 fragments séparés par ` | `
3. Contient du contenu NON PERTINENT ("Machine learning uses neural networks" pour une question sur la Normandie)
4. Pas de raisonnement multi-hop — juste du retrieval de communautés
5. L'answer extraction lit les résumés de communauté au lieu de la réponse LLM

### 3.3 Quantitative RAG — RÉPONSES VIDES sur mauvais datasets

Exemple (squad_v2, "In what country is Normandy located?"):
- **Attendu**: "France"
- **Reçu**: "" (vide)
- **Verdict**: **BY DESIGN** — le Quantitative RAG est un Text-to-SQL qui rejette les questions non-financières

**Points importants**:
- Quantitative RAG DOIT être testé avec finqa, tatqa, convfinqa, wikitablequestions
- Il est NORMAL qu'il retourne "" pour squad_v2, popqa, etc.

---

## 4. QUESTIONS RESTANTES PAR PRIORITÉ

### Priorité 1: 1,000 Questions Graph+Quantitative spécialisées (JAMAIS POSÉES)

Ces questions ont été générées spécifiquement pour tester Graph et Quantitative RAG mais n'ont JAMAIS été envoyées au système n8n.

| Dataset | Type | Questions | Source HuggingFace |
|---------|------|-----------|--------------------|
| musique | graph | 200 | bdsaglam/musique |
| 2wikimultihopqa | graph | 300 | framolfese/2WikiMultihopQA |
| finqa | quantitative | 200 | dreamerdeo/finqa |
| tatqa | quantitative | 150 | galileo-ai/ragbench |
| convfinqa | quantitative | 100 | MehdiHosseiniMoghadam/ConvFinQA |
| wikitablequestions | quantitative | 50 | TableSenseAI/WikiTableQuestions |

### Priorité 2: Re-run des 28,053 questions Supabase (bugs corrigés)

Toutes les questions sont déjà dans Supabase mais les résultats sont tous en erreur `fetch is not defined`. Il faut:
1. Purger les résultats en erreur
2. Re-lancer avec le workflow corrigé
3. batch_size=2 pour éviter les timeouts Code node

### Priorité 3: hotpotqa manquant du benchmark Multi-RAG

hotpotqa (1,000 questions) n'a pas été inclus dans le benchmark multi-RAG graph+quantitative (listé dans ALREADY_DONE car déjà fait en standard).

---

## 5. ANALYSE DU ROUTAGE RAG (1000 questions Graph+Quantitative)

L'analyse de routage montre des problèmes majeurs:

| RAG Type | Correct | Incorrect | Ambiguous |
|----------|---------|-----------|-----------|
| Graph | 21.6% | 5.6% | **72.8%** |
| Quantitative | 75.6% | 0.2% | 24.2% |

**Le routage Graph est très mauvais**: 72.8% des questions graph sont classées "ambiguous" — le routeur ne sait pas les envoyer au bon pipeline.

Par dataset:
- **musique** (graph): seulement 18.5% correctement routé
- **2wikimultihopqa** (graph): 23.7% correct
- **finqa** (quantitative): 83.5% correct
- **tatqa** (quantitative): 66.0% correct
- **convfinqa** (quantitative): 87.0% correct

---

## 6. PROBLÈMES IDENTIFIÉS ET CORRECTIONS NÉCESSAIRES

### 6.1 Bugs corrigés (déjà appliqués)

| # | Bug | Correction |
|---|-----|------------|
| 1 | `fetch()` non disponible dans sandbox n8n | → `this.helpers.httpRequest()` |
| 2 | URLs RAG endpoint incorrects | → Mise à jour des webhooks |
| 3 | Graph/Quant webhooks retournent immédiatement | → `responseMode: responseNode` |
| 4 | Timeout Code node 60s | → batch_size=2 |
| 5 | Format réponse Graph non géré | → Multi-format extraction |
| 6 | Bug JS truthy `[] || fallback` | → Vérification `.length` |

### 6.2 Problèmes RESTANTS à corriger AVANT de lancer les 1000 questions

| # | Problème | Impact | Correction proposée |
|---|----------|--------|---------------------|
| A | **Graph RAG renvoie des community summaries bruts** | Réponses garbage | Revoir l'answer extraction dans le workflow Graph RAG |
| B | **Réponses en français pour questions anglaises** | Mauvais scoring | Ajouter détection de langue dans le prompt |
| C | **Évaluation exact-match cassée** | accuracy toujours 0 | Implémenter F1/EM token-level comparison |
| D | **Routage graph ambiguous à 73%** | Mauvais pipeline choisi | Améliorer le prompt de routage de l'orchestrateur |
| E | **Quantitative RAG vide pour non-financial** | Normal mais confus | Filtrer les questions par type avant envoi |

### 6.3 Plan d'action recommandé

1. **CORRIGER d'abord** les problèmes A et C avant de lancer les questions
2. **Lancer les 1000 questions** spécialisées en lots de 100 avec évaluation intermédiaire
3. **Évaluer qualité** après chaque 100 questions
4. **Si >50% de réponses garbage**: stopper et corriger le workflow
5. **Git push** tous les 1000 questions

---

## 7. STRUCTURE DES FICHIERS CONCERNÉS

```
benchmark-workflows/
├── rag-1000-test-questions.json      # 1000 questions Graph+Quant (4.8MB)
├── benchmark-qa-results-full.json    # 28,053 résultats (tous en erreur)
├── diagnostic-30q-results.json       # 30 résultats diagnostic
├── full-benchmark-multirag-results.json  # 13,648 résultats multi-RAG
├── rag-1000-test-analysis.json       # Analyse routage des 1000 questions
├── test-questions-analysis-report.json   # Rapport d'analyse complet
├── WF-Benchmark-RAG-Tester.json      # Workflow benchmark (corrigé)
├── run-benchmark-tests.py            # Script benchmark complet
├── run-full-benchmark-multirag.py    # Script multi-RAG
├── run-diagnostic-30q.py             # Script diagnostic 30q
└── generate-1000-rag-test-questions.py   # Générateur des 1000 questions
```

---

## 8. RÉSUMÉ EXÉCUTIF

| Métrique | Valeur |
|----------|--------|
| Questions totales disponibles | 29,053 |
| Questions posées au système | ~41,731 (avec doublons multi-RAG) |
| Réponses valides obtenues | ~69-89 (**0.2%**) |
| Questions Graph+Quant spécialisées | 1,000 (JAMAIS POSÉES) |
| Qualité Standard RAG | Fonctionnel mais verbeux |
| Qualité Graph RAG | **CATASTROPHIQUE** — community summaries bruts |
| Qualité Quantitative RAG | OK sur bons datasets, vide sinon |
| Bug principal restant | Graph RAG answer extraction |
| Routage Graph correct | 21.6% seulement |

**Conclusion**: Le système est dans un état où seul le Standard RAG fonctionne de manière acceptable. Le Graph RAG produit des réponses garbage et le Quantitative RAG n'a pas été testé avec les bons datasets. Les 1,000 questions spécialisées n'ont jamais été envoyées. Il faut corriger le Graph RAG answer extraction AVANT de lancer les tests massifs.
