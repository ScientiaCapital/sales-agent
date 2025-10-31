import React, { useState, useEffect } from 'react';
import { PieChart } from '../components/charts/PieChart';
import { LineChart } from '../components/charts/LineChart';
import { BudgetProgressBar } from '../components/BudgetProgressBar';

interface CostSummary {
  total_cost_usd: number;
  total_requests: number;
  avg_cost_per_request: number;
  provider_breakdown: Array<{
    provider: string;
    total_cost_usd: number;
    total_requests: number;
    percentage: number;
  }>;
  cost_trend: Array<{
    date: string;
    cost_usd: number;
    requests: number;
  }>;
}

interface BudgetStatus {
  daily_budget_usd: number;
  daily_spend_usd: number;
  daily_utilization_percent: number;
  monthly_budget_usd: number;
  monthly_spend_usd: number;
  monthly_utilization_percent: number;
  threshold_status: 'OK' | 'WARNING' | 'CRITICAL' | 'BLOCKED';
  current_strategy: string;
}

interface TimeSeriesPoint {
  timestamp: string;
  total_cost_usd: number;
  total_requests: number;
  avg_latency_ms: number;
  provider_costs: Record<string, number>;
}

interface OptimizerStats {
  overall: {
    total_cost: number;
    total_requests: number;
    avg_cost_per_request: number;
  };
  by_provider: Record<string, any>;
  recent_requests: Array<any>;
}

interface CacheStats {
  hit_rate: number;
  miss_rate: number;
  total_savings_usd: number;
  by_type: Record<string, any>;
}

interface AgentStats {
  agent_name: string;
  total_cost: number;
  total_calls: number;
  avg_latency_ms: number;
  provider: string;
}

interface MetricCardProps {
  title: string;
  value: string;
  change?: number;
  icon: string;
  subtitle?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ title, value, change, icon, subtitle }) => {
  const isPositive = change && change > 0;
  const changeColor = isPositive ? 'text-red-600' : 'text-green-600';

  return (
    <div className="bg-white p-6 rounded-lg shadow hover:shadow-lg transition-shadow">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-2xl font-bold text-gray-900 mt-2">{value}</p>
          {subtitle && (
            <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
          )}
          {change !== undefined && (
            <p className={`text-sm mt-1 ${changeColor}`}>
              {isPositive ? '↑' : '↓'} {Math.abs(change).toFixed(1)}% vs yesterday
            </p>
          )}
        </div>
        <div className="text-4xl">{icon}</div>
      </div>
    </div>
  );
};

const ExportButton: React.FC<{ onExport: (format: 'csv' | 'json') => void }> = ({ onExport }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded-lg shadow transition-colors"
      >
        Export Data
      </button>
      {isOpen && (
        <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 z-10">
          <button
            onClick={() => {
              onExport('csv');
              setIsOpen(false);
            }}
            className="block w-full text-left px-4 py-2 hover:bg-gray-100 rounded-t-lg"
          >
            Export as CSV
          </button>
          <button
            onClick={() => {
              onExport('json');
              setIsOpen(false);
            }}
            className="block w-full text-left px-4 py-2 hover:bg-gray-100 rounded-b-lg"
          >
            Export as JSON
          </button>
        </div>
      )}
    </div>
  );
};

