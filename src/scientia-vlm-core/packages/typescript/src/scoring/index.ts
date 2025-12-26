/**
 * Confidence Scoring Module
 *
 * Multi-signal confidence aggregation for VLM extractions.
 * Provides weighted confidence calculation with configurable thresholds.
 *
 * @module scoring
 */

export {
  // Types
  SignalType,
  type ConfidenceSignal,
  type ConfidenceResult,
  type ConfidenceConfig,

  // Main functions
  calculateConfidence,
  mergeConfidenceResults,

  // Signal factory functions
  createVLMSignal,
  createCacheSignal,
  createCompletenessSignal,
  createFeedbackSignal,
  createValidationSignal,
  createHumanReviewSignal,
  createConsensusSignal,
  createHistoricalSignal,

  // Utility functions
  meetsThreshold,
  getConfidenceDescription,
} from './confidence-scorer.js';
