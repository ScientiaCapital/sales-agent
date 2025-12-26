/**
 * Confidence Scoring - Usage Examples
 *
 * This file demonstrates how to use the multi-signal confidence scoring
 * system for VLM extractions.
 */

import {
  calculateConfidence,
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
  SignalType,
  type ConfidenceConfig,
} from '../src/scoring';

// ============================================================================
// Example 1: Basic VLM Confidence Check
// ============================================================================

function example1_basicVLMConfidence() {
  console.log('\n=== Example 1: Basic VLM Confidence ===\n');

  // Simple VLM confidence signal
  const result = calculateConfidence([
    createVLMSignal(0.87, { model: 'qwen-vl-72b' }),
  ]);

  console.log('Score:', result.score);
  console.log('Level:', result.level);
  console.log('Recommendation:', result.recommendation);
  console.log('Description:', getConfidenceDescription(result));
}

// ============================================================================
// Example 2: Blueprint Takeoff with Multiple Signals
// ============================================================================

function example2_blueprintTakeoff() {
  console.log('\n=== Example 2: Blueprint Takeoff ===\n');

  // Simulated VLM extraction
  const extractedData = {
    materials: ['2x4 lumber', 'OSB sheathing', 'roof shingles'],
    quantities: [150, 32, 18],
    units: ['linear ft', 'sheets', 'bundles'],
    totalCost: 4250,
  };

  // Required fields for completeness check
  const requiredFields = ['materials', 'quantities', 'units', 'totalCost'];

  // Multiple signals
  const signals = [
    createVLMSignal(0.84, { model: 'qwen-vl-72b', temperature: 0.1 }),
    createCompletenessSignal(requiredFields, extractedData),
    createCacheSignal(true, 3), // Cache hit 3 times = validated
    createValidationSignal(9, 10), // 9 out of 10 validation rules passed
  ];

  const result = calculateConfidence(signals);

  console.log('Signal Breakdown:');
  console.log(JSON.stringify(result.signalBreakdown, null, 2));
  console.log('\nOverall Score:', result.score.toFixed(3));
  console.log('Confidence Level:', result.level);
  console.log('Recommendation:', result.recommendation);
  console.log('\nMeets Threshold (0.75)?', result.meetsThreshold ? 'Yes' : 'No');
  console.log('Meets Threshold (0.90)?', meetsThreshold(result, 0.9) ? 'Yes' : 'No');
}

// ============================================================================
// Example 3: Field Photo Analysis with Model Consensus
// ============================================================================

function example3_fieldPhotoConsensus() {
  console.log('\n=== Example 3: Field Photo with Model Consensus ===\n');

  // Simulated multi-model analysis
  const qwenResult = { equipment: 'HVAC Unit Model XYZ', confidence: 0.88 };
  const glmResult = { equipment: 'HVAC Unit Model XYZ', confidence: 0.82 }; // Agrees

  // Both models agree on equipment
  const modelsAgree = qwenResult.equipment === glmResult.equipment;

  const signals = [
    createVLMSignal(qwenResult.confidence, { model: 'qwen-vl' }),
    createConsensusSignal(modelsAgree ? 2 : 1, 2), // 2/2 models agree
    createHistoricalSignal(0.91, 15), // 91% success rate with 15 samples for HVAC
  ];

  const result = calculateConfidence(signals);

  console.log('Qwen Confidence:', qwenResult.confidence);
  console.log('GLM Confidence:', glmResult.confidence);
  console.log('Models Agree?', modelsAgree ? 'Yes' : 'No');
  console.log('\nOverall Score:', result.score.toFixed(3));
  console.log('Recommendation:', result.recommendation);

  // Decision logic
  if (result.recommendation === 'accept') {
    console.log('\n✓ Auto-accept extraction');
  } else if (result.recommendation === 'review') {
    console.log('\n⚠ Queue for human review');
  } else if (result.recommendation === 'fallback') {
    console.log('\n↻ Try fallback strategy (e.g., ROI targeting)');
  } else {
    console.log('\n✗ Reject extraction');
  }
}

// ============================================================================
// Example 4: User Feedback Loop
// ============================================================================

function example4_userFeedbackLoop() {
  console.log('\n=== Example 4: User Feedback Loop ===\n');

  // Initial extraction with low-medium confidence
  const initialSignals = [
    createVLMSignal(0.72, { model: 'qwen-vl' }),
    createCompletenessSignal(['name', 'model', 'condition'], {
      name: 'Water Heater',
      model: 'AO Smith 50gal',
      condition: 'Fair', // All fields present
    }),
  ];

  const initialResult = calculateConfidence(initialSignals);

  console.log('Initial Confidence:', initialResult.score.toFixed(3));
  console.log('Initial Recommendation:', initialResult.recommendation);

  // User provides positive feedback after review
  console.log('\n--- User reviews and approves ---\n');

  const updatedSignals = [
    ...initialSignals,
    createFeedbackSignal(true), // Thumbs up
    createHumanReviewSignal(true, 1), // Reviewed with 1 correction
  ];

  const updatedResult = calculateConfidence(updatedSignals);

  console.log('Updated Confidence:', updatedResult.score.toFixed(3));
  console.log('Updated Recommendation:', updatedResult.recommendation);
  console.log('\nConfidence Boost:', (updatedResult.score - initialResult.score).toFixed(3));
}

// ============================================================================
// Example 5: Multi-Step Workflow (Multiple Blueprint Pages)
// ============================================================================

