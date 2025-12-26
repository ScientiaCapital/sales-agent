/**
 * Workflow Retry Module (GAP-7)
 * Per-step retry with exponential backoff for workflow resilience
 *
 * Features:
 * - Configurable retry attempts per step
 * - Exponential backoff with jitter
 * - Step-level retry (not top-level)
 * - Maximum delay cap to prevent infinite waits
 */

/**
 * Retry configuration for a step or operation
 */
export interface RetryConfig {
  /**
   * Maximum number of retry attempts (excluding initial attempt)
   * @default 3
   */
  maxRetries?: number;

  /**
   * Base delay in milliseconds before first retry
   * @default 1000 (1 second)
   */
  baseDelay?: number;

  /**
   * Maximum delay cap in milliseconds
   * @default 30000 (30 seconds)
   */
  maxDelay?: number;

  /**
   * Exponential backoff multiplier (2 = double each time)
   * @default 2
   */
  backoffMultiplier?: number;

  /**
   * Add random jitter to delays (0-1 = percentage of delay)
   * Prevents thundering herd when multiple calls fail simultaneously
   * @default 0.1 (10%)
   */
  jitter?: number;

  /**
   * Custom function to determine if an error is retryable
   * @default Retries on all errors except explicit no-retry markers
   */
  shouldRetry?: (error: unknown, attempt: number) => boolean;

  /**
   * Callback invoked before each retry attempt
   */
  onRetry?: (error: unknown, attempt: number, delayMs: number) => void;

  /**
   * Optional error logger callback
   * @param error - The error that occurred
   * @param context - Additional context about the error
   */
  onError?: (error: unknown, context: Record<string, unknown>) => void | Promise<void>;
}

/**
 * Result of a retry operation including attempt metadata
 */
export interface RetryResult<T> {
  /** Result value from successful execution */
  value: T;
  /** Number of attempts made (1 = success on first try) */
  attempts: number;
  /** Total time spent including delays (ms) */
  totalTimeMs: number;
  /** Whether any retries were needed */
  hadRetries: boolean;
}

/**
 * Error thrown when all retry attempts are exhausted
 */
export class RetryExhaustedError extends Error {
  constructor(
    public readonly attempts: number,
    public readonly lastError: unknown
  ) {
    const message = lastError instanceof Error
      ? lastError.message
      : String(lastError);
    super(`All ${attempts} retry attempts exhausted. Last error: ${message}`);
    this.name = 'RetryExhaustedError';
  }
}

/**
 * Marker to indicate an error should not be retried
 * Wrap errors with this class to skip retry logic
 */
export class NonRetryableError extends Error {
  constructor(message: string, public readonly originalError?: unknown) {
    super(message);
    this.name = 'NonRetryableError';
  }
}

/**
 * Default retry configuration
 */
const DEFAULT_CONFIG: Required<RetryConfig> = {
  maxRetries: 3,
  baseDelay: 1000,
  maxDelay: 30000,
  backoffMultiplier: 2,
  jitter: 0.1,
  shouldRetry: (error: unknown) => {
    // Don't retry NonRetryableError
    if (error instanceof NonRetryableError) {
      return false;
    }
    // Don't retry 4xx client errors (except 429 rate limit)
    if (error instanceof Error) {
      const message = error.message.toLowerCase();
      const is4xx = /4\d{2}/.test(message);
      const is429 = /429/.test(message);
      if (is4xx && !is429) {
        return false;
      }
    }
    return true;
  },
  onRetry: () => {}, // No-op by default
  onError: () => {}, // No-op by default
};

/**
 * Calculate delay for a given retry attempt with exponential backoff and jitter
 *
 * @param attempt - Current attempt number (1-indexed)
 * @param config - Retry configuration
 * @returns Delay in milliseconds
 */
function calculateDelay(attempt: number, config: Required<RetryConfig>): number {
  // Exponential backoff: baseDelay * (multiplier ^ (attempt - 1))
  const exponentialDelay = config.baseDelay * Math.pow(config.backoffMultiplier, attempt - 1);

  // Cap at maxDelay
  const cappedDelay = Math.min(exponentialDelay, config.maxDelay);

  // Add jitter: random value between (1 - jitter) and (1 + jitter)
  const jitterFactor = 1 + (Math.random() * 2 - 1) * config.jitter;
  const delayWithJitter = cappedDelay * jitterFactor;

  return Math.floor(delayWithJitter);
}

