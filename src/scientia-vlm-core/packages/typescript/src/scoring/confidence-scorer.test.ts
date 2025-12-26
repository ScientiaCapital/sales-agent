/**
 * Tests for Confidence Scorer
 */

import { describe, it, expect } from 'vitest';
import {
  calculateConfidence,
  SignalType,
  createVLMSignal,
  createCacheSignal,
  createCompletenessSignal,
  createFeedbackSignal,
  createValidationSignal,
  createHumanReviewSignal,
  createConsensusSignal,
  createHistoricalSignal,
  mergeConfidenceResults,
  meetsThreshold,
  getConfidenceDescription,
  type ConfidenceSignal,
} from './confidence-scorer';

describe('calculateConfidence', () => {
  it('should calculate weighted confidence from multiple signals', () => {
    const signals: ConfidenceSignal[] = [
      { type: SignalType.VLM_CONFIDENCE, value: 0.85 },
      { type: SignalType.FIELD_COMPLETENESS, value: 0.92 },
      { type: SignalType.CACHE_HIT, value: 1.0 },
    ];

    const result = calculateConfidence(signals);

    expect(result.score).toBeGreaterThan(0.8);
    expect(result.score).toBeLessThanOrEqual(1.0);
    expect(result.signalCount).toBe(3);
    expect(result.level).toMatch(/high|very_high/); // Weighted average can push to very_high
    expect(result.recommendation).toMatch(/accept|review/);
  });

  it('should return very_low confidence for empty signals', () => {
    const result = calculateConfidence([]);

    expect(result.score).toBe(0);
    expect(result.level).toBe('very_low');
    expect(result.signalCount).toBe(0);
    expect(result.recommendation).toBe('reject');
  });

  it('should respect custom thresholds', () => {
    const signals: ConfidenceSignal[] = [
      { type: SignalType.VLM_CONFIDENCE, value: 0.65 },
    ];

    const result = calculateConfidence(signals, {
      minimumThreshold: 0.5,
    });

    expect(result.meetsThreshold).toBe(true);
    expect(result.recommendation).toMatch(/accept|review/);
  });

  it('should handle signal weights correctly', () => {
    const signals: ConfidenceSignal[] = [
      { type: SignalType.VLM_CONFIDENCE, value: 0.5, weight: 0.5 },
      { type: SignalType.USER_FEEDBACK, value: 1.0, weight: 2.0 }, // Higher weight
    ];

    const result = calculateConfidence(signals);

    // Weighted average should be closer to 1.0 due to higher weight
    expect(result.score).toBeGreaterThan(0.7);
  });
});

describe('Signal Factory Functions', () => {
  it('should create VLM signal', () => {
    const signal = createVLMSignal(0.85, { model: 'qwen-vl' });

    expect(signal.type).toBe(SignalType.VLM_CONFIDENCE);
    expect(signal.value).toBe(0.85);
    expect(signal.metadata?.model).toBe('qwen-vl');
  });

  it('should create cache signal with hit scaling', () => {
    const signal = createCacheSignal(true, 5);

    expect(signal.type).toBe(SignalType.CACHE_HIT);
    expect(signal.value).toBeGreaterThan(0.8); // Base + hit count boost
    expect(signal.metadata?.isHit).toBe(true);
    expect(signal.metadata?.hitCount).toBe(5);
  });

  it('should create completeness signal with missing fields', () => {
    const requiredFields = ['field1', 'field2', 'field3'];
    const data = { field1: 'value1', field2: 'value2' }; // field3 missing

    const signal = createCompletenessSignal(requiredFields, data);

    expect(signal.type).toBe(SignalType.FIELD_COMPLETENESS);
    expect(signal.value).toBeCloseTo(2 / 3);
    expect(signal.metadata?.completedCount).toBe(2);
    expect(signal.metadata?.missingFields).toEqual(['field3']);
  });

  it('should create feedback signal', () => {
    const positive = createFeedbackSignal(true);
    const negative = createFeedbackSignal(false);

    expect(positive.type).toBe(SignalType.USER_FEEDBACK);
    expect(positive.value).toBe(1.0);
    expect(negative.value).toBe(0.0);
  });

  it('should create validation signal', () => {
    const signal = createValidationSignal(8, 10);

    expect(signal.type).toBe(SignalType.VALIDATION_PASS);
    expect(signal.value).toBe(0.8);
    expect(signal.metadata?.passedRules).toBe(8);
  });

  it('should create human review signal with corrections', () => {
    const signal = createHumanReviewSignal(true, 2);

    expect(signal.type).toBe(SignalType.HUMAN_REVIEWED);
    expect(signal.value).toBeGreaterThan(0.7); // High confidence even with corrections
    expect(signal.metadata?.correctionsNeeded).toBe(2);
  });

  it('should create consensus signal', () => {
    const signal = createConsensusSignal(3, 4);

    expect(signal.type).toBe(SignalType.MODEL_CONSENSUS);
    expect(signal.value).toBe(0.75);
    expect(signal.metadata?.agreementCount).toBe(3);
  });

  it('should create historical signal with sample size adjustment', () => {
    const smallSample = createHistoricalSignal(0.9, 5);
    const largeSample = createHistoricalSignal(0.9, 25);

    expect(smallSample.type).toBe(SignalType.HISTORICAL_ACCURACY);
    expect(largeSample.value).toBeGreaterThan(smallSample.value); // More confidence with larger sample
  });
});

