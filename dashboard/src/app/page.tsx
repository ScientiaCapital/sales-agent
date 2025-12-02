"use client";

import { useState } from "react";
import {
  ExecutiveSummary,
  PipelineFunnel,
  AgentHealth,
  RecentActivity,
  TimePeriodToggle,
  LeadLifecycleFunnel,
  NeedsAttentionQueue,
  BDRWorkQueue,
  ImportHistory,
  OutreachMetrics,
  ICPQueue,
} from "@/components/dashboard";
import { CommandCenter, DraftReviewQueue } from "@/components/ai";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BarChart3, ClipboardList, Target, Zap, Mail } from "lucide-react";

export default function Dashboard() {
  const [period, setPeriod] = useState<"7d" | "mtd">("7d");

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header with Time Period Toggle */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-[var(--turkish-blue)]">
          Sales Agent Dashboard
        </h1>
        <TimePeriodToggle value={period} onChange={setPeriod} />
      </div>

      {/* Tab Navigation: AI Command Center + CEO/CTO View vs BDR View vs ICP/Sales */}
      <Tabs defaultValue="command-center" className="space-y-6">
        <TabsList className="grid w-full max-w-4xl grid-cols-5">
          <TabsTrigger value="command-center" className="flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Command Center
          </TabsTrigger>
          <TabsTrigger value="draft-queue" className="flex items-center gap-2">
            <Mail className="h-4 w-4" />
            Draft Queue
          </TabsTrigger>
          <TabsTrigger value="icp" className="flex items-center gap-2">
            <Target className="h-4 w-4" />
            ICP Queue
          </TabsTrigger>
          <TabsTrigger value="bdr" className="flex items-center gap-2">
            <ClipboardList className="h-4 w-4" />
            BDR View
          </TabsTrigger>
          <TabsTrigger value="executive" className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            CEO/CTO
          </TabsTrigger>
        </TabsList>

        {/* AI Command Center - Interactive Chat with LangGraph Agents */}
        <TabsContent value="command-center">
          <CommandCenter />
        </TabsContent>

        {/* Draft Review Queue - Email/LinkedIn Message Review */}
        <TabsContent value="draft-queue">
          <DraftReviewQueue />
        </TabsContent>

        {/* ICP Queue - Tim's Smart Views + AE Pipeline */}
        <TabsContent value="icp" className="space-y-6">
          {/* Full Width: ICP Queue with Smart Views + AE Tracking */}
          <div className="grid gap-6">
            <ICPQueue />
          </div>

          {/* Outreach + Work Queue */}
          <div className="grid gap-6 lg:grid-cols-2">
            <OutreachMetrics period={period} />
            <NeedsAttentionQueue />
          </div>
        </TabsContent>

        {/* Sr. BDR Tim Kipper View */}
        <TabsContent value="bdr" className="space-y-6">
          {/* Top Row: Outreach Metrics + Work Queue */}
          <div className="grid gap-6 lg:grid-cols-2">
            <OutreachMetrics period={period} />
            <BDRWorkQueue />
          </div>

          {/* Middle Row: Lifecycle Funnel + Alerts */}
          <div className="grid gap-6 lg:grid-cols-2">
            <LeadLifecycleFunnel period={period} />
            <NeedsAttentionQueue />
          </div>

          {/* Bottom Row: Import History + Recent Activity */}
          <div className="grid gap-6 lg:grid-cols-2">
            <ImportHistory />
            <RecentActivity />
          </div>
        </TabsContent>

        {/* CEO/CTO Executive View */}
        <TabsContent value="executive" className="space-y-6">
          {/* Executive Summary - 4 KPI Cards */}
          <ExecutiveSummary />

          {/* Two Column Layout: New Lifecycle Funnel + Alerts */}
          <div className="grid gap-6 lg:grid-cols-2">
            <LeadLifecycleFunnel period={period} />
            <NeedsAttentionQueue />
          </div>

          {/* Two Column Layout: Agent Health + Activity */}
          <div className="grid gap-6 lg:grid-cols-2">
            <AgentHealth />
            <RecentActivity />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
