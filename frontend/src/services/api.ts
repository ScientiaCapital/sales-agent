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
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

/**
 * Custom error class for API errors
 */
export class APIClientError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public detail?: string
  ) {
    super(message);
    this.name = 'APIClientError';
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
    return fetchAPI<{ status: string }>('/api/health');
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
    return fetchAPI<LeadQualificationResponse>('/api/leads/qualify', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  /**
   * List all leads with pagination
   */
  listLeads: async (skip = 0, limit = 100): Promise<LeadListResponse[]> => {
    return fetchAPI<LeadListResponse[]>(
      `/api/leads/?skip=${skip}&limit=${limit}`
    );
  },

  /**
   * Get a specific lead by ID
   */
  getLead: async (leadId: number): Promise<Lead> => {
    return fetchAPI<Lead>(`/api/leads/${leadId}`);
  },

  /**
   * Import leads from CSV file
   */
  importCSV: async (file: File): Promise<CSVImportProgress> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/api/leads/import/csv`, {
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
    }>(`/api/stream/start/${leadId}?agent_type=${agentType}`, {
      method: 'POST',
    });
  },

  /**
   * Get stream status
   */
  getStreamStatus: async (streamId: string): Promise<StreamStatus> => {
    return fetchAPI<StreamStatus>(`/api/stream/status/${streamId}`);
  },

  /**
   * Create WebSocket URL for streaming
   */
  getWebSocketURL: (streamId: string): string => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = API_BASE_URL.replace(/^https?:/, '').replace(/\/$/, '');
    return `${wsProtocol}${wsHost}/api/stream/ws/${streamId}`;
  },
};

export default apiClient;
