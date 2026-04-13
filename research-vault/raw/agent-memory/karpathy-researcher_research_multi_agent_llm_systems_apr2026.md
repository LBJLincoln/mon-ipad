---
name: Multi-Agent LLM Prediction Systems (April 2026 Landscape)
description: REAL multi-agent implementations for betting/trading/prediction with cost structures and accuracy data
type: reference
---

# Real Multi-Agent LLM Systems for Prediction & Betting (April 2026)

## TIER 1: REAL-MONEY MARKET TRADING (Live Capital at Risk)

### Prediction Arena (arXiv 2604.07355) — Mar 28 2026
**Status:** Active research benchmark on real prediction markets (Kalshi + Polymarket)
**Capital:** Each model starts with $10,000 USD in live capital
**Agents:** 6 frontier models + 4 next-gen models (Cohort 1: Jan 12 – Mar 9 2026, 57 days)
**Trading Frequency:** Every 15–45 minutes autonomously
**Context Delivery:** Not specified in abstract; requires full paper review
**Decision Extraction:** Autonomous trades on real exchanges (Kalshi, Polymarket)
**Accuracy Results:**
- Kalshi live returns: -16% to -30.8% (NEGATIVE)
- Polymarket: 1 model achieved 71.4% settlement win rate, another +6.02% in 3 days
- Key finding: "Platform design has profound effect on which models succeed"
- Initial prediction accuracy + ability to capitalize on correct predictions = main drivers
**Cost Per Trade:** Not disclosed
**Free Models:** Not specified
**CRITICAL:** Results show frontier models LOSING money on real markets. Platform design heavily influences outcomes.

