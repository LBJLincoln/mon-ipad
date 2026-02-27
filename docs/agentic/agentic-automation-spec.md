# Agentic Automation Spec — Nomos42 Rollout

> **Version:** 1.0  
> **Date:** 2026-02-27  
> **Target:** Nomos42 (ex-PME) rollout tomorrow  
> **Status:** Implementation-ready

---

## 1. Automated Bug Signature Detection

### 1.1 Architecture Overview
```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────┐
│  OpenRouter │───→│   n8n        │───→│   Supabase  │───→│  Alerting   │
│   (LLM)     │    │  (webhook)   │    │   (logs)    │    │  (n8n/Slack)│
└─────────────┘    └──────────────┘    └─────────────┘    └─────────────┘
                          │
                          ↓
                   ┌──────────────┐
                   │  Signature   │
                   │   Matcher    │
                   └──────────────┘
```

### 1.2 OpenRouter Error Pattern Detection

**File:** `scripts/openrouter-monitor.py`

```python
# Error signatures to detect
ERROR_SIGNATURES = {
    "rate_limit": {
        "patterns": ["429", "rate limit", "too many requests"],
        "severity": "warning",
        "auto_action": "rotate_key",
        "cooldown_minutes": 5
    },
    "auth_failure": {
        "patterns": ["401", "invalid api key", "authentication failed"],
        "severity": "critical",
        "auto_action": "alert_rotate",
        "cooldown_minutes": 1
    },
    "model_overload": {
        "patterns": ["503", "overloaded", "unavailable"],
        "severity": "warning",
        "auto_action": "fallback_model",
        "cooldown_minutes": 2
    },
    "empty_response": {
        "patterns": ["empty body", "null response", "no output"],
        "severity": "high",
        "auto_action": "retry_with_backup",
        "cooldown_minutes": 0
    },
    "timeout": {
        "patterns": ["timeout", "deadline exceeded", "ETIMEDOUT"],
        "severity": "warning",
        "auto_action": "increase_timeout",
        "cooldown_minutes": 3
    }
}
```

**Implementation Steps:**
1. Hook into `eval/quick-test.py` output parsing (line 122-134)
2. Parse logs from `logs/session-intelligence-report.json`
3. Insert detected signatures to `db/migrations/supabase-core.sql` → `benchmark_alerts` table

### 1.3 Webhook Health Monitoring

**File:** `scripts/webhook-health-monitor.py`

| Webhook Path | Pipeline | Expected Latency | Timeout Threshold |
|-------------|----------|------------------|-------------------|
| `/webhook/rag-multi-index-v3` | Standard | <3s | 90s |
| `/webhook/ff622742-6d71-4e91-af71-b5c666088717` | Graph | <5s | 90s |
| `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9` | Quantitative | <8s | 120s |
| `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` | Orchestrator | <10s | 180s |
| `/webhook/project-chatbot` | Nomos42 | <3s | 60s |

**Health Check Logic:**
```bash
# From dashboard/index.html lines 744-774
curl -X POST "${N8N_HOST}${webhook}" \
  -H "Content-Type: application/json" \
  -d '{"query": "health", "sessionId": "monitor-"}' \
  --max-time ${timeout} \
  -w "%{http_code},%{time_total}"
```

### 1.4 n8n Execution Analysis

**File:** `scripts/analyze_n8n_executions.py` (existing, enhanced)

**New Signature Detection:**
```python
# Add to existing parse_rich_node function
BUG_SIGNATURES = {
    "credential_null": {
        "check": lambda node: "Bearer null" in str(node.get("full_output_data", {})),
        "signature_id": "SIG-CRED-001",
        "fix_ref": "technicals/debug/fixes-library.md#FIX-54"
    },
    "redis_missing": {
        "check": lambda node: "Redis" in node.get("name", "") and node.get("status") == "error",
        "signature_id": "SIG-REDIS-001",
        "fix_ref": "technicals/debug/fixes-library.md#FIX-48"
    },
    "template_sql_fail": {
        "check": lambda node: "template" in str(node.get("full_output_data", {})).lower() and node.get("status") == "error",
        "signature_id": "SIG-SQL-001",
        "fix_ref": "technicals/debug/fixes-library.md#FIX-55"
    }
}
```

### 1.5 Database Alert Schema

**Migration:** `db/migrations/create_bug_signatures.sql`

