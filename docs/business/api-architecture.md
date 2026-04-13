# Nomos42 API Architecture — SaaS Design v1.0

> API-First Design | Updated: 2026-04-03 | Forge v19

---

## Overview

Nomos42 monetizes NBA prediction intelligence through a tiered API subscription model. Every product feature is exposed as an endpoint; the dashboard, Telegram bot, and mobile app are all consumers of the same API. This document defines the full architecture, endpoint contracts, rate limits, and marketplace mechanics.

---

## Tier Summary

| Tier | Price | Target User | Key Unlock |
|------|-------|-------------|------------|
| **Free** | $0/mo | Fans, trialists | 3 predictions/day, basic stats |
| **Scout** | $19/mo | Casual bettors | All daily predictions, basic odds, email alerts |
| **Edge** | $49/mo | Serious bettors | Real-time predictions, Kelly sizing, Telegram, 50+ categories |
| **Whale** | $149/mo | Syndicates, funds | Raw model outputs, custom features, agent marketplace, departments API |

Annual billing: 20% discount (Scout $182/yr, Edge $470/yr, Whale $1,430/yr).

---

## Authentication

All endpoints require an `Authorization: Bearer <api_key>` header. API keys are issued on subscription and scoped to tier capabilities. Free tier keys are rate-limited by IP in addition to key-level limits.

```
Header: Authorization: Bearer nom42_live_<32-char-hex>
```

Keys never expire unless rotated. Rotation is instant via dashboard. Webhook signing uses HMAC-SHA256 with a separate `signing_secret`.

---

## Endpoint Reference

### POST /api/auth/token

Exchange credentials for a short-lived JWT (15 min) for browser-based flows.

**Request:**
```json
{
  "api_key": "nom42_live_abc123..."
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "expires_in": 900,
  "tier": "edge",
  "rate_limits": {
    "predictions_per_day": -1,
    "requests_per_minute": 60
  }
}
```

---

### GET /api/predictions

Today's game predictions. The core product.

**Auth:** All tiers. Free limited to 3 games/day.

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `date` | ISO date | today | Game date (Scout+ only, historical) |
| `min_edge` | float | 0.03 | Minimum model edge (Edge+: 0.00 allowed) |
| `model` | string | `ensemble` | `tabicl`, `catboost`, `xgboost`, `lightgbm`, `extra_trees`, `ensemble` |
| `include_kelly` | bool | false | Include Kelly sizing (Edge+ only) |
| `format` | string | `json` | `json`, `csv` |

**Response (Edge tier):**
```json
{
  "date": "2026-04-03",
  "generated_at": "2026-04-03T10:00:00Z",
  "model_version": "tabicl_ensemble_v3.1",
  "brier_score": 0.21570,
  "predictions": [
    {
      "game_id": "nba_20260403_BOS_MIA",
      "home_team": "BOS",
      "away_team": "MIA",
      "tip_off": "2026-04-03T19:30:00Z",
      "home_win_prob": 0.672,
      "away_win_prob": 0.328,
      "confidence": "high",
      "model_agreement": 0.91,
      "market_implied_home": 0.638,
      "edge": 0.034,
      "kelly_fraction": 0.068,
      "recommended_bet_pct": 2.3,
      "categories_used": 46,
      "feature_count": 110
    }
  ],
  "meta": {
    "games_today": 8,
    "high_confidence": 3,
    "avg_edge": 0.041,
    "total_exposure_pct": 18.6
  }
}
```

**Response (Free tier):** Same structure, max 3 games, no `kelly_fraction`, no `recommended_bet_pct`, no `edge`.

**Rate limits:**

| Tier | Predictions/day | Requests/min |
|------|----------------|--------------|
| Free | 3 | 5 |
| Scout | unlimited | 20 |
| Edge | unlimited | 60 |
| Whale | unlimited | 300 |

---

### GET /api/odds

Live and pre-game odds aggregated from multiple sportsbooks with model overlay.

**Auth:** Scout+

