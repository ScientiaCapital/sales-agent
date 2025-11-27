"use client";

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
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

interface FunnelStage {
  name: string;
  value: number;
  color: string;
  bgColor: string;
  conversionRate?: number;
}

function FunnelSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-6 w-32" />
      </CardHeader>
      <CardContent className="space-y-3">
        {[100, 85, 60, 40, 25].map((width, i) => (
          <Skeleton key={i} className="h-12" style={{ width: `${width}%` }} />
        ))}
      </CardContent>
    </Card>
  );
}

export function PipelineFunnel() {
  const { data: metrics, isLoading } = useSWR<MetricsSummary>(
    "/api/metrics",
    fetcher,
    { refreshInterval: 300000 }
  );

  if (isLoading || !metrics) {
    return <FunnelSkeleton />;
  }

  // Calculate widths based on actual data (max = total_leads)
  const maxValue = metrics.total_leads;

  const stages: FunnelStage[] = [
    {
      name: "Total Leads (MQL)",
      value: metrics.total_leads,
      color: "text-slate-700",
      bgColor: "bg-slate-200",
    },
    {
      name: "Qualified (SQL)",
      value: metrics.qualified_leads,
      color: "text-blue-700",
      bgColor: "bg-blue-200",
      conversionRate: metrics.qualification_rate,
    },
    {
      name: "Meetings Booked",
      value: metrics.meetings_booked,
      color: "text-indigo-700",
      bgColor: "bg-indigo-200",
      conversionRate: metrics.meeting_conversion_rate,
    },
    {
      name: "Opportunities",
      value: metrics.opportunities,
      color: "text-amber-700",
      bgColor: "bg-amber-200",
      conversionRate: metrics.opportunity_conversion_rate,
    },
    {
      name: "Won Deals",
      value: metrics.won_deals,
      color: "text-green-700",
      bgColor: "bg-green-200",
      conversionRate: metrics.win_rate,
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[var(--turkish-blue)]">
          Pipeline Funnel
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {stages.map((stage, index) => {
            // Calculate width as percentage of max, minimum 15% for visibility
            const widthPercent = Math.max(
              15,
              Math.round((stage.value / maxValue) * 100)
            );

            return (
              <div key={stage.name} className="relative">
                {/* Funnel bar */}
                <div
                  className={`${stage.bgColor} rounded-lg py-3 px-4 transition-all hover:opacity-90`}
                  style={{ width: `${widthPercent}%` }}
                >
                  <div className="flex justify-between items-center">
                    <span className={`font-medium ${stage.color}`}>
                      {stage.name}
                    </span>
                    <span className={`font-bold ${stage.color}`}>
                      {stage.value.toLocaleString()}
                    </span>
                  </div>
                </div>

                {/* Conversion arrow (except for first stage) */}
                {index > 0 && stage.conversionRate && (
                  <div className="absolute -top-2 right-4 text-xs text-muted-foreground bg-white px-1 rounded">
                    ↓ {(stage.conversionRate * 100).toFixed(1)}%
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Summary stats */}
        <div className="mt-6 pt-4 border-t grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Lost Deals:</span>
            <span className="ml-2 font-medium text-red-600">
              {metrics.lost_deals}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">Overall Win Rate:</span>
            <span className="ml-2 font-medium text-green-600">
              {(metrics.win_rate * 100).toFixed(1)}%
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
