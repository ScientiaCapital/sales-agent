import { useState } from "react";
import { StatsGrid } from "./StatsGrid";
import { TierBreakdown } from "./TierBreakdown";
import { PipelineCharts } from "./PipelineCharts";
import { TopProspectsTable } from "./TopProspectsTable";
import { StrategicInsights } from "./StrategicInsights";
import { TimePeriodSelector } from "./TimePeriodSelector";
import type { TimePeriod } from "./TimePeriodSelector";
import { BarChart3 } from "lucide-react";

export function ExecutiveDashboard() {
  const [timePeriod, setTimePeriod] = useState<TimePeriod>("7d");

  return (
    <div
      className="min-h-screen py-8 px-6"
      style={{
        background: "linear-gradient(135deg, #0f0f23 0%, #1a1a3e 100%)",
      }}
    >
      {/* Header */}
      <div className="max-w-[1600px] mx-auto mb-8">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-3 rounded-xl bg-gradient-to-br from-purple-600 to-pink-600 shadow-lg shadow-purple-500/50">
                <BarChart3 className="h-8 w-8 text-white" />
              </div>
              <h1
                className="text-5xl font-black text-transparent bg-clip-text"
                style={{
                  backgroundImage:
                    "linear-gradient(135deg, #818cf8 0%, #c084fc 50%, #f472b6 100%)",
                }}
              >
                Executive Dashboard
              </h1>
            </div>
            <p className="text-gray-400 text-lg ml-16">
              Real-time sales performance and pipeline insights
            </p>
          </div>
          <TimePeriodSelector value={timePeriod} onChange={setTimePeriod} />
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-[1600px] mx-auto space-y-8">
        {/* Stats Grid - 8 KPI Cards */}
        <section>
          <StatsGrid />
        </section>

        {/* ICP Tier Breakdown */}
        <section>
          <TierBreakdown />
        </section>

        {/* Charts - 4 Visualizations */}
        <section>
          <h2 className="text-3xl font-bold mb-6 text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-cyan-400 to-teal-400">
            Pipeline Analytics
          </h2>
          <PipelineCharts />
        </section>

        {/* Strategic Insights */}
        <section>
          <StrategicInsights />
        </section>

        {/* Top Prospects Table */}
        <section>
          <TopProspectsTable />
        </section>
      </div>

      {/* Footer */}
      <div className="max-w-[1600px] mx-auto mt-12 pt-8 border-t border-gray-800">
        <div className="flex items-center justify-between text-sm text-gray-500">
          <div>
            <span className="font-medium text-gray-400">Sales Agent Dashboard</span>
            <span className="mx-2">•</span>
            <span>Powered by LangGraph Multi-Agent System</span>
          </div>
          <div>
            <span className="text-gray-600">Last updated: </span>
            <span className="text-gray-400 font-medium">
              {new Date().toLocaleTimeString()}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
