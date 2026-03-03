# Storage Strategy — Phase 3 → Phase 5

> Last updated: 2026-03-03T10:30:00Z

## Current State

| Location | Used | Free | Contents |
|----------|------|------|----------|
| VM disk | 12 GB | 17 GB | Code, datasets (phase 1-3), eval results |
| Pinecone sota-rag-jina-1024 | 13.4K vectors | 100K limit | Benchmark + standard contexts |
| Neo4j Aura | 34.9K nodes / 153.7K rels | 200K / 400K limit | Entities + relationships |
| Supabase | ~17K rows | 500MB limit | Financial tables, benchmark data |
| GitHub LFS (rag-storage) | ~200 MB | 1 GB limit | Archived datasets, snapshots |

## Strategy by Phase

### Phase 3 (current — 11,700 questions)
- **VM**: Keep all 4 dataset files (~75 MB) + merged file (72 MB)
- **Pinecone**: Ingest standard contexts (~7,700 unique) → default namespace
  - Jina free tier: ~1M tokens/day → ~570 contexts/day → ~14 days total
  - Run daily batch via `scripts/ingest-phase3-pinecone.py`
- **Neo4j**: Already populated (19,965 nodes from phase2_extraction)
- **Supabase**: Financial tables already exist (no new ingestion needed)

### Phase 4 (planned — ~100K questions, ~700 MB datasets)
- **VM**: Only keep active dataset files, archive completed phases
- **rag-storage**: Push completed phase datasets to GitHub LFS
- **Pinecone**: May need second index or namespace rotation
- **Neo4j**: Monitor node count (200K limit)
- **Ingestion**: Use HF Space n8n workflows or batch scripts from VM

### Phase 5 (future — 1M+ questions)
- **VM**: Streaming ingestion only, no local dataset storage
- **HF Space**: Primary ingestion engine (16 GB RAM)
- **rag-storage**: All datasets in GitHub LFS
- **Consider**: Pinecone paid tier, Neo4j paid tier

## Archival Process

Archive completed phases to free VM disk:

```bash
# Push to rag-storage
cd /home/termius/mon-ipad
tar czf /tmp/phase-N-archive.tar.gz datasets/phase-N/
git -C /path/to/rag-storage add phase-N-archive.tar.gz
git -C /path/to/rag-storage commit -m "Archive phase N datasets"
git -C /path/to/rag-storage push

# Remove from VM
rm -rf datasets/phase-N/
```

## Pinecone Token Budget (Jina Free Tier)

| Phase | Unique Contexts | Est. Tokens | Days at 1M/day |
|-------|----------------|-------------|-----------------|
| Phase 3 Standard | 7,700 | ~13.5M | ~14 days |
| Phase 4 (projected) | ~70K | ~120M | ~120 days |

**Optimization**: Only embed contexts not already in benchmark-* namespaces.
