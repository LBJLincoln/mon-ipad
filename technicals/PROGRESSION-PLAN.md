# Plan de Progression — Nomos Expert IA Sectoriel

> Date: 2026-03-10 | Auteur: Claude Code Opus 4.6
> Objectif: Transformer 4 pipelines RAG en experts sectoriels de classe mondiale
> Methode: Progression par etapes mesurables avec gates de validation

---

## DIAGNOSTIC: Pourquoi on est a 26%

L'accuracy Phase 5 (26% sur donnees reelles) vs Phase 3 (87% sur donnees synthetiques)
revele un probleme fondamental: **les pipelines n'ont jamais ete entraines/testes
sur de vraies donnees sectorielles**.

Causes racines identifiees:
1. **Data Gap**: 12.5K vecteurs E5 total vs 250K+ necessaires par secteur
2. **Eval Mismatch**: Questions expertises posees a un index sous-peuple
3. **Pas de progression intermediaire**: Saut de 87% synthetique → 26% reel
4. **Pipelines Graph/Quant non alimentees**: Neo4j + Supabase sous-peuples
5. **Docling deconnecte**: Aucun vrai PDF sectoriel traite

---

## ARCHITECTURE DU PLAN

```
STAGE 0: Foundation     ─── data + baseline
    ↓ Gate: 5/5 smoke test par secteur
STAGE 1: Retrieval      ─── multi-index + reranking
    ↓ Gate: 50% sur 50 questions/secteur
STAGE 2: Enrichment     ─── Graph + entity extraction
    ↓ Gate: 65% Standard + 50% Graph
STAGE 3: Structured     ─── Quant tables + SQL
    ↓ Gate: 75% Standard + 60% Graph + 70% Quant
STAGE 4: Orchestration  ─── routing intelligent
    ↓ Gate: 80% sur toutes les pipelines
STAGE 5: Expert         ─── scoring LLM + adversarial
    ↓ Gate: 90%+ avec evaluation experte multi-criteres
STAGE 6: Production     ─── 24/7 continu + self-healing
    ↓ Gate: 95%+ maintenu sur 7 jours sans regression
```

---

## STAGE 0: FOUNDATION (Sessions S95-S96)

### Objectif
Etablir une base de donnees solide et un smoke test fiable par secteur.

### Actions
| # | Action | Script/Outil | Critere de succes |
|---|--------|-------------|-------------------|
| 0.1 | Verifier contenu E5 par secteur | `ops/rag-proxy.py` | Compter vecteurs: fin>=3K, btp>=2K, jur>=2K, ind>=1K |
| 0.2 | Ingerer les JSONL manquants | `ops/ingest-integrated.py` | Tous 19 fichiers dans E5 |
| 0.3 | Tester Docling sur 3 PDFs reels | HF Space S6 `/convert` | Extraction texte + tableaux OK |
| 0.4 | Creer smoke test 5q/secteur | `eval/quick-test.py --proxy` | Questions basiques, reponses verifiables |
| 0.5 | Valider les 4 pipelines repondent | n8n webhooks + proxy | Pas de 404/503 |

### Gate de sortie
- [x] Standard proxy: 5/5 (PASSE)
- [ ] Graph proxy: 4/5 minimum
- [ ] Quant proxy: 3/5 minimum
- [ ] Orchestrator: repond sans 404
- [ ] Chaque secteur a >= 2K vecteurs E5

### Metriques a tracker
```
smoke_standard: X/5
smoke_graph: X/5
smoke_quant: X/5
smoke_orchestrator: X/5
e5_vectors_per_sector: {finance: N, btp: N, juridique: N, industrie: N}
```

---

## STAGE 1: RETRIEVAL QUALITY (Sessions S97-S98)

### Objectif
Passer de 26% a 50% accuracy en ameliorant la qualite de retrieval.

### Diagnostic technique
Le bottleneck #1 est le **retrieval**: les documents pertinents ne sont pas dans le top-10
des resultats de recherche. Avant d'ameliorer le LLM, il faut que les bons docs arrivent.

### Actions
| # | Action | Impact estime | Effort |
|---|--------|--------------|--------|
| 1.1 | Multi-index RRF (E5 + Jina + BM25) | +15% recall | Moyen — V3.5 deploye |
| 1.2 | Ingerer 50K vecteurs/secteur | +20% coverage | Long — Docling + JSONL |
| 1.3 | Reranking FlashRank sur top-20 → top-5 | +10% precision | Court — deja deploye |
| 1.4 | HyDE (Hypothetical Document Embeddings) | +5% recall | Moyen — a implementer |
| 1.5 | Query expansion sectorielle | +3% recall | Court |

### Evaluation
- **Dataset**: 50 questions/secteur (200 total)
- **Methode**: Mesurer Context Recall (les docs pertinents sont-ils dans le top-10?)
- **Outil**: `eval/expert-eval.py --proxy --sample 50 --measure-retrieval`

### Gate de sortie
- [ ] Context Recall >= 70% (les bons docs sont retrouves)
- [ ] Standard accuracy >= 50% sur 200 questions
- [ ] Latence moyenne < 15s
- [ ] 50K+ vecteurs dans E5