**Query params:**

| Param | Type | Description |
|-------|------|-------------|
| `game_id` | string | Single game |
| `date` | ISO date | All games on date |
| `books` | string | Comma-separated: `draftkings,fanduel,betmgm,pinnacle` |

**Response:**
```json
{
  "game_id": "nba_20260403_BOS_MIA",
  "last_updated": "2026-04-03T18:55:00Z",
  "lines": [
    {
      "book": "draftkings",
      "home_ml": -210,
      "away_ml": +175,
      "home_implied": 0.677,
      "away_implied": 0.364,
      "juice": 0.041,
      "line_movement": [
        { "ts": "2026-04-03T09:00:00Z", "home_ml": -195 },
        { "ts": "2026-04-03T14:30:00Z", "home_ml": -210 }
      ]
    },
    {
      "book": "pinnacle",
      "home_ml": -208,
      "away_ml": +174,
      "home_implied": 0.675,
      "away_implied": 0.365,
      "juice": 0.040
    }
  ],
  "best_line": {
    "book": "pinnacle",
    "side": "home",
    "ml": -208,
    "model_prob": 0.672,
    "edge": 0.034,
    "ev_per_dollar": 0.034
  },
  "consensus": {
    "home_implied": 0.671,
    "sharp_money_direction": "home",
    "line_drift_4h": -0.015
  }
}
```

**Rate limits:** Scout: 20/min | Edge: 120/min | Whale: 600/min

---

### GET/POST /api/bankroll

Portfolio management, bet tracking, and Kelly-optimal sizing engine.

**Auth:** Scout+. POST (logging bets) requires Scout+. Kelly sizing requires Edge+.

#### GET /api/bankroll/status

```json
{
  "balance": 91.89,
  "initial_balance": 100.00,
  "roi_pct": -8.11,
  "win_rate_pct": 39.02,
  "record": "16W-25L-0P",
  "peak_balance": 110.43,
  "max_drawdown_pct": 16.79,
  "sharpe_ratio": -2.99,
  "total_bets": 41,
  "total_wagered": 103.86,
  "season_start": "2026-03-19",
  "kelly_config": {
    "fraction": 0.35,
    "min_edge": 0.03,
    "max_bet_pct": 5.0
  }
}
```

#### POST /api/bankroll/kelly

Calculate Kelly-optimal bet size given model probability and market odds.

**Request:**
```json
{
  "home_win_prob": 0.672,
  "market_odds_ml": -210,
  "current_bankroll": 1000.00,
  "kelly_fraction": 0.35,
  "max_bet_pct": 5.0
}
```

**Response:**
```json
{
  "kelly_full": 0.0982,
  "kelly_fractional": 0.0344,
  "recommended_bet": 34.40,
  "recommended_bet_pct": 3.44,
  "edge": 0.034,
  "expected_value": 1.18,
  "ruin_probability_100bets": 0.0023
}
```

#### POST /api/bankroll/log

Log a placed bet for tracking.

**Request:**
```json
{
  "game_id": "nba_20260403_BOS_MIA",
  "side": "home",
  "amount": 34.40,
  "odds_ml": -210,
  "book": "draftkings"
}
```

**Response:** Bet ID + updated bankroll state.

**Rate limits:** GET: same as predictions. POST: 100/day (Scout), 500/day (Edge), unlimited (Whale).

---

### GET /api/evolution

Model evolution status across all 6 HF islands and Kaggle Karpathy loop.

**Auth:** Edge+

**Query params:** `island` (S10–S15 | all), `metric` (brier | roi | sharpe)

