-- ============================================================
-- RAG Benchmark System — Supabase Schema Migration
-- Create documents table for BM25 full-text search
-- ============================================================

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    source TEXT,
    tenant_id TEXT NOT NULL DEFAULT 'benchmark',
    is_obsolete BOOLEAN NOT NULL DEFAULT FALSE,
    embedding_id TEXT, -- To link with Pinecone/Cohere if needed
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    -- Add a tsvector column for full-text search
    content_tsvector TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

-- Index for tenant_id filtering
CREATE INDEX IF NOT EXISTS idx_documents_tenant_id ON documents(tenant_id);

-- GIN index for full-text search on content_tsvector
CREATE INDEX IF NOT EXISTS idx_documents_content_tsvector ON documents USING GIN(content_tsvector);

-- Function to update updated_at on change
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE OR REPLACE TRIGGER update_documents_updated_at
BEFORE UPDATE ON documents
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();