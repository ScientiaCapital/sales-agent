/**
 * Confidence Scoring Module (GAP-8)
 * Multi-signal confidence aggregation for VLM extractions
 *
 * Features:
 * - Dynamic confidence calculation (0-1 range)
 * - Multiple signal types with weighted aggregation
 * - Configurable thresholds per use case
 * - Confidence-driven fallback decisions
 */

/**
 * Types of confidence signals
 */
export enum SignalType {
  /** VLM-reported confidence score */
  VLM_CONFIDENCE = 'vlm_confidence',
  /** Cache hit indicates validated extraction */
  CACHE_HIT = 'cache_hit',
  /** Extraction field completeness */
  FIELD_COMPLETENESS = 'field_completeness',
  /** User feedback (thumbs up/down) */
  USER_FEEDBACK = 'user_feedback',
  /** Validation rule pass rate */
  VALIDATION_PASS = 'validation_pass',
  /** Human review/correction applied */
  HUMAN_REVIEWED = 'human_reviewed',
  /** Multi-model consensus */
  MODEL_CONSENSUS = 'model_consensus',
  /** Historical accuracy for similar cases */
  HISTORICAL_ACCURACY = 'historical_accuracy',
}

/**
 * Single confidence signal input
 */
export interface ConfidenceSignal {
  /** Type of signal */
  type: SignalType;
  /** Signal value (0-1 range) */
  value: number;
  /** Signal weight (0-1 range, defaults to 1.0) */
  weight?: number;
  /** Optional metadata about the signal */
  metadata?: Record<string, unknown>;
}

/**
 * Result of confidence calculation
 */
export interface ConfidenceResult {
  /** Final aggregated confidence score (0-1) */
  score: number;
  /** Confidence level category */
  level: 'very_low' | 'low' | 'medium' | 'high' | 'very_high';
  /** Number of signals used */
  signalCount: number;
  /** Breakdown by signal type */
  signalBreakdown: Record<string, number>;
  /** Whether score meets minimum threshold */
  meetsThreshold: boolean;
  /** Recommended action based on confidence */
  recommendation: 'accept' | 'review' | 'reject' | 'fallback';
}

/**
 * Configuration for confidence scoring
 */
export interface ConfidenceConfig {
  /**
   * Minimum acceptable confidence threshold
   * @default 0.75
   */
  minimumThreshold?: number;

  /**
   * Default weights for signal types
   * If not specified, defaults to equal weights
   */
  defaultWeights?: Partial<Record<SignalType, number>>;

  /**
   * Thresholds for confidence levels
   */
  levelThresholds?: {
    veryLow?: number;
    low?: number;
    medium?: number;
    high?: number;
  };

  /**
   * Whether to require minimum signal count
   * @default false
   */
  requireMinSignals?: boolean;

  /**
   * Minimum number of signals required
   * @default 2
   */
  minSignalCount?: number;
}

/**
 * Default configuration
 */
const DEFAULT_CONFIG: Required<ConfidenceConfig> = {
  minimumThreshold: 0.75,
  defaultWeights: {
    [SignalType.VLM_CONFIDENCE]: 1.0,
    [SignalType.CACHE_HIT]: 0.8,
    [SignalType.FIELD_COMPLETENESS]: 0.9,
    [SignalType.USER_FEEDBACK]: 1.2,
    [SignalType.VALIDATION_PASS]: 1.0,
    [SignalType.HUMAN_REVIEWED]: 1.5,
    [SignalType.MODEL_CONSENSUS]: 1.1,
    [SignalType.HISTORICAL_ACCURACY]: 0.7,
  },
  levelThresholds: {
    veryLow: 0.4,
    low: 0.6,
    medium: 0.75,
    high: 0.9,
  },
  requireMinSignals: false,
  minSignalCount: 2,
};

/**
 * Calculate weighted confidence score from multiple signals
 *
 * @param signals - Array of confidence signals
 * @param config - Optional configuration
 * @returns Confidence calculation result
 *
 * @example
 * ```ts
 * const result = calculateConfidence([
 *   { type: SignalType.VLM_CONFIDENCE, value: 0.85 },
 *   { type: SignalType.FIELD_COMPLETENESS, value: 0.92 },
 *   { type: SignalType.CACHE_HIT, value: 1.0 }
 * ]);
 *
 * console.log(`Confidence: ${result.score} (${result.level})`);
 * console.log(`Recommendation: ${result.recommendation}`);
 * ```
 */
