/**
 * VLM Model Selection Algorithm
 *
 * Intelligent model selection based on empirical audit data.
 * This algorithm encodes the findings from 216 tests across 6 trades.
 *
 * MOAT: The selection logic represents defensible IP that gives
 * FieldVault a 10-150x cost advantage over competitors.
 *
 * @module @scientia/vlm-core/selection
 * @version 1.0.0
 * @license Proprietary - Scientia Capital
 */

import type { VLMModel, SelectionConfig, SelectionResult, Trade, ImageType } from '../models/types';
import {
  QWEN_30B,
  QWEN_VL_MAX,
  QWEN2_5_72B,
  GLM_4_6V,
  CLAUDE_HAIKU,
  getModelById,
  AUDIT_METADATA,
} from '../models/registry';
import { shouldAvoidModel } from './chains';

/**
 * Default configuration values
 */
const DEFAULTS = {
  confidenceThreshold: 0.6,
  maxCost: 0.05, // $0.05 max per analysis
  preferSpeed: false,
};

/**
 * Select the optimal model for a given analysis task
 *
 * Algorithm:
 * 1. If forceModel is specified, use that (bypass selection)
 * 2. If imageType is reference_chart/symbol_legend, use GLM-4.6V
 * 3. Otherwise, use Qwen3-30B (audit winner)
 *
 * @param config - Selection configuration
 * @returns Selection result with model, fallback chain, and reasoning
 */
export function selectModel(config: SelectionConfig = {}): SelectionResult {
  const {
    trade,
    imageType,
    maxCost = DEFAULTS.maxCost,
    preferSpeed = DEFAULTS.preferSpeed,
    forceModel,
  } = config;

  // Check for forced model
  if (forceModel) {
    return handleForcedModel(forceModel, trade, imageType);
  }

  // Check for avoided models in budget constraint
  if (maxCost < 0.001) {
    // Budget mode: use cheapest model
    return selectBudgetModel(trade, imageType);
  }

  // Special case: Reference charts
  if (imageType === 'reference_chart' || imageType === 'symbol_legend') {
    return selectForReferenceChart(trade);
  }

  // Default: Use audit winner (Qwen3-30B)
  return selectDefault(trade, imageType, preferSpeed);
}

/**
 * Handle forced model selection
 */
function handleForcedModel(
  modelId: string,
  _trade?: Trade,
  _imageType?: ImageType
): SelectionResult {
  const model = getModelById(modelId);

  if (!model) {
    // Fallback to default if model not found
    return selectDefault(_trade, _imageType, false);
  }

  // Warn if model should be avoided
  const warning = shouldAvoidModel(modelId)
    ? ' WARNING: This model should be avoided per audit results.'
    : '';

  return {
    model,
    fallbackChain: [QWEN_VL_MAX, QWEN2_5_72B, CLAUDE_HAIKU],
    prompt: '', // Prompt should be set by caller based on trade
    estimatedCost: model.costPerCall,
    reasoning: `Forced selection: ${model.name}.${warning}`,
    auditBasis: {
      auditDate: AUDIT_METADATA.date,
      totalTests: AUDIT_METADATA.totalTests,
      winRate: model.auditWins / 43, // ~43 tests per model
    },
  };
}

/**
 * Budget mode: Select cheapest viable model
 */
function selectBudgetModel(_trade?: Trade, _imageType?: ImageType): SelectionResult {
  return {
    model: QWEN2_5_72B,
    fallbackChain: [QWEN_30B, QWEN_VL_MAX],
    prompt: '',
    estimatedCost: QWEN2_5_72B.costPerCall,
    reasoning: 'Budget mode: Qwen2.5-72B is the cheapest model ($0.00012/call)',
    auditBasis: {
      auditDate: AUDIT_METADATA.date,
      totalTests: AUDIT_METADATA.totalTests,
      winRate: QWEN2_5_72B.auditWins / 43,
    },
  };
}

/**
 * Select model for reference charts (GLM-4.6V specialist)
 */