```sql
-- Bug signature detection log
CREATE TABLE IF NOT EXISTS bug_signatures (
    id BIGSERIAL PRIMARY KEY,
    signature_id TEXT NOT NULL,           -- e.g., "SIG-CRED-001"
    pipeline TEXT NOT NULL,               -- standard|graph|quantitative|orchestrator|nomos42
    source TEXT NOT NULL,                 -- openrouter|webhook|n8n|eval
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    execution_id TEXT,                    -- n8n execution ID if applicable
    error_snippet TEXT,                   -- truncated error message
    metadata JSONB DEFAULT '{}',          -- additional context
    acknowledged BOOLEAN DEFAULT FALSE,
    auto_action_taken TEXT,               -- what automation did
    fix_applied BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_bs_signature ON bug_signatures(signature_id);
CREATE INDEX idx_bs_pipeline ON bug_signatures(pipeline);
CREATE INDEX idx_bs_detected ON bug_signatures(detected_at DESC);
CREATE INDEX idx_bs_ack ON bug_signatures(acknowledged);
```

---

## 2. KEEP/REVERT Decision Engine

### 2.1 Golden Check Framework

**File:** `eval/golden-check.py`

```python
GOLDEN_THRESHOLDS = {
    "standard": {
        "min_accuracy": 85.0,
        "max_latency_p95": 5000,      # ms
        "max_error_rate": 5.0,        # %
        "required_smoke_pass": 4/5    # from quick-test.py
    },
    "graph": {
        "min_accuracy": 70.0,
        "max_latency_p95": 8000,
        "max_error_rate": 10.0,
        "required_smoke_pass": 3/5
    },
    "quantitative": {
        "min_accuracy": 85.0,
        "max_latency_p95": 10000,
        "max_error_rate": 5.0,
        "required_smoke_pass": 4/5
    },
    "orchestrator": {
        "min_accuracy": 70.0,
        "max_latency_p95": 15000,
        "max_error_rate": 10.0,
        "required_smoke_pass": 3/5
    },
    "nomos42": {
        "min_accuracy": 75.0,
        "max_latency_p95": 5000,
        "max_error_rate": 15.0,
        "required_smoke_pass": 3/4
    }
}
```

### 2.2 Decision Matrix

**File:** `scripts/decision-engine.py`

```python
def make_keep_revert_decision(pipeline: str, metrics: dict) -> dict:
    """
    Returns: {"decision": "KEEP"|"REVERT"|"HOLD", "reasons": [], "confidence": 0-1}
    """
    golden = GOLDEN_THRESHOLDS[pipeline]
    reasons = []
    confidence = 1.0
    
    # Critical: accuracy regression >10%
    if metrics["accuracy"] < golden["min_accuracy"] * 0.9:
        reasons.append(f"CRITICAL: Accuracy {metrics['accuracy']}% < 90% of golden")
        confidence = 1.0
        return {"decision": "REVERT", "reasons": reasons, "confidence": confidence}
    
    # Warning: accuracy below golden
    if metrics["accuracy"] < golden["min_accuracy"]:
        reasons.append(f"WARNING: Accuracy {metrics['accuracy']}% < golden {golden['min_accuracy']}%")
        confidence -= 0.2
    
    # Smoke test failure
    if metrics["smoke_pass_rate"] < golden["required_smoke_pass"]:
        reasons.append(f"CRITICAL: Smoke tests {metrics['smoke_pass_rate']} < required {golden['required_smoke_pass']}")
        confidence -= 0.4
    
    # Error spike
    if metrics["error_rate"] > golden["max_error_rate"] * 2:
        reasons.append(f"CRITICAL: Error rate {metrics['error_rate']}% > 2x threshold")
        confidence -= 0.3
    
    # Latency degradation
    if metrics["latency_p95"] > golden["max_latency_p95"] * 1.5:
        reasons.append(f"WARNING: P95 latency {metrics['latency_p95']}ms > 1.5x threshold")
        confidence -= 0.1
    
    decision = "KEEP" if confidence >= 0.7 else ("HOLD" if confidence >= 0.4 else "REVERT")
    return {"decision": decision, "reasons": reasons, "confidence": confidence}
```

### 2.3 Revert Automation

**File:** `scripts/auto-revert.py`

