import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, Clock } from "lucide-react";

interface AttentionItem {
  id: string;
  company_name: string;
  reason: string;
  priority: string;
  days_stale: number;
  last_activity?: string;
  contact_name?: string;
  contact_phone?: string;
}

interface AttentionResponse {
  items: AttentionItem[];
  total: number;
  urgent_count: number;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

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

  const urgentCount = data.urgent_count || 0;
  const totalItems = data.items?.length || 0;

  return (
    <Card className={urgentCount > 0 ? "border-red-300" : "border-amber-200"}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold text-red-600 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Needs Attention
          </CardTitle>
          <div className="flex gap-1">
            {urgentCount > 0 && (
              <Badge variant="destructive" className="text-xs">
                {urgentCount} urgent
              </Badge>
            )}
            {totalItems > urgentCount && (
              <Badge variant="outline" className="text-xs border-amber-500 text-amber-600">
                {totalItems - urgentCount} others
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {data.items.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <p className="text-green-600 font-medium">All clear!</p>
            <p className="text-sm">No leads need attention right now.</p>
          </div>
        ) : (
          <div className="space-y-2 max-h-[300px] overflow-y-auto">
            {data.items.map((item) => {
              const isHighPriority = item.priority === "HIGH";

              return (
                <div
                  key={item.id}
                  className={`flex items-start gap-3 p-2 rounded-lg ${
                    isHighPriority
                      ? "bg-red-50"
                      : "bg-amber-50"
                  }`}
                >
                  <div className="mt-0.5">
                    <Clock className={`h-5 w-5 ${isHighPriority ? "text-red-500" : "text-amber-500"}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium text-sm truncate">
                        {item.company_name}
                      </p>
                      <span className="text-xs text-muted-foreground whitespace-nowrap">
                        {item.days_stale}d stale
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground truncate">
                      {item.reason}
                    </p>
                    {item.contact_name && (
                      <div className="flex items-center gap-2 mt-1 text-xs">
                        <span className="font-medium">{item.contact_name}</span>
                        {item.contact_phone && (
                          <a
                            href={`tel:${item.contact_phone}`}
                            className="text-[var(--turkish-blue)] hover:underline"
                          >
                            {item.contact_phone}
                          </a>
                        )}
                      </div>
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
