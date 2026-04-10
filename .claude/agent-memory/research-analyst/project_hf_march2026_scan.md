---
name: hf_march2026_scan
description: HuggingFace comprehensive scan March 2026 — top models, datasets, spaces, papers for NBA prediction improvement
type: project
---

## HuggingFace March 2026 Comprehensive Scan Results

Conducted 2026-03-25. Goal: find models, datasets, spaces, and papers to push Brier from 0.2187 to below 0.20.

### Top HF Models Found (tabular classification)

1. **Prior-Labs/tabpfn_2_5** — #1 trending tabular model, 31.6k downloads, updated 2026-03-24
   - 100% win rate vs XGBoost on <=10k samples
   - Non-commercial license required for production
   - pip install tabpfn

2. **soda-inria/tabicl (TabICLv2)** — Feb 2026 release (arXiv 2602.11139)
   - Beats RealTabPFN-2.5 without any tuning on TabArena + TALENT benchmarks
   - Fully MIT open-source — NO commercial licensing issues
   - 10x faster than TabPFN v2
   - Scales to million rows on <50GB GPU
   - pip install tabicl
   - **BEST OPTION** for our HF Space integration

3. **SAP/sap-rpt-1-oss** (ConTextTab, NeurIPS 2025) — 16.3k downloads
   - Semantic-aware tabular ICL
   - Requires 80GB GPU — impractical for our CPU HF Spaces

### Top HF Datasets Found (sports/basketball)

1. **Emlembow/march-madness-2026-data** — March 2026 NCAA tournament data
   - 13,308 player-season records, 15 seasons 2011-2026, 55 columns
   - 917 tournament game records + 2026 bracket structure
   - Useful for feature engineering inspiration and cross-sport calibration

2. **dcayton/nba_tracking_data_15_16** — NBA SportVU tracking data 2015-16
   - Raw spatial tracking data — useful to validate tracking feature approach

3. **yuvalyam007/sport_betting_analysis** — Sports betting behavioral dataset
   - Columns: odds, stake, gain, GGR, is_win, sport category
   - Football most common, then Tennis, then Basketball

### New Papers from HF — March 2026 (updated 2026-03-25 second scan)

- **arXiv 2603.09151** "Deep Tabular Research via Continual Experience-Driven Execution" (Tencent, Mar 2026)
  - Agentic framework for multi-table tabular reasoning — relevant for cross-table feature discovery
- **arXiv 2603.10916** "NCAA Bracket Prediction via Combinatorial Fusion Analysis" (Mar 11, 2026)
  - CFA rank combination beats all 10 public ranking systems: 74.60% vs 73.02%
  - KEY INSIGHT: Rank-based ensemble fusion outperforms probability averaging — try this for our 6-island blend
- **arXiv 2603.05671** "Graph-based Encoding for NBA Salary Prediction" (Mar 5, 2026, Su/Grimsman/Archibald)
  - Knowledge graph of player-team-opponent relationships + embeddings added to tabular features
  - Transfer potential: graph embeddings as game prediction features
- **arXiv 2602.22777** "KMLP: KAN + gMLP for Web-Scale Tabular Data" (Feb 2026, WWW 2026)
  - KAN front-end learns per-feature nonlinear activations; code not yet released
- **arXiv 2512.08591** "Long-Sequence LSTM NBA Prediction" (Dec 2025)
  - 8-season LSTM sequences capture dynasty/coaching effects; no Brier score but 72.35% acc
  - Insight: add 2-3 year rolling features (franchise momentum) to engine.py

### New Models Trending on HF (March 2026)

- **Qwen3.5 family** (Feb 2026) — #1 trending. 0.8B to 397B, Apache 2.0, tool calling, 201 languages
  - Use Qwen3.5-9B as LLM-FE proposer (free, replaces Claude API calls)
- **DeepSeek-V3.2** (685B, MIT, Feb 2026) — surpasses GPT-5 on math/coding benchmarks
- **Llama 4 Scout/Maverick** (Apr 2025) — 17B active MoE, 10M context, GGUF available
- **Gemma 3n** (2026) — E2B/E4B effective params, on-device, multimodal (audio/video/image/text)
- **Qwen3-Coder-Next** (Feb 2026) — 80B/3B active, 256K context, best for coding agents
- **OpenForecaster-8B** (`nikhilchandak/OpenForecaster-8B`) — Qwen3-8B post-trained on Brier score reward; trained explicitly for calibrated forecasting

### TabICLv2 Latest Release Info (March 2026)

- v2.0.3 released March 2, 2026 (latest stable)
- v2.0.2 (Feb 23): Added TabICLForecaster for time series
- v2.0.0 (Feb 12): Major TabICLv2 launch
- Best checkpoint: tabicl-classifier-v1.1-0506.ckpt

### New Datasets (March 2026)

- **yulupan/BASKET** (CVPR 2025): 4,477 hours NBA+21 leagues video, 32,232 players, 20 fine-grained skill ratings 0-4; could provide player skill embeddings
- **hamzas/nba-games**: NBA historical games supplement

### Current State of Tabular ML (2026)

- TabArena benchmark: TabICLv2 > RealTabPFN-2.5 > AutoGluon 4h ensemble
- For datasets <10k rows: TabICLv2 or TabPFN-2.5 best
- For datasets >100k rows: XGBoost/CatBoost still competitive
- Our dataset (~9k games): squarely in TabICLv2/TabPFN-2.5 sweet spot
- Commercial licensing: TabICLv2 is MIT (use freely), TabPFN-2.5 requires enterprise license

### Competitive Intelligence (March 2026)

- NO competing NBA game prediction spaces with validated Brier scores exist on HF
- Our 6-island evolutionary system is unique on the platform
- Most "sports betting" spaces are static HTML, not ML models
- ThinkingRock/nba: GPT-style player token model, no reported Brier score

**Why:** HF scan results to accelerate Brier from 0.2187 toward 0.20 target
**How to apply:** (1) TabICLv2 as new HF island; (2) Rank-based ensemble fusion from CFA; (3) Multi-year lookback features; (4) Qwen3.5-9B for LLM-FE pipeline. Full findings at /home/termius/mon-ipad/data/hf-scan-march2026.md