export default function CostDashboard() {
  const [summary, setSummary] = useState<CostSummary | null>(null);
  const [budgetStatus, setBudgetStatus] = useState<BudgetStatus | null>(null);
  const [timeseries, setTimeseries] = useState<TimeSeriesPoint[]>([]);
  const [optimizerStats, setOptimizerStats] = useState<OptimizerStats | null>(null);
  const [cacheStats, setCacheStats] = useState<CacheStats | null>(null);
  const [agentStats, setAgentStats] = useState<AgentStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCostData = async () => {
    try {
      setError(null);
      const now = new Date();
      const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);

      // Fetch all data in parallel
      const [
        summaryRes, 
        budgetRes, 
        timeseriesRes,
        optimizerStatsRes,
        cacheStatsRes,
        agentStatsRes
      ] = await Promise.all([
        fetch('/api/v1/costs/summary?days=7'),
        fetch('/api/v1/costs/budget/status'),
        fetch(
          `/api/v1/costs/usage?start_date=${sevenDaysAgo.toISOString()}&end_date=${now.toISOString()}&interval=daily`
        ),
        fetch('/api/v1/costs/optimizer/stats').catch(() => null), // Graceful failure
        fetch('/api/v1/costs/optimizer/cache-stats').catch(() => null),
        fetch('/api/v1/costs/optimizer/agent-stats').catch(() => null)
      ]);

      if (!summaryRes.ok || !budgetRes.ok || !timeseriesRes.ok) {
        throw new Error('Failed to fetch core cost data');
      }

      const [summaryData, budgetData, timeseriesData] = await Promise.all([
        summaryRes.json(),
        budgetRes.json(),
        timeseriesRes.json(),
      ]);

      setSummary(summaryData);
      setBudgetStatus(budgetData);
      setTimeseries(timeseriesData.data_points || []);

      // Handle optimizer stats (optional)
      if (optimizerStatsRes && optimizerStatsRes.ok) {
        const optimizerData = await optimizerStatsRes.json();
        setOptimizerStats(optimizerData);
      }

      // Handle cache stats (optional)
      if (cacheStatsRes && cacheStatsRes.ok) {
        const cacheData = await cacheStatsRes.json();
        setCacheStats(cacheData);
      }

      // Handle agent stats (optional)
      if (agentStatsRes && agentStatsRes.ok) {
        const agentData = await agentStatsRes.json();
        // Extract agent stats from overall stats
        if (agentData.by_agent) {
          const agents = Object.entries(agentData.by_agent).map(([name, stats]: [string, any]) => ({
            agent_name: name,
            total_cost: stats.total_cost || 0,
            total_calls: stats.total_requests || 0,
            avg_latency_ms: stats.avg_latency_ms || 0,
            provider: stats.primary_provider || 'unknown'
          }));
          setAgentStats(agents);
        }
      }
    } catch (err) {
      console.error('Failed to fetch cost data:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Initial fetch
    fetchCostData();

    // Refresh every 30 seconds
    const interval = setInterval(fetchCostData, 30000);

    return () => clearInterval(interval);
  }, []);

  const downloadCostReport = async (format: 'csv' | 'json') => {
    try {
      const now = new Date();
      const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);

      const response = await fetch(
        `/api/v1/costs/export?format=${format}&start_date=${thirtyDaysAgo.toISOString()}&end_date=${now.toISOString()}`
      );

      if (!response.ok) {
        throw new Error('Export failed');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `cost-report-${new Date().toISOString().split('T')[0]}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export cost report:', err);
      alert('Failed to export cost report. Please try again.');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading cost data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md">
          <h2 className="text-lg font-semibold text-red-900 mb-2">Error Loading Dashboard</h2>
          <p className="text-red-700">{error}</p>
          <button
            onClick={() => {
              setLoading(true);
              fetchCostData();
            }}
            className="mt-4 bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Cost Dashboard</h1>
            <p className="text-gray-600 mt-1">Real-time cost tracking and budget monitoring</p>
          </div>
          <ExportButton onExport={downloadCostReport} />
        </div>

        {/* Metric Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          <MetricCard
            title="7-Day Total Cost"
            value={`$${summary?.total_cost_usd.toFixed(4) || '0.00'}`}
            icon="💰"
          />
          <MetricCard
            title="Total Requests"
            value={summary?.total_requests.toLocaleString() || '0'}
            icon="📊"
          />
          <MetricCard
            title="Avg Cost/Request"
            value={`$${summary?.avg_cost_per_request.toFixed(6) || '0.00'}`}
            icon="📈"
          />
        </div>

        {/* Budget Utilization */}
        {budgetStatus && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <BudgetProgressBar
              label="Daily Budget"
              utilization={budgetStatus.daily_utilization_percent}
              status={budgetStatus.threshold_status}
              budget={budgetStatus.daily_budget_usd}
              spent={budgetStatus.daily_spend_usd}
            />
            <BudgetProgressBar
              label="Monthly Budget"
              utilization={budgetStatus.monthly_utilization_percent}
              status={budgetStatus.threshold_status}
              budget={budgetStatus.monthly_budget_usd}
              spent={budgetStatus.monthly_spend_usd}
            />
          </div>
        )}

        {/* Cache Savings Section */}
        {cacheStats && (
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-lg p-6 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-green-900">💾 Cache Performance</h3>
                <p className="text-sm text-green-700 mt-1">Savings from LinkedIn & Qualification caching</p>
              </div>
              <div className="text-right">
                <p className="text-3xl font-bold text-green-900">${cacheStats.total_savings_usd.toFixed(4)}</p>
                <p className="text-sm text-green-700">Total Saved</p>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4 mt-4">
              <div>
                <p className="text-xs text-green-600 font-medium">Hit Rate</p>
                <p className="text-xl font-bold text-green-900">{(cacheStats.hit_rate * 100).toFixed(1)}%</p>
              </div>
              <div>
                <p className="text-xs text-green-600 font-medium">Miss Rate</p>
                <p className="text-xl font-bold text-green-900">{(cacheStats.miss_rate * 100).toFixed(1)}%</p>
              </div>
              <div>
                <p className="text-xs text-green-600 font-medium">ROI</p>
                <p className="text-xl font-bold text-green-900">
                  {cacheStats.total_savings_usd > 0 ? '30-50%' : 'N/A'}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Agent Performance Cards */}
        {agentStats.length > 0 && (
          <div className="mb-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">🤖 Agent Performance</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {agentStats.map((agent) => (
                <div key={agent.agent_name} className="bg-white p-4 rounded-lg shadow border-l-4 border-blue-500">
                  <p className="text-sm font-medium text-gray-600 capitalize">{agent.agent_name}</p>
                  <p className="text-lg font-bold text-gray-900 mt-1">${agent.total_cost.toFixed(6)}</p>
                  <div className="mt-2 space-y-1">
                    <p className="text-xs text-gray-600">
                      {agent.total_calls} calls • {agent.avg_latency_ms}ms avg
                    </p>
                    <p className="text-xs text-blue-600 font-medium">{agent.provider}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Real-time Optimizer Stats */}
        {optimizerStats && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <MetricCard
              title="Optimizer Total Cost"
              value={`$${optimizerStats.overall.total_cost.toFixed(6)}`}
              subtitle="From ai-cost-optimizer"
              icon="⚡"
            />
            <MetricCard
              title="Optimizer Requests"
              value={optimizerStats.overall.total_requests.toLocaleString()}
              subtitle="Tracked by optimizer"
              icon="📡"
            />
            <MetricCard
              title="Optimizer Avg Cost"
              value={`$${optimizerStats.overall.avg_cost_per_request.toFixed(8)}`}
              subtitle="Per request"
              icon="💎"
            />
          </div>
        )}

        {/* Charts */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <PieChart
            data={summary?.provider_breakdown || []}
            title="Cost by Provider"
          />
          <LineChart
            data={timeseries}
            title="7-Day Cost Trend"
          />
        </div>

        {/* Footer */}
        <div className="text-center text-sm text-gray-500 mt-8">
          Last updated: {new Date().toLocaleString()}
          <span className="mx-2">•</span>
          Auto-refreshes every 30 seconds
        </div>
      </div>
    </div>
  );
}
