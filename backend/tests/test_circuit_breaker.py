"""Unit tests for circuit breaker resilience pattern."""

import pytest
from unittest.mock import Mock, AsyncMock
import asyncio
from datetime import datetime, timedelta

from app.services.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerError


@pytest.fixture
def circuit_breaker():
    """Create CircuitBreaker instance with test configuration."""
    return CircuitBreaker(
        failure_threshold=3,
        timeout_seconds=60,
        half_open_max_calls=2
    )


class TestCircuitBreaker:
    """Test suite for CircuitBreaker pattern."""

    @pytest.mark.asyncio
    async def test_initial_state_closed(self, circuit_breaker):
        """Test circuit breaker starts in CLOSED state."""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_successful_call_in_closed_state(self, circuit_breaker):
        """Test successful calls in CLOSED state."""
        async def successful_call():
            return "success"

        result = await circuit_breaker.call(successful_call)

        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_failure_increments_count(self, circuit_breaker):
        """Test failures increment failure count."""
        async def failing_call():
            raise Exception("Service unavailable")

        with pytest.raises(Exception):
            await circuit_breaker.call(failing_call)

        assert circuit_breaker.failure_count == 1
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self, circuit_breaker):
        """Test circuit opens after hitting failure threshold."""
        async def failing_call():
            raise Exception("Service error")

        # Trigger 3 failures to open circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_call)

        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.failure_count == 3

    @pytest.mark.asyncio
    async def test_rejects_calls_when_open(self, circuit_breaker):
        """Test circuit rejects calls when OPEN."""
        async def any_call():
            return "result"

        # Force circuit open
        circuit_breaker.state = CircuitState.OPEN
        circuit_breaker.failure_count = 3

        with pytest.raises(CircuitBreakerError, match="Circuit breaker is OPEN"):
            await circuit_breaker.call(any_call)

    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_timeout(self, circuit_breaker):
        """Test circuit transitions to HALF_OPEN after timeout."""
        # Set breaker to OPEN with past timeout
        circuit_breaker.state = CircuitState.OPEN
        circuit_breaker.failure_count = 3
        circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=61)

        async def test_call():
            return "test"

        # Next call should transition to HALF_OPEN
        result = await circuit_breaker.call(test_call)

        assert result == "test"
        assert circuit_breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(self, circuit_breaker):
        """Test successful calls in HALF_OPEN close the circuit."""
        circuit_breaker.state = CircuitState.HALF_OPEN
        circuit_breaker.failure_count = 3

        async def successful_call():
            return "success"

        # Make successful calls up to half_open_max_calls
        for _ in range(2):
            result = await circuit_breaker.call(successful_call)
            assert result == "success"

        # Should transition back to CLOSED
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self, circuit_breaker):
        """Test failure in HALF_OPEN reopens the circuit."""
        circuit_breaker.state = CircuitState.HALF_OPEN

        async def failing_call():
            raise Exception("Still failing")

        with pytest.raises(Exception):
            await circuit_breaker.call(failing_call)

        assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_reset_circuit(self, circuit_breaker):
        """Test manual circuit reset."""
        # Force circuit open
        circuit_breaker.state = CircuitState.OPEN
        circuit_breaker.failure_count = 5

        circuit_breaker.reset()

        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_concurrent_calls_in_closed_state(self, circuit_breaker):
        """Test handling concurrent calls when circuit is CLOSED."""
        async def slow_call(delay):
            await asyncio.sleep(delay)
            return f"result_{delay}"

        tasks = [
            circuit_breaker.call(lambda d=d: slow_call(d))
            for d in [0.1, 0.05, 0.15]
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        assert circuit_breaker.state == CircuitState.CLOSED

    def test_get_state_info(self, circuit_breaker):
        """Test retrieving circuit state information."""
        info = circuit_breaker.get_state_info()

        assert "state" in info
        assert "failure_count" in info
        assert "failure_threshold" in info
        assert info["state"] == "CLOSED"
        assert info["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_different_failure_thresholds(self):
        """Test circuit with different failure thresholds."""
        cb_low = CircuitBreaker(failure_threshold=2)
        cb_high = CircuitBreaker(failure_threshold=10)

        async def failing_call():
            raise Exception("Fail")

        # Low threshold opens after 2 failures
        for _ in range(2):
            with pytest.raises(Exception):
                await cb_low.call(failing_call)
        assert cb_low.state == CircuitState.OPEN

        # High threshold still closed after 2 failures
        for _ in range(2):
            with pytest.raises(Exception):
                await cb_high.call(failing_call)
        assert cb_high.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self, circuit_breaker):
        """Test successful call resets failure count in CLOSED state."""
        async def failing_call():
            raise Exception("Fail")

        async def successful_call():
            return "success"

        # Accumulate some failures
        for _ in range(2):
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_call)

        assert circuit_breaker.failure_count == 2

        # Successful call should reset
        await circuit_breaker.call(successful_call)

        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_timeout_configuration(self):
        """Test different timeout configurations."""
        cb_short = CircuitBreaker(timeout_seconds=1)
        cb_long = CircuitBreaker(timeout_seconds=300)

        # Force both open
        cb_short.state = CircuitState.OPEN
        cb_short.last_failure_time = datetime.now() - timedelta(seconds=2)
        
        cb_long.state = CircuitState.OPEN
        cb_long.last_failure_time = datetime.now() - timedelta(seconds=2)

        async def test_call():
            return "test"

        # Short timeout should transition to HALF_OPEN
        await cb_short.call(test_call)
        assert cb_short.state == CircuitState.HALF_OPEN

        # Long timeout should still reject
        with pytest.raises(CircuitBreakerError):
            await cb_long.call(test_call)
        assert cb_long.state == CircuitState.OPEN


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker in realistic scenarios."""

    @pytest.mark.asyncio
    async def test_protect_flaky_service(self):
        """Test circuit breaker protecting against flaky service."""
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=1)
        call_count = 0

        async def flaky_service():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise Exception("Service error")
            return "success"

        # First 3 calls fail, opening circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await cb.call(flaky_service)

        assert cb.state == CircuitState.OPEN

        # Circuit rejects without calling service
        with pytest.raises(CircuitBreakerError):
            await cb.call(flaky_service)

        # Still 3 calls (circuit prevented 4th)
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_recovery_scenario(self):
        """Test full recovery scenario: CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=0.1)
        
        async def failing_service():
            raise Exception("Down")

        async def recovered_service():
            return "success"

        # 1. Start CLOSED
        assert cb.state == CircuitState.CLOSED

        # 2. Failures open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await cb.call(failing_service)

        assert cb.state == CircuitState.OPEN

        # 3. Wait for timeout
        await asyncio.sleep(0.2)

        # 4. Next call transitions to HALF_OPEN
        result = await cb.call(recovered_service)
        assert cb.state == CircuitState.HALF_OPEN

        # 5. Successful calls close circuit
        await cb.call(recovered_service)
        assert cb.state == CircuitState.CLOSED
