# rag-website — CLAUDE.md

> Last updated: 2026-02-25T11:30:00+00:00
> **Ce repo s'exécute dans un Codespace GitHub éphémère (dev) + Vercel (prod).**
> Tu es un agent Claude Code specialise dans le SITE BUSINESS multi-secteurs.
> **MODELE PRINCIPAL : `claude-opus-4-6`** — Architecture, decisions, evaluation qualite.
> **DELEGATION** : Sonnet 4.5 pour generation composants repetitifs via `Task(model: "sonnet")`.
> **DELEGATION** : Haiku 4.5 pour exploration codebase via `Task(model: "haiku", subagent_type: "Explore")`.
> Tu suis le même workflow-process que mon-ipad, adapté à ton objectif secteur.
> Processus team-agentic multi-model : voir `technicals/project/team-agentic-process.md` (dans mon-ipad).
> **Bottleneck-first** : Builds/tests fonctionnels en background. Se concentrer sur les problèmes et blocages.
> **Push régulier** : Commit + push toutes les 15-20 min. Ne jamais perdre de travail.

---

## ÉTAT ACTUEL — 25 fév 2026

| | |
|-|-|
| **Status** | Live sur Vercel : https://nomos-ai-pied.vercel.app |
| **GitHub Action** | Has a known failure that needs fixing (deployment still works) |
| **Dashboard SSE** | /dashboard route active with real-time updates |
| **Codespace** | Can be created on-demand for development |
| **Prochain objectif immédiat** | Fix GitHub Action workflow + Intégrer vrais docs sectoriels dans démos chatbot |

### Commandes clés pour cette session
```bash
# Redémarrer le Codespace si nécessaire
gh codespace start --codespace nomos-rag-website-jr7q9gr69qqfqp6r

# Dans le Codespace — dev local
npm install
npm run dev  # port 3000

# Déployer en prod
git push origin main  # → Vercel auto-deploy

# Vérifier le build
npm run build
```

### Livrables déjà en prod (session 13 — 17 fév 2026)
- Hero : problem-first, pain points cycliques, dual CTA + lien dashboard
- SectorCard : Apple-style, pain point en grand, ROI chips, bouton vidéo
- VideoModal : storyboard cinématique scripts Kimi (4 secteurs)
- HowItWorks : "Sous le capot", pipelines en sous-section
- DashboardCTA : section transparence avec métriques live
- evalStore.ts : Zustand SSE store (XP levels, streaming, pipeline stats)
- useEvalStream.ts : SSE hook avec reconnect exponentiel
- dashboard/live/ : QuestionRow, VirtualizedFeedList, FeedStatusBar, MilestoneNotification
- XPProgressionBar : 7 niveaux gamifiés (1q → 1000q)

---

## POSITION DANS LE PLAN GLOBAL (phases A→D)

```
PHASE A — RAG Pipeline Iteration  ← RAG-TESTS + MON-IPAD
  Phase 1 (200q)  BLOQUÉE — ne concerne pas directement ce repo

PHASE B — Analyse SOTA 2026  ← MON-IPAD (résultats dans technicals/)
  → Ce repo CONSOMME les résultats SOTA pour ses démos

PHASE C — Ingestion & Enrichment  ← RAG-DATA-INGESTION
  → Ce repo CONSOMME les datasets sectoriels ingérés (Pinecone website-sectors-*)

PHASE D — Production & Déploiement  ← CE REPO EST ICI ✅
  Statut actuel : MVP en prod (nomos-ai-pied.vercel.app)
  Manquant : vraies données sectorielles dans les démos chatbot
```

### Ce que ce repo attend des autres repos

| Dépendance | Depuis | Condition |
|------------|--------|-----------|
| Architectures pipelines validées | mon-ipad Phase 1 | Copier quand Phase 1 passée |
| Données Finance dans Supabase | rag-data-ingestion | FinQA + TatQA ingérés |
| Données Juridique dans Neo4j | rag-data-ingestion | French Case Law ingéré |
| Données BTP/Industrie dans Pinecone | rag-data-ingestion | Datasets sectoriels BTP/Industrie |

