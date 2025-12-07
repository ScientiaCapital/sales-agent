import { RefreshCw, Clock } from "lucide-react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

interface ActivityItem {
  id: string;
  type: string;
  title: string;
  description: string;
  timestamp: string;
  lead_id?: string;
  lead_name?: string;
  icon: string;
  color: string;
}

interface ActivityResponse {
  activities: ActivityItem[];
  total: number;
  period_hours: number;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

const eventConfig: Record<string, { color: string; label: string }> = {
  high_value_lead: { color: "bg-yellow-100 text-yellow-700", label: "High Value" },
  hot_lead: { color: "bg-red-100 text-red-700", label: "HOT" },
  enrichment: { color: "bg-purple-100 text-purple-700", label: "Enriched" },
  lead_imported: { color: "bg-blue-100 text-blue-700", label: "Imported" },
  lead_qualified: { color: "bg-green-100 text-green-700", label: "Qualified" },
  crm_match_found: { color: "bg-cyan-100 text-cyan-700", label: "CRM Match" },
  lead_enriched: { color: "bg-purple-100 text-purple-700", label: "Enriched" },
  atl_contact_found: { color: "bg-emerald-100 text-emerald-700", label: "ATL Found" },
  dedup_create_new: { color: "bg-slate-100 text-slate-700", label: "New Lead" },
  dedup_skip_duplicate: { color: "bg-amber-100 text-amber-700", label: "Duplicate" },
  lead_exported: { color: "bg-indigo-100 text-indigo-700", label: "Exported" },
};

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}


function ActivitySkeleton() {
  return (
    <div className="flex items-start gap-3 py-3 border-b last:border-0">
      <Skeleton className="h-5 w-16" />
      <div className="flex-1 space-y-1">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-3 w-32" />
      </div>
      <Skeleton className="h-3 w-12" />
    </div>
  );
}

export function RecentActivity() {
  const { data, isLoading, mutate } = useSWR<ActivityResponse>(
    "/api/dashboard/activity?hours=24&limit=15",
    fetcher,
    { refreshInterval: 60000 } // Refresh every minute
  );

  // Extract activities from response object
  const activities = data?.activities || [];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock className="h-5 w-5 text-[var(--turkish-blue)]" />
          <CardTitle className="text-[var(--turkish-blue)]">
            Recent Activity
          </CardTitle>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => mutate()}
          className="h-8 w-8 p-0"
        >
          <RefreshCw className="h-4 w-4" />
        </Button>
      </CardHeader>
      <CardContent>
        <div className="space-y-0 max-h-[400px] overflow-y-auto">
          {isLoading || !data ? (
            <>
              <ActivitySkeleton />
              <ActivitySkeleton />
              <ActivitySkeleton />
              <ActivitySkeleton />
              <ActivitySkeleton />
            </>
          ) : activities.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              No recent activity
            </p>
          ) : (
            activities.map((activity) => {
              const config = eventConfig[activity.type] || {
                color: "bg-gray-100 text-gray-700",
                label: activity.type,
              };

              return (
                <div
                  key={activity.id}
                  className="flex items-start gap-3 py-3 border-b last:border-0 hover:bg-slate-50 transition-colors rounded px-2 -mx-2"
                >
                  <Badge
                    variant="secondary"
                    className={`${config.color} text-xs whitespace-nowrap`}
                  >
                    {config.label}
                  </Badge>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{activity.title}</p>
                    {activity.description && (
                      <p className="text-xs text-muted-foreground">{activity.description}</p>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {formatRelativeTime(activity.timestamp)}
                  </span>
                </div>
              );
            })
          )}
        </div>

        {activities && activities.length > 0 && (
          <p className="text-xs text-center text-muted-foreground mt-4 pt-2 border-t">
            Showing {activities.length} activities from the last {data?.period_hours || 24} hours
          </p>
        )}
      </CardContent>
    </Card>
  );
}