export function calculateConfidence(
  signals: ConfidenceSignal[],
  config: ConfidenceConfig = {}
): ConfidenceResult {
  const fullConfig = { ...DEFAULT_CONFIG, ...config };

  // Validate signals
  if (signals.length === 0) {
    return {
      score: 0,
      level: 'very_low',
      signalCount: 0,
      signalBreakdown: {},
      meetsThreshold: false,
      recommendation: 'reject',
    };
  }

  // Check minimum signal count if required
  if (fullConfig.requireMinSignals && signals.length < fullConfig.minSignalCount) {
    console.warn(
      `[ConfidenceScorer] Insufficient signals: ${signals.length} < ${fullConfig.minSignalCount}`
    );
  }

  // Calculate weighted average
  let weightedSum = 0;
  let totalWeight = 0;
  const signalBreakdown: Record<string, number> = {};

  for (const signal of signals) {
    // Clamp signal value to 0-1 range
    const clampedValue = Math.max(0, Math.min(1, signal.value));

    // Get weight (signal weight or default weight for type)
    const weight =
      signal.weight ??
      fullConfig.defaultWeights![signal.type] ??
      1.0;

    weightedSum += clampedValue * weight;
    totalWeight += weight;
    signalBreakdown[signal.type] = clampedValue;
  }

  // Calculate final score
  const score = totalWeight > 0 ? weightedSum / totalWeight : 0;
  const clampedScore = Math.max(0, Math.min(1, score));

  // Determine confidence level
  const level = getConfidenceLevel(clampedScore, fullConfig.levelThresholds!);

  // Check if meets threshold
  const meetsThreshold = clampedScore >= fullConfig.minimumThreshold;

  // Determine recommendation
  const recommendation = getRecommendation(clampedScore, fullConfig.minimumThreshold);

  return {
    score: clampedScore,
    level,
    signalCount: signals.length,
    signalBreakdown,
    meetsThreshold,
    recommendation,
  };
}

/**
 * Get confidence level category from score
 */
function getConfidenceLevel(
  score: number,
  thresholds: Required<ConfidenceConfig>['levelThresholds']
): ConfidenceResult['level'] {
  if (score < thresholds.veryLow!) return 'very_low';
  if (score < thresholds.low!) return 'low';
  if (score < thresholds.medium!) return 'medium';
  if (score < thresholds.high!) return 'high';
  return 'very_high';
}

/**
 * Get recommended action based on score
 */
function getRecommendation(
  score: number,
  threshold: number
): ConfidenceResult['recommendation'] {
  if (score >= threshold + 0.1) return 'accept'; // Well above threshold
  if (score >= threshold) return 'review'; // At threshold, suggest review
  if (score >= threshold - 0.15) return 'fallback'; // Close but below, try fallback
  return 'reject'; // Too low, reject
}

/**
 * Create a confidence signal from VLM response
 *
 * @param vlmConfidence - VLM-reported confidence (0-1)
 * @param metadata - Optional metadata
 * @returns Confidence signal
 */
export function createVLMSignal(
  vlmConfidence: number,
  metadata?: Record<string, unknown>
): ConfidenceSignal {
  return {
    type: SignalType.VLM_CONFIDENCE,
    value: vlmConfidence,
    metadata,
  };
}

/**
 * Create a confidence signal from cache hit
 *
 * @param isHit - Whether cache was hit
 * @param hitCount - Number of times this extraction was cached (higher = more validated)
 * @returns Confidence signal
 */
export function createCacheSignal(isHit: boolean, hitCount: number = 1): ConfidenceSignal {
  // Cache hits provide high confidence, scaled by hit count
  const value = isHit ? Math.min(1.0, 0.8 + hitCount * 0.05) : 0;

  return {
    type: SignalType.CACHE_HIT,
    value,
    metadata: { isHit, hitCount },
  };
}

/**
 * Create a confidence signal from field completeness
 *
 * @param requiredFields - Array of required field names
 * @param extractedData - Extracted data object
 * @returns Confidence signal
 */
export function createCompletenessSignal(
  requiredFields: string[],
  extractedData: Record<string, unknown>
): ConfidenceSignal {
  if (requiredFields.length === 0) {
    return {
      type: SignalType.FIELD_COMPLETENESS,
      value: 1.0,
      metadata: { reason: 'no_required_fields' },
    };
  }

  let completedCount = 0;
  const missingFields: string[] = [];

  for (const field of requiredFields) {
    const value = extractedData[field];
    const isPresent =
      value !== null &&
      value !== undefined &&
      value !== '' &&
      !(Array.isArray(value) && value.length === 0);

    if (isPresent) {
      completedCount++;
    } else {
      missingFields.push(field);
    }
  }

  const completeness = completedCount / requiredFields.length;

  return {
    type: SignalType.FIELD_COMPLETENESS,
    value: completeness,
    metadata: {
      completedCount,
      totalCount: requiredFields.length,
      missingFields,
    },
  };
}

/**
 * Create a confidence signal from user feedback
 *
 * @param isPositive - Whether feedback was positive (thumbs up)
 * @returns Confidence signal
 */
export function createFeedbackSignal(isPositive: boolean): ConfidenceSignal {
  return {
    type: SignalType.USER_FEEDBACK,
    value: isPositive ? 1.0 : 0.0,
    metadata: { isPositive },
  };
}

/**
 * Create a confidence signal from validation results
 *
 * @param passedRules - Number of validation rules passed
 * @param totalRules - Total number of validation rules
 * @returns Confidence signal
 */
