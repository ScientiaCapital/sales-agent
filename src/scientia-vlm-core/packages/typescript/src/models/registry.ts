/**
 * VLM Model Registry
 *
 * Central registry of all VLM models with empirical performance data
 * from the 216-test audit conducted on 2025-12-13.
 *
 * MOAT: This data represents defensible IP - competitors using
 * GPT-4V or Claude for this task pay 10-150x more.
 *
 * @module @scientia/vlm-core/models
 * @version 1.0.0
 * @license Proprietary - Scientia Capital
 */

import type { VLMModel, AuditStats, Trade } from './types';

/**
 * Qwen3 VL 30B - AUDIT WINNER
 *
 * Best overall model across all 6 trades.
 * - Avg Score: 5.9/10
 * - Cost: $0.00022/call
 * - 10 wins (8+ scores), 7 perfect scores (10/10)
 */
export const QWEN_30B: VLMModel = {
  id: 'qwen/qwen3-vl-30b-a3b-instruct',
  name: 'Qwen3-30B',
  provider: 'qwen',
  avgScore: 5.9,
  costPerCall: 0.00022,
  avgLatencyMs: 1800,
  contextLength: 128000,
  supportsPdf: true,
  bestFor: ['blueprint', 'field_photo', 'nameplate'],
  auditWins: 10,
  perfectScores: 7,
  avoid: false,
};

/**
 * Qwen VL Max
 *
 * High accuracy fallback when primary fails.
 * - Avg Score: 5.5/10
 * - Cost: $0.00073/call (3.3x more than 30B)
 */
export const QWEN_VL_MAX: VLMModel = {
  id: 'qwen/qwen-vl-max',
  name: 'Qwen-VL-Max',
  provider: 'qwen',
  avgScore: 5.5,
  costPerCall: 0.00073,
  avgLatencyMs: 2100,
  contextLength: 32768,
  supportsPdf: true,
  bestFor: ['blueprint', 'field_photo'],
  auditWins: 8,
  perfectScores: 4,
  avoid: false,
};

/**
 * Qwen3 VL 8B Thinking - AVOID
 *
 * Too expensive for the accuracy it provides.
 * - Avg Score: 5.0/10
 * - Cost: $0.00434/call (20x more than 30B!)
 * - Same or LOWER accuracy than 30B
 */
export const QWEN_8B_THINKING: VLMModel = {
  id: 'qwen/qwen3-vl-8b-thinking',
  name: 'Qwen3-8B-Thinking',
  provider: 'qwen',
  avgScore: 5.0,
  costPerCall: 0.00434,
  avgLatencyMs: 2400,
  contextLength: 256000,
  supportsPdf: true,
  bestFor: [],
  auditWins: 4,
  perfectScores: 1,
  avoid: true,
  avoidReason: '20x more expensive than Qwen3-30B with same or lower accuracy',
};

/**
 * Qwen 2.5 VL 72B
 *
 * Budget fallback - cheapest option.
 * - Avg Score: 4.8/10
 * - Cost: $0.00012/call (cheapest)
 */
export const QWEN2_5_72B: VLMModel = {
  id: 'qwen/qwen2.5-vl-72b-instruct',
  name: 'Qwen2.5-72B',
  provider: 'qwen',
  avgScore: 4.8,
  costPerCall: 0.00012,
  avgLatencyMs: 2200,
  contextLength: 32768,
  supportsPdf: true,
  bestFor: ['nameplate'],
  auditWins: 3,
  perfectScores: 1,
  avoid: false,
};

/**
 * GLM-4.6V (Zhipu AI)
 *
 * Specialist for reference charts and pitch tables.
 * - Best at reading charts: 6/10 vs 3/10 for other models
 * - Cost: $0.00110/call
 */
export const GLM_4_6V: VLMModel = {
  id: 'z-ai/glm-4.6v',
  name: 'GLM-4.6V',
  provider: 'glm',
  avgScore: 4.7,
  costPerCall: 0.00110,
  avgLatencyMs: 2800,
  contextLength: 128000,
  supportsPdf: false,
  bestFor: ['reference_chart', 'symbol_legend'],
  auditWins: 4,
  perfectScores: 2,
  avoid: false,
};

