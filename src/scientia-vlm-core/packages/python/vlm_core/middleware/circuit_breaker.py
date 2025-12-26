"""Circuit Breaker Pattern Implementation.

Prevents cascading failures by detecting when a service is down
and stopping attempts to call it until recovery is detected.

States:
- CLOSED: Service is working normally, calls proceed
- OPEN: Service is down, calls fail immediately without attempting
- HALF_OPEN: Testing if service has recovered, limited calls allowed

Ported from TypeScript implementation in FieldVault.ai
"""
from enum import Enum
from typing import Any, Callable, Optional, TypeVar
from pydantic import BaseModel, Field
import time
import random

from ..exceptions import CircuitBreakerOpenError


T = TypeVar('T')


class CircuitState(str, Enum):
    """Circuit breaker state enum."""
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerConfig(BaseModel):
    """Circuit breaker configuration options."""

    failure_threshold: int = Field(
        default=5,
        description="Number of failures before opening the circuit"
    )
    reset_timeout: int = Field(
        default=30000,
        description="Time in milliseconds before attempting to close from HALF_OPEN state"
    )
    success_threshold: int = Field(
        default=2,
        description="Number of successes needed to close circuit from HALF_OPEN"
    )
    half_open_call_percentage: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Percentage of allowed calls during HALF_OPEN state"
    )
    service_name: str = Field(
        default="unknown",
        description="Name of the service for logging and monitoring"
    )


class CircuitBreakerMetrics(BaseModel):
    """Metrics tracked by the circuit breaker."""

    total_requests: int = 0
    total_failures: int = 0
    total_successes: int = 0
    last_failure_time: Optional[int] = None
    last_success_time: Optional[int] = None
    half_open_attempts: int = 0
    half_open_successes: int = 0
    state: CircuitState
    state_change_time: int


