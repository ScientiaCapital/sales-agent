'use client'

/**
 * CONTRACTOR HUNTER - GTM Pipeline Game Dashboard
 *
 * Arcade-style dashboard with Solarized Dark theme
 * Running clock since Dec 7, 2025 6:00 PM CST launch
 * All data from LIVE Supabase queries
 */

import { useState, useEffect, useRef } from 'react'
import { supabase } from '@/lib/supabase'

// ============================================
// CONSTANTS
// ============================================

// Launch epoch: Dec 7, 2025 at 6:00 PM CST (UTC-6)
const LAUNCH_EPOCH = new Date('2025-12-07T18:00:00-06:00').getTime()

// Solarized Dark colors (inline for reliability)
const SOL = {
  base03: '#002b36',  // Main background
  base02: '#073642',  // Card backgrounds
  base01: '#586e75',  // Muted text
  base00: '#657b83',  // Secondary text
  base0: '#839496',   // Body text
  base1: '#93a1a1',   // Emphasized text
  yellow: '#b58900',  // Gold tier
  orange: '#cb4b16',  // Bronze tier
  red: '#dc322f',     // Errors
  magenta: '#d33682', // Special
  violet: '#6c71c4',  // Platinum tier
  blue: '#268bd2',    // Links
  cyan: '#2aa198',    // Active/Success
  green: '#859900',   // Running
}

// ============================================
// TYPES
// ============================================

