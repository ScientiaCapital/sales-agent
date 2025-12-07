import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  AlertTriangle,
  Clock,
  XCircle,
  PauseCircle,
  PhoneOff,
} from "lucide-react";

interface Alert {
  id: string;
  company_name: string;
  alert_type: string;
  type_label: string;
  severity: string;
  message: string;
  stage: string | null;
  icon: string;
  color: string;
  created_at: string;
}

interface AttentionResponse {
  alerts: Alert[];
  total: number;
  by_severity: Record<string, number>;
  by_type: Record<string, number>;
  data_source: string;
  updated_at: string;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  clock: Clock,
  "x-circle": XCircle,
  "pause-circle": PauseCircle,
  "phone-off": PhoneOff,
};

function AlertSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <div key={i} className="flex items-start gap-3 p-2">
          <Skeleton className="h-5 w-5 rounded-full" />
          <div className="flex-1">
            <Skeleton className="h-4 w-32 mb-1" />
            <Skeleton className="h-3 w-48" />
          </div>
        </div>
      ))}
    </div>
  );
}

function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 0) return `${diffDays}d ago`;
  if (diffHours > 0) return `${diffHours}h ago`;
  return "Just now";
}

export function NeedsAttentionQueue() {
  const { data, isLoading } = useSWR<AttentionResponse>(
    "/api/dashboard/attention",
    fetcher,
    { refreshInterval: 30000 } // Refresh every 30s
  );

  if (isLoading || !data) {
    return (
      <Card className="border-red-200">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg font-semibold text-red-600 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Needs Attention
          </CardTitle>
        </CardHeader>
        <CardContent>
          <AlertSkeleton />
        </CardContent>
      </Card>
    );
  }

  const criticalCount = data.by_severity?.critical || 0;
  const warningCount = data.by_severity?.warning || 0;

  return (
    <Card className={criticalCount > 0 ? "border-red-300" : "border-amber-200"}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold text-red-600 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Needs Attention
          </CardTitle>
          <div className="flex gap-1">
            {criticalCount > 0 && (
              <Badge variant="destructive" className="text-xs">
                {criticalCount} critical
              </Badge>
            )}
            {warningCount > 0 && (
              <Badge variant="outline" className="text-xs border-amber-500 text-amber-600">
                {warningCount} warning
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {data.alerts.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <p className="text-green-600 font-medium">All clear!</p>
            <p className="text-sm">No leads need attention right now.</p>
          </div>
        ) : (
          <div className="space-y-2 max-h-[300px] overflow-y-auto">
            {data.alerts.map((alert) => {
              const IconComponent = ICON_MAP[alert.icon] || AlertTriangle;

              return (
                <div
                  key={alert.id}
                  className={`flex items-start gap-3 p-2 rounded-lg ${
                    alert.severity === "critical"
                      ? "bg-red-50"
                      : alert.severity === "warning"
                      ? "bg-amber-50"
                      : "bg-muted/50"
                  }`}
                >
                  <div className="mt-0.5" style={{ color: alert.color }}>
                    <IconComponent className="h-5 w-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium text-sm truncate">
                        {alert.company_name}
                      </p>
                      <span className="text-xs text-muted-foreground whitespace-nowrap">
                        {formatTimeAgo(alert.created_at)}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground truncate">
                      {alert.message}
                    </p>
                    {alert.stage && (
                      <Badge variant="outline" className="text-xs mt-1">
                        {alert.stage}
                      </Badge>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
