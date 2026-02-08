-- ============================================================
-- Phase 2: Financial Table Data for Quantitative RAG (WF4)
-- Stores parsed table data from FinQA, TAT-QA, and ConvFinQA
-- datasets for text-to-SQL evaluation.
--
-- Each question in these datasets comes with its own financial
-- report table. This migration creates per-dataset tables that
-- store both the structured JSONB data and a text representation
-- for the RAG workflow to use as SQL context.
-- ============================================================

-- 1. FinQA tables (200 questions, each with a financial report table)
CREATE TABLE IF NOT EXISTS finqa_tables (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL DEFAULT 'benchmark',
    question_id     TEXT NOT NULL,           -- e.g. "quantitative-finqa-0"
    question        TEXT NOT NULL,
    expected_answer TEXT,
    context_text    TEXT,                     -- accompanying financial text
    table_data      JSONB NOT NULL,           -- parsed 2D array [[headers], [row1], ...]
    table_string    TEXT,                     -- human-readable text version of table
    num_rows        INT DEFAULT 0,
    num_cols        INT DEFAULT 0,
    headers         TEXT[],                   -- column headers extracted from first row
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_finqa_tenant ON finqa_tables(tenant_id);
CREATE INDEX IF NOT EXISTS idx_finqa_qid ON finqa_tables(question_id);

-- 2. TAT-QA tables (150 questions, tables embedded in context)
CREATE TABLE IF NOT EXISTS tatqa_tables (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL DEFAULT 'benchmark',
    question_id     TEXT NOT NULL,           -- e.g. "quantitative-tatqa-0"
    question        TEXT NOT NULL,
    expected_answer TEXT,
    context_text    TEXT,                     -- full context (may include both text and tables)
    table_data      JSONB,                    -- extracted table data if parseable
    table_string    TEXT,                     -- human-readable text version of table
    num_rows        INT DEFAULT 0,
    num_cols        INT DEFAULT 0,
    headers         TEXT[],
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_tatqa_tenant ON tatqa_tables(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tatqa_qid ON tatqa_tables(question_id);

-- 3. ConvFinQA tables (100 questions, conversational financial QA)
CREATE TABLE IF NOT EXISTS convfinqa_tables (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL DEFAULT 'benchmark',
    question_id     TEXT NOT NULL,           -- e.g. "quantitative-convfinqa-0"
    question        TEXT NOT NULL,
    expected_answer TEXT,
    context_text    TEXT,                     -- accompanying financial text
    table_data      JSONB NOT NULL,           -- parsed 2D array [[headers], [row1], ...]
    table_string    TEXT,                     -- human-readable text version of table
    num_rows        INT DEFAULT 0,
    num_cols        INT DEFAULT 0,
    headers         TEXT[],
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_convfinqa_tenant ON convfinqa_tables(tenant_id);
CREATE INDEX IF NOT EXISTS idx_convfinqa_qid ON convfinqa_tables(question_id);

-- 4. Unified view for the RAG workflow to query across all Phase 2 tables
CREATE OR REPLACE VIEW v_phase2_financial_questions AS
SELECT
    question_id,
    'finqa' AS dataset,
    question,
    expected_answer,
    context_text,
    table_data,
    table_string,
    num_rows,
    num_cols,
    headers,
    tenant_id
FROM finqa_tables
WHERE tenant_id = 'benchmark'
UNION ALL
SELECT
    question_id,
    'tatqa' AS dataset,
    question,
    expected_answer,
    context_text,
    table_data,
    table_string,
    num_rows,
    num_cols,
    headers,
    tenant_id
FROM tatqa_tables
WHERE tenant_id = 'benchmark'
UNION ALL
SELECT
    question_id,
    'convfinqa' AS dataset,
    question,
    expected_answer,
    context_text,
    table_data,
    table_string,
    num_rows,
    num_cols,
    headers,
    tenant_id
FROM convfinqa_tables
WHERE tenant_id = 'benchmark';

-- ============================================================
-- Verify table creation
-- ============================================================
SELECT 'finqa_tables' AS tbl, COUNT(*) AS rows FROM finqa_tables
UNION ALL
SELECT 'tatqa_tables', COUNT(*) FROM tatqa_tables
UNION ALL
SELECT 'convfinqa_tables', COUNT(*) FROM convfinqa_tables
ORDER BY tbl;