class CircuitBreaker:
    """Main CircuitBreaker class.

    Implements the circuit breaker pattern for fault tolerance.

    Example:
        ```python
        breaker = CircuitBreaker(
            CircuitBreakerConfig(
                service_name='openrouter',
                failure_threshold=5,
                reset_timeout=30000,
                success_threshold=2,
            )
        )

        try:
            result = await breaker.execute(
                lambda: call_openrouter_api(),
            )
        except CircuitBreakerOpenError:
            print('Service is down, use fallback')
        ```
    """

    def __init__(self, config: CircuitBreakerConfig | None = None):
        """Creates a new CircuitBreaker instance.

        Args:
            config: Configuration options (uses defaults if None).
        """
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_attempts = 0
        self.half_open_successes = 0
        self.last_failure_time: Optional[int] = None
        self.last_success_time: Optional[int] = None
        self.next_attempt_time = 0

        self.metrics = CircuitBreakerMetrics(
            state=CircuitState.CLOSED,
            state_change_time=self._current_time_ms(),
        )

    def _current_time_ms(self) -> int:
        """Get current time in milliseconds."""
        return int(time.time() * 1000)

    async def execute(
        self,
        fn: Callable[[], T],
    ) -> T:
        """Executes a function with circuit breaker protection.

        Throws CircuitBreakerOpenError if circuit is open.

        Args:
            fn: Async function to execute.

        Returns:
            Result of function execution.

        Raises:
            CircuitBreakerOpenError: If circuit is open.
            Exception: Original error if function throws.
        """
        # Check current state and update if needed
        self._update_state()

        # Increment request counter
        self.metrics.total_requests += 1

        # Check if circuit is open
        if self.state == CircuitState.OPEN:
            error = CircuitBreakerOpenError(self.config.service_name)
            print(
                f"[CircuitBreaker] {self.config.service_name} is OPEN - "
                f"next attempt at {time.ctime(self.next_attempt_time / 1000)}"
            )
            raise error

        # In HALF_OPEN state, limit call percentage
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_attempts += 1
            self.metrics.half_open_attempts += 1

            allow_call = random.random() < self.config.half_open_call_percentage
            if not allow_call:
                error = CircuitBreakerOpenError(self.config.service_name)
                raise error

        # Execute the function
        try:
            result = await fn()
            self._on_success()
            return result
        except Exception as error:
            await self._on_failure(error)
            raise error

    def get_state(self) -> CircuitState:
        """Gets the current state of the circuit."""
        self._update_state()
        return self.state

    def get_metrics(self) -> CircuitBreakerMetrics:
        """Gets current metrics."""
        return self.metrics.model_copy()

    def reset(self) -> None:
        """Manually resets the circuit to CLOSED state.

        Useful for external recovery signals or monitoring dashboards.
        """
        previous_state = self.state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_attempts = 0
        self.half_open_successes = 0
        self.next_attempt_time = 0

        # Reset all metrics including totals
        self.metrics = CircuitBreakerMetrics(
            state=CircuitState.CLOSED,
            state_change_time=self._current_time_ms(),
        )

        print(
            f"[CircuitBreaker] {self.config.service_name} reset "
            f"from {previous_state} to CLOSED"
        )

    def open(self) -> None:
        """Force opens the circuit.

        Useful when external monitoring detects issues.
        """
        previous_state = self.state
        self.state = CircuitState.OPEN
        self.next_attempt_time = self._current_time_ms() + self.config.reset_timeout
        self.failure_count = self.config.failure_threshold

        self.metrics.state = CircuitState.OPEN
        self.metrics.state_change_time = self._current_time_ms()

        print(
            f"[CircuitBreaker] {self.config.service_name} forced open "
            f"from {previous_state}"
        )

    def _update_state(self) -> None:
        """Updates circuit state based on time and current failure count."""
        if self.state == CircuitState.OPEN:
            # Check if it's time to attempt recovery
            if self._current_time_ms() >= self.next_attempt_time:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self.half_open_attempts = 0
                self.half_open_successes = 0

                self.metrics.state = CircuitState.HALF_OPEN
                self.metrics.state_change_time = self._current_time_ms()

                print(
                    f"[CircuitBreaker] {self.config.service_name} transitioning "
                    f"to HALF_OPEN to test recovery"
                )

    def _on_success(self) -> None:
        """Handles successful function execution."""
        self.failure_count = 0
        self.success_count += 1
        self.last_success_time = self._current_time_ms()
        self.metrics.total_successes += 1
        self.metrics.last_success_time = self.last_success_time

        if self.state == CircuitState.CLOSED:
            # Normal operation, reset success counter
            self.success_count = 0
        elif self.state == CircuitState.HALF_OPEN:
            self.half_open_successes += 1
            self.metrics.half_open_successes += 1

            # Check if we've achieved enough successes to close
            if self.half_open_successes >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.success_count = 0
                self.failure_count = 0

                self.metrics.state = CircuitState.CLOSED
                self.metrics.state_change_time = self._current_time_ms()

                print(
                    f"[CircuitBreaker] {self.config.service_name} recovered - "
                    f"closing circuit"
                )

    async def _on_failure(self, error: Exception) -> None:
        """Handles failed function execution."""
        self.failure_count += 1
        self.last_failure_time = self._current_time_ms()
        self.metrics.total_failures += 1
        self.metrics.last_failure_time = self.last_failure_time

        error_message = str(error)

        if self.state == CircuitState.HALF_OPEN:
            # Failure during recovery test - reopen circuit
            self.state = CircuitState.OPEN
            self.next_attempt_time = self._current_time_ms() + self.config.reset_timeout
            self.success_count = 0

            self.metrics.state = CircuitState.OPEN
            self.metrics.state_change_time = self._current_time_ms()

            print(
                f"[CircuitBreaker] {self.config.service_name} failed during "
                f"recovery test, reopening circuit: {error_message}"
            )

        elif self.state == CircuitState.CLOSED:
            # Regular failure in closed state
            if self.failure_count >= self.config.failure_threshold:
                # Threshold reached, open circuit
                self.state = CircuitState.OPEN
                self.next_attempt_time = (
                    self._current_time_ms() + self.config.reset_timeout
                )

                self.metrics.state = CircuitState.OPEN
                self.metrics.state_change_time = self._current_time_ms()

                print(
                    f"[CircuitBreaker] {self.config.service_name} failure threshold "
                    f"reached ({self.failure_count}/{self.config.failure_threshold}) - "
                    f"opening circuit"
                )
            else:
                # Log failure but stay closed
                print(
                    f"[CircuitBreaker] {self.config.service_name} failure "
                    f"({self.failure_count}/{self.config.failure_threshold}): "
                    f"{error_message}"
                )