/**
 * Claude 3.5 Haiku - Last Resort Fallback
 *
 * Proven reliable, but much more expensive.
 * Use only when all Chinese VLMs fail.
 *
 * IMPORTANT: Uses direct Anthropic API (not OpenRouter)
 * - Direct API provides better rate limits and reliability
 * - Requires ANTHROPIC_API_KEY environment variable
 * - Model ID for Anthropic API: claude-3-5-haiku-20241022
 *
 * Verified Score: 10/10 on electrical blueprint test (2025-12-13)
 */
export const CLAUDE_HAIKU: VLMModel = {
  id: 'claude-3-5-haiku-20241022', // Direct Anthropic API model ID
  name: 'Claude Haiku 3.5',
  provider: 'anthropic', // Uses direct Anthropic API, not OpenRouter
  avgScore: 10.0, // Verified 10/10 on electrical blueprint
  costPerCall: 0.02000,
  avgLatencyMs: 1500,
  contextLength: 200000,
  supportsPdf: true,
  bestFor: ['blueprint', 'field_photo', 'nameplate', 'reference_chart'],
  auditWins: 1, // Verified perfect score
  perfectScores: 1,
  avoid: false,
};

/**
 * All registered models
 */
export const MODEL_REGISTRY: VLMModel[] = [
  QWEN_30B,
  QWEN_VL_MAX,
  QWEN_8B_THINKING,
  QWEN2_5_72B,
  GLM_4_6V,
  CLAUDE_HAIKU,
];

/**
 * Get a model by ID
 */
export function getModelById(modelId: string): VLMModel | undefined {
  return MODEL_REGISTRY.find(m => m.id === modelId);
}

/**
 * Get all non-avoided models
 */
export function getRecommendedModels(): VLMModel[] {
  return MODEL_REGISTRY.filter(m => !m.avoid);
}

/**
 * Get models sorted by score (descending)
 */
export function getModelsByScore(): VLMModel[] {
  return [...MODEL_REGISTRY]
    .filter(m => !m.avoid)
    .sort((a, b) => b.avgScore - a.avgScore);
}

/**
 * Get models sorted by cost (ascending)
 */
export function getModelsByCost(): VLMModel[] {
  return [...MODEL_REGISTRY]
    .filter(m => !m.avoid)
    .sort((a, b) => a.costPerCall - b.costPerCall);
}

/**
 * Get the best model for an image type
 */
export function getBestModelForImageType(imageType: string): VLMModel {
  // Reference charts: GLM-4.6V is the specialist
  if (imageType === 'reference_chart' || imageType === 'symbol_legend') {
    return GLM_4_6V;
  }

  // Everything else: Qwen3-30B is the audit winner
  return QWEN_30B;
}

/**
 * Audit statistics summary
 */
export const AUDIT_SUMMARY: AuditStats = {
  totalTests: 216,
  jsonSuccessRate: 0.95,
  winCount: 29, // Total 8+ scores across all models
  perfectCount: 15, // Total 10/10 scores
  avgScore: 5.18,
  avgCost: 0.00129,
  avgLatency: 2260,
  tradeBreakdown: {
    roofing: { tests: 40, avgScore: 5.8, wins: 5 },
    electrical: { tests: 40, avgScore: 6.2, wins: 7 },
    hvac: { tests: 35, avgScore: 5.5, wins: 4 },
    solar: { tests: 40, avgScore: 6.5, wins: 8 },
    plumbing: { tests: 40, avgScore: 4.8, wins: 3 },
    general: { tests: 21, avgScore: 4.2, wins: 2 }, // Edge cases
  },
};

/**
 * Audit metadata
 */
export const AUDIT_METADATA = {
  date: '2025-12-13',
  version: '3.0 FINAL',
  totalTests: 216,
  totalCost: 0.28,
  trades: ['roofing', 'electrical', 'hvac', 'solar', 'plumbing'] as Trade[],
  winner: QWEN_30B.id,
  costAdvantage: '10-150x cheaper than GPT-4V/Claude',
};
