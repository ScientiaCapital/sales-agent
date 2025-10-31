/**
 * Unit tests for API hooks
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useLeads, useLead, useQualifyLead, useMetricsSummary, useApiError } from '../../hooks/useApi';
import { apiClient } from '../../services/api';
import { APIClientError } from '../../services/api';

// Mock the API client
vi.mock('../../services/api', () => ({
  apiClient: {
    listLeads: vi.fn(),
    getLead: vi.fn(),
    qualifyLead: vi.fn(),
    getMetricsSummary: vi.fn(),
  },
}));

// Mock debug logger
vi.mock('../../lib/debug', () => ({
  logger: {
    apiCall: vi.fn(),
    info: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    warn: vi.fn(),
  },
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: ReactNode }) => {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
};

describe('useLeads', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch leads successfully', async () => {
    const mockLeads = [
      { id: 1, company_name: 'Test Corp', industry: 'SaaS', qualification_score: 85, created_at: '2024-01-01' },
      { id: 2, company_name: 'Another Corp', industry: 'Tech', qualification_score: 75, created_at: '2024-01-02' },
    ];

    vi.mocked(apiClient.listLeads).mockResolvedValue(mockLeads as any);

    const { result } = renderHook(() => useLeads(0, 10), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockLeads);
    expect(apiClient.listLeads).toHaveBeenCalledWith(0, 10);
  });

  it('should handle API errors', async () => {
    const error = new APIClientError('Not found', 404);
    vi.mocked(apiClient.listLeads).mockRejectedValue(error);

    const { result } = renderHook(() => useLeads(0, 10), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBe(error);
  });
});

describe('useLead', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch a single lead', async () => {
    const mockLead = {
      id: 1,
      company_name: 'Test Corp',
      industry: 'SaaS',
      qualification_score: 85,
      created_at: '2024-01-01',
      updated_at: '2024-01-01',
    };

    vi.mocked(apiClient.getLead).mockResolvedValue(mockLead as any);

    const { result } = renderHook(() => useLead(1), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockLead);
    expect(apiClient.getLead).toHaveBeenCalledWith(1);
  });

  it('should not fetch if leadId is null', () => {
    const { result } = renderHook(() => useLead(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.isFetching).toBe(false);
    expect(apiClient.getLead).not.toHaveBeenCalled();
  });
});

describe('useQualifyLead', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should qualify a lead successfully', async () => {
    const request = {
      company_name: 'Test Corp',
      industry: 'SaaS',
    };

    const response = {
      id: 1,
      company_name: 'Test Corp',
      industry: 'SaaS',
      qualification_score: 85,
      created_at: '2024-01-01',
      updated_at: '2024-01-01',
    };

    vi.mocked(apiClient.qualifyLead).mockResolvedValue(response as any);

    const { result } = renderHook(() => useQualifyLead(), {
      wrapper: createWrapper(),
    });

    result.current.mutate(request);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(response);
    expect(apiClient.qualifyLead).toHaveBeenCalledWith(request);
  });
});

describe('useMetricsSummary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch metrics successfully', async () => {
    const mockMetrics = {
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
      leads_processed: 200,
      leads_qualified: 150,
      qualification_rate: 0.75,
    };

    vi.mocked(apiClient.getMetricsSummary).mockResolvedValue(mockMetrics);

    const { result } = renderHook(() => useMetricsSummary(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockMetrics);
  });
});

describe('useApiError', () => {
  it('should handle APIClientError', () => {
    const error = new APIClientError('Not found', 404, 'Resource not found');
    const { message, statusCode, isNetworkError } = useApiError(error);

    expect(message).toBe('Not found');
    expect(statusCode).toBe(404);
    expect(isNetworkError).toBe(false);
  });

  it('should handle network errors', () => {
    const error = new APIClientError('Network error', 0);
    const { message, statusCode, isNetworkError } = useApiError(error);

    expect(message).toBe('Network error');
    expect(statusCode).toBe(0);
    expect(isNetworkError).toBe(true);
  });

  it('should handle generic Error', () => {
    const error = new Error('Something went wrong');
    const { message, isNetworkError } = useApiError(error);

    expect(message).toBe('Something went wrong');
    expect(isNetworkError).toBe(false);
  });

  it('should handle unknown errors', () => {
    const error = 'Unknown error';
    const { message, isNetworkError } = useApiError(error);

    expect(message).toBe('An unknown error occurred');
    expect(isNetworkError).toBe(false);
  });
});

