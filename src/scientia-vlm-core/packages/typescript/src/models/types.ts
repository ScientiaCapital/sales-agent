/**
 * VLM Model Types
 *
 * Type definitions for the VLM model selection system.
 * Based on empirical audit data from 216 tests across 6 construction trades.
 *
 * @module @scientia/vlm-core/models
 * @version 1.0.0
 * @license Proprietary - Scientia Capital
 */

/**
 * Construction trades supported by FieldVault
 */
export type Trade =
  | 'roofing'
  | 'electrical'
  | 'hvac'
  | 'solar'
  | 'plumbing'
  | 'general';

/**
 * Image types that the VLM stack can process
 */
export type ImageType =
  | 'blueprint'
  | 'field_photo'
  | 'nameplate'
  | 'reference_chart'
  | 'symbol_legend';

/**
 * VLM provider identifiers
 */
export type VLMProvider = 'qwen' | 'glm' | 'anthropic' | 'deepseek';

/**
 * Model metadata from 216-test audit (2025-12-13)
 *
 * All cost and performance metrics are empirically measured,
 * not theoretical estimates.
 */
export interface VLMModel {
  /** OpenRouter model ID (e.g., 'qwen/qwen3-vl-30b-a3b-instruct') */
  id: string;

  /** Human-readable display name */
  name: string;

  /** Model provider */
  provider: VLMProvider;

  /** Average score from audit (0-10 scale) */
  avgScore: number;

  /** Average cost per API call in USD */
  costPerCall: number;

  /** Average latency in milliseconds */
  avgLatencyMs: number;

  /** Maximum context length in tokens */
  contextLength: number;

  /** Whether the model supports PDF input */
  supportsPdf: boolean;

  /** Image types this model excels at (from audit) */
  bestFor: ImageType[];

  /** Number of audit wins (scores >= 8) */
  auditWins: number;

  /** Number of perfect scores (10/10) from audit */
  perfectScores: number;

  /** Whether to avoid this model (e.g., Qwen3-8B-Thinking: expensive, lower accuracy) */
  avoid: boolean;

  /** Reason for avoiding (if avoid is true) */
  avoidReason?: string;
}

/**
 * Configuration for model selection
 */
export interface SelectionConfig {
  /** Target trade (optional - will auto-detect if not provided) */
  trade?: Trade;

  /** Image type (optional - will auto-detect if not provided) */
  imageType?: ImageType;

  /** Minimum confidence threshold to accept result (default: 0.6) */
  confidenceThreshold?: number;

  /** Maximum cost per analysis in USD (optional budget cap) */
  maxCost?: number;

  /** Prefer faster models over more accurate ones */
  preferSpeed?: boolean;

  /** Force a specific model (bypasses selection algorithm) */
  forceModel?: string;
}

/**
 * Result of model selection algorithm
 */
export interface SelectionResult {
  /** Selected primary model */
  model: VLMModel;

  /** Ordered fallback chain (try in sequence if primary fails) */
  fallbackChain: VLMModel[];

  /** Trade-specific extraction prompt */
  prompt: string;

  /** Estimated cost for this analysis */
  estimatedCost: number;

  /** Explanation of why this model was selected */
  reasoning: string;

  /** Audit data that informed this selection */
  auditBasis: {
    /** Date of audit */
    auditDate: string;
    /** Total tests in audit */
    totalTests: number;
    /** Model's win rate in audit */
    winRate: number;
  };
}

/**
 * Fallback chain definition
 */
export interface FallbackChain {
  /** Chain identifier */
  id: string;

  /** Human-readable name */
  name: string;

  /** Image types this chain is optimized for */
  targetImageTypes: ImageType[];

  /** Ordered list of model IDs to try */
  models: string[];

  /** Confidence threshold to trigger fallback */
  fallbackThreshold: number;

  /** Total estimated cost if all models tried */
  maxCost: number;
}

/**
 * Audit statistics for a model
 */
export interface AuditStats {
  /** Total tests run */
  totalTests: number;

  /** Tests with valid JSON output */
  jsonSuccessRate: number;

  /** Tests with score >= 8 */
  winCount: number;

  /** Tests with score = 10 */
  perfectCount: number;

  /** Average score (0-10) */
  avgScore: number;

  /** Average cost per call (USD) */
  avgCost: number;

  /** Average latency (ms) */
  avgLatency: number;

  /** Per-trade breakdown */
  tradeBreakdown: Record<Trade, {
    tests: number;
    avgScore: number;
    wins: number;
  }>;
}
