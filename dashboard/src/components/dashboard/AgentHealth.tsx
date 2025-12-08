import { Activity, Clock, CheckCircle, AlertTriangle, XCircle, Zap, TrendingUp, Bot, Brain, Mail, Search, BarChart3, Calendar } from "lucide-react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

interface AgentMetric {
  agent_type: string;
  display_name: string;
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  avg_latency_ms: number;
  target_latency_ms: number;
  avg_cost_usd: number;
  success_rate: number;
  status: "healthy" | "degraded" | "failing" | "idle";
  last_execution_at: string;
}

// Agent descriptions for C-suite context with icons and detailed info
const agentDescriptions: Record<string, {
  role: string;
  value: string;
  schedule: string;
  icon: typeof Search;
  accentColor: string;
  kpiLabel: string;
}> = {
  lead_scout: {
    role: "Lead Discovery",
    value: "Autonomously discovers new leads from data sources and enrichment providers",
    schedule: "Every 30 min",
    icon: Search,
    accentColor: "text-blue-600",
    kpiLabel: "Leads Found"
  },
  icp_checker: {
    role: "ICP Scoring",
    value: "Recalculates Ideal Customer Profile scores when company data changes",
    schedule: "Every 15 min",
    icon: BarChart3,
    accentColor: "text-purple-600",
    kpiLabel: "Scores Updated"
  },
  prediction_agent: {
    role: "Call Priority",
    value: "Ranks leads by call-worthiness using ML prediction for optimal cold outbound",
    schedule: "Every 5 min",
    icon: TrendingUp,
    accentColor: "text-green-600",
    kpiLabel: "Predictions Made"
  },
  morning_briefing: {
    role: "Daily Briefing",
    value: "Generates \"Why Call Now\" reasoning for top 10 priority leads each morning",
    schedule: "7 AM EST",
    icon: Calendar,
    accentColor: "text-orange-600",
    kpiLabel: "Briefings Sent"
  },
  sales_intel: {
    role: "Intel Extraction",
    value: "Extracts personal hooks, company stories, and pain points from web research",
    schedule: "Hourly",
    icon: Brain,
    accentColor: "text-indigo-600",
    kpiLabel: "Intel Extracted"
  },
  bdr_outreach: {
    role: "Draft Generation",
    value: "Creates personalized email/SMS drafts with Slack approval workflow",
    schedule: "Hourly",
    icon: Mail,
    accentColor: "text-pink-600",
    kpiLabel: "Drafts Created"
  },
};

const fetcher = (url: string) => fetch(url).then((res) => res.json());

const statusConfig = {
  healthy: {
    icon: CheckCircle,
    color: "bg-green-100 text-green-700 border-green-200",
    label: "Healthy",
  },
  degraded: {
    icon: AlertTriangle,
    color: "bg-yellow-100 text-yellow-700 border-yellow-200",
    label: "Degraded",
  },
  failing: {
    icon: XCircle,
    color: "bg-red-100 text-red-700 border-red-200",
    label: "Failing",
  },
  idle: {
    icon: Clock,
    color: "bg-gray-100 text-gray-700 border-gray-200",
    label: "Idle",
  },
};

