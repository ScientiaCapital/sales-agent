"use client";

import { useState } from "react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import {
  GitBranch,
  Play,
  Pause,
  StopCircle,
  Users,
  Mail,
  Clock,
  CheckCircle,
  AlertCircle,
  ChevronRight,
  RefreshCw,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * SequenceManager - Close CRM sequence management panel
 *
 * Features:
 * - View all active Close sequences
 * - Subscriber counts and completion rates
 * - Pause/Resume/Stop sequence controls
 * - Step progress indicators
 * - Next scheduled send times
 */

// ============================================================================
// Types
// ============================================================================

interface SequenceStep {
  step_number: number;
  type: "email" | "sms" | "call" | "wait";
  subject?: string;
  delay_days?: number;
  status: "pending" | "active" | "completed";
}

interface Sequence {
  id: string;
  name: string;
  status: "active" | "paused" | "stopped";
  total_subscribers: number;
  active_subscribers: number;
  completed_subscribers: number;
  steps: SequenceStep[];
  current_step: number;
  total_steps: number;
  created_at: string;
  last_activity_at: string | null;
  next_scheduled_at: string | null;
}

interface SequencesResponse {
  sequences: Sequence[];
  total: number;
  timestamp: string;
}

// ============================================================================
// Helpers
// ============================================================================

const fetcher = (url: string) => fetch(url).then((res) => res.json());

function getStatusConfig(status: Sequence["status"]) {
  switch (status) {
    case "active":
      return {
        className: "bg-green-100 text-green-700 border-green-300",
        dot: "bg-green-500 animate-pulse",
        label: "Active",
      };
    case "paused":
      return {
        className: "bg-yellow-100 text-yellow-700 border-yellow-300",
        dot: "bg-yellow-500",
        label: "Paused",
      };
    case "stopped":
      return {
        className: "bg-gray-100 text-gray-500 border-gray-300",
        dot: "bg-gray-400",
        label: "Stopped",
      };
  }
}

function formatTimeUntil(timestamp: string | null): string {
  if (!timestamp) return "Not scheduled";

  const now = new Date();
  const time = new Date(timestamp);
  const diffMs = time.getTime() - now.getTime();

  if (diffMs < 0) return "Overdue";

  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 60) return `in ${diffMins}m`;
  if (diffHours < 24) return `in ${diffHours}h`;
  return `in ${diffDays}d`;
}

// ============================================================================
// Components
// ============================================================================

function SequenceSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2].map((i) => (
        <div key={i} className="border rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-6 w-16" />
          </div>
          <Skeleton className="h-2 w-full" />
          <div className="flex gap-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-24" />
          </div>
        </div>
      ))}
    </div>
  );
}

interface SequenceCardProps {
  sequence: Sequence;
  onAction: (action: "pause" | "resume" | "stop", id: string) => void;
}

