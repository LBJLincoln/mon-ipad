-- ============================================================
-- RAG Benchmark System — Supabase Schema Migration
-- Tables for dataset storage, test runs, results & monitoring
-- ============================================================

-- 1. Benchmark datasets: stores all ingested Q&A pairs
CREATE TABLE IF NOT EXISTS benchmark_datasets (
    id              BIGSERIAL PRIMARY KEY,
    dataset_name    TEXT NOT NULL,           -- e.g. "natural_questions", "hotpotqa"
    category        TEXT NOT NULL,           -- e.g. "single_hop_qa", "multi_hop_qa", "retrieval"
    split           TEXT NOT NULL DEFAULT 'test',  -- train/test/dev/validation
    item_index      INT NOT NULL,            -- index within dataset
    question        TEXT NOT NULL,
    expected_answer  TEXT,
    context         TEXT,                    -- optional supporting context
    supporting_facts JSONB,                  -- for multi-hop: list of facts
    metadata        JSONB DEFAULT '{}',      -- dataset-specific metadata
    embedding_id    TEXT,                    -- reference to Pinecone vector ID
    neo4j_node_id   TEXT,                    -- reference to Neo4j node if applicable
    tenant_id       TEXT NOT NULL DEFAULT 'benchmark',
    ingested_at     TIMESTAMPTZ DEFAULT NOW(),
    batch_id        TEXT,                    -- which ingestion batch
    UNIQUE(dataset_name, split, item_index, tenant_id)
);

CREATE INDEX idx_bd_dataset ON benchmark_datasets(dataset_name);
CREATE INDEX idx_bd_category ON benchmark_datasets(category);
CREATE INDEX idx_bd_tenant ON benchmark_datasets(tenant_id);
CREATE INDEX idx_bd_batch ON benchmark_datasets(batch_id);

-- 2. Benchmark runs: each test execution session
CREATE TABLE IF NOT EXISTS benchmark_runs (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT UNIQUE NOT NULL,     -- e.g. "run-20260206-143000-abc12"
    run_type        TEXT NOT NULL,            -- "ingestion", "retrieval", "generation", "e2e", "orchestrator", "robustness", "regression"
    phase           TEXT NOT NULL,            -- "phase_1" through "phase_8"
    workflow_name   TEXT NOT NULL,            -- n8n workflow name
    dataset_names   TEXT[] NOT NULL,          -- datasets used in this run
    config          JSONB NOT NULL DEFAULT '{}',  -- batch_size, metrics requested, thresholds
    status          TEXT NOT NULL DEFAULT 'running',  -- running, completed, failed, partial
    total_items     INT DEFAULT 0,
    processed_items INT DEFAULT 0,
    error_count     INT DEFAULT 0,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    duration_ms     INT,
    trace_id        TEXT,                    -- OTEL trace ID
    tenant_id       TEXT NOT NULL DEFAULT 'benchmark',
    triggered_by    TEXT DEFAULT 'manual'    -- manual, scheduled, orchestrator
);

CREATE INDEX idx_br_run_id ON benchmark_runs(run_id);
CREATE INDEX idx_br_status ON benchmark_runs(status);
CREATE INDEX idx_br_run_type ON benchmark_runs(run_type);
CREATE INDEX idx_br_phase ON benchmark_runs(phase);

-- 3. Benchmark results: per-query results within a run
CREATE TABLE IF NOT EXISTS benchmark_results (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES benchmark_runs(run_id),
    dataset_name    TEXT NOT NULL,
    item_index      INT NOT NULL,
    question        TEXT NOT NULL,
    expected_answer  TEXT,
    actual_answer   TEXT,
    retrieved_docs  JSONB,                   -- list of retrieved document IDs/scores
    metrics         JSONB NOT NULL DEFAULT '{}',  -- per-query metrics (EM, F1, Recall, etc.)
    latency_ms      INT,
    tokens_used     INT,
    error           TEXT,                    -- error message if failed
    metadata        JSONB DEFAULT '{}',      -- additional data (model used, routing decision, etc.)
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    tenant_id       TEXT NOT NULL DEFAULT 'benchmark'
);

CREATE INDEX idx_bres_run ON benchmark_results(run_id);
CREATE INDEX idx_bres_dataset ON benchmark_results(dataset_name);
CREATE INDEX idx_bres_metrics ON benchmark_results USING GIN (metrics);

-- 4. Benchmark baselines: reference metrics for regression detection
CREATE TABLE IF NOT EXISTS benchmark_baselines (
    id              BIGSERIAL PRIMARY KEY,
    baseline_name   TEXT UNIQUE NOT NULL,     -- e.g. "v4.0-baseline-20260206"
    dataset_name    TEXT NOT NULL,
    phase           TEXT NOT NULL,
    metrics         JSONB NOT NULL,           -- aggregated metrics
    run_id          TEXT REFERENCES benchmark_runs(run_id),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    notes           TEXT
);