function formatLatency(ms: number): string {
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(1)}s`;
  }
  return `${ms.toFixed(0)}ms`;
}

function formatCost(usd: number): string {
  if (usd < 0.0001) {
    return `$${(usd * 1000000).toFixed(1)}µ`;
  }
  if (usd < 0.01) {
    return `$${(usd * 1000).toFixed(2)}m`;
  }
  return `$${usd.toFixed(4)}`;
}

function AgentCardSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex justify-between items-start">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-5 w-16" />
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
      </CardContent>
    </Card>
  );
}

function formatTimeAgo(dateString: string): string {
  if (!dateString) return "Never";
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

function AgentCard({ agent }: { agent: AgentMetric }) {
  const config = statusConfig[agent.status];
  const StatusIcon = config.icon;
  const isOverTarget = agent.avg_latency_ms > agent.target_latency_ms;

  // Get agent description or use defaults
  const description = agentDescriptions[agent.agent_type] || {
    role: agent.display_name,
    value: "Autonomous AI agent for sales automation",
    schedule: "On-demand",
    icon: Bot,
    accentColor: "text-gray-600",
    kpiLabel: "Executions"
  };
  const AgentIcon = description.icon;

  return (
    <Card className={`transition-all hover:shadow-lg hover:scale-[1.02] ${
      agent.status === "failing" ? "border-red-300 bg-red-50/30" :
      agent.status === "healthy" ? "border-green-200 hover:border-green-300" : ""
    }`}>
      <CardHeader className="pb-3">
        {/* Top Row: Icon + Role Badge + Status */}
        <div className="flex justify-between items-start mb-2">
          <div className="flex items-center gap-2">
            <div className={`p-2 rounded-lg bg-gradient-to-br from-gray-50 to-gray-100 ${description.accentColor}`}>
              <AgentIcon className="h-5 w-5" />
            </div>
            <div>
              <CardTitle className="text-base font-semibold text-gray-900">
                {description.role}
              </CardTitle>
              <div className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5">
                <Clock className="h-3 w-3" />
                <span>{description.schedule}</span>
              </div>
            </div>
          </div>
          <Badge variant="outline" className={`${config.color} text-xs px-2 py-0.5`}>
            <StatusIcon className="h-3 w-3 mr-1" />
            {config.label}
          </Badge>
        </div>

        {/* Value Proposition */}
        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
          {description.value}
        </p>
      </CardHeader>

      <CardContent className="space-y-3 pt-0">
        {/* Primary KPI - Large Number */}
        <div className="bg-gradient-to-r from-gray-50 to-transparent rounded-lg p-3 -mx-1">
          <div className="flex justify-between items-baseline">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              {description.kpiLabel}
            </span>
            <span className={`text-2xl font-bold ${description.accentColor}`}>
              {agent.successful_executions.toLocaleString()}
            </span>
          </div>
          {agent.failed_executions > 0 && (
            <div className="text-right text-xs text-red-500 mt-1">
              {agent.failed_executions} failed of {agent.total_executions.toLocaleString()} total
            </div>
          )}
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-2 gap-3 text-sm">
          {/* Success Rate */}
          <div className="space-y-1">
            <span className="text-xs text-muted-foreground block">Success Rate</span>
            <div className="flex items-center gap-1.5">
              <div className={`h-2 w-2 rounded-full ${agent.success_rate >= 0.95 ? "bg-green-500" : agent.success_rate >= 0.8 ? "bg-yellow-500" : "bg-red-500"}`} />
              <span className={`font-semibold ${agent.success_rate >= 0.95 ? "text-green-600" : "text-yellow-600"}`}>
                {(agent.success_rate * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          {/* Latency */}
          <div className="space-y-1">
            <span className="text-xs text-muted-foreground block">Avg Latency</span>
            <div className="flex items-center gap-1.5">
              <Zap className={`h-3 w-3 ${isOverTarget ? "text-yellow-500" : "text-green-500"}`} />
              <span className={`font-semibold ${isOverTarget ? "text-yellow-600" : "text-green-600"}`}>
                {formatLatency(agent.avg_latency_ms)}
              </span>
            </div>
          </div>

          {/* Cost */}
          <div className="space-y-1">
            <span className="text-xs text-muted-foreground block">Avg Cost</span>
            <span className="font-semibold text-blue-600">
              {formatCost(agent.avg_cost_usd)}
            </span>
          </div>

          {/* Last Run */}
          <div className="space-y-1">
            <span className="text-xs text-muted-foreground block">Last Run</span>
            <span className="font-medium text-gray-700">
              {formatTimeAgo(agent.last_execution_at)}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function AgentHealth() {
  const { data: agents, isLoading, error } = useSWR<AgentMetric[]>(
    "/api/dashboard/agents",
    fetcher,
    { refreshInterval: 30000 } // Refresh every 30 seconds
  );

  // Error state
  if (error) {
    return (
      <section className="mb-8">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="h-5 w-5 text-[var(--turkish-blue)]" />
          <h2 className="text-2xl font-bold text-[var(--turkish-blue)]">
            Agent Health
          </h2>
        </div>
        <Card>
          <CardContent className="pt-6">
            <div className="text-center py-6 text-red-500">
              <XCircle className="h-8 w-8 mx-auto mb-2" />
              <p className="font-medium">Failed to load agent metrics</p>
              <p className="text-sm text-muted-foreground">
                Please check if the backend server is running
              </p>
            </div>
          </CardContent>
        </Card>
      </section>
    );
  }

  return (
    <section className="mb-8">
      <div className="flex items-center gap-2 mb-4">
        <Activity className="h-5 w-5 text-[var(--turkish-blue)]" />
        <h2 className="text-2xl font-bold text-[var(--turkish-blue)]">
          Agent Health
        </h2>
        <span className="text-sm text-muted-foreground">
          (6 LangGraph Agents)
        </span>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {isLoading || !agents ? (
          <>
            <AgentCardSkeleton />
            <AgentCardSkeleton />
            <AgentCardSkeleton />
            <AgentCardSkeleton />
            <AgentCardSkeleton />
            <AgentCardSkeleton />
          </>
        ) : (
          agents.map((agent) => (
            <AgentCard key={agent.agent_type} agent={agent} />
          ))
        )}
      </div>
    </section>
  );
}
