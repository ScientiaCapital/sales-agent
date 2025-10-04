"""Exponential backoff retry handler for resilient API calls.

Implements configurable retry logic with exponential backoff to handle
transient failures without overwhelming failing services.
"""

import asyncio
import logging
from typing import Callable, TypeVar, Optional, Type

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted."""
    pass


class RetryWithBackoff:
    """
    Retry handler with exponential backoff.

    Calculates delay using: delay = min(base_delay * (exponential_base ** attempt), max_delay)
    Example with base_delay=1.0, exponential_base=2.0:
        - Attempt 1: 1s
        - Attempt 2: 2s
        - Attempt 3: 4s
        - Attempt 4: 8s (capped at max_delay)
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        retry_on_exceptions: Optional[tuple[Type[Exception], ...]] = None
    ):
        """
        Initialize retry handler.

        Args:
            max_retries: Maximum number of retry attempts (0 = no retries)
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds (caps exponential growth)
            exponential_base: Base for exponential calculation (typically 2.0)
            retry_on_exceptions: Tuple of exception types to retry on (None = all)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retry_on_exceptions = retry_on_exceptions

        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if base_delay <= 0:
            raise ValueError("base_delay must be > 0")
        if max_delay < base_delay:
            raise ValueError("max_delay must be >= base_delay")
        if exponential_base <= 1:
            raise ValueError("exponential_base must be > 1")

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        Execute a function with retry logic.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of successful func execution

        Raises:
            RetryExhaustedError: If all retries are exhausted
            Exception: Last exception from func if not retryable
        """
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):  # +1 for initial attempt
            try:
                # Execute the function
                result = await func(*args, **kwargs)
                
                # Success - log if this was a retry
                if attempt > 0:
                    logger.info(
                        f"Retry succeeded on attempt {attempt + 1}/{self.max_retries + 1}"
                    )
                
                return result

            except Exception as e:
                last_exception = e

                # Check if we should retry this exception type
                if self.retry_on_exceptions and not isinstance(e, self.retry_on_exceptions):
                    logger.debug(
                        f"Exception {type(e).__name__} not in retry list, failing immediately"
                    )
                    raise

                # If this was the last attempt, fail
                if attempt >= self.max_retries:
                    logger.error(
                        f"All retry attempts exhausted ({self.max_retries + 1} attempts). "
                        f"Last error: {type(e).__name__}: {str(e)}"
                    )
                    raise RetryExhaustedError(
                        f"Failed after {self.max_retries + 1} attempts: {str(e)}"
                    ) from e

                # Calculate exponential backoff delay
                delay = self._calculate_delay(attempt)

                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries + 1} failed: "
                    f"{type(e).__name__}: {str(e)}. "
                    f"Retrying in {delay:.2f}s..."
                )

                # Wait before retry
                await asyncio.sleep(delay)

        # Should never reach here, but for type safety
        if last_exception:
            raise last_exception
        raise RetryExhaustedError("Retry logic failed unexpectedly")

    async def execute_streaming(self, func, *args, **kwargs):
        """
        Execute a streaming function with retry logic.
        
        Args:
            func: Async generator function to execute with retry
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Yields:
            Chunks from the streaming function
            
        Raises:
            RetryExhaustedError: If all retries are exhausted
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                # Stream chunks from the function
                async for chunk in func(*args, **kwargs):
                    yield chunk
                
                # Success - exit retry loop
                return
                
            except Exception as e:
                last_exception = e
                
                # Check if we should retry this exception
                if self.retry_on_exceptions and not any(isinstance(e, exc_type) for exc_type in self.retry_on_exceptions):
                    logger.error(f"Non-retryable exception: {type(e).__name__}")
                    raise
                
                # Calculate delay before next retry
                if attempt < self.max_retries - 1:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Streaming attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"All {self.max_retries} streaming retry attempts exhausted"
                    )
        
        # All retries exhausted
        raise RetryExhaustedError(
            f"Failed after {self.max_retries} retry attempts. "
            f"Last error: {last_exception}"
        )

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay for given attempt.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: base_delay * (exponential_base ** attempt)
        delay = self.base_delay * (self.exponential_base ** attempt)
        
        # Cap at max_delay
        delay = min(delay, self.max_delay)
        
        return delay

    def get_config(self) -> dict:
        """Get current retry configuration for logging/debugging."""
        return {
            "max_retries": self.max_retries,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
            "exponential_base": self.exponential_base,
            "retry_on_exceptions": [
                e.__name__ for e in self.retry_on_exceptions
            ] if self.retry_on_exceptions else "all"
        }


# Pre-configured retry strategies for common use cases
class RetryStrategies:
    """Common retry configurations for different scenarios."""

    @staticmethod
    def aggressive() -> RetryWithBackoff:
        """
        Aggressive retry strategy for critical operations.
        5 retries with fast backoff (1s, 2s, 4s, 8s, 16s).
        """
        return RetryWithBackoff(
            max_retries=5,
            base_delay=1.0,
            max_delay=16.0,
            exponential_base=2.0
        )

    @staticmethod
    def standard() -> RetryWithBackoff:
        """
        Standard retry strategy for normal operations.
        3 retries with moderate backoff (1s, 2s, 4s).
        """
        return RetryWithBackoff(
            max_retries=3,
            base_delay=1.0,
            max_delay=4.0,
            exponential_base=2.0
        )

    @staticmethod
    def conservative() -> RetryWithBackoff:
        """
        Conservative retry strategy for rate-limited APIs.
        2 retries with slow backoff (2s, 4s).
        """
        return RetryWithBackoff(
            max_retries=2,
            base_delay=2.0,
            max_delay=8.0,
            exponential_base=2.0
        )

    @staticmethod
    def none() -> RetryWithBackoff:
        """
        No retry strategy - fail immediately.
        Useful for non-idempotent operations.
        """
        return RetryWithBackoff(
            max_retries=0,
            base_delay=0.0,
            max_delay=0.0,
            exponential_base=2.0
        )
