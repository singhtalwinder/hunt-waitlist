import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

export type WaitlistEntry = {
  id: string
  name: string
  email: string
  created_at: string
}

export type WaitlistDetails = {
  id: string
  waitlist_id: string
  field: string
  seniority: string
  expected_pay: number
  country: string
  work_type: string[]
  role_type: string[]
  created_at: string
}
