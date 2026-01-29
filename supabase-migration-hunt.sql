-- Hunt Database Schema Migration
-- Run this in Supabase SQL Editor after the initial waitlist migration

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For text search

-- ============================================
-- COMPANIES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS companies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  domain TEXT UNIQUE,
  careers_url TEXT,
  ats_type TEXT CHECK (ats_type IN ('greenhouse', 'lever', 'ashby', 'workday', 'custom', NULL)),
  ats_identifier TEXT,  -- e.g., "stripe" for boards.greenhouse.io/stripe
  crawl_priority INTEGER DEFAULT 50 CHECK (crawl_priority >= 0 AND crawl_priority <= 100),
  last_crawled_at TIMESTAMPTZ,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for companies
CREATE INDEX IF NOT EXISTS idx_companies_ats_type ON companies(ats_type);
CREATE INDEX IF NOT EXISTS idx_companies_active ON companies(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_companies_crawl_priority ON companies(crawl_priority DESC);

-- ============================================
-- CRAWL SNAPSHOTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS crawl_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  html_hash TEXT,  -- SHA256 for change detection
  html_content TEXT,  -- Store raw HTML (can be large)
  status_code INTEGER,
  rendered BOOLEAN DEFAULT FALSE,  -- Was JS rendered?
  crawled_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for crawl_snapshots
CREATE INDEX IF NOT EXISTS idx_crawl_snapshots_company ON crawl_snapshots(company_id);
CREATE INDEX IF NOT EXISTS idx_crawl_snapshots_hash ON crawl_snapshots(html_hash);
CREATE INDEX IF NOT EXISTS idx_crawl_snapshots_crawled_at ON crawl_snapshots(crawled_at DESC);

-- ============================================
-- RAW JOBS TABLE (before normalization)
-- ============================================
CREATE TABLE IF NOT EXISTS jobs_raw (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
  source_url TEXT NOT NULL,
  title_raw TEXT,
  description_raw TEXT,
  location_raw TEXT,
  department_raw TEXT,
  employment_type_raw TEXT,
  posted_at_raw TEXT,
  salary_raw TEXT,
  extracted_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(company_id, source_url)
);

-- Indexes for jobs_raw
CREATE INDEX IF NOT EXISTS idx_jobs_raw_company ON jobs_raw(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_raw_extracted_at ON jobs_raw(extracted_at DESC);

-- ============================================
-- CANONICAL JOBS TABLE (normalized)
-- ============================================
CREATE TABLE IF NOT EXISTS jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
  raw_job_id UUID REFERENCES jobs_raw(id) ON DELETE SET NULL,
  
  -- Core fields
  title TEXT NOT NULL,
  description TEXT,
  source_url TEXT NOT NULL,
  
  -- Normalized fields
  role_family TEXT NOT NULL CHECK (role_family IN (
    'software_engineering', 'infrastructure', 'data', 'product', 'design',
    'engineering_management', 'sales', 'marketing', 'operations', 'finance',
    'legal', 'people', 'customer_success', 'other'
  )),
  role_specialization TEXT,  -- frontend, backend, fullstack, ios, android, etc.
  seniority TEXT CHECK (seniority IN ('intern', 'junior', 'mid', 'senior', 'staff', 'principal', 'director', 'vp', 'c_level', NULL)),
  location_type TEXT CHECK (location_type IN ('remote', 'hybrid', 'onsite', NULL)),
  locations TEXT[],  -- Normalized location strings
  skills TEXT[],  -- Normalized skill tags
  min_salary INTEGER,
  max_salary INTEGER,
  employment_type TEXT CHECK (employment_type IN ('full_time', 'part_time', 'contract', 'freelance', 'internship', NULL)),
  
  -- Metadata
  posted_at TIMESTAMPTZ,
  freshness_score FLOAT CHECK (freshness_score >= 0 AND freshness_score <= 1),
  embedding vector(384),  -- MiniLM embeddings
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(company_id, source_url)
);

-- Indexes for jobs
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_role_family ON jobs(role_family);
CREATE INDEX IF NOT EXISTS idx_jobs_seniority ON jobs(seniority);
CREATE INDEX IF NOT EXISTS idx_jobs_location_type ON jobs(location_type);
CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_jobs_posted_at ON jobs(posted_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_freshness ON jobs(freshness_score DESC NULLS LAST);

-- Vector index for semantic search (IVFFlat)
CREATE INDEX IF NOT EXISTS idx_jobs_embedding ON jobs USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- GIN index for skills array search
CREATE INDEX IF NOT EXISTS idx_jobs_skills ON jobs USING GIN (skills);

-- ============================================
-- CANDIDATE PROFILES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS candidate_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  waitlist_id UUID REFERENCES waitlist(id) ON DELETE SET NULL UNIQUE,
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  
  -- Preferences
  role_families TEXT[],  -- Derived from waitlist field
  seniority TEXT CHECK (seniority IN ('intern', 'junior', 'mid', 'senior', 'staff', 'principal', 'director', 'vp', 'c_level', NULL)),
  min_salary INTEGER,
  locations TEXT[],  -- Normalized from country
  location_types TEXT[] CHECK (location_types <@ ARRAY['remote', 'hybrid', 'onsite']),
  role_types TEXT[] CHECK (role_types <@ ARRAY['permanent', 'contract', 'freelance']),
  skills TEXT[],
  exclusions TEXT[],  -- Companies/keywords to exclude
  
  -- Matching
  embedding vector(384),
  last_matched_at TIMESTAMPTZ,
  last_notified_at TIMESTAMPTZ,
  
  -- Metadata
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for candidate_profiles
CREATE INDEX IF NOT EXISTS idx_candidates_email ON candidate_profiles(email);
CREATE INDEX IF NOT EXISTS idx_candidates_waitlist ON candidate_profiles(waitlist_id);
CREATE INDEX IF NOT EXISTS idx_candidates_active ON candidate_profiles(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_candidates_embedding ON candidate_profiles USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================
-- MATCHES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS matches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id UUID REFERENCES candidate_profiles(id) ON DELETE CASCADE,
  job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
  
  -- Match details
  score FLOAT NOT NULL CHECK (score >= 0 AND score <= 1),
  hard_match BOOLEAN DEFAULT FALSE,  -- Passed all hard constraints
  match_reasons JSONB,  -- Explanation factors
  
  -- Tracking
  shown_at TIMESTAMPTZ,
  clicked_at TIMESTAMPTZ,
  applied_at TIMESTAMPTZ,
  dismissed_at TIMESTAMPTZ,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(candidate_id, job_id)
);

-- Indexes for matches
CREATE INDEX IF NOT EXISTS idx_matches_candidate ON matches(candidate_id);
CREATE INDEX IF NOT EXISTS idx_matches_job ON matches(job_id);
CREATE INDEX IF NOT EXISTS idx_matches_score ON matches(score DESC);
CREATE INDEX IF NOT EXISTS idx_matches_created_at ON matches(created_at DESC);

-- ============================================
-- METRICS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  value FLOAT NOT NULL,
  labels JSONB,
  recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for metrics
CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(name);
CREATE INDEX IF NOT EXISTS idx_metrics_recorded_at ON metrics(recorded_at DESC);

-- Partition metrics by time (optional, for scale)
-- CREATE INDEX IF NOT EXISTS idx_metrics_name_time ON metrics(name, recorded_at DESC);

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================

-- Enable RLS on all tables
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE crawl_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs_raw ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE metrics ENABLE ROW LEVEL SECURITY;

-- Public read access for jobs (for job feed)
CREATE POLICY "Public can read active jobs" ON jobs
  FOR SELECT USING (is_active = TRUE);

-- Public read access for companies (for job display)
CREATE POLICY "Public can read active companies" ON companies
  FOR SELECT USING (is_active = TRUE);

-- Candidates can read their own profile
CREATE POLICY "Users can read own profile" ON candidate_profiles
  FOR SELECT USING (auth.email() = email);

-- Candidates can update their own profile
CREATE POLICY "Users can update own profile" ON candidate_profiles
  FOR UPDATE USING (auth.email() = email);

-- Candidates can read their own matches
CREATE POLICY "Users can read own matches" ON matches
  FOR SELECT USING (
    candidate_id IN (
      SELECT id FROM candidate_profiles WHERE email = auth.email()
    )
  );

-- Service role has full access (for backend)
CREATE POLICY "Service role has full access to companies" ON companies
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to crawl_snapshots" ON crawl_snapshots
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to jobs_raw" ON jobs_raw
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to jobs" ON jobs
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to candidate_profiles" ON candidate_profiles
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to matches" ON matches
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to metrics" ON metrics
  FOR ALL USING (auth.role() = 'service_role');

-- ============================================
-- FUNCTIONS
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_candidate_profiles_updated_at
    BEFORE UPDATE ON candidate_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to calculate freshness score
CREATE OR REPLACE FUNCTION calculate_freshness_score(posted TIMESTAMPTZ, half_life_days INTEGER DEFAULT 7)
RETURNS FLOAT AS $$
DECLARE
    days_old FLOAT;
BEGIN
    IF posted IS NULL THEN
        RETURN 0.5;  -- Default for unknown dates
    END IF;
    days_old := EXTRACT(EPOCH FROM (NOW() - posted)) / 86400.0;
    RETURN POWER(0.5, days_old / half_life_days);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to find similar jobs using vector similarity
CREATE OR REPLACE FUNCTION find_similar_jobs(
    target_embedding vector(384),
    limit_count INTEGER DEFAULT 10,
    min_similarity FLOAT DEFAULT 0.5
)
RETURNS TABLE (
    job_id UUID,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        j.id,
        1 - (j.embedding <=> target_embedding) as similarity
    FROM jobs j
    WHERE j.is_active = TRUE
      AND j.embedding IS NOT NULL
      AND 1 - (j.embedding <=> target_embedding) >= min_similarity
    ORDER BY j.embedding <=> target_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================
-- VIEWS
-- ============================================

-- View for job feed with company info
CREATE OR REPLACE VIEW job_feed AS
SELECT 
    j.id,
    j.title,
    j.role_family,
    j.role_specialization,
    j.seniority,
    j.location_type,
    j.locations,
    j.skills,
    j.min_salary,
    j.max_salary,
    j.employment_type,
    j.source_url,
    j.posted_at,
    j.freshness_score,
    j.created_at,
    c.id as company_id,
    c.name as company_name,
    c.domain as company_domain
FROM jobs j
JOIN companies c ON j.company_id = c.id
WHERE j.is_active = TRUE AND c.is_active = TRUE;

-- View for candidate matches with job and company info
CREATE OR REPLACE VIEW candidate_matches AS
SELECT 
    m.id as match_id,
    m.candidate_id,
    m.score,
    m.hard_match,
    m.match_reasons,
    m.shown_at,
    m.clicked_at,
    m.created_at as matched_at,
    j.id as job_id,
    j.title as job_title,
    j.role_family,
    j.seniority,
    j.location_type,
    j.locations,
    j.source_url,
    j.posted_at,
    c.id as company_id,
    c.name as company_name,
    c.domain as company_domain
FROM matches m
JOIN jobs j ON m.job_id = j.id
JOIN companies c ON j.company_id = c.id
WHERE j.is_active = TRUE;

-- ============================================
-- SEED DATA HELPER
-- ============================================

-- Function to seed initial companies (call from backend)
-- This is just a helper, actual seeding done via API
CREATE OR REPLACE FUNCTION seed_company(
    p_name TEXT,
    p_domain TEXT,
    p_careers_url TEXT,
    p_ats_type TEXT,
    p_ats_identifier TEXT,
    p_priority INTEGER DEFAULT 50
)
RETURNS UUID AS $$
DECLARE
    new_id UUID;
BEGIN
    INSERT INTO companies (name, domain, careers_url, ats_type, ats_identifier, crawl_priority)
    VALUES (p_name, p_domain, p_careers_url, p_ats_type, p_ats_identifier, p_priority)
    ON CONFLICT (domain) DO UPDATE SET
        name = EXCLUDED.name,
        careers_url = EXCLUDED.careers_url,
        ats_type = EXCLUDED.ats_type,
        ats_identifier = EXCLUDED.ats_identifier,
        crawl_priority = EXCLUDED.crawl_priority
    RETURNING id INTO new_id;
    
    RETURN new_id;
END;
$$ LANGUAGE plpgsql;
