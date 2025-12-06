"use client";

import { useState } from "react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Search,
  CheckCircle,
  TrendingUp,
  Sun,
  FileText,
  Brain,
  Rocket,
  Mail,
  RefreshCw,
  MessageSquare,
  Forward,
  AlertCircle,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { AgentControls } from "./AgentControls";

/**
 * Agent configuration with icon mapping
 */
interface AgentConfig {
  name: string;
  displayName: string;
  schedule: string;
  icon: LucideIcon;
  description: string;
}

const AGENTS: AgentConfig[] = [
  {
    name: "lead_scout",
    displayName: "Lead Scout",
    schedule: "Every 30 min",
    icon: Search,
    description: "Discover new leads from Supabase",
  },
  {
    name: "icp_checker",
    displayName: "ICP Checker",
    schedule: "Every 15 min",
    icon: CheckCircle,
    description: "Recalculate ICP scores",
  },
  {
    name: "prediction_market",
    displayName: "Prediction Market",
    schedule: "Every 5 min",
    icon: TrendingUp,
    description: "Rank leads by conversion probability",
  },
  {
    name: "morning_briefing",
    displayName: "Morning Briefing",
    schedule: "7 AM EST",
    icon: Sun,
    description: "Why call now reasoning for top 10",
  },
  {
    name: "morning_report",
    displayName: "Morning Report",
    schedule: "9 AM EST",
    icon: FileText,
    description: "Daily summary report",
  },
  {
    name: "sales_intel",
    displayName: "Sales Intel",
    schedule: "Hourly :30",
    icon: Brain,
    description: "Extract personal hooks from research",
  },
  {
    name: "growth_campaigns",
    displayName: "Growth Campaigns",
    schedule: "10 AM EST",
    icon: Rocket,
    description: "5-cycle campaigns for HOT leads",
  },
  {
    name: "bdr_outreach",
    displayName: "BDR Outreach",
    schedule: "Hourly :00",
    icon: Mail,
    description: "Draft emails with Slack approval",
  },
  {
    name: "close_sync",
    displayName: "Close Sync",
    schedule: "Every 15 min",
    icon: RefreshCw,
    description: "Sync activities from Close CRM",
  },
  {
    name: "reply_polling",
    displayName: "Reply Polling",
    schedule: "Every 5 min",
    icon: MessageSquare,
    description: "Poll for email replies",
  },
  {
    name: "sequence_advance",
    displayName: "Sequence Advance",
    schedule: "Hourly",
    icon: Forward,
    description: "Move leads through sequences",
  },
];

/**
 * Agent status from backend
 */
interface AgentStatus {
  name: string;
  status: "running" | "idle" | "error" | "disabled";
  last_run: string | null;
  next_run: string | null;
  runs_today: number;
  error_message?: string;
}

interface AgentStatusResponse {
  agents: AgentStatus[];
  timestamp: string;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

/**
 * Get status badge color and pulse animation
 */
function getStatusBadge(status: AgentStatus["status"]) {
  switch (status) {
    case "running":
      return {
        className: "bg-green-100 text-green-700 border-green-300",
        dot: "bg-green-500 animate-pulse",
        label: "Running",
      };
    case "idle":
      return {
        className: "bg-yellow-100 text-yellow-700 border-yellow-300",
        dot: "bg-yellow-500",
        label: "Idle",
      };
    case "error":
      return {
        className: "bg-red-100 text-red-700 border-red-300",
        dot: "bg-red-500",
        label: "Error",
      };
    case "disabled":
      return {
        className: "bg-gray-100 text-gray-500 border-gray-300",
        dot: "bg-gray-400",
        label: "Disabled",
      };
  }
}

/**
 * Format timestamp to relative time
 */
function formatRelativeTime(timestamp: string | null): string {
  if (!timestamp) return "Never";

  const now = new Date();
  const time = new Date(timestamp);
  const diffMs = now.getTime() - time.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

function AgentSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {[...Array(11)].map((_, i) => (
        <div key={i} className="border rounded-lg p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Skeleton className="h-5 w-5" />
            <Skeleton className="h-4 w-24" />
          </div>
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-3/4" />
        </div>
      ))}
    </div>
  );
}

