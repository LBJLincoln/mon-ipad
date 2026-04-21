# Proposal: TabPFN-2.5 base + Venn-Abers head for S22 (`nba-evo-s22`)

- **Author:** DR FRANKENSTEIN (queued from HAWKEYE SOTA scan, 2026-04-20 cycle)
- **Status:** DRAFT — writeup only. No engine.py or HF-Space edits this cycle (S22 is running a Cat 66 canary).
- **Target island:** S22 `TESTforge42/nba-evo-s22`, role `venn_abers_fusion`, current fleet-best Brier **0.22073** (gen 39, checkpointed 2026-04-19).
- **Expected delta:** Brier **-0.002 to -0.006** → ~**0.2148 – 0.2187**.
- **Sources:** arXiv:2511.08667 (TabPFN-2.5), arXiv:2603.26611 (TabArena Apr-2026), code https://github.com/PriorLabs/TabPFN.
- **Effort:** 2 dev-days + 1 GPU canary day.
- **Execution cycle:** NEXT (2026-04-21 00:00 UTC slot), contingent on S22 Cat-66 canary closing green.

---

## 1. Model swap points in S22's training pipeline

S22 today uses the standard tree zoo (lightgbm/catboost/xgboost ± Brier variants) wrapped in a Venn-Abers head via MAPIE. All relevant code lives in `nba-quant-space/app.py`:

| Concern | Current location | Change |
|---|---|---|
| Model zoo registry | `ALL_MODEL_TYPES` L651-668, `CPU_MODEL_TYPES` L674 | Add `"tabpfn25"` (GPU-only — gated on `_HAS_GPU`) |
| Random init | `Individual.__init__` L760 `"model_type": random.choice(...)` | No change — picked up via ALL_MODEL_TYPES |
| Mutation | L834 `self.hyperparams["model_type"] = random.choice(...)` | No change |
| Role specialization | `elif role == "lightgbm_specialist":` L994 | Add `elif role == "venn_abers_fusion":` block that seeds 3/5 islands with `["tabpfn25", "lightgbm_brier"]` |
| Model builder | the big `if model_type == "..."` ladder around L1200 (base_models block) | Add `elif model_type == "tabpfn25":` branch that instantiates `TabPFNClassifier(device='cuda', ignore_pretraining_limits=True)` |
| Calibration head | L1427-L1460 (Venn-Abers via `MapieClassifier`) | **UNCHANGED** — TabPFN-2.5 feeds probas through existing venn_abers path |
| Elite config carry-over | L3011-3015 | Ensure `"model_type"` and `"calibration"` survive across gens (already does) |

Key invariant: **Venn-Abers head stays**. S22's edge is the calibration fusion; we are only swapping the tree base for a TabPFN-2.5 base.

## 2. GPU requirement

TabPFN-2.5 is GPU-only at our scale. Two viable rails:

1. **Paperspace Gradient** (already wired, free-tier unlimited restarts). Pipe: `scripts/gpu-burst/modal-burst.py` pattern → new `scripts/gpu-burst/tabpfn-burst.py`. Write predictions to `data/departments/gpu-results-tabpfn.jsonl`, then cross-island-sync promotes.
2. **Colab T4** (manual, fallback). Notebook in `notebooks/tabpfn25-s22-canary.ipynb`.

HF Space S22 itself stays CPU — `_HAS_GPU` guard in `ALL_MODEL_TYPES` keeps CPU workers from ever selecting `tabpfn25`. The Space only receives *weights/predictions* via the existing cross-island-sync pickle channel (`scripts/gpu-burst/cross-island-sync.py`).

**Memory footprint (per TabPFN-2.5 benchmark in arXiv:2511.08667):** ~4.6 GB VRAM @ 50k rows × 200 features in fp16. Fits T4/A10G/H100. Paperspace Free (M4000 8 GB) is tight but workable in fp16.

## 3. Canary protocol + kill criteria

- **Canary island:** shadow copy of S22 at `TESTforge42/nba-evo-s22-tabpfn`, duplicated via `HfApi.duplicate_space(..., hardware='cpu-basic')`.
- **Gen budget:** 3 generations, ≤ 36 hours wallclock.
- **Tracking:** `data/experiment-ledger.json` entry + `data/audit/` snapshot at each gen via INTERNAL AFFAIRS.
- **Kill criteria (HARD REVERT):**
  - gen-1 Brier > **0.22200** → revert (0.13% worse than baseline).
  - gen-2 Brier not strictly better than gen-1 → revert.
  - gen-3 Brier > **0.21900** → revert (did not hit the -0.002 floor).
  - Any `nan`, calibration-head exception, or cross-island-sync checksum mismatch → revert immediately.
- **Graduation:** if gen-3 Brier ≤ 0.21900 AND Venn-Abers head alarm rate ≤ current S22 → promote tabpfn25 into S22 main role (delete `-tabpfn` shadow, flip `role` on primary).

## 4. Dependency audit

```
tabpfn==2.5.*            # from PriorLabs/TabPFN
torch>=2.3,<3            # already pinned via LightGBM GPU stack
numpy>=1.26
```

- `pip install tabpfn` pulls a ~30 MB wheel + lazily downloads the pretrained checkpoint (~1.3 GB, cached under `~/.cache/tabpfn`).
- No new C/CUDA toolchain requirement — wheels are manylinux + cu121.
- Hub Space size budget: checkpoint MUST be fetched on first inference from PriorLabs HF (not committed to the Space repo; stays below the 13 MB LFS-free ceiling that bit us in the coalition deploy).
- Risk: `ignore_pretraining_limits=True` required because NBA train set > TabPFN's 10k-row comfort band. Paper claims degradation begins > 500k rows, we are well inside.

## 5. Concrete diff spec for the island engine

File: `nba-quant-space/app.py` (mirror: `council-spaces/template/app.py` if used).

```python
# --- L651-L674 zone ---
ALL_MODEL_TYPES = [
    "xgboost", "xgboost_brier", "lightgbm", "lightgbm_brier",
    "catboost", "catboost_brier", "random_forest", "extra_trees",
    "logistic_regression", "stacking",
+   "tabpfn25",  # GPU-only, arXiv:2511.08667
]
# CPU_MODEL_TYPES stays untouched → tabpfn25 never selected on CPU workers.

# --- L994 role block, add new branch ---
elif role == "venn_abers_fusion":
    island_model_pool = [
        ["tabpfn25", "lightgbm_brier"],
        ["tabpfn25", "catboost_brier"],
        ["lightgbm_brier", "catboost_brier"],
        ["tabpfn25", "lightgbm_brier", "extra_trees"],
        ["lightgbm_brier", "xgboost_brier", "extra_trees"],
    ]

# --- L1200 model builder ladder, add branch ---
elif model_type == "tabpfn25":
    from tabpfn import TabPFNClassifier
    base_models.append(TabPFNClassifier(
        device="cuda",
        ignore_pretraining_limits=True,
        n_estimators=hp_eval.get("n_estimators", 8),
        random_state=seed,
    ))
    # Calibration head (Venn-Abers via MAPIE) handled by existing L1427 path — no change.
```

Mirror + sha256 parity step (day-of):
```
sha256sum nba-quant-space/app.py | tee engine.sha256.lock
# confirm identical on hf-space mirror before deploy
```

## 6. Top-line risk

Checkpoint fetch from PriorLabs HF during Space cold-boot could race against S22's Karpathy loop and silently fall back to random inference — mitigation is a startup probe + explicit fail-closed before the first generation starts.
