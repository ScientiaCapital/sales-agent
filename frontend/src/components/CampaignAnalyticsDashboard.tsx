/**
 * Campaign Analytics Dashboard Component
 *
 * Comprehensive A/B testing analytics with charts and performance metrics
 */

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import type { ChartOptions } from 'chart.js';
import { Bar, Line } from 'react-chartjs-2';
import type { AnalyticsResponse, TimelineDataPoint } from '../types';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend
);

interface CampaignAnalyticsDashboardProps {
  analytics: AnalyticsResponse;
  timelineData?: TimelineDataPoint[];
}

export function CampaignAnalyticsDashboard({
  analytics,
  timelineData,
}: CampaignAnalyticsDashboardProps) {
  const { campaign, metrics, cost, ab_testing, top_performing_messages } = analytics;

  // Metrics cards data
  const metricCards = [
    {
      label: 'Messages Sent',
      value: campaign.total_sent.toLocaleString(),
      subtext: `of ${campaign.total_messages.toLocaleString()} total`,
      color: 'bg-blue-100 text-blue-800',
      icon: (
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      ),
    },
    {
      label: 'Delivery Rate',
      value: `${metrics.delivery_rate.toFixed(1)}%`,
      subtext: `${campaign.total_delivered.toLocaleString()} delivered`,
      color: 'bg-green-100 text-green-800',
      icon: (
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      ),
    },
    {
      label: 'Open Rate',
      value: `${metrics.open_rate.toFixed(1)}%`,
      subtext: `${campaign.total_opened.toLocaleString()} opens`,
      color: 'bg-purple-100 text-purple-800',
      icon: (
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
      ),
    },
    {
      label: 'Click Rate',
      value: `${metrics.click_rate.toFixed(1)}%`,
      subtext: `${campaign.total_clicked.toLocaleString()} clicks`,
      color: 'bg-yellow-100 text-yellow-800',
      icon: (
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
        </svg>
      ),
    },
    {
      label: 'Reply Rate',
      value: `${metrics.reply_rate.toFixed(1)}%`,
      subtext: `${campaign.total_replied.toLocaleString()} replies`,
      color: 'bg-indigo-100 text-indigo-800',
      icon: (
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
        </svg>
      ),
    },
    {
      label: 'Total Cost',
      value: `$${cost.total.toFixed(2)}`,
      subtext: `$${cost.per_message.toFixed(4)} per message`,
      color: 'bg-red-100 text-red-800',
      icon: (
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
  ];

  // A/B Testing Chart Data
  const variantChartData = {
    labels: ab_testing.variants.map((v) => `Variant ${v.variant_number}: ${v.tone}`),
    datasets: [
      {
        label: 'Opens',
        data: ab_testing.variants.map((v) => v.times_opened),
        backgroundColor: 'rgba(59, 130, 246, 0.5)',
        borderColor: 'rgb(59, 130, 246)',
        borderWidth: 1,
      },
      {
        label: 'Clicks',
        data: ab_testing.variants.map((v) => v.times_clicked),
        backgroundColor: 'rgba(234, 179, 8, 0.5)',
        borderColor: 'rgb(234, 179, 8)',
        borderWidth: 1,
      },
      {
        label: 'Replies',
        data: ab_testing.variants.map((v) => v.times_replied),
        backgroundColor: 'rgba(34, 197, 94, 0.5)',
        borderColor: 'rgb(34, 197, 94)',
        borderWidth: 1,
      },
    ],
  };

  const variantChartOptions: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: 'A/B Testing: Variant Performance Comparison',
        font: {
          size: 16,
          weight: 'bold',
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: {
          precision: 0,
        },
      },
    },
  };

  // Timeline Chart Data (if available)
  const timelineChartData = timelineData
    ? {
        labels: timelineData.map((d) => new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })),
        datasets: [
          {
            label: 'Sent',
            data: timelineData.map((d) => d.sent),
            borderColor: 'rgb(59, 130, 246)',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            tension: 0.4,
          },
          {
            label: 'Opened',
            data: timelineData.map((d) => d.opened),
            borderColor: 'rgb(168, 85, 247)',
            backgroundColor: 'rgba(168, 85, 247, 0.1)',
            tension: 0.4,
          },
          {
            label: 'Clicked',
            data: timelineData.map((d) => d.clicked),
            borderColor: 'rgb(234, 179, 8)',
            backgroundColor: 'rgba(234, 179, 8, 0.1)',
            tension: 0.4,
          },
          {
            label: 'Replied',
            data: timelineData.map((d) => d.replied),
            borderColor: 'rgb(34, 197, 94)',
            backgroundColor: 'rgba(34, 197, 94, 0.1)',
            tension: 0.4,
          },
        ],
      }
    : null;

  const timelineChartOptions: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: 'Campaign Performance Over Time',
        font: {
          size: 16,
          weight: 'bold',
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: {
          precision: 0,
        },
      },
    },
  };

  return (
    <div className="space-y-6">
      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {metricCards.map((metric, index) => (
          <div key={index} className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <div className={`p-3 rounded-lg ${metric.color}`}>{metric.icon}</div>
              {ab_testing.winner === index && (
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-bold bg-yellow-100 text-yellow-800">
                  Winner
                </span>
              )}
            </div>
            <h3 className="text-sm font-medium text-gray-500 mb-1">{metric.label}</h3>
            <p className="text-3xl font-bold text-gray-900 mb-1">{metric.value}</p>
            <p className="text-sm text-gray-600">{metric.subtext}</p>
          </div>
        ))}
      </div>

      {/* A/B Testing Results */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-gray-900">A/B Testing Results</h3>
          {ab_testing.statistical_significance && (
            <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
              Statistically Significant
            </span>
          )}
        </div>

        {/* Variant Performance Chart */}
        <div className="h-80 mb-6">
          <Bar data={variantChartData} options={variantChartOptions} />
        </div>

        {/* Variant Metrics Table */}
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Variant
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Sent
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Open Rate
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Click Rate
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Reply Rate
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {ab_testing.variants.map((variant) => (
                <tr
                  key={variant.variant_number}
                  className={
                    ab_testing.winner === variant.variant_number ? 'bg-yellow-50' : ''
                  }
                >
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="text-sm font-medium text-gray-900">
                        Variant {variant.variant_number}
                      </div>
                      <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800 capitalize">
                        {variant.tone}
                      </span>
                      {ab_testing.winner === variant.variant_number && (
                        <svg
                          className="ml-2 h-5 w-5 text-yellow-400"
                          fill="currentColor"
                          viewBox="0 0 20 20"
                        >
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {variant.times_selected.toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {variant.open_rate.toFixed(1)}%
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {variant.click_rate.toFixed(1)}%
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="text-sm font-semibold text-green-600">
                      {variant.reply_rate.toFixed(1)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Timeline Chart */}
      {timelineChartData && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-bold text-gray-900 mb-4">Performance Timeline</h3>
          <div className="h-80">
            <Line data={timelineChartData} options={timelineChartOptions} />
          </div>
        </div>
      )}

      {/* Top Performing Messages */}
      {top_performing_messages.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-bold text-gray-900 mb-4">Top Performing Messages</h3>
          <div className="space-y-4">
            {top_performing_messages.map((message, index) => (
              <div
                key={message.message_id}
                className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <span className="flex items-center justify-center w-6 h-6 rounded-full bg-indigo-100 text-indigo-800 text-xs font-bold">
                      {index + 1}
                    </span>
                    <span className="text-sm font-semibold text-gray-900">
                      {message.lead_name}
                    </span>
                    <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800 capitalize">
                      {message.tone}
                    </span>
                  </div>
                  <span className="text-sm font-bold text-green-600">
                    {message.reply_rate.toFixed(1)}% reply rate
                  </span>
                </div>
                {message.subject && (
                  <p className="text-sm font-medium text-gray-700 mb-1">
                    Subject: {message.subject}
                  </p>
                )}
                <p className="text-sm text-gray-600 line-clamp-2">{message.preview}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
