import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import type { ChartOptions } from 'chart.js';
import { Line, Doughnut } from 'react-chartjs-2';
import {
  TrendingUp,
  MessageSquare,
  Zap,
  ArrowRight,
  Target,
  Brain,
  Phone,
  CheckCircle2,
  Clock,
  Activity
} from 'lucide-react';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

// Mock data - replace with real API calls later
const mockDashboardData = {
  metrics: {
    totalLeads: 247,
    leadsThisWeek: 42,
    avgQualificationScore: 73.5,
    researchReports: 156,
    reportsThisWeek: 28,
    campaignsActive: 5,
    messagesSent: 1834,
    messagesThisWeek: 312,
    conversationsTracked: 89,
    conversationsToday: 12,
    systemHealth: 99.2,
    avgResponseTime: 633
  },
  leadsTrend: {
    labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    qualified: [12, 19, 15, 23, 18, 14, 8],
    total: [18, 25, 22, 31, 27, 19, 12]
  },
  industryBreakdown: {
    labels: ['SaaS', 'Fintech', 'Healthcare', 'E-commerce', 'Manufacturing', 'Other'],
    data: [32, 24, 18, 14, 8, 4]
  },
  recentActivity: [
    { type: 'lead', company: 'Acme Corp', action: 'Qualified', score: 87, time: '2 min ago', color: 'green' },
    { type: 'research', company: 'TechStart Inc', action: 'Research completed', time: '8 min ago', color: 'blue' },
    { type: 'campaign', name: 'Q4 Enterprise Outreach', action: 'Message sent', time: '12 min ago', color: 'purple' },
    { type: 'conversation', company: 'DataFlow Systems', action: 'Call ended', time: '18 min ago', color: 'orange' },
    { type: 'lead', company: 'CloudScale LLC', action: 'Qualified', score: 91, time: '23 min ago', color: 'green' },
    { type: 'research', company: 'AI Dynamics', action: 'Research completed', time: '31 min ago', color: 'blue' },
  ],
  topPerformers: [
    { company: 'Acme Corp', score: 91, industry: 'SaaS', trend: 'up' },
    { company: 'DataFlow Systems', score: 87, industry: 'Fintech', trend: 'up' },
    { company: 'CloudScale LLC', score: 84, industry: 'SaaS', trend: 'stable' },
  ],
  systemStatus: {
    database: { status: 'operational', latency: 12 },
    redis: { status: 'operational', latency: 2 },
    cerebras: { status: 'operational', latency: 633 },
    research: { status: 'operational', latency: 8247 }
  }
};

