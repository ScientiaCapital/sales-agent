/**
 * Middleware Module
 * Production-grade middleware for VLM workflows
 *
 * @module middleware
 */

// Circuit Breaker Pattern
export {
  CircuitBreaker,
  CircuitBreakerOpenError,
  CircuitState,
  type CircuitBreakerConfig,
  type CircuitBreakerMetrics,
} from './circuit-breaker';

// Retry Pattern
export {
  withRetry,
  retry,
  makeRetryable,
  RetryExhaustedError,
  NonRetryableError,
  type RetryConfig,
  type RetryResult,
} from './workflow-retry';
