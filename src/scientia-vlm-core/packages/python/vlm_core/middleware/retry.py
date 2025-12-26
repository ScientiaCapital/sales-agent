"""Workflow Retry Module.

Per-step retry with exponential backoff for workflow resilience.

Features:
- Configurable retry attempts per step
- Exponential backoff with jitter
- Step-level retry (not top-level)
- Maximum delay cap to prevent infinite waits

Ported from TypeScript implementation in FieldVault.ai
"""
import asyncio
import time
import random
from typing import Any, Callable, TypeVar
from pydantic import BaseModel, Field

from ..exceptions import RetryExhaustedError, NonRetryableError


T = TypeVar('T')


class RetryConfig(BaseModel):
    """Retry configuration for a step or operation."""

    max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts (excluding initial attempt)"
    )
    base_delay: int = Field(
        default=1000,
        description="Base delay in milliseconds before first retry"
    )
    max_delay: int = Field(
        default=30000,
        description="Maximum delay cap in milliseconds"
    )
    backoff_multiplier: float = Field(
        default=2.0,
        description="Exponential backoff multiplier"
    )
    jitter: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Add random jitter to delays (percentage of delay)"
    )


class RetryResult(BaseModel):
    """Result of a retry operation including attempt metadata."""

    value: Any
    attempts: int
    total_time_ms: int
    had_retries: bool


def _should_retry_default(error: Exception, attempt: int) -> bool:
    """Default retry logic.

    Args:
        error: Exception that occurred.
        attempt: Current attempt number.

    Returns:
        True if should retry, False otherwise.
    """
    # Don't retry NonRetryableError
    if isinstance(error, NonRetryableError):
        return False

    # Don't retry 4xx client errors (except 429 rate limit)
    error_message = str(error).lower()
    is_4xx = any(f'4{i}{j}' in error_message for i in range(10) for j in range(10))
    is_429 = '429' in error_message

    if is_4xx and not is_429:
        return False

    return True


def _calculate_delay(attempt: int, config: RetryConfig) -> int:
    """Calculate delay for a given retry attempt with exponential backoff and jitter.

    Args:
        attempt: Current attempt number (1-indexed).
        config: Retry configuration.

    Returns:
        Delay in milliseconds.
    """
    # Exponential backoff: base_delay * (multiplier ^ (attempt - 1))
    exponential_delay = config.base_delay * (config.backoff_multiplier ** (attempt - 1))

    # Cap at max_delay
    capped_delay = min(exponential_delay, config.max_delay)

    # Add jitter: random value between (1 - jitter) and (1 + jitter)
    jitter_factor = 1 + (random.random() * 2 - 1) * config.jitter
    delay_with_jitter = capped_delay * jitter_factor

    return int(delay_with_jitter)


async def withRetry(
    fn: Callable[[], T],
    config: RetryConfig | None = None,
    should_retry: Callable[[Exception, int], bool] | None = None,
    on_retry: Callable[[Exception, int, int], None] | None = None,
) -> RetryResult:
    """Execute a function with retry logic and exponential backoff.

    Args:
        fn: Async function to execute.
        config: Retry configuration (uses defaults if None).
        should_retry: Custom function to determine if error is retryable.
        on_retry: Callback invoked before each retry attempt.

    Returns:
        RetryResult with value and metadata.

    Raises:
        RetryExhaustedError: If all attempts fail.

    Example:
        ```python
        # Basic usage
        result = await withRetry(
            lambda: call_unreliable_api(),
            RetryConfig(max_retries=3, base_delay=1000)
        )
        print(f"Succeeded after {result.attempts} attempts")

        # With custom retry logic
        result = await withRetry(
            lambda: fetch_data(),
            config=RetryConfig(),
            should_retry=lambda error, attempt: (
                attempt < 5 and is_network_error(error)
            ),
            on_retry=lambda error, attempt, delay: (
                print(f"Retry attempt {attempt} after {delay}ms")
            )
        )
        ```
    """
    config = config or RetryConfig()
    should_retry_fn = should_retry or _should_retry_default
    on_retry_fn = on_retry or (lambda e, a, d: None)

    start_time = time.time()
    last_error: Exception | None = None
    attempt = 0

    while attempt <= config.max_retries:
        attempt += 1

        try:
            value = await fn()
            total_time_ms = int((time.time() - start_time) * 1000)

            return RetryResult(
                value=value,
                attempts=attempt,
                total_time_ms=total_time_ms,
                had_retries=attempt > 1,
            )
        except Exception as error:
            last_error = error

            # Check if we should retry this error
            should_retry_error = should_retry_fn(error, attempt)

            # Check if we've exhausted attempts
            is_last_attempt = attempt > config.max_retries

            if not should_retry_error or is_last_attempt:
                # Log final failure
                print(
                    f"[Retry] All attempts exhausted (attempt {attempt}/"
                    f"{config.max_retries + 1}): {error}"
                )
                raise RetryExhaustedError(attempt, error)

            # Calculate delay and wait
            delay_ms = _calculate_delay(attempt, config)

            # Invoke retry callback
            on_retry_fn(error, attempt, delay_ms)

            print(
                f"[Retry] Attempt {attempt}/{config.max_retries + 1} failed, "
                f"retrying in {delay_ms}ms: {error}"
            )

            await asyncio.sleep(delay_ms / 1000.0)

    # This should never be reached, but Python needs it
    if last_error:
        raise RetryExhaustedError(attempt, last_error)
    else:
        raise RuntimeError("Retry loop exited without error or success")


async def retry(
    fn: Callable[[], T],
    config: RetryConfig | None = None,
    should_retry: Callable[[Exception, int], bool] | None = None,
    on_retry: Callable[[Exception, int, int], None] | None = None,
) -> T:
    """Simplified retry function that returns the value directly.

    Throws original error if all retries exhausted.

    Args:
        fn: Async function to execute.
        config: Retry configuration.
        should_retry: Custom retry logic.
        on_retry: Retry callback.

    Returns:
        Function result.

    Raises:
        Original error (wrapped in RetryExhaustedError) if all attempts fail.

    Example:
        ```python
        # Simpler API when you don't need retry metadata
        data = await retry(
            lambda: fetch_data(),
            RetryConfig(max_retries=3)
        )
        ```
    """
    result = await withRetry(fn, config, should_retry, on_retry)
    return result.value


def makeRetryable(
    fn: Callable[..., T],
    config: RetryConfig | None = None,
    should_retry: Callable[[Exception, int], bool] | None = None,
    on_retry: Callable[[Exception, int, int], None] | None = None,
) -> Callable[..., T]:
    """Create a retryable version of a function with baked-in retry config.

    Useful for creating service clients with consistent retry behavior.

    Args:
        fn: Function to wrap with retry logic.
        config: Retry configuration to apply.
        should_retry: Custom retry logic.
        on_retry: Retry callback.

    Returns:
        Wrapped function with retry behavior.

    Example:
        ```python
        # Create retryable service methods
        vlm_analyze = makeRetryable(
            lambda image: vlm_client.analyze(image),
            RetryConfig(max_retries=5, base_delay=2000)
        )

        # Use like normal function, retries automatically
        result = await vlm_analyze(image_data)
        ```
    """
    async def wrapped(*args: Any, **kwargs: Any) -> T:
        return await retry(
            lambda: fn(*args, **kwargs),
            config,
            should_retry,
            on_retry
        )

    return wrapped
