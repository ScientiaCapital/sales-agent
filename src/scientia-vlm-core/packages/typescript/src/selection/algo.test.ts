/**
 * VLM Model Selection Algorithm Tests
 *
 * Comprehensive unit tests for the selection algorithm based on 216-test audit.
 * Tests cover: selectModel(), executeWithFallback(), cost functions, edge cases.
 *
 * @module @scientia/vlm-core/selection
 * @version 1.0.0
 * @license Proprietary - Scientia Capital
 */

import { describe, it, expect, vi } from 'vitest';
import {
  selectModel,
  executeWithFallback,
  getEstimatedCost,
  getSelectionWorstCaseCost,
  isValidModelId,
  getRecommendationSummary,
} from './algo';
import { MODEL_IDS, shouldAvoidModel } from './chains';
import { QWEN_30B, GLM_4_6V, QWEN2_5_72B, CLAUDE_HAIKU } from '../models/registry';

describe('selectModel()', () => {
  describe('default selection', () => {
    it('returns Qwen3-30B as default model with no config', () => {
      const result = selectModel();
      expect(result.model.id).toBe(MODEL_IDS.QWEN_30B);
      expect(result.reasoning).toContain('Qwen3-30B');
    });

    it('returns Qwen3-30B for blueprint image type', () => {
      const result = selectModel({ imageType: 'blueprint', trade: 'roofing' });
      expect(result.model.id).toBe(MODEL_IDS.QWEN_30B);
    });

    it('returns Qwen3-30B for field_photo image type', () => {
      const result = selectModel({ imageType: 'field_photo', trade: 'hvac' });
      expect(result.model.id).toBe(MODEL_IDS.QWEN_30B);
    });

    it('includes fallback chain with Qwen-VL-Max, Qwen2.5-72B, Claude Haiku', () => {
      const result = selectModel();
      const fallbackIds = result.fallbackChain.map(m => m.id);
      expect(fallbackIds).toContain(MODEL_IDS.QWEN_VL_MAX);
      expect(fallbackIds).toContain(MODEL_IDS.QWEN2_5_72B);
      expect(fallbackIds).toContain(MODEL_IDS.CLAUDE_HAIKU);
    });
  });

  describe('forced model selection', () => {
    it('uses forced model when forceModel is specified', () => {
      const result = selectModel({ forceModel: MODEL_IDS.CLAUDE_HAIKU });
      expect(result.model.id).toBe(MODEL_IDS.CLAUDE_HAIKU);
      expect(result.reasoning).toContain('Forced selection');
    });

    it('falls back to default when forceModel is invalid', () => {
      const result = selectModel({ forceModel: 'invalid/model-id' });
      expect(result.model.id).toBe(MODEL_IDS.QWEN_30B);
    });

    it('adds warning when forcing an avoided model', () => {
      const result = selectModel({ forceModel: MODEL_IDS.QWEN_8B_THINKING });
      expect(result.reasoning).toContain('WARNING');
      expect(result.reasoning).toContain('should be avoided');
    });
  });

  describe('budget mode selection', () => {
    it('selects Qwen2.5-72B when maxCost < 0.001', () => {
      const result = selectModel({ maxCost: 0.0005 });
      expect(result.model.id).toBe(MODEL_IDS.QWEN2_5_72B);
      expect(result.reasoning).toContain('Budget mode');
    });

    it('returns cheaper fallback chain in budget mode', () => {
      const result = selectModel({ maxCost: 0.0005 });
      // Budget chain should not include expensive Claude Haiku
      const fallbackIds = result.fallbackChain.map(m => m.id);
      expect(fallbackIds).not.toContain(MODEL_IDS.CLAUDE_HAIKU);
    });
  });

  describe('reference chart selection', () => {
    it('selects GLM-4.6V for reference_chart image type', () => {
      const result = selectModel({ imageType: 'reference_chart' });
      expect(result.model.id).toBe(MODEL_IDS.GLM_4_6V);
      expect(result.reasoning).toContain('GLM-4.6V');
      expect(result.reasoning).toContain('6/10 vs 3/10');
    });

    it('selects GLM-4.6V for symbol_legend image type', () => {
      const result = selectModel({ imageType: 'symbol_legend' });
      expect(result.model.id).toBe(MODEL_IDS.GLM_4_6V);
    });

    it('includes Qwen models as fallbacks for reference charts', () => {
      const result = selectModel({ imageType: 'reference_chart' });
      const fallbackIds = result.fallbackChain.map(m => m.id);
      expect(fallbackIds).toContain(MODEL_IDS.QWEN_30B);
    });
  });

  describe('audit basis metadata', () => {
    it('includes audit date in result', () => {
      const result = selectModel();
      expect(result.auditBasis.auditDate).toBe('2025-12-13');
    });

    it('includes total test count in result', () => {
      const result = selectModel();
      expect(result.auditBasis.totalTests).toBe(216);
    });

    it('includes win rate in result', () => {
      const result = selectModel();
      expect(result.auditBasis.winRate).toBeGreaterThan(0);
    });
  });
});