### Ce que ce repo produit pour le projet
- Site vitrine déployé (preuve de concept pour clients)
- Dashboard live `/dashboard` avec SSE feed (932q actuellement)
- Scripts Kimi → vidéos marketing 4 secteurs

---

## OBJECTIF DE CE REPO

Construire un **Multi-RAG Orchestrator sectoriel** capable de répondre aux questions
métier des ETI et Grands Groupes français dans 4 secteurs :
- **BTP/Construction** — normes, marchés, CCTP, RE2020
- **Industrie** — maintenance, ICPE, qualité ISO, AMDEC
- **Finance** — états financiers, IFRS, prudentiel, KYC
- **Juridique** — jurisprudence, codes, contrats, compliance

**Cible finale** : performance SOTA sur les 20 datasets sectoriels désignés,
avec des bases de données **SÉPARÉES** de mon-ipad.

---

## POINT DE DÉPART : VERSION RÉUSSIE DE MON-IPAD PHASE 2

**Tu pars de la dernière version validée de mon-ipad** (4 pipelines RAG Phase 2).
- Copier l'architecture des 4 pipelines (Standard, Graph, Quantitative, Orchestrator)
- Adapter les workflows n8n pour les documents sectoriels (pas les benchmarks académiques)
- Créer des **bases de données séparées** avec les datasets sectoriels

### Bases de données SÉPARÉES (ne pas utiliser celles de mon-ipad)
| BDD | Index/Schema mon-ipad | Index/Schema rag-website |
|-----|----------------------|--------------------------|
| Pinecone | `sota-rag-jina-1024` | `website-sectors-jina-1024` |
| Neo4j | graph mon-ipad | labels préfixés `WEB_` |
| Supabase | schéma `public` | schéma `website_` |

---

## RECHERCHE ACADÉMIQUE PRÉLIMINAIRE (PHASE 0 — OBLIGATOIRE)

**Avant de commencer le développement**, effectuer une revue des papiers 2026 :

### Sources prioritaires
- **ArXiv** (cs.IR, cs.CL) : papiers RAG SOTA 2025-2026
- **Anthropic Research** : techniques de retrieval, contextual RAG
- **OpenAI Research** : file search improvements, embedding models
- **ECIR 2026, ACL 2026, EMNLP 2025** : papers acceptés sur RAG sectoriel

### Topics à rechercher
```
1. "Sector-specific RAG" OR "domain RAG 2026"
2. "Contextual retrieval" OR "late chunking" (Jina)
3. "Graph RAG" domain adaptation 2026
4. "Quantitative RAG" financial documents
5. "Document-level embeddings" multilingue FR/EN
6. "Hybrid retrieval" dense + sparse sectoriel
```

### Intégration des découvertes
- Documenter les techniques dans `research/papers-2026.md`
- Appliquer les meilleures techniques aux workflows n8n sectoriels
- Comparer avant/après avec la double analyse (node-analyzer + analyze_n8n_executions)

---

## LES 20 DATASETS SECTORIELS (source : mon-ipad/technicals/data/sector-datasets.md)

5 datasets prioritaires par secteur = 20 datasets totaux.
Voir la liste complète dans `technicals/data/sector-datasets.md` (sections 3.1 à 3.4).

### BTP/Construction (5 datasets prioritaires)
| # | Dataset | Source HF | Utilité |
|---|---------|-----------|---------|
| 1 | **CODE-ACCORD** | `GT4SD/code-accord` | NER réglementations bâtiment FR (DTU, Eurocodes) |
| 2 | **ConstructionSite VQA** | `joyjeni/ConstructionSite-VQA-GPT4` | QA chantiers (sécurité, équipements) |
| 3 | **Engineering Drawings AS1100** | `cclabsai/engineering-drawing-qa-as1100` | QA dessins techniques / plans |
| 4 | **DesignQA** | `filipeabperes/DesignQA` | QA conformité normes ingénierie |
| 5 | **SQuAD Construction subset** | `rajpurkar/squad_v2` (filtré bâtiment) | QA extractif documents construction |

