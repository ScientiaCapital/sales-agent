"use client";

import { Activity, RefreshCw } from "lucide-react";
import useSWR from "swr";
import { Badge } from "@/components/ui/badge";

interface HealthResponse {
  status: "healthy" | "degraded" | "unhealthy";
  timestamp: string;
  version: string;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export function Header() {
  const { data: health, mutate } = useSWR<HealthResponse>(
    "/api/health",
    fetcher,
    { refreshInterval: 30000 } // Refresh every 30s
  );

  const statusColors = {
    healthy: "bg-green-500",
    degraded: "bg-yellow-500",
    unhealthy: "bg-red-500",
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-[var(--turkish-blue)] text-white">
      <div className="container flex h-16 items-center justify-between px-4 mx-auto">
        {/* Logo + Title */}
        <div className="flex items-center gap-3">
          <span className="text-3xl" role="img" aria-label="Evil eye logo">
            🧿
          </span>
          <div>
            <h1 className="text-xl font-bold tracking-tight">Sales Agent</h1>
            <p className="text-xs text-blue-100 opacity-80">Pipeline Dashboard</p>
          </div>
        </div>

        {/* Health Indicator */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            <span className="text-sm hidden sm:inline">System Status:</span>
            {health ? (
              <Badge
                variant="secondary"
                className={`${statusColors[health.status]} text-white border-0`}
              >
                {health.status.charAt(0).toUpperCase() + health.status.slice(1)}
              </Badge>
            ) : (
              <Badge variant="secondary" className="bg-gray-400">
                Loading...
              </Badge>
            )}
          </div>
          <button
            onClick={() => mutate()}
            className="p-2 hover:bg-white/10 rounded-lg transition-colors"
            title="Refresh health status"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