/**
 * Sleep for a specified duration
 *
 * @param ms - Milliseconds to sleep
 * @returns Promise resolving after delay
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Execute a function with retry logic and exponential backoff
 *
 * @param fn - Async function to execute
 * @param config - Retry configuration
 * @returns Promise resolving to retry result with metadata
 * @throws RetryExhaustedError if all attempts fail
 *
 * @example
 * ```ts
 * // Basic usage
 * const result = await withRetry(
 *   () => callUnreliableAPI(),
 *   { maxRetries: 3, baseDelay: 1000 }
 * );
 * console.log(`Succeeded after ${result.attempts} attempts`);
 *
 * // With custom retry logic
 * const result = await withRetry(
 *   () => fetchData(),
 *   {
 *     shouldRetry: (error, attempt) => {
 *       // Only retry network errors, max 5 times
 *       return attempt < 5 && isNetworkError(error);
 *     },
 *     onRetry: (error, attempt, delay) => {
 *       console.log(`Retry attempt ${attempt} after ${delay}ms`);
 *     }
 *   }
 * );
 * ```
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  config: RetryConfig = {}
): Promise<RetryResult<T>> {
  // Merge with defaults
  const fullConfig: Required<RetryConfig> = {
    ...DEFAULT_CONFIG,
    ...config,
  };

  const startTime = Date.now();
  let lastError: unknown;
  let attempt = 0;

  while (attempt <= fullConfig.maxRetries) {
    attempt++;

    try {
      const value = await fn();
      const totalTimeMs = Date.now() - startTime;

      return {
        value,
        attempts: attempt,
        totalTimeMs,
        hadRetries: attempt > 1,
      };
    } catch (error) {
      lastError = error;

      // Check if we should retry this error
      const shouldRetry = fullConfig.shouldRetry(error, attempt);

      // Check if we've exhausted attempts
      const isLastAttempt = attempt > fullConfig.maxRetries;

      if (!shouldRetry || isLastAttempt) {
        // Log final failure
        await fullConfig.onError(error, {
          functionName: 'withRetry',
          attempt,
          maxRetries: fullConfig.maxRetries,
          shouldRetry,
          isLastAttempt,
          totalTimeMs: Date.now() - startTime,
        });

        throw new RetryExhaustedError(attempt, lastError);
      }

      // Calculate delay and wait
      const delayMs = calculateDelay(attempt, fullConfig);

      // Invoke retry callback
      fullConfig.onRetry(error, attempt, delayMs);

      console.warn(
        `[Retry] Attempt ${attempt}/${fullConfig.maxRetries + 1} failed, retrying in ${delayMs}ms:`,
        error instanceof Error ? error.message : String(error)
      );

      await sleep(delayMs);
    }
  }

  // This should never be reached, but TypeScript needs it
  throw new RetryExhaustedError(attempt, lastError);
}

/**
 * Simplified retry function that returns the value directly
 * Throws original error if all retries exhausted
 *
 * @param fn - Async function to execute
 * @param config - Retry configuration
 * @returns Promise resolving to function result
 * @throws Original error (wrapped in RetryExhaustedError) if all attempts fail
 *
 * @example
 * ```ts
 * // Simpler API when you don't need retry metadata
 * const data = await retry(
 *   () => fetchData(),
 *   { maxRetries: 3 }
 * );
 * ```
 */
export async function retry<T>(
  fn: () => Promise<T>,
  config: RetryConfig = {}
): Promise<T> {
  const result = await withRetry(fn, config);
  return result.value;
}

/**
 * Create a retryable version of a function with baked-in retry config
 * Useful for creating service clients with consistent retry behavior
 *
 * @param fn - Function to wrap with retry logic
 * @param config - Retry configuration to apply
 * @returns Wrapped function with retry behavior
 *
 * @example
 * ```ts
 * // Create retryable service methods
 * const vlmAnalyze = makeRetryable(
 *   (image: string) => vlmClient.analyze(image),
 *   { maxRetries: 5, baseDelay: 2000 }
 * );
 *
 * // Use like normal function, retries automatically
 * const result = await vlmAnalyze(imageData);
 * ```
 */
export function makeRetryable<TArgs extends unknown[], TReturn>(
  fn: (...args: TArgs) => Promise<TReturn>,
  config: RetryConfig = {}
): (...args: TArgs) => Promise<TReturn> {
  return async (...args: TArgs) => {
    return retry(() => fn(...args), config);
  };
}
