import React, { useState, useEffect, useCallback } from 'react';
import { TimeRangeSelector, TimeRange } from '../components/metrics/TimeRangeSelector';
import { RefreshIndicator } from '../components/metrics/RefreshIndicator';
import { MetricsSummaryCards } from '../components/metrics/MetricsSummaryCards';
import { AgentPerformanceChart } from '../components/metrics/AgentPerformanceChart';
import { apiClient } from '../services/api';
import type {
  MetricsSummaryResponse,
  AgentMetricResponse,
} from '../types';

/**
 * Calculate start and end dates based on time range selection
 */
const getDateRangeFromTimeRange = (
  range: TimeRange
): { startDate: string; endDate: string } => {
  const endDate = new Date();
  const startDate = new Date();

  switch (range) {
    case '24h':
      startDate.setHours(startDate.getHours() - 24);
      break;
    case '7d':
      startDate.setDate(startDate.getDate() - 7);
      break;
    case '30d':
      startDate.setDate(startDate.getDate() - 30);
      break;
    case '90d':
      startDate.setDate(startDate.getDate() - 90);
      break;
  }

  return {
    startDate: startDate.toISOString(),
    endDate: endDate.toISOString(),
  };
};

/**
 * PerformanceDashboard Page Component
 *
 * Main dashboard for performance metrics with:
 * - Time range filtering (24h, 7d, 30d, 90d)
 * - Auto-refresh every 30 seconds
 * - Manual refresh capability
 * - Real-time metrics summary
 * - Agent performance charts
 */
export const PerformanceDashboard: React.FC = () => {
  // State management
  const [timeRange, setTimeRange] = useState<TimeRange>('7d');
  const [summaryData, setSummaryData] = useState<MetricsSummaryResponse | null>(null);
  const [agentMetrics, setAgentMetrics] = useState<AgentMetricResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  /**
   * Fetch all metrics data
   */
  const fetchMetricsData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const { startDate, endDate } = getDateRangeFromTimeRange(timeRange);

      // Fetch summary and agent metrics in parallel
      const [summary, agents] = await Promise.all([
        apiClient.getMetricsSummary(startDate, endDate),
        apiClient.getAgentMetrics(startDate, endDate, undefined, 100),
      ]);

      setSummaryData(summary);
      setAgentMetrics(agents);
      setLastRefresh(new Date());
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to fetch metrics data';
      setError(errorMessage);
      console.error('Error fetching metrics:', err);
    } finally {
      setIsLoading(false);
    }
  }, [timeRange]);

  /**
   * Initial data fetch on mount
   */
  useEffect(() => {
    fetchMetricsData();
  }, [fetchMetricsData]);

  /**
   * Auto-refresh every 30 seconds
   */
  useEffect(() => {
    const interval = setInterval(() => {
      fetchMetricsData();
    }, 30000); // 30 seconds

    return () => clearInterval(interval);
  }, [fetchMetricsData]);

  /**
   * Handle time range change
   */
  const handleTimeRangeChange = useCallback((newRange: TimeRange) => {
    setTimeRange(newRange);
  }, []);

  /**
   * Handle manual refresh
   */
  const handleManualRefresh = useCallback(() => {
    if (!isLoading) {
      fetchMetricsData();
    }
  }, [isLoading, fetchMetricsData]);

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Performance Dashboard
        </h1>
        <p className="text-gray-600">
          Monitor agent performance, costs, and system metrics in real-time
        </p>
      </div>

      {/* Controls */}
      <div className="max-w-7xl mx-auto mb-6">
        <div className="bg-white rounded-lg shadow p-4 border border-gray-200">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            {/* Time Range Selector */}
            <TimeRangeSelector
              selectedRange={timeRange}
              onRangeChange={handleTimeRangeChange}
            />

            {/* Refresh Indicator */}
            <RefreshIndicator
              isRefreshing={isLoading}
              lastRefresh={lastRefresh}
              onManualRefresh={handleManualRefresh}
              autoRefreshInterval={30}
            />
          </div>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="max-w-7xl mx-auto mb-6">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <svg
                className="w-5 h-5 text-red-600 mt-0.5"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
              <div>
                <h3 className="text-sm font-medium text-red-800">
                  Error loading metrics
                </h3>
                <p className="text-sm text-red-700 mt-1">{error}</p>
                <button
                  onClick={handleManualRefresh}
                  className="mt-2 text-sm text-red-600 hover:text-red-800 font-medium"
                >
                  Try again
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Metrics Summary Cards */}
        <MetricsSummaryCards
          data={summaryData}
          isLoading={isLoading && !summaryData}
        />

        {/* Agent Performance Chart */}
        <AgentPerformanceChart
          data={agentMetrics}
          isLoading={isLoading && agentMetrics.length === 0}
        />

        {/* Additional Charts Section - Placeholder for future expansion */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Cost Distribution Chart */}
          {summaryData && summaryData.cost_by_provider && (
            <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Cost Distribution by Provider
              </h3>
              <div className="space-y-3">
                {Object.entries(summaryData.cost_by_provider).map(
                  ([provider, cost]) => {
                    const percentage =
                      (cost / summaryData.total_cost_usd) * 100;
                    return (
                      <div key={provider}>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="font-medium text-gray-700 capitalize">
                            {provider}
                          </span>
                          <span className="text-gray-600">
                            ${cost.toFixed(2)} ({percentage.toFixed(1)}%)
                          </span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full"
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                      </div>
                    );
                  }
                )}
              </div>
            </div>
          )}

          {/* Quick Stats */}
          <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Quick Statistics
            </h3>
            {summaryData && (
              <div className="space-y-3">
                <div className="flex justify-between items-center py-2 border-b border-gray-100">
                  <span className="text-sm text-gray-600">
                    Total API Requests
                  </span>
                  <span className="text-sm font-semibold text-gray-900">
                    {summaryData.total_api_requests.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-gray-100">
                  <span className="text-sm text-gray-600">
                    Avg Response Time
                  </span>
                  <span className="text-sm font-semibold text-gray-900">
                    {Math.round(summaryData.avg_response_time_ms)}ms
                  </span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-gray-100">
                  <span className="text-sm text-gray-600">Leads Processed</span>
                  <span className="text-sm font-semibold text-gray-900">
                    {summaryData.leads_processed.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between items-center py-2">
                  <span className="text-sm text-gray-600">
                    Qualification Rate
                  </span>
                  <span className="text-sm font-semibold text-gray-900">
                    {(summaryData.qualification_rate * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            )}
            {isLoading && !summaryData && (
              <div className="animate-pulse space-y-3">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="h-8 bg-gray-100 rounded"></div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
