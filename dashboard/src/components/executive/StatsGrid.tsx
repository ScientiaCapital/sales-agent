import useSWR from "swr";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Target,
  Users,
  Phone,
  Mail,
  TrendingUp,
  DollarSign,
  CircleDollarSign,
  Percent,
} from "lucide-react";

interface MetricsSummary {
  total_leads: number;
  qualified_leads: number;
  meetings_booked: number;
  opportunities: number;
  won_deals: number;
  lost_deals: number;
  qualification_rate: number;
  meeting_conversion_rate: number;
  opportunity_conversion_rate: number;
  win_rate: number;
  avg_qualification_time_ms: number;
  total_cost_usd: number;
  cost_per_lead: number;
  total_revenue: number;
  avg_deal_size: number;
  period_start: string;
  period_end: string;
  // Executive Dashboard KPIs
  icp_fit_count: number;
  atl_contacts: number;
  call_ready: number;
  outreach_sent: number;
}

interface ICPQueueResponse {
  summary: {
    total_leads: number;
    untouched_count: number;
    by_quarter: { Q3: number; Q4: number; PPL: number };
  };
  smart_views: Record<
    string,
    {
      name: string;
      color: string;
      priority: number;
      total: number;
      untouched: number;
      leads: any[];
    }
  >;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

function formatCurrency(value: number, decimals = 0): string {
  if (value >= 1000000) {
    return `$${(value / 1000000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `$${(value / 1000).toFixed(0)}K`;
  }
  if (decimals > 0) {
    return `$${value.toFixed(decimals)}`;
  }
  return `$${value.toFixed(0)}`;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle: string;
  icon: React.ElementType;
  color: string;
  bgColor: string;
}

function StatCard({ title, value, subtitle, icon: Icon, color, bgColor }: StatCardProps) {
  return (
    <Card className="border border-gray-700/50 bg-gradient-to-br from-slate-900/90 to-slate-800/90 hover:shadow-lg hover:shadow-purple-500/10 transition-all duration-300">
      <CardContent className="p-6">
        <div className="flex items-start justify-between mb-3">
          <div className={`p-3 rounded-xl ${bgColor} bg-opacity-10`}>
            <Icon className={`h-6 w-6 ${color}`} />
          </div>
        </div>
        <div className="text-4xl font-bold mb-2 text-white">{value}</div>
        <div className="text-sm font-medium text-gray-300 mb-1">{title}</div>
        <div className="text-xs text-gray-500">{subtitle}</div>
      </CardContent>
    </Card>
  );
}

function StatCardSkeleton() {
  return (
    <Card className="border border-gray-700/50 bg-gradient-to-br from-slate-900/90 to-slate-800/90">
      <CardContent className="p-6">
        <div className="flex items-start justify-between mb-3">
          <Skeleton className="h-12 w-12 rounded-xl" />
        </div>
        <Skeleton className="h-10 w-24 mb-2" />
        <Skeleton className="h-4 w-32 mb-1" />
        <Skeleton className="h-3 w-40" />
      </CardContent>
    </Card>
  );
}

export function StatsGrid() {
  const { data: metrics, isLoading: metricsLoading } = useSWR<MetricsSummary>(
    "/api/dashboard/metrics",
    fetcher,
    { refreshInterval: 300000 }
  );

  const { data: icpData, isLoading: icpLoading } = useSWR<ICPQueueResponse>(
    "/api/dashboard/icp-queue?days=7&limit=10",
    fetcher,
    { refreshInterval: 60000 }
  );

  if (metricsLoading || icpLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[...Array(8)].map((_, i) => (
          <StatCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (!metrics || !icpData) {
    return null;
  }

  // Use real KPI data from backend
  const icpFitCount = metrics.icp_fit_count || 0;
  const atlContacts = metrics.atl_contacts || 0;
  const callReady = metrics.call_ready || 0;
  const outreachSent = metrics.outreach_sent || 0;

  // Row 1: Sales-Focused KPIs
  const row1Cards = [
    {
      title: "ICP Fit Count",
      value: icpFitCount.toLocaleString(),
      subtitle: "Companies matching ICP criteria",
      icon: Target,
      color: "text-green-400",
      bgColor: "bg-green-500",
    },
    {
      title: "ATL Contacts",
      value: atlContacts.toLocaleString(),
      subtitle: "Above-the-line decision makers",
      icon: Users,
      color: "text-purple-400",
      bgColor: "bg-purple-500",
    },
    {
      title: "Call-Ready",
      value: callReady.toLocaleString(),
      subtitle: "Contacts with phone numbers",
      icon: Phone,
      color: "text-blue-400",
      bgColor: "bg-blue-500",
    },
    {
      title: "Outreach Sent",
      value: outreachSent.toLocaleString(),
      subtitle: "Emails/SMS sent today",
      icon: Mail,
      color: "text-orange-400",
      bgColor: "bg-orange-500",
    },
  ];

  // Row 2: Pipeline-Focused KPIs
  const row2Cards = [
    {
      title: "Total Leads",
      value: metrics.total_leads.toLocaleString(),
      subtitle: `${metrics.qualified_leads} qualified`,
      icon: TrendingUp,
      color: "text-blue-400",
      bgColor: "bg-blue-500",
    },
    {
      title: "Conversion Rate",
      value: formatPercent(metrics.win_rate),
      subtitle: `${metrics.won_deals} won / ${metrics.opportunities} opps`,
      icon: Percent,
      color: "text-green-400",
      bgColor: "bg-green-500",
    },
    {
      title: "Pipeline Revenue",
      value: formatCurrency(metrics.total_revenue),
      subtitle: `${formatCurrency(metrics.avg_deal_size)} avg deal`,
      icon: CircleDollarSign,
      color: "text-emerald-400",
      bgColor: "bg-emerald-500",
    },
    {
      title: "Cost per Lead",
      value: formatCurrency(metrics.cost_per_lead, 3),
      subtitle: `${formatCurrency(metrics.total_cost_usd)} total AI costs`,
      icon: DollarSign,
      color: "text-amber-400",
      bgColor: "bg-amber-500",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Row 1: Sales-Focused */}
      <div>
        <h3 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">
          Sales Metrics
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {row1Cards.map((card) => (
            <StatCard key={card.title} {...card} />
          ))}
        </div>
      </div>

      {/* Row 2: Pipeline-Focused */}
      <div>
        <h3 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">
          Pipeline Performance
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {row2Cards.map((card) => (
            <StatCard key={card.title} {...card} />
          ))}
        </div>
      </div>
    </div>
  );
}