### Industrie/Manufacturing (5 datasets prioritaires)
| # | Dataset | Source HF | Utilité |
|---|---------|-----------|---------|
| 1 | **Manufacturing QA** | `thesven/manufacturing-qa-gpt4o` | 5 000 QA process fab, qualité, lean |
| 2 | **TAT-QA** | `nextplusplus/TAT-QA` | QA hybride tableaux + texte (rapports qualité) |
| 3 | **QuALITY** | `nyu-mll/quality` | QA documents longs (manuels, procédures 5000+ tokens) |
| 4 | **RAGBench** | `rungalileo/ragbench` | 100K exemples RAG multi-domaine industrie |
| 5 | **CRAG** | `facebook/crag` | Benchmark RAG NeurIPS 2024 (multi-hop, dynamique) |

### Finance (5 datasets prioritaires)
| # | Dataset | Source HF | Utilité |
|---|---------|-----------|---------|
| 1 | FinanceBench | `PatronusAI/financebench` | QA états financiers |
| 2 | ConvFinQA | `TheFinAI/convfinqa` | Raisonnement financier |
| 3 | FinQA | Standard (déjà dans mon-ipad) | Calculs financiers |
| 4 | TAT-QA | Standard (déjà dans mon-ipad) | Tableaux financiers |
| 5 | Finance-Instruct | `sujet-ai/Sujet-Finance-Instruct-500k` | Instructions métier |

### Juridique (5 datasets prioritaires)
| # | Dataset | Source HF | Utilité |
|---|---------|-----------|---------|
| 1 | French Case Law | `rcds/french_case_law` | Jurisprudence FR |
| 2 | COLD French Law | `rcds/cold-french-law` | Code civil, pénal |
| 3 | MultiEURLEX | `joelito/multi_eurlex` | Droit européen |
| 4 | LegalBench | Identifier depuis sector-datasets.md | Raisonnement juridique |
| 5 | Contrats commerciaux | Identifier depuis sector-datasets.md | Clauses contractuelles |

### Procédure de téléchargement
```bash
source .env.local
# Les scripts de téléchargement sont dans scripts/download-sector-datasets.py
python3 scripts/download-sector-datasets.py --sector btp --max-questions 10000
python3 scripts/download-sector-datasets.py --sector finance --max-questions 10000
# etc.
```

---

## INFRASTRUCTURE DE CE CODESPACE

```
Type        : GitHub Codespace (éphémère)
CPU         : 2 cores | RAM : 8 GB | Disque : 32 GB
n8n local   : OUI — docker-compose standalone
              (n8n + postgres, démarré par setup.sh)
Déploiement : Vercel (auto sur push main)
```

### Containers Docker locaux
```
rag-website-n8n-1       n8nio/n8n:latest   Port 5678
rag-website-postgres-1  postgres:15         Port 5432 (interne)
```

---

## ETAPE 0 — Consulter la Bibliotheque de Fixes (OBLIGATOIRE)

**AVANT tout debug, TOUJOURS consulter `technicals/debug/fixes-library.md` en premier.**

```bash
cat technicals/debug/fixes-library.md
```

35 bugs documentes ont deja ete resolus (sessions 7–27). Chercher le symptome dans le tableau PIEGES RECURRENTS avant toute analyse. **Si symptome connu → appliquer directement SANS re-analyser.** Particulierement pertinent : FIX-04 (Jina JSON), FIX-07 (Neo4j URL), FIX-09 (PUT 400), FIX-12 (Pinecone dim). Si le symptome est nouveau → debugger, puis signaler a mon-ipad.

### Protocole Auto-Stop
3 echecs consecutifs sur le meme type d'erreur → STOP, documenter dans `logs/diagnostics/`, signaler a mon-ipad.

### Fixes Library Partagee
La bibliotheque de fixes master est dans `mon-ipad/technicals/debug/fixes-library.md`. Ce repo recoit une copie via `push-directives.sh`. Si tu decouvres un nouveau bug, documente-le dans `logs/diagnostics/` + commit + push.

---

