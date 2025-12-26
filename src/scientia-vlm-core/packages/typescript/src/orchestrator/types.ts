/**
 * Multi-Provider VLM Orchestrator Types
 *
 * Enables flexible provider selection across all Scientia Capital projects.
 * Each project can configure which providers to use based on:
 * - Cost requirements
 * - Accuracy needs
 * - Latency constraints
 * - Data residency requirements
 *
 * @module @scientia/vlm-core/orchestrator
 * @version 1.0.0
 */

/**
 * Supported VLM providers
 */
export type VLMProvider =
  | 'openrouter'    // Chinese VLMs (Qwen, GLM) - cheapest
  | 'anthropic'     // Claude models - most reliable
  | 'google'        // Gemini models - good balance
  | 'deepseek';     // DeepSeek - text specialist

/**
 * Provider-specific model IDs
 */
export interface ProviderModels {
  openrouter: {
    primary: 'qwen/qwen3-vl-30b-a3b-instruct';
    fallback: 'qwen/qwen-vl-max';
    specialist: 'z-ai/glm-4.6v';
    budget: 'qwen/qwen2.5-vl-72b-instruct';
  };
  anthropic: {
    haiku: 'claude-3-5-haiku-20241022';
    sonnet: 'claude-sonnet-4-5-20250514';
    opus: 'claude-opus-4-5-20250514';
  };
  google: {
    flash: 'gemini-2.5-flash';
    pro: 'gemini-2.5-pro';
    flash_lite: 'gemini-2.0-flash-lite';
  };
  deepseek: {
    chat: 'deepseek-chat-v3.1';
    reasoner: 'deepseek-reasoner';
  };
}

/**
 * Provider pricing (per 1M tokens or per call)
 */
export interface ProviderPricing {
  provider: VLMProvider;
  model: string;
  inputPer1M: number;
  outputPer1M: number;
  estimatedPerCall: number;  // For typical VLM call
}

/**
 * Project-level configuration
 */
export interface ProjectConfig {
  /** Project identifier */
  projectId: string;

  /** Display name */
  name: string;

  /** Primary provider for this project */
  primaryProvider: VLMProvider;

  /** Primary model within that provider */
  primaryModel: string;

  /** Fallback chain (ordered) */
  fallbackChain: Array<{
    provider: VLMProvider;
    model: string;
    triggerOn: 'low_confidence' | 'error' | 'timeout';
  }>;

  /** Budget constraints */
  budget: {
    maxCostPerCall: number;
    maxMonthlyCost: number;
  };

  /** Feature flags */
  features: {
    usePreprocessing: boolean;
    useROIDetection: boolean;
    useConfidenceScoring: boolean;
  };
}

/**
 * Orchestrator request
 */
export interface OrchestratorRequest {
  /** Image as base64 or URL */
  image: string;
  imageType: 'base64' | 'url';
  mimeType: 'image/png' | 'image/jpeg' | 'image/webp';

  /** Extraction prompt */
  prompt: string;

  /** Expected output schema (for validation) */
  schema?: Record<string, unknown>;

  /** Override project config for this request */
  overrides?: Partial<ProjectConfig>;
}

/**
 * Orchestrator response
 */
export interface OrchestratorResponse {
  /** Extracted data */
  data: Record<string, unknown>;

  /** Which provider/model was used */
  provider: VLMProvider;
  model: string;

  /** Was fallback triggered? */
  usedFallback: boolean;
  fallbackReason?: string;

  /** Confidence score (0-1) */
  confidence: number;

  /** Cost tracking */
  cost: {
    inputTokens: number;
    outputTokens: number;
    totalCost: number;
  };

  /** Timing */
  latencyMs: number;

  /** Raw response for debugging */
  raw?: unknown;
}

/**
 * Provider health status
 */
export interface ProviderHealth {
  provider: VLMProvider;
  status: 'healthy' | 'degraded' | 'down';
  lastCheck: Date;
  errorRate: number;
  avgLatencyMs: number;
}

/**
 * Orchestrator configuration
 */
export interface OrchestratorConfig {
  /** Default project config (used if project not found) */
  defaultConfig: ProjectConfig;

  /** Project-specific configs */
  projects: Map<string, ProjectConfig>;

  /** Provider health tracking */
  healthCheck: {
    enabled: boolean;
    intervalMs: number;
  };

  /** Logging */
  logging: {
    level: 'debug' | 'info' | 'warn' | 'error';
    includeRawResponses: boolean;
  };
}
