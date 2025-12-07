import { CommandCenter, DraftReviewQueue } from "@/components/ai";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Zap, Mail, Target, ClipboardList, BarChart3 } from "lucide-react";

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
          <div className="text-center py-12 text-muted-foreground">
            <Target className="size-12 mx-auto mb-4 opacity-50" />
            <p className="font-medium">ICP Queue Coming Soon</p>
            <p className="text-sm">Dashboard components will be migrated in the next phase</p>
          </div>
        </TabsContent>

        {/* Sr. BDR Tim Kipper View */}
        <TabsContent value="bdr" className="space-y-6">
          <div className="text-center py-12 text-muted-foreground">
            <ClipboardList className="size-12 mx-auto mb-4 opacity-50" />
            <p className="font-medium">BDR View Coming Soon</p>
            <p className="text-sm">Dashboard components will be migrated in the next phase</p>
          </div>
        </TabsContent>

        {/* CEO/CTO Executive View */}
        <TabsContent value="executive" className="space-y-6">
          <div className="text-center py-12 text-muted-foreground">
            <BarChart3 className="size-12 mx-auto mb-4 opacity-50" />
            <p className="font-medium">Executive View Coming Soon</p>
            <p className="text-sm">Dashboard components will be migrated in the next phase</p>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
