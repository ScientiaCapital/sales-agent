/**
 * Circuit Breaker Pattern Implementation (GAP-10)
 * Prevents cascading failures by detecting when a service is down
 * and stopping attempts to call it until recovery is detected.
 *
 * States:
 * - CLOSED: Service is working normally, calls proceed
 * - OPEN: Service is down, calls fail immediately without attempting
 * - HALF_OPEN: Testing if service has recovered, limited calls allowed
 */

/**
 * Circuit breaker state enum
 */
export enum CircuitState {
  CLOSED = 'CLOSED',
  OPEN = 'OPEN',
  HALF_OPEN = 'HALF_OPEN',
}

/**
 * Circuit breaker configuration options
 */
export interface CircuitBreakerConfig {
  /**
   * Number of failures before opening the circuit
   * @default 5
   */
  failureThreshold?: number;

  /**
   * Time in milliseconds before attempting to close from HALF_OPEN state
   * @default 30000 (30 seconds)
   */
  resetTimeout?: number;

  /**
   * Number of successes needed to close circuit from HALF_OPEN
   * @default 2
   */
  successThreshold?: number;

  /**
   * Percentage of allowed calls during HALF_OPEN state (0-1)
   * @default 0.5 (50%)
   */
  halfOpenCallPercentage?: number;

  /**
   * Name of the service for logging and monitoring
   */
  serviceName?: string;

  /**
   * Optional error logger callback
   * @param error - The error that occurred
   * @param context - Additional context about the error
   */
  onError?: (error: unknown, context: Record<string, unknown>) => void | Promise<void>;
}

/**
 * Metrics tracked by the circuit breaker
 */
export interface CircuitBreakerMetrics {
  totalRequests: number;
  totalFailures: number;
  totalSuccesses: number;
  lastFailureTime?: number;
  lastSuccessTime?: number;
  halfOpenAttempts: number;
  halfOpenSuccesses: number;
  state: CircuitState;
  stateChangeTime: number;
}

/**
 * Error thrown when circuit is open
 */
export class CircuitBreakerOpenError extends Error {
  constructor(serviceName: string) {
    super(`Circuit breaker is OPEN for service: ${serviceName}`);
    this.name = 'CircuitBreakerOpenError';
  }
}

/**
 * Main CircuitBreaker class
 * Implements the circuit breaker pattern for fault tolerance
 */
export class CircuitBreaker {
  private state: CircuitState = CircuitState.CLOSED;
  private failureCount: number = 0;
  private successCount: number = 0;
  private halfOpenAttempts: number = 0;
  private halfOpenSuccesses: number = 0;
  private lastFailureTime?: number;
  private lastSuccessTime?: number;
  private nextAttemptTime: number = 0;
  private metrics: CircuitBreakerMetrics;

  private readonly config: Required<CircuitBreakerConfig>;

  /**
   * Creates a new CircuitBreaker instance
   *
   * @param config Configuration options
   *
   * @example
   * ```ts
   * const breaker = new CircuitBreaker({
   *   serviceName: 'openrouter',
   *   failureThreshold: 5,
   *   resetTimeout: 30000,
   *   successThreshold: 2,
   * });
   * ```
   */
  constructor(config: CircuitBreakerConfig = {}) {
    this.config = {
      failureThreshold: config.failureThreshold ?? 5,
      resetTimeout: config.resetTimeout ?? 30000,
      successThreshold: config.successThreshold ?? 2,
      halfOpenCallPercentage: config.halfOpenCallPercentage ?? 0.5,
      serviceName: config.serviceName ?? 'unknown',
      onError: config.onError ?? (() => {}),
    };

    this.metrics = {
      totalRequests: 0,
      totalFailures: 0,
      totalSuccesses: 0,
      halfOpenAttempts: 0,
      halfOpenSuccesses: 0,
      state: CircuitState.CLOSED,
      stateChangeTime: Date.now(),
    };
  }

