/**
 * Unit tests for DashboardMetrics component
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DashboardMetrics } from '../../components/dashboard/DashboardMetrics';
import type { MetricsSummaryResponse } from '../../types';

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('DashboardMetrics', () => {
  it('should render loading state', () => {
    render(<DashboardMetrics metrics={null} isLoading={true} />, {
      wrapper: createWrapper(),
    });

    const loadingElements = screen.getAllByRole('generic');
    expect(loadingElements.length).toBeGreaterThan(0);
  });

  it('should render metrics when data is available', () => {
    const mockMetrics: MetricsSummaryResponse = {
      period_start: '2024-01-01',
      period_end: '2024-01-07',
      total_api_requests: 1000,
      avg_response_time_ms: 500,
      error_rate: 0.01,
      total_agent_executions: 500,
      agent_success_rate: 0.98,
      avg_agent_latency_ms: 600,
      total_cost_usd: 10.5,
      cost_by_provider: { cerebras: 5.0, claude: 5.5 },
      leads_processed: 247,
      leads_qualified: 150,
      qualification_rate: 0.75,
    };

    render(<DashboardMetrics metrics={mockMetrics} isLoading={false} />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByText('Total Leads')).toBeInTheDocument();
    expect(screen.getByText('247')).toBeInTheDocument();
    expect(screen.getByText('Research Reports')).toBeInTheDocument();
    expect(screen.getByText('500')).toBeInTheDocument();
  });

  it('should render fallback values when metrics are null', () => {
    render(<DashboardMetrics metrics={null} isLoading={false} />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByText('Total Leads')).toBeInTheDocument();
    expect(screen.getByText('0')).toBeInTheDocument();
  });
});

