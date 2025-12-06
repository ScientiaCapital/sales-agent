"use client";

import { Users, Target, DollarSign, TrendingUp, AlertCircle } from "lucide-react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

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

function KPICardSkeleton() {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-4" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-8 w-20 mb-1" />
        <Skeleton className="h-3 w-32" />
      </CardContent>
    </Card>
  );
}

export function ExecutiveSummary() {
  const { data: metrics, isLoading, error } = useSWR<MetricsSummary>(
    "/api/dashboard/metrics",
    fetcher,
    { refreshInterval: 300000 } // Refresh every 5 minutes
  );

  if (error) {
    return (
      <section className="mb-8">
        <h2 className="text-2xl font-bold mb-4 text-[var(--turkish-blue)]">
          Executive Summary
        </h2>
        <Card>
          <CardContent className="pt-6">
            <div className="text-center py-6 text-red-500">
              <AlertCircle className="h-8 w-8 mx-auto mb-2" />
              <p className="font-medium">Failed to load metrics</p>
              <p className="text-sm text-muted-foreground">
                Please check if the backend server is running
              </p>
            </div>
          </CardContent>
        </Card>
      </section>
    );
  }

  if (isLoading || !metrics) {
    return (
      <section className="mb-8">
        <h2 className="text-2xl font-bold mb-4 text-[var(--turkish-blue)]">
          Executive Summary
        </h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <KPICardSkeleton />
          <KPICardSkeleton />
          <KPICardSkeleton />
          <KPICardSkeleton />
        </div>
      </section>
    );
  }

  const kpiCards = [
    {
      title: "Lead Pipeline",
      value: metrics.qualified_leads.toLocaleString(),
      subtitle: `${metrics.total_leads.toLocaleString()} total leads imported`,
      icon: Users,
      trend: `${formatPercent(metrics.qualification_rate)} qualification rate`,
      color: "text-blue-600",
    },
    {
      title: "Conversion Rate",
      value: formatPercent(metrics.win_rate),
      subtitle: `${metrics.won_deals} won / ${metrics.opportunities} opportunities`,
      icon: Target,
      trend: `${formatPercent(metrics.meeting_conversion_rate)} meeting → opp`,
      color: "text-green-600",
    },
    {
      title: "Cost Efficiency",
      value: formatCurrency(metrics.cost_per_lead, 3),
      subtitle: `${formatCurrency(metrics.total_cost_usd)} total AI costs`,
      icon: DollarSign,
      trend: `${metrics.avg_qualification_time_ms.toFixed(0)}ms avg qualification`,
      color: "text-amber-600",
    },
    {
      title: "Pipeline Revenue",
      value: formatCurrency(metrics.total_revenue),
      subtitle: `${formatCurrency(metrics.avg_deal_size)} avg deal size`,
      icon: TrendingUp,
      trend: `${metrics.meetings_booked} meetings booked`,
      color: "text-emerald-600",
    },
  ];

  return (
    <section className="mb-8">
      <h2 className="text-2xl font-bold mb-4 text-[var(--turkish-blue)]">
        Executive Summary
      </h2>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {kpiCards.map((card) => (
          <Card key={card.title} className="hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {card.title}
              </CardTitle>
              <card.icon className={`h-4 w-4 ${card.color}`} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{card.value}</div>
              <p className="text-xs text-muted-foreground">{card.subtitle}</p>
              <p className="text-xs text-muted-foreground mt-1 border-t pt-1">
                {card.trend}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
