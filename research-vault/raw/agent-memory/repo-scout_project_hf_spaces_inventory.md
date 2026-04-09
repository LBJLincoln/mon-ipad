---
name: project_hf_spaces_inventory
description: Complete HuggingFace spaces inventory across all 3 accounts — status, recommendation, RGWA repurpose plan
type: project
---

## Complete HF Spaces Inventory (2026-03-25)

Total: 31 spaces across 3 accounts. 6 KEEP (NBA evolution), 19 DELETE (RAG/Eve/dead), 5 REPURPOSE (RGWA), 1 INVESTIGATE.

**Why:** RGWA creative AI project needs 4 new spaces. 19 dead spaces free up slots.
**How to apply:** Use this as authoritative reference before creating any new spaces. Always check this before suggesting "create a new space".

### KEEP (6) — NBA Evolution Islands
| ID | Space | Status |
|----|-------|--------|
| S10 | Nomos42/nba-quant | running (migrated 2026-03-26) |
| S11 | Nomos42/nba-quant-2 | running (migrated 2026-03-26) |
| S12 | Nomos42/nba-evo-3 | running (migrated 2026-03-26) |
| S13 | Nomos42/nba-evo-4 | running (migrated 2026-03-26) |
| S14 | Nomos42/nba-evo-5 | running |
| S15 | Nomos42/nba-evo-6 | running |

### INVESTIGATE (1)
- Nomos42/nomos42-pnl-3d — currently RUNNING, unclear purpose. Verify before touching.

### REPURPOSE for RGWA (5 candidates → 4 slots)
| RGWA Purpose | Candidate Space |
|---|---|
| Creative Studio GUI (Gradio) | LBJLincoln/nomos-rgwa (slug ideal) |
| Music Gen (ACE-Step/DiffRhythm) | LBJLincoln/nomos-nba-swarm OR Nomos42/nomos-eve |
| Video Gen (Wan2.1) | Nomos42/nomos-worker-2 OR LBJLincoln/nomos-embeddings-api |
| Voice Synthesis (GPT-SoVITS/RVC) | LBJLincoln/nomos-neo4j-proxy (verify Neo4j MCP still needed first) |

### DELETE (19) — All dead RAG/Eve/LiteLLM
LBJLincoln: nomos-eve-agent, nomos-openclaw, nomos-rag-engine-7, nomos-docling-api, nomos-rag-engine, nomos-rag-engine-5, nomos-rag-engine-3, nomos-rag-engine-9
LBJLincoln26: nomos-rag-engine-6, nomos-rag-engine-4, nomos-rag-engine-2, nomos-rag-engine-10 (runtime error!), nomos-rag-engine-8
Nomos42: nomos-docling-2, nomos-rag-worker-2, nomos-litellm-2, nomos-embeddings-2, nomos-rag-engine-11

Full inventory JSON: /home/termius/nomos-nba-agent/data/results/hf-spaces-inventory.json

### GPU constraint for RGWA
- Wan2.1 video gen is GPU-heavy — CPU free tier will be extremely slow
- Lightning.ai credits arrive 2026-04-01 (account: moretalexis24@gmail.com)
- Consider deferring video gen space until Lightning.ai credits available
- ACE-Step 1.5 and GPT-SoVITS RVC inference are CPU-compatible
