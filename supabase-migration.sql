-- Run this migration in your Supabase SQL Editor for project: cpuqlgckpkbyvvohhbrf

-- Primary waitlist signups
CREATE TABLE IF NOT EXISTS waitlist (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Additional details (optional, linked to waitlist)
CREATE TABLE IF NOT EXISTS waitlist_details (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  waitlist_id UUID REFERENCES waitlist(id) ON DELETE CASCADE,
  field TEXT,
  seniority TEXT,
  expected_pay INTEGER,
  country TEXT,
  work_type TEXT[],
  role_type TEXT[],
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE waitlist ENABLE ROW LEVEL SECURITY;
ALTER TABLE waitlist_details ENABLE ROW LEVEL SECURITY;

-- Allow anonymous inserts (for waitlist signups)
CREATE POLICY "Allow anonymous inserts" ON waitlist FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anonymous inserts" ON waitlist_details FOR INSERT WITH CHECK (true);
