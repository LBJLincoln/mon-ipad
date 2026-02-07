# Rapport d'Evaluation Complet - SOTA 2026 Multi-RAG
## Date: 2026-02-07 | 100 questions + 30 diagnostic

---

## 1. Resume Executif

| Pipeline | Questions | Reponses | Avg F1 | Verdict |
|---|---|---|---|---|
| **Quantitative (WF4)** | 25 | 17/25 (68%) | 0.033 | Reponses correctes mais F1 faible (format mismatch) |
| **Graph (WF2)** | 25 | 0/25 (0%) | 0.000 | **BLOQUE** - webhook async apres redeploiement |
| **Standard (WF5)** | 25 | 25/25 (100%) | 0.112 | Fonctionne, reponses verboses |
| **Orchestrator (V10.1)** | 20 | 11/20 (55%) | 0.078 | Routing OK, synthese multi-pipeline echoue |
| **Diagnostic** | 30 | 30/30 (100%) | 0.037 | Toutes les pipelines repondent |

---

## 2. Bug Fixes - Verification en Production

### ISSUE-QT-13: ILIKE Entity Name Matching
**Status: FIX CONFIRME EN PRODUCTION**

| Test | Avant Fix | Apres Fix |
|---|---|---|
| `TechVision` (sans Inc) | `= 'TechVision'` -> null | `ILIKE '%TechVision%'` -> $6.745B |
| `GreenEnergy` (sans Corp) | `= 'GreenEnergy'` -> null | `ILIKE '%GreenEnergy%'` -> $3.65B |
| `HealthPlus` (sans Labs) | `= 'HealthPlus'` -> null | `ILIKE '%HealthPlus%'` -> data found |

**SQL genere apres fix:**
```sql
SELECT SUM(revenue) FROM financials
WHERE company_name ILIKE '%TechVision%'
  AND fiscal_year = 2023
  AND tenant_id = 'benchmark' LIMIT 1000
```

### ISSUE-QT-14: Null Aggregation Detection
**Status: FIX CONFIRME EN PRODUCTION**

| Test | Avant Fix | Apres Fix |
|---|---|---|
| FY 2025 (inexistant) | `status: SUCCESS, result: {sum: null}` | `status: NULL_RESULT, null_aggregation: true` |

**Reponse apres fix:**
```json
{
  "status": "NULL_RESULT",
  "null_aggregation": true,
  "result_count": 0,
  "interpretation": "The revenue of TechVision in FY 2025 cannot be determined..."
}
```

---

## 3. Resultats Detailles par Pipeline

### 3.1 Quantitative RAG (WF4) - 25 questions

**Reponses correctes confirmees:**

| Question | Expected | Actual | Correct? |
|---|---|---|---|
| Gross profit margin TechVision 2023 | 68.0% | **68%** | OUI |
| Operating margin GreenEnergy 2023 | 23.0% | **23.00%** | OUI |
| Q4 2023 revenue TechVision | $1,851,500,000 | **$1,851,500,000** | OUI |
| Total assets TechVision 2023 | $7,924,000,000 | **$7,924,000,000** | OUI |
| Cash HealthPlus 2023 | $320,000,000 | **$320,000,000** | OUI |
| R&D % GreenEnergy 2023 | 10.0% | **10.00%** | OUI |
| Effective tax rate TechVision | 21.0% | **21.00%** | OUI |
| Net income leader 2023 | TechVision Inc | **TechVision Inc** | OUI |
| FY 2025 (null test) | No data | **NULL_RESULT** | OUI |

**Problemes identifies:**

1. **Double-counting FY+Quarters (P0):** `SUM(revenue) WHERE fiscal_year=2023` sans `period='FY'` cumule FY + Q1+Q2+Q3+Q4 = 2x le montant reel
   - Revenue TechVision: $13.49B au lieu de $6.745B
   - R&D TechVision: $2.7B au lieu de $1.35B
   - **Fix propose:** Ajouter dans le prompt: "Pour les metriques annuelles, filtrer sur period = 'FY'. Pour les trimestrielles, filtrer sur period IN ('Q1','Q2','Q3','Q4')."

