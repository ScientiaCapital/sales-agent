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
  MetricsSummaryResponse,
  AgentMetricResponse,
  ProviderCostMetrics,
  ABTest,
  ABTestCreate,
  ABTestUpdate,
  ABTestAnalysis,
  ABTestRecommendations,
  ReportTemplate,
  ReportTemplateCreate,
  ReportGenerateRequest,
  ReportGenerateResponse,
  ExportRequest,
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

  // ============================================================================
  // Metrics Endpoints (Task 11.2)
  // ============================================================================

  /**
   * Get comprehensive metrics summary for dashboard
   *
   * @param startDate - Start date for metrics (ISO 8601). Defaults to 7 days ago on backend
   * @param endDate - End date for metrics (ISO 8601). Defaults to now on backend
   */
  getMetricsSummary: async (
    startDate?: string,
    endDate?: string
  ): Promise<MetricsSummaryResponse> => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);

    const query = params.toString();
    return fetchAPI<MetricsSummaryResponse>(
      `/api/v1/metrics/summary${query ? `?${query}` : ''}`
    );
  },

  /**
   * Get agent execution metrics with optional filtering
   *
   * @param startDate - Start date for metrics (ISO 8601)
   * @param endDate - End date for metrics (ISO 8601)
   * @param agentType - Filter by specific agent type (e.g., 'qualification', 'enrichment')
   * @param limit - Maximum number of results to return (default: 100, max: 1000)
   */
  getAgentMetrics: async (
    startDate?: string,
    endDate?: string,
    agentType?: string,
    limit = 100
  ): Promise<AgentMetricResponse[]> => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (agentType) params.append('agent_type', agentType);
    params.append('limit', limit.toString());

    return fetchAPI<AgentMetricResponse[]>(`/api/v1/metrics/agents?${params}`);
  },

  /**
   * Get cost metrics by AI provider
   *
   * @param startDate - Start date for metrics (ISO 8601)
   * @param endDate - End date for metrics (ISO 8601)
   * @param provider - Filter by specific provider (cerebras, claude, deepseek, ollama)
   * @param limit - Maximum number of results to return (default: 100, max: 1000)
   */
  getCostMetrics: async (
    startDate?: string,
    endDate?: string,
    provider?: string,
    limit = 100
  ): Promise<ProviderCostMetrics[]> => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (provider) params.append('provider', provider);
    params.append('limit', limit.toString());

    return fetchAPI<ProviderCostMetrics[]>(`/api/v1/metrics/costs?${params}`);
  },

  // ============================================================================
  // A/B Testing Endpoints (Task 11.3)
  // ============================================================================

  /**
   * List all A/B tests with optional filters
   *
   * @param status - Filter by test status (draft, running, completed, paused)
   * @param testType - Filter by test type (campaign, agent_performance, ui_element)
   * @param skip - Number of records to skip for pagination
   * @param limit - Maximum number of results to return
   */
  listABTests: async (
    status?: string,
    testType?: string,
    skip = 0,
    limit = 100
  ): Promise<ABTest[]> => {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (testType) params.append('test_type', testType);
    params.append('skip', skip.toString());
    params.append('limit', limit.toString());
    return fetchAPI<ABTest[]>(`/api/v1/ab-tests?${params}`);
  },

  /**
   * Create a new A/B test
   */
  createABTest: async (request: ABTestCreate): Promise<ABTest> => {
    return fetchAPI<ABTest>('/api/v1/ab-tests', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  /**
   * Get A/B test by ID
   */
  getABTest: async (testId: string): Promise<ABTest> => {
    return fetchAPI<ABTest>(`/api/v1/ab-tests/${testId}`);
  },

  /**
   * Get detailed statistical analysis for A/B test
   */
  getABTestAnalysis: async (testId: string): Promise<ABTestAnalysis> => {
    return fetchAPI<ABTestAnalysis>(`/api/v1/ab-tests/${testId}/analysis`);
  },

  /**
   * Update A/B test metrics
   */
  updateABTestMetrics: async (
    testId: string,
    metrics: ABTestUpdate
  ): Promise<ABTest> => {
    return fetchAPI<ABTest>(`/api/v1/ab-tests/${testId}`, {
      method: 'PATCH',
      body: JSON.stringify(metrics),
    });
  },

  /**
   * Start A/B test
   */
  startABTest: async (testId: string): Promise<ABTest> => {
    return fetchAPI<ABTest>(`/api/v1/ab-tests/${testId}/start`, {
      method: 'POST',
    });
  },

  /**
   * Stop A/B test and run final analysis
   */
  stopABTest: async (testId: string): Promise<ABTest> => {
    return fetchAPI<ABTest>(`/api/v1/ab-tests/${testId}/stop`, {
      method: 'POST',
    });
  },

  /**
   * Get early stopping recommendations for A/B test
   */
  getABTestRecommendations: async (
    testId: string
  ): Promise<ABTestRecommendations> => {
    return fetchAPI<ABTestRecommendations>(
      `/api/v1/ab-tests/${testId}/recommendations`
    );
  },

  // ============================================================================
  // Report Template Endpoints (Task 11.4)
  // ============================================================================

  /**
   * List all report templates
   *
   * @param reportType - Filter by report type
   * @param skip - Number of records to skip for pagination
   * @param limit - Maximum number of results to return
   */
  listReportTemplates: async (
    reportType?: string,
    skip = 0,
    limit = 100
  ): Promise<ReportTemplate[]> => {
    const params = new URLSearchParams();
    if (reportType) params.append('report_type', reportType);
    params.append('skip', skip.toString());
    params.append('limit', limit.toString());
    return fetchAPI<ReportTemplate[]>(`/api/v1/report-templates?${params}`);
  },

  /**
   * Create a new report template
   */
  createReportTemplate: async (
    request: ReportTemplateCreate
  ): Promise<ReportTemplate> => {
    return fetchAPI<ReportTemplate>('/api/v1/report-templates', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  /**
   * Get report template by ID
   */
  getReportTemplate: async (templateId: string): Promise<ReportTemplate> => {
    return fetchAPI<ReportTemplate>(`/api/v1/report-templates/${templateId}`);
  },

  /**
   * Generate report from template
   */
  generateReportFromTemplate: async (
    request: ReportGenerateRequest
  ): Promise<ReportGenerateResponse> => {
    return fetchAPI<ReportGenerateResponse>(
      '/api/v1/report-templates/generate',
      {
        method: 'POST',
        body: JSON.stringify(request),
      }
    );
  },

  /**
   * Delete report template
   */
  deleteReportTemplate: async (templateId: string): Promise<{ success: boolean }> => {
    return fetchAPI<{ success: boolean }>(
      `/api/v1/report-templates/${templateId}`,
      {
        method: 'DELETE',
      }
    );
  },

  // ============================================================================
  // Export Endpoints (Task 11.5)
  // ============================================================================

  /**
   * Export report data in specified format (CSV, PDF, XLSX)
   *
   * Returns a Blob that can be downloaded as a file
   */
  exportReport: async (request: ExportRequest): Promise<Blob> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/exports/report`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error: APIError = await response.json().catch(() => ({
        detail: response.statusText,
        status_code: response.status,
      }));

      throw new APIClientError(
        error.detail || 'Export failed',
        response.status,
        error.detail
      );
    }

    return await response.blob();
  },

  /**
   * Download exported file
   *
   * Helper method to trigger file download in browser
   */
  downloadExport: async (
    request: ExportRequest,
    filename?: string
  ): Promise<void> => {
    const blob = await apiClient.exportReport(request);

    // Generate filename if not provided
    const timestamp = new Date().toISOString().split('T')[0];
    const defaultFilename = `report_${timestamp}.${request.format}`;

    // Create download link
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename || defaultFilename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },
};

export default apiClient;
