'use client'

/**
 * LEAD HUNTER - Agent Mission Control
 *
 * Atari-style retro terminal dashboard for CEO/CTO/VC demos
 * Shows live agent activity, lead growth, and Tim Kipper's GTM journey
 *
 * Inspired by quantify-mvp VLM Demo terminal aesthetic
 */

import { useState, useEffect, useRef } from 'react'
import { supabase } from '@/lib/supabase'

// ============================================
// TYPES
// ============================================

interface GameStats {
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
  // Growth tracking
  startingLeads: number // Dec 2025 baseline
  leadsAddedToday: number
  leadsAddedThisWeek: number
}

// ICP Segment tracking - Coperniq MCP+Energy verticals
interface ICPSegments {
  hvac: number
  solar: number
  electrical: number
  plumbing: number
  roofing: number
  // Market segments
  resiOnly: number      // Residential only
  commercial: number    // Pure commercial
  resimercial: number   // Both resi + commercial
  cAndI: number         // Large C&I solar
  // Quality metrics
  multiTrade: number    // 3+ trades
  avgTradeCount: number
  avgLocations: number
  avgEmployees: number
}

// Valuation point values - gamified scoring
const VALUATION_POINTS = {
  leadBase: 50,              // Every lead = $50
  enriched: 25,              // +$25 for enrichment
  atlContact: 100,           // +$100 for decision maker
  directPhone: 150,          // +$150 for direct dial
  platinum: 500,             // +$500 for platinum ICP
  gold: 250,                 // +$250 for gold
  silver: 100,               // +$100 for silver
  multiTrade: 200,           // +$200 for 3+ trades (Coperniq sweet spot)
  hasSolar: 300,             // +$300 for solar capability
  multiLocation: 150,        // +$150 for multi-location
}

interface AgentStatus {
  name: string
  icon: string
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
  { name: 'SCOUT', icon: '🔍', status: 'active', lastRun: '', tasksCompleted: 0, schedule: 'Every 30 min' },
  { name: 'ICP-SCORER', icon: '📊', status: 'idle', lastRun: '', tasksCompleted: 0, schedule: 'Every 15 min' },
  { name: 'PREDICTOR', icon: '🎯', status: 'active', lastRun: '', tasksCompleted: 0, schedule: 'Every 5 min' },
  { name: 'BRIEFER', icon: '📋', status: 'sleeping', lastRun: '', tasksCompleted: 0, schedule: '7 AM EST' },
  { name: 'INTEL', icon: '🧠', status: 'active', lastRun: '', tasksCompleted: 0, schedule: 'Hourly' },
  { name: 'OUTREACH', icon: '✉️', status: 'idle', lastRun: '', tasksCompleted: 0, schedule: 'Hourly' },
]

const DECEMBER_2025_BASELINE = {
  leads: 6568, // Original gold standard leads
  contacts: 562, // ATL contacts from Batch 1
  date: '2025-12-01'
}

// ============================================
// COMPONENT
// ============================================

