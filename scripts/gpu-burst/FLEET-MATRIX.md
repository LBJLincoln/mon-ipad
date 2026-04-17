# Nomos42 GPU Fleet Matrix — 1 Account = 1 Hypothesis

Stop burning the same experiment on every platform. Each row below is a **distinct
scientific question** assigned to a specific account. Collated result lands in
`data/fleet-matrix/<slot>/last.json` and competes for Pareto-best on the season board.

## NBA slots (8 parallel hypotheses)

| Slot | Platform / Account | GPU | Hypothesis | Data | Launcher |
|------|--------------------|-----|------------|------|----------|
| G1 | Kaggle `alexismoret6` | P100 9h/wk | TabICL-186f walk-forward (iter 129 baseline) | full 1257-game season | `scripts/kaggle/nba_season_backtest.py` |
| G2 | Colab #1 (user) | T4 ~3h/day | TabPFN-2.5 + isotonic (S20 canon) | 186f | manual .ipynb |
| G3 | Colab #2 (user) | T4 ~3h/day | Darwinian weights (S21 canon) + atlas-gic PnL | 186f | manual .ipynb |
| G4 | Lightning #1 | T4/A10G 22h/wk | Venn-Abers fusion (S22 canon) — NBA | 186f | `scripts/lightning/launch_karpathy.py --project nba` |
| G5 | Lightning #2 | T4/A10G 22h/wk | CPCV + DSR gated walk-forward | 186f | `scripts/lightning/launch_karpathy.py --project political` |
| G6 | Modal (user) | A10G PAYG | Karpathy ensemble mutation (S10-S17 diversify) | 186f | `modal run scripts/gpu-burst/modal-burst.py` |
| G7 | Brev Launchable (NVIDIA free tier) | A10G free | Karpathy autoresearch 1h burst | 186f | `brev-launchable/nomos42-karpathy.yaml` |
| G8 | Brev Launchable (NVIDIA Inception credits) | H100 | TabPFN-2.5 FULL 186f walk-forward | 186f | `brev-launchable/nomos42-tabpfn-train.yaml` |

## Political slots (4 parallel hypotheses)

| Slot | Platform / Account | GPU | Hypothesis | Data | Launcher |
|------|--------------------|-----|------------|------|----------|
| P-G1 | Lightning #2 | T4 | Full season walk-forward w/ 37-cat preds | 834 events | `scripts/lightning/launch_karpathy.py --project political` |
| P-G2 | Modal (brother) | A10G | Isotonic calibration on signal_type buckets | 834 events | `modal run scripts/gpu-burst/modal-burst.py --project political` |
| P-G3 | Colab (brother) | T4 | CatBoost + LightGBM stack on political_engine.py | 834 events | manual .ipynb |
| P-G4 | Kaggle (brother) | P100 | Mean-field signal aggregation + Darwinian | 834 events | `scripts/kaggle/nba_season_backtest.py --project political` |

## Shared-input invariant

ALL slots consume the same inputs:
- `features/engine.py` (parity-locked with HF spaces)
- `data/nba-agent/full-season-backtest.json` (NBA) or `data/political-signals.json` (POL)
- `scripts/arena/hf-llm-trading-floor/data/model-predictions-2025-26.json` (core predictions fan-out)

Only the **mutation/training hypothesis** differs. That way the scoreboard is apples-to-apples.

## Scoreboard

- `data/fleet-matrix/scoreboard.json` — latest Brier/ROI/Sharpe per slot + gen count + wall-time
- `data/fleet-matrix/<slot>/metrics.jsonl` — append-only history
- Cron (`*/6h`) rolls up best-of-fleet into `data/fleet-best.json` → wired into dashboard/trading-floor

## Rule

If two slots drift toward the same hypothesis, the later one **must** pick from the open-question list:
- 7K raw features + autoencoder embedding vs. 186f hand-picked
- Graph neural network over team-graph (TabGNN) vs. tabular tree ensemble
- Online Bayesian calibration per bucket vs. batch PAV isotonic
- Cross-season pretraining vs. same-season only

Track which ones are TAKEN in `data/fleet-matrix/hypothesis-registry.json`.
