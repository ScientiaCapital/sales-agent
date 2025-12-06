"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Play, Square, Pause, AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface AgentControlsProps {
  agentName: string;
  onSuccess?: () => void;
}

type ControlState = "idle" | "loading" | "success" | "error";

/**
 * Agent Controls - Start/Stop/Pause buttons for individual agents
 *
 * POST endpoints:
 * - /api/v1/agents/{name}/start
 * - /api/v1/agents/{name}/stop
 * - /api/v1/agents/{name}/pause
 */
export function AgentControls({ agentName, onSuccess }: AgentControlsProps) {
  const [startState, setStartState] = useState<ControlState>("idle");
  const [stopState, setStopState] = useState<ControlState>("idle");
  const [pauseState, setPauseState] = useState<ControlState>("idle");
  const [showStopConfirm, setShowStopConfirm] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const displayName = agentName
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

  // Auto-cancel stop confirmation after 5s
  useEffect(() => {
    if (showStopConfirm) {
      const timer = setTimeout(() => {
        setShowStopConfirm(false);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [showStopConfirm]);

  /**
   * Start agent
   */
  const handleStart = async () => {
    setStartState("loading");
    setErrorMessage(null);

    try {
      const response = await fetch(`/api/v1/agents/${agentName}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to start agent");
      }

      setStartState("success");
      setTimeout(() => setStartState("idle"), 2000);
      onSuccess?.();
    } catch (err) {
      setStartState("error");
      setErrorMessage(err instanceof Error ? err.message : "Unknown error");
      setTimeout(() => setStartState("idle"), 3000);
    }
  };

  /**
   * Stop agent (with confirmation)
   */
  const handleStop = async () => {
    if (!showStopConfirm) {
      setShowStopConfirm(true);
      return;
    }

    setStopState("loading");
    setErrorMessage(null);

    try {
      const response = await fetch(`/api/v1/agents/${agentName}/stop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to stop agent");
      }

      setStopState("success");
      setShowStopConfirm(false);
      setTimeout(() => setStopState("idle"), 2000);
      onSuccess?.();
    } catch (err) {
      setStopState("error");
      setErrorMessage(err instanceof Error ? err.message : "Unknown error");
      setTimeout(() => setStopState("idle"), 3000);
    }
  };

  /**
   * Pause agent
   */
  const handlePause = async () => {
    setPauseState("loading");
    setErrorMessage(null);

    try {
      const response = await fetch(`/api/v1/agents/${agentName}/pause`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to pause agent");
      }

      setPauseState("success");
      setTimeout(() => setPauseState("idle"), 2000);
      onSuccess?.();
    } catch (err) {
      setPauseState("error");
      setErrorMessage(err instanceof Error ? err.message : "Unknown error");
      setTimeout(() => setPauseState("idle"), 3000);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">Agent Controls</h3>
        <Badge variant="outline" className="text-xs">
          {displayName}
        </Badge>
      </div>

      {/* Control Buttons */}
      <div className="flex gap-3">
        {/* Start Button */}
        <Button
          variant="outline"
          size="sm"
          disabled={startState === "loading"}
          onClick={handleStart}
          className={cn(
            "flex items-center gap-2 transition-all",
            startState === "success" && "bg-green-100 text-green-700 border-green-300"
          )}
        >
          {startState === "loading" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : startState === "success" ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          {startState === "loading" ? "Starting..." : startState === "success" ? "Started" : "Start"}
        </Button>

        {/* Pause Button */}
        <Button
          variant="outline"
          size="sm"
          disabled={pauseState === "loading"}
          onClick={handlePause}
          className={cn(
            "flex items-center gap-2 transition-all",
            pauseState === "success" && "bg-yellow-100 text-yellow-700 border-yellow-300"
          )}
        >
          {pauseState === "loading" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : pauseState === "success" ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : (
            <Pause className="h-4 w-4" />
          )}
          {pauseState === "loading" ? "Pausing..." : pauseState === "success" ? "Paused" : "Pause"}
        </Button>

        {/* Stop Button */}
        <Button
          variant="outline"
          size="sm"
          disabled={stopState === "loading"}
          onClick={handleStop}
          className={cn(
            "flex items-center gap-2 transition-all",
            showStopConfirm && "bg-red-100 text-red-700 border-red-300",
            stopState === "success" && "bg-green-100 text-green-700 border-green-300"
          )}
        >
          {stopState === "loading" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : stopState === "success" ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : (
            <Square className="h-4 w-4" />
          )}
          {stopState === "loading"
            ? "Stopping..."
            : stopState === "success"
            ? "Stopped"
            : showStopConfirm
            ? "Confirm Stop"
            : "Stop"}
        </Button>
      </div>

      {/* Stop Confirmation Message */}
      {showStopConfirm && (
        <div className="flex items-start gap-2 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
          <AlertCircle className="h-4 w-4 text-yellow-600 mt-0.5 flex-shrink-0" />
          <div className="flex-1 text-xs">
            <p className="font-medium text-yellow-900">Are you sure?</p>
            <p className="text-yellow-700 mt-1">
              Stopping this agent will interrupt any in-progress tasks. Click "Confirm Stop" to
              proceed or wait 5 seconds to cancel.
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="text-yellow-700 hover:text-yellow-900"
            onClick={() => setShowStopConfirm(false)}
          >
            Cancel
          </Button>
        </div>
      )}

      {/* Error Message */}
      {errorMessage && (
        <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-md">
          <AlertCircle className="h-4 w-4 text-red-600 mt-0.5 flex-shrink-0" />
          <div className="flex-1 text-xs text-red-700">
            <p className="font-medium">Error</p>
            <p className="mt-1">{errorMessage}</p>
          </div>
        </div>
      )}

    </div>
  );
}
