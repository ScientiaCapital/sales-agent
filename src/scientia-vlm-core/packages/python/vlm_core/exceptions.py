"""Exception hierarchy for VLM core.

Following the principle: Errors should never pass silently.
All provider errors should be caught and wrapped in these exceptions.
"""


class VLMError(Exception):
    """Base exception for all VLM errors.

    All custom exceptions in vlm-ai-core inherit from this.
    Makes it easy to catch all VLM errors with one except clause.
    """
    pass


class ProviderError(VLMError):
    """Exception raised when a VLM provider operation fails.

    Examples:
    - API request failures
    - Invalid API keys
    - Service unavailable
    - Network timeouts
    """
    pass


class RateLimitError(VLMError):
    """Exception raised when rate limits are exceeded.

    Includes information about when the limit resets.
    """
    def __init__(self, message: str, retry_after: float = 0):
        super().__init__(message)
        self.retry_after = retry_after


class CreditError(VLMError):
    """Exception raised when credits/quota are exhausted.

    Examples:
    - Daily API quota exceeded
    - Prepaid credits depleted
    - Free tier limits reached
    """
    pass


class ConfigurationError(VLMError):
    """Exception raised when configuration is invalid.

    Examples:
    - Missing required API keys
    - Invalid parameter values
    - Unsupported model/image combinations
    """
    pass


class CircuitBreakerOpenError(VLMError):
    """Exception raised when circuit breaker is open.

    Indicates the service is currently unavailable and calls are being blocked
    to prevent cascading failures.
    """
    def __init__(self, service_name: str):
        super().__init__(f"Circuit breaker is OPEN for service: {service_name}")
        self.service_name = service_name


class RetryExhaustedError(VLMError):
    """Exception raised when all retry attempts are exhausted.

    Contains the number of attempts and the last error encountered.
    """
    def __init__(self, attempts: int, last_error: Exception):
        message = f"All {attempts} retry attempts exhausted. Last error: {str(last_error)}"
        super().__init__(message)
        self.attempts = attempts
        self.last_error = last_error


class NonRetryableError(VLMError):
    """Marker to indicate an error should not be retried.

    Wrap errors with this class to skip retry logic.
    """
    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error
