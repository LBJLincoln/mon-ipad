# Status de Session — 13 Fevrier 2026

> Resume final de la session de reorganisation du repo.

---

## Fichiers modifies ou crees UNIQUEMENT lors de cette session

### Fichiers crees (4)
| Fichier | Type | Description |
|---------|------|-------------|
| `directives/status.md` | NOUVEAU | Ce fichier — resume de session |
| `directives/claude.md` | NOUVEAU (symlink) | Symlink vers ../CLAUDE.md |
| `utilisation/commands.md` | NOUVEAU | Reference complete des commandes |
| `docs/data.json` | REINITIALISE | 37 executions, 4 pipelines, timestamps detailles |

### Fichiers modifies (2)
| Fichier | Modification |
|---------|-------------|
| `CLAUDE.md` | Reecrit en tour de controle (LIRE → UTILISER → PRODUIRE) |
| `directives/n8n-endpoints.md` | Enrichi : timestamps Paris/seconde, formats verifies, chemins post-reorg, double source Workflow IDs |

### Fichiers deplaces (159 mouvements)
| Destination | Origine | Nb |
|-------------|---------|-----|
| `directives/` | `context/`, `docs/technical/` | 3 |
| `technicals/` | `docs/technical/`, `docs/`, `context/`, `directives/` | 16 |
| `eval/` | `eval/` (ancienne position) via `utilisation/eval/` | 8 |
| `scripts/` | root + `scripts/` via `utilisation/scripts/` | 13 |
| `n8n/analysis/` | `n8n_analysis_results/` | 36 |
| `n8n/live/` + `n8n/validated/` + `n8n/sync.py` | `workflows/` | 15 |
| `datasets/` | `datasets/` via `utilisation/datasets/` | 4 |
| `db/` | `db/` via `utilisation/db/` | 24 |
| `mcp/` | `mcp/` via `utilisation/mcp/` | 1 |
| `snapshot/` | `workflows/snapshots/` + `logs/db-snapshots/` | 11 |
| `logs/` | `logs/` via `outputs/` | 45 |
| `outputs/` | `docs/`, root, `context/` | 5 |
| `docs/` | reste en place (3 fichiers) | 0 |

### Fichiers supprimes (8)
| Fichier | Raison |
|---------|--------|
| `scripts/install-mcp-servers.sh` | Shell script — consigne user |
| `scripts/n8n-oracle-setup.sh` | Shell script — consigne user |
| `scripts/setup-n8n-docker.sh` | Shell script — consigne user |
| `start-next-session.sh` | Shell script — consigne user |
| `start-session.sh` | Shell script — consigne user |
| `start-sota-session.sh` | Shell script — consigne user |
| `logs/db-snapshots/.gitkeep` | Dossier deplace vers snapshot/db/ |
| `logs/errors/.gitkeep` | Dossier deplace vers logs/ (reconstruit) |

### Dossiers supprimes (anciens, vides apres deplacements)
`context/`, `eval/` (ancien), `scripts/` (ancien), `phases/`, `mcp/` (ancien), `datasets/` (ancien), `db/` (ancien), `n8n_analysis_results/`, `workflows/`, `logs/` (ancien), `docs/technical/`, `docs/migration/`, `utilisation/` (intermediaire)

---

## Analyse concrete de l'etat d'avancement

### Metriques live (docs/status.json du 2026-02-12)

| Pipeline | Accuracy | Tested | Target | Gap | Status |
|----------|----------|--------|--------|-----|--------|
| Standard | 0.0% | 8 | 85% | -85pp | BLOQUE |
| Graph | 76.5% | 17 | 70% | +6.5pp | PASSE |
| Quantitative | 0.0% | 8 | 85% | -85pp | BLOQUE |
| Orchestrator | 0% | 0 | 70% | -70pp | NON TESTE |
| **Overall** | **25.5%** | **33** | **75%** | **-49.5pp** | **BLOQUE** |

### Bilan
- **1 pipeline passe** : Graph (76.5% > 70% cible)
- **2 pipelines bloques** : Standard (0%) et Quantitative (0%)
- **1 pipeline non teste** : Orchestrator
- **Infrastructure** : reorganisation complete, 13 dossiers, architecture agentic loop
- **data.json** : reinitialise avec 37 executions (28 standard, 4 quant, 3 graph, 1 orch, 1 unknown)
- **Derniere execution par pipeline** : standard #19476, graph #19479, quantitative #19457, orchestrator #19323

### Blockers
1. Standard : requetes retournent erreurs/timeouts — noeud a diagnostiquer
2. Quantitative : 6 timeouts sur 8 tests — webhook timeout probable (30s)
3. Orchestrator : depend de Standard + Quantitative fonctionnels

### Prochaine action
```
1. python3 eval/quick-test.py --questions 1 --pipeline standard
2. python3 eval/node-analyzer.py --execution-id <ID>
3. python3 scripts/analyze_n8n_executions.py --execution-id <ID>
4. Identifier le noeud defaillant → fixer dans n8n → retester 5/5
```