function selectForReferenceChart(_trade?: Trade): SelectionResult {
  return {
    model: GLM_4_6V,
    fallbackChain: [QWEN_30B, QWEN_VL_MAX],
    prompt: '',
    estimatedCost: GLM_4_6V.costPerCall,
    reasoning: 'GLM-4.6V excels at reference charts (6/10 vs 3/10 for others per audit)',
    auditBasis: {
      auditDate: AUDIT_METADATA.date,
      totalTests: AUDIT_METADATA.totalTests,
      winRate: GLM_4_6V.auditWins / 43,
    },
  };
}

/**
 * Default selection: Qwen3-30B (audit winner)
 */
function selectDefault(
  _trade?: Trade,
  _imageType?: ImageType,
  _preferSpeed?: boolean
): SelectionResult {
  return {
    model: QWEN_30B,
    fallbackChain: [QWEN_VL_MAX, QWEN2_5_72B, CLAUDE_HAIKU],
    prompt: '',
    estimatedCost: QWEN_30B.costPerCall,
    reasoning: `Qwen3-30B: Best accuracy/cost ratio per 216-test audit. ` +
      `Avg score: ${QWEN_30B.avgScore}/10, Cost: $${QWEN_30B.costPerCall}/call, ` +
      `${QWEN_30B.auditWins} wins, ${QWEN_30B.perfectScores} perfect scores.`,
    auditBasis: {
      auditDate: AUDIT_METADATA.date,
      totalTests: AUDIT_METADATA.totalTests,
      winRate: QWEN_30B.auditWins / 43,
    },
  };
}

/**
 * Execute analysis with automatic fallback
 *
 * Tries models in sequence until one succeeds with sufficient confidence.
 *
 * @param analyzeFunc - Function to call model API
 * @param selection - Selection result from selectModel()
 * @param config - Selection configuration
 * @returns Analysis result from first successful model
 */
export async function executeWithFallback<T>(
  analyzeFunc: (modelId: string) => Promise<{ result: T; confidence: number }>,
  selection: SelectionResult,
  config: SelectionConfig = {}
): Promise<{
  result: T;
  confidence: number;
  modelUsed: VLMModel;
  fallbacksUsed: number;
  totalCost: number;
}> {
  const { confidenceThreshold = DEFAULTS.confidenceThreshold } = config;

  const modelsToTry = [selection.model, ...selection.fallbackChain];
  let totalCost = 0;
  let lastError: Error | undefined;

  for (let i = 0; i < modelsToTry.length; i++) {
    const model = modelsToTry[i];
    totalCost += model.costPerCall;

    try {
      const { result, confidence } = await analyzeFunc(model.id);

      // Check confidence threshold
      if (confidence >= confidenceThreshold) {
        return {
          result,
          confidence,
          modelUsed: model,
          fallbacksUsed: i,
          totalCost,
        };
      }

      // Confidence too low, try next model
      console.warn(
        `[VLM Selection] ${model.name} confidence ${confidence.toFixed(2)} < threshold ${confidenceThreshold}, trying fallback...`
      );
    } catch (error) {
      lastError = error as Error;
      console.error(`[VLM Selection] ${model.name} failed:`, error);
    }
  }

  // All models failed
  throw new Error(
    `All models in fallback chain failed. Last error: ${lastError?.message ?? 'Unknown'}`
  );
}

/**
 * Get estimated cost for an analysis
 */
export function getEstimatedCost(config: SelectionConfig): number {
  const selection = selectModel(config);
  return selection.estimatedCost;
}

/**
 * Get worst-case cost for a selection (all fallbacks tried)
 */
export function getSelectionWorstCaseCost(config: SelectionConfig): number {
  const selection = selectModel(config);
  let total = selection.model.costPerCall;
  for (const model of selection.fallbackChain) {
    total += model.costPerCall;
  }
  return total;
}

/**
 * Validate that a model ID is in the registry
 */
export function isValidModelId(modelId: string): boolean {
  return getModelById(modelId) !== undefined;
}

/**
 * Get recommendation summary for logging/debugging
 */
export function getRecommendationSummary(config: SelectionConfig): string {
  const selection = selectModel(config);
  return [
    `Model: ${selection.model.name} (${selection.model.id})`,
    `Cost: $${selection.estimatedCost.toFixed(5)}`,
    `Fallbacks: ${selection.fallbackChain.map(m => m.name).join(' → ')}`,
    `Reasoning: ${selection.reasoning}`,
  ].join('\n');
}