export function createValidationSignal(
  passedRules: number,
  totalRules: number
): ConfidenceSignal {
  const passRate = totalRules > 0 ? passedRules / totalRules : 1.0;

  return {
    type: SignalType.VALIDATION_PASS,
    value: passRate,
    metadata: { passedRules, totalRules },
  };
}

/**
 * Create a confidence signal from human review
 *
 * @param wasReviewed - Whether human review occurred
 * @param correctionsNeeded - Number of corrections made by human
 * @returns Confidence signal
 */
export function createHumanReviewSignal(
  wasReviewed: boolean,
  correctionsNeeded: number = 0
): ConfidenceSignal {
  // High confidence if reviewed with few corrections
  const value = wasReviewed ? Math.max(0.7, 1.0 - correctionsNeeded * 0.1) : 0;

  return {
    type: SignalType.HUMAN_REVIEWED,
    value,
    metadata: { wasReviewed, correctionsNeeded },
  };
}

/**
 * Create a confidence signal from model consensus
 *
 * @param agreementCount - Number of models that agree
 * @param totalModels - Total number of models
 * @returns Confidence signal
 */
export function createConsensusSignal(
  agreementCount: number,
  totalModels: number
): ConfidenceSignal {
  const consensus = totalModels > 0 ? agreementCount / totalModels : 0;

  return {
    type: SignalType.MODEL_CONSENSUS,
    value: consensus,
    metadata: { agreementCount, totalModels },
  };
}

/**
 * Create a confidence signal from historical accuracy
 *
 * @param successRate - Historical success rate (0-1) for similar cases
 * @param sampleSize - Number of historical samples
 * @returns Confidence signal
 */
export function createHistoricalSignal(
  successRate: number,
  sampleSize: number
): ConfidenceSignal {
  // Adjust confidence based on sample size (more samples = more confidence)
  const sampleConfidence = Math.min(1.0, sampleSize / 20); // Full confidence at 20+ samples
  const adjustedValue = successRate * (0.5 + sampleConfidence * 0.5);

  return {
    type: SignalType.HISTORICAL_ACCURACY,
    value: adjustedValue,
    metadata: { successRate, sampleSize },
  };
}

/**
 * Check if confidence meets a specific threshold
 *
 * @param result - Confidence calculation result
 * @param threshold - Threshold to check (defaults to config minimum)
 * @returns Whether threshold is met
 */
export function meetsThreshold(result: ConfidenceResult, threshold?: number): boolean {
  return threshold !== undefined ? result.score >= threshold : result.meetsThreshold;
}

/**
 * Get a human-readable confidence description
 *
 * @param result - Confidence calculation result
 * @returns Description string
 */
export function getConfidenceDescription(result: ConfidenceResult): string {
  const percentage = (result.score * 100).toFixed(1);

  const descriptions: Record<ConfidenceResult['level'], string> = {
    very_low: `Very low confidence (${percentage}%) - Extraction likely unreliable`,
    low: `Low confidence (${percentage}%) - Extraction needs significant review`,
    medium: `Medium confidence (${percentage}%) - Extraction usable with review`,
    high: `High confidence (${percentage}%) - Extraction reliable`,
    very_high: `Very high confidence (${percentage}%) - Extraction highly reliable`,
  };

  return descriptions[result.level];
}

/**
 * Merge multiple confidence results (useful for multi-step workflows)
 *
 * @param results - Array of confidence results to merge
 * @returns Merged confidence result
 */
export function mergeConfidenceResults(results: ConfidenceResult[]): ConfidenceResult {
  if (results.length === 0) {
    return {
      score: 0,
      level: 'very_low',
      signalCount: 0,
      signalBreakdown: {},
      meetsThreshold: false,
      recommendation: 'reject',
    };
  }

  // Average scores
  const avgScore = results.reduce((sum, r) => sum + r.score, 0) / results.length;

  // Merge signal breakdowns
  const mergedBreakdown: Record<string, number> = {};
  for (const result of results) {
    for (const [type, value] of Object.entries(result.signalBreakdown)) {
      mergedBreakdown[type] = Math.max(mergedBreakdown[type] || 0, value);
    }
  }

  // Total signal count
  const totalSignals = results.reduce((sum, r) => sum + r.signalCount, 0);

  // Use lowest recommendation (most conservative)
  const recommendations = results.map((r) => r.recommendation);
  const recommendation =
    recommendations.includes('reject')
      ? 'reject'
      : recommendations.includes('fallback')
        ? 'fallback'
        : recommendations.includes('review')
          ? 'review'
          : 'accept';

  const level = getConfidenceLevel(avgScore, DEFAULT_CONFIG.levelThresholds!);
  const meetsThreshold = avgScore >= DEFAULT_CONFIG.minimumThreshold;

  return {
    score: avgScore,
    level,
    signalCount: totalSignals,
    signalBreakdown: mergedBreakdown,
    meetsThreshold,
    recommendation,
  };
}