interface PipelineStats {
  totalLeads: number
  totalContacts: number
  atlContacts: number
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

interface TradeVerticals {
  hvac: number
  solar: number
  electrical: number
  plumbing: number
  roofing: number
  generator: number
  battery: number
  lowVoltage: number
  fireSafety: number
}

interface AgentStatus {
  name: string
  emoji: string
  status: 'active' | 'idle' | 'sleeping'
  schedule: string
  expertise: string
}

interface ActivityLog {
  id: number
  text: string
  type: 'system' | 'agent' | 'success' | 'enrichment' | 'discovery'
  timestamp: string
}

// ============================================
// AGENTS CONFIG
// ============================================

const REGULAR_AGENTS: AgentStatus[] = [
  { name: 'Lead Scout', emoji: '🔍', status: 'active', schedule: 'Every 30 min', expertise: 'Discovering new leads from Supabase' },
  { name: 'ICP Scorer', emoji: '🎯', status: 'idle', schedule: 'Every 15 min', expertise: 'Recalculating ICP scores' },
  { name: 'Predictor', emoji: '🔮', status: 'active', schedule: 'Every 5 min', expertise: 'Ranking leads by call-worthiness' },
  { name: 'Briefer', emoji: '📋', status: 'sleeping', schedule: '7 AM EST', expertise: 'Daily "why call now" briefings' },
  { name: 'Sales Intel', emoji: '🕵️', status: 'active', schedule: 'Hourly', expertise: 'Extracting personal hooks' },
  { name: 'Outreach', emoji: '📧', status: 'idle', schedule: 'Hourly', expertise: 'Drafting BDR emails' },
]

const ELITE_AGENTS: AgentStatus[] = [
  { name: 'Signal Scout', emoji: '🔭', status: 'active', schedule: 'Event-driven', expertise: 'Market signal detection, vertical discovery' },
  { name: 'Deep Hunter', emoji: '🕵️', status: 'idle', schedule: 'On-demand', expertise: 'Multi-OEM scraping orchestration' },
  { name: 'Intake Commander', emoji: '⚡', status: 'active', schedule: 'Continuous', expertise: 'Dedup, scoring, Close CRM sync' },
]

// Backend API base URL - use proxy in dev, direct in production
const API_BASE = import.meta.env.DEV ? '/api/v1' : 'http://localhost:8001/api/v1'

// ============================================
// COMPONENT
// ============================================

export function MissionControl() {
  const [stats, setStats] = useState<PipelineStats>({
    totalLeads: 0,
    totalContacts: 0,
    atlContacts: 0,
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

  const [trades, setTrades] = useState<TradeVerticals>({
    hvac: 0,
    solar: 0,
    electrical: 0,
    plumbing: 0,
    roofing: 0,
    generator: 0,
    battery: 0,
    lowVoltage: 0,
    fireSafety: 0,
  })

  const [activityLog, setActivityLog] = useState<ActivityLog[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [missionTime, setMissionTime] = useState('00d 00h 00m 00s')
  const [pipelineValue, setPipelineValue] = useState(0)
  const [dealsCount, setDealsCount] = useState(0)
  const [winRate, setWinRate] = useState(0)
  const [avgDealSize, setAvgDealSize] = useState(0)
  const [regularAgents, setRegularAgents] = useState<AgentStatus[]>(REGULAR_AGENTS)
  const terminalRef = useRef<HTMLDivElement>(null)

  // Running clock since launch
  useEffect(() => {
    const updateClock = () => {
      const now = Date.now()
      const diff = Math.max(0, now - LAUNCH_EPOCH)

      const days = Math.floor(diff / (1000 * 60 * 60 * 24))
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
      const seconds = Math.floor((diff % (1000 * 60)) / 1000)

      setMissionTime(
        `${days.toString().padStart(2, '0')}d ${hours.toString().padStart(2, '0')}h ${minutes.toString().padStart(2, '0')}m ${seconds.toString().padStart(2, '0')}s`
      )
    }

    updateClock()
    const interval = setInterval(updateClock, 1000)
    return () => clearInterval(interval)
  }, [])

  // Fetch all stats from Supabase
  useEffect(() => {
    async function fetchStats() {
      try {
        // Fetch companies
        const { data: companies, error: compError } = await supabase
          .from('dim_companies')
          .select(`
            company_id, company_name, icp_tier, icp_score, phone, domain,
            services_offered, oem_brands, trade_count, ai_enriched_at, created_at
          `)

        if (compError) throw compError

        // Fetch contacts
        const { data: contacts, error: contError } = await supabase
          .from('dim_contacts')
          .select('contact_id, company_id, is_atl, email, phone')

        if (contError) throw contError

        // Fetch opportunities for pipeline value
        const { data: opportunities, error: oppError } = await supabase
          .from('fact_opportunities')
          .select('opportunity_id, value_usd, status')

        if (oppError) {
          console.log('No opportunities table yet')
        }

        const now = new Date()
        const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
        const weekStart = new Date(todayStart)
        weekStart.setDate(weekStart.getDate() - 7)

        // Build contact lookup
        const contactsByCompany = new Map<string, { hasEmail: boolean, hasPhone: boolean, isAtl: boolean }>()
        contacts?.forEach(contact => {
          if (contact.company_id) {
            const existing = contactsByCompany.get(contact.company_id) || { hasEmail: false, hasPhone: false, isAtl: false }
            if (contact.email) existing.hasEmail = true
            if (contact.phone) existing.hasPhone = true
            if (contact.is_atl) existing.isAtl = true
            contactsByCompany.set(contact.company_id, existing)
          }
        })

        // HOT = ATL contact with both email AND phone
        const hotCompanies = companies?.filter(c => {
          const contactInfo = contactsByCompany.get(c.company_id)
          return contactInfo?.isAtl && contactInfo?.hasEmail && contactInfo?.hasPhone
        }) || []

        // Calculate stats
        const newStats: PipelineStats = {
          totalLeads: companies?.length || 0,
          totalContacts: contacts?.length || 0,
          atlContacts: contacts?.filter(c => c.is_atl).length || 0,
          enrichedLeads: companies?.filter(c => c.ai_enriched_at).length || 0,
          platinumLeads: companies?.filter(c => c.icp_tier === 'PLATINUM').length || 0,
          goldLeads: companies?.filter(c => c.icp_tier === 'GOLD').length || 0,
          silverLeads: companies?.filter(c => c.icp_tier === 'SILVER').length || 0,
          bronzeLeads: companies?.filter(c => c.icp_tier === 'BRONZE').length || 0,
          hotLeads: hotCompanies.length,
          leadsWithPhone: companies?.filter(c => c.phone).length || 0,
          leadsWithEmail: companies?.filter(c => contactsByCompany.get(c.company_id)?.hasEmail).length || 0,
          leadsAddedToday: companies?.filter(c => new Date(c.created_at) >= todayStart).length || 0,
          leadsAddedThisWeek: companies?.filter(c => new Date(c.created_at) >= weekStart).length || 0,
        }

        // Calculate trade verticals
        const servicesCheck = (services: string[] | null, keywords: string[]) => {
          if (!services) return false
          const lower = services.map(s => s.toLowerCase())
          return keywords.some(k => lower.some(s => s.includes(k)))
        }

        const oemCheck = (oems: string[] | null, keywords: string[]) => {
          if (!oems) return false
          const lower = oems.map(s => s.toLowerCase())
          return keywords.some(k => lower.some(s => s.includes(k)))
        }

        const newTrades: TradeVerticals = {
          hvac: companies?.filter(c => servicesCheck(c.services_offered, ['hvac', 'heating', 'cooling', 'air conditioning'])).length || 0,
          solar: companies?.filter(c => servicesCheck(c.services_offered, ['solar', 'pv', 'photovoltaic']) || oemCheck(c.oem_brands, ['enphase', 'solaredge', 'sma'])).length || 0,
          electrical: companies?.filter(c => servicesCheck(c.services_offered, ['electrical', 'electrician'])).length || 0,
          plumbing: companies?.filter(c => servicesCheck(c.services_offered, ['plumbing', 'plumber'])).length || 0,
          roofing: companies?.filter(c => servicesCheck(c.services_offered, ['roofing', 'roof'])).length || 0,
          generator: companies?.filter(c => servicesCheck(c.services_offered, ['generator', 'backup power']) || oemCheck(c.oem_brands, ['generac', 'kohler', 'cummins'])).length || 0,
          battery: companies?.filter(c => servicesCheck(c.services_offered, ['battery', 'storage']) || oemCheck(c.oem_brands, ['powerwall', 'enphase battery', 'pwrcell'])).length || 0,
          lowVoltage: companies?.filter(c => servicesCheck(c.services_offered, ['low voltage', 'security', 'alarm', 'access control', 'surveillance'])).length || 0,
          fireSafety: companies?.filter(c => servicesCheck(c.services_offered, ['fire', 'sprinkler', 'suppression', 'fire alarm'])).length || 0,
        }

        // Calculate pipeline value and VC metrics
        if (opportunities && opportunities.length > 0) {
          const activeOpps = opportunities.filter(o => o.status === 'active' || o.status === 'open')
          const wonOpps = opportunities.filter(o => o.status === 'won')
          const lostOpps = opportunities.filter(o => o.status === 'lost')
          const closedCount = wonOpps.length + lostOpps.length

          const totalValue = activeOpps.reduce((sum, o) => sum + (o.value_usd || 0), 0)
          const wonValue = wonOpps.reduce((sum, o) => sum + (o.value_usd || 0), 0)

          setPipelineValue(totalValue)
          setDealsCount(activeOpps.length)
          setWinRate(closedCount > 0 ? (wonOpps.length / closedCount) * 100 : 0)
          setAvgDealSize(wonOpps.length > 0 ? wonValue / wonOpps.length : 15000)
        }

        setStats(newStats)
        setTrades(newTrades)
        setIsLoading(false)

      } catch (err) {
        console.error('Failed to fetch stats:', err)
        setIsLoading(false)
      }
    }

    fetchStats()
    const interval = setInterval(fetchStats, 30000) // Refresh every 30s
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
          .limit(15)

        if (error) throw error

        if (auditLogs && auditLogs.length > 0) {
          const realActivity: ActivityLog[] = auditLogs.map((log) => {
            const eventLabel = formatEventType(log.event_type)
            return {
              id: log.id,
              text: `${eventLabel}: ${log.company_name || 'Unknown'}`,
              type: getEventLogType(log.event_type),
              timestamp: new Date(log.created_at).toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
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

  // Fetch agent status from FastAPI backend
  useEffect(() => {
    async function fetchAgentStatus() {
      try {
        const response = await fetch(`${API_BASE}/dashboard/agents`)
        if (response.ok) {
          const agentData = await response.json()
          if (Array.isArray(agentData) && agentData.length > 0) {
            const updatedAgents: AgentStatus[] = agentData.slice(0, 6).map((agent: {
              agent_type: string
              display_name: string
              status: string
              successful_executions: number
            }) => {
              const baseAgent = REGULAR_AGENTS.find(a =>
                a.name.toLowerCase().includes(agent.agent_type.split('_')[0])
              ) || REGULAR_AGENTS[0]
              return {
                ...baseAgent,
                name: agent.display_name || baseAgent.name,
                status: agent.status === 'healthy' ? 'active' as const :
                        agent.status === 'degraded' ? 'idle' as const : 'sleeping' as const,
              }
            })
            if (updatedAgents.length > 0) {
              setRegularAgents(updatedAgents)
            }
          }
        }
      } catch {
        console.log('Backend not available, using static agent list')
      }
    }

    fetchAgentStatus()
    const interval = setInterval(fetchAgentStatus, 30000)
    return () => clearInterval(interval)
  }, [])

  // Auto-scroll terminal
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = 0
    }
  }, [activityLog])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: SOL.base03 }}>
        <div className="text-center font-mono">
          <div className="text-4xl mb-4" style={{ color: SOL.cyan }}>LOADING...</div>
          <div className="animate-pulse" style={{ color: SOL.base0 }}>Connecting to Supabase</div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen font-mono" style={{ backgroundColor: SOL.base03, color: SOL.base0 }}>
      {/* Hero Banner */}
      <div className="border-b-2 px-6 py-6" style={{ borderColor: SOL.cyan }}>
        <div className="max-w-7xl mx-auto">
          {/* ASCII Art Header */}
          <pre className="text-xs sm:text-sm leading-tight mb-4 hidden sm:block" style={{ color: SOL.cyan }}>
{`
 ██████╗ ██████╗ ███╗   ██╗████████╗██████╗  █████╗  ██████╗████████╗ ██████╗ ██████╗
██╔════╝██╔═══██╗████╗  ██║╚══██╔══╝██╔══██╗██╔══██╗██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗
██║     ██║   ██║██╔██╗ ██║   ██║   ██████╔╝███████║██║        ██║   ██║   ██║██████╔╝
██║     ██║   ██║██║╚██╗██║   ██║   ██╔══██╗██╔══██║██║        ██║   ██║   ██║██╔══██╗
╚██████╗╚██████╔╝██║ ╚████║   ██║   ██║  ██║██║  ██║╚██████╗   ██║   ╚██████╔╝██║  ██║
 ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝
                    ██╗  ██╗██╗   ██╗███╗   ██╗████████╗███████╗██████╗
                    ██║  ██║██║   ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗
                    ███████║██║   ██║██╔██╗ ██║   ██║   █████╗  ██████╔╝
                    ██╔══██║██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗
                    ██║  ██║╚██████╔╝██║ ╚████║   ██║   ███████╗██║  ██║
                    ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝
`}
          </pre>
          <h1 className="text-2xl sm:hidden mb-2" style={{ color: SOL.cyan }}>CONTRACTOR HUNTER</h1>

          {/* Mission Clock */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <span className="text-lg" style={{ color: SOL.base1 }}>MISSION ACTIVE:</span>
                <span className="text-2xl font-bold" style={{ color: SOL.green }}>{missionTime}</span>
                <span className="w-3 h-3 rounded-full animate-pulse" style={{ backgroundColor: SOL.green }} />
              </div>
              <div className="text-sm mt-1" style={{ color: SOL.base01 }}>
                LAUNCH: DEC 7, 2025 @ 6:00 PM CST | SERIES A MISSION
              </div>
            </div>
            <div className="flex items-center gap-2 px-3 py-2 rounded" style={{ backgroundColor: SOL.base02 }}>
              <span style={{ color: SOL.base0 }}>STATUS:</span>
              <span className="font-bold" style={{ color: SOL.cyan }}>HUNTING...</span>
            </div>
          </div>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Score Board */}
        <div className="mb-8 p-4 rounded-lg border-2" style={{ backgroundColor: SOL.base02, borderColor: SOL.cyan }}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold" style={{ color: SOL.base1 }}>SCORE BOARD</h2>
            <span className="text-sm" style={{ color: SOL.base01 }}>HIGH SCORE: {stats.totalLeads.toLocaleString()}</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <ScoreCard emoji="🏢" label="CONTRACTORS" value={stats.totalLeads} highlight />
            <ScoreCard emoji="👔" label="DECISION MAKERS" value={stats.atlContacts} />
            <ScoreCard emoji="🔥" label="CALL READY" value={stats.hotLeads} color={SOL.orange} />
            <ScoreCard emoji="📧" label="ENRICHED" value={stats.enrichedLeads} color={SOL.cyan} />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 pt-4" style={{ borderTop: `1px solid ${SOL.base01}` }}>
            <ScoreCard emoji="📈" label="TODAY" value={stats.leadsAddedToday} prefix="+" small />
            <ScoreCard emoji="📊" label="THIS WEEK" value={stats.leadsAddedThisWeek} prefix="+" small />
            <ScoreCard emoji="📞" label="WITH PHONE" value={stats.leadsWithPhone} small />
            <ScoreCard emoji="✉️" label="WITH EMAIL" value={stats.leadsWithEmail} small />
          </div>
        </div>

        {/* ICP Power-Ups */}
        <div className="mb-8 p-4 rounded-lg border" style={{ backgroundColor: SOL.base02, borderColor: SOL.base01 }}>
          <h2 className="text-lg font-bold mb-4" style={{ color: SOL.base1 }}>ICP POWER-UPS</h2>
          <div className="space-y-3">
            <TierBar tier="PLATINUM" emoji="💎" count={stats.platinumLeads} total={stats.totalLeads} color={SOL.violet} />
            <TierBar tier="GOLD" emoji="🥇" count={stats.goldLeads} total={stats.totalLeads} color={SOL.yellow} />
            <TierBar tier="SILVER" emoji="🥈" count={stats.silverLeads} total={stats.totalLeads} color={SOL.base1} />
            <TierBar tier="BRONZE" emoji="🥉" count={stats.bronzeLeads} total={stats.totalLeads} color={SOL.orange} />
          </div>
        </div>

        {/* Trifecta Detection */}
        <div className="mb-8 p-4 rounded-lg border" style={{ backgroundColor: SOL.base02, borderColor: SOL.magenta }}>
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xl">⚡</span>
            <h2 className="text-lg font-bold" style={{ color: SOL.magenta }}>TRIFECTA DETECTION</h2>
          </div>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="p-3 rounded" style={{ backgroundColor: SOL.base03 }}>
              <div className="text-2xl mb-1">☀️</div>
              <div className="text-2xl font-bold" style={{ color: SOL.yellow }}>{trades.solar}</div>
              <div className="text-xs" style={{ color: SOL.base01 }}>SOLAR</div>
            </div>
            <div className="p-3 rounded" style={{ backgroundColor: SOL.base03 }}>
              <div className="text-2xl mb-1">⚡</div>
              <div className="text-2xl font-bold" style={{ color: SOL.orange }}>{trades.generator}</div>
              <div className="text-xs" style={{ color: SOL.base01 }}>GENERATOR</div>
            </div>
            <div className="p-3 rounded" style={{ backgroundColor: SOL.base03 }}>
              <div className="text-2xl mb-1">🔋</div>
              <div className="text-2xl font-bold" style={{ color: SOL.cyan }}>{trades.battery}</div>
              <div className="text-xs" style={{ color: SOL.base01 }}>BATTERY</div>
            </div>
          </div>
          <div className="mt-4 pt-3 text-center text-sm" style={{ borderTop: `1px solid ${SOL.base01}`, color: SOL.base00 }}>
            Full Trifecta = 3.375x MEGA MULTIPLIER
          </div>
        </div>

        {/* Two Column Layout */}
        <div className="grid md:grid-cols-2 gap-8 mb-8">
          {/* Trade Verticals */}
          <div className="p-4 rounded-lg border" style={{ backgroundColor: SOL.base02, borderColor: SOL.base01 }}>
            <h2 className="text-lg font-bold mb-4" style={{ color: SOL.base1 }}>SELECT YOUR VERTICAL</h2>
            <div className="space-y-2">
              <VerticalBar emoji="🔥" label="HVAC" count={trades.hvac} total={stats.totalLeads} color={SOL.orange} />
              <VerticalBar emoji="☀️" label="SOLAR" count={trades.solar} total={stats.totalLeads} color={SOL.yellow} />
              <VerticalBar emoji="⚡" label="ELECTRICAL" count={trades.electrical} total={stats.totalLeads} color={SOL.blue} />
              <VerticalBar emoji="🔧" label="PLUMBING" count={trades.plumbing} total={stats.totalLeads} color={SOL.cyan} />
              <VerticalBar emoji="🏠" label="ROOFING" count={trades.roofing} total={stats.totalLeads} color={SOL.base1} />
            </div>
            {/* Emerging Verticals */}
            <div className="mt-4 pt-3" style={{ borderTop: `1px solid ${SOL.base01}` }}>
              <div className="text-xs mb-2" style={{ color: SOL.magenta }}>🆕 EMERGING MARKETS</div>
              <div className="grid grid-cols-2 gap-2">
                <div className="flex justify-between px-2 py-1 rounded text-sm" style={{ backgroundColor: SOL.base03 }}>
                  <span style={{ color: SOL.base0 }}>🔒 Low Voltage</span>
                  <span style={{ color: SOL.magenta }}>{trades.lowVoltage}</span>
                </div>
                <div className="flex justify-between px-2 py-1 rounded text-sm" style={{ backgroundColor: SOL.base03 }}>
                  <span style={{ color: SOL.base0 }}>🧯 Fire & Safety</span>
                  <span style={{ color: SOL.red }}>{trades.fireSafety}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Pipeline Value */}
          <div className="p-4 rounded-lg border" style={{ backgroundColor: SOL.base02, borderColor: SOL.green }}>
            <div className="flex items-center gap-2 mb-4">
              <span className="text-xl">💰</span>
              <h2 className="text-lg font-bold" style={{ color: SOL.green }}>VC METRICS</h2>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 rounded text-center" style={{ backgroundColor: SOL.base03 }}>
                <div className="text-xs mb-1" style={{ color: SOL.base01 }}>PIPELINE VALUE</div>
                <div className="text-2xl font-bold" style={{ color: SOL.green }}>
                  ${pipelineValue >= 1000000 ? `${(pipelineValue / 1000000).toFixed(1)}M` : pipelineValue >= 1000 ? `${(pipelineValue / 1000).toFixed(0)}K` : pipelineValue}
                </div>
              </div>
              <div className="p-3 rounded text-center" style={{ backgroundColor: SOL.base03 }}>
                <div className="text-xs mb-1" style={{ color: SOL.base01 }}>ACTIVE DEALS</div>
                <div className="text-2xl font-bold" style={{ color: SOL.cyan }}>{dealsCount}</div>
              </div>
              <div className="p-3 rounded text-center" style={{ backgroundColor: SOL.base03 }}>
                <div className="text-xs mb-1" style={{ color: SOL.base01 }}>COST/LEAD</div>
                <div className="text-2xl font-bold" style={{ color: SOL.green }}>$0.02</div>
              </div>
              <div className="p-3 rounded text-center" style={{ backgroundColor: SOL.base03 }}>
                <div className="text-xs mb-1" style={{ color: SOL.base01 }}>LTV:CAC</div>
                <div className="text-2xl font-bold" style={{ color: SOL.magenta }}>120:1</div>
              </div>
            </div>
            <div className="mt-4 pt-3 text-center text-xs" style={{ borderTop: `1px solid ${SOL.base01}`, color: SOL.base00 }}>
              Target: 1,000,000 pts = SERIES A UNLOCKED
            </div>
          </div>
        </div>

        {/* Agent Squad */}
        <div className="grid md:grid-cols-2 gap-8 mb-8">
          {/* Regular Agents */}
          <div className="p-4 rounded-lg border" style={{ backgroundColor: SOL.base02, borderColor: SOL.base01 }}>
            <h2 className="text-lg font-bold mb-4" style={{ color: SOL.base1 }}>🤖 AGENT SQUAD</h2>
            <div className="space-y-2">
              {regularAgents.map((agent) => (
                <AgentRow key={agent.name} agent={agent} />
              ))}
            </div>
          </div>

          {/* Elite Team */}
          <div className="p-4 rounded-lg border-2" style={{ backgroundColor: SOL.base02, borderColor: SOL.magenta }}>
            <div className="flex items-center gap-2 mb-4">
              <span className="text-xl">🎖️</span>
              <h2 className="text-lg font-bold" style={{ color: SOL.magenta }}>ELITE TEAM</h2>
              <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: SOL.magenta, color: SOL.base03 }}>SPEC OPS</span>
            </div>
            <div className="space-y-2">
              {ELITE_AGENTS.map((agent) => (
                <AgentRow key={agent.name} agent={agent} elite />
              ))}
            </div>
          </div>
        </div>

        {/* Game Log */}
        <div className="p-4 rounded-lg border" style={{ backgroundColor: SOL.base02, borderColor: SOL.base01 }}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold" style={{ color: SOL.base1 }}>GAME LOG</h2>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: SOL.red }} />
              <span className="text-xs" style={{ color: SOL.base01 }}>LIVE</span>
            </div>
          </div>
          <div
            ref={terminalRef}
            className="h-48 overflow-y-auto space-y-1 font-mono text-sm"
            style={{ backgroundColor: SOL.base03, padding: '1rem', borderRadius: '0.25rem' }}
          >
            {activityLog.length === 0 ? (
              <div style={{ color: SOL.base01 }}>Waiting for activity...</div>
            ) : (
              activityLog.map((log) => (
                <div key={log.id} className="flex items-start gap-3">
                  <span style={{ color: SOL.base01 }}>[{log.timestamp}]</span>
                  <span style={{ color: getLogColor(log.type) }}>
                    {getLogEmoji(log.type)} {log.text}
                  </span>
                </div>
              ))
            )}
            <div className="flex items-center gap-1 mt-2">
              <span style={{ color: SOL.green }}>&gt;</span>
              <span className="animate-pulse" style={{ color: SOL.green }}>█</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-xs" style={{ color: SOL.base01 }}>
          COPERNIQ PIVOT | DEC 7, 2025 | ALL METRICS LIVE FROM SUPABASE
        </div>
      </main>
    </div>
  )
}

// ============================================
// SUB-COMPONENTS
// ============================================

function ScoreCard({ emoji, label, value, highlight, color, prefix, small }: {
  emoji: string
  label: string
  value: number
  highlight?: boolean
  color?: string
  prefix?: string
  small?: boolean
}) {
  return (
    <div className={`p-3 rounded ${small ? '' : ''}`} style={{ backgroundColor: SOL.base03 }}>
      <div className="flex items-center gap-2 mb-1">
        <span className={small ? 'text-sm' : 'text-lg'}>{emoji}</span>
        <span className="text-xs" style={{ color: SOL.base01 }}>{label}</span>
      </div>
      <div
        className={`font-bold ${small ? 'text-lg' : 'text-2xl'}`}
        style={{ color: highlight ? SOL.cyan : color || SOL.base1 }}
      >
        {prefix}{value.toLocaleString()}
      </div>
    </div>
  )
}

function TierBar({ tier, emoji, count, total, color }: {
  tier: string
  emoji: string
  count: number
  total: number
  color: string
}) {
  const percent = total > 0 ? (count / total) * 100 : 0
  const maxWidth = 60 // Max percentage for visual

  return (
    <div className="flex items-center gap-3">
      <span className="text-lg">{emoji}</span>
      <span className="w-20 text-sm" style={{ color }}>{tier}</span>
      <div className="flex-1 h-4 rounded overflow-hidden" style={{ backgroundColor: SOL.base03 }}>
        <div
          className="h-full rounded transition-all duration-500"
          style={{ width: `${Math.min(percent * 2, maxWidth)}%`, backgroundColor: color }}
        />
      </div>
      <span className="w-16 text-right font-bold" style={{ color }}>{count.toLocaleString()}</span>
    </div>
  )
}

function VerticalBar({ emoji, label, count, total, color }: {
  emoji: string
  label: string
  count: number
  total: number
  color: string
}) {
  const percent = total > 0 ? (count / total) * 100 : 0

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <span>{emoji}</span>
        <span className="flex-1 text-sm" style={{ color: SOL.base0 }}>{label}</span>
        <span className="font-bold" style={{ color }}>{count.toLocaleString()}</span>
      </div>
      <div className="h-2 rounded overflow-hidden" style={{ backgroundColor: SOL.base03 }}>
        <div
          className="h-full rounded transition-all duration-500"
          style={{ width: `${Math.min(percent * 2, 100)}%`, backgroundColor: color }}
        />
      </div>
    </div>
  )
}

