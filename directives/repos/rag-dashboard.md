# rag-dashboard — CLAUDE.md

> Last updated: 2026-02-25T11:30:00+00:00
> **Ce repo est statique — déployé PUBLIQUEMENT sur Vercel.**
> **URL LIVE : https://nomos-dashboard-alexis-morets-projects.vercel.app/**
> Tu es un agent Claude Code specialise dans le DASHBOARD DE MONITORING live.
> **MODELE PRINCIPAL : `claude-opus-4-6`** — Decisions UI/UX, architecture, evaluation.
> **DELEGATION** : Haiku 4.5 pour exploration rapide si necessaire.
> Ce repo est en lecture seule vis-à-vis des pipelines RAG.
> Processus team-agentic multi-model : voir `technicals/project/team-agentic-process.md` (dans mon-ipad).
> **Bottleneck-first** : Builds fonctionnels en background. Se concentrer sur les problèmes d'affichage et de data.
> **Push régulier** : Commit + push toutes les 15-20 min.

---

## OBJECTIF DE CE REPO

Afficher en temps réel les métriques de performance de tous les pipelines RAG.
**Lecture seule** — ne modifie aucun workflow, aucune BDD.

### Ce que le dashboard affiche
- Accuracy par pipeline (Standard, Graph, Quantitative, Orchestrator)
- Phase gates (Phase 1 → 5 passées ou non)
- Dernières exécutions (timestamps, latences)
- État des BDD (Pinecone, Neo4j, Supabase)
- Historique des sessions et des améliorations

---

## SOURCE DE DONNÉES

```
API (VM)  : http://34.136.180.66:5678/webhook/nomos-status
Fallback  : https://raw.githubusercontent.com/LBJLincoln/mon-ipad/main/docs/status.json
```

**Le dashboard lit `status.json` généré par `eval/generate_status.py` sur la VM.**
Il n'y a pas de n8n local ni de Codespace nécessaire.

---

## INFRASTRUCTURE

```
Type        : Site statique (HTML/JS/CSS)
Deploy      : Vercel (PUBLIC — https://nomos-dashboard-alexis-morets-projects.vercel.app/)
n8n local   : AUCUN
Codespace   : AUCUN nécessaire
Status      : LIVE — dashboard displaying real-time metrics from status.json
```

---

## STACK TECHNIQUE

```
Statique    : HTML5 + Vanilla JS (ou React minimal)
Polling     : Fetch status.json toutes les 30 secondes
Charts      : Chart.js ou similaire (CDN, pas de npm)
Style       : Tailwind CDN ou CSS minimal
Deploy      : GitHub Pages (simple, gratuit, illimité)
```

---

## DÉVELOPPEMENT (si modifications nécessaires)

Les modifications du dashboard se font directement en local ou dans un Codespace simple.
Pas de n8n, pas de Docker nécessaire.

```bash
# Démarrer en local
python3 -m http.server 3000
# Ouvrir http://localhost:3000

# Modifier index.html / app.js / styles.css
# Commit + push → GitHub Pages auto-déploie
git add .
git commit -m "feat(dashboard): [description]"
git push origin main
```

---

## MÉTRIQUES AFFICHÉES (depuis status.json)

```json
{
  "phase": 1,
  "overall_accuracy": 0.781,
  "gates_passed": false,
  "pipelines": {
    "standard": {"accuracy": 0.855, "target": 0.85, "pass": true},
    "graph": {"accuracy": 0.687, "target": 0.70, "pass": false},
    "quantitative": {"accuracy": 0.783, "target": 0.85, "pass": false},
    "orchestrator": {"accuracy": 0.800, "target": 0.70, "pass": true}
  }
}
```

---

## RÈGLES D'OR

1. **Lecture seule** — ne jamais écrire dans les BDD ou workflows
2. **Pas de credentials** côté client (status.json est public par design)
3. **Polling 30s max** — ne pas surcharger le webhook VM
4. **Fallback GitHub** si le webhook VM ne répond pas
5. **Push → auto-deploy** GitHub Pages ou Vercel

---

## DATASETS & METRIQUES — CE QUE LE DASHBOARD AFFICHE

### Metriques actuelles (Phase 1 PASSED, Phase 2 EN COURS)
| Pipeline | Phase 1 (PASSED) | Phase 2 v10 (last completed) | Target P2 |
|----------|------------------|------------------------------|-----------|
| Standard | 85.5% PASS | 60.4% (1263q tested) | >= 75% |
| Graph | 78.0% PASS | 55.7% | >= 55% |
| Quantitative | 92.0% PASS | 53.3% | >= 65% |
| Orchestrator | 80.0% PASS | 58.2% | >= 70% |
| Overall | 83.9% PASS | 57.0% | >= 75% |

### Metriques Phase 2 (a ajouter)
| Metrique | Source | Format |
|----------|--------|--------|
| Questions testees | `status.json → total_questions` | Nombre (actuellement 932) |
| Accuracy par pipeline | `status.json → pipelines.<name>.accuracy` | Pourcentage |
| Phase gates | `status.json → gates_passed` | Booleen |
| Iterations stables | `status.json → stable_iterations` | Nombre (cible: 3) |
| Latence moyenne | A ajouter | Secondes |
| Concurrence max testee | A ajouter | Nombre de questions simultanées |

### Total datasets du projet
| Phase | Questions |
|-------|-----------|
| Phase 1 | 200 |
| Phase 2 | 3,000 |
| Sectoriels | 7,609 |
| **Total disponible** | **10,809** |

### HF Space status (pour monitoring)
```
URL Health  : https://lbjlincoln-nomos-rag-engine.hf.space/healthz
Status API  : http://34.136.180.66:5678/webhook/nomos-status
Fallback    : https://raw.githubusercontent.com/LBJLincoln/mon-ipad/main/docs/status.json
```
Le dashboard peut afficher un indicateur de sante HF Space en interrogeant le healthcheck.

---

*Ce CLAUDE.md est géré depuis `mon-ipad/directives/repos/rag-dashboard.md`.*
