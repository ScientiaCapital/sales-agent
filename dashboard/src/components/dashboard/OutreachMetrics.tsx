"use client";

import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Phone,
  Mail,
  MessageSquare,
  Calendar,
  TrendingUp,
} from "lucide-react";

interface OutreachMetrics {
  calls: {
    total: number;
    count_7d: number;
    count_mtd: number;
    outbound: number;
    inbound: number;
    avg_duration: number;
  };
  emails: {
    total: number;
    count_7d: number;
    count_mtd: number;
    sent: number;
    received: number;
  };
  sms: {
    total: number;
    count_7d: number;
    count_mtd: number;
    sent: number;
    received: number;
  };
  meetings: {
    total: number;
    count_7d: number;
    count_mtd: number;
    scheduled: number;
    completed: number;
  };
}

interface OutreachResponse {
  metrics: OutreachMetrics;
  summary: {
    total_outreach: number;
    total_7d: number;
    meetings_booked: number;
    response_rate: number;
  };
  period: string;
  data_source: string;
  updated_at: string;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

function MetricsSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-4">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="text-center">
          <Skeleton className="h-8 w-16 mx-auto mb-1" />
          <Skeleton className="h-3 w-12 mx-auto" />
        </div>
      ))}
    </div>
  );
}

function formatDuration(seconds: number): string {
  if (!seconds) return "0:00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

interface OutreachMetricsProps {
  period?: "7d" | "mtd";
}

export function OutreachMetrics({ period = "7d" }: OutreachMetricsProps) {
  const { data, isLoading } = useSWR<OutreachResponse>(
    `/api/outreach?period=${period}`,
    fetcher,
    { refreshInterval: 120000 } // Refresh every 2 min
  );

  if (isLoading || !data) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Outreach (Close CRM)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <MetricsSkeleton />
        </CardContent>
      </Card>
    );
  }

  const { metrics, summary } = data;

  const activityCards = [
    {
      icon: Phone,
      label: "Calls",
      value: period === "7d" ? metrics.calls.count_7d : metrics.calls.count_mtd,
      sublabel: `${metrics.calls.outbound} out / ${metrics.calls.inbound} in`,
      extra: `Avg: ${formatDuration(metrics.calls.avg_duration)}`,
      color: "text-blue-600",
      bgColor: "bg-blue-50",
    },
    {
      icon: Mail,
      label: "Emails",
      value: period === "7d" ? metrics.emails.count_7d : metrics.emails.count_mtd,
      sublabel: `${metrics.emails.sent} sent / ${metrics.emails.received} received`,
      color: "text-purple-600",
      bgColor: "bg-purple-50",
    },
    {
      icon: MessageSquare,
      label: "SMS",
      value: period === "7d" ? metrics.sms.count_7d : metrics.sms.count_mtd,
      sublabel: `${metrics.sms.sent} sent / ${metrics.sms.received} received`,
      color: "text-green-600",
      bgColor: "bg-green-50",
    },
    {
      icon: Calendar,
      label: "Meetings",
      value: period === "7d" ? metrics.meetings.count_7d : metrics.meetings.count_mtd,
      sublabel: `${metrics.meetings.completed} completed`,
      color: "text-amber-600",
      bgColor: "bg-amber-50",
    },
  ];

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Outreach (Close CRM)
          </CardTitle>
          <Badge
            variant="outline"
            className={
              summary.response_rate >= 15
                ? "border-green-500 text-green-600"
                : "border-amber-500 text-amber-600"
            }
          >
            {summary.response_rate}% response
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {/* Summary */}
        <div className="flex gap-4 mb-4 pb-4 border-b">
          <div className="text-center">
            <p className="text-2xl font-bold text-[var(--turkish-blue)]">
              {summary.total_7d}
            </p>
            <p className="text-xs text-muted-foreground">Total (7d)</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-green-600">
              {summary.meetings_booked}
            </p>
            <p className="text-xs text-muted-foreground">Meetings</p>
          </div>
        </div>

        {/* Activity Grid */}
        <div className="grid grid-cols-2 gap-3">
          {activityCards.map((card) => (
            <div
              key={card.label}
              className={`${card.bgColor} rounded-lg p-3 text-center`}
            >
              <card.icon className={`h-5 w-5 mx-auto mb-1 ${card.color}`} />
              <p className="text-xl font-bold">{card.value}</p>
              <p className="text-xs font-medium">{card.label}</p>
              <p className="text-xs text-muted-foreground truncate">
                {card.sublabel}
              </p>
              {card.extra && (
                <p className="text-xs text-muted-foreground mt-1">
                  {card.extra}
                </p>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
