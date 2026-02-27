# Repo Control Tower

Updated: 2026-02-27T15:40:00Z

## Canonical repos observed from mon-ipad
- mon-ipad (control tower)
- rag-website (ETI site)
- rag-pme-connectors (Nomos42 target)
- rag-pme-usecases
- rag-dashboard
- rag-storage (garbage/storage archive)
- rag-data-ingestion
- rag-tests

## Commands
```bash
# quick health snapshot
for d in /home/termius/mon-ipad /home/termius/rag-website /home/termius/rag-pme-connectors /home/termius/rag-pme-usecases /home/termius/rag-dashboard /home/termius/rag-storage /home/termius/satellite-cleanup/rag-data-ingestion /home/termius/satellite-cleanup/rag-tests; do
  echo "=== $d ==="; git -C "$d" status --short | head -n 20; done

# sync all outputs/artifacts to storage repo
bash scripts/sync-garbage-storage.sh
```

## Rule
After each milestone: update `docs/executive-summary.md`, run garbage sync, then commit+push affected repos.
