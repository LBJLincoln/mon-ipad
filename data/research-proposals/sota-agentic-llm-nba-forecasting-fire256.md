# Agentic LLMs for Real-Time NBA Forecasting and Market Betting (fire-256 EVEN WebSearch)

## Source
- Title: "Playing the Odds: Agentic LLMs for Real-Time NBA Forecasting and Market Betting"
- Published: April 2026
- URL: https://www.researchgate.net/publication/403692431_Playing_the_Odds_Agentic_LLMs_for_Real-Time_NBA_Forecasting_and_Market_Betting
- Note: ResearchGate access returned 403; no arXiv ID found yet. Found via fire-256 EVEN WebSearch.

## Key Findings
- Unified framework using LLM agents for NBA probabilistic forecasting and decision-making
- Specialized information retrieval agents fetch real-time data (injuries, lineups, betting lines)
- Role-based LLM predictors (analyst, quant, risk manager) produce probabilistic game outcomes
- Forecasts aggregated into final probabilities via ensemble coordination
- Fractional Kelly criterion strategy for bankroll management and bet sizing
- Combines ML predictions with market efficiency theory

## Applications to Nomos42

### Application 1: LLM Meta-Ensemble Layer
- Add LLM-based meta-ensemble on top of our GA Pareto front models
- Role-based LLM predictors aggregate the top-5 Pareto models via weighted consensus
- Expected: 0.001-0.002 Brier improvement from better ensemble coordination
- Integration point: `/api/export` → LLM aggregation layer → final prediction

### Application 2: Fractional Kelly Strategy for Trading Floor
- Replace fixed bet sizing in nba-llm-trading-floor with fractional Kelly
- Kelly fraction f = (bp - q) / b where b = odds, p = our probability, q = 1-p
- Fractional Kelly (25%-50%) reduces variance while maintaining positive EV
- Expected: 10-20% ROI improvement with lower drawdown

### Application 3: Axelrod + LLM Coordination (Synergy with fire-218)
- Combine this paper's role-based LLM predictors with our Axelrod Mech A/B/C framework
- Sacrificial role (Mech B) maps naturally to Kelly's concept of risking limited capital
- Post-mortem log (Mech C) feeds back into LLM retrieval agents
- BLOCKED: do_not_push_hf_space_yet (Rule #7)

### Application 4: Real-Time Data Retrieval Agents
- Implement specialized NBA information retrieval agents:
  - Injury report agent (scrapes NBA injury lists)
  - Line movement agent (tracks betting line shifts)
  - Team news agent (roster changes, coach quotes)
- These agents augment our feature engineering pipeline

### Application 5: Port to Political Alpha
- Political equivalent: role-based LLM predictors for election probability
- Information retrieval: polling aggregation, fundraising data, news sentiment
- Kelly strategy for political prediction market sizing

## Libraries
- anthropic SDK (Claude API for LLM predictors)
- scipy.optimize (fractional Kelly criterion)
- requests / BeautifulSoup (NBA data retrieval agents)

## Expected Improvement
- Brier: 0.001-0.002 improvement from LLM meta-ensemble
- ROI: 10-20% improvement from Kelly strategy
- Cross-project: political forecasting enhancement

## Work Queue
- ID: vm-research-agentic-llm-nba-forecasting-fire256
- Priority: 116
- Owner: local-vm
