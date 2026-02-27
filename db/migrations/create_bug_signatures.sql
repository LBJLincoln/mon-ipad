-- ============================================================
-- Bug Signature Detection Log
-- Migration: create_bug_signatures
-- Source: docs/agentic/agentic-automation-spec.md (Section 1.5)
-- ============================================================
-- Stores detected error patterns (rate limits, auth failures,
-- empty responses, timeouts, credential issues, etc.) with
-- auto-action tracking and acknowledgement workflow.

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