```bash
#!/bin/bash
# Automatic revert to last known good snapshot

SNAPSHOT_DIR="snapshot/working-session$(cat .last_good_session)/"
WORKFLOW_DIR="n8n/live/"

revert_workflow() {
    local pipeline=$1
    local golden_file=$2
    
    echo "[REVERT] $pipeline to golden: $golden_file"
    
    # Use existing workflow-diff-engine.py
    python3 scripts/workflow-diff-engine.py \
        --revert \
        --pipeline $pipeline \
        --space "https://lbjlincoln-nomos-rag-engine.hf.space"
    
    # Log revert action
    psql $SUPABASE_URL -c "
        INSERT INTO bug_signatures (signature_id, pipeline, source, auto_action_taken)
        VALUES ('AUTO-REVERT', '$pipeline', 'decision_engine', 'revert_to_golden');
    "
}
```

### 2.4 Integration with Existing Workflow Diff Engine

**Reference:** `scripts/workflow-diff-engine.py` lines 575-636

The existing revert functionality is enhanced with:
1. Pre-revert snapshot backup to `snapshot/auto-backup/`
2. Post-revert smoke test (5 questions)
3. Rollback of revert if smoke test fails
4. Notification via n8n webhook

---

## 3. Trading-Board Dashboard Schema

### 3.1 Dashboard Layout

**File:** `dashboard/trading-board.html` (new)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  TRADING BOARD — Multi-RAG Performance Monitor      [Auto-refresh: 30s] │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │   BEST       │  │   WORST      │  │   MIDDLE (Rolling Window)    │  │
│  │  (Fixed)     │  │  (Fixed)     │  │  (Last 24h, 50-test min)     │  │
│  ├──────────────┤  ├──────────────┤  ├──────────────────────────────┤  │
│  │ • Pipeline   │  │ • Pipeline   │  │ • Accuracy trend             │  │
│  │ • Accuracy   │  │ • Accuracy   │  │ • Latency trend              │  │
│  │ • Latency    │  │ • Latency    │  │ • Error rate trend           │  │
│  │ • Trend ↗    │  │ • Trend ↘    │  │ • Volume (tests/hour)        │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│  DECISION LOG                    │  ALERT FEED (Last 10)               │
│  [Timestamp] KEEP standard 85.2% │  🔴 SIG-CRED-001 detected...        │
│  [Timestamp] REVERT quant 62.1%  │  🟡 Rate limit on key #3...         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Schema

**Supabase Migration:** `db/migrations/create_trading_board.sql`

```sql
-- Trading board snapshots (updated every 5 minutes)
CREATE TABLE IF NOT EXISTS trading_board_snapshots (
    id BIGSERIAL PRIMARY KEY,
    snapshot_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- BEST performer (fixed since last reset)
    best_pipeline TEXT,
    best_accuracy FLOAT,
    best_latency_p95 INT,
    best_tests_count INT,
    best_since TIMESTAMPTZ,
    
    -- WORST performer (fixed since last reset)
    worst_pipeline TEXT,
    worst_accuracy FLOAT,
    worst_latency_p95 INT,
    worst_tests_count INT,
    worst_since TIMESTAMPTZ,
    
    -- MIDDLE performers (rolling 24h window, min 50 tests)
    middle_pipelines JSONB,  -- [{pipeline, accuracy, latency, tests, trend}]
    
    -- Overall metrics
    total_tests_24h INT,
    overall_accuracy FLOAT,
    active_alerts_count INT,
    
    -- Decision log
    last_decision TEXT,      -- KEEP/REVERT/HOLD
    last_decision_pipeline TEXT,
    last_decision_at TIMESTAMPTZ
);

CREATE INDEX idx_tbs_time ON trading_board_snapshots(snapshot_at DESC);

-- Rolling window materialized view (refreshed every 10 min)
CREATE MATERIALIZED VIEW mv_pipeline_rolling_24h AS
SELECT 
    br.dataset_name as pipeline,
    COUNT(*) as test_count,
    AVG((metrics->>'accuracy')::float) as avg_accuracy,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency,
    COUNT(CASE WHEN error IS NOT NULL THEN 1 END)::float / COUNT(*) * 100 as error_rate,
    MAX(created_at) as last_test_at
FROM benchmark_results br
JOIN benchmark_runs brr ON br.run_id = brr.run_id
WHERE br.created_at > NOW() - INTERVAL '24 hours'
GROUP BY br.dataset_name
HAVING COUNT(*) >= 50;  -- Minimum 50 tests for statistical significance
```

