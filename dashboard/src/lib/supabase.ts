/**
 * Supabase Client for Production Dashboard
 *
 * Connects directly to Supabase for live data fetching.
 * Used when deployed to Vercel (no backend proxy available).
 */

import { createClient } from '@supabase/supabase-js';

// Supabase configuration from environment variables
// REQUIRED: Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in Vercel/local .env
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error(
    'Missing Supabase configuration. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY environment variables.'
  );
}

// Create Supabase client
export const supabase = createClient(supabaseUrl, supabaseAnonKey);

/**
 * Database Types (matching Supabase tables)
 */
export interface Company {
  id: string;
  company_name: string;
  domain: string | null;
  close_lead_id: string | null;
  close_lead_url: string | null;
  icp_tier: string | null;
  icp_score: number | null;
  current_stage: string | null;
  priority_score: number | null;
  has_phone: boolean | null;
  has_email: boolean | null;
  enrichment_status: string | null;
  created_at: string;
  updated_at: string | null;
  // AI columns
  ai_personal_hooks: string | null;
  ai_company_story: string | null;
  ai_pain_points: string | null;
  ai_enriched_at: string | null;
}

export interface Contact {
  id: string;
  company_id: string | null;
  full_name: string | null;
  email: string | null;
  phone: string | null;
  title: string | null;
  is_atl: boolean | null;
  linkedin_url: string | null;
  created_at: string;
}

export interface AgentRun {
  id: string;
  agent_type: string;
  status: 'running' | 'completed' | 'failed';
  started_at: string;
  completed_at: string | null;
  metadata: Record<string, unknown> | null;
}

/**
 * Fetch functions for dashboard data
 */

export async function getCompanyStats() {
  const { data, error } = await supabase
    .from('dim_companies')
    .select('id, icp_tier, current_stage, enrichment_status, has_phone, has_email', { count: 'exact' });

  if (error) throw error;

  const stats = {
    total: data?.length || 0,
    byTier: {
      platinum: data?.filter(c => c.icp_tier === 'PLATINUM').length || 0,
      gold: data?.filter(c => c.icp_tier === 'GOLD').length || 0,
      silver: data?.filter(c => c.icp_tier === 'SILVER').length || 0,
      bronze: data?.filter(c => c.icp_tier === 'BRONZE').length || 0,
    },
    enriched: data?.filter(c => c.enrichment_status === 'complete').length || 0,
    withPhone: data?.filter(c => c.has_phone).length || 0,
    withEmail: data?.filter(c => c.has_email).length || 0,
  };

  return stats;
}

export async function getContactStats() {
  const { data, error } = await supabase
    .from('dim_contacts')
    .select('id, is_atl, email, phone', { count: 'exact' });

  if (error) throw error;

  return {
    total: data?.length || 0,
    atl: data?.filter(c => c.is_atl).length || 0,
    btl: data?.filter(c => !c.is_atl).length || 0,
    withEmail: data?.filter(c => c.email).length || 0,
    withPhone: data?.filter(c => c.phone).length || 0,
  };
}

export async function getRecentEnrichments(limit = 10) {
  const { data, error } = await supabase
    .from('dim_companies')
    .select('id, company_name, domain, icp_tier, icp_score, ai_enriched_at')
    .not('ai_enriched_at', 'is', null)
    .order('ai_enriched_at', { ascending: false })
    .limit(limit);

  if (error) throw error;
  return data || [];
}

export async function getTopLeads(limit = 20) {
  const { data, error } = await supabase
    .from('dim_companies')
    .select('*')
    .not('current_stage', 'in', '("customer","do_not_contact")')
    .order('priority_score', { ascending: false, nullsFirst: false })
    .limit(limit);

  if (error) throw error;
  return data || [];
}

/**
 * Real-time subscription for live updates
 */
export function subscribeToEnrichments(callback: (company: Company) => void) {
  const subscription = supabase
    .channel('enrichment-updates')
    .on(
      'postgres_changes',
      {
        event: 'UPDATE',
        schema: 'public',
        table: 'dim_companies',
        filter: 'ai_enriched_at=neq.null',
      },
      (payload) => {
        callback(payload.new as Company);
      }
    )
    .subscribe();

  return () => {
    supabase.removeChannel(subscription);
  };
}
