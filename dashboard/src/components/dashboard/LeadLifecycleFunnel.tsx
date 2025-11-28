"use client";

import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle } from "lucide-react";

interface StageData {
  stage: string;
  display_name: string;
  count: number;
  count_7d: number;
  count_mtd: number;
  avg_score: number | null;
  attention_count: number;
  atl_count: number;
  color: string;
  order: number;
}

interface LifecycleResponse {
  stages: StageData[];
  period: string;
  data_source: string;
  updated_at: string;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

function FunnelSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

interface LeadLifecycleFunnelProps {
  period?: "7d" | "mtd";
}

export function LeadLifecycleFunnel({ period = "7d" }: LeadLifecycleFunnelProps) {
  const { data, isLoading } = useSWR<LifecycleResponse>(
    `/api/lifecycle?period=${period}`,
    fetcher,
    { refreshInterval: 60000 } // Refresh every 60s
  );

  if (isLoading || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)]">
            Lead Lifecycle Funnel
          </CardTitle>
        </CardHeader>
        <CardContent>
          <FunnelSkeleton />
        </CardContent>
      </Card>
    );
  }

  // Get max count for bar scaling
  const maxCount = Math.max(...data.stages.map((s) => s.count), 1);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)]">
            Lead Lifecycle Funnel
          </CardTitle>
          <Badge variant="outline" className="text-xs">
            {data.data_source === "mock" ? "Demo" : "Live"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {data.stages
            .filter((s) => !["won", "lost"].includes(s.stage))
            .map((stage) => {
              const barWidth = Math.max((stage.count / maxCount) * 100, 5);
              const displayCount = period === "7d" ? stage.count_7d : stage.count_mtd;

              return (
                <div key={stage.stage} className="relative">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium w-28 truncate">
                      {stage.display_name}
                    </span>
                    {stage.attention_count > 0 && (
                      <AlertTriangle className="h-3 w-3 text-amber-500" />
                    )}
                    <span className="text-xs text-muted-foreground ml-auto">
                      {stage.atl_count > 0 && (
                        <span className="text-green-600 mr-2">
                          {stage.atl_count} ATL
                        </span>
                      )}
                      {displayCount}
                    </span>
                  </div>
                  <div className="h-6 bg-muted rounded-sm overflow-hidden">
                    <div
                      className="h-full rounded-sm transition-all duration-500 flex items-center justify-end pr-2"
                      style={{
                        width: `${barWidth}%`,
                        backgroundColor: stage.color,
                      }}
                    >
                      <span className="text-xs font-bold text-white drop-shadow">
                        {displayCount}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
        </div>

        {/* Won/Lost Summary */}
        <div className="mt-4 pt-4 border-t flex gap-4">
          {data.stages
            .filter((s) => ["won", "lost"].includes(s.stage))
            .map((stage) => (
              <div key={stage.stage} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: stage.color }}
                />
                <span className="text-sm">
                  {stage.display_name}: {stage.count}
                </span>
              </div>
            ))}
        </div>
      </CardContent>
    </Card>
  );
}
