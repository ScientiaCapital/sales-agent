"""
Custom Exception Hierarchy for Sales Agent Platform

Provides domain-specific exceptions with structured error codes, logging,
and user-friendly messages for better debugging and error handling.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
import traceback

logger = logging.getLogger(__name__)


class SalesAgentException(Exception):
    """
    Base exception for all Sales Agent errors.

    Attributes:
        error_code: Unique error identifier for logging/debugging
        message: User-friendly error message
        details: Technical details for logging (not exposed to users)
        status_code: HTTP status code (default: 500)
    """

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.status_code = status_code
        self.timestamp = datetime.utcnow().isoformat()

        # Log the error with full context
        logger.error(
            f"[{error_code}] {message}",
            extra={
                "error_code": error_code,
                "details": details,
                "status_code": status_code,
                "timestamp": self.timestamp
            },
            exc_info=True
        )

        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.error_code,
            "message": self.message,
            "timestamp": self.timestamp
        }


# ============================================================================
# Lead Qualification Errors
# ============================================================================

class LeadQualificationError(SalesAgentException):
    """Errors during lead qualification process."""

    def __init__(
        self,
        message: str = "Lead qualification failed",
        error_code: str = "LEAD_QUALIFICATION_FAILED",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            status_code=500
        )


class CerebrasAPIError(LeadQualificationError):
    """Errors from Cerebras API calls."""

    def __init__(
        self,
        message: str = "Cerebras API request failed",
        error_code: str = "CEREBRAS_API_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details
        )


class CerebrasTimeoutError(CerebrasAPIError):
    """Cerebras API timeout errors."""

    def __init__(
        self,
        message: str = "Cerebras API request timed out",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="CEREBRAS_API_TIMEOUT",
            details=details
        )


class CerebrasRateLimitError(CerebrasAPIError):
    """Cerebras API rate limit errors."""

    def __init__(
        self,
        message: str = "Cerebras API rate limit exceeded",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="CEREBRAS_RATE_LIMIT",
            details=details
        )
        self.status_code = 429  # Too Many Requests


# ============================================================================
# External API Errors
# ============================================================================

class ExternalAPIError(SalesAgentException):
    """Errors from external API calls (RunPod, social media, etc.)."""

    def __init__(
        self,
        message: str = "External API request failed",
        error_code: str = "EXTERNAL_API_ERROR",
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 502  # Bad Gateway
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            status_code=status_code
        )


class RunPodAPIError(ExternalAPIError):
    """Errors from RunPod API calls."""

    def __init__(
        self,
        message: str = "RunPod API request failed",
        error_code: str = "RUNPOD_API_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details
        )


class RunPodTimeoutError(RunPodAPIError):
    """RunPod API timeout errors."""

    def __init__(
        self,
        message: str = "RunPod API request timed out",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="RUNPOD_API_TIMEOUT",
            details=details
        )


class SocialMediaAPIError(ExternalAPIError):
    """Errors from social media API calls (Twitter, Reddit, LinkedIn)."""

    def __init__(
        self,
        message: str = "Social media API request failed",
        error_code: str = "SOCIAL_MEDIA_API_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details
        )


class TwitterAPIError(SocialMediaAPIError):
    """Twitter/X API specific errors."""

    def __init__(
        self,
        message: str = "Twitter API request failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="TWITTER_API_ERROR",
            details=details
        )


class RedditAPIError(SocialMediaAPIError):
    """Reddit API specific errors."""

    def __init__(
        self,
        message: str = "Reddit API request failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="REDDIT_API_ERROR",
            details=details
        )


# ============================================================================
# Storage Errors
# ============================================================================

class StorageError(SalesAgentException):
    """Errors related to storage operations (S3, local filesystem)."""

    def __init__(
        self,
        message: str = "Storage operation failed",
        error_code: str = "STORAGE_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            status_code=500
        )


class S3UploadError(StorageError):
    """S3 upload operation errors."""

    def __init__(
        self,
        message: str = "S3 upload failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="S3_UPLOAD_FAILED",
            details=details
        )


class S3DownloadError(StorageError):
    """S3 download operation errors."""

    def __init__(
        self,
        message: str = "S3 download failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="S3_DOWNLOAD_FAILED",
            details=details
        )


# ============================================================================
# Database Errors
# ============================================================================

class DatabaseError(SalesAgentException):
    """Errors during database operations."""

    def __init__(
        self,
        message: str = "Database operation failed",
        error_code: str = "DATABASE_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            status_code=500
        )


class DatabaseConnectionError(DatabaseError):
    """Database connection failures."""

    def __init__(
        self,
        message: str = "Failed to connect to database",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="DATABASE_CONNECTION_ERROR",
            details=details
        )


class DatabaseQueryError(DatabaseError):
    """Database query execution failures."""

    def __init__(
        self,
        message: str = "Database query failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="DATABASE_QUERY_ERROR",
            details=details
        )


# ============================================================================
# Validation Errors
# ============================================================================

class ValidationError(SalesAgentException):
    """Input validation errors."""

    def __init__(
        self,
        message: str = "Validation failed",
        error_code: str = "VALIDATION_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            status_code=400  # Bad Request
        )


class InvalidFileFormatError(ValidationError):
    """Invalid file format errors."""

    def __init__(
        self,
        message: str = "Invalid file format",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="INVALID_FILE_FORMAT",
            details=details
        )


class FileSizeExceededError(ValidationError):
    """File size limit exceeded errors."""

    def __init__(
        self,
        message: str = "File size exceeds maximum allowed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="FILE_SIZE_EXCEEDED",
            details=details
        )


class MissingRequiredFieldError(ValidationError):
    """Missing required field errors."""

    def __init__(
        self,
        message: str = "Missing required field",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="MISSING_REQUIRED_FIELD",
            details=details
        )


# ============================================================================
# Resource Errors
# ============================================================================

class ResourceNotFoundError(SalesAgentException):
    """Resource not found errors."""

    def __init__(
        self,
        message: str = "Resource not found",
        error_code: str = "RESOURCE_NOT_FOUND",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            status_code=404  # Not Found
        )


class LeadNotFoundError(ResourceNotFoundError):
    """Lead not found errors."""

    def __init__(
        self,
        lead_id: int,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        details["lead_id"] = lead_id

        super().__init__(
            message=f"Lead with ID {lead_id} not found",
            error_code="LEAD_NOT_FOUND",
            details=details
        )


class DocumentNotFoundError(ResourceNotFoundError):
    """Document not found errors."""

    def __init__(
        self,
        document_id: int,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        details["document_id"] = document_id

        super().__init__(
            message=f"Document with ID {document_id} not found",
            error_code="DOCUMENT_NOT_FOUND",
            details=details
        )


# ============================================================================
# Authentication/Authorization Errors (Future use)
# ============================================================================

class AuthenticationError(SalesAgentException):
    """Authentication errors."""

    def __init__(
        self,
        message: str = "Authentication failed",
        error_code: str = "AUTHENTICATION_FAILED",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            status_code=401  # Unauthorized
        )


class AuthorizationError(SalesAgentException):
    """Authorization/permission errors."""

    def __init__(
        self,
        message: str = "Access denied",
        error_code: str = "ACCESS_DENIED",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            status_code=403  # Forbidden
        )


# ============================================================================
# Service Unavailable Errors
# ============================================================================

class ServiceUnavailableError(SalesAgentException):
    """Service temporarily unavailable errors."""

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        error_code: str = "SERVICE_UNAVAILABLE",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            status_code=503  # Service Unavailable
        )


class CircuitBreakerOpenError(ServiceUnavailableError):
    """Circuit breaker is open, preventing requests."""

    def __init__(
        self,
        service_name: str,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        details["service_name"] = service_name

        super().__init__(
            message=f"Service {service_name} is temporarily unavailable (circuit breaker open)",
            error_code="CIRCUIT_BREAKER_OPEN",
            details=details
        )


# ============================================================================
# Configuration Errors
# ============================================================================

class ConfigurationError(SalesAgentException):
    """Configuration errors."""

    def __init__(
        self,
        message: str = "Configuration error",
        error_code: str = "CONFIGURATION_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            status_code=500
        )


class MissingAPIKeyError(ConfigurationError):
    """Missing API key configuration errors."""

    def __init__(
        self,
        service_name: str,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        details["service_name"] = service_name

        super().__init__(
            message=f"{service_name} API key not configured",
            error_code="MISSING_API_KEY",
            details=details
        )
        self.status_code = 501  # Not Implemented