---

## STAGE 2: ENRICHMENT (Sessions S99-S100)

### Objectif
Passer de 50% a 65% en ajoutant les entites Graph et les relations.

### Diagnostic technique
Certaines questions necessitent du **raisonnement multi-hop**: "Quels articles sont
lies a X?" → necessite Graph RAG avec entites et relations dans Neo4j.

### Actions
| # | Action | Impact estime | Effort |
|---|--------|--------------|--------|
| 2.1 | Extraire entites depuis 50K docs → Neo4j | +10% multi-hop | Long |
| 2.2 | Enrichment V4.0 pipeline continue | auto-extraction | Moyen |
| 2.3 | Graph RAG: entity → relations → summary | +5% complex queries | Moyen |
| 2.4 | CRAG grading (filter irrelevant chunks) | +3% precision | Court |

### Evaluation
- **Dataset**: 150 questions (50 standard + 50 graph + 50 mixte)
- **Methode**: Mesurer accuracy Standard + Graph separement
- **Outil**: `eval/expert-eval.py --proxy --pipelines standard,graph`

### Gate de sortie
- [ ] Standard accuracy >= 65% sur 150 questions
- [ ] Graph accuracy >= 50% sur 50 questions graph-specifiques
- [ ] Neo4j >= 50K entities avec relations
- [ ] Faithfulness >= 85% (pas d'hallucinations)

---

## STAGE 3: STRUCTURED DATA (Sessions S101-S102)

### Objectif
Passer de 65% a 75% en ajoutant les donnees structurees (tableaux, SQL).

### Diagnostic technique
Les questions financieres/quantitatives (CAPEX, ratios, marges) necessitent
des **tableaux structures** queryables en SQL, pas du texte vectoriel.

### Actions
| # | Action | Impact estime | Effort |
|---|--------|--------------|--------|
| 3.1 | Populer Supabase tables par secteur | +15% finance | Moyen |
| 3.2 | SQL generation fiable (Quant pipeline) | +10% numerical | Moyen |
| 3.3 | CompactRAG: pre-generer QA pairs pour formules | +5% complex calc | Long |
| 3.4 | Table extraction Docling → schema SQL auto | +5% new tables | Long |

### Evaluation
- **Dataset**: 220 questions full dataset
- **Methode**: Accuracy par pipeline ET par secteur
- **Outil**: `eval/expert-eval.py --proxy --full`

### Gate de sortie
- [ ] Standard >= 75%
- [ ] Graph >= 60%
- [ ] Quant >= 70% (finance specifiquement)
- [ ] Orchestrator >= 65% (routing correct)

---

## STAGE 4: ORCHESTRATION (Sessions S103-S104)

### Objectif
Passer de 75% a 85% avec un routage intelligent et des fallbacks.

### Diagnostic technique
L'orchestrateur doit **router chaque question** vers la meilleure pipeline
(Standard vs Graph vs Quant) en fonction du type de question.

### Actions
| # | Action | Impact estime | Effort |
|---|--------|--------------|--------|
| 4.1 | Intent classifier: type question → pipeline | +10% routing | Moyen |
| 4.2 | Fallback chain: si pipeline 1 fail → pipeline 2 | +5% robustesse | Court |
| 4.3 | A-RAG (Adaptive RAG): selection dynamique | +3% complex | Long |
| 4.4 | Confidence scoring: si confiance < 0.5 → try another | +2% | Moyen |

### Evaluation
- **Dataset**: 500+ questions (220 standard + 280 nouvelles adversariales)
- **Methode**: Accuracy globale + scoring multi-criteres LLM
- **Outil**: `eval/expert-eval.py --proxy --full --adversarial`

### Gate de sortie
- [ ] Standard >= 85%
- [ ] Graph >= 70%
- [ ] Quant >= 80%
- [ ] Orchestrator >= 80%
- [ ] Latence p95 < 30s

---

## STAGE 5: EXPERT QUALITY (Sessions S105-S108)

### Objectif
Passer de 85% a 90%+ avec evaluation experte multi-criteres.

### Diagnostic technique
A ce stade, l'accuracy brute ne suffit plus. Il faut mesurer la **qualite experte**:
terminologie, citations, completude, langue.

### Actions
| # | Action | Impact estime | Effort |
|---|--------|--------------|--------|
| 5.1 | LLM-as-Judge (GPT-5.4): scoring 5 criteres | Mesure qualite | Moyen |
| 5.2 | Tests adversariaux: questions pieges, ambigues | +3% robustesse | Court |
| 5.3 | Prompt engineering sectoriel | +5% terminologie | Court |
| 5.4 | Few-shot examples par secteur | +3% format | Court |
| 5.5 | Validation par expert humain (echantillon) | Ground truth | Long |

### Criteres de scoring (LLM-as-Judge)
| Critere | Poids | Description |
|---------|-------|-------------|
| Precision factuelle | 30% | Info correcte basee sur les sources |
| Citation des sources | 20% | Cite des documents/articles specifiques |
| Terminologie experte | 20% | Utilise les bons termes professionnels |
| Completude | 15% | Reponse suffisamment detaillee |
| Langue correcte | 15% | Repond dans la langue de la question |

### Gate de sortie
- [ ] Score expert moyen >= 4.0/5.0
- [ ] Precision factuelle >= 90%
- [ ] Citations sources >= 80%
- [ ] Terminologie experte >= 80%
- [ ] Zero hallucination sur echantillon de 50 questions

---

## STAGE 6: PRODUCTION (Sessions S109+)

### Objectif
Maintenir 90%+ accuracy en continu avec self-healing.

### Actions
| # | Action | Critere |
|---|--------|---------|
| 6.1 | Eval continue 24/7 (cron 30min) | Alertes si drop > 5% |
| 6.2 | Self-healing auto (metrics → analyze → fix → test) | MTTR < 1h |
| 6.3 | Ingestion continue (nouveaux docs chaque semaine) | +1K vecteurs/semaine |
| 6.4 | A/B testing shadow (nouveau prompt vs ancien) | Pas de regression |
| 6.5 | Dashboard metriques temps reel | Google Sheets + Drive |

### Gate de sortie
- [ ] 95%+ accuracy maintenue sur 7 jours consecutifs
- [ ] Zero downtime non-detecte
- [ ] Temps de recuperation < 1h apres incident
- [ ] Expert humain valide un echantillon mensuel

---

## DOCLING: PLAN PROGRESSIF DEDIE

### Etape D0: Validation (S95)
- [ ] Tester HF Space S6 sur 3 PDFs reels (1 finance, 1 BTP, 1 juridique)
- [ ] Mesurer: temps extraction, completude texte, fidelite tableaux
- [ ] Baseline fidelity score >= 80%

### Etape D1: Integration E5 (S96)
- [ ] Connecter Docling → Pinecone E5 integrated embedding
- [ ] Ingerer 20 PDFs sectoriels via Docling
- [ ] Mesurer impact sur accuracy (avant/apres)

### Etape D2: Pipeline continue (S97-S98)
- [ ] Workflow n8n: check nouveaux PDFs → Docling → embed → upsert
- [ ] Cron quotidien a 2h UTC
- [ ] Monitoring: docs traites/jour, echecs, fidelite

### Etape D3: Scale (S99+)
- [ ] 100+ types de documents par secteur
- [ ] Chunking sectoriel intelligent (tables finance, articles juridiques, normes BTP)
- [ ] Fidelite >= 95% sur documents complexes
- [ ] Target: 1M documents traites

---

## METRIQUES DE SUIVI

### Tableau de bord (mis a jour a chaque session)

| Metrique | Stage 0 | Stage 1 | Stage 2 | Stage 3 | Stage 4 | Stage 5 | Stage 6 |
|----------|---------|---------|---------|---------|---------|---------|---------|
| Standard Accuracy | 26% | →50% | →65% | →75% | →85% | →90% | →95% |
| Graph Accuracy | 0% | →20% | →50% | →60% | →70% | →80% | →90% |
| Quant Accuracy | 0% | →10% | →30% | →70% | →80% | →85% | →90% |
| Orchestrator | 0% | →20% | →40% | →65% | →80% | →85% | →90% |
| E5 Vectors | 12.5K | →50K | →100K | →200K | →500K | →750K | →1M |
| Neo4j Entities | 1.3K | →10K | →50K | →100K | →150K | →200K | →200K |
| Supabase Tables | 3.8K | →5K | →10K | →20K | →50K | →100K | →200K |
| Context Recall | ? | →70% | →80% | →85% | →90% | →95% | →95% |
| Faithfulness | ? | →70% | →85% | →90% | →95% | →98% | →99% |
| Latence p95 | ~47s | →30s | →20s | →15s | →10s | →8s | →5s |
| Expert Score | ? | ? | ? | 3.0/5 | 3.5/5 | 4.0/5 | 4.5/5 |

### Etat actuel (S95 debut)

| Metrique | Valeur | Stage |
|----------|--------|-------|
| Standard (proxy) | 5/5 smoke = 100% | Stage 0 ✓ (smoke) |
| Graph (proxy) | 4/5 smoke = 80% | Stage 0 ✓ (smoke) |
| Standard (220q) | ~26% | Stage 0 (baseline) |
| E5 Vectors | 12,502 | Stage 0 |
| Neo4j Entities | 41,747 | Stage 1-2 (avance) |
| Supabase Tables | 212 rows (3 tables) | Stage 0 |
| LLM Providers | 4 actifs (Groq, OpenAI, Gemini, OpenRouter) | Stage 0+ |

---

## PRINCIPES D'EXECUTION

1. **Un stage a la fois** — ne pas sauter d'etape
2. **Gate obligatoire** — ne pas passer au stage suivant sans valider la gate
3. **Mesurer avant/apres** — chaque changement doit etre mesure
4. **1 fix par iteration** — jamais 2 changements simultanes
5. **Revert si regression** — drop > 5% = revert immediat
6. **10% improvement minimum par session** — sur le secteur le plus faible
7. **Commit regulier** — toutes les 15-20 minutes
8. **Documentation** — MAJ ce fichier apres chaque gate passee
