/**
 * TypeScript type definitions for Sales Agent frontend
 */

// ============================================================================
// Lead Types
// ============================================================================

export interface Lead {
  id: number;
  company_name: string;
  company_website?: string;
  company_size?: string;
  industry?: string;
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;
  contact_title?: string;
  qualification_score?: number;
  qualification_reasoning?: string;
  qualification_model?: string;
  qualification_latency_ms?: number;
  qualified_at?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface LeadQualificationRequest {
  company_name: string;
  company_website?: string;
  company_size?: string;
  industry?: string;
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;
  contact_title?: string;
  notes?: string;
}

export interface LeadQualificationResponse extends Lead {}

export interface LeadListResponse {
  id: number;
  company_name: string;
  industry?: string;
  qualification_score?: number;
  created_at: string;
}

// ============================================================================
// Iterative Refinement Types
// ============================================================================

export interface RefinementStep {
  step: number;
  score: number;
  reasoning: string;
  improvements: string[];
  timestamp: string;
}

export interface RefinementProcess {
  lead_id: number;
  original_score: number;
  steps: RefinementStep[];
  final_score: number;
  total_improvement: number;
  status: 'pending' | 'processing' | 'completed' | 'error';
  created_at: string;
  completed_at?: string;
}

// ============================================================================
// WebSocket Streaming Types
// ============================================================================

export interface StreamMessage {
  type: 'start' | 'chunk' | 'complete' | 'error';
  stream_id?: string;
  agent_type?: string;
  content?: string;
  delta?: string;
  error?: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

export interface StreamStatus {
  stream_id: string;
  workflow_id: string;
  status: 'pending' | 'streaming' | 'completed' | 'error';
  current_step: string;
  active_connections: number;
  total_latency_ms?: number;
  total_cost_usd?: number;
  created_at: string;
  completed_at?: string;
}

// ============================================================================
// Research Pipeline Types
// ============================================================================

export interface ResearchAgent {
  id: string;
  name: string;
  role: 'query' | 'search' | 'summarize' | 'synthesize' | 'format';
  status: 'idle' | 'working' | 'completed' | 'error';
  progress: number;
  output?: string;
}

export interface ResearchPipeline {
  id: string;
  lead_id: number;
  agents: ResearchAgent[];
  status: 'pending' | 'running' | 'completed' | 'error';
  total_progress: number;
  result?: string;
  created_at: string;
  completed_at?: string;
}

export interface ResearchRequest {
  topic: string;
  depth: 'shallow' | 'medium' | 'deep';
  format_style: 'markdown' | 'json' | 'plain';
  temperature: number;
  stream: boolean;
  preferred_method?: string;
  max_queries: number;
  timeout_seconds: number;
}

export interface ResearchResponse {
  research_topic: string;
  final_output: string;
  total_latency_ms: number;
  total_cost_usd: number;
  queries_generated: string[];
  search_results_count: number;
  agents_executed: number;
  metadata: Record<string, unknown>;
}

export interface ResearchStatus {
  pipeline_configuration: Record<string, unknown>;
  resource_usage: Record<string, unknown>;
  router_status: Record<string, unknown>;
}

export interface ResearchSSEEvent {
  type: 'pipeline_start' | 'agent_start' | 'agent_complete' | 'final' | 'error';
  agent?: string;
  output?: unknown;
  latency_ms?: number;
  cost_usd?: number;
  message?: string;
  result?: ResearchResponse;
}

export interface ResearchHistoryItem {
  id: string;
  topic: string;
  depth: string;
  format_style: string;
  status: 'completed' | 'error' | 'pending';
  final_output?: string;
  total_latency_ms?: number;
  total_cost_usd?: number;
  queries_generated?: string[];
  search_results_count?: number;
  agents_executed?: number;
  created_at: string;
  error?: string;
}

// ============================================================================
// Knowledge Base Types
// ============================================================================

export interface Document {
  id: string;
  name: string;
  type: 'pdf' | 'docx' | 'txt' | 'md';
  size: number;
  uploaded_at: string;
  processed: boolean;
  vector_count?: number;
  metadata?: Record<string, unknown>;
}

export interface ICPCriteria {
  id: string;
  name: string;
  description: string;
  weight: number;
  created_at: string;
}

export interface VectorSearchResult {
  document_id: string;
  document_name: string;
  chunk_text: string;
  similarity_score: number;
  metadata?: Record<string, unknown>;
}

// ============================================================================
// Contact Discovery Types
// ============================================================================

export interface Contact {
  id: string;
  name: string;
  title: string;
  company: string;
  email?: string;
  phone?: string;
  linkedin_url?: string;
  twitter_handle?: string;
  social_activity_score: number;
}

export interface SocialActivity {
  id: string;
  contact_id: string;
  platform: 'linkedin' | 'twitter' | 'github';
  activity_type: 'post' | 'comment' | 'share' | 'commit';
  content: string;
  timestamp: string;
  engagement_score: number;
}

export interface RelationshipNode {
  id: string;
  name: string;
  type: 'contact' | 'company' | 'organization';
  connections: string[];
}

// ============================================================================
// Agent Teams Types
// ============================================================================

export interface AgentDeployment {
  id: string;
  customer_id: string;
  customer_name: string;
  agent_count: number;
  status: 'active' | 'paused' | 'stopped';
  leads_processed: number;
  messages_sent: number;
  success_rate: number;
  created_at: string;
}

export interface AgentStatus {
  agent_id: string;
  deployment_id: string;
  status: 'idle' | 'working' | 'error';
  current_task?: string;
  tasks_completed: number;
  last_active: string;
}

// ============================================================================
// Voice Agent Types
// ============================================================================

export interface VoiceCall {
  id: string;
  lead_id: number;
  status: 'initializing' | 'ringing' | 'connected' | 'ended' | 'failed';
  duration_seconds?: number;
  transcript?: string;
  sentiment_score?: number;
  started_at: string;
  ended_at?: string;
}

export interface AudioWaveform {
  timestamp: number;
  amplitude: number;
}

// ============================================================================
// Document Processing Types
// ============================================================================

export interface JobMatch {
  job_id: string;
  job_title: string;
  company: string;
  match_score: number;
  key_skills: string[];
  reasoning: string;
}

export interface DocumentAnalysis {
  id: string;
  document_id: string;
  candidate_name?: string;
  extracted_skills: string[];
  experience_years?: number;
  job_matches: JobMatch[];
  processed_at: string;
}

// ============================================================================
// CSV Import Types
// ============================================================================

export interface CSVImportPreview {
  headers: string[];
  rows: string[][];
  total_rows: number;
  detected_mappings: Record<string, string>;
}

export interface CSVImportProgress {
  total: number;
  processed: number;
  succeeded: number;
  failed: number;
  errors: string[];
}

// ============================================================================
// Campaign & Outreach Types
// ============================================================================

export interface CampaignCreateRequest {
  name: string;
  channel: 'email' | 'linkedin' | 'sms';
  min_qualification_score?: number;
  target_industries?: string[];
  target_company_sizes?: string[];
  message_template?: string;
  custom_context?: string;
}

export interface CampaignResponse {
  id: number;
  name: string;
  status: 'draft' | 'active' | 'paused' | 'completed' | 'cancelled';
  channel: 'email' | 'linkedin' | 'sms';
  min_qualification_score?: number;
  target_industries?: string[];
  target_company_sizes?: string[];
  total_messages: number;
  total_sent: number;
  total_delivered: number;
  total_opened: number;
  total_clicked: number;
  total_replied: number;
  total_cost: number;
  created_at: string;
}

export interface MessageVariant {
  subject?: string;
  body: string;
  tone: 'professional' | 'friendly' | 'direct';
}

export interface MessageResponse {
  id: number;
  campaign_id: number;
  lead_id: number;
  variants: MessageVariant[];
  selected_variant: number;
  status: 'pending' | 'sent' | 'delivered' | 'opened' | 'clicked' | 'replied' | 'bounced' | 'failed';
  generation_cost: number;
  created_at: string;
}

export interface VariantAnalytics {
  variant_number: number;
  tone: 'professional' | 'friendly' | 'direct';
  times_selected: number;
  times_opened: number;
  times_clicked: number;
  times_replied: number;
  open_rate: number;
  click_rate: number;
  reply_rate: number;
}

export interface AnalyticsResponse {
  campaign: CampaignResponse;
  metrics: {
    delivery_rate: number;
    open_rate: number;
    click_rate: number;
    reply_rate: number;
  };
  cost: {
    total: number;
    per_message: number;
    per_reply: number;
  };
  ab_testing: {
    variants: VariantAnalytics[];
    winner?: number;
    statistical_significance?: boolean;
  };
  top_performing_messages: Array<{
    message_id: number;
    lead_name: string;
    variant: number;
    tone: string;
    reply_rate: number;
    subject?: string;
    preview: string;
  }>;
}

export interface TimelineDataPoint {
  date: string;
  sent: number;
  opened: number;
  clicked: number;
  replied: number;
}

// ============================================================================
// Firebase Types
// ============================================================================

export interface FirebaseConfig {
  apiKey: string;
  authDomain: string;
  projectId: string;
  storageBucket: string;
  messagingSenderId: string;
  appId: string;
}

export interface RealtimeUpdate<T> {
  id: string;
  data: T;
  timestamp: number;
  action: 'created' | 'updated' | 'deleted';
}

// ============================================================================
// API Response Types
// ============================================================================

export interface APIError {
  detail: string;
  status_code: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

// ============================================================================
// Component Props Types
// ============================================================================

export interface BaseComponentProps {
  className?: string;
}

export interface LoadingState {
  isLoading: boolean;
  error?: string | null;
}

// ============================================================================
// Metrics & Analytics Types (Task 11.2)
// ============================================================================

/**
 * Single time-series metric point
 */
export interface MetricPoint {
  timestamp: string;
  value: number;
  count: number;
}

/**
 * Agent execution metrics response
 */
export interface AgentMetricResponse {
  agent_type: string;
  date: string;
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  avg_latency_ms: number;
  min_latency_ms?: number;
  max_latency_ms?: number;
  total_cost_usd: number;
  avg_cost_usd: number;
  success_rate: number;
}

/**
 * Cost metrics by AI provider
 */
export interface ProviderCostMetrics {
  provider: string;
  date: string;
  total_calls: number;
  total_tokens: number;
  total_cost_usd: number;
  avg_latency_ms?: number;
}

/**
 * System-level metric response
 */
export interface SystemMetricResponse {
  metric_name: string;
  metric_value: number;
  metric_unit: string;
  category: string;
  recorded_at: string;
  tags?: Record<string, unknown>;
}

/**
 * Comprehensive metrics summary for dashboard
 */
export interface MetricsSummaryResponse {
  period_start: string;
  period_end: string;
  // API Performance
  total_api_requests: number;
  avg_response_time_ms: number;
  error_rate: number;
  // Agent Performance
  total_agent_executions: number;
  agent_success_rate: number;
  avg_agent_latency_ms: number;
  // Cost Tracking
  total_cost_usd: number;
  cost_by_provider: Record<string, number>;
  // Business Metrics
  leads_processed: number;
  leads_qualified: number;
  qualification_rate: number;
}

/**
 * API endpoint performance metrics
 */
export interface EndpointMetricResponse {
  endpoint_path: string;
  method: string;
  date: string;
  total_requests: number;
  avg_response_time_ms: number;
  p50_response_time_ms?: number;
  p95_response_time_ms?: number;
  p99_response_time_ms?: number;
  error_count: number;
  error_rate: number;
}

// ============================================================================
// A/B Testing Types (Task 11.3)
// ============================================================================

/**
 * A/B Test entity
 */
export interface ABTest {
  id: number;
  test_id: string;
  test_name: string;
  test_description?: string;
  variant_a_name: string;
  variant_b_name: string;
  test_type: 'campaign' | 'agent_performance' | 'ui_element';
  status: 'draft' | 'running' | 'completed' | 'paused';
  participants_a: number;
  participants_b: number;
  conversions_a: number;
  conversions_b: number;
  conversion_rate_a?: number;
  conversion_rate_b?: number;
  statistical_significance?: number;
  confidence_level?: number;
  winner?: 'A' | 'B' | null;
  start_date?: string;
  end_date?: string;
  created_at: string;
  updated_at?: string;
  campaign_id?: number;
  segment_filters?: Record<string, unknown>;
}

/**
 * Create A/B Test request
 */
export interface ABTestCreate {
  test_name: string;
  test_description?: string;
  variant_a_name: string;
  variant_b_name: string;
  test_type: 'campaign' | 'agent_performance' | 'ui_element';
  campaign_id?: number;
  segment_filters?: Record<string, unknown>;
}

/**
 * Update A/B Test metrics request
 */
export interface ABTestUpdate {
  participants_a?: number;
  participants_b?: number;
  conversions_a?: number;
  conversions_b?: number;
}

/**
 * Complete A/B Test statistical analysis
 */
export interface ABTestAnalysis {
  test_id: string;
  test_name: string;
  variant_a_name: string;
  variant_a_conversions: number;
  variant_a_participants: number;
  variant_a_conversion_rate: number;
  variant_a_confidence_interval: [number, number];
  variant_b_name: string;
  variant_b_conversions: number;
  variant_b_participants: number;
  variant_b_conversion_rate: number;
  variant_b_confidence_interval: [number, number];
  p_value: number;
  chi_square_statistic: number;
  is_significant: boolean;
  confidence_level: number;
  winner?: 'A' | 'B' | null;
  lift_percentage: number;
  minimum_sample_size: number;
  sample_adequacy: number;
  can_stop_early: boolean;
  recommendations: string[];
  days_remaining_estimate?: number;
}

/**
 * A/B Test recommendations for early stopping
 */
export interface ABTestRecommendations {
  test_id: string;
  can_stop_early: boolean;
  recommendations: string[];
  confidence_level: number;
  sample_adequacy: number;
  days_remaining_estimate?: number;
}

// ============================================================================
// Report Template Types (Task 11.4)
// ============================================================================

/**
 * Report Template for custom reports
 */
export interface ReportTemplate {
  id: number;
  template_id: string;
  name: string;
  description?: string;
  report_type: string;
  query_config: QueryConfig;
  visualization_config?: VisualizationConfig;
  filter_config?: FilterConfig;
  is_system_template: boolean;
  created_by?: string;
  created_at: string;
  updated_at?: string;
  usage_count: number;
}

/**
 * Query configuration for report builder
 */
export interface QueryConfig {
  table: string;
  columns: string[];
  filters: FilterClause[];
  aggregations: Aggregation[];
  group_by: string[];
  order_by: OrderClause[];
  limit: number;
}

/**
 * Filter clause for WHERE conditions
 */
export interface FilterClause {
  column: string;
  operator: '=' | '>' | '<' | '>=' | '<=' | '!=' | 'in' | 'like';
  value: string | number | string[] | number[];
}

/**
 * Aggregation function configuration
 */
export interface Aggregation {
  function: 'count' | 'sum' | 'avg' | 'min' | 'max';
  column: string;
  alias: string;
}

/**
 * Order by clause configuration
 */
export interface OrderClause {
  column: string;
  direction: 'asc' | 'desc';
}

/**
 * Visualization configuration for charts
 */
export interface VisualizationConfig {
  chart_type: 'bar' | 'line' | 'pie' | 'scatter' | 'table';
  x_axis?: string;
  y_axis?: string;
  color_by?: string;
  bubble_size?: string;
}

/**
 * Filter configuration with defaults
 */
export interface FilterConfig {
  default_filters?: FilterClause[];
  available_filters?: string[];
}

/**
 * Create Report Template request
 */
export interface ReportTemplateCreate {
  name: string;
  description?: string;
  report_type: string;
  query_config: QueryConfig;
  visualization_config?: VisualizationConfig;
  filter_config?: FilterConfig;
}

/**
 * Generate report from template request
 */
export interface ReportGenerateRequest {
  template_id: string;
  override_filters?: FilterClause[];
  time_range_start?: string;
  time_range_end?: string;
}

/**
 * Generated report response
 */
export interface ReportGenerateResponse {
  template_id: string;
  template_name: string;
  report_type: string;
  data: Record<string, unknown>[];
  row_count: number;
  generated_at: string;
}

// ============================================================================
// Export Types (Task 11.5)
// ============================================================================

/**
 * Export request configuration
 */
export interface ExportRequest {
  report_id?: number;
  template_id?: string;
  query_config?: QueryConfig;
  format: 'csv' | 'pdf' | 'xlsx';
  include_charts: boolean;
}

/**
 * Scheduled export configuration
 */
export interface ScheduledExport {
  id: number;
  schedule_id: string;
  name: string;
  template_id?: string;
  query_config?: QueryConfig;
  export_format: 'csv' | 'pdf' | 'xlsx';
  schedule_type: 'daily' | 'weekly' | 'monthly';
  schedule_time: string; // HH:MM format
  schedule_day?: number; // Day of week (0-6) or month (1-31)
  recipient_emails: string[];
  is_active: boolean;
  last_run_at?: string;
  next_run_at?: string;
  created_at: string;
}

/**
 * Create scheduled export request
 */
export interface ScheduledExportCreate {
  name: string;
  template_id?: string;
  query_config?: QueryConfig;
  export_format: 'csv' | 'pdf' | 'xlsx';
  schedule_type: 'daily' | 'weekly' | 'monthly';
  schedule_time: string;
  schedule_day?: number;
  recipient_emails: string[];
}

/**
 * Batch export result
 */
export interface BatchExportResult {
  status: 'completed' | 'partial' | 'failed';
  total: number;
  successful: number;
  failed: number;
  results: Array<{
    report_id: number;
    status: 'success' | 'failed';
    file_path?: string;
    error?: string;
  }>;
}
