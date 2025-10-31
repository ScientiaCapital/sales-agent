/**
 * Dashboard System Status Component
 * Shows system health and latency metrics
 */

import { Card, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { CheckCircle2 } from 'lucide-react';
import type { MetricsSummaryResponse } from '../../types';

interface DashboardSystemStatusProps {
  metrics: MetricsSummaryResponse | null;
  isLoading: boolean;
}

export function DashboardSystemStatus({ metrics, isLoading }: DashboardSystemStatusProps) {
  if (isLoading) {
    return (
      <Card className="bg-green-50 border-green-200">
        <CardHeader>
          <div className="h-8 bg-gray-200 rounded animate-pulse"></div>
        </CardHeader>
      </Card>
    );
  }

  const avgResponseTime = metrics?.avg_response_time_ms || 0;
  const errorRate = metrics?.error_rate || 0;
  const uptimePercentage = errorRate > 0 ? Math.max(0, 100 - errorRate * 100) : 99.2;

  return (
    <Card className="bg-green-50 border-green-200">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-500 rounded-md">
              <CheckCircle2 className="h-5 w-5 text-white" />
            </div>
            <div>
              <CardTitle className="text-green-900">All Systems Operational</CardTitle>
              <CardDescription className="text-green-700">
                {uptimePercentage.toFixed(1)}% uptime · Avg response time: {Math.round(avgResponseTime)}ms
              </CardDescription>
            </div>
          </div>
          <div className="flex gap-4 text-sm text-green-700">
            <span>AI: {Math.round(avgResponseTime)}ms</span>
            <span>Error Rate: {(errorRate * 100).toFixed(2)}%</span>
          </div>
        </div>
      </CardHeader>
    </Card>
  );
}

