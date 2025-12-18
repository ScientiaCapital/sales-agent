import { CommandCenter, DraftReviewQueue } from "@/components/ai";
import {
  ICPQueue,
  BDRWorkQueue,
  NeedsAttentionQueue,
  RecentActivity,
  ExecutiveSummary,
  LeadLifecycleFunnel,
  OutreachMetrics,
  AgentHealth,
} from "@/components/dashboard";
import { ExecutiveDashboard } from "@/components/executive";
import { MissionControl } from "@/components/MissionControl";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Zap, Mail, Target, ClipboardList, BarChart3, Gamepad2 } from "lucide-react";

export default function App() {

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-[var(--turkish-blue)]">
          Sales Agent Dashboard
        </h1>
        {/* TODO: Add TimePeriodToggle component when dashboard components are migrated */}
      </div>

      {/* Tab Navigation */}
      <Tabs defaultValue="mission-control" className="space-y-6">
        <TabsList className="grid w-full max-w-5xl grid-cols-6">
          <TabsTrigger value="mission-control" className="flex items-center gap-2 bg-black text-green-400 data-[state=active]:bg-green-900/50 data-[state=active]:text-green-300">
            <Gamepad2 className="h-4 w-4" />
            LEAD HUNTER
          </TabsTrigger>
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

        {/* LEAD HUNTER - Atari-style Agent Mission Control (CEO/CTO/VC Demo) */}
        <TabsContent value="mission-control" className="-mx-4 -mt-2">
          <MissionControl />
        </TabsContent>

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
          <ICPQueue />
        </TabsContent>

        {/* Sr. BDR Tim Kipper View */}
        <TabsContent value="bdr" className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <BDRWorkQueue />
            <NeedsAttentionQueue />
          </div>
          <RecentActivity />
        </TabsContent>

        {/* CEO/CTO Executive View - New Chart.js Dashboard */}
        <TabsContent value="executive" className="-mx-4 -my-8">
          <ExecutiveDashboard />
        </TabsContent>
      </Tabs>
    </div>
  );
}