**Response:**
```json
{
  "timestamp": "2026-04-03T20:00:00Z",
  "fleet_summary": {
    "islands_active": 6,
    "total_generations": 2408,
    "fleet_best_brier": 0.22159,
    "fleet_avg_brier": 0.22419,
    "atr_best_brier": 0.21570,
    "atr_model": "tabicl_ensemble",
    "target_brier": 0.20000,
    "gap_to_target": 0.01570
  },
  "islands": {
    "S10": {
      "name": "Exploitation",
      "status": "running",
      "brier": 0.22454,
      "generation": 213,
      "model": "xgboost_brier",
      "mutation_rate": 0.09,
      "crossover_rate": 0.80,
      "features_selected": 63,
      "url": "nomos42-nba-quant.hf.space"
    },
    "S11": {
      "name": "Exploration",
      "status": "running",
      "brier": 0.22273,
      "generation": 295,
      "model": "xgboost",
      "mutation_rate": 0.15,
      "features_selected": 80,
      "url": "nomos42-nba-quant-2.hf.space"
    },
    "S12": {
      "name": "Extra-Trees Specialist",
      "status": "running",
      "brier": 0.22506,
      "generation": 590,
      "model": "catboost",
      "mutation_rate": 0.08,
      "features_selected": 60
    },
    "S13": {
      "name": "CatBoost Specialist",
      "status": "running",
      "brier": 0.22455,
      "generation": 381,
      "model": "extra_trees",
      "mutation_rate": 0.10,
      "features_selected": 66
    },
    "S14": {
      "name": "LightGBM Specialist",
      "status": "running",
      "brier": 0.22666,
      "generation": 448,
      "model": "xgboost_brier",
      "mutation_rate": 0.08,
      "features_selected": 55
    },
    "S15": {
      "name": "Wide Search",
      "status": "running",
      "brier": 0.22159,
      "generation": 481,
      "model": "random_forest",
      "mutation_rate": 0.18,
      "features_selected": 80,
      "population": 50
    }
  },
  "kaggle": {
    "nba_karpathy": {
      "status": "running",
      "sessions": 15,
      "iterations_per_session": 100,
      "best_brier_achieved": 0.21570,
      "platform": "P100 GPU"
    }
  },
  "feature_engine": {
    "version": "v3.1-46cat",
    "categories": 46,
    "raw_features": 6253,
    "max_selected": 200
  }
}
```

**Rate limits:** 30/min (Edge), 200/min (Whale)

---

### GET/POST /api/agents

Agent marketplace — buy, sell, and rent prediction strategies and model configurations.

**Auth:** Edge (read/subscribe). Whale (publish, revenue share).

This is the network-effect moat of Nomos42. Agents are parameterized strategy objects: a combination of model weights, feature sets, Kelly configurations, and betting filters. Any Whale subscriber can publish an agent; any Edge+ subscriber can subscribe to one.

#### GET /api/agents/marketplace

```json
{
  "agents": [
    {
      "agent_id": "ag_grok_valuehunter_v3",
      "name": "Grok Value Hunter",
      "author": "nomos42_internal",
      "description": "High-edge value bets only. Requires edge > 7%. Half-Kelly. Ignores home favorites.",
      "strategy": "value_hunter",
      "kelly_fraction": 0.5,
      "min_edge": 0.07,
      "model_weights": {
        "tabicl": 0.4,
        "catboost": 0.3,
        "xgboost": 0.3
      },
      "backtest": {
        "roi_pct": 1631.08,
        "sharpe": 2.66,
        "bets": 3554,
        "win_rate": 0.493,
        "start_date": "2025-10-21"
      },
      "price_per_month": 9.99,
      "subscribers": 47,
      "tier_required": "edge",
      "verified": true,
      "revenue_share_pct": 70
    },
    {
      "agent_id": "ag_openrouter_diversified",
      "name": "OpenRouter Diversified",
      "author": "nomos42_internal",
      "description": "Spread across 5 models, 3 strategies simultaneously. Lower variance.",
      "backtest": {
        "roi_pct": 64.63,
        "sharpe": 0.56,
        "bets": 2125
      },
      "price_per_month": 4.99,
      "subscribers": 23,
      "tier_required": "edge"
    }
  ],
  "meta": {
    "total_agents": 12,
    "verified_agents": 5,
    "community_agents": 7,
    "total_subscribers": 203
  }
}
```

