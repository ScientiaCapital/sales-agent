"use client";

import { useState } from "react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Mail, Phone, MessageSquare, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

type TimePeriod = "today" | "week" | "month";

interface OutreachStat {
  count: number;
  change: number; // Percentage change from previous period
  trend: "up" | "down" | "neutral";
}

interface OutreachMetricsData {
  today: {
    emails: OutreachStat;
    sms: OutreachStat;
    calls: OutreachStat;
  };
  week: {
    emails: OutreachStat;
    sms: OutreachStat;
    calls: OutreachStat;
  };
  month: {
    emails: OutreachStat;
    sms: OutreachStat;
    calls: OutreachStat;
  };
  timestamp: string;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

function MetricSkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-8 w-20" />
        ))}
      </div>
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-3 w-12" />
          </div>
        ))}
      </div>
    </div>
  );
}

function StatCard({
  label,
  stat,
  icon: Icon,
  color,
}: {
  label: string;
  stat: OutreachStat;
  icon: typeof Mail;
  color: string;
}) {
  const TrendIcon = stat.trend === "up" ? TrendingUp : TrendingDown;
  const trendColor =
    stat.trend === "up"
      ? "text-green-600"
      : stat.trend === "down"
      ? "text-red-600"
      : "text-gray-500";

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Icon className={cn("h-4 w-4", color)} />
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
      </div>
      <div className="text-2xl font-bold">{stat.count.toLocaleString()}</div>
      {stat.change !== 0 && (
        <div className={cn("flex items-center gap-1 text-xs", trendColor)}>
          <TrendIcon className="h-3 w-3" />
          <span>{Math.abs(stat.change)}%</span>
        </div>
      )}
    </div>
  );
}

export function OutreachMetrics() {
  const [period, setPeriod] = useState<TimePeriod>("today");

  const { data, isLoading, error } = useSWR<OutreachMetricsData>(
    "/api/v1/metrics/outreach",
    fetcher,
    { refreshInterval: 30000 } // Refresh every 30s
  );

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)]">
            Outreach Metrics
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-6 text-red-500">
            <p className="font-medium">Failed to load metrics</p>
            <p className="text-sm text-muted-foreground">
              Please check backend connection
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isLoading || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)]">
            Outreach Metrics
          </CardTitle>
        </CardHeader>
        <CardContent>
          <MetricSkeleton />
        </CardContent>
      </Card>
    );
  }

  const metrics = data[period];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)]">
            Outreach Metrics
          </CardTitle>
          <Badge variant="outline" className="text-xs">
            {period === "today" ? "Today" : period === "week" ? "This Week" : "This Month"}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          Last updated: {new Date(data.timestamp).toLocaleTimeString()}
        </p>
      </CardHeader>
      <CardContent>
        {/* Time Period Toggle */}
        <div className="flex gap-2 mb-6">
          <Button
            variant={period === "today" ? "default" : "outline"}
            size="sm"
            className={cn(
              "text-xs",
              period === "today" &&
                "bg-[var(--turkish-blue)] hover:bg-[var(--turkish-blue)]/90"
            )}
            onClick={() => setPeriod("today")}
          >
            Today
          </Button>
          <Button
            variant={period === "week" ? "default" : "outline"}
            size="sm"
            className={cn(
              "text-xs",
              period === "week" &&
                "bg-[var(--turkish-blue)] hover:bg-[var(--turkish-blue)]/90"
            )}
            onClick={() => setPeriod("week")}
          >
            This Week
          </Button>
          <Button
            variant={period === "month" ? "default" : "outline"}
            size="sm"
            className={cn(
              "text-xs",
              period === "month" &&
                "bg-[var(--turkish-blue)] hover:bg-[var(--turkish-blue)]/90"
            )}
            onClick={() => setPeriod("month")}
          >
            This Month
          </Button>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-3 gap-6">
          <StatCard
            label="Emails"
            stat={metrics.emails}
            icon={Mail}
            color="text-blue-600"
          />
          <StatCard
            label="SMS"
            stat={metrics.sms}
            icon={MessageSquare}
            color="text-green-600"
          />
          <StatCard
            label="Calls"
            stat={metrics.calls}
            icon={Phone}
            color="text-purple-600"
          />
        </div>

        {/* Total Activity */}
        <div className="mt-6 pt-6 border-t">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">
              Total Activity
            </span>
            <span className="text-xl font-bold text-[var(--turkish-blue)]">
              {(
                metrics.emails.count +
                metrics.sms.count +
                metrics.calls.count
              ).toLocaleString()}
            </span>
          </div>
        </div>

        {/* Activity Breakdown */}
        <div className="mt-4 space-y-2">
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-600 rounded-full transition-all"
                style={{
                  width: `${
                    (metrics.emails.count /
                      (metrics.emails.count +
                        metrics.sms.count +
                        metrics.calls.count)) *
                    100
                  }%`,
                }}
              />
            </div>
            <span className="text-xs text-muted-foreground w-12 text-right">
              {(
                (metrics.emails.count /
                  (metrics.emails.count + metrics.sms.count + metrics.calls.count)) *
                100
              ).toFixed(0)}
              %
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-green-600 rounded-full transition-all"
                style={{
                  width: `${
                    (metrics.sms.count /
                      (metrics.emails.count +
                        metrics.sms.count +
                        metrics.calls.count)) *
                    100
                  }%`,
                }}
              />
            </div>
            <span className="text-xs text-muted-foreground w-12 text-right">
              {(
                (metrics.sms.count /
                  (metrics.emails.count + metrics.sms.count + metrics.calls.count)) *
                100
              ).toFixed(0)}
              %
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-purple-600 rounded-full transition-all"
                style={{
                  width: `${
                    (metrics.calls.count /
                      (metrics.emails.count +
                        metrics.sms.count +
                        metrics.calls.count)) *
                    100
                  }%`,
                }}
              />
            </div>
            <span className="text-xs text-muted-foreground w-12 text-right">
              {(
                (metrics.calls.count /
                  (metrics.emails.count + metrics.sms.count + metrics.calls.count)) *
                100
              ).toFixed(0)}
              %
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