function example5_multiStepWorkflow() {
  console.log('\n=== Example 5: Multi-Step Workflow ===\n');

  // Page 1: High confidence
  const page1Result = calculateConfidence([
    createVLMSignal(0.91),
    createCompletenessSignal(['materials', 'quantities'], {
      materials: ['lumber', 'nails'],
      quantities: [100, 5],
    }),
    createValidationSignal(10, 10),
  ]);

  // Page 2: Medium confidence
  const page2Result = calculateConfidence([
    createVLMSignal(0.78),
    createCompletenessSignal(['materials', 'quantities'], {
      materials: ['insulation'],
      quantities: [50],
    }),
    createValidationSignal(7, 10),
  ]);

  // Page 3: Low confidence (OCR quality issues)
  const page3Result = calculateConfidence([
    createVLMSignal(0.62),
    createCompletenessSignal(['materials', 'quantities'], {
      materials: ['drywall'],
      quantities: [], // Missing quantities!
    }),
    createValidationSignal(4, 10),
  ]);

  console.log('Page 1 Confidence:', page1Result.score.toFixed(3), `(${page1Result.recommendation})`);
  console.log('Page 2 Confidence:', page2Result.score.toFixed(3), `(${page2Result.recommendation})`);
  console.log('Page 3 Confidence:', page3Result.score.toFixed(3), `(${page3Result.recommendation})`);

  // Merge all pages
  const overallResult = mergeConfidenceResults([page1Result, page2Result, page3Result]);

  console.log('\n--- Overall Results ---');
  console.log('Average Score:', overallResult.score.toFixed(3));
  console.log('Total Signals:', overallResult.signalCount);
  console.log('Overall Recommendation:', overallResult.recommendation);
  console.log('Note: Recommendation is most conservative (worst page determines action)');
}

// ============================================================================
// Example 6: Custom Configuration
// ============================================================================

function example6_customConfiguration() {
  console.log('\n=== Example 6: Custom Configuration ===\n');

  // Strict configuration for critical extractions
  const strictConfig: ConfidenceConfig = {
    minimumThreshold: 0.90, // Higher threshold
    requireMinSignals: true,
    minSignalCount: 3, // Require at least 3 signals
    levelThresholds: {
      veryLow: 0.6,
      low: 0.75,
      medium: 0.85,
      high: 0.95,
    },
    defaultWeights: {
      [SignalType.VLM_CONFIDENCE]: 1.0,
      [SignalType.USER_FEEDBACK]: 2.0, // Double weight for user feedback
      [SignalType.HUMAN_REVIEWED]: 2.5, // Extra high weight for human review
      [SignalType.CACHE_HIT]: 0.5, // Lower weight for cache
    },
  };

  const signals = [
    createVLMSignal(0.85),
    createCompletenessSignal(['critical_field'], { critical_field: 'value' }),
    createValidationSignal(9, 10),
  ];

  const defaultResult = calculateConfidence(signals);
  const strictResult = calculateConfidence(signals, strictConfig);

  console.log('Default Config:');
  console.log('  Score:', defaultResult.score.toFixed(3));
  console.log('  Level:', defaultResult.level);
  console.log('  Recommendation:', defaultResult.recommendation);
  console.log('  Meets Threshold?', defaultResult.meetsThreshold);

  console.log('\nStrict Config:');
  console.log('  Score:', strictResult.score.toFixed(3));
  console.log('  Level:', strictResult.level);
  console.log('  Recommendation:', strictResult.recommendation);
  console.log('  Meets Threshold?', strictResult.meetsThreshold);
}

// ============================================================================
// Example 7: Cache Hit Boosting
// ============================================================================

function example7_cacheHitBoosting() {
  console.log('\n=== Example 7: Cache Hit Boosting ===\n');

  // First time extraction - no cache
  const firstTimeSignals = [createVLMSignal(0.78), createCacheSignal(false, 0)];

  const firstTime = calculateConfidence(firstTimeSignals);

  console.log('First Time (No Cache):');
  console.log('  Score:', firstTime.score.toFixed(3));
  console.log('  Recommendation:', firstTime.recommendation);

  // Second time - cache hit once (validated by one user)
  const cachedOnce = calculateConfidence([createVLMSignal(0.78), createCacheSignal(true, 1)]);

  console.log('\nCached Once (1 validation):');
  console.log('  Score:', cachedOnce.score.toFixed(3));
  console.log('  Recommendation:', cachedOnce.recommendation);

  // Multiple hits - validated by many users
  const cachedMany = calculateConfidence([createVLMSignal(0.78), createCacheSignal(true, 10)]);

  console.log('\nCached Many Times (10 validations):');
  console.log('  Score:', cachedMany.score.toFixed(3));
  console.log('  Recommendation:', cachedMany.recommendation);
  console.log('\nNote: Cache hit value = min(1.0, 0.8 + hitCount * 0.05)');
}

// ============================================================================
// Run All Examples
// ============================================================================

function runAllExamples() {
  console.log('╔════════════════════════════════════════════════════════════════╗');
  console.log('║       VLM AI Core - Confidence Scoring Examples               ║');
  console.log('╚════════════════════════════════════════════════════════════════╝');

  example1_basicVLMConfidence();
  example2_blueprintTakeoff();
  example3_fieldPhotoConsensus();
  example4_userFeedbackLoop();
  example5_multiStepWorkflow();
  example6_customConfiguration();
  example7_cacheHitBoosting();

  console.log('\n╔════════════════════════════════════════════════════════════════╗');
  console.log('║                    Examples Complete                          ║');
  console.log('╚════════════════════════════════════════════════════════════════╝\n');
}

// Run examples if this file is executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runAllExamples();
}

export {
  example1_basicVLMConfidence,
  example2_blueprintTakeoff,
  example3_fieldPhotoConsensus,
  example4_userFeedbackLoop,
  example5_multiStepWorkflow,
  example6_customConfiguration,
  example7_cacheHitBoosting,
  runAllExamples,
};
