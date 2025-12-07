import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Target,
  TrendingUp,
  TrendingDown,
  Clock,
  Phone,
  Mail,
  AlertTriangle,
  AlertCircle,
} from "lucide-react";

interface Lead {
  id: string;
  company_name: string;
  status: string;
  contact_name: string;
  contact_phone: string;
  contact_email: string;
  smart_view: string;
  quarter: string;
  priority: number;
  color: string;
  days_since_activity: number;
  is_untouched: boolean;
}

interface SmartView {
  name: string;
  color: string;
  priority: number;
  leads: Lead[];
  total: number;
  untouched: number;
}

interface Opportunity {
  id: string;
  lead_name: string;
  status_label: string;
  value: number;
  confidence: number;
}

interface AETracking {
  name: string;
  active: Opportunity[];
  won: Opportunity[];
  lost: Opportunity[];
  totals: {
    active_count: number;
    active_value: number;
    won_count: number;
    won_value: number;
    lost_count: number;
    lost_value: number;
  };
}

interface ICPQueueResponse {
  smart_views: Record<string, SmartView>;
  untouched_leads: Lead[];
  ae_tracking: Record<string, AETracking>;
  summary: {
    total_leads: number;
    untouched_count: number;
    by_quarter: { Q3: number; Q4: number; PPL: number };
  };
  philosophy: string;
  data_source: string;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

function formatCurrency(value: number): string {
  if (value >= 1000000) {
    return `$${(value / 1000000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `$${(value / 1000).toFixed(0)}K`;
  }
  return `$${value.toFixed(0)}`;
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-20 w-full" />
    </div>
  );
}

export function ICPQueue() {
  const { data, isLoading, error } = useSWR<ICPQueueResponse>(
    "/api/dashboard/icp-queue?days=7&limit=10",
    fetcher,
    { refreshInterval: 60000 } // Refresh every 60 seconds
  );

  if (error) {
    return (
      <Card className="col-span-2">
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <Target className="h-5 w-5" />
            ICP Queue - "Never Lost, Always Aware"
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-6 text-red-500">
            <AlertCircle className="h-8 w-8 mx-auto mb-2" />
            <p className="font-medium">Failed to load ICP queue</p>
            <p className="text-sm text-muted-foreground">
              Please check if the backend server is running
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isLoading || !data) {
    return (
      <Card className="col-span-2">
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <Target className="h-5 w-5" />
            ICP Queue - "Never Lost, Always Aware"
          </CardTitle>
        </CardHeader>
        <CardContent>
          <LoadingSkeleton />
        </CardContent>
      </Card>
    );
  }

  const { smart_views, untouched_leads, ae_tracking, summary } = data;

  // Sort smart views by priority
  const sortedViews = Object.entries(smart_views).sort(
    (a, b) => a[1].priority - b[1].priority
  );

  return (
    <Card className="col-span-2">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <Target className="h-5 w-5" />
            ICP Queue - "Never Lost, Always Aware"
          </CardTitle>
          <Badge variant="outline" className="text-amber-600 border-amber-500">
            {summary.untouched_count} untouched ({">"}7d)
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="smart_views" className="space-y-4">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="smart_views">Tim's Views</TabsTrigger>
            <TabsTrigger value="untouched">Needs Attention</TabsTrigger>
            <TabsTrigger value="ae_tracking">AE Pipeline</TabsTrigger>
          </TabsList>

          {/* Tim's Smart Views Tab */}
          <TabsContent value="smart_views" className="space-y-3">
            {/* Quarter Summary */}
            <div className="flex gap-4 mb-4 pb-3 border-b">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500" />
                <span className="text-sm">
                  Q3: {summary.by_quarter.Q3} leads
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-purple-500" />
                <span className="text-sm">
                  Q4: {summary.by_quarter.Q4} leads
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-green-500" />
                <span className="text-sm">
                  PPL: {summary.by_quarter.PPL} leads
                </span>
              </div>
            </div>

            {/* Smart View Cards */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
              {sortedViews.map(([key, view]) => (
                <div
                  key={key}
                  className="rounded-lg border p-3 hover:shadow-md transition-shadow"
                  style={{ borderLeftColor: view.color, borderLeftWidth: 4 }}
                >
                  <p className="font-medium text-sm truncate">{view.name}</p>
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-2xl font-bold">{view.total}</span>
                    {view.untouched > 0 && (
                      <Badge
                        variant="destructive"
                        className="text-xs px-1.5 py-0"
                      >
                        {view.untouched} stale
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Priority #{view.priority}
                  </p>
                </div>
              ))}
            </div>
          </TabsContent>

          {/* Untouched Leads Tab */}
          <TabsContent value="untouched" className="space-y-2">
            {untouched_leads.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Clock className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>All leads contacted within 7 days! 🎉</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {untouched_leads.slice(0, 15).map((lead) => (
                  <div
                    key={lead.id}
                    className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50"
                    style={{ borderLeftColor: lead.color, borderLeftWidth: 4 }}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{lead.company_name}</p>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Badge variant="outline" className="text-xs">
                          {lead.smart_view}
                        </Badge>
                        <span>{lead.status}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 ml-2">
                      {lead.contact_phone && (
                        <a
                          href={`tel:${lead.contact_phone}`}
                          className="text-blue-600 hover:text-blue-800"
                        >
                          <Phone className="h-4 w-4" />
                        </a>
                      )}
                      {lead.contact_email && (
                        <a
                          href={`mailto:${lead.contact_email}`}
                          className="text-purple-600 hover:text-purple-800"
                        >
                          <Mail className="h-4 w-4" />
                        </a>
                      )}
                      <div className="text-right">
                        <p className="text-sm font-semibold text-red-600">
                          {lead.days_since_activity}d
                        </p>
                        <p className="text-xs text-muted-foreground">ago</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>

          {/* AE Pipeline Tracking Tab */}
          <TabsContent value="ae_tracking" className="space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {Object.entries(ae_tracking).map(([key, ae]) => (
                <div key={key} className="rounded-lg border p-3">
                  <p className="font-medium text-sm mb-2">{ae.name}</p>

                  {/* Active Pipeline */}
                  <div className="flex items-center gap-2 mb-1">
                    <TrendingUp className="h-4 w-4 text-blue-600" />
                    <span className="text-sm">
                      {ae.totals.active_count} active
                    </span>
                    <span className="text-xs text-muted-foreground ml-auto">
                      {formatCurrency(ae.totals.active_value)}
                    </span>
                  </div>

                  {/* Won */}
                  <div className="flex items-center gap-2 mb-1">
                    <Target className="h-4 w-4 text-green-600" />
                    <span className="text-sm">{ae.totals.won_count} won</span>
                    <span className="text-xs text-muted-foreground ml-auto">
                      {formatCurrency(ae.totals.won_value)}
                    </span>
                  </div>

                  {/* Lost */}
                  <div className="flex items-center gap-2">
                    <TrendingDown className="h-4 w-4 text-red-600" />
                    <span className="text-sm">{ae.totals.lost_count} lost</span>
                    <span className="text-xs text-muted-foreground ml-auto">
                      {formatCurrency(ae.totals.lost_value)}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Lost Deal Alert */}
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mt-4">
              <div className="flex items-center gap-2 text-amber-800">
                <AlertTriangle className="h-5 w-5" />
                <span className="font-medium">Lost Deal Review</span>
              </div>
              <p className="text-sm text-amber-700 mt-1">
                Track lost opportunities to learn and improve win rates. Review
                patterns across AEs.
              </p>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
