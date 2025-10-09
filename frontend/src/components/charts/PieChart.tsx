import React from 'react';
import { Pie } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
} from 'chart.js';
import type { ChartOptions } from 'chart.js';

// Register Chart.js components
ChartJS.register(ArcElement, Tooltip, Legend);

interface PieChartProps {
  data: {
    provider: string;
    total_cost_usd: number;
  }[];
  title: string;
}

const PROVIDER_COLORS: Record<string, string> = {
  cerebras: '#3B82F6',      // Blue
  openrouter: '#10B981',    // Green
  ollama: '#F59E0B',        // Amber
  anthropic: '#8B5CF6',     // Purple
  deepseek: '#EF4444',      // Red
  default: '#6B7280',       // Gray
};

export const PieChart: React.FC<PieChartProps> = ({ data, title }) => {
  if (!data || data.length === 0) {
    return (
      <div className="chart-container p-4 bg-white rounded-lg shadow">
        <h3 className="text-lg font-semibold mb-4">{title}</h3>
        <p className="text-gray-500 text-center py-8">No data available</p>
      </div>
    );
  }

  const chartData = {
    labels: data.map((p) => p.provider),
    datasets: [
      {
        data: data.map((p) => p.total_cost_usd),
        backgroundColor: data.map((p) => PROVIDER_COLORS[p.provider] || PROVIDER_COLORS.default),
        borderWidth: 2,
        borderColor: '#ffffff',
      },
    ],
  };

  const options: ChartOptions<'pie'> = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          padding: 15,
          usePointStyle: true,
        },
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            const label = context.label || '';
            const value = context.parsed || 0;
            const total = context.dataset.data.reduce((a: number, b: number) => a + b, 0);
            const percentage = ((value / total) * 100).toFixed(1);
            return `${label}: $${value.toFixed(6)} (${percentage}%)`;
          },
        },
      },
    },
  };

  return (
    <div className="chart-container p-4 bg-white rounded-lg shadow">
      <h3 className="text-lg font-semibold mb-4">{title}</h3>
      <div className="relative h-64">
        <Pie data={chartData} options={options} />
      </div>
    </div>
  );
};
