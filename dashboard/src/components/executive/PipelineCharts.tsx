import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertCircle } from "lucide-react";
import {
  Chart as ChartJS,
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
} from "chart.js";
import type { ChartOptions } from "chart.js";
import { Doughnut, Bar } from "react-chartjs-2";

// Register Chart.js components
ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, Tooltip, Legend);

// Set global Chart.js defaults for dark theme
ChartJS.defaults.color = "#9ca3af";
ChartJS.defaults.borderColor = "rgba(99, 102, 241, 0.2)";

interface ICPQueueResponse {
  summary: {
    total_leads: number;
    untouched_count: number;
    by_quarter: { Q3: number; Q4: number; PPL: number };
  };
  tier_breakdown: { PLATINUM: number; GOLD: number; SILVER: number; BRONZE: number; UNSCORED: number };
  state_breakdown: Record<string, number>;
}

interface LifecycleStage {
  stage: string;
  count: number;
  conversion_rate: number;
}

interface LifecycleResponse {
  stages: LifecycleStage[];
  total_leads: number;
}

interface WorkQueueItem {
  id: string;
  company_name: string;
  state: string;
  lead_score: number;
  icp_tier?: string;
}

interface WorkQueueResponse {
  tasks: WorkQueueItem[];
  total: number;
  by_priority: Record<string, number>;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

const chartOptions: ChartOptions<"doughnut"> = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: "bottom" as const,
      labels: {
        color: "#e5e7eb",
        padding: 15,
        font: { size: 12 },
      },
    },
    tooltip: {
      backgroundColor: "rgba(17, 24, 39, 0.95)",
      titleColor: "#f3f4f6",
      bodyColor: "#d1d5db",
      borderColor: "#6366f1",
      borderWidth: 1,
      padding: 12,
      displayColors: true,
    },
  },
};

const barChartOptions: ChartOptions<"bar"> = {
  responsive: true,
  maintainAspectRatio: false,
  indexAxis: "y" as const,
  plugins: {
    legend: {
      display: false,
    },
    tooltip: {
      backgroundColor: "rgba(17, 24, 39, 0.95)",
      titleColor: "#f3f4f6",
      bodyColor: "#d1d5db",
      borderColor: "#6366f1",
      borderWidth: 1,
      padding: 12,
    },
  },
  scales: {
    x: {
      grid: {
        color: "rgba(99, 102, 241, 0.1)",
      },
      ticks: {
        color: "#9ca3af",
      },
    },
    y: {
      grid: {
        display: false,
      },
      ticks: {
        color: "#e5e7eb",
        font: {
          size: 12,
        },
      },
    },
  },
};

const verticalBarOptions: ChartOptions<"bar"> = {
  ...barChartOptions,
  indexAxis: "x" as const,
  scales: {
    x: {
      grid: {
        display: false,
      },
      ticks: {
        color: "#e5e7eb",
        font: {
          size: 11,
        },
      },
    },
    y: {
      grid: {
        color: "rgba(99, 102, 241, 0.1)",
      },
      ticks: {
        color: "#9ca3af",
      },
    },
  },
};

function ChartCardSkeleton({ title }: { title: string }) {
  return (
    <Card className="border border-gray-700/50 bg-gradient-to-br from-slate-900/90 to-slate-800/90">
      <CardHeader>
        <CardTitle className="text-lg text-gray-300">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-64 flex items-center justify-center">
          <Skeleton className="h-48 w-48 rounded-full" />
        </div>
      </CardContent>
    </Card>
  );
}

