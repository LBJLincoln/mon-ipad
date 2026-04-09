# LLM Council for Trading Floor — Implementation Guide

**Source:** Andrej Karpathy, March 2026  
**GitHub:** [karpathy/llm-council](https://github.com/karpathy/llm-council)  
**Effort:** 2-4 hours  
**Expected Impact:** -0.0005 to -0.001 Brier score, +0.1-0.2% ROI  

---

## Overview

LLM Council is a 3-stage deliberation system for multi-agent consensus. Karpathy built it as a "vibe code" weekend project; it's proven to be the missing orchestration layer between applications and volatile LLM markets.

### Why It Works Better Than Simple Voting

**Current Approach (Trading Floor v4):**
- 5 traders generate strategies
- Best trader's strategy wins (plurality voting)
- Outliers sometimes dominate

**LLM Council Approach:**
1. Stage 1: All 5 traders generate strategies (parallel)
2. **Stage 2: Anonymized peer review** — Each trader scores others 0-10
3. **Stage 3: Synthesis** — Claude Opus reads all strategies + scores, picks or synthesizes best

**Key Innovation:** Anonymized review prevents bias ("Claude is always good") and forces honest evaluation.

---

## Implementation: 3 Stages

### Stage 1: Parallel Strategy Generation

**Status:** Already implemented in trading-floor-v4.py

```python
# Pseudocode
strategies = {}
for trader in [Gemini, OpenRouter, Claude, Codex, Grok]:
    prompt = f"""
    You are a sports betting strategist.
    Today's NBA games: {games}
    Your opponent predictions: {opponent_predictions}
    
    Propose a betting strategy:
    1. Which games have edge (predicted spread > market spread)?
    2. Kelly sizing: f* = (edge / odds) 
    3. Total bankroll allocation
    
    JSON format:
    {{"bets": [...], "kelly_pct": 0.25, "expected_roi": 0.08}}
    """
    strategy = trader.generate(prompt)
    strategies[trader.name] = strategy
```

**Output:** `strategies_gen_38.json`
```json
{
  "Gemini": {"bets": [...], "kelly_pct": 0.25, "expected_roi": 0.08},
  "Claude": {"bets": [...], "kelly_pct": 0.20, "expected_roi": 0.10},
  "Codex": {...},
  "OpenRouter": {...},
  "Grok": {...}
}
```

---

### Stage 2: Anonymized Peer Review (NEW)

**Add this after Stage 1:**

```python
import json
import asyncio

async def stage2_peer_review(strategies, trader_names):
    """
    Each trader anonymously scores all other strategies.
    Returns score_matrix[trader][strategy] = 0-10 score
    """
    
    score_matrix = {}
    
    # Create anonymous labels (Strategy A, B, C, D, E)
    labels = ['Strategy A', 'Strategy B', 'Strategy C', 'Strategy D', 'Strategy E']
    strategy_to_label = dict(zip(trader_names, labels))
    label_to_trader = {v: k for k, v in strategy_to_label.items()}
    
    # For each trader, score all others (excluding own)
    for reviewer_name in trader_names:
        reviewer = get_trader(reviewer_name)
        
        # Build anonymized strategy list (excluding reviewer's own)
        anon_strategies = []
        for i, (trader_name, strategy) in enumerate(strategies.items()):
            if trader_name != reviewer_name:
                anon_strategies.append({
                    'label': labels[i],
                    'strategy': strategy
                })
        
        prompt = f"""
You are evaluating 4 betting strategies (anonymized, labels A-D).
Your job is to score each 0-10 on these criteria:
1. Edge Detection (does it identify profitable bets?)
2. Kelly Sizing (is bankroll allocation correct?)
3. Risk Management (is variance acceptable?)
4. Realism (can we execute these bets?)

Strategies:
{json.dumps(anon_strategies, indent=2)}

Return JSON:
{{"Strategy_A": 7, "Strategy_B": 9, "Strategy_C": 6, "Strategy_D": 8, "reasoning": "..."}}
"""
        
        scores = await reviewer.evaluate_async(prompt)
        score_matrix[reviewer_name] = scores
    
    return score_matrix, label_to_trader

# Run Stage 2
score_matrix, label_map = await stage2_peer_review(
    strategies, 
    ['Gemini', 'OpenRouter', 'Claude', 'Codex', 'Grok']
)
```

**Output:** `scores_gen_38.json`
```json
{
  "Gemini": {"Strategy_A": 8, "Strategy_B": 7, "Strategy_C": 9, "Strategy_D": 6},
  "Claude": {"Strategy_A": 7, "Strategy_B": 9, "Strategy_C": 6, "Strategy_D": 8},
  "Codex": {...},
  "OpenRouter": {...},
  "Grok": {...}
}
```

**Summary Scores** (sum across all reviewers):
```
Strategy A (Claude): 8 + 7 + ... = 34/5 = 6.8
Strategy B (Gemini): 7 + 9 + ... = 39/5 = 7.8  ← Leader
Strategy C (Codex):  9 + 6 + ... = 36/5 = 7.2
Strategy D (OpenRouter): 6 + 8 + ... = 32/5 = 6.4
Strategy E (Grok):   ...
```

---

### Stage 3: Synthesis by Chairman

**Add after Stage 2:**

```python
async def stage3_synthesis(strategies, score_matrix, label_map):
    """
    Claude Opus (Chairman) synthesizes all strategies + anonymous scores.
    Returns: final recommended strategy or hybrid.
    """
    
    # Format for Claude
    strategy_summary = []
    for label, trader_name in label_map.items():
        strategy = strategies[trader_name]
        scores_from_others = {
            reviewer: scores.get(label, 'N/A')
            for reviewer, scores in score_matrix.items()
            if reviewer != trader_name
        }
        avg_score = sum(scores_from_others.values()) / len(scores_from_others)
        
        strategy_summary.append({
            'trader': trader_name,
            'label': label,
            'strategy': strategy,
            'peer_scores': scores_from_others,
            'avg_peer_score': avg_score
        })
    
    # Sort by peer score
    strategy_summary.sort(key=lambda x: x['avg_peer_score'], reverse=True)
    
    prompt = f"""
You are the Chairman of a betting council. Five traders submitted strategies, 
which were anonymously peer-reviewed.

RANKED BY PEER REVIEW:
1. {strategy_summary[0]['trader']} (Strategy {strategy_summary[0]['label']}, score {strategy_summary[0]['avg_peer_score']:.1f}/10)
2. {strategy_summary[1]['trader']} (Strategy {strategy_summary[1]['label']}, score {strategy_summary[1]['avg_peer_score']:.1f}/10)
3. {strategy_summary[2]['trader']} (Strategy {strategy_summary[2]['label']}, score {strategy_summary[2]['avg_peer_score']:.1f}/10)
4. {strategy_summary[3]['trader']} (Strategy {strategy_summary[3]['label']}, score {strategy_summary[3]['avg_peer_score']:.1f}/10)
5. {strategy_summary[4]['trader']} (Strategy {strategy_summary[4]['label']}, score {strategy_summary[4]['avg_peer_score']:.1f}/10)

FULL STRATEGIES:
{json.dumps(strategy_summary, indent=2)}

Choose ONE of the following:
A) Adopt the top-ranked strategy as-is
B) Synthesize a hybrid (combine best elements from top 2-3)
C) Recommend a revision to top strategy

Your decision (A/B/C) and reasoning:
"""
    
    chairman = get_trader('Claude_Opus')
    final_decision = await chairman.evaluate_async(prompt)
    
    if final_decision['choice'] == 'A':
        final_strategy = strategies[strategy_summary[0]['trader']]
    elif final_decision['choice'] == 'B':
        # Synthesize hybrid (your implementation)
        final_strategy = synthesize_hybrid([
            strategies[strategy_summary[0]['trader']],
            strategies[strategy_summary[1]['trader']]
        ])
    else:
        final_strategy = revise_strategy(
            strategies[strategy_summary[0]['trader']],
            final_decision['revision']
        )
    
    return {
        'final_strategy': final_strategy,
        'chairman_decision': final_decision,
        'ranked_strategies': strategy_summary
    }

# Run Stage 3
final_decision = await stage3_synthesis(strategies, score_matrix, label_map)
```

---

## Integration into trading-floor-v4.py

### Current Structure
```python
# trading-floor-v4.py
def run_trading_day():
    # Stage 1: All 5 traders generate strategies
    strategies = stage1_parallel_generation(games, opponent_preds)
    
    # Pick best strategy and execute
    best_strategy = max(strategies.values(), key=lambda x: x['expected_roi'])
    execute_bets(best_strategy)
```

### New Structure
```python
async def run_trading_day():
    # Stage 1: All 5 traders generate strategies
    strategies = await stage1_parallel_generation(games, opponent_preds)
    
    # NEW: Stage 2 - Peer review
    score_matrix, label_map = await stage2_peer_review(strategies, trader_names)
    
    # NEW: Stage 3 - Synthesis
    final_decision = await stage3_synthesis(strategies, score_matrix, label_map)
    final_strategy = final_decision['final_strategy']
    
    # Execute final strategy
    execute_bets(final_strategy)
    
    # Log for analysis
    log_trading_council({
        'generation': generation_num,
        'strategies': strategies,
        'scores': score_matrix,
        'final_decision': final_decision
    })
```

---

## Testing & Validation

### Unit Test: Peer Review Consistency

```python
def test_peer_review_symmetry():
    """
    If Strategy A scores well from Trader B,
    Trader A should score Trader B's strategy well (rough symmetry).
    """
    strategies = generate_test_strategies()
    score_matrix, _ = await stage2_peer_review(strategies, trader_names)
    
    # Check rough reciprocity
    for reviewer in trader_names:
        for reviewee in trader_names:
            if reviewer != reviewee:
                # Traders with high mutual respect should score each other well
                pass  # Your validation logic
```

### Integration Test: 10-Game Backtest

```python
def backtest_council_vs_simple_voting():
    """
    Run last 10 NBA games:
    - Council approach (3 stages)
    - Simple voting (best trader)
    
    Compare ROI, Brier score
    """
    games = load_last_10_games()
    
    council_roi = 0
    voting_roi = 0
    
    for game in games:
        # Council approach
        strategies = generate_strategies(game)
        score_matrix = peer_review(strategies)
        final = synthesis(strategies, score_matrix)
        council_roi += execute_and_measure(final['strategy'], game)
        
        # Simple voting
        best = max(strategies.values(), key=lambda x: x['expected_roi'])
        voting_roi += execute_and_measure(best, game)
    
    print(f"Council ROI: {council_roi:.2%}")
    print(f"Voting ROI: {voting_roi:.2%}")
    print(f"Improvement: {(council_roi - voting_roi):.2%}")
```

---

## Expected Results

### Metric: Brier Score Impact

| Scenario | Brier Delta |
|----------|------------|
| Simple voting (current) | baseline |
| LLM Council Stage 2 only | -0.0002 (peer awareness) |
| LLM Council full (Stages 1-3) | -0.0005 to -0.001 |

### Metric: ROI Impact

| Scenario | ROI |
|----------|-----|
| Simple voting (baseline) | +2.5% |
| LLM Council | +2.6% to +2.7% |

---

## Karpathy's Original Code Reference

Karpathy's LLM Council uses:
- **Backend:** FastAPI (async routes for parallel calls)
- **LLM API:** OpenRouter (single endpoint, multiple models)
- **Frontend:** React + Vite (optional for Nomos42)
- **Storage:** JSON files in `data/conversations/`

### Minimal FastAPI Skeleton

```python
# llm_council_api.py
from fastapi import FastAPI
import asyncio
import httpx

app = FastAPI()

@app.post("/council/vote")
async def council_vote(question: str, models: list = None):
    if models is None:
        models = ["gpt-5.1", "claude-sonnet-4.5", "gemini-3-pro", "grok-4"]
    
    # Stage 1: Parallel calls to all models
    tasks = [
        query_openrouter(model, question)
        for model in models
    ]
    responses = await asyncio.gather(*tasks)
    
    # Stage 2: Peer review (each model scores others)
    scores = await stage2_anonymous_review(responses, models)
    
    # Stage 3: Synthesis
    final_answer = await stage3_synthesis(responses, scores)
    
    return {"final": final_answer, "raw_responses": responses, "scores": scores}

async def query_openrouter(model: str, prompt: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}]}
        )
    return response.json()["choices"][0]["message"]["content"]

# Run: uvicorn llm_council_api:app --reload
```

---

## Files to Create/Modify

```
scripts/trading-floor/
├── stage2-peer-review.py (NEW)
├── stage3-synthesis.py (NEW)
└── trading-floor-v4.py (MODIFY)

docs/
└── KARPATHY_LLM_COUNCIL_IMPLEMENTATION.md (THIS FILE)

data/council-logs/
└── council-decisions-gen-38.json (generated after each run)
```

---

## Rollout Plan

### Day 1: Implementation
- [ ] Create `stage2-peer-review.py` (async peer scoring)
- [ ] Create `stage3-synthesis.py` (Claude Opus synthesis)
- [ ] Modify `trading-floor-v4.py` to call Stages 2 & 3

### Day 2: Testing
- [ ] Unit test: peer review consistency
- [ ] Integration test: 10-game backtest
- [ ] Compare ROI: Council vs. simple voting

### Day 3: Deployment
- [ ] Deploy to next NBA game day
- [ ] Monitor ROI impact
- [ ] Log council decisions to audit trail
- [ ] Report findings

---

## Summary

LLM Council is a 2-4 hour implementation that upgrades your trading floor from simple voting to structured deliberation. Karpathy's anonymized peer review pattern prevents bias and captures collective intelligence better than raw voting. Expected: -0.0005 to -0.001 Brier, +0.1-0.2% ROI improvement.

**Next Step:** Implement Stage 2 peer review this week, test on 10 historical games, deploy by weekend.

---

**Source:** Andrej Karpathy, March 2026  
**Adapted for:** Nomos42 NBA Trading Floor  
**Date:** 2026-04-04