  /**
   * Executes a function with circuit breaker protection
   * Throws CircuitBreakerOpenError if circuit is open
   *
   * @param fn Function to execute
   * @param context Optional context for error logging
   * @returns Result of function execution
   * @throws CircuitBreakerOpenError if circuit is open
   * @throws Original error if function throws
   *
   * @example
   * ```ts
   * const breaker = new CircuitBreaker({ serviceName: 'openrouter' });
   *
   * try {
   *   const result = await breaker.execute(
   *     () => callOpenRouterAPI(),
   *     { serviceName: 'openrouter' }
   *   );
   * } catch (error) {
   *   if (error instanceof CircuitBreakerOpenError) {
   *     console.log('Service is down, use fallback');
   *   }
   * }
   * ```
   */
  async execute<T>(
    fn: () => Promise<T>,
    context?: Record<string, unknown>
  ): Promise<T> {
    // Check current state and update if needed
    this.updateState();

    // Increment request counter
    this.metrics.totalRequests++;

    // Check if circuit is open
    if (this.state === CircuitState.OPEN) {
      const error = new CircuitBreakerOpenError(this.config.serviceName);
      await this.config.onError(error, {
        serviceName: this.config.serviceName,
        functionName: 'execute',
        circuitState: this.state,
        failureCount: this.failureCount,
        nextAttemptTime: new Date(this.nextAttemptTime).toISOString(),
        ...context,
      });
      throw error;
    }

    // In HALF_OPEN state, limit call percentage
    if (this.state === CircuitState.HALF_OPEN) {
      this.halfOpenAttempts++;
      this.metrics.halfOpenAttempts++;

      const allowCall = Math.random() < this.config.halfOpenCallPercentage;
      if (!allowCall) {
        const error = new CircuitBreakerOpenError(this.config.serviceName);
        error.message += ' (rate limited in HALF_OPEN state)';
        throw error;
      }
    }

    // Execute the function
    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      await this.onFailure(error, context);
      throw error;
    }
  }

  /**
   * Gets the current state of the circuit
   */
  getState(): CircuitState {
    this.updateState();
    return this.state;
  }

  /**
   * Gets current metrics
   */
  getMetrics(): CircuitBreakerMetrics {
    return { ...this.metrics };
  }

  /**
   * Manually resets the circuit to CLOSED state
   * Useful for external recovery signals or monitoring dashboards
   */
  reset(): void {
    const previousState = this.state;
    this.state = CircuitState.CLOSED;
    this.failureCount = 0;
    this.successCount = 0;
    this.halfOpenAttempts = 0;
    this.halfOpenSuccesses = 0;
    this.nextAttemptTime = 0;

    // Reset all metrics including totals
    this.metrics = {
      totalRequests: 0,
      totalFailures: 0,
      totalSuccesses: 0,
      halfOpenAttempts: 0,
      halfOpenSuccesses: 0,
      state: CircuitState.CLOSED,
      stateChangeTime: Date.now(),
    };

    console.log(
      `[CircuitBreaker] ${this.config.serviceName} reset from ${previousState} to CLOSED`
    );
  }

  /**
   * Force opens the circuit
   * Useful when external monitoring detects issues
   */
  open(): void {
    const previousState = this.state;
    this.state = CircuitState.OPEN;
    this.nextAttemptTime = Date.now() + this.config.resetTimeout;
    this.failureCount = this.config.failureThreshold;

    this.metrics.state = CircuitState.OPEN;
    this.metrics.stateChangeTime = Date.now();

    console.log(
      `[CircuitBreaker] ${this.config.serviceName} forced open from ${previousState}`
    );
  }

  /**
   * Updates circuit state based on time and current failure count
   */
  private updateState(): void {
    if (this.state === CircuitState.OPEN) {
      // Check if it's time to attempt recovery
      if (Date.now() >= this.nextAttemptTime) {
        this.state = CircuitState.HALF_OPEN;
        this.successCount = 0;
        this.halfOpenAttempts = 0;
        this.halfOpenSuccesses = 0;

        this.metrics.state = CircuitState.HALF_OPEN;
        this.metrics.stateChangeTime = Date.now();

        console.log(
          `[CircuitBreaker] ${this.config.serviceName} transitioning to HALF_OPEN to test recovery`
        );
      }
    }
  }

  /**
   * Handles successful function execution
   */
  private onSuccess(): void {
    this.failureCount = 0;
    this.successCount++;
    this.lastSuccessTime = Date.now();
    this.metrics.totalSuccesses++;
    this.metrics.lastSuccessTime = this.lastSuccessTime;

    if (this.state === CircuitState.CLOSED) {
      // Normal operation, reset success counter
      this.successCount = 0;
    } else if (this.state === CircuitState.HALF_OPEN) {
      this.halfOpenSuccesses++;
      this.metrics.halfOpenSuccesses++;

      // Check if we've achieved enough successes to close
      if (this.halfOpenSuccesses >= this.config.successThreshold) {
        this.state = CircuitState.CLOSED;
        this.successCount = 0;
        this.failureCount = 0;

        this.metrics.state = CircuitState.CLOSED;
        this.metrics.stateChangeTime = Date.now();

        console.log(
          `[CircuitBreaker] ${this.config.serviceName} recovered - closing circuit`
        );
      }
    }
  }

  /**
   * Handles failed function execution
   */
  private async onFailure(error: unknown, context?: Record<string, unknown>): Promise<void> {
    this.failureCount++;
    this.lastFailureTime = Date.now();
    this.metrics.totalFailures++;
    this.metrics.lastFailureTime = this.lastFailureTime;

    const errorMessage =
      error instanceof Error ? error.message : JSON.stringify(error);

    if (this.state === CircuitState.HALF_OPEN) {
      // Failure during recovery test - reopen circuit
      this.state = CircuitState.OPEN;
      this.nextAttemptTime = Date.now() + this.config.resetTimeout;
      this.successCount = 0;

      this.metrics.state = CircuitState.OPEN;
      this.metrics.stateChangeTime = Date.now();

      console.log(
        `[CircuitBreaker] ${this.config.serviceName} failed during recovery test, reopening circuit`
      );

      await this.config.onError(error, {
        serviceName: this.config.serviceName,
        functionName: 'onFailure',
        circuitState: 'HALF_OPEN -> OPEN',
        failureCount: this.failureCount,
        halfOpenSuccesses: this.halfOpenSuccesses,
        ...context,
      });
    } else if (this.state === CircuitState.CLOSED) {
      // Regular failure in closed state
      if (this.failureCount >= this.config.failureThreshold) {
        // Threshold reached, open circuit
        this.state = CircuitState.OPEN;
        this.nextAttemptTime = Date.now() + this.config.resetTimeout;

        this.metrics.state = CircuitState.OPEN;
        this.metrics.stateChangeTime = Date.now();

        console.log(
          `[CircuitBreaker] ${this.config.serviceName} failure threshold reached (${this.failureCount}/${this.config.failureThreshold}) - opening circuit`
        );

        await this.config.onError(error, {
          serviceName: this.config.serviceName,
          functionName: 'onFailure',
          circuitState: 'CLOSED -> OPEN',
          failureCount: this.failureCount,
          failureThreshold: this.config.failureThreshold,
          ...context,
        });
      } else {
        // Log failure but stay closed
        console.warn(
          `[CircuitBreaker] ${this.config.serviceName} failure (${this.failureCount}/${this.config.failureThreshold}): ${errorMessage}`
        );
      }
    }
  }
}
