-- Maintenance System Migration
-- Tracks job verification runs that re-crawl companies to ensure job data is current

-- =====================================================
-- MAINTENANCE RUNS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS maintenance_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Run type
    run_type VARCHAR(50) NOT NULL DEFAULT 'full',  -- 'full', 'company', 'ats_type'
    ats_type VARCHAR(50),  -- If filtering by ATS
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'running',  -- 'running', 'completed', 'failed', 'cancelled'
    current_step VARCHAR(200),
    
    -- Statistics
    companies_checked INT NOT NULL DEFAULT 0,
    jobs_verified INT NOT NULL DEFAULT 0,
    jobs_new INT NOT NULL DEFAULT 0,
    jobs_delisted INT NOT NULL DEFAULT 0,
    jobs_unchanged INT NOT NULL DEFAULT 0,
    errors INT NOT NULL DEFAULT 0,
    
    -- Error tracking
    error_message TEXT,
    
    -- Progress logs - list of log entries
    -- Each entry: {"ts": "2024-01-01T12:00:00Z", "level": "info", "msg": "...", "data": {...}}
    logs JSONB DEFAULT '[]'::jsonb,
    
    -- Timestamps
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Index for status filtering
CREATE INDEX IF NOT EXISTS idx_maintenance_runs_status ON maintenance_runs(status);
CREATE INDEX IF NOT EXISTS idx_maintenance_runs_started_at ON maintenance_runs(started_at DESC);


-- =====================================================
-- JOB MAINTENANCE TRACKING
-- =====================================================

-- Add columns to jobs table for tracking maintenance status
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS last_verified_at TIMESTAMPTZ;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS delisted_at TIMESTAMPTZ;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS delist_reason VARCHAR(100);  -- 'removed_from_ats', 'company_inactive', 'page_not_found'

-- Index for maintenance queries
CREATE INDEX IF NOT EXISTS idx_jobs_last_verified ON jobs(last_verified_at) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_jobs_delisted ON jobs(delisted_at) WHERE is_active = false;


-- =====================================================
-- COMPANY MAINTENANCE TRACKING  
-- =====================================================

-- Add column for tracking last maintenance check
ALTER TABLE companies ADD COLUMN IF NOT EXISTS last_maintenance_at TIMESTAMPTZ;

-- Index for finding companies due for maintenance
CREATE INDEX IF NOT EXISTS idx_companies_last_maintenance 
    ON companies(last_maintenance_at NULLS FIRST) 
    WHERE is_active = true AND ats_type IS NOT NULL;


-- =====================================================
-- HELPER VIEWS
-- =====================================================

-- View: Jobs pending verification (not verified in last 7 days)
-- Includes both standard ATS and custom career page companies
CREATE OR REPLACE VIEW jobs_pending_verification AS
SELECT 
    j.id,
    j.title,
    j.source_url,
    j.company_id,
    c.name as company_name,
    COALESCE(c.ats_type, 'unknown') as ats_type,
    j.created_at,
    j.last_verified_at,
    EXTRACT(DAY FROM NOW() - COALESCE(j.last_verified_at, j.created_at)) as days_since_verified
FROM jobs j
JOIN companies c ON j.company_id = c.id
WHERE j.is_active = true
  AND c.is_active = true
  AND c.careers_url IS NOT NULL
  AND (j.last_verified_at IS NULL OR j.last_verified_at < NOW() - INTERVAL '7 days')
ORDER BY j.last_verified_at NULLS FIRST, j.created_at;


-- View: Recently delisted jobs
CREATE OR REPLACE VIEW recently_delisted_jobs AS
SELECT 
    j.id,
    j.title,
    j.source_url,
    j.company_id,
    c.name as company_name,
    c.ats_type,
    j.delisted_at,
    j.delist_reason,
    j.created_at
FROM jobs j
JOIN companies c ON j.company_id = c.id
WHERE j.is_active = false
  AND j.delisted_at IS NOT NULL
  AND j.delisted_at > NOW() - INTERVAL '30 days'
ORDER BY j.delisted_at DESC;


-- View: Maintenance statistics by ATS (includes custom and unknown types)
CREATE OR REPLACE VIEW maintenance_stats_by_ats AS
SELECT 
    COALESCE(c.ats_type, 'unknown') as ats_type,
    COUNT(DISTINCT c.id) as companies,
    COUNT(j.id) as total_jobs,
    COUNT(j.id) FILTER (WHERE j.is_active = true) as active_jobs,
    COUNT(j.id) FILTER (WHERE j.is_active = false AND j.delisted_at IS NOT NULL) as delisted_jobs,
    COUNT(j.id) FILTER (
        WHERE j.is_active = true 
        AND (j.last_verified_at IS NULL OR j.last_verified_at < NOW() - INTERVAL '7 days')
    ) as pending_verification,
    AVG(EXTRACT(DAY FROM NOW() - j.last_verified_at)) FILTER (WHERE j.last_verified_at IS NOT NULL) as avg_days_since_verified
FROM companies c
LEFT JOIN jobs j ON j.company_id = c.id
WHERE c.is_active = true
  AND c.careers_url IS NOT NULL
GROUP BY COALESCE(c.ats_type, 'unknown')
ORDER BY companies DESC;


-- =====================================================
-- RLS POLICIES (if RLS is enabled)
-- =====================================================

-- Maintenance runs are admin-only (no RLS needed for now)
-- ALTER TABLE maintenance_runs ENABLE ROW LEVEL SECURITY;


-- =====================================================
-- GRANTS
-- =====================================================

-- Grant access to service role
-- GRANT ALL ON maintenance_runs TO service_role;
-- GRANT SELECT ON jobs_pending_verification TO service_role;
-- GRANT SELECT ON recently_delisted_jobs TO service_role;
-- GRANT SELECT ON maintenance_stats_by_ats TO service_role;