CREATE INDEX idx_bb_active ON benchmark_baselines(is_active);
CREATE INDEX idx_bb_dataset ON benchmark_baselines(dataset_name);

-- 5. Benchmark alerts: regression and anomaly alerts
CREATE TABLE IF NOT EXISTS benchmark_alerts (
    id              BIGSERIAL PRIMARY KEY,
    alert_type      TEXT NOT NULL,            -- "regression", "threshold_breach", "error_spike", "latency_spike"
    severity        TEXT NOT NULL DEFAULT 'warning',  -- info, warning, critical
    run_id          TEXT REFERENCES benchmark_runs(run_id),
    dataset_name    TEXT,
    metric_name     TEXT NOT NULL,
    baseline_value  FLOAT,
    current_value   FLOAT,
    delta_pct       FLOAT,                   -- percentage change
    threshold       FLOAT,
    message         TEXT NOT NULL,
    acknowledged    BOOLEAN DEFAULT FALSE,
    slack_sent      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ba_severity ON benchmark_alerts(severity);
CREATE INDEX idx_ba_ack ON benchmark_alerts(acknowledged);
CREATE INDEX idx_ba_created ON benchmark_alerts(created_at DESC);

-- 6. Benchmark ingestion stats: tracks ingestion progress per dataset
CREATE TABLE IF NOT EXISTS benchmark_ingestion_stats (
    id              BIGSERIAL PRIMARY KEY,
    dataset_name    TEXT NOT NULL,
    split           TEXT NOT NULL DEFAULT 'test',
    total_items     INT NOT NULL,
    ingested_items  INT NOT NULL DEFAULT 0,
    pinecone_vectors INT DEFAULT 0,
    neo4j_nodes     INT DEFAULT 0,
    supabase_rows   INT DEFAULT 0,
    last_batch_id   TEXT,
    status          TEXT DEFAULT 'pending',  -- pending, in_progress, completed, failed
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_log       TEXT,
    UNIQUE(dataset_name, split)
);

-- 7. Dashboard snapshots: periodic metric snapshots for trend visualization
CREATE TABLE IF NOT EXISTS benchmark_dashboard_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    snapshot_time   TIMESTAMPTZ DEFAULT NOW(),
    phase           TEXT NOT NULL,
    dataset_name    TEXT NOT NULL,
    metrics_summary JSONB NOT NULL,           -- aggregated metrics at snapshot time
    comparison_to_baseline JSONB,             -- delta vs active baseline
    total_runs      INT DEFAULT 0,
    avg_latency_ms  INT,
    error_rate      FLOAT,
    trend           TEXT                      -- "improving", "stable", "degrading"
);

CREATE INDEX idx_bds_time ON benchmark_dashboard_snapshots(snapshot_time DESC);
CREATE INDEX idx_bds_phase ON benchmark_dashboard_snapshots(phase);

-- ============================================================
-- VIEWS for monitoring dashboard
-- ============================================================

-- Latest results per dataset (most recent run)
CREATE OR REPLACE VIEW v_latest_benchmark_results AS
SELECT DISTINCT ON (br.dataset_names, br.phase)
    br.run_id,
    br.run_type,
    br.phase,
    br.dataset_names,
    br.status,
    br.total_items,
    br.processed_items,
    br.error_count,
    br.started_at,
    br.completed_at,
    br.duration_ms
FROM benchmark_runs br
WHERE br.status IN ('completed', 'partial')
ORDER BY br.dataset_names, br.phase, br.completed_at DESC;

-- Regression summary: compare latest runs to baselines
CREATE OR REPLACE VIEW v_regression_summary AS
SELECT
    bb.dataset_name,
    bb.phase,
    bb.metrics AS baseline_metrics,
    (
        SELECT jsonb_agg(res.metrics)
        FROM benchmark_results res
        WHERE res.run_id = (
            SELECT br.run_id FROM benchmark_runs br
            WHERE bb.dataset_name = ANY(br.dataset_names)
            AND br.status = 'completed'
            ORDER BY br.completed_at DESC LIMIT 1
        )
    ) AS latest_metrics,
    bb.baseline_name,
    bb.created_at AS baseline_date
FROM benchmark_baselines bb
WHERE bb.is_active = TRUE;

-- Active alerts summary
CREATE OR REPLACE VIEW v_active_alerts AS
SELECT
    alert_type,
    severity,
    dataset_name,
    metric_name,
    delta_pct,
    message,
    created_at
FROM benchmark_alerts
WHERE acknowledged = FALSE
ORDER BY
    CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
    created_at DESC;
