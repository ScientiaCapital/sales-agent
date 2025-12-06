"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Bell,
  CheckCircle,
  AlertTriangle,
  AlertCircle,
  Info,
  Wifi,
  WifiOff,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getAuthenticatedWebSocketUrl } from "@/lib/auth";

/**
 * AlertFeed - Real-time alert stream with WebSocket integration
 *
 * Features:
 * - WebSocket connection to /api/v1/ws/cockpit for live updates
 * - Fallback to REST polling if WebSocket unavailable
 * - Alert severity levels: critical, high, medium, low
 * - Acknowledge/dismiss functionality
 * - Connection status indicator
 */

// ============================================================================
// Types
// ============================================================================

interface Alert {
  id: string;
  severity: "critical" | "high" | "medium" | "low";
  title: string;
  message: string;
  agent_name?: string;
  company_id?: string;
  contact_id?: string;
  created_at: string;
  acknowledged: boolean;
}

interface AlertsResponse {
  alerts: Alert[];
  total: number;
  unread_count: number;
}

interface WebSocketEvent {
  type: "alert" | "agent_started" | "agent_completed" | "agent_failed" | "connected" | "keepalive" | "pong";
  severity?: string;
  title?: string;
  message?: string;
  agent?: string;
  task_id?: string;
  timestamp?: string;
  lead_id?: string;
}

// ============================================================================
// Helpers
// ============================================================================

const fetcher = (url: string) => fetch(url).then((res) => res.json());

function getSeverityConfig(severity: Alert["severity"]) {
  switch (severity) {
    case "critical":
      return {
        icon: AlertCircle,
        className: "bg-red-100 text-red-700 border-red-300",
        dotColor: "bg-red-500 animate-pulse",
        label: "Critical",
      };
    case "high":
      return {
        icon: AlertTriangle,
        className: "bg-orange-100 text-orange-700 border-orange-300",
        dotColor: "bg-orange-500",
        label: "High",
      };
    case "medium":
      return {
        icon: Bell,
        className: "bg-yellow-100 text-yellow-700 border-yellow-300",
        dotColor: "bg-yellow-500",
        label: "Medium",
      };
    case "low":
      return {
        icon: Info,
        className: "bg-blue-100 text-blue-700 border-blue-300",
        dotColor: "bg-blue-500",
        label: "Low",
      };
  }
}

function formatTimeAgo(timestamp: string): string {
  const now = new Date();
  const time = new Date(timestamp);
  const diffMs = now.getTime() - time.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return time.toLocaleDateString();
}

// ============================================================================
// Components
// ============================================================================

function AlertSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <div key={i} className="flex items-start gap-3 p-3 border rounded-lg">
          <Skeleton className="h-5 w-5 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-1/4" />
          </div>
        </div>
      ))}
    </div>
  );
}

interface AlertItemProps {
  alert: Alert;
  onAcknowledge: (id: string) => void;
}