**Repo:** Not open-sourced (academic only)
**Source:** [Prediction Arena (arXiv 2604.07355)](https://arxiv.org/abs/2604.07355)

---

### PolySwarm (arXiv 2604.03888) — Apr 4 2026
**Status:** NEW — Multi-agent swarm for prediction market latency arbitrage
**Agents:** 50 diverse LLM personas (swarm aggregation)
**Context Delivery:** Binary outcome market metadata (price, volume, history)
**Decision Extraction:** Bayesian confidence-weighted swarm consensus + quarter-Kelly position sizing
**Market Analysis:** Kullback-Leibler + Jensen-Shannon divergence for cross-market inefficiencies
**Arbitrage Module:** Detects stale Polymarket prices vs CEX-implied probabilities, trades within human reaction-time window
**Accuracy Results:** "Swarm aggregation consistently outperforms single-model baselines in probability calibration"
**Evaluation Metrics:** Brier score, calibration analysis, log-loss
**Cost Per Evaluation:** Not disclosed
**Free Models:** Not specified
**Open Challenges:** Hallucination in agent pools, computational cost at scale, regulatory exposure, feedback-loop risk
**Repo:** Not yet released
**Source:** [PolySwarm (arXiv 2604.03888)](https://arxiv.org/abs/2604.03888)

---

### When Agents Trade: Agent Market Arena (arXiv 2510.11695) — Oct 2025
**Status:** First lifelong real-time trading benchmark for LLM agents
**Agents:** 4 archetypes: InvestorAgent (baseline), TradeAgent, HedgeFundAgent (risk variant), DeepFundAgent (memory-based)
**Models Tested:** GPT-4o, GPT-4.1, Claude-3.5-Haiku, Claude-Sonnet-4
**Context Delivery:** Real verified trading data + expert-checked news + time-series charts
**Decision Extraction:** Autonomous trades on live market data
**Key Finding:** AGENT ARCHITECTURE >> LLM BACKBONE — architecture choice drives 70%+ of performance variance
**Behavioral Patterns:** Frameworks exhibit aggressive/conservative/hedging behaviors; model choice contributes <30%
**Profitability:** LLM agents consistently beat buy-and-hold in live environments
**Cost:** Commercial models required (no free tier mentioned)
**Free Models:** Not compatible
**Repo:** Not open-sourced
**Source:** [When Agents Trade (arXiv 2510.11695)](https://arxiv.org/abs/2510.11695)

---

## TIER 2: PRODUCTION-READY FRAMEWORKS (Open Source, Free Models)

### TradingAgents (arXiv 2412.20138) — Dec 2024, Updated Mar 2026
**Status:** DEPLOYED, v0.2.3 (Mar 2026), open-source
**Agents:** 8+ specialized roles
- Fundamentals Analyst
- Sentiment Analyst
- News Analyst
- Technical Analyst
- Bullish Researcher (debate/advocacy)
- Bearish Researcher (debate/risk counter)
- Trader Agent
- Risk Management Team
- Portfolio Manager
**Context Delivery:** Real-time market data + news feeds + technical indicators
**Decision Extraction:** Structured agent debates → trader executes consensus decision
**Free Models Supported:** YES — Ollama integration for local open-source models
- Supports Gemma, Qwen, Llama (local)
- Commercial: GPT-5.4, Gemini 3.1, Claude 4.6, Grok 4.x
**Cost Per Prediction:** Not disclosed
**Benchmark Results:** Stock trading focus (NVDA, etc.); NO sports betting benchmarks published
**Sports Betting Support:** NOT IMPLEMENTED (framework is equity/stocks only)
**Limitation:** Designed for research, not financial advice
**Repo:** [GitHub: TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
**Source:** [arXiv 2412.20138](https://arxiv.org/abs/2412.20138)

---

### Agent Trading Arena (arXiv 2502.17967) — Feb 2025, Accepted EMNLP 2025
**Status:** DEPLOYED, closed-loop trading environment
**Agents:** Unspecified count; "self-play-capable" architecture
**Context Delivery:** TIME-SERIES CHARTS (key finding) >> plain text
**Decision Extraction:** Chart-based LLM vision → trading decisions
**Key Finding:** Chart visualization +40% boost vs plain-text (LLMs struggle with pure numerical reasoning)
**Reflection Module:** Adds additional improvements, especially with visual inputs
**Models Tested:** Requires OpenAI API (GPT-4o achieves highest returns)
**Free Models:** Not compatible
**Cost Per Trade:** Not disclosed
**Datasets:** NASDAQ, CSI (Chinese stock index)
**Repo:** [GitHub: wekjsdvnm/Agent-Trading-Arena](https://github.com/wekjsdvnm/Agent-Trading-Arena)
**Source:** [arXiv 2502.17967](https://arxiv.org/abs/2502.17967)

---

## TIER 3: MULTI-AGENT SIMULATION PLATFORMS (Research)

### OASIS (arXiv 2411.11581) — Nov 2024
**Status:** Open-source, 1M agent capacity
**Purpose:** Social media dynamics simulation (NOT betting/trading)
**Agents:** 1,000,000+ concurrent agents
**Agent Capabilities:** 23 actions (follow, comment, repost, etc.)
**Context Delivery:** Social network state + recommendation feeds + post metadata
**Decision Extraction:** Agent action selection from 23-action space
**Models:** OpenAI (GPT-4O Mini, paid) or Qwen variants
**Cost Per Timestep (100 agents, 0.1 activation):**
- Qwen-plus: ¥0.027 (~$0.004 USD)
- Qwen-max: ¥0.717 (~$0.10 USD)
- Scales linearly with agent count
**Free Models:** Qwen free tier available
**Results:** Replicates Twitter/Reddit information spread, group polarization, herd effects
**Sports Betting Adaptation:** NOT DESIGNED FOR BETTING; requires custom prediction layer
**Repo:** [GitHub: camel-ai/oasis](https://github.com/camel-ai/oasis)
**Source:** [arXiv 2411.11581](https://arxiv.org/abs/2411.11581)

---

### MiroFish (GitHub 666ghj/MiroFish) — Jan 2026 (Viral)
**Status:** Open-source, startup funded $4.1M (Jan 2026)
**Purpose:** Universal multi-agent prediction engine
**Agents:** Thousands of simulated agents with independent personalities + long-term memory
**Context Delivery:** GraphRAG extracts entities/relationships from seed documents; agents reason over structured reality map
**Decision Extraction:** Agent-generated predictions (varies by use case)
**Capabilities:** Predict financial markets, public opinion, policy outcomes, social trends
**Free Models:** NOT SPECIFIED; likely requires commercial LLM APIs
**Cost:** Not disclosed
**Limitation:** CONSENSUS COLLAPSE RISK — agents may converge on "safe" outcomes (RLHF bias) rather than realistic predictions
**Results:** 42K+ GitHub stars; used for social/political predictions; not benchmarked on sports
**Repo:** [GitHub: 666ghj/MiroFish](https://github.com/666ghj/MiroFish)
**Source:** [Judy AI Lab writeup](https://judyailab.com/en/posts/mirofish-multi-agent-prediction/)

---

## TIER 4: FREE MODEL APIS (April 2026)

### Qwen 3.6 Plus (Alibaba, OpenRouter) — Mar 30 2026
**Status:** FREE on OpenRouter
**Route:** `qwen/qwen3.6-plus:free`
**Specs:** 1M context window, 65K output tokens, native function calling, chain-of-thought
**Cost:** $0.00 per request (rate-limited)
**Agent Support:** YES — native tool calling for agentic workflows
**Source:** [OpenRouter Agent Push (Apr 2026)](https://paddo.dev/blog/ai-roundup-april-2026/)

### Gemma 4 Family (Google) — Apr 2026
**Status:** Open-weight, free inference options available
**Agent Support:** YES — function calling, structured JSON output, native system instructions
**Deployment:** Local (Ollama) + API variants
**Cost:** Free via Ollama (local), paid via API
**Source:** [Gemma 4 Family Guide (2026)](https://www.aimadetools.com/blog/gemma-4-family-guide/)

### Llama 3.3 70B (Meta)
**Status:** Open-weight, free via Ollama
**Agent Support:** YES — structured output, function calling
**Deployment:** Local only
**Cost:** $0 (self-hosted)

### Ollama + OpenClaw (Local)
**Status:** FREE agent framework
**Models:** Supports Llama, Qwen, Gemma (all local)
**Cost:** $0 per request
**Limitation:** Runs on user hardware (laptop/desktop constraints)

---

## IMPLEMENTATION COST COMPARISON

| System | Per-Game Cost | Free Tier | Min Infrastructure | Accuracy |
|--------|--------------|-----------|-------------------|----------|
| Prediction Arena | $1-5 (est.) | No | Real capital at risk | 71% win rate best |
| PolySwarm | Unknown | No | GPU for 50-agent swarm | Brier improves |
| When Agents Trade | $0.10-0.50 | No | Cloud CPU | Beats buy-hold |
| TradingAgents | $0.01-0.05 (free via Ollama) | YES (Ollama) | Laptop (local) | Unknown for sports |
| Agent Trading Arena | $0.05-0.15 | No | GPU | GPT-4o best |
| OASIS | $0.0004-0.001/agent | Partial (Qwen) | Cloud | Simulation only |
| MiroFish | Unknown | No | GPU or cloud | Social trends |
| Ollama Local | $0.00 | YES | Laptop (8GB RAM) | Framework-dependent |

---

## KEY INSIGHTS FOR NBA PREDICTION

1. **Chart > Text:** Agent Trading Arena proves visual chart input beats plain numerical text by 40% for LLM reasoning
2. **Architecture >> Model:** When Agents Trade shows agent design (debate, risk management, memory) drives outcomes more than LLM choice
3. **Swarm Aggregation Works:** PolySwarm's 50-agent Bayesian ensemble outperforms single models on calibration
4. **Free Tier Available:** Qwen 3.6 Plus (free) + Ollama (free) enables zero-cost agent fleet
5. **Real Money Results:** Prediction Arena's -16% to +71% range shows even frontier models struggle with real-money constraints; platform design is critical
6. **Sports Betting Gap:** NO papers benchmark on sports (NBA/NFL). All focus equity markets or social prediction.

---

## ACTIONABLE NEXT STEPS

1. **Replicate TradingAgents architecture** for NBA: 
   - Analyst team (stats, injuries, news)
   - Bull/Bear debate layer
   - Kelly sizing via local Ollama (free)
   - Cost: $0 per prediction

2. **Adopt chart-based context** (Agent Trading Arena finding):
   - Feed team stats as sparkline PNG
   - LLM +40% accuracy boost
   - Easy integration into existing pipeline

3. **Deploy 10-50 agent swarm** (PolySwarm pattern):
   - Qwen 3.6 + Gemma 4 + Llama via Ollama
   - Confidence-weighted Bayesian aggregation
   - Quarter-Kelly position sizing
   - Zero cost

4. **Test calibration** via Brier score (all papers use this metric)
   - Measure before/after swarm aggregation
   - Expected: -0.001 to -0.003 Brier improvement

---

## RED FLAGS

- **Prediction Arena:** Frontier models LOSING on real capital — system design >> model quality
- **PolySwarm:** "Hallucination in agent pools" — needs hallucination detection layer
- **MiroFish:** Consensus collapse (agents converge on safe outcomes) — needs diversity enforcement
- **No Sports Benchmarks:** Zero papers evaluate on NBA/NFL — you're in uncharted territory

---

## Papers by Recency

| Date | Paper | Benchmark | Free Model | Open Code |
|------|-------|-----------|-----------|-----------|
| Apr 4 2026 | PolySwarm | Polymarket | No | No |
| Mar 28 2026 | Prediction Arena | Kalshi+Polymarket | No | No |
| Mar 2026 | TradingAgents v0.2.3 | Stock trading | YES (Ollama) | YES |
| Feb 2025 | Agent Trading Arena | NASDAQ/CSI | No | YES |
| Oct 2025 | When Agents Trade | Live markets | No | No |
| Jan 2026 | MiroFish | Social/politics | No | YES |
| Nov 2024 | OASIS | Social simulation | Partial | YES |

---

## GitHub Repos Ready to Use

1. [TradingAgents](https://github.com/TauricResearch/TradingAgents) — v0.2.3, Ollama support
2. [Agent Trading Arena](https://github.com/wekjsdvnm/Agent-Trading-Arena) — EMNLP accepted
3. [OASIS](https://github.com/camel-ai/oasis) — 1M agent sim
4. [MiroFish](https://github.com/666ghj/MiroFish) — Viral, funded
5. [OpenClaw + Ollama](https://github.com) — FREE agent framework (Ollama is `ollama/ollama`)