describe('executeWithFallback()', () => {
  it('returns result from primary model when confidence is high', async () => {
    const selection = selectModel();
    const mockAnalyze = vi.fn().mockResolvedValue({ result: { data: 'test' }, confidence: 0.9 });

    const output = await executeWithFallback(mockAnalyze, selection);

    expect(output.result).toEqual({ data: 'test' });
    expect(output.confidence).toBe(0.9);
    expect(output.modelUsed.id).toBe(QWEN_30B.id);
    expect(output.fallbacksUsed).toBe(0);
    expect(mockAnalyze).toHaveBeenCalledTimes(1);
  });

  it('falls back when primary model confidence is below threshold', async () => {
    const selection = selectModel();
    const mockAnalyze = vi.fn()
      .mockResolvedValueOnce({ result: { data: 'low' }, confidence: 0.3 })
      .mockResolvedValueOnce({ result: { data: 'high' }, confidence: 0.8 });

    const output = await executeWithFallback(mockAnalyze, selection);

    expect(output.result).toEqual({ data: 'high' });
    expect(output.fallbacksUsed).toBe(1);
    expect(mockAnalyze).toHaveBeenCalledTimes(2);
  });

  it('uses custom confidence threshold when provided', async () => {
    const selection = selectModel();
    const mockAnalyze = vi.fn().mockResolvedValue({ result: { data: 'test' }, confidence: 0.5 });

    const output = await executeWithFallback(mockAnalyze, selection, { confidenceThreshold: 0.4 });

    expect(output.confidence).toBe(0.5);
    expect(output.fallbacksUsed).toBe(0);
  });

  it('falls back when primary model throws an error', async () => {
    const selection = selectModel();
    const mockAnalyze = vi.fn()
      .mockRejectedValueOnce(new Error('API error'))
      .mockResolvedValueOnce({ result: { data: 'fallback' }, confidence: 0.8 });

    const output = await executeWithFallback(mockAnalyze, selection);

    expect(output.result).toEqual({ data: 'fallback' });
    expect(output.fallbacksUsed).toBe(1);
  });

  it('throws error when all models fail', async () => {
    const selection = selectModel();
    const mockAnalyze = vi.fn().mockRejectedValue(new Error('All failed'));

    await expect(executeWithFallback(mockAnalyze, selection)).rejects.toThrow('All models in fallback chain failed');
  });

  it('accumulates total cost across all models tried', async () => {
    const selection = selectModel();
    const mockAnalyze = vi.fn()
      .mockResolvedValueOnce({ result: {}, confidence: 0.3 })
      .mockResolvedValueOnce({ result: {}, confidence: 0.3 })
      .mockResolvedValueOnce({ result: {}, confidence: 0.9 });

    const output = await executeWithFallback(mockAnalyze, selection);

    // Cost should include primary + 2 fallbacks
    expect(output.totalCost).toBeGreaterThan(selection.model.costPerCall);
    expect(output.fallbacksUsed).toBe(2);
  });
});

