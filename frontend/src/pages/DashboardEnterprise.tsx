/**
 * Enterprise Dashboard - Redesigned with ShadCN/ui components
 * Professional, enterprise-level UI with consistent design system
 */

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
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { MetricsCard } from '../components/ui/metrics-card';
import { Separator } from '../components/ui/separator';

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
    const timer = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(timer);
  }, []);

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
        <div className="h-48 bg-slate-200 rounded-xl"></div>
        <div className="grid grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-40 bg-slate-200 rounded-xl"></div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* System Health Alert */}
      <Card className="border-emerald-200 bg-gradient-to-r from-emerald-50 to-green-50">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-emerald-500 rounded-lg">
                <CheckCircle2 className="h-6 w-6 text-white" />
              </div>
              <div>
                <CardTitle className="text-emerald-900">All Systems Operational</CardTitle>
                <CardDescription className="text-emerald-700">
                  99.2% uptime · Avg response time: {mockDashboardData.metrics.avgResponseTime}ms
                </CardDescription>
              </div>
            </div>
            <div className="flex gap-6 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
                <span className="text-emerald-700 font-medium">DB: {mockDashboardData.systemStatus.database.latency}ms</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
                <span className="text-emerald-700 font-medium">Redis: {mockDashboardData.systemStatus.redis.latency}ms</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
                <span className="text-emerald-700 font-medium">AI: {mockDashboardData.systemStatus.cerebras.latency}ms</span>
              </div>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricsCard
          title="Total Leads"
          value={mockDashboardData.metrics.totalLeads}
          description={`Avg Score: ${mockDashboardData.metrics.avgQualificationScore}`}
          icon={Target}
          iconColor="bg-blue-100 text-blue-600"
          trend={{ value: `+${mockDashboardData.metrics.leadsThisWeek} this week`, isPositive: true }}
        />
        <MetricsCard
          title="Research Reports"
          value={mockDashboardData.metrics.researchReports}
          description="Avg Time: <10s"
          icon={Brain}
          iconColor="bg-emerald-100 text-emerald-600"
          trend={{ value: `+${mockDashboardData.metrics.reportsThisWeek} this week`, isPositive: true }}
        />
        <MetricsCard
          title="Messages Sent"
          value={mockDashboardData.metrics.messagesSent.toLocaleString()}
          description={`${mockDashboardData.metrics.campaignsActive} active campaigns`}
          icon={MessageSquare}
          iconColor="bg-purple-100 text-purple-600"
          trend={{ value: `+${mockDashboardData.metrics.messagesThisWeek} this week`, isPositive: true }}
        />
        <MetricsCard
          title="Conversations"
          value={mockDashboardData.metrics.conversationsTracked}
          description="Avg duration: 12m"
          icon={Phone}
          iconColor="bg-orange-100 text-orange-600"
          trend={{ value: `+${mockDashboardData.metrics.conversationsToday} today`, isPositive: true }}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Lead Activity (Last 7 Days)</CardTitle>
            <CardDescription>Qualified vs Total Leads</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-80">
              <Line data={leadsTrendData} options={leadsTrendOptions} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Top Industries</CardTitle>
            <CardDescription>Lead Distribution</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-80">
              <Doughnut data={industryData} options={industryOptions} />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Activity & Top Performers */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Recent Activity</CardTitle>
                <CardDescription>Live updates from all systems</CardDescription>
              </div>
              <Badge variant="success">
                <Activity className="h-3 w-3 mr-1" />
                Live
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y">
              {mockDashboardData.recentActivity.map((activity, index) => (
                <div key={index} className="p-6 hover:bg-slate-50 transition-colors">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-4 flex-1">
                      <div className={`p-2 rounded-lg ${
                        activity.color === 'green' ? 'bg-emerald-100' :
                        activity.color === 'blue' ? 'bg-blue-100' :
                        activity.color === 'purple' ? 'bg-purple-100' :
                        'bg-orange-100'
                      }`}>
                        {activity.type === 'lead' && <Target className="h-4 w-4 text-emerald-700" />}
                        {activity.type === 'research' && <Brain className="h-4 w-4 text-blue-700" />}
                        {activity.type === 'campaign' && <MessageSquare className="h-4 w-4 text-purple-700" />}
                        {activity.type === 'conversation' && <Phone className="h-4 w-4 text-orange-700" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-semibold text-slate-900">
                            {activity.company || activity.name}
                          </span>
                          {activity.score && (
                            <Badge variant={activity.score >= 80 ? 'success' : activity.score >= 60 ? 'info' : 'warning'}>
                              Score: {activity.score}
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-slate-600">{activity.action}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <Clock className="h-4 w-4" />
                      {activity.time}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
          <Separator />
          <CardContent className="py-4">
            <Button variant="ghost" className="w-full">
              View all activity <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Top Leads</CardTitle>
            <CardDescription>Highest scores</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {mockDashboardData.topPerformers.map((lead, index) => (
              <div key={index} className="flex items-center justify-between p-4 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors">
                <div className="flex items-center gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 text-white font-bold">
                    {index + 1}
                  </div>
                  <div>
                    <p className="font-semibold text-slate-900">{lead.company}</p>
                    <p className="text-sm text-slate-500">{lead.industry}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold text-emerald-600">{lead.score}</p>
                  <p className="text-xs text-slate-500">{lead.trend === 'up' ? '↗ Rising' : '→ Stable'}</p>
                </div>
              </div>
            ))}
            <Link to="/leads" className="block">
              <Button variant="outline" className="w-full">
                View all rankings
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* Performance Stats & CTA */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-indigo-600" />
              Platform Performance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-6">
              <div className="text-center">
                <div className="text-3xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent mb-2">
                  633ms
                </div>
                <p className="text-sm font-medium text-slate-700">Lead Qualification</p>
                <p className="text-xs text-slate-500">Cerebras AI</p>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold bg-gradient-to-r from-emerald-600 to-green-600 bg-clip-text text-transparent mb-2">
                  &lt;10s
                </div>
                <p className="text-sm font-medium text-slate-700">Research Pipeline</p>
                <p className="text-xs text-slate-500">5 AI Agents</p>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent mb-2">
                  42%
                </div>
                <p className="text-sm font-medium text-slate-700">Reply Rate</p>
                <p className="text-xs text-slate-500">A/B Tested</p>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold bg-gradient-to-r from-orange-600 to-red-600 bg-clip-text text-transparent mb-2">
                  &lt;100ms
                </div>
                <p className="text-sm font-medium text-slate-700">Voice Latency</p>
                <p className="text-xs text-slate-500">Real-time</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-600 border-0 text-white">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Zap className="h-6 w-6 animate-pulse" />
              Ready to scale your outreach?
            </CardTitle>
            <CardDescription className="text-indigo-100">
              Our AI agents have processed {mockDashboardData.metrics.totalLeads} leads with {mockDashboardData.metrics.avgQualificationScore}% average score
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Link to="/csv-import" className="block">
              <Button variant="secondary" size="lg" className="w-full">
                Import Leads
              </Button>
            </Link>
            <Link to="/campaigns" className="block">
              <Button variant="outline" size="lg" className="w-full bg-white/10 text-white border-white/20 hover:bg-white/20">
                New Campaign
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