export function AgentStatusPanel() {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  const { data, isLoading, error, mutate } = useSWR<AgentStatusResponse>(
    "/api/v1/agents/status",
    fetcher,
    { refreshInterval: 30000 } // Refresh every 30s
  );

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-red-500" />
            Agent Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-6 text-red-500">
            <p className="font-medium">Failed to load agent status</p>
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
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)]">
            Agent Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <AgentSkeleton />
        </CardContent>
      </Card>
    );
  }

  // Merge config with status data
  const agentsWithStatus = AGENTS.map((config) => {
    const status = data.agents.find((s) => s.name === config.name);
    return { config, status };
  });

  // Count agents by status
  const statusCounts = data.agents.reduce(
    (acc, agent) => {
      acc[agent.status] = (acc[agent.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)]">
            Agent Status
          </CardTitle>
          <div className="flex gap-2">
            {statusCounts.running > 0 && (
              <Badge className="bg-green-100 text-green-700 text-xs">
                {statusCounts.running} running
              </Badge>
            )}
            {statusCounts.idle > 0 && (
              <Badge className="bg-yellow-100 text-yellow-700 text-xs">
                {statusCounts.idle} idle
              </Badge>
            )}
            {statusCounts.error > 0 && (
              <Badge className="bg-red-100 text-red-700 text-xs">
                {statusCounts.error} error
              </Badge>
            )}
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Last updated: {new Date(data.timestamp).toLocaleTimeString()}
        </p>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {agentsWithStatus.map(({ config, status }) => {
            const Icon = config.icon;
            const statusBadge = getStatusBadge(status?.status || "disabled");
            const isSelected = selectedAgent === config.name;

            return (
              <div
                key={config.name}
                className={cn(
                  "border rounded-lg p-4 transition-all cursor-pointer hover:shadow-md",
                  isSelected && "ring-2 ring-[var(--turkish-blue)] shadow-md",
                  status?.status === "error" && "border-red-300 bg-red-50/30"
                )}
                onClick={() =>
                  setSelectedAgent(isSelected ? null : config.name)
                }
              >
                {/* Header */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Icon className="h-5 w-5 text-[var(--turkish-blue)]" />
                    <h3 className="font-semibold text-sm">{config.displayName}</h3>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className={cn("h-2 w-2 rounded-full", statusBadge.dot)} />
                  </div>
                </div>

                {/* Description */}
                <p className="text-xs text-muted-foreground mb-3">
                  {config.description}
                </p>

                {/* Status Badge */}
                <Badge variant="outline" className={cn("text-xs mb-2", statusBadge.className)}>
                  {statusBadge.label}
                </Badge>

                {/* Metrics */}
                <div className="space-y-1 text-xs text-muted-foreground">
                  <div className="flex justify-between">
                    <span>Schedule:</span>
                    <span className="font-medium">{config.schedule}</span>
                  </div>
                  {status && (
                    <>
                      <div className="flex justify-between">
                        <span>Last run:</span>
                        <span className="font-medium">
                          {formatRelativeTime(status.last_run)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>Next run:</span>
                        <span className="font-medium">
                          {formatRelativeTime(status.next_run)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>Runs today:</span>
                        <span className="font-medium text-[var(--turkish-blue)]">
                          {status.runs_today}
                        </span>
                      </div>
                    </>
                  )}
                </div>

                {/* Error Message */}
                {status?.error_message && (
                  <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
                    {status.error_message}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Agent Controls - Show when agent selected */}
        {selectedAgent && (
          <div className="mt-6 pt-6 border-t">
            <AgentControls agentName={selectedAgent} onSuccess={() => mutate()} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
