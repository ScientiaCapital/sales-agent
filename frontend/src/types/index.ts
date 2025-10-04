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