#### POST /api/agents/publish

Whale tier only. Publish a custom agent to the marketplace.

**Request:**
```json
{
  "name": "My Closing Line Value Hunter",
  "description": "Bets only when model diverges >5% from closing line",
  "strategy_config": {
    "min_edge": 0.05,
    "kelly_fraction": 0.25,
    "model_weights": { "tabicl": 0.6, "xgboost": 0.4 },
    "filters": {
      "min_market_implied": 0.20,
      "max_market_implied": 0.80,
      "require_closing_line_available": true
    }
  },
  "price_per_month": 7.99,
  "revenue_share_pct": 70
}
```

**Response:**
```json
{
  "agent_id": "ag_user_abc123_clv_v1",
  "status": "pending_verification",
  "backtest_queued": true,
  "estimated_verification_hours": 24,
  "revenue_share": {
    "your_pct": 70,
    "platform_pct": 30,
    "payout_threshold": 50.00,
    "payout_currency": "USD"
  }
}
```

**Revenue Model:** Platform takes 30% of all marketplace agent subscriptions. Creators earn 70%. Minimum payout $50, monthly via Stripe.

**Rate limits:** GET: 60/min (Edge), 300/min (Whale). POST /publish: 5/day (Whale only).

---

### GET /api/research

Curated research papers, extracted techniques, and active proposals powering the evolution engine.

**Auth:** Edge+

**Query params:** `status` (active|proposed|deployed|rejected), `department` (research|engineering|evolution)

**Response:**
```json
{
  "pipeline": {
    "papers_scanned_total": 14,
    "techniques_extracted": 18,
    "sota_reference": {
      "paper": "Montrucchio 2026 (MDPI Information 17/1/56)",
      "brier": 0.199,
      "our_gap": 0.01570
    },
    "active_proposals": 3
  },
  "papers": [
    {
      "id": "rp_001",
      "title": "NBA Game Outcome Prediction Using Ensemble ML Methods",
      "authors": "Montrucchio et al.",
      "year": 2026,
      "journal": "MDPI Information 17/1/56",
      "key_result": "Brier 0.199 with 47-feature XGBoost + temporal validation",
      "techniques": ["temporal_cv", "feature_importance_pruning", "calibration_isotonic"],
      "status": "deployed",
      "brier_impact": -0.003
    }
  ],
  "proposals": [
    {
      "id": "prop_platt_calibration",
      "title": "Platt Scaling Post-Hoc Calibration",
      "priority": 1,
      "effort": "medium",
      "expected_brier_delta": -0.008,
      "department": "engineering",
      "status": "queued"
    }
  ],
  "categories": {
    "total": 46,
    "deployed": 46,
    "pipeline": ["Cat47_Drive_Rim", "Cat48_Passing_PPP", "Cat49_PlayType_PPP"]
  }
}
```

**Rate limits:** 20/min (Edge), 100/min (Whale)

---

### GET /api/departments

Internal department status and Karpathy loop metrics. Whale tier only — this exposes the engine room.

**Auth:** Whale only

**Query params:** `dept` (all | research | engineering | evolution | betting | evaluation | infra | political)

