'use client'

/**
 * GTM Pipeline Dashboard
 *
 * Clean, professional dashboard for Coperniq ICP pipeline visibility
 * Shows live agent activity, lead metrics, and pipeline health
 */

import { useState, useEffect, useRef } from 'react'
import { supabase } from '@/lib/supabase'

// ============================================
// TYPES
// ============================================

interface PipelineStats {
  totalLeads: number
  totalContacts: number
  enrichedLeads: number
  platinumLeads: number
  goldLeads: number
  silverLeads: number
  bronzeLeads: number
  hotLeads: number
  leadsWithPhone: number
  leadsWithEmail: number
  leadsAddedToday: number
  leadsAddedThisWeek: number
}

interface ICPSegments {
  hvac: number
  solar: number
  electrical: number
  plumbing: number
  roofing: number
  resiOnly: number
  commercial: number
  resimercial: number
  cAndI: number
  multiTrade: number
  avgTradeCount: number
  avgLocations: number
  avgEmployees: number
}

interface AgentStatus {
  name: string
  status: 'active' | 'idle' | 'sleeping'
  lastRun: string
  tasksCompleted: number
  schedule: string
}

interface ActivityLog {
  id: number
  text: string
  type: 'system' | 'agent' | 'success' | 'enrichment' | 'discovery'
  timestamp: string
}

// ============================================
// CONSTANTS
// ============================================

const AGENTS: AgentStatus[] = [
  { name: 'Lead Scout', status: 'active', lastRun: '', tasksCompleted: 0, schedule: 'Every 30 min' },
  { name: 'ICP Scorer', status: 'idle', lastRun: '', tasksCompleted: 0, schedule: 'Every 15 min' },
  { name: 'Predictor', status: 'active', lastRun: '', tasksCompleted: 0, schedule: 'Every 5 min' },
  { name: 'Briefer', status: 'sleeping', lastRun: '', tasksCompleted: 0, schedule: '7 AM EST' },
  { name: 'Sales Intel', status: 'active', lastRun: '', tasksCompleted: 0, schedule: 'Hourly' },
  { name: 'Outreach', status: 'idle', lastRun: '', tasksCompleted: 0, schedule: 'Hourly' },
]

// ============================================
// COMPONENT
// ============================================

