-- Job Board Verification Schema Migration
-- Run this in Supabase SQL Editor after the hunt migration
-- This adds tables for tracking job uniqueness across job boards (LinkedIn, Indeed, etc.)

-- ============================================
-- JOB BOARD LISTINGS TABLE
-- Stores verification results for each job on each board
-- ============================================
CREATE TABLE IF NOT EXISTS job_board_listings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  board TEXT NOT NULL,  -- 'linkedin', 'indeed', 'glassdoor', 'ziprecruiter', etc.
  
  -- Verification result
  found BOOLEAN NOT NULL,
  confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),  -- 0-1, based on search result relevance
  listing_url TEXT,  -- URL of the listing if found
  
  -- Search metadata
  search_query TEXT,  -- The query used for verification
  search_result_count INTEGER,  -- Number of results returned
  
  -- Timestamps
  verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  -- Unique constraint: one verification per job per board
  UNIQUE(job_id, board)
);

-- Indexes for job_board_listings
CREATE INDEX IF NOT EXISTS idx_job_board_listings_job ON job_board_listings(job_id);
CREATE INDEX IF NOT EXISTS idx_job_board_listings_board ON job_board_listings(board);
CREATE INDEX IF NOT EXISTS idx_job_board_listings_found ON job_board_listings(found);
CREATE INDEX IF NOT EXISTS idx_job_board_listings_verified_at ON job_board_listings(verified_at DESC);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_job_board_listings_board_found ON job_board_listings(board, found);

-- ============================================
-- VERIFICATION RUNS TABLE
-- Tracks each verification batch run for monitoring and stats
-- ============================================
CREATE TABLE IF NOT EXISTS verification_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  board TEXT NOT NULL,  -- Which board was checked
  status TEXT DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
  
  -- Stats
  jobs_checked INTEGER DEFAULT 0,
  jobs_found INTEGER DEFAULT 0,  -- Found on the board
  jobs_unique INTEGER DEFAULT 0,  -- NOT found on the board (unique to us)
  uniqueness_rate FLOAT CHECK (uniqueness_rate >= 0 AND uniqueness_rate <= 1),  -- jobs_unique / jobs_checked
  
  -- Error tracking
  error_message TEXT,
  
  -- Timestamps
  started_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

-- Indexes for verification_runs
CREATE INDEX IF NOT EXISTS idx_verification_runs_board ON verification_runs(board);
CREATE INDEX IF NOT EXISTS idx_verification_runs_status ON verification_runs(status);
CREATE INDEX IF NOT EXISTS idx_verification_runs_started_at ON verification_runs(started_at DESC);

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================

-- Enable RLS
ALTER TABLE job_board_listings ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_runs ENABLE ROW LEVEL SECURITY;

-- Service role has full access (for backend)
CREATE POLICY "Service role has full access to job_board_listings" ON job_board_listings
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to verification_runs" ON verification_runs
  FOR ALL USING (auth.role() = 'service_role');

-- ============================================
-- VIEWS
-- ============================================

-- View for current uniqueness stats per board
CREATE OR REPLACE VIEW verification_stats AS
SELECT 
    board,
    COUNT(*) as total_verified,
    COUNT(*) FILTER (WHERE found = TRUE) as found_on_board,
    COUNT(*) FILTER (WHERE found = FALSE) as unique_to_us,
    ROUND(
        (COUNT(*) FILTER (WHERE found = FALSE)::NUMERIC / NULLIF(COUNT(*), 0) * 100),
        2
    ) as uniqueness_rate_percent,
    MAX(verified_at) as last_verified_at
FROM job_board_listings
GROUP BY board;

-- View for jobs that need verification (not verified recently or never)
CREATE OR REPLACE VIEW jobs_needing_verification AS
SELECT 
    j.id as job_id,
    j.title,
    j.source_url,
    c.name as company_name,
    j.created_at,
    j.posted_at,
    COALESCE(
        (SELECT MAX(verified_at) FROM job_board_listings WHERE job_id = j.id),
        '1970-01-01'::TIMESTAMPTZ
    ) as last_verified_at
FROM jobs j
JOIN companies c ON j.company_id = c.id
WHERE j.is_active = TRUE
ORDER BY last_verified_at ASC, j.created_at DESC;

-- ============================================
-- FUNCTIONS
-- ============================================

-- Function to get verification summary
CREATE OR REPLACE FUNCTION get_verification_summary()
RETURNS TABLE (
    board TEXT,
    total_jobs BIGINT,
    verified_jobs BIGINT,
    unique_jobs BIGINT,
    found_jobs BIGINT,
    uniqueness_rate NUMERIC,
    coverage_rate NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    WITH job_count AS (
        SELECT COUNT(*) as total FROM jobs WHERE is_active = TRUE
    ),
    board_stats AS (
        SELECT 
            jbl.board,
            COUNT(*) as verified,
            COUNT(*) FILTER (WHERE found = FALSE) as unique_count,
            COUNT(*) FILTER (WHERE found = TRUE) as found_count
        FROM job_board_listings jbl
        JOIN jobs j ON jbl.job_id = j.id
        WHERE j.is_active = TRUE
        GROUP BY jbl.board
    )
    SELECT 
        bs.board,
        jc.total as total_jobs,
        bs.verified as verified_jobs,
        bs.unique_count as unique_jobs,
        bs.found_count as found_jobs,
        ROUND((bs.unique_count::NUMERIC / NULLIF(bs.verified, 0) * 100), 2) as uniqueness_rate,
        ROUND((bs.verified::NUMERIC / NULLIF(jc.total, 0) * 100), 2) as coverage_rate
    FROM board_stats bs
    CROSS JOIN job_count jc
    ORDER BY bs.board;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to get jobs for verification (sampling strategy)
CREATE OR REPLACE FUNCTION get_jobs_for_verification(
    p_board TEXT,
    p_limit INTEGER DEFAULT 100,
    p_reverify_after_days INTEGER DEFAULT 7
)
RETURNS TABLE (
    job_id UUID,
    title TEXT,
    company_name TEXT,
    source_url TEXT,
    last_verified_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        j.id,
        j.title,
        c.name,
        j.source_url,
        jbl.verified_at
    FROM jobs j
    JOIN companies c ON j.company_id = c.id
    LEFT JOIN job_board_listings jbl ON j.id = jbl.job_id AND jbl.board = p_board
    WHERE j.is_active = TRUE
      AND (
        jbl.verified_at IS NULL  -- Never verified
        OR jbl.verified_at < NOW() - (p_reverify_after_days || ' days')::INTERVAL  -- Needs re-verification
      )
    ORDER BY 
        jbl.verified_at NULLS FIRST,  -- Prioritize never-verified
        j.created_at DESC  -- Then prioritize newer jobs
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;