function AlertItem({ alert, onAcknowledge }: AlertItemProps) {
  const config = getSeverityConfig(alert.severity);
  const Icon = config.icon;

  return (
    <div
      className={cn(
        "flex items-start gap-3 p-3 border rounded-lg transition-all",
        alert.acknowledged ? "opacity-60 bg-gray-50" : "bg-white",
        !alert.acknowledged && "hover:shadow-sm"
      )}
    >
      {/* Severity Icon */}
      <div className="pt-0.5">
        <div className={cn("h-2 w-2 rounded-full", config.dotColor)} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <Icon className={cn("h-4 w-4", config.className.split(" ")[1])} />
          <h4 className="font-medium text-sm truncate">{alert.title}</h4>
          <Badge variant="outline" className={cn("text-xs", config.className)}>
            {config.label}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground line-clamp-2">{alert.message}</p>
        <div className="flex items-center gap-2 mt-2">
          <span className="text-xs text-muted-foreground">
            {formatTimeAgo(alert.created_at)}
          </span>
          {alert.agent_name && (
            <Badge variant="secondary" className="text-xs">
              {alert.agent_name}
            </Badge>
          )}
        </div>
      </div>

      {/* Acknowledge Button */}
      {!alert.acknowledged && (
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0 hover:bg-green-100"
          onClick={() => onAcknowledge(alert.id)}
          title="Acknowledge"
        >
          <CheckCircle className="h-4 w-4 text-green-600" />
        </Button>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function AlertFeed() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [showAcknowledged, setShowAcknowledged] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch initial alerts via REST
  const { data, isLoading, error, mutate } = useSWR<AlertsResponse>(
    "/api/v1/alerts?limit=50",
    fetcher,
    { refreshInterval: wsConnected ? 0 : 30000 } // Only poll if WS disconnected
  );

  // Update alerts when REST data changes
  useEffect(() => {
    if (data?.alerts) {
      setAlerts(data.alerts);
    }
  }, [data]);

  // WebSocket connection
  const connectWebSocket = useCallback(() => {
    // Get authenticated WebSocket URL (handles Supabase token retrieval)
    const wsUrl = getAuthenticatedWebSocketUrl("/api/v1/ws/cockpit");

    if (!wsUrl) {
      console.warn("AlertFeed: No auth token available for WebSocket");
      return;
    }

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("AlertFeed: WebSocket connected");
      setWsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data: WebSocketEvent = JSON.parse(event.data);

        // Handle different event types
        switch (data.type) {
          case "alert":
            // Add new alert to the list
            const newAlert: Alert = {
              id: `ws-${Date.now()}`,
              severity: (data.severity as Alert["severity"]) || "medium",
              title: data.title || "New Alert",
              message: data.message || "",
              agent_name: data.agent,
              created_at: data.timestamp || new Date().toISOString(),
              acknowledged: false,
            };
            setAlerts((prev) => [newAlert, ...prev.slice(0, 49)]);
            break;

          case "agent_started":
          case "agent_completed":
          case "agent_failed":
            // Convert agent events to alerts
            const agentAlert: Alert = {
              id: `ws-${data.task_id || Date.now()}`,
              severity: data.type === "agent_failed" ? "high" : "low",
              title: `Agent ${data.type.replace("agent_", "")}`,
              message: `${data.agent} ${data.type.replace("agent_", "")}`,
              agent_name: data.agent,
              created_at: data.timestamp || new Date().toISOString(),
              acknowledged: false,
            };
            setAlerts((prev) => [agentAlert, ...prev.slice(0, 49)]);
            break;

          case "connected":
          case "keepalive":
          case "pong":
            // Connection management events - no action needed
            break;
        }
      } catch (e) {
        console.error("AlertFeed: Failed to parse WebSocket message", e);
      }
    };

    ws.onclose = () => {
      console.log("AlertFeed: WebSocket disconnected");
      setWsConnected(false);
      wsRef.current = null;

      // Attempt reconnection after 5 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        connectWebSocket();
      }, 5000);
    };

    ws.onerror = (error) => {
      console.error("AlertFeed: WebSocket error", error);
    };

    wsRef.current = ws;
  }, []);

  // Connect WebSocket on mount
  useEffect(() => {
    connectWebSocket();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connectWebSocket]);

  // Acknowledge alert
  const handleAcknowledge = async (alertId: string) => {
    try {
      await fetch(`/api/v1/alerts/${alertId}/acknowledge`, {
        method: "POST",
      });

      // Update local state
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, acknowledged: true } : a))
      );

      // Refresh from server
      mutate();
    } catch (e) {
      console.error("Failed to acknowledge alert", e);
    }
  };

  // Filter alerts
  const visibleAlerts = showAcknowledged
    ? alerts
    : alerts.filter((a) => !a.acknowledged);

  const unreadCount = alerts.filter((a) => !a.acknowledged).length;

  // Error state
  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Alert Feed
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-6 text-red-500">
            <AlertCircle className="h-8 w-8 mx-auto mb-2" />
            <p className="font-medium">Failed to load alerts</p>
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={() => mutate()}
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Alert Feed
            {unreadCount > 0 && (
              <Badge className="bg-red-500 text-white text-xs ml-2">
                {unreadCount}
              </Badge>
            )}
          </CardTitle>
          <div className="flex items-center gap-2">
            {/* Connection Status */}
            <div
              className={cn(
                "flex items-center gap-1 text-xs",
                wsConnected ? "text-green-600" : "text-gray-400"
              )}
              title={wsConnected ? "Live updates active" : "Polling mode"}
            >
              {wsConnected ? (
                <Wifi className="h-3 w-3" />
              ) : (
                <WifiOff className="h-3 w-3" />
              )}
              <span>{wsConnected ? "Live" : "Polling"}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            Real-time activity notifications
          </p>
          <Button
            variant="ghost"
            size="sm"
            className="text-xs h-6"
            onClick={() => setShowAcknowledged(!showAcknowledged)}
          >
            {showAcknowledged ? "Hide acknowledged" : "Show all"}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading && !alerts.length ? (
          <AlertSkeleton />
        ) : visibleAlerts.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <CheckCircle className="h-8 w-8 mx-auto mb-2 text-green-500" />
            <p className="text-sm">All caught up!</p>
            <p className="text-xs">No new alerts</p>
          </div>
        ) : (
          <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
            {visibleAlerts.map((alert) => (
              <AlertItem
                key={alert.id}
                alert={alert}
                onAcknowledge={handleAcknowledge}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
