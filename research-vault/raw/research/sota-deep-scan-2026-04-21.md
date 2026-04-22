# SOTA Deep Scan — 2026-04-21

Author: HAWKEYE. Scope: arXiv Oct 2025 – Apr 2026, Semantic Scholar, NeurIPS 2025, ICML 2025, KDD 2025, MDPI Information 2026. Budget ~60 min, consolidated.

Universal data-leakage gate: every proposal must respect the `sim_date_cutoff` pattern PLUMBER shipped 2026-04-21 (NBA+POL YouTube stripped because 152/229 videos post-dated the sim window, same failure class as the POL `excess_return` bug 2026-04-18). Any new feed must log its publication timestamp per row and be filtered `pub_ts < sim_date` before it hits `features/engine.py`.

---

## Top-5 ranked proposals (expected-impact × effort-inverse)

| # | Proposal | Domain | Expected impact | Effort | Risk | Source |
|---|----------|--------|-----------------|--------|------|--------|
| 1 | **NBA TF: replace Kelly with calibration-aware fractional Kelly + over-bet penalty** | NBA TF | Stop the −70% bleed; ~+$40K salvage on $1,700→$100 trajectory within 10 days | 2 days | LOW | Downey (2026) + MDPI *Information* 17/1/56 (Jan 2026) |
| 2 | **Swap tree-ensemble ranker for OrionMSP or TabICLv2** on NBA fleet | NBA islands | Brier 0.22073 → ~0.215 projected (OrionMSP beats TabICL on imbalanced, high-dim per ScoringBench) | 3 days | MED | OrionMSP [arXiv:2511.02802](https://arxiv.org/abs/2511.02802), TabICLv2 [arXiv:2602.11139](https://arxiv.org/abs/2602.11139) |
| 3 | **ITF/PQTF: enforce no-trade regime via volatility classifier + action-sparsity penalty** | ITF | Recover $35K ITF drawdown; prevent weekend-crypto bleed; keep ≥3 allocations rule OFF on dead-tape days | 2 days | LOW | Amberdata *Volatility Framework* + MDPI Mathematics 13/15/2382 (Markov-switching vol) |
| 4 | **Generalized Venn-Abers on top of every islan d probability output** | Calibration | Uniform +0.003–0.007 Brier tightening across NBA+POL fleets; finite-sample guarantees | 2 days | LOW | [arXiv:2502.05676](https://arxiv.org/abs/2502.05676) (ICML 2025 poster) |
| 5 | **Market-implied calibration transfer: blend Kalshi/Polymarket prices into POL target distribution** | POL forecasting | POL Brier 0.24923 → ~0.243 projected (prediction markets hit 91% on 2026 Senate vs polls) | 3 days | MED | Kalshi 2026 Senate report + `py-clob-client` |

All five respect sim_date_cutoff: prices/quotes are point-in-time, Venn-Abers is fit on held-out calibration fold, OrionMSP runs in-context so no leakage-by-finetune.

---

## Domain sections

### 1. NBA outcome prediction (Brier optimization)

**Current diagnosis (critical):** NBA TF is −70% while our island Brier is 0.22073. That gap is a **calibration-to-Kelly mismatch**, not a prediction-quality miss. Matthew Downey's fractional-Kelly simulations and the NeurIPS 2025 discussion both show that slight over-betting against a miscalibrated edge compounds to ruin — exactly our trajectory. The fix is not "better Brier"; it is "scale bets by calibration confidence."

- **P1 — `kelly_fraction = raw_kelly × (1 − ECE) × √(prob_conf_width)`.** Implement in `scripts/arena/hf-llm-trading-floor/app.py` at the Kelly-sizing stage. Calibration-aware fractional Kelly is the exact medicine for our symptoms.
  - Anchor: MDPI *Information* 17(1):56 (Jan 2026) — NBA RNN + MC-dropout + fractional-Kelly decision layer, mapped explicitly to "probabilistic lift → economic performance." [link](https://www.mdpi.com/2078-2489/17/1/56)
  - Map: feed the MC-dropout width as `prob_conf_width`; cap `kelly_fraction ≤ 0.25` (user pref: aggressive but not suicidal).

- **P2 — Replace TabICL with OrionMSP on the fleet foundation-model lane.** OrionMSP uses multi-scale sparse attention + Perceiver-latent memory, rivals/beats TabICL on imbalanced + high-dim tabular, near-linear attention scaling. [arXiv:2511.02802](https://arxiv.org/abs/2511.02802) (Nov 2025). Also evaluate TabICLv2 [arXiv:2602.11139](https://arxiv.org/abs/2602.11139) (Feb 2026) — open, faster.

- **P3 — Category-specific ML ensemble instead of single-game-outcome model.** Recent NBA paper on arXiv/Nature *Scientific Reports* 2025-13657-1 shows stacked ensembles (LR + XGB + CatBoost) per-category beat single-model. Map to our 227-category edge engine: one head per category, isotonic on top.

- **P4 — ScoringBench proper-scoring-rule evaluation.** Replace "Brier only" island selector with CRPS + ECE + Brier bundle — [arXiv:2603.29928](https://arxiv.org/abs/2603.29928). Avoids selecting islands that over-fit Brier but are miscalibrated.

### 2. Political event forecasting

**Current:** POL is the only winning TF (+28%), fleet-best P5 Brier 0.24923. Headroom exists.

- **P5 — Kalshi + Polymarket prices as features.** Kalshi hit 91% on 34/2026 Senate races (news.kalshi.com 2026 Senate report). `py-clob-client` + Kalshi's public API give real-time implied probabilities. Add 3 features to POL engine: `kalshi_prob`, `kalshi_volume_24h`, `market_vs_model_delta`. Respect sim_date_cutoff by pulling the snapshot at 06:00 UTC of each sim-date.
- **P6 — Market-movement-over-news-latency signal.** Kalshi dropped Florida candidate 78%→34% in hours while polls took 2 weeks — use `|kalshi_prob(t) − kalshi_prob(t−24h)|` as volatility feature.
- **Kill:** classical polling-drift models — already subsumed by market prices, will just add noise.

### 3. LLM multi-agent trading (preventing overtrading / lockstep / hype-chase)

**Current:** ITF 17 MAX-aggressive agents at −35%. Root cause (from memory `project_itf_aggressive_v2_apr20`): we **mandated** ≥3 allocations/day + 75% deploy floor. In dead-tape crypto weekends that forces bad trades.

- **P7 — Action-sparsity / "no-trade" reward shaping.** Volatility-regime gate: if `realized_vol_24h < regime_floor` (Markov-switching detector), **waive** the MIN_DEPLOY_PCT floor and the ≥3 allocations rule. Anchor: Amberdata volatility framework + MDPI Mathematics 13/15/2382 (Markov-switching quantile spillover vol forecasting). Dead-tape detector is the literature-canonical fix.
- **P8 — ATLAS Adaptive-OPRO prompt optimization.** [arXiv:2510.15949](https://arxiv.org/abs/2510.15949). Dynamically updates each agent's instructions using real-time stochastic feedback — closes the post-mortem → next-day prompt loop we already started with `prompt_mutator.py`. Port as "ATLAS mode" flag.
- **P9 — Risk Analysis for Governed LLM Multi-Agent Systems.** [arXiv:2508.05687](https://arxiv.org/abs/2508.05687). Formal risk-budget allocation across agents — replaces our current "everyone gets $5,932" with capability-weighted budget.
- **Kill:** do NOT add more agents until P7 lands. We already proved (PQTF $602K) that 6 agents with smart sizing beat 17 forced into action.

### 4. Calibration

- **P10 — Generalized Venn-Abers on top of every island output.** [arXiv:2502.05676](https://arxiv.org/abs/2502.05676) (Feb 2025, ICML 2025 poster). Finite-sample calibration guarantees, drops onto any classifier. Uses `github.com/ip200/venn-abers` Python impl.
- **P11 — Bias-Corrected Adaptive Conformal Inference (BC-ACI).** [arXiv:2604.13253](https://arxiv.org/abs/2604.13253) (Apr 2026). Standard ACI only shifts the quantile threshold, BC-ACI re-centers via EWMA forecast-bias estimate. Critical for our "NBA TF bleeds even though island Brier is good" pattern — we have a centered-bias problem.
- **P12 — Attention-based online conformal prediction.** [arXiv:2511.15838](https://arxiv.org/abs/2511.15838) (Nov 2025). Adaptively weights historical obs by relevance to test point. Natural fit for our walk-forward backtests.

### 5. Intraday crypto / 24/7 trading

- **P13 — 3-regime vol classifier gate** (low / high / distress). Low-vol regime: NO trades, or Polymarket-only hedging. Distress regime: tighter VaR, reduce position count to 1-2. Anchors: regime-switching frameworks cited above.
- **P14 — Polymarket as crypto hedge surface.** PM-TF proposal already queued (memory `project_polymarket_tf_proposal_apr20`). Recast: use Polymarket binary outcomes to cap crypto tail risk on weekends rather than as a 5th trading floor.

### 6. Feature engineering from unstructured text/video

- **P15 — FinBERT2 as feature extractor.** [arXiv:2506.06335](https://arxiv.org/abs/2506.06335). Pretrained on 32B financial tokens; beats leading LLMs by 9.7–12.3% on classification. Embed POL political text + NBA injury reports → 768-dim feature bank.
- **P16 — LLM-FE evolutionary feature engineering.** [arXiv:2503.14434](https://arxiv.org/abs/2503.14434). Uses LLM as evolutionary optimizer for tabular feature engineering. Wire into our existing GA islands.
- **P17 — FinKario knowledge-graph extraction.** [arXiv:2508.00961](https://arxiv.org/abs/2508.00961). 305K entities, 9.6K triples, event-enhanced. For POL: extract political-event triples from news stream; respect sim_date_cutoff per triple.
- **YouTube-OAuth flag:** P17 and any video-based proposal currently **blocked** until user provides `@bartolipower` YouTube OAuth (transcripts API is blocked on cloud IPs — see memory `project_youtube_manual_ingest_apr20`). Without OAuth we are stuck with manually-ingested videos + Data API v3 metadata.

---

## Kill list (do NOT pursue)

- **More evolution islands beyond current 11 survivors.** 10 "nuls" were eliminated 2026-04-17 for good reason. No Brier delta from count, only from algorithm diversity.
- **Reproducing classical "sentiment → return" papers** (e.g. vanilla FinBERT + logistic). FinBERT2 strictly dominates.
- **Adding more TF agents beyond 17.** We already proved (PQTF 6 agents, $602K) that sizing > count.
- **"LLM picks stocks" benchmarks that report annualized-return only without Brier/log-loss.** [arXiv:2505.07078](https://arxiv.org/abs/2505.07078) discusses long-run underperformance; consistent with our ITF/NBA losses.
- **Stacking deep-neural NBA models on CPU islands.** Violates our "tree-only on CPU" rule #8. Keep deep models on GPU-burst lanes only.
- **Any paper claiming Brier < 0.18 on NBA without a public benchmark split.** Reproduction-failure risk is high; our walk-forward ceiling is near theoretical entropy of NBA outcomes.

---

## Implementation priority (first 2 weeks)

Week 1: P1 (Kelly fix) → P7 (no-trade regime) → P10 (Venn-Abers) → P5 (Kalshi features).
Week 2: P2 (OrionMSP) → P11 (BC-ACI) → P15 (FinBERT2) → P8 (ATLAS Adaptive-OPRO).

Every landing must ship with: (a) backtest on frozen sim-dates, (b) `sim_date_cutoff` assertion, (c) per-agent / per-island Brier + ECE regression gate, (d) one commit per fix (rule #3).

Delegation: all implementation → DR FRANKENSTEIN. Experiments → SWISH (NBA) / LOBBYIST (POL). Audit → INTERNAL AFFAIRS.
