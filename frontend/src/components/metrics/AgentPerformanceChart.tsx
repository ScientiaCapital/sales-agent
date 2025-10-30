import React, { useMemo } from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions,
} from 'chart.js';
import type { AgentMetricResponse } from '../../types';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface AgentPerformanceChartProps {
  data: AgentMetricResponse[];
  isLoading: boolean;
  className?: string;
}

/**
 * AgentPerformanceChart Component
 *
 * Displays multi-line chart of agent latency over time, grouped by agent type
 */
export const AgentPerformanceChart: React.FC<AgentPerformanceChartProps> = ({
  data,
  isLoading,
  className = '',
}) => {
  const chartData = useMemo(() => {
    if (!data || data.length === 0) {
      return null;
    }

    // Group data by agent_type
    const agentTypes = Array.from(new Set(data.map((d) => d.agent_type)));

    // Extract unique dates and sort them
    const dates = Array.from(
      new Set(
        data.map((d) => {
          const date = new Date(d.date);
          return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
          });
        })
      )
    );

    // Color palette for different agent types
    const colors = [
      { border: 'rgb(59, 130, 246)', background: 'rgba(59, 130, 246, 0.1)' }, // Blue
      { border: 'rgb(16, 185, 129)', background: 'rgba(16, 185, 129, 0.1)' }, // Green
      { border: 'rgb(249, 115, 22)', background: 'rgba(249, 115, 22, 0.1)' }, // Orange
      { border: 'rgb(139, 92, 246)', background: 'rgba(139, 92, 246, 0.1)' }, // Purple
      { border: 'rgb(236, 72, 153)', background: 'rgba(236, 72, 153, 0.1)' }, // Pink
    ];

    // Create datasets for each agent type
    const datasets = agentTypes.map((agentType, index) => {
      const agentData = data.filter((d) => d.agent_type === agentType);
      const latencyByDate = agentData.map((d) => ({
        date: new Date(d.date).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
        }),
        latency: d.avg_latency_ms,
      }));

      // Map to dates array to ensure consistent x-axis
      const latencyValues = dates.map((date) => {
        const entry = latencyByDate.find((l) => l.date === date);
        return entry ? entry.latency : null;
      });

      const color = colors[index % colors.length];

      return {
        label: agentType.charAt(0).toUpperCase() + agentType.slice(1),
        data: latencyValues,
        borderColor: color.border,
        backgroundColor: color.background,
        borderWidth: 2,
        tension: 0.4,
        pointRadius: 4,
        pointHoverRadius: 6,
        spanGaps: true, // Connect points even if there are null values
      };
    });

    return {
      labels: dates,
      datasets,
    };
  }, [data]);

  const options: ChartOptions<'line'> = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top' as const,
          labels: {
            usePointStyle: true,
            padding: 20,
            font: {
              size: 12,
              family: "'Inter', sans-serif",
            },
          },
        },
        title: {
          display: true,
          text: 'Agent Performance - Average Latency Over Time',
          font: {
            size: 16,
            weight: 'bold',
            family: "'Inter', sans-serif",
          },
          padding: {
            bottom: 20,
          },
        },
        tooltip: {
          mode: 'index' as const,
          intersect: false,
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          titleFont: {
            size: 14,
            family: "'Inter', sans-serif",
          },
          bodyFont: {
            size: 12,
            family: "'Inter', sans-serif",
          },
          padding: 12,
          callbacks: {
            label: (context) => {
              const label = context.dataset.label || '';
              const value = context.parsed.y;
              return `${label}: ${Math.round(value)}ms`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: {
            display: false,
          },
          ticks: {
            font: {
              size: 11,
              family: "'Inter', sans-serif",
            },
          },
        },
        y: {
          beginAtZero: true,
          grid: {
            color: 'rgba(0, 0, 0, 0.05)',
          },
          ticks: {
            font: {
              size: 11,
              family: "'Inter', sans-serif",
            },
            callback: (value) => `${value}ms`,
          },
          title: {
            display: true,
            text: 'Average Latency (ms)',
            font: {
              size: 12,
              weight: 'bold',
              family: "'Inter', sans-serif",
            },
          },
        },
      },
      interaction: {
        mode: 'nearest' as const,
        axis: 'x' as const,
        intersect: false,
      },
    }),
    []
  );

  if (isLoading) {
    return (
      <div className={`bg-white rounded-lg shadow p-6 border border-gray-200 ${className}`}>
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="h-64 bg-gray-100 rounded"></div>
        </div>
      </div>
    );
  }

  if (!chartData || chartData.datasets.length === 0) {
    return (
      <div className={`bg-white rounded-lg shadow p-6 border border-gray-200 ${className}`}>
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Agent Performance - Average Latency Over Time
        </h3>
        <div className="h-64 flex items-center justify-center text-gray-500">
          <p>No performance data available for the selected time range</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-white rounded-lg shadow p-6 border border-gray-200 ${className}`}>
      <div className="h-80">
        <Line data={chartData} options={options} />
      </div>
    </div>
  );
};
