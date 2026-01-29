-- Migration: Add pipeline_runs table for tracking pipeline execution history
-- This table stores logs for each pipeline run (crawl, enrich, embeddings)

-- Create pipeline_runs table
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage VARCHAR(50) NOT NULL,  -- 'crawl', 'enrich', 'embeddings'
    status VARCHAR(20) NOT NULL DEFAULT 'running',  -- 'running', 'completed', 'failed'
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    processed INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    error TEXT,
    current_step TEXT,
    cascade BOOLEAN DEFAULT FALSE,
    logs JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for querying by stage and status
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_stage ON pipeline_runs(stage);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at ON pipeline_runs(started_at DESC);

-- Add crawl_attempts column to companies if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'companies' AND column_name = 'crawl_attempts'
    ) THEN
        ALTER TABLE companies ADD COLUMN crawl_attempts INTEGER DEFAULT 0;
    END IF;
END $$;

-- Create index on crawl_attempts for efficient queries
CREATE INDEX IF NOT EXISTS idx_companies_crawl_attempts ON companies(crawl_attempts) WHERE is_active = true;

COMMENT ON TABLE pipeline_runs IS 'Tracks execution history of pipeline stages (crawl, enrich, embeddings)';
COMMENT ON COLUMN pipeline_runs.stage IS 'Pipeline stage: crawl, enrich, or embeddings';
COMMENT ON COLUMN pipeline_runs.status IS 'Current status: running, completed, or failed';
COMMENT ON COLUMN pipeline_runs.cascade IS 'Whether this run cascades to subsequent stages';
COMMENT ON COLUMN pipeline_runs.logs IS 'JSON array of log entries with timestamp, level, and message';