describe('cost functions', () => {
  describe('getEstimatedCost()', () => {
    it('returns primary model cost for default selection', () => {
      const cost = getEstimatedCost({});
      expect(cost).toBe(QWEN_30B.costPerCall);
    });

    it('returns GLM-4.6V cost for reference charts', () => {
      const cost = getEstimatedCost({ imageType: 'reference_chart' });
      expect(cost).toBe(GLM_4_6V.costPerCall);
    });

    it('returns Qwen2.5-72B cost in budget mode', () => {
      const cost = getEstimatedCost({ maxCost: 0.0005 });
      expect(cost).toBe(QWEN2_5_72B.costPerCall);
    });
  });

  describe('getSelectionWorstCaseCost()', () => {
    it('returns sum of primary + all fallback costs', () => {
      const worstCase = getSelectionWorstCaseCost({});
      const selection = selectModel();

      let expectedTotal = selection.model.costPerCall;
      for (const model of selection.fallbackChain) {
        expectedTotal += model.costPerCall;
      }

      expect(worstCase).toBeCloseTo(expectedTotal, 5);
    });

    it('worst case cost is greater than estimated cost', () => {
      const estimated = getEstimatedCost({});
      const worstCase = getSelectionWorstCaseCost({});
      expect(worstCase).toBeGreaterThan(estimated);
    });
  });
});

describe('validation functions', () => {
  describe('isValidModelId()', () => {
    it('returns true for valid model IDs', () => {
      expect(isValidModelId(MODEL_IDS.QWEN_30B)).toBe(true);
      expect(isValidModelId(MODEL_IDS.GLM_4_6V)).toBe(true);
      expect(isValidModelId(MODEL_IDS.CLAUDE_HAIKU)).toBe(true);
    });

    it('returns false for invalid model IDs', () => {
      expect(isValidModelId('invalid/model')).toBe(false);
      expect(isValidModelId('')).toBe(false);
      expect(isValidModelId('openai/gpt-4')).toBe(false);
    });
  });

  describe('shouldAvoidModel()', () => {
    it('returns true for Qwen3-8B-Thinking', () => {
      expect(shouldAvoidModel(MODEL_IDS.QWEN_8B_THINKING)).toBe(true);
    });

    it('returns false for recommended models', () => {
      expect(shouldAvoidModel(MODEL_IDS.QWEN_30B)).toBe(false);
      expect(shouldAvoidModel(MODEL_IDS.GLM_4_6V)).toBe(false);
    });
  });
});

describe('getRecommendationSummary()', () => {
  it('includes model name in summary', () => {
    const summary = getRecommendationSummary({});
    expect(summary).toContain('Qwen3-30B');
  });

  it('includes cost in summary', () => {
    const summary = getRecommendationSummary({});
    expect(summary).toContain('Cost');
    expect(summary).toContain('$');
  });

  it('includes fallback chain in summary', () => {
    const summary = getRecommendationSummary({});
    expect(summary).toContain('Fallbacks');
    expect(summary).toContain('→');
  });

  it('includes reasoning in summary', () => {
    const summary = getRecommendationSummary({});
    expect(summary).toContain('Reasoning');
  });
});

describe('edge cases', () => {
  it('handles undefined config values gracefully', () => {
    const result = selectModel({
      trade: undefined,
      imageType: undefined,
      maxCost: undefined,
    });
    expect(result.model).toBeDefined();
  });

  it('handles empty string trade', () => {
    const result = selectModel({ trade: '' as any });
    expect(result.model.id).toBe(MODEL_IDS.QWEN_30B);
  });

  it('handles unknown image type', () => {
    const result = selectModel({ imageType: 'unknown' as any });
    expect(result.model.id).toBe(MODEL_IDS.QWEN_30B);
  });

  it('cost is always a positive number', () => {
    const configs = [
      {},
      { imageType: 'blueprint' as const },
      { imageType: 'reference_chart' as const },
      { maxCost: 0.0001 },
    ];

    for (const config of configs) {
      const cost = getEstimatedCost(config);
      expect(cost).toBeGreaterThan(0);
    }
  });

  it('selection always has at least one fallback model', () => {
    const configs = [
      {},
      { imageType: 'blueprint' as const },
      { imageType: 'reference_chart' as const },
      { maxCost: 0.0001 },
    ];

    for (const config of configs) {
      const result = selectModel(config);
      expect(result.fallbackChain.length).toBeGreaterThan(0);
    }
  });
});