### 3.3 Trend Calculation

**File:** `eval/calculate-trends.py`

```python
def calculate_trend(pipeline: str, window_hours: int = 24) -> dict:
    """
    Returns trend direction and confidence
    """
    query = """
    SELECT 
        DATE_TRUNC('hour', created_at) as hour,
        AVG((metrics->>'accuracy')::float) as hourly_accuracy
    FROM benchmark_results
    WHERE dataset_name = %s
      AND created_at > NOW() - INTERVAL '%s hours'
    GROUP BY DATE_TRUNC('hour', created_at)
    ORDER BY hour;
    """
    
    # Linear regression on hourly accuracy
    hours, accuracies = fetch_data(query, pipeline, window_hours)
    
    if len(hours) < 3:
        return {"trend": "insufficient_data", "slope": 0, "r2": 0}
    
    slope, intercept, r_value, _, _ = linregress(hours, accuracies)
    
    if slope > 0.5 and r_value**2 > 0.5:
        trend = "improving_strong"
    elif slope > 0.1 and r_value**2 > 0.3:
        trend = "improving_weak"
    elif slope < -0.5 and r_value**2 > 0.5:
        trend = "degrading_strong"
    elif slope < -0.1 and r_value**2 > 0.3:
        trend = "degrading_weak"
    else:
        trend = "stable"
    
    return {"trend": trend, "slope": slope, "r2": r_value**2}
```

### 3.4 API Endpoint

**File:** `scripts/trading-board-api.py`

```python
from flask import Flask, jsonify
import psycopg2

app = Flask(__name__)

@app.route('/api/trading-board')
def get_trading_board():
    """Returns current trading board state"""
    conn = psycopg2.connect(SUPABASE_URL)
    cur = conn.cursor()
    
    # Get latest snapshot
    cur.execute("""
        SELECT * FROM trading_board_snapshots
        ORDER BY snapshot_at DESC LIMIT 1;
    """)
    snapshot = cur.fetchone()
    
    # Get rolling window data
    cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_pipeline_rolling_24h;")
    cur.execute("SELECT * FROM mv_pipeline_rolling_24h;")
    rolling = cur.fetchall()
    
    return jsonify({
        "snapshot": snapshot,
        "rolling_24h": rolling,
        "generated_at": datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

---

## 4. Rollout Checklist — Nomos42 Tomorrow

### 4.1 Pre-Rollout Verification (T-24h)

| Check | Command/Action | Expected Result | Owner |
|-------|---------------|-----------------|-------|
| HF Space #1 health | `curl -s ${N8N_HOST}/healthz` | HTTP 200 | Auto |
| Chatbot webhook | `python3 eval/quick-test.py --pipeline nomos42 --questions 4` | 3/4 pass | Auto |
| OpenRouter keys | `grep -c "OPENROUTER" .env.local` | >= 6 keys | Manual |
| Supabase connection | `psql $SUPABASE_URL -c "SELECT 1"` | 1 row | Auto |
| Vercel sites | `curl -s https://nomos-ai-pied.vercel.app/api/health` | HTTP 200 | Auto |
| Golden snapshots | `ls snapshot/working-session*/` | >= 1 valid | Manual |
| Bug signature DB | `psql $SUPABASE_URL -c "SELECT COUNT(*) FROM bug_signatures"` | Table exists | Auto |

### 4.2 Deployment Sequence (T-0)