**Response:**
```json
{
  "forge_version": "v19",
  "timestamp": "2026-04-03T20:00:00Z",
  "departments": {
    "research": {
      "status": "active",
      "iteration": 9,
      "papers_this_week": 14,
      "techniques_extracted": 18,
      "proposals_queued": 3,
      "karpathy_loop": "running",
      "last_run": "2026-04-03T20:02:04Z"
    },
    "engineering": {
      "status": "active",
      "iteration": 7,
      "deployments_this_week": 3,
      "test_pass_rate": 0.94,
      "open_bugs": 2,
      "last_deploy": "2026-04-02T15:00:00Z"
    },
    "evolution": {
      "status": "active",
      "islands_running": 6,
      "total_generations_today": 400,
      "best_brier_today": 0.22159,
      "diversity_score": 0.567,
      "cross_pollination_pending": 3
    },
    "betting": {
      "status": "active",
      "strategies_live": 5,
      "top_strategy": "full_kelly",
      "simulated_roi": 135550.14,
      "bets_today": 8
    },
    "evaluation": {
      "status": "active",
      "biases_detected": 4,
      "calibration_ece": 0.2758,
      "open_issues": ["phantom_game_guard", "odds_sanity_gate"]
    },
    "infra": {
      "status": "active",
      "uptime_pct": 88.0,
      "spaces_up": "6/6",
      "kaggle_loops": "1/2",
      "last_restart": null
    }
  },
  "trading_floor": {
    "iteration": 297,
    "traders": {
      "gemini": { "bankroll": 1731.08, "roi_pct": 1631.08, "sharpe": 2.66 },
      "openrouter": { "bankroll": 164.63, "roi_pct": 64.63, "sharpe": 0.56 }
    },
    "best_trader": "gemini"
  },
  "guardian": {
    "version": "v3",
    "departments_monitored": 11,
    "resource_allocations": "auto",
    "last_cycle": "2026-04-03T20:12:32Z"
  }
}
```

**Rate limits:** 10/min (Whale only)

---

## Webhooks

Edge+ subscribers can register webhooks for real-time event delivery.

**Events:**
- `prediction.new` — New daily predictions published (~10:00 UTC)
- `prediction.update` — Prediction revised due to injury report
- `odds.movement` — Significant line move (>5% in 30 min)
- `bet.result` — Game result + P&L for tracked bets
- `evolution.improvement` — Fleet Brier improves (Whale only)
- `agent.signal` — Subscribed agent triggers a recommendation

**Registration:**
```bash
POST /api/webhooks
{
  "url": "https://your-server.com/hook",
  "events": ["prediction.new", "odds.movement"],
  "secret": "your_signing_secret"
}
```

**Payload signature:** `X-Nomos42-Signature: sha256=<hmac>`

---

## SDK Support

Official SDKs planned for:
- **Python**: `pip install nomos42` — priority Q2 2026
- **JavaScript/TypeScript**: `npm install @nomos42/sdk` — priority Q3 2026
- **REST**: OpenAPI 3.1 spec at `/api/openapi.json`

---

## Infrastructure

| Component | Technology | Notes |
|-----------|-----------|-------|
| API gateway | Vercel Edge Functions | Globally distributed |
| Auth | Supabase JWT + Row-Level Security | Tier enforcement at DB layer |
| ML inference | HF Spaces (6 islands, CPU) | Tree-based ensemble |
| GPU training | Kaggle P100 / Colab T4 | Karpathy loop, 9h sessions |
| Data store | Supabase (PostgreSQL) | Experiments, proposals, bets |
| Cache | Redis (Upstash) | Predictions cached 1h |
| Queue | Supabase Realtime | Webhook delivery |

---

## Rate Limit Responses

```json
HTTP 429 Too Many Requests
{
  "error": "rate_limit_exceeded",
  "limit": 20,
  "window": "1 minute",
  "reset_at": "2026-04-03T20:01:00Z",
  "upgrade_url": "https://nomosdashboard.vercel.app/pricing"
}
```

---

## Pricing Justification

- **Free → Scout conversion**: 3 predictions/day creates FOMO on missed games. Email alert feature drives daily engagement.
- **Scout → Edge**: Kelly sizing is the unlock. Once users understand position sizing, they need it. Telegram replaces email for live alerts.
- **Edge → Whale**: Raw model outputs + departments API allows sophisticated operators (syndicates, hedge funds) to build proprietary layers on top of Nomos42 intelligence. The agent marketplace creates lock-in.

**Target ARR (Year 1):**
- 500 Scout ($19) = $114,000
- 200 Edge ($49) = $117,600
- 50 Whale ($149) = $89,400
- Agent marketplace (30% cut) = ~$20,000
- **Total: $341,000 ARR**