## BOUCLE D'ITÉRATION (même que workflow-process.md — adapté secteurs)

### Étape 1 : Test 1/1 (par secteur)
```bash
source .env.local
python3 eval/quick-test.py --questions 1 --pipeline standard --sector btp
python3 eval/quick-test.py --questions 1 --pipeline quantitative --sector finance
```
- Si erreur → double analyse AVANT tout fix
- Si succès → passer à 5/5

### Étape 2 : Test 5/5 (double analyse OBLIGATOIRE)
```bash
python3 eval/quick-test.py --questions 5 --pipeline <pipeline> --sector <secteur>
# Pour chaque execution-id :
python3 eval/node-analyzer.py --execution-id <ID>
python3 scripts/analyze_n8n_executions.py --execution-id <ID>
```

### Étape 3 : Test 10/10
```bash
python3 eval/run-eval-parallel.py --max 10 --sector <secteur> --label "sector-fix"
```

### Étape 4 : Tests 200q → 1000q par secteur
```bash
python3 eval/run-eval-parallel.py --sector btp --label "btp-baseline"
python3 eval/run-eval-parallel.py --sector finance --questions 1000 --label "finance-phase2"
```

### Cibles par secteur
| Secteur | Pipeline principal | Cible |
|---------|-------------------|-------|
| BTP | Standard + Graph | >= 75% |
| Industrie | Standard + Quantitative | >= 75% |
| Finance | Quantitative | >= 80% |
| Juridique | Graph + Orchestrator | >= 70% |

---

## STACK TECHNIQUE

```
Frontend    : Next.js 14 (App Router) + Tailwind + shadcn/ui
Backend     : n8n local Codespace (workflows sectoriels)
LLM         : OpenRouter (Llama 70B, Gemma 27B) — même que mon-ipad
Embeddings  : Jina embeddings-v3 1024-dim (PRIMARY)
Vector DB   : Pinecone `website-sectors-jina-1024` (SÉPARÉE)
Graph DB    : Neo4j Aura Free — labels `WEB_*` (SÉPARÉE)
SQL DB      : Supabase schéma `website_*` (SÉPARÉE)
Deploy      : Vercel (auto push main)
```

---

## RÈGLES D'OR

1. **Consulter fixes-library.md EN PREMIER** — avant tout debug (`technicals/debug/fixes-library.md`)
2. **source .env.local** avant tout script Python
3. **Bases de données SÉPARÉES** — ne jamais écrire dans les indexes de mon-ipad
4. **Recherche papiers 2026 OBLIGATOIRE** avant développement
5. **UN fix par itération** — même règle que mon-ipad
6. **Double analyse** (node-analyzer + analyze_n8n_executions) pour chaque exécution
7. **Tests séquentiels** — jamais parallèles (503)
8. **5/5 minimum** avant sync/commit
9. **Push avant arrêt Codespace** — éphémère !
10. **Résultats vers GitHub** — mon-ipad lit depuis rag-website/main
11. **Delegation multi-model** — Opus decide, Sonnet genere les composants repetitifs, Haiku explore

### Strategie Multi-Model (Session 26)
- **Opus 4.6** : Decisions architecturales, evaluation UX, review code, communication
- **Sonnet 4.5** : Generation de composants repetitifs, batch operations, recherches web (`Task(model: "sonnet")`)
- **Haiku 4.5** : Exploration rapide du codebase Next.js (`Task(model: "haiku", subagent_type: "Explore")`)
- **Regle** : Opus DECIDE quand deleguer. Jamais deleguer l'architecture ou l'evaluation qualite.

---

## FIN DE SESSION

```bash
# Build Next.js
npm run build

# Génération status sectoriel
python3 eval/generate_status.py --mode sectors

# Commit
git add .
git commit -m "feat(sectors): BTP X% Finance X% — [description fix]"
git push origin main  # → déclenche Vercel auto-deploy
```

---

---

## REDESIGN DEMANDE (Session 18 — 18 fev 2026)

### Changements requis

1. **Retirer** la promesse "reponse en 3 secondes" → remplacer par **"IA experte sectorielle connectee a VOS donnees"**

