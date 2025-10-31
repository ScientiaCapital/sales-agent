/**
 * React Query hooks for API calls
 * Provides data fetching, caching, error handling, and loading states
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient, APIClientError } from '../services/api';
import { logger } from '../lib/debug';
import type {
  LeadQualificationRequest,
  LeadQualificationResponse,
  MetricsSummaryResponse,
  AgentMetricResponse,
  CampaignResponse,
} from '../types';

/**
 * Hook for fetching leads list
 */
export function useLeads(skip = 0, limit = 100) {
  return useQuery({
    queryKey: ['leads', skip, limit],
    queryFn: async () => {
      const start = performance.now();
      try {
        const result = await apiClient.listLeads(skip, limit);
        const duration = performance.now() - start;
        logger.apiCall('GET', `/api/v1/leads/?skip=${skip}&limit=${limit}`, duration);
        return result;
      } catch (error) {
        const duration = performance.now() - start;
        logger.apiCall('GET', `/api/v1/leads/`, duration, undefined, error as Error);
        throw error;
      }
    },
    staleTime: 30000, // 30 seconds
    retry: 2,
  });
}

/**
 * Hook for fetching a single lead
 */
export function useLead(leadId: number | null, enabled = true) {
  return useQuery({
    queryKey: ['lead', leadId],
    queryFn: async () => {
      if (!leadId) throw new Error('Lead ID is required');
      const start = performance.now();
      try {
        const result = await apiClient.getLead(leadId);
        const duration = performance.now() - start;
        logger.apiCall('GET', `/api/v1/leads/${leadId}`, duration);
        return result;
      } catch (error) {
        const duration = performance.now() - start;
        logger.apiCall('GET', `/api/v1/leads/${leadId}`, duration, undefined, error as Error);
        throw error;
      }
    },
    enabled: enabled && leadId !== null,
    staleTime: 60000, // 1 minute
  });
}

/**
 * Hook for qualifying a lead (mutation)
 */
export function useQualifyLead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: LeadQualificationRequest): Promise<LeadQualificationResponse> => {
      const start = performance.now();
      try {
        const result = await apiClient.qualifyLead(request);
        const duration = performance.now() - start;
        logger.apiCall('POST', '/api/v1/leads/qualify', duration);
        return result;
      } catch (error) {
        const duration = performance.now() - start;
        logger.apiCall('POST', '/api/v1/leads/qualify', duration, undefined, error as Error);
        throw error;
      }
    },
    onSuccess: () => {
      // Invalidate leads list to refetch
      queryClient.invalidateQueries({ queryKey: ['leads'] });
    },
  });
}

/**
 * Hook for fetching metrics summary (dashboard)
 */
export function useMetricsSummary(startDate?: string, endDate?: string) {
  return useQuery({
    queryKey: ['metrics', 'summary', startDate, endDate],
    queryFn: async (): Promise<MetricsSummaryResponse> => {
      const start = performance.now();
      try {
        const result = await apiClient.getMetricsSummary(startDate, endDate);
        const duration = performance.now() - start;
        logger.apiCall('GET', '/api/v1/metrics/summary', duration);
        return result;
      } catch (error) {
        const duration = performance.now() - start;
        logger.apiCall('GET', '/api/v1/metrics/summary', duration, undefined, error as Error);
        throw error;
      }
    },
    staleTime: 60000, // 1 minute
    refetchInterval: 30000, // Refetch every 30 seconds for live dashboard
  });
}

/**
 * Hook for fetching agent metrics
 */
export function useAgentMetrics(
  startDate?: string,
  endDate?: string,
  agentType?: string,
  limit = 100
) {
  return useQuery({
    queryKey: ['metrics', 'agents', startDate, endDate, agentType, limit],
    queryFn: async (): Promise<AgentMetricResponse[]> => {
      const start = performance.now();
      try {
        const result = await apiClient.getAgentMetrics(startDate, endDate, agentType, limit);
        const duration = performance.now() - start;
        logger.apiCall('GET', '/api/v1/metrics/agents', duration);
        return result;
      } catch (error) {
        const duration = performance.now() - start;
        logger.apiCall('GET', '/api/v1/metrics/agents', duration, undefined, error as Error);
        throw error;
      }
    },
    staleTime: 60000,
  });
}

/**
 * Hook for fetching campaigns
 */
export function useCampaigns() {
  return useQuery({
    queryKey: ['campaigns'],
    queryFn: async (): Promise<CampaignResponse[]> => {
      const start = performance.now();
      try {
        const result = await apiClient.listCampaigns();
        const duration = performance.now() - start;
        logger.apiCall('GET', '/api/v1/campaigns/', duration);
        return result;
      } catch (error) {
        const duration = performance.now() - start;
        logger.apiCall('GET', '/api/v1/campaigns/', duration, undefined, error as Error);
        throw error;
      }
    },
    staleTime: 30000,
  });
}

/**
 * Generic hook for API error handling
 */
export function useApiError(error: unknown): {
  message: string;
  statusCode?: number;
  isNetworkError: boolean;
} {
  if (error instanceof APIClientError) {
    return {
      message: error.message,
      statusCode: error.statusCode,
      isNetworkError: error.statusCode === 0,
    };
  }

  if (error instanceof Error) {
    return {
      message: error.message,
      isNetworkError: false,
    };
  }

  return {
    message: 'An unknown error occurred',
    isNetworkError: false,
  };
}

