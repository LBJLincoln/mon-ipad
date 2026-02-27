-- ============================================================
-- Trading Board Dashboard Schema
-- Migration: create_trading_board
-- Source: docs/agentic/agentic-automation-spec.md (Section 3.2)
-- ============================================================
-- Stores periodic snapshots of pipeline performance for the
-- trading-board dashboard: best/worst performers, rolling 24h
-- window metrics, decision log, and alert feed.

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
