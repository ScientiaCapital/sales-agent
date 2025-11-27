"use client";

import {
  ExecutiveSummary,
  PipelineFunnel,
  AgentHealth,
  RecentActivity,
} from "@/components/dashboard";

export default function Dashboard() {
  return (
    <div className="container mx-auto px-4 py-8">
      {/* Executive Summary - 4 KPI Cards */}
      <ExecutiveSummary />

      {/* Two Column Layout: Funnel + Activity */}
      <div className="grid gap-6 lg:grid-cols-2 mb-8">
        <PipelineFunnel />
        <RecentActivity />
      </div>

      {/* Agent Health Grid - 6 Agents */}
      <AgentHealth />
    </div>
  );
}
