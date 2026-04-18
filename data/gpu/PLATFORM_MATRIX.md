# GPU Platform Matrix — 2026-04-18

Seven GPU platforms, each runs a **unique** strategy and logs to **one** department's council feed.

| Platform | Hardware | Strategy | Dept | Schedule | Script |
|---|---|---|---|---|---|
| Colab A | T4 (~2-3h/day) | TabPFN 7.1.1 ensemble stack | D3 Evolution | manual | `notebooks/colab_tabpfn7_ensemble.ipynb` |
| Colab B | T4 (~2-3h/day) | TabICL 2.0.3 context sweep | D3 Evolution | manual | `notebooks/colab_tabicl2_contexts.ipynb` |
| Kaggle P100 | P100 16GB (9h/session) | SOTA reimplement queue (cycle 13+ papers) | D1 Research | manual + GH Action dispatch | `scripts/kaggle/nba_karpathy_loop.py` |
| ZeroGPU H200 | H200 (~15min/day free) | TabICL/TabPFN serverless + island seeding | D6 Evaluation | GH Action every 6h | `scripts/gpu-burst/zerogpu-burst.py` |
| Modal A10G | A10G serverless | CPCV + DSR gate walk-forward | D6 Evaluation | GH Action every 4h :15 | `scripts/gpu-burst/modal-burst.py` |
| Lightning T4 | T4 (22h × 2 accts) | Karpathy tree-loop NBA (02:00) + POL (14:00) | D3 Evolution | GH Action 2×/day | `scripts/lightning/launch_karpathy.py` |
| Paperspace Gradient | Free GPU (unlim restarts) | Darwinian weights + Venn-Abers fusion | D2 Engineering | GH Action every 8h | `scripts/paperspace/launch_karpathy.py` |

## Each run writes to:

- `data/gpu/<platform>/<iso>.jsonl` — raw result log
- `data/departments/gpu-results-<dept>.jsonl` — dept-council feed
- Supabase `experiments` table (if DATABASE_URL set)

## Zero duplication guarantee

Each platform touches a distinct **(strategy × dept)** pair. No two platforms run the same mutate-eval loop on the same model family.

- Tree-based evolution: only Lightning T4
- TabPFN: only Colab A
- TabICL: Colab B + ZeroGPU (different: Colab sweeps hparams, ZeroGPU seeds from live islands)
- CPCV+DSR: only Modal A10G
- Darwinian+Venn-Abers fusion: only Paperspace (new 2026-04-18)
- SOTA paper reimpl: only Kaggle P100 (9h deep)

## Adding a new platform

1. Add row to this matrix.
2. Create `scripts/<plat>/launch.py`.
3. Add GH Action at `.github/workflows/<plat>-burst.yml`.
4. Call `scripts.gpu.dept_log.record()` at the end of every run.