```bash
#!/bin/bash
# Nomos42 rollout script

set -e

echo "=== NOMOS42 ROLLOUT ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# 1. Verify pre-conditions
echo "[1/8] Verifying pre-conditions..."
python3 eval/quick-test.py --pipeline nomos42 --questions 4 || exit 1

# 2. Backup current state
echo "[2/8] Creating pre-deploy snapshot..."
python3 scripts/workflow-diff-engine.py --dry-run > logs/pre-deploy-check.json

# 3. Deploy to Vercel (staging)
echo "[3/8] Deploying to Vercel..."
cd ../rag-pme-connectors && git push origin main
sleep 30  # Wait for Vercel build

# 4. Run smoke tests
echo "[4/8] Running smoke tests..."
curl -X POST "https://nomos-pme-connectors-alexis-morets-projects.vercel.app/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, can you help me?"}' \
  --max-time 10

# 5. Activate monitoring
echo "[5/8] Activating bug signature detection..."
python3 scripts/openrouter-monitor.py --daemon &
python3 scripts/webhook-health-monitor.py --daemon &

# 6. Start trading board
echo "[6/8] Starting trading board..."
nohup python3 scripts/trading-board-api.py > logs/trading-board.log 2>&1 &

# 7. Verify decision engine
echo "[7/8] Testing decision engine..."
python3 scripts/decision-engine.py --test

# 8. Final health check
echo "[8/8] Final health check..."
python3 eval/quick-test.py --pipeline nomos42 --questions 5
echo "✅ ROLLOUT COMPLETE"
```

### 4.3 Post-Rollout Monitoring (T+1h to T+24h)

| Time | Action | Threshold | Escalation |
|------|--------|-----------|------------|
| T+15min | Check error rate | <5% | Auto-alert |
| T+1h | Review trading board | All pipelines stable | Manual review |
| T+4h | Run golden checks | All PASS | Auto if FAIL |
| T+12h | Performance report | Latency <3s median | Daily digest |
| T+24h | Full accuracy eval | Nomos42 >=75% | Decision engine |

### 4.4 Rollback Triggers

**Immediate rollback (auto-triggered):**
- Error rate >20% for 5 consecutive minutes
- Chatbot webhook returns 5xx for 3 consecutive checks
- Decision engine returns REVERT with confidence >0.9

**Manual rollback criteria:**
- User complaints >5 in 1 hour
- Accuracy <60% on manual spot-check
- Latency P95 >10s sustained

**Rollback command:**
```bash
# One-line rollback
python3 scripts/workflow-diff-engine.py --revert --pipeline nomos42 && \
  git -C ../rag-pme-connectors revert HEAD && \
  git -C ../rag-pme-connectors push origin main
```

### 4.5 Success Criteria (24h post-rollout)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Uptime | >=99% | Webhook health checks |
| Response time P50 | <=2.5s | Trading board metrics |
| Response time P95 | <=5s | Trading board metrics |
| User satisfaction | >=4/5 | In-chat feedback (20+ responses) |
| Error rate | <=5% | Bug signature count / total requests |
| Golden check pass | 100% | 4/4 smoke tests |

---

## 5. File Inventory

### New Files to Create
| Path | Purpose |
|------|---------|
| `scripts/openrouter-monitor.py` | Error pattern detection |
| `scripts/webhook-health-monitor.py` | Webhook health checks |
| `scripts/decision-engine.py` | KEEP/REVERT logic |
| `scripts/auto-revert.py` | Automated rollback |
| `scripts/trading-board-api.py` | Dashboard API server |
| `eval/golden-check.py` | Golden threshold validation |
| `eval/calculate-trends.py` | Trend calculation |
| `dashboard/trading-board.html` | Trading board UI |
| `db/migrations/create_bug_signatures.sql` | Bug signature table |
| `db/migrations/create_trading_board.sql` | Trading board schema |

### Existing Files to Modify
| Path | Modification |
|------|-------------|
| `scripts/workflow-diff-engine.py` | Add auto-revert integration |
| `scripts/analyze_n8n_executions.py` | Add bug signature detection |
| `eval/quick-test.py` | Add golden check validation |
| `docs/status.json` | Add trading board fields |

---

## 6. Quick Start Commands

```bash
# 1. Setup database tables
psql $SUPABASE_URL -f db/migrations/create_bug_signatures.sql
psql $SUPABASE_URL -f db/migrations/create_trading_board.sql

# 2. Start monitoring (background)
nohup python3 scripts/openrouter-monitor.py --daemon > logs/openrouter.log 2>&1 &
nohup python3 scripts/webhook-health-monitor.py --daemon > logs/webhook.log 2>&1 &

# 3. Start trading board API
nohup python3 scripts/trading-board-api.py > logs/trading-board.log 2>&1 &

# 4. Run decision engine check
python3 scripts/decision-engine.py --check-all

# 5. Deploy Nomos42
bash scripts/nomos42-rollout.sh
```

---

*Last updated: 2026-02-27T15:49:00Z*  
*Next review: Post-Nomos42 rollout (2026-02-28)*
