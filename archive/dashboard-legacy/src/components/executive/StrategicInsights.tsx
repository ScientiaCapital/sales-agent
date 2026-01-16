import useSWR from "swr";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { MapPin, TrendingUp, Lightbulb, AlertCircle } from "lucide-react";

interface WorkQueueItem {
  id: string;
  company_name: string;
  state: string;
  lead_score: number;
  icp_tier?: string;
}

interface WorkQueueResponse {
  tasks: WorkQueueItem[];
  total: number;
  by_priority: Record<string, number>;
}

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

interface AttentionItem {
  company_id: string;
  company_name: string;
  days_stale: number;
}

interface NeedsAttentionResponse {
  items: AttentionItem[];
  total: number;
  urgent_count: number;
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

function InsightBoxSkeleton() {
  return (
    <Card className="border-2">
      <CardContent className="p-6">
        <Skeleton className="h-6 w-48 mb-4" />
        <Skeleton className="h-4 w-full mb-2" />
        <Skeleton className="h-4 w-5/6 mb-2" />
        <Skeleton className="h-4 w-4/6" />
      </CardContent>
    </Card>
  );
}

export function StrategicInsights() {
  const { data: workQueueData, isLoading: workQueueLoading } = useSWR<WorkQueueResponse>(
    "/api/dashboard/workqueue?limit=100",
    fetcher,
    { refreshInterval: 60000 }
  );

  const { data: metrics, isLoading: metricsLoading } = useSWR<MetricsSummary>(
    "/api/dashboard/metrics",
    fetcher,
    { refreshInterval: 300000 }
  );

  const { data: attentionData, isLoading: attentionLoading } = useSWR<NeedsAttentionResponse>(
    "/api/dashboard/attention?days=7",
    fetcher,
    { refreshInterval: 300000 }
  );

  if (workQueueLoading || metricsLoading || attentionLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <InsightBoxSkeleton />
        <InsightBoxSkeleton />
        <InsightBoxSkeleton />
      </div>
    );
  }

