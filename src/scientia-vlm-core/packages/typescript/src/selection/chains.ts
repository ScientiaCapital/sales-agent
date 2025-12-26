/**
 * VLM Fallback Chains
 *
 * Defines the fallback sequences for different image types.
 * Based on empirical audit data from 216 tests (2025-12-13).
 *
 * Key findings:
 * - Qwen3-30B is the best overall model (5.9/10 avg, $0.00022/call)
 * - GLM-4.6V excels at reference charts (6/10 vs 3/10 for others)
 * - Qwen3-8B-Thinking should be AVOIDED (20x cost, lower accuracy)
 *
 * @module @scientia/vlm-core/selection
 * @version 1.0.0
 * @license Proprietary - Scientia Capital
 */

import type { FallbackChain, ImageType } from '../models/types';

/**
 * Model IDs (OpenRouter format)
 */
export const MODEL_IDS = {
  // Primary - Audit winner
  QWEN_30B: 'qwen/qwen3-vl-30b-a3b-instruct',

  // Secondary - High accuracy fallback
  QWEN_VL_MAX: 'qwen/qwen-vl-max',

  // Tertiary - Budget fallback
  QWEN2_5_72B: 'qwen/qwen2.5-vl-72b-instruct',

  // Reference charts specialist
  GLM_4_6V: 'z-ai/glm-4.6v',

  // Last resort - Proven reliable
  CLAUDE_HAIKU: 'anthropic/claude-3-5-haiku-20241022',

  // AVOID - Too expensive for accuracy
  QWEN_8B_THINKING: 'qwen/qwen3-vl-8b-thinking',
} as const;

/**
 * Cost per call (USD) - from audit
 */
export const MODEL_COSTS: Record<string, number> = {
  [MODEL_IDS.QWEN_30B]: 0.00022,
  [MODEL_IDS.QWEN_VL_MAX]: 0.00073,
  [MODEL_IDS.QWEN2_5_72B]: 0.00012,
  [MODEL_IDS.GLM_4_6V]: 0.00110,
  [MODEL_IDS.CLAUDE_HAIKU]: 0.02000,
  [MODEL_IDS.QWEN_8B_THINKING]: 0.00434, // AVOID
};

/**
 * Blueprint Analysis Chain
 *
 * For construction blueprints, floor plans, and technical drawings.
 * Primary: Qwen3-30B (best accuracy/cost ratio)
 * Fallback: Qwen-VL-Max → Claude Haiku
 */
export const BLUEPRINT_CHAIN: FallbackChain = {
  id: 'blueprint',
  name: 'Blueprint Analysis Chain',
  targetImageTypes: ['blueprint'],
  models: [
    MODEL_IDS.QWEN_30B,
    MODEL_IDS.QWEN_VL_MAX,
    MODEL_IDS.CLAUDE_HAIKU,
  ],
  fallbackThreshold: 0.6,
  maxCost: 0.00022 + 0.00073 + 0.02, // $0.02295 worst case
};

/**
 * Field Photo Chain
 *
 * For equipment photos, installation shots, and site assessments.
 * Primary: Qwen3-30B (best at visual context)
 * Fallback: Qwen-VL-Max → Qwen2.5-72B (cheap nameplate OCR)
 */
export const FIELD_PHOTO_CHAIN: FallbackChain = {
  id: 'field_photo',
  name: 'Field Photo Chain',
  targetImageTypes: ['field_photo', 'nameplate'],
  models: [
    MODEL_IDS.QWEN_30B,
    MODEL_IDS.QWEN_VL_MAX,
    MODEL_IDS.QWEN2_5_72B,
  ],
  fallbackThreshold: 0.5,
  maxCost: 0.00022 + 0.00073 + 0.00012, // $0.00107 worst case
};

/**
 * Reference Chart Chain
 *
 * For pitch charts, symbol legends, and reference tables.
 * Primary: GLM-4.6V (best at reading charts - 6/10 vs 3/10)
 * Fallback: Qwen3-30B → Qwen-VL-Max
 */
export const REFERENCE_CHART_CHAIN: FallbackChain = {
  id: 'reference_chart',
  name: 'Reference Chart Chain',
  targetImageTypes: ['reference_chart', 'symbol_legend'],
  models: [
    MODEL_IDS.GLM_4_6V,
    MODEL_IDS.QWEN_30B,
    MODEL_IDS.QWEN_VL_MAX,
  ],
  fallbackThreshold: 0.5,
  maxCost: 0.00110 + 0.00022 + 0.00073, // $0.00205 worst case
};

/**
 * Default Chain
 *
 * General-purpose fallback for unknown image types.
 * Uses the audit-winning model with standard fallbacks.
 */
export const DEFAULT_CHAIN: FallbackChain = {
  id: 'default',
  name: 'Default Analysis Chain',
  targetImageTypes: ['blueprint', 'field_photo', 'nameplate', 'reference_chart', 'symbol_legend'],
  models: [
    MODEL_IDS.QWEN_30B,
    MODEL_IDS.QWEN_VL_MAX,
    MODEL_IDS.QWEN2_5_72B,
    MODEL_IDS.CLAUDE_HAIKU,
  ],
  fallbackThreshold: 0.6,
  maxCost: 0.00022 + 0.00073 + 0.00012 + 0.02, // $0.02107 worst case
};

/**
 * Get the appropriate fallback chain for an image type
 */
export function getChainForImageType(imageType: ImageType): FallbackChain {
  switch (imageType) {
    case 'blueprint':
      return BLUEPRINT_CHAIN;

    case 'field_photo':
    case 'nameplate':
      return FIELD_PHOTO_CHAIN;

    case 'reference_chart':
    case 'symbol_legend':
      return REFERENCE_CHART_CHAIN;

    default:
      return DEFAULT_CHAIN;
  }
}

/**
 * Get estimated cost for a chain (primary model only)
 */
export function getPrimaryCost(chain: FallbackChain): number {
  const primaryModelId = chain.models[0];
  return MODEL_COSTS[primaryModelId] ?? 0.001;
}

/**
 * Get worst-case cost for a chain (all fallbacks tried)
 */
export function getWorstCaseCost(chain: FallbackChain): number {
  return chain.maxCost;
}

/**
 * Check if a model should be avoided
 */
export function shouldAvoidModel(modelId: string): boolean {
  return modelId === MODEL_IDS.QWEN_8B_THINKING;
}

/**
 * Get avoid reason for a model
 */
export function getAvoidReason(modelId: string): string | undefined {
  if (modelId === MODEL_IDS.QWEN_8B_THINKING) {
    return '20x more expensive than Qwen3-30B with same or lower accuracy per 216-test audit';
  }
  return undefined;
}

/**
 * All available chains
 */
export const ALL_CHAINS: FallbackChain[] = [
  BLUEPRINT_CHAIN,
  FIELD_PHOTO_CHAIN,
  REFERENCE_CHART_CHAIN,
  DEFAULT_CHAIN,
];