2. **CTA principal** : "TESTEZ DIRECTEMENT PAR VOUS-MEME" — place avant la section chatbot, bien visible

3. **Pipeline en 3 etapes Apple-style** :
   - Etape 1 : **Connexion donnees** (1M+ documents indexes)
   - Etape 2 : **Chatbot IA** (question en langage naturel)
   - Etape 3 : **Reponses detaillees avec sources** (citations, confiance, traces)

4. **Ordre des secteurs** (modifie) :
   1. Industrie (maintenance, ICPE, qualite ISO, AMDEC)
   2. BTP Construction (normes, marches, CCTP, RE2020)
   3. Finance (etats financiers, IFRS, prudentiel, KYC)
   4. Juridique (jurisprudence, codes, contrats, compliance)

5. **Chatbot cards** : mosaique 4-apps iPad style, clairement cliquables, avec icon + titre secteur + preview question exemple

6. **Execution** : dans Codespace rag-website, PAS sur la VM

### Elements a conserver
- Hero problem-first (pain points cycliques)
- SectorCards Apple-style (pain point BIG + ROI chips)
- VideoModal storyboard cinematique
- HowItWorks "Sous le capot"
- DashboardCTA section transparence
- Dashboard SSE live (/dashboard)

---

## DATASETS & QUESTIONS — VUE SECTORIELLE

### Inventaire des datasets sectoriels (pour les demos chatbot)
| Secteur | Datasets | Questions/items | Taille | Status ingestion |
|---------|----------|----------------|--------|-----------------|
| **BTP** | CODE-ACCORD, ConstructionSite VQA, Engineering Drawings, DesignQA, SQuAD filtered | 1,844 items telecharges | 5.7 MB | NON INGERE |
| **Industrie** | Manufacturing QA, TAT-QA, QuALITY, RAGBench, CRAG | 1,015 items telecharges | 1.6 MB | NON INGERE |
| **Finance** | FinanceBench, ConvFinQA, FinQA, TAT-QA, Finance-Instruct | 2,250 items telecharges | 6.5 MB | NON INGERE |
| **Juridique** | French Case Law, COLD French Law, MultiEURLEX, LegalBench, Contrats | 2,500 items telecharges | 13 MB | NON INGERE |
| **Total** | **20 datasets** | **7,609 items** | **26.8 MB** | |

**DEPENDANCE** : L'ingestion des datasets sectoriels est faite par le repo `rag-data-ingestion`.
Les datasets sont telecharges dans `datasets/sectors/` (mon-ipad) mais pas encore ingeres dans les BDD separees.

### Methodes de test par secteur
| Methode | Commande | Usage |
|---------|----------|-------|
| Test rapide sectoriel | `python3 eval/quick-test.py --questions 5 --pipeline standard --sector btp` | Validation post-ingestion |
| Test batch sectoriel | `python3 eval/run-eval-parallel.py --sector finance --label "finance-baseline"` | Evaluation complete |

### HF Space — Endpoints pour chatbot integration
Les chatbots du site peuvent appeler les pipelines RAG sur HF Space :
```
Standard     : https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3
Graph        : https://lbjlincoln-nomos-rag-engine.hf.space/webhook/ff622742-6d71-4e91-af71-b5c666088717
Quantitative : https://lbjlincoln-nomos-rag-engine.hf.space/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9
Orchestrator : https://lbjlincoln-nomos-rag-engine.hf.space/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0
```
Appel depuis le frontend Next.js :
```javascript
const response = await fetch('https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: userQuestion })
});
const data = await response.json();
```
**IMPORTANT** : Le champ est `query` (PAS `question`).

### Etat HF Space (session 27)
- Standard : 200 OK, 100% accuracy (rock solid)
- Graph : 200 OK, 100% accuracy
- Orchestrator : 200 OK, 100% accuracy (sequential only)
- Quantitative : 200 OK, infra OK mais OpenRouter 429 rate limit

---

*Ce CLAUDE.md est géré depuis `mon-ipad/directives/repos/rag-website.md`.*