export function MissionControl() {
  const [stats, setStats] = useState<PipelineStats>({
    totalLeads: 0,
    totalContacts: 0,
    enrichedLeads: 0,
    platinumLeads: 0,
    goldLeads: 0,
    silverLeads: 0,
    bronzeLeads: 0,
    hotLeads: 0,
    leadsWithPhone: 0,
    leadsWithEmail: 0,
    leadsAddedToday: 0,
    leadsAddedThisWeek: 0,
  })

  const [segments, setSegments] = useState<ICPSegments>({
    hvac: 0,
    solar: 0,
    electrical: 0,
    plumbing: 0,
    roofing: 0,
    resiOnly: 0,
    commercial: 0,
    resimercial: 0,
    cAndI: 0,
    multiTrade: 0,
    avgTradeCount: 0,
    avgLocations: 0,
    avgEmployees: 0,
  })

  const [topBrands, setTopBrands] = useState<{name: string, count: number}[]>([])
  const [agents, setAgents] = useState<AgentStatus[]>(AGENTS)
  const [activityLog, setActivityLog] = useState<ActivityLog[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const terminalRef = useRef<HTMLDivElement>(null)

  // Fetch stats from Supabase
  useEffect(() => {
    async function fetchStats() {
      try {
        const { data: companies, error: compError } = await supabase
          .from('dim_companies')
          .select(`
            id, icp_tier, enrichment_status, has_phone, has_email, created_at,
            services_offered, oem_brands, trade_count, employee_count, location_count,
            industries_served
          `)

        if (compError) throw compError

        const { data: contacts, error: contError } = await supabase
          .from('dim_contacts')
          .select('id, is_atl')

        if (contError) throw contError

        const now = new Date()
        const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
        const weekStart = new Date(todayStart)
        weekStart.setDate(weekStart.getDate() - 7)

        const newStats: PipelineStats = {
          totalLeads: companies?.length || 0,
          totalContacts: contacts?.length || 0,
          enrichedLeads: companies?.filter(c => c.enrichment_status === 'complete').length || 0,
          platinumLeads: companies?.filter(c => c.icp_tier === 'PLATINUM').length || 0,
          goldLeads: companies?.filter(c => c.icp_tier === 'GOLD').length || 0,
          silverLeads: companies?.filter(c => c.icp_tier === 'SILVER').length || 0,
          bronzeLeads: companies?.filter(c => c.icp_tier === 'BRONZE').length || 0,
          hotLeads: companies?.filter(c => c.has_phone && c.has_email).length || 0,
          leadsWithPhone: companies?.filter(c => c.has_phone).length || 0,
          leadsWithEmail: companies?.filter(c => c.has_email).length || 0,
          leadsAddedToday: companies?.filter(c => new Date(c.created_at) >= todayStart).length || 0,
          leadsAddedThisWeek: companies?.filter(c => new Date(c.created_at) >= weekStart).length || 0,
        }

        // Calculate ICP Segments
        const servicesCheck = (services: string[] | null, keywords: string[]) => {
          if (!services) return false
          const lower = services.map(s => s.toLowerCase())
          return keywords.some(k => lower.some(s => s.includes(k)))
        }

        const hvacCount = companies?.filter(c =>
          servicesCheck(c.services_offered, ['hvac', 'heating', 'cooling', 'air conditioning', 'furnace'])
        ).length || 0

        const solarCount = companies?.filter(c =>
          servicesCheck(c.services_offered, ['solar', 'pv', 'photovoltaic']) ||
          servicesCheck(c.industries_served, ['solar', 'renewable'])
        ).length || 0

        const electricalCount = companies?.filter(c =>
          servicesCheck(c.services_offered, ['electrical', 'electrician', 'wiring'])
        ).length || 0

        const plumbingCount = companies?.filter(c =>
          servicesCheck(c.services_offered, ['plumbing', 'plumber', 'pipe'])
        ).length || 0

        const roofingCount = companies?.filter(c =>
          servicesCheck(c.services_offered, ['roofing', 'roof'])
        ).length || 0

        const resiCount = companies?.filter(c =>
          servicesCheck(c.services_offered, ['residential']) &&
          !servicesCheck(c.services_offered, ['commercial'])
        ).length || 0

        const commercialCount = companies?.filter(c =>
          servicesCheck(c.services_offered, ['commercial']) &&
          !servicesCheck(c.services_offered, ['residential'])
        ).length || 0

        const resimercialCount = companies?.filter(c =>
          servicesCheck(c.services_offered, ['residential']) &&
          servicesCheck(c.services_offered, ['commercial'])
        ).length || 0

        const cAndICount = companies?.filter(c =>
          servicesCheck(c.industries_served, ['industrial', 'c&i', 'commercial solar']) ||
          servicesCheck(c.services_offered, ['industrial', 'commercial solar'])
        ).length || 0

        const multiTradeCount = companies?.filter(c =>
          c.trade_count && c.trade_count >= 3
        ).length || 0

        const withTrades = companies?.filter(c => c.trade_count && c.trade_count > 0) || []
        const withLocations = companies?.filter(c => c.location_count && c.location_count > 0) || []
        const withEmployees = companies?.filter(c => c.employee_count) || []

        const avgTradeCount = withTrades.length > 0
          ? withTrades.reduce((sum, c) => sum + (c.trade_count || 0), 0) / withTrades.length
          : 0

        const avgLocations = withLocations.length > 0
          ? withLocations.reduce((sum, c) => sum + (c.location_count || 0), 0) / withLocations.length
          : 0

        const parseEmployees = (emp: string | null): number => {
          if (!emp) return 0
          const num = parseInt(emp.replace(/[^0-9]/g, ''))
          return isNaN(num) ? 0 : num
        }
        const avgEmployees = withEmployees.length > 0
          ? withEmployees.reduce((sum, c) => sum + parseEmployees(c.employee_count), 0) / withEmployees.length
          : 0

        setSegments({
          hvac: hvacCount,
          solar: solarCount,
          electrical: electricalCount,
          plumbing: plumbingCount,
          roofing: roofingCount,
          resiOnly: resiCount,
          commercial: commercialCount,
          resimercial: resimercialCount,
          cAndI: cAndICount,
          multiTrade: multiTradeCount,
          avgTradeCount: Math.round(avgTradeCount * 10) / 10,
          avgLocations: Math.round(avgLocations * 10) / 10,
          avgEmployees: Math.round(avgEmployees),
        })

        // Calculate OEM brand frequency
        const brandCounts: Record<string, number> = {}
        companies?.forEach(c => {
          if (c.oem_brands && Array.isArray(c.oem_brands)) {
            c.oem_brands.forEach((brand: string) => {
              brandCounts[brand] = (brandCounts[brand] || 0) + 1
            })
          }
        })
        const sortedBrands = Object.entries(brandCounts)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 8)
          .map(([name, count]) => ({ name, count }))
        setTopBrands(sortedBrands)

        setStats(newStats)
        setIsLoading(false)

      } catch (err) {
        console.error('Failed to fetch stats:', err)
        setIsLoading(false)
      }
    }

    fetchStats()
    const interval = setInterval(fetchStats, 30000)
    return () => clearInterval(interval)
  }, [])

  // Fetch activity from lead_audit_log
  useEffect(() => {
    async function fetchActivity() {
      try {
        const { data: auditLogs, error } = await supabase
          .from('lead_audit_log')
          .select('id, event_type, company_name, created_at, details')
          .order('created_at', { ascending: false })
          .limit(20)

        if (error) throw error

        if (auditLogs && auditLogs.length > 0) {
          const realActivity: ActivityLog[] = auditLogs.map((log) => {
            const eventLabel = log.event_type.replace(/_/g, ' ')
            return {
              id: log.id,
              text: `${eventLabel}: ${log.company_name || 'Unknown'}`,
              type: getEventLogType(log.event_type),
              timestamp: new Date(log.created_at).toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
                hour12: true
              })
            }
          })
          setActivityLog(realActivity)
        }
      } catch (err) {
        console.error('Failed to fetch activity:', err)
      }
    }

    fetchActivity()
    const interval = setInterval(fetchActivity, 10000)
    return () => clearInterval(interval)
  }, [])

  // Fetch agent health
  useEffect(() => {
    async function fetchAgentHealth() {
      try {
        const response = await fetch('/api/dashboard/agents')
        if (response.ok) {
          const agentData = await response.json()
          if (Array.isArray(agentData) && agentData.length > 0) {
            const updatedAgents: AgentStatus[] = agentData.map((agent: {
              agent_type: string
              display_name: string
              status: string
              last_execution_at: string
              successful_executions: number
            }) => ({
              name: agent.display_name || formatAgentName(agent.agent_type),
              status: agent.status === 'healthy' ? 'active' as const :
                      agent.status === 'degraded' ? 'idle' as const : 'sleeping' as const,
              lastRun: agent.last_execution_at || '',
              tasksCompleted: agent.successful_executions || 0,
              schedule: getAgentSchedule(agent.agent_type)
            }))
            setAgents(updatedAgents)
          }
        }
      } catch {
        console.log('Backend not available, using static agent list')
      }
    }

    fetchAgentHealth()
    const interval = setInterval(fetchAgentHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  // Auto-scroll activity feed
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [activityLog])

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-slate-200 border-t-slate-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-slate-600">Loading pipeline data...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">GTM Pipeline</h1>
            <p className="text-sm text-slate-500">Coperniq ICP Contractor Intelligence</p>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-500">
              Last updated: {new Date().toLocaleTimeString()}
            </span>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              <span className="text-sm text-slate-600">Live</span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Primary Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <MetricCard
            label="Total Contractors"
            value={stats.totalLeads}
            trend={stats.leadsAddedThisWeek > 0 ? `+${stats.leadsAddedThisWeek} this week` : undefined}
            primary
          />
          <MetricCard label="Decision Makers" value={stats.totalContacts} />
          <MetricCard label="Call Ready" value={stats.hotLeads} highlight />
          <MetricCard label="Enriched" value={stats.enrichedLeads} />
        </div>

        {/* ICP Tiers */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-8">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">ICP Tiers</h2>
          <div className="grid grid-cols-4 gap-4">
            <TierCard tier="Platinum" count={stats.platinumLeads} color="purple" />
            <TierCard tier="Gold" count={stats.goldLeads} color="amber" />
            <TierCard tier="Silver" count={stats.silverLeads} color="slate" />
            <TierCard tier="Bronze" count={stats.bronzeLeads} color="orange" />
          </div>
        </div>

        {/* Two Column Layout */}
        <div className="grid md:grid-cols-2 gap-8 mb-8">
          {/* Trade Verticals */}
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-4">Trade Verticals</h2>
            <div className="space-y-3">
              <VerticalBar label="HVAC" count={segments.hvac} total={stats.totalLeads} />
              <VerticalBar label="Solar" count={segments.solar} total={stats.totalLeads} />
              <VerticalBar label="Electrical" count={segments.electrical} total={stats.totalLeads} />
              <VerticalBar label="Plumbing" count={segments.plumbing} total={stats.totalLeads} />
              <VerticalBar label="Roofing" count={segments.roofing} total={stats.totalLeads} />
            </div>
          </div>

          {/* Market Segments */}
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-4">Market Segments</h2>
            <div className="grid grid-cols-2 gap-4">
              <SegmentCard label="Residential" count={segments.resiOnly} />
              <SegmentCard label="Commercial" count={segments.commercial} />
              <SegmentCard label="Resimercial" count={segments.resimercial} />
              <SegmentCard label="C&I" count={segments.cAndI} />
            </div>
            <div className="mt-4 pt-4 border-t border-slate-100">
              <div className="flex justify-between text-sm">
                <span className="text-slate-500">Multi-Trade (3+)</span>
                <span className="font-medium text-slate-900">{segments.multiTrade}</span>
              </div>
            </div>
          </div>
        </div>

        {/* OEM Brands */}
        {topBrands.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 mb-8">
            <h2 className="text-lg font-semibold text-slate-900 mb-4">Top OEM Brands</h2>
            <div className="flex flex-wrap gap-2">
              {topBrands.map((brand, idx) => (
                <span
                  key={brand.name}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium ${
                    idx === 0 ? 'bg-amber-100 text-amber-800' :
                    idx === 1 ? 'bg-slate-100 text-slate-700' :
                    idx === 2 ? 'bg-orange-100 text-orange-700' :
                    'bg-slate-50 text-slate-600'
                  }`}
                >
                  {brand.name} ({brand.count})
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Agents & Activity */}
        <div className="grid md:grid-cols-2 gap-8">
          {/* Agents */}
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-4">Agent Status</h2>
            <div className="space-y-3">
              {agents.map((agent) => (
                <div
                  key={agent.name}
                  className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0"
                >
                  <div className="flex items-center gap-3">
                    <span className={`w-2 h-2 rounded-full ${
                      agent.status === 'active' ? 'bg-green-500' :
                      agent.status === 'idle' ? 'bg-amber-500' : 'bg-slate-300'
                    }`} />
                    <span className="font-medium text-slate-900">{agent.name}</span>
                  </div>
                  <div className="text-right">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                      agent.status === 'active' ? 'bg-green-100 text-green-700' :
                      agent.status === 'idle' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'
                    }`}>
                      {agent.status === 'active' ? 'Running' :
                       agent.status === 'idle' ? 'Standby' : 'Scheduled'}
                    </span>
                    <p className="text-xs text-slate-400 mt-1">{agent.schedule}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Activity Feed */}
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-4">Recent Activity</h2>
            <div
              ref={terminalRef}
              className="h-64 overflow-y-auto space-y-2"
            >
              {activityLog.length === 0 ? (
                <p className="text-slate-400 text-sm">Waiting for activity...</p>
              ) : (
                activityLog.map((log) => (
                  <div
                    key={log.id}
                    className="flex items-start gap-3 text-sm py-1.5 border-b border-slate-50 last:border-0"
                  >
                    <span className="text-slate-400 text-xs whitespace-nowrap">{log.timestamp}</span>
                    <span className={`capitalize ${getLogColorClass(log.type)}`}>{log.text}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

// ============================================
// SUB-COMPONENTS
// ============================================

function MetricCard({ label, value, trend, primary, highlight }: {
  label: string
  value: number
  trend?: string
  primary?: boolean
  highlight?: boolean
}) {
  return (
    <div className={`rounded-xl p-5 ${
      primary ? 'bg-slate-900 text-white' :
      highlight ? 'bg-green-50 border border-green-200' :
      'bg-white border border-slate-200'
    }`}>
      <p className={`text-sm ${primary ? 'text-slate-400' : 'text-slate-500'}`}>{label}</p>
      <p className={`text-3xl font-semibold mt-1 ${
        primary ? 'text-white' : highlight ? 'text-green-700' : 'text-slate-900'
      }`}>
        {value.toLocaleString()}
      </p>
      {trend && (
        <p className={`text-xs mt-2 ${primary ? 'text-green-400' : 'text-green-600'}`}>{trend}</p>
      )}
    </div>
  )
}

function TierCard({ tier, count, color }: {
  tier: string
  count: number
  color: 'purple' | 'amber' | 'slate' | 'orange'
}) {
  const colorClasses = {
    purple: 'bg-purple-50 border-purple-200 text-purple-700',
    amber: 'bg-amber-50 border-amber-200 text-amber-700',
    slate: 'bg-slate-100 border-slate-200 text-slate-600',
    orange: 'bg-orange-50 border-orange-200 text-orange-700',
  }

  return (
    <div className={`rounded-lg border p-4 text-center ${colorClasses[color]}`}>
      <p className="text-2xl font-semibold">{count.toLocaleString()}</p>
      <p className="text-sm mt-1">{tier}</p>
    </div>
  )
}

function VerticalBar({ label, count, total }: {
  label: string
  count: number
  total: number
}) {
  const percent = total > 0 ? (count / total) * 100 : 0

  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-slate-700">{label}</span>
        <span className="text-slate-500">{count.toLocaleString()}</span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-slate-600 rounded-full transition-all duration-500"
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
    </div>
  )
}

function SegmentCard({ label, count }: {
  label: string
  count: number
}) {
  return (
    <div className="bg-slate-50 rounded-lg p-4">
      <p className="text-2xl font-semibold text-slate-900">{count.toLocaleString()}</p>
      <p className="text-sm text-slate-500">{label}</p>
    </div>
  )
}

function getLogColorClass(type: ActivityLog['type']): string {
  switch (type) {
    case 'success': return 'text-green-600 font-medium'
    case 'enrichment': return 'text-amber-600'
    case 'discovery': return 'text-purple-600'
    case 'agent': return 'text-blue-600'
    default: return 'text-slate-600'
  }
}

function getEventLogType(eventType: string): ActivityLog['type'] {
  switch (eventType) {
    case 'lead_enriched': return 'enrichment'
    case 'lead_qualified':
    case 'opportunity_created': return 'success'
    case 'contact_added': return 'discovery'
    case 'icp_scored':
    case 'email_sent':
    case 'call_logged': return 'agent'
    default: return 'system'
  }
}

function formatAgentName(agentType: string): string {
  return agentType
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function getAgentSchedule(agentType: string): string {
  const schedules: Record<string, string> = {
    'lead_scout': 'Every 30 min',
    'icp_checker': 'Every 15 min',
    'prediction_agent': 'Every 5 min',
    'morning_briefing': '7 AM EST',
    'sales_intel': 'Hourly',
    'bdr_outreach': 'Hourly',
  }
  return schedules[agentType] || 'On-demand'
}

export default MissionControl