export function MissionControl() {
  const [stats, setStats] = useState<GameStats>({
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
    startingLeads: DECEMBER_2025_BASELINE.leads,
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

  const [pipelineValuation, setPipelineValuation] = useState(0)
  const [displayedValuation, setDisplayedValuation] = useState(0)
  const [topBrands, setTopBrands] = useState<{name: string, count: number}[]>([])

  const [agents, setAgents] = useState<AgentStatus[]>(AGENTS)
  const [activityLog, setActivityLog] = useState<ActivityLog[]>([])
  const [displayedScore, setDisplayedScore] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const terminalRef = useRef<HTMLDivElement>(null)
  const scoreRef = useRef<HTMLDivElement>(null)

  // Fetch stats from Supabase
  useEffect(() => {
    async function fetchStats() {
      try {
        // Get company counts with ICP segment data
        const { data: companies, error: compError } = await supabase
          .from('dim_companies')
          .select(`
            id, icp_tier, enrichment_status, has_phone, has_email, created_at,
            services_offered, oem_brands, trade_count, employee_count, location_count,
            industries_served
          `)

        if (compError) throw compError

        // Get contact counts
        const { data: contacts, error: contError } = await supabase
          .from('dim_contacts')
          .select('id, is_atl')

        if (contError) throw contError

        const now = new Date()
        const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
        const weekStart = new Date(todayStart)
        weekStart.setDate(weekStart.getDate() - 7)

        const newStats: GameStats = {
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
          startingLeads: DECEMBER_2025_BASELINE.leads,
          leadsAddedToday: companies?.filter(c => new Date(c.created_at) >= todayStart).length || 0,
          leadsAddedThisWeek: companies?.filter(c => new Date(c.created_at) >= weekStart).length || 0,
        }

        // Calculate ICP Segments from services_offered and industries_served
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

        // Market segment classification
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

        // C&I = Large commercial + industrial solar focus
        const cAndICount = companies?.filter(c =>
          (servicesCheck(c.industries_served, ['industrial', 'c&i', 'commercial solar']) ||
           servicesCheck(c.services_offered, ['industrial', 'commercial solar']))
        ).length || 0

        // Multi-trade (Coperniq sweet spot: 3+ trades)
        const multiTradeCount = companies?.filter(c =>
          c.trade_count && c.trade_count >= 3
        ).length || 0

        // Calculate averages
        const withTrades = companies?.filter(c => c.trade_count && c.trade_count > 0) || []
        const withLocations = companies?.filter(c => c.location_count && c.location_count > 0) || []
        const withEmployees = companies?.filter(c => c.employee_count) || []

        const avgTradeCount = withTrades.length > 0
          ? withTrades.reduce((sum, c) => sum + (c.trade_count || 0), 0) / withTrades.length
          : 0

        const avgLocations = withLocations.length > 0
          ? withLocations.reduce((sum, c) => sum + (c.location_count || 0), 0) / withLocations.length
          : 0

        // Parse employee_count which might be text like "50+" or "100-200"
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
          .slice(0, 10)
          .map(([name, count]) => ({ name, count }))
        setTopBrands(sortedBrands)

        // Calculate Pipeline Valuation (gamified scoring)
        let valuation = 0
        companies?.forEach(c => {
          valuation += VALUATION_POINTS.leadBase  // Every lead
          if (c.enrichment_status === 'complete') valuation += VALUATION_POINTS.enriched
          if (c.has_phone) valuation += VALUATION_POINTS.directPhone
          if (c.icp_tier === 'PLATINUM') valuation += VALUATION_POINTS.platinum
          else if (c.icp_tier === 'GOLD') valuation += VALUATION_POINTS.gold
          else if (c.icp_tier === 'SILVER') valuation += VALUATION_POINTS.silver
          if (c.trade_count && c.trade_count >= 3) valuation += VALUATION_POINTS.multiTrade
          if (servicesCheck(c.services_offered, ['solar'])) valuation += VALUATION_POINTS.hasSolar
          if (c.location_count && c.location_count > 1) valuation += VALUATION_POINTS.multiLocation
        })
        // Add value for ATL contacts
        const atlCount = contacts?.filter(c => c.is_atl).length || 0
        valuation += atlCount * VALUATION_POINTS.atlContact
        setPipelineValuation(valuation)

        setStats(newStats)
        setIsLoading(false)

      } catch (err) {
        console.error('Failed to fetch stats:', err)
        setIsLoading(false)
      }
    }

    fetchStats()

    // Refresh every 30 seconds
    const interval = setInterval(fetchStats, 30000)
    return () => clearInterval(interval)
  }, [])

  // Fetch REAL activity from lead_audit_log
  useEffect(() => {
    async function fetchActivity() {
      try {
        const { data: auditLogs, error } = await supabase
          .from('lead_audit_log')
          .select('id, event_type, company_name, created_at, details')
          .order('created_at', { ascending: false })
          .limit(50)

        if (error) throw error

        if (auditLogs && auditLogs.length > 0) {
          const realActivity: ActivityLog[] = auditLogs.map((log) => {
            // Map event types to display format
            const eventIcons: Record<string, string> = {
              'lead_imported': '📥',
              'lead_qualified': '✅',
              'lead_enriched': '✨',
              'contact_added': '👔',
              'icp_scored': '📊',
              'email_sent': '✉️',
              'call_logged': '📞',
              'opportunity_created': '🎯',
              'stage_changed': '📈',
            }
            const icon = eventIcons[log.event_type] || '•'
            const eventLabel = log.event_type.replace(/_/g, ' ').toUpperCase()

            return {
              id: log.id,
              text: `${icon} ${eventLabel}: ${log.company_name || 'Unknown'}`,
              type: getEventLogType(log.event_type),
              timestamp: new Date(log.created_at).toLocaleTimeString('en-US', { hour12: false })
            }
          })
          setActivityLog(realActivity)
        }
      } catch (err) {
        console.error('Failed to fetch activity:', err)
      }
    }

    fetchActivity()

    // Refresh every 10 seconds for live updates
    const interval = setInterval(fetchActivity, 10000)
    return () => clearInterval(interval)
  }, [])

  // Fetch REAL agent health from FastAPI backend (when running locally)
  useEffect(() => {
    async function fetchAgentHealth() {
      try {
        // Try local FastAPI backend first
        const response = await fetch('/api/dashboard/agents')
        if (response.ok) {
          const agentData = await response.json()
          if (Array.isArray(agentData) && agentData.length > 0) {
            const updatedAgents: AgentStatus[] = agentData.map((agent: {
              agent_type: string;
              display_name: string;
              status: string;
              last_execution_at: string;
              successful_executions: number;
            }) => ({
              name: agent.display_name || agent.agent_type.toUpperCase(),
              icon: getAgentIcon(agent.agent_type),
              status: agent.status === 'healthy' ? 'active' as const :
                      agent.status === 'degraded' ? 'idle' as const : 'sleeping' as const,
              lastRun: agent.last_execution_at || '',
              tasksCompleted: agent.successful_executions || 0,
              schedule: getAgentSchedule(agent.agent_type)
            }))
            setAgents(updatedAgents)
          }
        }
      } catch (err) {
        // Backend not running - use default static agents (no fake data)
        console.log('FastAPI backend not available, using static agent list')
      }
    }

    fetchAgentHealth()

    // Refresh every 30 seconds
    const interval = setInterval(fetchAgentHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  // Animate score counter
  useEffect(() => {
    if (stats.totalLeads === 0) return

    const duration = 2000 // 2 seconds
    const steps = 60
    const increment = stats.totalLeads / steps
    let current = 0

    const timer = setInterval(() => {
      current += increment
      if (current >= stats.totalLeads) {
        setDisplayedScore(stats.totalLeads)
        clearInterval(timer)
      } else {
        setDisplayedScore(Math.floor(current))
      }
    }, duration / steps)

    return () => clearInterval(timer)
  }, [stats.totalLeads])

  // Animate valuation counter (slightly slower, like a stock ticker)
  useEffect(() => {
    if (pipelineValuation === 0) return

    const duration = 3000 // 3 seconds for dramatic effect
    const steps = 90
    const increment = pipelineValuation / steps
    let current = 0

    const timer = setInterval(() => {
      current += increment
      if (current >= pipelineValuation) {
        setDisplayedValuation(pipelineValuation)
        clearInterval(timer)
      } else {
        setDisplayedValuation(Math.floor(current))
      }
    }, duration / steps)

    return () => clearInterval(timer)
  }, [pipelineValuation])

  // Auto-scroll terminal
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [activityLog])

  const growthPercent = ((stats.totalLeads - stats.startingLeads) / stats.startingLeads * 100).toFixed(1)
  const growthPositive = stats.totalLeads >= stats.startingLeads

  return (
    <div className="min-h-screen bg-black p-4 font-mono">
      {/* HEADER - Game Title */}
      <div className="text-center mb-6">
        <div className="text-green-500 text-xs mb-2">
          ╔══════════════════════════════════════════════════════════════════════════════╗
        </div>
        <h1 className="text-4xl md:text-6xl font-bold text-green-400 tracking-wider animate-pulse">
          🎮 CONTRACTOR HUNTER 🎮
        </h1>
        <p className="text-green-600 text-sm mt-2">
          HVAC • SOLAR • ELECTRICAL • PLUMBING • ROOFING • EV | COPERNIQ ICP PIPELINE
        </p>
        <p className="text-cyan-500 text-xs mt-1">
          AUTONOMOUS GTM AGENT SYSTEM v1.0 | LANGGRAPH + CLAUDE AI
        </p>
        <div className="text-green-500 text-xs mt-2">
          ╚══════════════════════════════════════════════════════════════════════════════╝
        </div>
      </div>

      {/* MAIN SCORE DISPLAY */}
      <div className="bg-black border-4 border-green-500 rounded-lg p-6 mb-6 text-center relative overflow-hidden">
        {/* Scanline effect */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: 'linear-gradient(rgba(0,255,0,0.03) 1px, transparent 1px)',
            backgroundSize: '100% 3px',
          }}
        />

        <div className="text-green-600 text-sm mb-2">CONTRACTORS IN PIPELINE</div>
        <div
          ref={scoreRef}
          className="text-6xl md:text-8xl font-bold text-green-400 tabular-nums"
          style={{ textShadow: '0 0 20px rgba(0,255,0,0.5), 0 0 40px rgba(0,255,0,0.3)' }}
        >
          {displayedScore.toLocaleString()}
        </div>

        {/* Growth indicator */}
        <div className={`text-2xl mt-4 ${growthPositive ? 'text-green-400' : 'text-red-400'}`}>
          {growthPositive ? '▲' : '▼'} {growthPercent}% since Dec 2025
        </div>
        <div className="text-green-600 text-sm">
          Baseline: {DECEMBER_2025_BASELINE.leads.toLocaleString()} contractors |
          Discovered: +{(stats.totalLeads - stats.startingLeads).toLocaleString()}
        </div>
      </div>

      {/* STATS GRID - Arcade Style */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatBox label="DECISION MAKERS" value={stats.totalContacts} icon="👔" color="cyan" />
        <StatBox label="INTEL COMPLETE" value={stats.enrichedLeads} icon="✨" color="yellow" />
        <StatBox label="🔥 CALL READY" value={stats.hotLeads} icon="🔥" color="red" />
        <StatBox label="DIRECT DIAL" value={stats.leadsWithPhone} icon="📱" color="green" />

        <StatBox label="⭐ PLATINUM" value={stats.platinumLeads} icon="💎" color="purple" />
        <StatBox label="🥇 GOLD" value={stats.goldLeads} icon="🥇" color="yellow" />
        <StatBox label="🥈 SILVER" value={stats.silverLeads} icon="🥈" color="gray" />
        <StatBox label="🥉 BRONZE" value={stats.bronzeLeads} icon="🥉" color="orange" />
      </div>

      {/* PIPELINE VALUATION - Stock Ticker Style */}
      <div className="bg-black border-4 border-yellow-500 rounded-lg p-6 mb-6 relative overflow-hidden">
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: 'linear-gradient(rgba(255,215,0,0.02) 1px, transparent 1px)',
            backgroundSize: '100% 3px',
          }}
        />
        <div className="grid md:grid-cols-3 gap-6 items-center">
          {/* Valuation Clock */}
          <div className="text-center">
            <div className="text-yellow-600 text-sm mb-1">💰 PIPELINE VALUATION</div>
            <div
              className="text-4xl md:text-5xl font-bold text-yellow-400 tabular-nums"
              style={{ textShadow: '0 0 15px rgba(255,215,0,0.4)' }}
            >
              ${displayedValuation.toLocaleString()}
            </div>
            <div className="text-yellow-700 text-xs mt-1">
              +${VALUATION_POINTS.leadBase}/lead • +${VALUATION_POINTS.atlContact}/ATL • +${VALUATION_POINTS.hasSolar}/solar
            </div>
          </div>

          {/* Quality Metrics */}
          <div className="text-center border-l border-r border-yellow-500/30 px-4">
            <div className="text-yellow-600 text-sm mb-2">📊 QUALITY METRICS</div>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div>
                <div className="text-yellow-400 text-lg font-bold">{segments.multiTrade}</div>
                <div className="text-yellow-700">Multi-Trade</div>
              </div>
              <div>
                <div className="text-yellow-400 text-lg font-bold">{segments.avgTradeCount}</div>
                <div className="text-yellow-700">Avg Trades</div>
              </div>
              <div>
                <div className="text-yellow-400 text-lg font-bold">{segments.avgEmployees}</div>
                <div className="text-yellow-700">Avg Staff</div>
              </div>
            </div>
          </div>

          {/* Bonus Multipliers */}
          <div className="text-center">
            <div className="text-yellow-600 text-sm mb-2">🎯 BONUS POINTS</div>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between text-yellow-500">
                <span>💎 Platinum:</span>
                <span>+{stats.platinumLeads * VALUATION_POINTS.platinum}</span>
              </div>
              <div className="flex justify-between text-yellow-500">
                <span>☀️ Solar Capable:</span>
                <span>+{segments.solar * VALUATION_POINTS.hasSolar}</span>
              </div>
              <div className="flex justify-between text-yellow-500">
                <span>🔧 Multi-Trade:</span>
                <span>+{segments.multiTrade * VALUATION_POINTS.multiTrade}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ICP SEGMENTS - MCP+Energy Verticals */}
      <div className="grid md:grid-cols-2 gap-6 mb-6">
        {/* Trade Verticals */}
        <div className="bg-black border-2 border-purple-500/50 rounded-lg p-4">
          <div className="text-purple-400 font-bold mb-4 text-center">
            ═══ MCP+ENERGY VERTICALS ═══
          </div>
          <div className="grid grid-cols-5 gap-2 text-center">
            <VerticalBox label="HVAC" count={segments.hvac} icon="❄️" />
            <VerticalBox label="SOLAR" count={segments.solar} icon="☀️" />
            <VerticalBox label="ELEC" count={segments.electrical} icon="⚡" />
            <VerticalBox label="PLUMB" count={segments.plumbing} icon="🔧" />
            <VerticalBox label="ROOF" count={segments.roofing} icon="🏠" />
          </div>
        </div>

        {/* Market Segments */}
        <div className="bg-black border-2 border-blue-500/50 rounded-lg p-4">
          <div className="text-blue-400 font-bold mb-4 text-center">
            ═══ MARKET SEGMENTS ═══
          </div>
          <div className="grid grid-cols-4 gap-2 text-center">
            <SegmentBox label="RESI" count={segments.resiOnly} color="green" />
            <SegmentBox label="COMM" count={segments.commercial} color="blue" />
            <SegmentBox label="RESIMER" count={segments.resimercial} color="purple" />
            <SegmentBox label="C&I" count={segments.cAndI} color="orange" />
          </div>
        </div>
      </div>

      {/* OEM BRANDS LEADERBOARD */}
      {topBrands.length > 0 && (
        <div className="bg-black border-2 border-emerald-500/50 rounded-lg p-4 mb-6">
          <div className="text-emerald-400 font-bold mb-4 text-center">
            ═══ TOP OEM BRANDS IN PIPELINE ═══
          </div>
          <div className="flex flex-wrap justify-center gap-2">
            {topBrands.map((brand, idx) => (
              <div
                key={brand.name}
                className={`px-3 py-1 rounded-full text-sm ${
                  idx === 0 ? 'bg-yellow-900/40 text-yellow-400 border border-yellow-500' :
                  idx === 1 ? 'bg-gray-800/40 text-gray-300 border border-gray-500' :
                  idx === 2 ? 'bg-orange-900/40 text-orange-400 border border-orange-600' :
                  'bg-emerald-900/20 text-emerald-400 border border-emerald-700/50'
                }`}
              >
                {idx < 3 && <span className="mr-1">{idx === 0 ? '🥇' : idx === 1 ? '🥈' : '🥉'}</span>}
                {brand.name}: {brand.count}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AGENT STATUS PANEL */}
      <div className="grid md:grid-cols-2 gap-6 mb-6">
        {/* Agents */}
        <div className="bg-black border-2 border-green-500/50 rounded-lg p-4">
          <div className="text-green-400 font-bold mb-4 text-center">
            ═══ ACTIVE AGENTS ═══
          </div>
          <div className="grid grid-cols-2 gap-3">
            {agents.map((agent) => (
              <div
                key={agent.name}
                className={`p-3 rounded border ${
                  agent.status === 'active'
                    ? 'border-green-400 bg-green-900/20'
                    : agent.status === 'idle'
                    ? 'border-yellow-400/50 bg-yellow-900/10'
                    : 'border-gray-600 bg-gray-900/20'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-2xl">{agent.icon}</span>
                  <div>
                    <div className={`font-bold text-sm ${
                      agent.status === 'active' ? 'text-green-400' :
                      agent.status === 'idle' ? 'text-yellow-400' : 'text-gray-500'
                    }`}>
                      {agent.name}
                    </div>
                    <div className="text-xs text-green-600">
                      {agent.status === 'active' && '● RUNNING'}
                      {agent.status === 'idle' && '○ STANDBY'}
                      {agent.status === 'sleeping' && '◐ SCHEDULED'}
                    </div>
                  </div>
                </div>
                <div className="text-xs text-green-700 mt-1">
                  Tasks: {agent.tasksCompleted} | {agent.schedule}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Activity Terminal */}
        <div className="bg-black border-2 border-green-500/50 rounded-lg overflow-hidden">
          <div className="bg-green-900/30 px-4 py-2 text-green-400 font-bold text-center border-b border-green-500/30">
            ═══ LIVE ACTIVITY FEED ═══
          </div>
          <div
            ref={terminalRef}
            className="h-64 overflow-y-auto p-3 text-sm"
            style={{
              backgroundImage: 'linear-gradient(rgba(0,255,0,0.02) 1px, transparent 1px)',
              backgroundSize: '100% 2px',
            }}
          >
            {activityLog.length === 0 ? (
              <div className="text-green-600 animate-pulse">
                {'>'} Initializing agent swarm...
                <span className="animate-pulse">█</span>
              </div>
            ) : (
              activityLog.map((log) => (
                <div
                  key={log.id}
                  className={`leading-relaxed ${getLogColor(log.type)}`}
                >
                  <span className="text-green-900">[{log.timestamp}]</span> {log.text}
                </div>
              ))
            )}
            <div className="text-green-400 animate-pulse">█</div>
          </div>
        </div>
      </div>

      {/* TIM KIPPER'S GTM JOURNEY */}
      <div className="bg-black border-2 border-cyan-500/50 rounded-lg p-6">
        <div className="text-cyan-400 font-bold text-center mb-4 text-xl">
          🚀 AUTONOMOUS GTM PIPELINE 🚀
        </div>
        <div className="text-center text-green-500 text-sm mb-4">
          AGENTS RUN 6AM-11PM CST | 15+ HOURS/DAY OF AUTONOMOUS PROSPECTING
        </div>
        <div className="grid md:grid-cols-4 gap-4 text-center">
          <JourneyMilestone
            year="2022-2024"
            title="FOUNDER-LED SALES"
            description="3 years closing deals at HVAC/MEP contractors"
            icon="💼"
            status="complete"
          />
          <JourneyMilestone
            year="DEC 2025"
            title="AI AGENTS BUILT"
            description="6 LangGraph agents with Claude + Cerebras"
            icon="🤖"
            status="complete"
          />
          <JourneyMilestone
            year="NOW"
            title="SCALING PIPELINE"
            description={`${stats.totalLeads.toLocaleString()} contractors, ${stats.totalContacts} decision makers`}
            icon="📈"
            status="active"
          />
          <JourneyMilestone
            year="2026"
            title="GTME @ COPERNIQ"
            description="First GTM Engineer - hybrid AE/BDR/RevOps"
            icon="🎯"
            status="pending"
          />
        </div>
        <div className="text-center mt-4 text-cyan-600 text-sm">
          Built with Claude Code by Tim Kipper | coperniq.io
        </div>
      </div>
    </div>
  )
}

// ============================================
// SUB-COMPONENTS
// ============================================

function StatBox({ label, value, icon, color }: {
  label: string
  value: number
  icon: string
  color: 'green' | 'cyan' | 'yellow' | 'red' | 'purple' | 'gray' | 'orange'
}) {
  const colorClasses = {
    green: 'border-green-500 text-green-400',
    cyan: 'border-cyan-500 text-cyan-400',
    yellow: 'border-yellow-500 text-yellow-400',
    red: 'border-red-500 text-red-400',
    purple: 'border-purple-500 text-purple-400',
    gray: 'border-gray-500 text-gray-400',
    orange: 'border-orange-500 text-orange-400',
  }

  return (
    <div className={`bg-black border-2 ${colorClasses[color]} rounded-lg p-4 text-center`}>
      <div className="text-2xl mb-1">{icon}</div>
      <div className="text-3xl font-bold tabular-nums">
        {value.toLocaleString()}
      </div>
      <div className="text-xs opacity-70 mt-1">{label}</div>
    </div>
  )
}

function JourneyMilestone({ year, title, description, icon, status }: {
  year: string
  title: string
  description: string
  icon: string
  status: 'complete' | 'active' | 'pending'
}) {
  return (
    <div className={`p-4 rounded-lg border ${
      status === 'complete' ? 'border-green-500 bg-green-900/20' :
      status === 'active' ? 'border-cyan-500 bg-cyan-900/20 animate-pulse' :
      'border-gray-600 bg-gray-900/20'
    }`}>
      <div className="text-3xl mb-2">{icon}</div>
      <div className={`text-xs font-bold ${
        status === 'complete' ? 'text-green-400' :
        status === 'active' ? 'text-cyan-400' : 'text-gray-500'
      }`}>
        {year}
      </div>
      <div className={`font-bold ${
        status === 'complete' ? 'text-green-300' :
        status === 'active' ? 'text-cyan-300' : 'text-gray-400'
      }`}>
        {title}
      </div>
      <div className="text-xs text-gray-500 mt-1">{description}</div>
      {status === 'complete' && <div className="text-green-400 mt-2">✓</div>}
      {status === 'active' && <div className="text-cyan-400 mt-2">●</div>}
      {status === 'pending' && <div className="text-gray-500 mt-2">○</div>}
    </div>
  )
}

function VerticalBox({ label, count, icon }: {
  label: string
  count: number
  icon: string
}) {
  return (
    <div className="p-2 rounded border border-purple-500/30 bg-purple-900/10">
      <div className="text-xl">{icon}</div>
      <div className="text-lg font-bold text-purple-400">{count.toLocaleString()}</div>
      <div className="text-[10px] text-purple-600">{label}</div>
    </div>
  )
}

function SegmentBox({ label, count, color }: {
  label: string
  count: number
  color: 'green' | 'blue' | 'purple' | 'orange'
}) {
  const colorClasses = {
    green: 'border-green-500/30 bg-green-900/10 text-green-400',
    blue: 'border-blue-500/30 bg-blue-900/10 text-blue-400',
    purple: 'border-purple-500/30 bg-purple-900/10 text-purple-400',
    orange: 'border-orange-500/30 bg-orange-900/10 text-orange-400',
  }

  return (
    <div className={`p-2 rounded border ${colorClasses[color]}`}>
      <div className="text-lg font-bold">{count.toLocaleString()}</div>
      <div className="text-[10px] opacity-70">{label}</div>
    </div>
  )
}

function getLogColor(type: ActivityLog['type']): string {
  switch (type) {
    case 'system': return 'text-green-600'
    case 'agent': return 'text-cyan-400'
    case 'success': return 'text-green-300 font-bold'
    case 'enrichment': return 'text-yellow-400'
    case 'discovery': return 'text-purple-400 font-bold'
    default: return 'text-green-400'
  }
}

function getEventLogType(eventType: string): ActivityLog['type'] {
  switch (eventType) {
    case 'lead_enriched':
      return 'enrichment'
    case 'lead_qualified':
    case 'opportunity_created':
      return 'success'
    case 'contact_added':
      return 'discovery'
    case 'icp_scored':
    case 'email_sent':
    case 'call_logged':
      return 'agent'
    default:
      return 'system'
  }
}

function getAgentIcon(agentType: string): string {
  const icons: Record<string, string> = {
    'lead_scout': '🔍',
    'icp_checker': '📊',
    'prediction_agent': '🎯',
    'morning_briefing': '📋',
    'sales_intel': '🧠',
    'bdr_outreach': '✉️',
  }
  return icons[agentType] || '🤖'
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
