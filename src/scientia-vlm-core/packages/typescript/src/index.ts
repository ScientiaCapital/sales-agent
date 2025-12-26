/**
 * @scientia/vlm-core
 *
 * Scientia Capital VLM Stack - Vision Language Model integration
 * with circuit breaker, retry, confidence scoring, and context management.
 *
 * NEW in v1.1.0:
 * - Model Registry with 216-test audit data (2025-12-13)
 * - Model Selection Algorithm with automatic fallback
 * - Trade-specific extraction prompts (6 trades)
 *
 * PRIVATE - Proprietary IP
 *
 * @module @scientia/vlm-core
 */

// Middleware - Circuit Breaker & Retry
export * from './middleware/index';

// Confidence Scoring
export * from './scoring/index';

// Utilities - Context Compaction
export * from './utils/index';

// Model Registry & Selection Algorithm (NEW)
export * from './models/index';
export * from './selection/index';

// Trade-Specific Prompts (NEW)
export * from './prompts/index';
