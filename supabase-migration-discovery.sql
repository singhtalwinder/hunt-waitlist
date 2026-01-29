-- Discovery Engine Database Migration
-- Run this in Supabase SQL Editor after the hunt migration

-- ============================================
-- ADD DISCOVERY COLUMNS TO COMPANIES TABLE
-- ============================================

-- Add new columns to companies table
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS website_url TEXT,
ADD COLUMN IF NOT EXISTS discovery_source TEXT,
ADD COLUMN IF NOT EXISTS discovered_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS country TEXT,
ADD COLUMN IF NOT EXISTS location TEXT,
ADD COLUMN IF NOT EXISTS description TEXT,
ADD COLUMN IF NOT EXISTS industry TEXT,
ADD COLUMN IF NOT EXISTS employee_count INTEGER,
ADD COLUMN IF NOT EXISTS funding_stage TEXT;

-- Add constraint for country (ISO 3166-1 alpha-2)
ALTER TABLE companies 
ADD CONSTRAINT companies_country_length CHECK (country IS NULL OR length(country) = 2);

-- Index for discovery queries
CREATE INDEX IF NOT EXISTS idx_companies_discovery_source ON companies(discovery_source);
CREATE INDEX IF NOT EXISTS idx_companies_country ON companies(country);
CREATE INDEX IF NOT EXISTS idx_companies_discovered_at ON companies(discovered_at DESC);

-- ============================================
-- DISCOVERY QUEUE TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS discovery_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- Company identification
  name TEXT NOT NULL,
  domain TEXT,
  careers_url TEXT,
  website_url TEXT,
  
  -- Source info
  source TEXT NOT NULL,
  source_url TEXT,
  
  -- Location info
  location TEXT,
  country TEXT CHECK (country IS NULL OR length(country) = 2),
  
  -- Additional metadata
  description TEXT,
  industry TEXT,
  employee_count INTEGER,
  funding_stage TEXT,
  
  -- ATS info if detected
  ats_type TEXT,
  ats_identifier TEXT,
  
  -- Processing status
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'skipped', 'review')),
  error_message TEXT,
  retry_count INTEGER DEFAULT 0,
  
  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  processed_at TIMESTAMPTZ,
  
  -- Reference to created company (if successful)
  company_id UUID REFERENCES companies(id) ON DELETE SET NULL
);

-- Indexes for discovery_queue
CREATE INDEX IF NOT EXISTS idx_discovery_queue_domain ON discovery_queue(domain);
CREATE INDEX IF NOT EXISTS idx_discovery_queue_source ON discovery_queue(source);
CREATE INDEX IF NOT EXISTS idx_discovery_queue_status ON discovery_queue(status);
CREATE INDEX IF NOT EXISTS idx_discovery_queue_created_at ON discovery_queue(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_discovery_queue_pending ON discovery_queue(status, created_at) WHERE status = 'pending';

-- ============================================
-- DISCOVERY RUNS TABLE (for monitoring)
-- ============================================
CREATE TABLE IF NOT EXISTS discovery_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  source TEXT NOT NULL,
  status TEXT DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
  
  -- Stats
  total_discovered INTEGER DEFAULT 0,
  new_companies INTEGER DEFAULT 0,
  updated_companies INTEGER DEFAULT 0,
  skipped_duplicates INTEGER DEFAULT 0,
  filtered_non_us INTEGER DEFAULT 0,
  errors INTEGER DEFAULT 0,
  
  error_message TEXT,
  
  -- Progress logs - list of log entries with timestamp, level, message
  -- Each entry: {"ts": "2024-01-01T12:00:00Z", "level": "info", "msg": "...", "data": {...}}
  logs JSONB DEFAULT '[]'::jsonb,
  
  -- Current progress info for real-time UI updates
  current_step TEXT,
  progress_count INTEGER DEFAULT 0,
  progress_total INTEGER,
  
  started_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

-- Add new columns to existing discovery_runs table (if table already exists)
ALTER TABLE discovery_runs 
ADD COLUMN IF NOT EXISTS logs JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS current_step TEXT,
ADD COLUMN IF NOT EXISTS progress_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS progress_total INTEGER;

-- Indexes for discovery_runs
CREATE INDEX IF NOT EXISTS idx_discovery_runs_source ON discovery_runs(source);
CREATE INDEX IF NOT EXISTS idx_discovery_runs_status ON discovery_runs(status);
CREATE INDEX IF NOT EXISTS idx_discovery_runs_started_at ON discovery_runs(started_at DESC);

-- ============================================
-- ROW LEVEL SECURITY POLICIES
-- ============================================

-- Enable RLS on new tables
ALTER TABLE discovery_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE discovery_runs ENABLE ROW LEVEL SECURITY;

-- Service role has full access to discovery tables
CREATE POLICY "Service role full access to discovery_queue" ON discovery_queue
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Service role full access to discovery_runs" ON discovery_runs
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Function to get next item from discovery queue
CREATE OR REPLACE FUNCTION get_next_discovery_item()
RETURNS SETOF discovery_queue AS $$
BEGIN
  RETURN QUERY
  UPDATE discovery_queue
  SET status = 'processing', processed_at = NOW()
  WHERE id = (
    SELECT id FROM discovery_queue
    WHERE status = 'pending'
    ORDER BY created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
  )
  RETURNING *;
END;
$$ LANGUAGE plpgsql;

-- Function to mark discovery item as completed
CREATE OR REPLACE FUNCTION complete_discovery_item(
  item_id UUID,
  new_company_id UUID DEFAULT NULL
)
RETURNS void AS $$
BEGIN
  UPDATE discovery_queue
  SET 
    status = 'completed',
    company_id = new_company_id,
    processed_at = NOW()
  WHERE id = item_id;
END;
$$ LANGUAGE plpgsql;

-- Function to mark discovery item as failed
CREATE OR REPLACE FUNCTION fail_discovery_item(
  item_id UUID,
  error_msg TEXT
)
RETURNS void AS $$
BEGIN
  UPDATE discovery_queue
  SET 
    status = CASE WHEN retry_count >= 3 THEN 'failed' ELSE 'pending' END,
    error_message = error_msg,
    retry_count = retry_count + 1,
    processed_at = NOW()
  WHERE id = item_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get discovery stats
CREATE OR REPLACE FUNCTION get_discovery_stats()
RETURNS TABLE (
  source TEXT,
  total_discovered BIGINT,
  completed BIGINT,
  pending BIGINT,
  failed BIGINT
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    dq.source,
    COUNT(*) as total_discovered,
    COUNT(*) FILTER (WHERE dq.status = 'completed') as completed,
    COUNT(*) FILTER (WHERE dq.status = 'pending') as pending,
    COUNT(*) FILTER (WHERE dq.status = 'failed') as failed
  FROM discovery_queue dq
  GROUP BY dq.source
  ORDER BY total_discovered DESC;
END;
$$ LANGUAGE plpgsql;