function SequenceCard({ sequence, onAction }: SequenceCardProps) {
  const [expanded, setExpanded] = useState(false);
  const statusConfig = getStatusConfig(sequence.status);
  const completionRate = sequence.total_subscribers > 0
    ? (sequence.completed_subscribers / sequence.total_subscribers) * 100
    : 0;
  const progressRate = sequence.total_steps > 0
    ? (sequence.current_step / sequence.total_steps) * 100
    : 0;

  return (
    <div className="border rounded-lg overflow-hidden transition-all hover:shadow-sm">
      {/* Header */}
      <div
        className="p-4 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <GitBranch className="h-5 w-5 text-[var(--turkish-blue)]" />
            <h3 className="font-semibold text-sm">{sequence.name}</h3>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className={cn("text-xs", statusConfig.className)}>
              <div className={cn("h-1.5 w-1.5 rounded-full mr-1.5", statusConfig.dot)} />
              {statusConfig.label}
            </Badge>
            <ChevronRight
              className={cn(
                "h-4 w-4 text-muted-foreground transition-transform",
                expanded && "rotate-90"
              )}
            />
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mb-3">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span>Step {sequence.current_step} of {sequence.total_steps}</span>
            <span>{progressRate.toFixed(0)}% complete</span>
          </div>
          <Progress value={progressRate} className="h-2" />
        </div>

        {/* Stats Row */}
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <Users className="h-3.5 w-3.5" />
            <span>{sequence.active_subscribers} active</span>
          </div>
          <div className="flex items-center gap-1">
            <CheckCircle className="h-3.5 w-3.5 text-green-500" />
            <span>{sequence.completed_subscribers} completed</span>
          </div>
          <div className="flex items-center gap-1">
            <Clock className="h-3.5 w-3.5" />
            <span>Next: {formatTimeUntil(sequence.next_scheduled_at)}</span>
          </div>
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div className="border-t bg-gray-50/50 p-4 space-y-4">
          {/* Steps Timeline */}
          <div className="space-y-2">
            <h4 className="text-xs font-medium text-muted-foreground">Sequence Steps</h4>
            <div className="flex items-center gap-1">
              {sequence.steps.slice(0, 8).map((step, idx) => (
                <div
                  key={idx}
                  className={cn(
                    "flex-1 h-1.5 rounded-full transition-all",
                    step.status === "completed"
                      ? "bg-green-500"
                      : step.status === "active"
                      ? "bg-[var(--turkish-blue)] animate-pulse"
                      : "bg-gray-200"
                  )}
                  title={`Step ${step.step_number}: ${step.type}${step.subject ? ` - ${step.subject}` : ""}`}
                />
              ))}
              {sequence.steps.length > 8 && (
                <span className="text-xs text-muted-foreground ml-1">
                  +{sequence.steps.length - 8}
                </span>
              )}
            </div>
          </div>

          {/* Completion Stats */}
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="p-2 bg-white rounded border">
              <div className="text-lg font-bold text-[var(--turkish-blue)]">
                {sequence.total_subscribers}
              </div>
              <div className="text-xs text-muted-foreground">Total</div>
            </div>
            <div className="p-2 bg-white rounded border">
              <div className="text-lg font-bold text-green-600">
                {completionRate.toFixed(0)}%
              </div>
              <div className="text-xs text-muted-foreground">Completed</div>
            </div>
            <div className="p-2 bg-white rounded border">
              <div className="text-lg font-bold text-yellow-600">
                {sequence.active_subscribers}
              </div>
              <div className="text-xs text-muted-foreground">In Progress</div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 pt-2">
            {sequence.status === "active" ? (
              <Button
                variant="outline"
                size="sm"
                className="flex-1 text-xs"
                onClick={(e) => {
                  e.stopPropagation();
                  onAction("pause", sequence.id);
                }}
              >
                <Pause className="h-3.5 w-3.5 mr-1" />
                Pause
              </Button>
            ) : sequence.status === "paused" ? (
              <Button
                variant="outline"
                size="sm"
                className="flex-1 text-xs bg-green-50 hover:bg-green-100 text-green-700"
                onClick={(e) => {
                  e.stopPropagation();
                  onAction("resume", sequence.id);
                }}
              >
                <Play className="h-3.5 w-3.5 mr-1" />
                Resume
              </Button>
            ) : null}
            {sequence.status !== "stopped" && (
              <Button
                variant="outline"
                size="sm"
                className="flex-1 text-xs text-red-600 hover:bg-red-50"
                onClick={(e) => {
                  e.stopPropagation();
                  onAction("stop", sequence.id);
                }}
              >
                <StopCircle className="h-3.5 w-3.5 mr-1" />
                Stop
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function SequenceManager() {
  const { data, isLoading, error, mutate } = useSWR<SequencesResponse>(
    "/api/v1/sequences",
    fetcher,
    { refreshInterval: 30000 }
  );

  // Handle sequence actions
  const handleAction = async (action: "pause" | "resume" | "stop", sequenceId: string) => {
    try {
      const endpoint = action === "resume" ? "resume" : action;
      await fetch(`/api/v1/sequences/${sequenceId}/${endpoint}`, {
        method: "POST",
      });
      mutate();
    } catch (e) {
      console.error(`Failed to ${action} sequence`, e);
    }
  };

  // Error state
  if (error) {
    return (
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <GitBranch className="h-5 w-5" />
            Sequence Manager
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-6 text-red-500">
            <AlertCircle className="h-8 w-8 mx-auto mb-2" />
            <p className="font-medium">Failed to load sequences</p>
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

  // Calculate summary stats
  const activeCount = data?.sequences.filter((s) => s.status === "active").length || 0;
  const totalSubscribers = data?.sequences.reduce((sum, s) => sum + s.active_subscribers, 0) || 0;

  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <GitBranch className="h-5 w-5" />
            Sequence Manager
          </CardTitle>
          <div className="flex items-center gap-2">
            {activeCount > 0 && (
              <Badge className="bg-green-100 text-green-700 text-xs">
                <Zap className="h-3 w-3 mr-1" />
                {activeCount} active
              </Badge>
            )}
            <Badge variant="outline" className="text-xs">
              {totalSubscribers} subscribers
            </Badge>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Manage Close CRM outreach sequences
        </p>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <SequenceSkeleton />
        ) : !data?.sequences?.length ? (
          <div className="text-center py-8 text-muted-foreground">
            <GitBranch className="h-8 w-8 mx-auto mb-2 text-gray-400" />
            <p className="text-sm">No active sequences</p>
            <p className="text-xs">Create sequences in Close CRM to manage them here</p>
          </div>
        ) : (
          <div className="space-y-3">
            {data.sequences.map((sequence) => (
              <SequenceCard
                key={sequence.id}
                sequence={sequence}
                onAction={handleAction}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