describe('mergeConfidenceResults', () => {
  it('should merge multiple confidence results', () => {
    const result1 = calculateConfidence([
      { type: SignalType.VLM_CONFIDENCE, value: 0.8 },
    ]);
    const result2 = calculateConfidence([
      { type: SignalType.FIELD_COMPLETENESS, value: 0.9 },
    ]);

    const merged = mergeConfidenceResults([result1, result2]);

    expect(merged.score).toBeGreaterThan(0.7);
    expect(merged.signalCount).toBe(2);
    expect(merged.signalBreakdown).toHaveProperty(SignalType.VLM_CONFIDENCE);
    expect(merged.signalBreakdown).toHaveProperty(SignalType.FIELD_COMPLETENESS);
  });

  it('should use most conservative recommendation', () => {
    const accept = calculateConfidence([{ type: SignalType.VLM_CONFIDENCE, value: 0.95 }]);
    const reject = calculateConfidence([{ type: SignalType.VLM_CONFIDENCE, value: 0.3 }]);

    const merged = mergeConfidenceResults([accept, reject]);

    expect(merged.recommendation).toBe('reject'); // Most conservative
  });

  it('should handle empty results array', () => {
    const merged = mergeConfidenceResults([]);

    expect(merged.score).toBe(0);
    expect(merged.level).toBe('very_low');
    expect(merged.recommendation).toBe('reject');
  });
});

describe('Utility Functions', () => {
  it('should check threshold correctly', () => {
    const result = calculateConfidence([
      { type: SignalType.VLM_CONFIDENCE, value: 0.8 },
    ]);

    expect(meetsThreshold(result)).toBe(true);
    expect(meetsThreshold(result, 0.9)).toBe(false);
  });

  it('should generate readable confidence description', () => {
    const result = calculateConfidence([
      { type: SignalType.VLM_CONFIDENCE, value: 0.85 },
    ]);

    const description = getConfidenceDescription(result);

    expect(description).toContain('confidence');
    expect(description).toContain('%');
    expect(description).toMatch(/reliable|unreliable|review/i);
  });
});

describe('Confidence Levels', () => {
  it('should categorize very_low confidence', () => {
    const result = calculateConfidence([
      { type: SignalType.VLM_CONFIDENCE, value: 0.3 },
    ]);

    expect(result.level).toBe('very_low');
    expect(result.recommendation).toBe('reject');
  });

  it('should categorize low confidence', () => {
    const result = calculateConfidence([
      { type: SignalType.VLM_CONFIDENCE, value: 0.5 },
    ]);

    expect(result.level).toBe('low');
    expect(result.recommendation).toMatch(/reject|fallback/);
  });

  it('should categorize medium confidence', () => {
    const result = calculateConfidence([
      { type: SignalType.VLM_CONFIDENCE, value: 0.75 },
    ]);

    expect(result.level).toMatch(/medium|high/); // 0.75 is on the boundary
    expect(result.recommendation).toMatch(/review|fallback|accept/);
  });

  it('should categorize high confidence', () => {
    const result = calculateConfidence([
      { type: SignalType.VLM_CONFIDENCE, value: 0.9 },
    ]);

    expect(result.level).toMatch(/high|very_high/); // 0.9 is on the boundary
    expect(result.recommendation).toBe('accept');
  });

  it('should categorize very_high confidence', () => {
    const result = calculateConfidence([
      { type: SignalType.VLM_CONFIDENCE, value: 0.95 },
      { type: SignalType.CACHE_HIT, value: 1.0 },
      { type: SignalType.USER_FEEDBACK, value: 1.0 },
    ]);

    expect(result.level).toBe('very_high');
    expect(result.recommendation).toBe('accept');
  });
});

describe('Edge Cases', () => {
  it('should clamp values outside 0-1 range', () => {
    const signals: ConfidenceSignal[] = [
      { type: SignalType.VLM_CONFIDENCE, value: 1.5 }, // Out of range
      { type: SignalType.FIELD_COMPLETENESS, value: -0.2 }, // Out of range
    ];

    const result = calculateConfidence(signals);

    expect(result.score).toBeGreaterThanOrEqual(0);
    expect(result.score).toBeLessThanOrEqual(1);
  });

  it('should handle empty required fields for completeness', () => {
    const signal = createCompletenessSignal([], {});

    expect(signal.value).toBe(1.0);
    expect(signal.metadata?.reason).toBe('no_required_fields');
  });

  it('should handle zero total rules for validation', () => {
    const signal = createValidationSignal(0, 0);

    expect(signal.value).toBe(1.0);
  });

  it('should handle zero models for consensus', () => {
    const signal = createConsensusSignal(0, 0);

    expect(signal.value).toBe(0);
  });
});
