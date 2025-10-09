/**
 * API Client Service
 * 
 * Provides type-safe HTTP client for backend API communication
 * Following Context7 best practices for error handling and type safety
 */

import type {
  Lead,
  LeadQualificationRequest,
  LeadQualificationResponse,
  LeadListResponse,
  StreamStatus,
  APIError,
  CSVImportProgress,
  CampaignCreateRequest,
  CampaignResponse,
  MessageResponse,
  AnalyticsResponse,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

/**
 * Custom error class for API errors
 */
export class APIClientError extends Error {
  statusCode: number;
  detail?: string;

  constructor(
    message: string,
    statusCode: number,
    detail?: string
  ) {
    super(message);
    this.name = 'APIClientError';
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

/**
 * Generic fetch wrapper with error handling
 */
async function fetchAPI<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error: APIError = await response.json().catch(() => ({
        detail: response.statusText,
        status_code: response.status,
      }));

      throw new APIClientError(
        error.detail || 'API request failed',
        response.status,
        error.detail
      );
    }

    return await response.json();
  } catch (error) {
    if (error instanceof APIClientError) {
      throw error;
    }
    throw new APIClientError(
      error instanceof Error ? error.message : 'Network error',
      0
    );
  }
}

/**
 * API Client
 */
export const apiClient = {
  // ============================================================================
  // Health Endpoints
  // ============================================================================

  /**
   * Check API health status
   */
  health: async () => {
    return fetchAPI<{ status: string }>('/api/v1/health');
  },

  // ============================================================================
  // Lead Management
  // ============================================================================

  /**
   * Qualify a new lead using Cerebras AI
   */
  qualifyLead: async (
    request: LeadQualificationRequest
  ): Promise<LeadQualificationResponse> => {
    return fetchAPI<LeadQualificationResponse>('/api/v1/leads/qualify', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  /**
   * List all leads with pagination
   */
  listLeads: async (skip = 0, limit = 100): Promise<LeadListResponse[]> => {
    return fetchAPI<LeadListResponse[]>(
      `/api/v1/leads/?skip=${skip}&limit=${limit}`
    );
  },

  /**
   * Get a specific lead by ID
   */
  getLead: async (leadId: number): Promise<Lead> => {
    return fetchAPI<Lead>(`/api/v1/leads/${leadId}`);
  },

  /**
   * Import leads from CSV file
   */
  importCSV: async (file: File): Promise<CSVImportProgress> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/api/v1/leads/import/csv`, {
      method: 'POST',
      body: formData,
      // Don't set Content-Type header - browser will set it with boundary
    });

    if (!response.ok) {
      const error: APIError = await response.json().catch(() => ({
        detail: response.statusText,
        status_code: response.status,
      }));

      throw new APIClientError(
        error.detail || 'CSV import failed',
        response.status,
        error.detail
      );
    }

    return await response.json();
  },

  // ============================================================================
  // Campaign Management
  // ============================================================================

  /**
   * Create a new campaign
   */
  createCampaign: async (
    request: CampaignCreateRequest
  ): Promise<CampaignResponse> => {
    return fetchAPI<CampaignResponse>('/api/v1/campaigns/create', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  /**
   * Generate messages for a campaign
   */
  generateMessages: async (
    campaignId: number,
    customContext?: string,
    forceRegenerate = false
  ): Promise<{ success: boolean; campaign_id: number; statistics: any }> => {
    return fetchAPI<{ success: boolean; campaign_id: number; statistics: any }>(
      `/api/v1/campaigns/${campaignId}/generate-messages`,
      {
        method: 'POST',
        body: JSON.stringify({
          custom_context: customContext,
          force_regenerate: forceRegenerate,
        }),
      }
    );
  },

  /**
   * List all campaigns with optional filters
   */
  listCampaigns: async (
    status?: string,
    skip = 0,
    limit = 100
  ): Promise<CampaignResponse[]> => {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    params.append('skip', skip.toString());
    params.append('limit', limit.toString());
    return fetchAPI<CampaignResponse[]>(`/api/v1/campaigns?${params}`);
  },

  /**
   * Get campaign messages
   */
  getCampaignMessages: async (
    campaignId: number,
    status?: string,
    skip = 0,
    limit = 100
  ): Promise<MessageResponse[]> => {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    params.append('skip', skip.toString());
    params.append('limit', limit.toString());
    return fetchAPI<MessageResponse[]>(
      `/api/v1/campaigns/${campaignId}/messages?${params}`
    );
  },

  /**
   * Get campaign analytics
   */
  getCampaignAnalytics: async (
    campaignId: number
  ): Promise<AnalyticsResponse> => {
    return fetchAPI<AnalyticsResponse>(
      `/api/v1/campaigns/${campaignId}/analytics`
    );
  },

  /**
   * Activate campaign for sending
   */
  activateCampaign: async (
    campaignId: number
  ): Promise<{ success: boolean; campaign: CampaignResponse }> => {
    return fetchAPI<{ success: boolean; campaign: CampaignResponse }>(
      `/api/v1/campaigns/${campaignId}/send`,
      {
        method: 'POST',
      }
    );
  },

  /**
   * Get message variants
   */
  getMessageVariants: async (
    messageId: number
  ): Promise<{ message_id: number; variants: any }> => {
    return fetchAPI<{ message_id: number; variants: any }>(
      `/api/v1/campaigns/messages/${messageId}/variants`
    );
  },

  /**
   * Update message status
   */
  updateMessageStatus: async (
    messageId: number,
    status: string,
    variantNumber?: number
  ): Promise<{ success: boolean; message: MessageResponse }> => {
    return fetchAPI<{ success: boolean; message: MessageResponse }>(
      `/api/v1/campaigns/messages/${messageId}/status`,
      {
        method: 'PUT',
        body: JSON.stringify({
          status,
          variant_number: variantNumber,
        }),
      }
    );
  },

  // ============================================================================
  // Streaming Endpoints
  // ============================================================================

  /**
   * Start a streaming agent workflow
   */
  startStream: async (
    leadId: number,
    agentType: 'qualification' | 'enrichment' | 'growth' = 'qualification'
  ): Promise<{ stream_id: string; workflow_id: string; websocket_url: string }> => {
    return fetchAPI<{
      stream_id: string;
      workflow_id: string;
      websocket_url: string;
    }>(`/api/v1/stream/start/${leadId}?agent_type=${agentType}`, {
      method: 'POST',
    });
  },

  /**
   * Get stream status
   */
  getStreamStatus: async (streamId: string): Promise<StreamStatus> => {
    return fetchAPI<StreamStatus>(`/api/v1/stream/status/${streamId}`);
  },

  /**
   * Create WebSocket URL for streaming
   */
  getWebSocketURL: (streamId: string): string => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = API_BASE_URL.replace(/^https?:/, '').replace(/\/$/, '');
    return `${wsProtocol}${wsHost}/api/v1/stream/ws/${streamId}`;
  },

  // ============================================================================
  // Research Endpoints
  // ============================================================================

  /**
   * Execute research pipeline (non-streaming)
   */
  executeResearch: async (
    request: import('../types').ResearchRequest
  ): Promise<import('../types').ResearchResponse> => {
    return fetchAPI<import('../types').ResearchResponse>('/api/v1/research/', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  /**
   * Get research pipeline status
   */
  getResearchStatus: async (): Promise<import('../types').ResearchStatus> => {
    return fetchAPI<import('../types').ResearchStatus>('/api/v1/research/status');
  },
};

export default apiClient;
