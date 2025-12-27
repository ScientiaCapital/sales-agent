"""Circuit Breaker Registry for External API Services.

Provides pre-configured circuit breakers for all external API integrations.
Each service gets its own circuit breaker with appropriate thresholds.

Usage:
    from app.services.circuit_breaker_registry import get_circuit_breaker

    # In your service method:
    breaker = get_circuit_breaker("apollo")
    result = await breaker.call(self._make_api_request, params)
"""

from typing import Dict
from app.services.circuit_breaker import CircuitBreaker

# Global registry of circuit breakers
_circuit_breakers: Dict[str, CircuitBreaker] = {}

# Configuration for each external service
# Format: (failure_threshold, recovery_timeout_seconds, success_threshold)
CIRCUIT_BREAKER_CONFIG = {
    # LLM Providers - Lower threshold since they're critical
    "cerebras": (3, 30, 2),      # Opens after 3 failures, recovers in 30s
    "claude": (3, 30, 2),
    "deepseek": (5, 60, 2),
    "openrouter": (5, 45, 2),

    # Enrichment APIs - Higher threshold (transient failures more common)
    "apollo": (5, 60, 2),        # Opens after 5 failures, recovers in 60s
    "hunter": (5, 60, 2),
    "linkedin": (5, 90, 3),      # LinkedIn more restrictive, longer recovery

    # Communication APIs
    "slack": (5, 30, 2),
    "twilio": (3, 30, 2),        # Critical for voice, lower threshold
    "sendgrid": (5, 45, 2),

    # CRM APIs
    "close_crm": (5, 60, 2),
    "hubspot": (5, 60, 2),

    # Scraping/Data services
    "browserbase": (5, 60, 2),
    "firecrawl": (5, 45, 2),
    "assemblyai": (5, 60, 2),    # Call transcription

    # Default for any unspecified service
    "default": (5, 60, 2),
}


def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    """
    Get or create a circuit breaker for the specified service.

    Args:
        service_name: Name of the external service (e.g., "apollo", "cerebras")

    Returns:
        CircuitBreaker instance configured for the service
    """
    if service_name not in _circuit_breakers:
        # Get config for this service, fallback to default
        config = CIRCUIT_BREAKER_CONFIG.get(
            service_name.lower(),
            CIRCUIT_BREAKER_CONFIG["default"]
        )
        failure_threshold, recovery_timeout, success_threshold = config

        _circuit_breakers[service_name] = CircuitBreaker(
            name=service_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold
        )

    return _circuit_breakers[service_name]


def get_all_circuit_breaker_status() -> Dict[str, dict]:
    """
    Get status of all active circuit breakers.

    Returns:
        Dict mapping service name to status dict
    """
    return {
        name: breaker.get_status()
        for name, breaker in _circuit_breakers.items()
    }


def reset_circuit_breaker(service_name: str) -> bool:
    """
    Reset a circuit breaker to closed state.

    Args:
        service_name: Name of the service

    Returns:
        True if reset, False if service not found
    """
    if service_name in _circuit_breakers:
        breaker = _circuit_breakers[service_name]
        breaker._state = breaker._state.__class__.CLOSED
        breaker._failure_count = 0
        breaker._success_count = 0
        return True
    return False
