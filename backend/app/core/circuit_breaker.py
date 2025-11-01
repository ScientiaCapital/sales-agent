"""Circuit breaker pattern for fault tolerance."""
import time
import asyncio
from enum import Enum
from typing import Callable, Any, Optional
from functools import wraps

from app.core.logging import setup_logging

logger = setup_logging(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit open, failing fast
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerOpenError(Exception):
    """Raised when circuit is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker implementation for protecting against cascading failures.

    Usage:
        breaker = CircuitBreaker(failure_threshold=5, timeout_duration=30, recovery_timeout=60)

        @breaker.protected
        async def risky_operation():
            # Call external service
            pass

    States:
    - CLOSED: Normal operation, requests go through
    - OPEN: Too many failures, fail fast without calling service
    - HALF_OPEN: Testing if service recovered, allow one request through
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_duration: float = 30.0,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout_duration: Seconds to wait before attempting recovery
            recovery_timeout: Seconds before considering recovery attempt timeout
            success_threshold: Successes needed in HALF_OPEN to close circuit
        """
        self.failure_threshold = failure_threshold
        self.timeout_duration = timeout_duration
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        async with self._lock:
            if self.state == CircuitState.OPEN:
                # Check if recovery timeout elapsed
                if time.time() - self.last_failure_time >= self.timeout_duration:
                    logger.info("Circuit breaker entering HALF_OPEN state (testing recovery)")
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker is OPEN. Wait {self.timeout_duration}s before retry."
                    )

        try:
            # Execute function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Success - update state
            await self._on_success()
            return result

        except Exception as e:
            # Failure - update state
            await self._on_failure(e)
            raise

    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            self.failure_count = 0

            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                logger.info(f"Circuit breaker HALF_OPEN success {self.success_count}/{self.success_threshold}")

                if self.success_count >= self.success_threshold:
                    logger.info("Circuit breaker closing (service recovered)")
                    self.state = CircuitState.CLOSED
                    self.success_count = 0

    async def _on_failure(self, exception: Exception):
        """Handle failed call."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            logger.warning(
                f"Circuit breaker failure {self.failure_count}/{self.failure_threshold}: {exception}"
            )

            if self.state == CircuitState.HALF_OPEN:
                # Failed during recovery test - reopen circuit
                logger.error("Circuit breaker reopening (recovery test failed)")
                self.state = CircuitState.OPEN
                self.failure_count = 0
                self.success_count = 0

            elif self.failure_count >= self.failure_threshold:
                # Too many failures - open circuit
                logger.error(f"Circuit breaker opening (threshold reached: {self.failure_threshold})")
                self.state = CircuitState.OPEN

    def protected(self, func: Callable) -> Callable:
        """
        Decorator to protect async functions with circuit breaker.

        Usage:
            @breaker.protected
            async def my_function():
                pass
        """
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.call(func, *args, **kwargs)

        return wrapper

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.state

    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time
        }

    async def reset(self):
        """Manually reset circuit breaker (for testing/admin)."""
        async with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            logger.info("Circuit breaker manually reset")


# Global circuit breakers for common services
qualification_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout_duration=30.0,
    recovery_timeout=60.0
)

enrichment_breaker = CircuitBreaker(
    failure_threshold=3,
    timeout_duration=60.0,
    recovery_timeout=120.0
)

crm_breaker = CircuitBreaker(
    failure_threshold=10,
    timeout_duration=30.0,
    recovery_timeout=60.0
)
