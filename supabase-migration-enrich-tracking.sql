-- Enrichment Failure Tracking Migration
-- Tracks when enrichment fails to prevent infinite retries
-- This is used by the one-click pipeline to skip jobs that failed in the current run

-- Add column to track enrichment failures
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS enrich_failed_at TIMESTAMPTZ;

-- Index for efficient queries (find jobs needing enrichment, skipping recently failed)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_jobs_enrich_failed 
    ON jobs(enrich_failed_at) 
    WHERE description IS NULL AND is_active = true;