export function PipelineCharts() {
  const { data: icpData, isLoading: icpLoading } = useSWR<ICPQueueResponse>(
    "/api/dashboard/icp-queue?days=7&limit=10",
    fetcher,
    { refreshInterval: 60000 }
  );

  const { data: lifecycleData, isLoading: lifecycleLoading } = useSWR<LifecycleResponse>(
    "/api/dashboard/lifecycle",
    fetcher,
    { refreshInterval: 300000 }
  );

  const { data: workQueueData, isLoading: workQueueLoading } = useSWR<WorkQueueResponse>(
    "/api/dashboard/workqueue?limit=100",
    fetcher,
    { refreshInterval: 60000 }
  );

  if (icpLoading || lifecycleLoading || workQueueLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <ChartCardSkeleton title="ICP Tier Distribution" />
        <ChartCardSkeleton title="Pipeline Funnel" />
        <ChartCardSkeleton title="Top States by Volume" />
        <ChartCardSkeleton title="Lead Score Distribution" />
      </div>
    );
  }

  if (!icpData || !lifecycleData || !workQueueData) {
    return (
      <Card className="border border-red-500/30 bg-gradient-to-br from-slate-900/90 to-slate-800/90">
        <CardContent className="p-6">
          <div className="text-center py-6 text-red-400">
            <AlertCircle className="h-8 w-8 mx-auto mb-2" />
            <p className="font-medium">Failed to load chart data</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // 1. ICP Tier Distribution (Doughnut) - Use real tier_breakdown data
  const tierBreakdown = icpData.tier_breakdown || { PLATINUM: 0, GOLD: 0, SILVER: 0, BRONZE: 0, UNSCORED: 0 };
  const tierDistribution = {
    labels: ["Platinum", "Gold", "Silver", "Bronze", "Unscored"],
    datasets: [
      {
        data: [
          tierBreakdown.PLATINUM || 0,
          tierBreakdown.GOLD || 0,
          tierBreakdown.SILVER || 0,
          tierBreakdown.BRONZE || 0,
          tierBreakdown.UNSCORED || 0,
        ],
        backgroundColor: [
          "rgba(34, 197, 94, 0.8)", // Green
          "rgba(59, 130, 246, 0.8)", // Blue
          "rgba(249, 115, 22, 0.8)", // Orange
          "rgba(168, 85, 247, 0.8)", // Purple
          "rgba(107, 114, 128, 0.8)", // Gray
        ],
        borderColor: [
          "rgba(34, 197, 94, 1)",
          "rgba(59, 130, 246, 1)",
          "rgba(249, 115, 22, 1)",
          "rgba(168, 85, 247, 1)",
          "rgba(107, 114, 128, 1)",
        ],
        borderWidth: 2,
      },
    ],
  };

  // 2. Pipeline Funnel (Vertical Bar)
  const funnelData = {
    labels: lifecycleData.stages.map((s) => s.stage),
    datasets: [
      {
        label: "Leads",
        data: lifecycleData.stages.map((s) => s.count),
        backgroundColor: [
          "rgba(59, 130, 246, 0.8)",
          "rgba(34, 197, 94, 0.8)",
          "rgba(249, 115, 22, 0.8)",
          "rgba(168, 85, 247, 0.8)",
          "rgba(16, 185, 129, 0.8)",
        ],
        borderColor: [
          "rgba(59, 130, 246, 1)",
          "rgba(34, 197, 94, 1)",
          "rgba(249, 115, 22, 1)",
          "rgba(168, 85, 247, 1)",
          "rgba(16, 185, 129, 1)",
        ],
        borderWidth: 2,
      },
    ],
  };

  // 3. Top States by Volume (Horizontal Bar) - Use real state_breakdown data
  const stateBreakdown = icpData.state_breakdown || {};
  const topStates = Object.entries(stateBreakdown)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  const statesData = {
    labels: topStates.map(([state]) => state),
    datasets: [
      {
        label: "Companies",
        data: topStates.map(([, count]) => count),
        backgroundColor: "rgba(99, 102, 241, 0.8)",
        borderColor: "rgba(99, 102, 241, 1)",
        borderWidth: 2,
      },
    ],
  };

  // 4. Lead Score Distribution (Histogram) - Use tasks from workQueueData
  const tasks = workQueueData.tasks || [];
  const scoreRanges = [
    { label: "100+", min: 100, max: Infinity },
    { label: "80-99", min: 80, max: 99 },
    { label: "60-79", min: 60, max: 79 },
    { label: "40-59", min: 40, max: 59 },
    { label: "20-39", min: 20, max: 39 },
  ];

  const scoreCounts = scoreRanges.map(
    (range) =>
      tasks.filter(
        (task) => task.lead_score >= range.min && task.lead_score <= range.max
      ).length
  );

  const scoreDistribution = {
    labels: scoreRanges.map((r) => r.label),
    datasets: [
      {
        label: "Leads",
        data: scoreCounts,
        backgroundColor: [
          "rgba(16, 185, 129, 0.8)",
          "rgba(34, 197, 94, 0.8)",
          "rgba(59, 130, 246, 0.8)",
          "rgba(249, 115, 22, 0.8)",
          "rgba(239, 68, 68, 0.8)",
        ],
        borderColor: [
          "rgba(16, 185, 129, 1)",
          "rgba(34, 197, 94, 1)",
          "rgba(59, 130, 246, 1)",
          "rgba(249, 115, 22, 1)",
          "rgba(239, 68, 68, 1)",
        ],
        borderWidth: 2,
      },
    ],
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* ICP Tier Distribution */}
      <Card className="border border-purple-500/30 bg-gradient-to-br from-slate-900/90 to-purple-900/20">
        <CardHeader>
          <CardTitle className="text-lg text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-400">
            ICP Tier Distribution
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <Doughnut data={tierDistribution} options={chartOptions} />
          </div>
        </CardContent>
      </Card>

      {/* Pipeline Funnel */}
      <Card className="border border-blue-500/30 bg-gradient-to-br from-slate-900/90 to-blue-900/20">
        <CardHeader>
          <CardTitle className="text-lg text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400">
            Pipeline Funnel
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <Bar data={funnelData} options={verticalBarOptions} />
          </div>
        </CardContent>
      </Card>

      {/* Top States by Volume */}
      <Card className="border border-orange-500/30 bg-gradient-to-br from-slate-900/90 to-orange-900/20">
        <CardHeader>
          <CardTitle className="text-lg text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-amber-400">
            Top States by Volume
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <Bar data={statesData} options={barChartOptions} />
          </div>
        </CardContent>
      </Card>

      {/* Lead Score Distribution */}
      <Card className="border border-green-500/30 bg-gradient-to-br from-slate-900/90 to-green-900/20">
        <CardHeader>
          <CardTitle className="text-lg text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-emerald-400">
            Lead Score Distribution
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <Bar data={scoreDistribution} options={verticalBarOptions} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