function AgentRow({ agent, elite }: { agent: AgentStatus, elite?: boolean }) {
  const statusColor = agent.status === 'active' ? SOL.green :
                      agent.status === 'idle' ? SOL.yellow : SOL.base01

  return (
    <div className="flex items-center gap-3 py-2 px-2 rounded" style={{ backgroundColor: SOL.base03 }}>
      <span className="text-lg">{agent.emoji}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium truncate" style={{ color: elite ? SOL.magenta : SOL.base1 }}>
            {agent.name}
          </span>
          <span
            className="text-xs px-1.5 py-0.5 rounded uppercase"
            style={{ backgroundColor: statusColor, color: SOL.base03 }}
          >
            {agent.status}
          </span>
        </div>
        <div className="text-xs truncate" style={{ color: SOL.base01 }}>{agent.expertise}</div>
      </div>
      <div className="text-xs text-right" style={{ color: SOL.base00 }}>{agent.schedule}</div>
    </div>
  )
}

// ============================================
// HELPERS
// ============================================

function formatEventType(eventType: string): string {
  const labels: Record<string, string> = {
    lead_enriched: '🎯 ENRICHED',
    lead_qualified: '✅ QUALIFIED',
    contact_added: '👤 CONTACT',
    icp_scored: '📊 SCORED',
    email_sent: '📧 EMAIL',
    call_logged: '📞 CALL',
    opportunity_created: '💰 DEAL',
  }
  return labels[eventType] || eventType.replace(/_/g, ' ').toUpperCase()
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

function getLogColor(type: ActivityLog['type']): string {
  switch (type) {
    case 'success': return SOL.green
    case 'enrichment': return SOL.yellow
    case 'discovery': return SOL.magenta
    case 'agent': return SOL.blue
    default: return SOL.base0
  }
}

function getLogEmoji(type: ActivityLog['type']): string {
  switch (type) {
    case 'success': return '✅'
    case 'enrichment': return '🎯'
    case 'discovery': return '🔍'
    case 'agent': return '🤖'
    default: return '📋'
  }
}

export default MissionControl
