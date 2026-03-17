# PILOTAGE — Commandes Termius & Dashboard Live

> Date: 2026-03-10 | Pour: Alexis via Termius

---

## 1. CONNEXION SSH

```bash
ssh termius@34.136.180.66
# ou via Termius: host "GCP-VM", port 22
```

## 2. TMUX — Pilotage multi-panes

### Lancer le cockpit complet (4 panes)
```bash
cd ~/mon-ipad && source .env.local

# Créer session tmux "nomos"
tmux new-session -d -s nomos -n monitor

# Pane 0: Monitor live (rafraîchit toutes les 5min)
tmux send-keys -t nomos:monitor 'source .env.local && python3 ops/monitor.py --loop 300' Enter

# Pane 1: Logs d'erreurs en temps réel
tmux split-window -h -t nomos:monitor
tmux send-keys -t nomos:monitor.1 'tail -f logs/errors/pipeline-errors.jsonl | python3 -m json.tool' Enter

# Pane 2: Eval continu
tmux split-window -v -t nomos:monitor.0
tmux send-keys -t nomos:monitor.2 'source .env.local && python3 eval/quick-test.py --proxy --pipelines standard --questions 5' Enter

# Pane 3: Git log / status
tmux split-window -v -t nomos:monitor.1
tmux send-keys -t nomos:monitor.3 'watch -n 60 "git log --oneline -5 && echo --- && cat data/health-status.json | python3 -m json.tool"' Enter

# Attacher
tmux attach -t nomos
```

### Commande one-liner (snippet Termius)
```bash
cd ~/mon-ipad && source .env.local && tmux new-session -d -s nomos 'python3 ops/monitor.py --loop 300' \; split-window -h 'tail -f logs/errors/pipeline-errors.jsonl 2>/dev/null || echo "No errors yet"' \; split-window -v -t 0 'watch -n 120 cat data/health-status.json' \; attach
```

## 3. SNIPPETS TERMIUS

Créer dans Termius > Snippets :

| Nom | Commande |
|-----|----------|
| `nomos-start` | `cd ~/mon-ipad && source .env.local && tmux attach -t nomos 2>/dev/null \|\| tmux new-session -s nomos` |
| `nomos-monitor` | `cd ~/mon-ipad && source .env.local && python3 ops/monitor.py` |
| `nomos-monitor-live` | `cd ~/mon-ipad && source .env.local && python3 ops/monitor.py --loop 300` |
| `nomos-errors` | `cd ~/mon-ipad && tail -20 logs/errors/pipeline-errors.jsonl \| python3 -m json.tool` |
| `nomos-eval` | `cd ~/mon-ipad && source .env.local && python3 eval/quick-test.py --proxy --pipelines standard --questions 5` |
| `nomos-health` | `cd ~/mon-ipad && cat data/health-status.json \| python3 -m json.tool` |
| `nomos-claude` | `cd ~/mon-ipad && ./scripts/claude-session.sh` |
| `nomos-push` | `cd ~/mon-ipad && git add -A && git commit -m "update" && git push` |
| `nomos-spaces` | `curl -s https://lbjlincoln-nomos-rag-engine.hf.space/healthz && echo " S1 OK"` |
| `nomos-e5-count` | `cd ~/mon-ipad && source .env.local && python3 -c "import socket;socket.getaddrinfo=lambda h,p,f=0,t=0,pr=0,fl=0:socket.__dict__['getaddrinfo'].__wrapped__(h,p,2,t,pr,fl) if hasattr(socket.getaddrinfo,'__wrapped__') else [(2,1,6,'',('0.0.0.0',443))];print('Use Pinecone MCP or ops/monitor.py')"` |

## 4. n8n WEB UI (accès depuis Termius/navigateur)

### Accès direct (pas besoin de gws)
Les Spaces n8n sont accessibles directement via navigateur :

| Space | URL | Login |
|-------|-----|-------|
| S1 | `https://lbjlincoln-nomos-rag-engine.hf.space` | ci@nomos.ai / CI-Nomos-2026! |
| S3 | `https://lbjlincoln-nomos-rag-engine-3.hf.space` | idem |
| S5 | `https://lbjlincoln-nomos-rag-engine-5.hf.space` | idem |
| S9 | `https://lbjlincoln-nomos-rag-engine-9.hf.space` | idem |

### Voir les exécutions d'un workflow
1. Ouvrir l'URL du Space dans un navigateur
2. Se connecter avec ci@nomos.ai
3. Aller dans Workflows > cliquer sur le workflow
4. Onglet "Executions" à gauche
5. Chaque exécution montre les nœuds en rouge (erreur) ou vert (succès)

### gws CLI (alternatif)
gws nécessite un navigateur pour l'OAuth initial. Sur VM headless :
```bash
# Option 1: Tunnel SSH depuis ton Mac/iPad
ssh -L 8080:localhost:8080 termius@34.136.180.66
# Puis ouvrir http://localhost:8080 dans ton navigateur local

# Option 2: Pas besoin de gws — les URLs HF sont déjà publiques
# Tout le pilotage se fait via ops/monitor.py + API n8n
```

## 5. COMMANDES PAR AGENT

### Agent 1: Monitor
```bash
python3 ops/monitor.py                    # One-shot
python3 ops/monitor.py --loop 300         # Live (5min)
python3 ops/monitor.py --hours 24         # Last 24h
python3 ops/monitor.py --errors-only      # Erreurs seulement
python3 ops/monitor.py --json             # JSON output
```

### Agent 2: Eval/Test
```bash
python3 eval/quick-test.py --proxy --pipelines standard --questions 5
python3 eval/quick-test.py --proxy --pipelines standard,graph --questions 10
python3 eval/expert-eval.py --sector all --questions 20
python3 eval/turbo-eval.py --sector all
```

### Agent 3: Pipeline RAG
```bash
python3 ops/n8n-api.py list               # Lister workflows
python3 ops/n8n-api.py activate <ID>      # Activer workflow
python3 ops/deploy-standard-v35.py        # Déployer Standard V3.5
```

### Agent 4: Ingestion/Enrichment
```bash
python3 ops/fast-ingest.py --sector all   # Ingestion parallèle E5
python3 ops/exa-mass-ingest.py            # Recherche + ingestion Exa.AI
python3 ops/local-pdf-ingest.py           # PDFs locaux
python3 ops/populate-neo4j-entities.py    # Enrichissement Neo4j
```

### Agent 5: Docs/State
```bash
cat directives/PROJECT-STATE.md           # État courant
cat data/health-status.json               # Santé live
cat logs/errors/pipeline-errors.jsonl     # Historique erreurs
git log --oneline -10                     # Derniers commits
```

## 6. FICHIERS CLÉS

| Fichier | Rôle | Auto-update |
|---------|------|-------------|
| `data/health-status.json` | Santé live (JSON) | Oui (monitor.py) |
| `logs/errors/pipeline-errors.jsonl` | Erreurs par nœud (JSONL) | Oui (monitor.py) |
| `logs/monitor-report.json` | Rapport complet | Oui (monitor.py) |
| `directives/PROJECT-STATE.md` | État projet | Manuel |
| `technicals/DEBUG-PLAYBOOK.md` | 90+ fixes | Manuel |
