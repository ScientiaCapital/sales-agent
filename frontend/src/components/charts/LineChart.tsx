import React from 'react';
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
} from 'chart.js';
import type { ChartOptions } from 'chart.js';

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

interface LineChartProps {
  data: {
    timestamp: string;
    total_cost_usd: number;
    provider_costs: Record<string, number>;
  }[];
  title: string;
}

const PROVIDER_COLORS: Record<string, string> = {
  cerebras: '#3B82F6',
  openrouter: '#10B981',
  ollama: '#F59E0B',
  anthropic: '#8B5CF6',
  deepseek: '#EF4444',
};

export const LineChart: React.FC<LineChartProps> = ({ data, title }) => {
  if (!data || data.length === 0) {
    return (
      <div className="chart-container p-4 bg-white rounded-lg shadow">
        <h3 className="text-lg font-semibold mb-4">{title}</h3>
        <p className="text-gray-500 text-center py-8">No data available</p>
      </div>
    );
  }

  // Extract providers from data
  const providers = new Set<string>();
  data.forEach((point) => {
    Object.keys(point.provider_costs).forEach((provider) => providers.add(provider));
  });

  const chartData = {
    labels: data.map((d) => {
      const date = new Date(d.timestamp);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }),
    datasets: Array.from(providers).map((provider) => ({
      label: provider.charAt(0).toUpperCase() + provider.slice(1),
      data: data.map((d) => d.provider_costs[provider] || 0),
      borderColor: PROVIDER_COLORS[provider] || '#6B7280',
      backgroundColor: PROVIDER_COLORS[provider] || '#6B7280',
      tension: 0.3,
      borderWidth: 2,
      pointRadius: 3,
      pointHoverRadius: 5,
    })),
  };

  const options: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: true,
    interaction: {
      mode: 'index',
      intersect: false,
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: {
          callback: (value) => `$${Number(value).toFixed(4)}`,
        },
      },
    },
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
            const label = context.dataset.label || '';
            const value = context.parsed.y;
            return `${label}: $${value.toFixed(6)}`;
          },
        },
      },
    },
  };

  return (
    <div className="chart-container p-4 bg-white rounded-lg shadow">
      <h3 className="text-lg font-semibold mb-4">{title}</h3>
      <div className="relative h-64">
        <Line data={chartData} options={options} />
      </div>
    </div>
  );
};