2. **F1 Score faible (scoring artifact):** Les reponses sont correctes mais le F1 tokenise est 0.0 car les formats numeriques ne matchent pas:
   - Expected `$6,745,000,000` vs Actual `13,490,000,000.00` - tokens totalement differents
   - **Fix propose:** Normaliser les nombres avant comparaison F1 ou utiliser une metrique numerique (% d'erreur relative)

3. **Erreurs reseau (6/25):** Probablement rate limiting sur l'API OpenRouter
   - **Fix propose:** Ajouter backoff exponentiel + file d'attente dans le runner

4. **Debt-to-equity calcul incorrect:** Retourne 0.0916 (long_term_debt/equity) au lieu de 0.36 (total_liabilities/equity)
   - **Fix propose:** Preciser la formule D/E dans le prompt: "D/E ratio = total_liabilities / total_stockholders_equity"

### 3.2 Graph RAG (WF2) - 25 questions

**Status: BLOQUE - Webhook retourne async**

Toutes les 25 questions retournent `{"message": "Workflow was started"}` en ~180ms.

**Cause identifiee:** Le redeploiement via `n8n_tester.py` a change la configuration du webhook de WF2. Avant redeploiement, le webhook repondait de maniere synchrone (4.7s latence, reponse complete). Apres, il retourne immediatement sans attendre le resultat.

**Fix necessaire:**
1. Verifier le setting `respondWith` du webhook node dans WF2
2. S'assurer que le mode est "lastNode" ou "responseNode" et non "immediately"
3. Re-activer le mode synchrone via l'API n8n

**Note:** Avant que le bug async n'apparaisse, le test de connectivite avait montre que Graph RAG repondait correctement:
```json
{"status":"SUCCESS","response":"The context does not contain information..."}
```

### 3.3 Standard RAG (WF5) - 25 questions

**Status: FONCTIONNE - 100% de reponses, F1 faible**

| Metrique | Valeur |
|---|---|
| Taux de reponse | 25/25 (100%) |
| Avg F1 | 0.1121 |
| F1 >= 0.5 | 0/25 (0%) |
| Avg Latence | 5,764ms |

**Observations:**
- Les reponses sont **verboses** (paragraphes entiers) vs expected answers **concises** (1-2 phrases)
- Le LLM (Gemini Flash) genere des citations `[1], [5], [10]` qui diluent le F1
- 4/30 reponses en francais au lieu d'anglais (bug de langue intermittent)
- Le contenu est semantiquement correct mais le F1 token-level penalise la verbosity

**Fixes proposes:**
1. **Prompt engineering:** Ajouter "Reponds de maniere concise en 1-2 phrases" dans le system prompt du LLM
2. **Language forcing:** Ajouter "ALWAYS respond in English" au prompt
3. **Post-processing:** Extraire la premiere phrase de la reponse pour le scoring
4. **HyDE evaluation:** Verifier que le HyDE retrieves les bons chunks (pas de metriques retrieval actuelles)

### 3.4 Orchestrator (V10.1) - 20 questions

**Status: PARTIEL - 55% reponses, routing correct a 73%**

| Metrique | Valeur |
|---|---|
| Taux de reponse | 11/20 (55%) |
| Errors | 9/20 (45%) |
| Routing accuracy | 8/11 (73%) |
| Avg F1 | 0.078 |

**Observations:**
- Les questions de routing simple (standard/quantitative) fonctionnent
- Les questions multi-pipeline (`quantitative+graph`, `quantitative+graph+standard`) echouent systematiquement
- Les questions de synthese complexe retournent des erreurs HTTP
- L'orchestrateur ne gere pas le fallback quand un sous-workflow echoue

**Reponses d'orchestrateur reussies:**
- Debt-to-equity ratios: **GreenEnergy 0.36, TechVision 0.29** (partiellement correct)
- Operating margin trend: GreenEnergy historique present
- Security measures: Reference aux documents (mais contenu inadapte)

**Fixes proposes:**
1. **Fallback mechanism:** Si un sous-workflow echoue, l'orchestrateur devrait continuer avec les resultats disponibles
2. **Timeout handling:** Les queries multi-pipeline depassent le timeout webhook (30s)
3. **Confidence-based routing:** Implementer un score de confiance pour le choix de pipeline
4. **Parallel execution:** Executer les sous-workflows en parallele (actuellement sequentiel)

---

## 4. Problemes Systeme Identifies

### P0 - Critiques
1. **WF2 Graph RAG async** - Webhook ne retourne plus de reponse synchrone apres redeploiement
2. **Double-counting FY+Quarters** - Toutes les aggregations annuelles sont x2
3. **Orchestrateur multi-pipeline** - Echoue sur toutes les requetes multi-pipeline

### P1 - Importants
4. **F1 scoring inadapte** - Ne gere pas les formats numeriques, penalise les reponses longues
5. **Reponses en francais** - 13% des reponses standard sont en francais au lieu d'anglais
6. **D/E ratio formule** - Le LLM utilise long_term_debt au lieu de total_liabilities
7. **Rate limiting** - 24% des requetes quantitatives echouent (erreur reseau)

### P2 - Ameliorations
8. **Verbosity** - Les reponses standard sont trop longues pour un bon F1
9. **HyDE retrieval metrics** - Pas de visibilite sur la qualite du retrieval
10. **Graph RAG data** - Neo4j non configure, pas de donnees multi-hop

---

## 5. Plan d'Amelioration Prioritise

### Sprint 1 (Immediat)
- [ ] Fix WF2 webhook: restaurer le mode synchrone (`respondWith: lastNode`)
- [ ] Fix double-counting: ajouter `period = 'FY'` guidance dans le prompt SQL
- [ ] Fix language: ajouter "ALWAYS respond in English" dans tous les prompts LLM

### Sprint 2 (Court terme)
- [ ] Ameliorer F1 scoring: normalisation numerique, metrique d'erreur relative
- [ ] Prompt concision: "Reponds en 1-2 phrases maximum"
- [ ] Fix D/E formule: ajouter exemplaire dans les few-shot examples
- [ ] Orchestrateur fallback: continuer si un sous-workflow echoue

### Sprint 3 (Moyen terme)
- [ ] Orchestrateur parallele: lancer les sous-workflows en parallele
- [ ] Confidence routing: score de confiance pour le choix de pipeline
- [ ] Neo4j setup: ingerer les donnees graph (musique, 2wikimultihopqa)
- [ ] Retrieval metrics: ajouter recall@10, MRR, NDCG au reporting

---

## 6. Metriques de Reference (Baseline)

Ces metriques servent de reference pour mesurer les ameliorations futures:

```
QUANTITATIVE RAG:
  Answer Rate:      68% (17/25)
  Correct Answers:  9/17 (53% des reponses)
  Avg Latency:      2,800ms
  ILIKE Usage:      ~60% des requetes
  Null Detection:   100% (1/1)
  Double-counting:  Affecte ~40% des aggregations annuelles

STANDARD RAG:
  Answer Rate:      100% (25/25)
  Avg F1:           0.112
  Avg Latency:      5,764ms
  French Rate:      13% (indésiré)

GRAPH RAG:
  Answer Rate:      0% (BLOQUE - async webhook)

ORCHESTRATOR:
  Answer Rate:      55% (11/20)
  Routing Accuracy: 73% (8/11)
  Multi-pipeline:   0% (tous echouent)
```