export function Dashboard() {
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Simulate loading
    const timer = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(timer);
  }, []);

  // Chart configurations
  const leadsTrendData = {
    labels: mockDashboardData.leadsTrend.labels,
    datasets: [
      {
        label: 'Qualified Leads',
        data: mockDashboardData.leadsTrend.qualified,
        borderColor: 'rgb(99, 102, 241)',
        backgroundColor: 'rgba(99, 102, 241, 0.1)',
        tension: 0.4,
        fill: true,
      },
      {
        label: 'Total Leads',
        data: mockDashboardData.leadsTrend.total,
        borderColor: 'rgb(203, 213, 225)',
        backgroundColor: 'rgba(203, 213, 225, 0.1)',
        tension: 0.4,
        fill: true,
      },
    ],
  };

  const leadsTrendOptions: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
        labels: {
          usePointStyle: true,
          padding: 15,
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: {
          precision: 0,
        },
      },
    },
  };

  const industryData = {
    labels: mockDashboardData.industryBreakdown.labels,
    datasets: [
      {
        data: mockDashboardData.industryBreakdown.data,
        backgroundColor: [
          'rgba(99, 102, 241, 0.8)',
          'rgba(34, 197, 94, 0.8)',
          'rgba(168, 85, 247, 0.8)',
          'rgba(251, 146, 60, 0.8)',
          'rgba(59, 130, 246, 0.8)',
          'rgba(156, 163, 175, 0.8)',
        ],
        borderWidth: 0,
      },
    ],
  };

  const industryOptions: ChartOptions<'doughnut'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'right' as const,
        labels: {
          padding: 15,
          usePointStyle: true,
        },
      },
    },
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-48 bg-gray-200 rounded-2xl"></div>
        <div className="grid grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-40 bg-gray-200 rounded-xl"></div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-8">
      {/* System Health Banner */}
      <div className="bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-200 rounded-xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex items-center space-x-4">
            <div className="p-3 bg-green-500 rounded-lg shadow-md">
              <CheckCircle2 className="w-6 h-6 text-white" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-green-900 mb-1">All Systems Operational</h3>
              <p className="text-base text-green-800 font-medium">99.2% uptime · Avg response time: {mockDashboardData.metrics.avgResponseTime}ms</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse shadow-sm"></div>
              <span className="text-green-800 font-medium">Database: {mockDashboardData.systemStatus.database.latency}ms</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse shadow-sm"></div>
              <span className="text-green-800 font-medium">Redis: {mockDashboardData.systemStatus.redis.latency}ms</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse shadow-sm"></div>
              <span className="text-green-800 font-medium">AI: {mockDashboardData.systemStatus.cerebras.latency}ms</span>
            </div>
          </div>
        </div>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Lead Metrics */}
        <div className="bg-white rounded-xl shadow-md hover:shadow-xl transition-all border-2 border-gray-100 overflow-hidden group">
          <div className="p-8">
            <div className="flex items-center justify-between mb-6">
              <div className="p-4 bg-blue-50 rounded-xl group-hover:bg-blue-100 transition-colors shadow-sm">
                <Target className="w-7 h-7 text-blue-600" />
              </div>
              <div className="text-right">
                <div className="text-sm font-semibold text-gray-600 mb-1">This Week</div>
                <div className="text-lg font-bold text-blue-600">+{mockDashboardData.metrics.leadsThisWeek}</div>
              </div>
            </div>
            <h3 className="text-base font-semibold text-gray-600 mb-3">Total Leads</h3>
            <div className="flex items-baseline mb-4">
              <span className="text-5xl font-bold text-gray-900 leading-none">{mockDashboardData.metrics.totalLeads}</span>
              <TrendingUp className="w-6 h-6 text-green-500 ml-3" />
            </div>
            <div className="flex items-center justify-between pt-4 border-t border-gray-100">
              <span className="text-base font-medium text-gray-700">Avg Score: {mockDashboardData.metrics.avgQualificationScore}</span>
              <span className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-bold bg-green-100 text-green-800 shadow-sm">
                +17% ↗
              </span>
            </div>
          </div>
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 px-8 py-4 border-t-2 border-blue-100">
            <Link to="/leads" className="text-base font-semibold text-blue-700 hover:text-blue-800 flex items-center group">
              View all leads
              <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </div>

        {/* Research Metrics */}
        <div className="bg-white rounded-xl shadow-md hover:shadow-xl transition-all border-2 border-gray-100 overflow-hidden group">
          <div className="p-8">
            <div className="flex items-center justify-between mb-6">
              <div className="p-4 bg-green-50 rounded-xl group-hover:bg-green-100 transition-colors shadow-sm">
                <Brain className="w-7 h-7 text-green-600" />
              </div>
              <div className="text-right">
                <div className="text-sm font-semibold text-gray-600 mb-1">This Week</div>
                <div className="text-lg font-bold text-green-600">+{mockDashboardData.metrics.reportsThisWeek}</div>
              </div>
            </div>
            <h3 className="text-base font-semibold text-gray-600 mb-3">Research Reports</h3>
            <div className="flex items-baseline mb-4">
              <span className="text-5xl font-bold text-gray-900 leading-none">{mockDashboardData.metrics.researchReports}</span>
              <TrendingUp className="w-6 h-6 text-green-500 ml-3" />
            </div>
            <div className="flex items-center justify-between pt-4 border-t border-gray-100">
              <span className="text-base font-medium text-gray-700">Avg Time: &lt;10s</span>
              <span className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-bold bg-green-100 text-green-800 shadow-sm">
                +22% ↗
              </span>
            </div>
          </div>
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 px-8 py-4 border-t-2 border-green-100">
            <Link to="/research" className="text-base font-semibold text-green-700 hover:text-green-800 flex items-center group">
              Start research
              <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </div>

        {/* Campaign Metrics */}
        <div className="bg-white rounded-xl shadow-md hover:shadow-xl transition-all border-2 border-gray-100 overflow-hidden group">
          <div className="p-8">
            <div className="flex items-center justify-between mb-6">
              <div className="p-4 bg-purple-50 rounded-xl group-hover:bg-purple-100 transition-colors shadow-sm">
                <MessageSquare className="w-7 h-7 text-purple-600" />
              </div>
              <div className="text-right">
                <div className="text-sm font-semibold text-gray-600 mb-1">This Week</div>
                <div className="text-lg font-bold text-purple-600">+{mockDashboardData.metrics.messagesThisWeek}</div>
              </div>
            </div>
            <h3 className="text-base font-semibold text-gray-600 mb-3">Messages Sent</h3>
            <div className="flex items-baseline mb-4">
              <span className="text-5xl font-bold text-gray-900 leading-none">{mockDashboardData.metrics.messagesSent.toLocaleString()}</span>
              <TrendingUp className="w-6 h-6 text-green-500 ml-3" />
            </div>
            <div className="flex items-center justify-between pt-4 border-t border-gray-100">
              <span className="text-base font-medium text-gray-700">{mockDashboardData.metrics.campaignsActive} active campaigns</span>
              <span className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-bold bg-purple-100 text-purple-800 shadow-sm">
                42% reply rate
              </span>
            </div>
          </div>
          <div className="bg-gradient-to-r from-purple-50 to-pink-50 px-8 py-4 border-t-2 border-purple-100">
            <Link to="/campaigns" className="text-base font-semibold text-purple-700 hover:text-purple-800 flex items-center group">
              Manage campaigns
              <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </div>

        {/* Conversation Metrics */}
        <div className="bg-white rounded-xl shadow-md hover:shadow-xl transition-all border-2 border-gray-100 overflow-hidden group">
          <div className="p-8">
            <div className="flex items-center justify-between mb-6">
              <div className="p-4 bg-orange-50 rounded-xl group-hover:bg-orange-100 transition-colors shadow-sm">
                <Phone className="w-7 h-7 text-orange-600" />
              </div>
              <div className="text-right">
                <div className="text-sm font-semibold text-gray-600 mb-1">Today</div>
                <div className="text-lg font-bold text-orange-600">+{mockDashboardData.metrics.conversationsToday}</div>
              </div>
            </div>
            <h3 className="text-base font-semibold text-gray-600 mb-3">Conversations</h3>
            <div className="flex items-baseline mb-4">
              <span className="text-5xl font-bold text-gray-900 leading-none">{mockDashboardData.metrics.conversationsTracked}</span>
              <Activity className="w-6 h-6 text-orange-500 ml-3 animate-pulse" />
            </div>
            <div className="flex items-center justify-between pt-4 border-t border-gray-100">
              <span className="text-base font-medium text-gray-700">Avg duration: 12m</span>
              <span className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-bold bg-orange-100 text-orange-800 shadow-sm">
                3 active now
              </span>
            </div>
          </div>
          <div className="bg-gradient-to-r from-orange-50 to-amber-50 px-8 py-4 border-t-2 border-orange-100">
            <Link to="/conversations" className="text-base font-semibold text-orange-700 hover:text-orange-800 flex items-center group">
              View conversations
              <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Lead Trend Chart */}
        <div className="lg:col-span-2 bg-white rounded-xl shadow-md border-2 border-gray-100 overflow-hidden">
          <div className="px-8 py-5 border-b-2 border-gray-100 bg-gradient-to-r from-gray-50 to-slate-50">
            <h2 className="text-xl font-bold text-gray-900 mb-1">Lead Activity (Last 7 Days)</h2>
            <p className="text-base text-gray-700 font-medium">Qualified vs Total Leads</p>
          </div>
          <div className="p-8">
            <div className="h-80">
              <Line data={leadsTrendData} options={leadsTrendOptions} />
            </div>
          </div>
        </div>

        {/* Industry Breakdown */}
        <div className="bg-white rounded-xl shadow-md border-2 border-gray-100 overflow-hidden">
          <div className="px-8 py-5 border-b-2 border-gray-100 bg-gradient-to-r from-gray-50 to-slate-50">
            <h2 className="text-xl font-bold text-gray-900 mb-1">Top Industries</h2>
            <p className="text-base text-gray-700 font-medium">Lead Distribution</p>
          </div>
          <div className="p-8">
            <div className="h-80">
              <Doughnut data={industryData} options={industryOptions} />
            </div>
          </div>
        </div>
      </div>

      {/* Activity Feed and Top Performers */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Activity */}
        <div className="lg:col-span-2 bg-white rounded-xl shadow-md border-2 border-gray-100 overflow-hidden">
          <div className="px-8 py-5 border-b-2 border-gray-100 bg-gradient-to-r from-gray-50 to-slate-50 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-gray-900 mb-1">Recent Activity</h2>
              <p className="text-base text-gray-700 font-medium">Live updates from all systems</p>
            </div>
            <div className="flex items-center text-sm text-green-700 font-bold">
              <div className="w-3 h-3 bg-green-500 rounded-full mr-2 animate-pulse shadow-sm"></div>
              Live
            </div>
          </div>
          <div className="divide-y-2 divide-gray-100">
            {mockDashboardData.recentActivity.map((activity, index) => (
              <div key={index} className="px-8 py-5 hover:bg-gray-50 transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start space-x-4 flex-1">
                    <div className={`p-3 ${
                      activity.color === 'green' ? 'bg-green-100' :
                      activity.color === 'blue' ? 'bg-blue-100' :
                      activity.color === 'purple' ? 'bg-purple-100' :
                      'bg-orange-100'
                    } rounded-xl mt-0.5 shadow-sm`}>
                      {activity.type === 'lead' && <Target className="w-5 h-5 text-green-700" />}
                      {activity.type === 'research' && <Brain className="w-5 h-5 text-blue-700" />}
                      {activity.type === 'campaign' && <MessageSquare className="w-5 h-5 text-purple-700" />}
                      {activity.type === 'conversation' && <Phone className="w-5 h-5 text-orange-700" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-3 mb-1 flex-wrap">
                        <span className="font-bold text-base text-gray-900">
                          {activity.company || activity.name}
                        </span>
                        {activity.score && (
                          <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-bold ${
                            activity.score >= 80 ? 'bg-green-100 text-green-800' :
                            activity.score >= 60 ? 'bg-blue-100 text-blue-800' :
                            'bg-yellow-100 text-yellow-800'
                          } shadow-sm`}>
                            Score: {activity.score}
                          </span>
                        )}
                      </div>
                      <p className="text-base text-gray-700 font-medium">{activity.action}</p>
                    </div>
                  </div>
                  <div className="flex items-center text-sm text-gray-600 font-medium whitespace-nowrap">
                    <Clock className="w-4 h-4 mr-2" />
                    {activity.time}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="px-8 py-5 bg-gray-50 border-t-2 border-gray-100">
            <button className="text-base text-indigo-600 hover:text-indigo-700 font-bold">
              View all activity →
            </button>
          </div>
        </div>

        {/* Top Performers */}
        <div className="bg-white rounded-xl shadow-md border-2 border-gray-100 overflow-hidden">
          <div className="px-8 py-5 border-b-2 border-gray-100 bg-gradient-to-r from-gray-50 to-slate-50">
            <h2 className="text-xl font-bold text-gray-900 mb-1">Top Leads</h2>
            <p className="text-base text-gray-700 font-medium">Highest scores</p>
          </div>
          <div className="p-8 space-y-4">
            {mockDashboardData.topPerformers.map((lead, index) => (
              <div key={index} className="flex items-center justify-between p-5 bg-gradient-to-r from-gray-50 to-white rounded-xl border-2 border-gray-100 hover:shadow-lg transition-all">
                <div className="flex items-center space-x-4">
                  <div className="flex-shrink-0 w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-full flex items-center justify-center text-white font-bold text-lg shadow-md">
                    {index + 1}
                  </div>
                  <div>
                    <p className="text-base font-bold text-gray-900 mb-1">{lead.company}</p>
                    <p className="text-sm text-gray-600 font-medium">{lead.industry}</p>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-green-600 mb-1">{lead.score}</div>
                  <div className="text-sm text-gray-600 font-medium">
                    {lead.trend === 'up' ? '↗ Rising' : '→ Stable'}
                  </div>
                </div>
              </div>
            ))}
            <Link
              to="/leads"
              className="block w-full text-center px-6 py-3 bg-gradient-to-r from-indigo-50 to-purple-50 text-indigo-700 rounded-xl font-bold text-base hover:from-indigo-100 hover:to-purple-100 transition-all shadow-sm border-2 border-indigo-100"
            >
              View all rankings
            </Link>
          </div>
        </div>
      </div>

      {/* Performance Stats */}
      <div className="bg-gradient-to-br from-slate-50 via-gray-50 to-slate-50 rounded-xl border-2 border-gray-200 p-10 shadow-md">
        <h2 className="text-2xl font-bold text-gray-900 mb-8 flex items-center">
          <Zap className="w-8 h-8 text-indigo-600 mr-3" />
          Platform Performance
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          <div className="text-center">
            <div className="text-5xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent mb-3 leading-none">
              633ms
            </div>
            <div className="text-base font-bold text-gray-800 mb-1">Lead Qualification</div>
            <div className="text-sm text-gray-600 font-medium">Cerebras AI</div>
          </div>
          <div className="text-center">
            <div className="text-5xl font-bold bg-gradient-to-r from-green-600 to-emerald-600 bg-clip-text text-transparent mb-3 leading-none">
              &lt;10s
            </div>
            <div className="text-base font-bold text-gray-800 mb-1">Research Pipeline</div>
            <div className="text-sm text-gray-600 font-medium">5 AI Agents</div>
          </div>
          <div className="text-center">
            <div className="text-5xl font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent mb-3 leading-none">
              42%
            </div>
            <div className="text-base font-bold text-gray-800 mb-1">Reply Rate</div>
            <div className="text-sm text-gray-600 font-medium">A/B Tested</div>
          </div>
          <div className="text-center">
            <div className="text-5xl font-bold bg-gradient-to-r from-orange-600 to-red-600 bg-clip-text text-transparent mb-3 leading-none">
              &lt;100ms
            </div>
            <div className="text-base font-bold text-gray-800 mb-1">Voice Latency</div>
            <div className="text-sm text-gray-600 font-medium">Real-time</div>
          </div>
        </div>
      </div>

      {/* Quick Actions CTA */}
      <div className="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 rounded-xl shadow-xl overflow-hidden border-4 border-white">
        <div className="px-10 py-10">
          <div className="flex flex-col lg:flex-row items-center lg:items-start justify-between gap-8">
            <div className="flex-1 text-center lg:text-left">
              <h3 className="text-3xl font-bold text-white mb-3 flex items-center justify-center lg:justify-start">
                <Zap className="w-8 h-8 mr-3 animate-pulse" />
                Ready to scale your outreach?
              </h3>
              <p className="text-indigo-50 text-xl font-medium leading-relaxed">
                Our AI agents have processed {mockDashboardData.metrics.totalLeads} leads with {mockDashboardData.metrics.avgQualificationScore}% average score
              </p>
            </div>
            <div className="flex flex-col gap-4 w-full lg:w-auto">
              <Link
                to="/csv-import"
                className="px-10 py-4 bg-white text-indigo-600 rounded-xl font-bold text-lg hover:bg-indigo-50 transition-all shadow-xl hover:shadow-2xl text-center border-2 border-white"
              >
                Import Leads
              </Link>
              <Link
                to="/campaigns"
                className="px-10 py-4 bg-indigo-500 text-white rounded-xl font-bold text-lg hover:bg-indigo-400 transition-all shadow-xl hover:shadow-2xl border-2 border-white border-opacity-30 text-center"
              >
                New Campaign
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
