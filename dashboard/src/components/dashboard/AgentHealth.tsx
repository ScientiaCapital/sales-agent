"use client";

import { Activity, Clock, CheckCircle, AlertTriangle, XCircle } from "lucide-react";
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

function AgentCard({ agent }: { agent: AgentMetric }) {
  const config = statusConfig[agent.status];
  const StatusIcon = config.icon;
  const isOverTarget = agent.avg_latency_ms > agent.target_latency_ms;

  return (
    <Card className={`transition-all hover:shadow-md ${agent.status === "failing" ? "border-red-200" : ""}`}>
      <CardHeader className="pb-2">
        <div className="flex justify-between items-start">
          <CardTitle className="text-sm font-medium">
            {agent.display_name}
          </CardTitle>
          <Badge variant="outline" className={config.color}>
            <StatusIcon className="h-3 w-3 mr-1" />
            {config.label}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {/* Executions */}
        <div className="flex justify-between">
          <span className="text-muted-foreground">Executions</span>
          <span className="font-medium">
            {agent.successful_executions.toLocaleString()}
            <span className="text-green-600">/</span>
            {agent.total_executions.toLocaleString()}
            {agent.failed_executions > 0 && (
              <span className="text-red-500 text-xs ml-1">
                ({agent.failed_executions} failed)
              </span>
            )}
          </span>
        </div>

        {/* Latency */}
        <div className="flex justify-between">
          <span className="text-muted-foreground">Avg Latency</span>
          <span className={`font-medium ${isOverTarget ? "text-yellow-600" : "text-green-600"}`}>
            {formatLatency(agent.avg_latency_ms)}
            <span className="text-muted-foreground text-xs ml-1">
              / {formatLatency(agent.target_latency_ms)}
            </span>
          </span>
        </div>

        {/* Success Rate */}
        <div className="flex justify-between">
          <span className="text-muted-foreground">Success Rate</span>
          <span className={`font-medium ${agent.success_rate >= 0.95 ? "text-green-600" : "text-yellow-600"}`}>
            {(agent.success_rate * 100).toFixed(1)}%
          </span>
        </div>

        {/* Cost */}
        <div className="flex justify-between">
          <span className="text-muted-foreground">Avg Cost</span>
          <span className="font-medium text-blue-600">
            {formatCost(agent.avg_cost_usd)}
          </span>
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
