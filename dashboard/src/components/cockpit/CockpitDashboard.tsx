"use client";

import { Activity, Terminal } from "lucide-react";
import { AgentStatusPanel } from "./AgentStatusPanel";
import { OutreachMetrics } from "./OutreachMetrics";
import { AlertFeed } from "./AlertFeed";
import { SequenceManager } from "./SequenceManager";

/**
 * BDR Cockpit Dashboard - Main control center for Tim's GTM automation
 *
 * 4-panel layout:
 * 1. Agent Status Panel - Shows status of all 11 autonomous agents
 * 2. Outreach Metrics - Email/SMS/call counters
 * 3. Alert Feed - Real-time WebSocket alerts and notifications
 * 4. Sequence Manager - Manage Close CRM sequences
 */
export function CockpitDashboard() {
  return (
    <div className="space-y-6">
      {/* Header with Terminal-Inspired Aesthetic */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Terminal className="h-8 w-8 text-[var(--turkish-blue)]" />
            <div className="absolute -top-1 -right-1 h-3 w-3 bg-green-500 rounded-full animate-pulse" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-[var(--turkish-blue)] tracking-tight">
              BDR Cockpit
            </h1>
            <p className="text-sm text-muted-foreground font-mono">
              GTM Automation Control Center • 11 Agents Active
            </p>
          </div>
        </div>
        {/* System Status Indicator */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-green-50 border border-green-200 rounded-full">
          <div className="h-2 w-2 bg-green-500 rounded-full animate-pulse" />
          <span className="text-xs font-medium text-green-700">Systems Online</span>
        </div>
      </div>

      {/* 4-Panel Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Panel 1: Agent Status - Full Width */}
        <div className="lg:col-span-2">
          <AgentStatusPanel />
        </div>

        {/* Panel 2: Outreach Metrics */}
        <OutreachMetrics />

        {/* Panel 3: Alert Feed - Real-time WebSocket alerts */}
        <AlertFeed />

        {/* Panel 4: Sequence Manager - Full Width */}
        <SequenceManager />
      </div>
    </div>
  );
}
