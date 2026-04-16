# Nomos42 L1 Coordinator (LangGraph)

One-tick coordinator that sits between Claude Code (L0) and the HF/evo fleet (L2/L3).
Magentic-One pattern — thin orchestrator, never executes ML, picks ONE action per tick.

## Run

```bash
# dry run (scan + decide, no dispatch)
python3 scripts/coord/coord.py --dry-run

# real tick (dispatches the decision)
python3 scripts/coord/coord.py --tick

# last 10 ticks
python3 scripts/coord/coord.py --status
```

## Install (optional LangGraph upgrade)

`coord.py` runs without LangGraph as a plain 4-step pipeline. To upgrade to
the durable graph-state version:

```bash
pip install -r scripts/coord/requirements.txt
```

## Decision log

Append-only JSONL: `data/coord/decisions.jsonl`
SQLite checkpoint:  `scripts/coord/coord-state.sqlite`

## Cron

Add to crontab to run every 2h at :15 (offset from `autonomous-cycle.sh` at :30):

```
15 */2 * * * cd /home/termius/mon-ipad && python3 scripts/coord/coord.py --tick >> logs/coord.log 2>&1
```
