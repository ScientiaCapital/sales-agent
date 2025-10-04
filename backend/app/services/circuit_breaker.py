"""Circuit breaker pattern implementation for resilient API calls.

Implements a three-state circuit breaker (CLOSED, OPEN, HALF_OPEN) to prevent
cascading failures when external services are unavailable.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Any, TypeVar, Optional

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation, requests pass through
    OPEN = "open"            # Failing, requests blocked immediately
    HALF_OPEN = "half_open"  # Testing recovery, single request allowed


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is in OPEN state."""
    pass


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.

    State transitions:
    - CLOSED -> OPEN: After failure_threshold consecutive failures
    - OPEN -> HALF_OPEN: After recovery_timeout seconds
    - HALF_OPEN -> CLOSED: On successful request
    - HALF_OPEN -> OPEN: On failed request
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Identifier for this circuit breaker (e.g., model name)
            failure_threshold: Number of consecutive failures before opening
            recovery_timeout: Seconds to wait before attempting recovery
            success_threshold: Consecutive successes needed to close from half-open
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        # State tracking
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_state_change: datetime = datetime.now()

        # Thread safety for async operations
        self._lock = asyncio.Lock()

        logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"threshold={failure_threshold}, timeout={recovery_timeout}s"
        )

    @property
    def state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute a function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func execution

        Raises:
            CircuitBreakerError: If circuit is OPEN
            Exception: Original exception from func if execution fails
        """
        async with self._lock:
            # Check if we should transition from OPEN to HALF_OPEN
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Retry after {self._time_until_retry():.1f}s"
                    )

            # In HALF_OPEN state, allow only one request at a time
            if self._state == CircuitState.HALF_OPEN:
                logger.debug(f"Circuit breaker '{self.name}': Testing recovery in HALF_OPEN state")

        # Execute the function outside the lock to allow concurrent requests
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result

        except Exception as e:
            await self._on_failure(e)
            raise

    async def call_streaming(self, func):
        """
        Execute a streaming function with circuit breaker protection.
        
        Args:
            func: Async generator function to execute
            
        Yields:
            Chunks from the streaming function
            
        Raises:
            CircuitBreakerError: If circuit is OPEN and recovery timeout not elapsed
        """
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
            else:
                time_until = self._time_until_retry()
                logger.warning(
                    f"Circuit breaker {self.name} is OPEN. "
                    f"Retry in {time_until:.1f}s"
                )
                raise CircuitBreakerError(
                    f"Circuit breaker {self.name} is OPEN. "
                    f"Retry in {time_until:.1f}s"
                )

        try:
            # Stream chunks from the function
            async for chunk in func():
                yield chunk
            
            # Success - update state
            await self._on_success()
            
        except Exception as e:
            await self._on_failure(e)
            raise

    async def _on_success(self):
        """Handle successful function execution."""
        async with self._lock:
            self._failure_count = 0

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                logger.info(
                    f"Circuit breaker '{self.name}': Success in HALF_OPEN "
                    f"({self._success_count}/{self.success_threshold})"
                )

                if self._success_count >= self.success_threshold:
                    self._transition_to_closed()
            elif self._state == CircuitState.CLOSED:
                self._success_count += 1

    async def _on_failure(self, exception: Exception):
        """Handle failed function execution."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()
            self._success_count = 0

            logger.warning(
                f"Circuit breaker '{self.name}': Failure #{self._failure_count} "
                f"in {self._state} state - {type(exception).__name__}: {str(exception)}"
            )

            if self._state == CircuitState.HALF_OPEN:
                # Immediately reopen on failure during recovery
                self._transition_to_open()
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._transition_to_open()

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if not self._last_failure_time:
            return True

        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    def _time_until_retry(self) -> float:
        """Calculate seconds until retry is allowed."""
        if not self._last_failure_time:
            return 0.0

        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return max(0.0, self.recovery_timeout - elapsed)

    def _transition_to_open(self):
        """Transition to OPEN state."""
        self._state = CircuitState.OPEN
        self._last_state_change = datetime.now()
        logger.error(
            f"Circuit breaker '{self.name}': OPEN "
            f"(failures={self._failure_count}, timeout={self.recovery_timeout}s)"
        )

    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        self._state = CircuitState.HALF_OPEN
        self._last_state_change = datetime.now()
        self._success_count = 0
        logger.info(f"Circuit breaker '{self.name}': HALF_OPEN (testing recovery)")

    def _transition_to_closed(self):
        """Transition to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._last_state_change = datetime.now()
        self._failure_count = 0
        self._success_count = 0
        logger.info(f"Circuit breaker '{self.name}': CLOSED (recovered)")

    def get_status(self) -> dict:
        """Get current circuit breaker status for monitoring."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
            "last_state_change": self._last_state_change.isoformat(),
            "time_until_retry": self._time_until_retry() if self._state == CircuitState.OPEN else 0.0
        }