  if (!workQueueData || !metrics || !attentionData) {
    return (
      <Card className="border border-red-500/30">
        <CardContent className="p-6">
          <div className="text-center text-red-400">
            <AlertCircle className="h-8 w-8 mx-auto mb-2" />
            <p className="font-medium">Failed to load insights</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Use tasks from workQueueData
  const tasks = workQueueData.tasks || [];

  // Calculate top states
  const stateAggregation = tasks.reduce((acc, task) => {
    const state = task.state || "Unknown";
    acc[state] = (acc[state] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const topStates = Object.entries(stateAggregation)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  // Calculate high-score leads
  const highScoreLeads = tasks.filter((task) => task.lead_score >= 80);

  // Calculate stale leads percentage
  const stalePercentage = (attentionData.total / metrics.total_leads) * 100;

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6 text-transparent bg-clip-text bg-gradient-to-r from-purple-400 via-pink-400 to-blue-400">
        Strategic Insights
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Green Box: Geographic Focus */}
        <Card className="border-2 border-green-500/50 bg-gradient-to-br from-green-500/10 to-emerald-500/5 hover:shadow-xl hover:shadow-green-500/20 transition-all duration-300">
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 rounded-xl bg-gradient-to-br from-green-500 to-emerald-500 bg-opacity-20">
                <MapPin className="h-6 w-6 text-green-400" />
              </div>
              <h3 className="text-xl font-bold text-green-300">Geographic Focus</h3>
            </div>
            <div className="space-y-3">
              <p className="text-gray-300 text-sm leading-relaxed">
                Top markets with high prospect concentration:
              </p>
              <div className="space-y-2">
                {topStates.map(([state, count], index) => (
                  <div
                    key={state}
                    className="flex items-center justify-between p-2 rounded-lg bg-green-500/5 border border-green-500/20"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-green-400 text-lg">#{index + 1}</span>
                      <span className="text-white font-medium">{state}</span>
                    </div>
                    <span className="text-green-300 font-semibold">{count} leads</span>
                  </div>
                ))}
              </div>
              <p className="text-xs text-gray-400 mt-3 italic">
                Focus outreach on these high-density markets for maximum ROI
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Purple Box: Key Metrics Summary */}
        <Card className="border-2 border-purple-500/50 bg-gradient-to-br from-purple-500/10 to-pink-500/5 hover:shadow-xl hover:shadow-purple-500/20 transition-all duration-300">
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 bg-opacity-20">
                <TrendingUp className="h-6 w-6 text-purple-400" />
              </div>
              <h3 className="text-xl font-bold text-purple-300">Key Metrics</h3>
            </div>
            <div className="space-y-3">
              <div className="p-3 rounded-lg bg-purple-500/5 border border-purple-500/20">
                <div className="text-sm text-gray-400 mb-1">Conversion Rate</div>
                <div className="text-2xl font-bold text-white">
                  {formatPercent(metrics.win_rate)}
                </div>
                <div className="text-xs text-purple-300 mt-1">
                  {metrics.won_deals} won / {metrics.opportunities} opportunities
                </div>
              </div>

              <div className="p-3 rounded-lg bg-purple-500/5 border border-purple-500/20">
                <div className="text-sm text-gray-400 mb-1">High-Score Prospects</div>
                <div className="text-2xl font-bold text-white">
                  {highScoreLeads.length}
                </div>
                <div className="text-xs text-purple-300 mt-1">
                  Leads scoring 80+ (ready to engage)
                </div>
              </div>

              <div className="p-3 rounded-lg bg-purple-500/5 border border-purple-500/20">
                <div className="text-sm text-gray-400 mb-1">Pipeline Revenue</div>
                <div className="text-2xl font-bold text-white">
                  {formatCurrency(metrics.total_revenue)}
                </div>
                <div className="text-xs text-purple-300 mt-1">
                  {formatCurrency(metrics.avg_deal_size)} average deal
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Yellow/Amber Box: Recommended Next Steps */}
        <Card className="border-2 border-amber-500/50 bg-gradient-to-br from-amber-500/10 to-yellow-500/5 hover:shadow-xl hover:shadow-amber-500/20 transition-all duration-300">
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 rounded-xl bg-gradient-to-br from-amber-500 to-yellow-500 bg-opacity-20">
                <Lightbulb className="h-6 w-6 text-amber-400" />
              </div>
              <h3 className="text-xl font-bold text-amber-300">Action Items</h3>
            </div>
            <div className="space-y-3">
              <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
                <div className="flex items-start gap-2">
                  <span className="font-bold text-amber-400 text-lg mt-0.5">1.</span>
                  <div>
                    <div className="text-white font-medium">Engage High-Score Leads</div>
                    <div className="text-xs text-gray-400 mt-1">
                      {highScoreLeads.length} prospects scoring 80+ are ready for immediate
                      outreach
                    </div>
                  </div>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
                <div className="flex items-start gap-2">
                  <span className="font-bold text-amber-400 text-lg mt-0.5">2.</span>
                  <div>
                    <div className="text-white font-medium">Re-engage Stale Leads</div>
                    <div className="text-xs text-gray-400 mt-1">
                      {attentionData.total} leads untouched for 7+ days (
                      {stalePercentage.toFixed(1)}% of pipeline)
                    </div>
                  </div>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
                <div className="flex items-start gap-2">
                  <span className="font-bold text-amber-400 text-lg mt-0.5">3.</span>
                  <div>
                    <div className="text-white font-medium">Optimize Cost Efficiency</div>
                    <div className="text-xs text-gray-400 mt-1">
                      Current cost per lead: {formatCurrency(metrics.cost_per_lead, 3)} (
                      {formatCurrency(metrics.total_cost_usd)} total)
                    </div>
                  </div>
                </div>
              </div>

              <p className="text-xs text-gray-400 mt-3 italic">
                Focus on these priorities to maximize pipeline velocity
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
