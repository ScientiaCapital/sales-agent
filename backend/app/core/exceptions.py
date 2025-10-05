"""
Custom Exception Hierarchy for Sales Agent Platform

This module defines domain-specific exceptions to replace generic exceptions
throughout the codebase. All custom exceptions inherit from SalesAgentException
and include error codes, HTTP status codes, and logging context.

Exception Hierarchy:
    SalesAgentException (base)
    ├── LeadException
    │   ├── LeadValidationError (400)
    │   ├── LeadNotFoundError (404)
    │   └── LeadQualificationError (500)
    ├── CRMException (imported from app.services.crm.base)
    │   ├── CRMAuthenticationError (401)
    │   ├── CRMRateLimitError (429)
    │   ├── CRMNotFoundError (404)
    │   ├── CRMValidationError (422)
    │   ├── CRMNetworkError (502)
    │   └── CRMWebhookError (400)
    ├── VoiceException
    │   ├── CartesiaAPIError (502)
    │   ├── VoiceGenerationError (500)
    │   └── AudioProcessingError (500)
    ├── DocumentException
    │   ├── PDFProcessingError (500)
    │   ├── DocumentParsingError (422)
    │   └── DocumentNotFoundError (404)
    └── ExternalAPIException
        ├── APIConnectionError (502)
        ├── APIRateLimitError (429)
        └── APIAuthenticationError (401)

Usage:
    >>> raise LeadNotFoundError(f"Lead {lead_id} not found", context={"lead_id": lead_id})
    >>> raise CartesiaAPIError("Voice generation failed", context={"voice_id": "abc"})
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# BASE EXCEPTION
# ============================================================================


class SalesAgentException(Exception):
    """
    Base exception for all Sales Agent application errors.
    
    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error code (e.g., "LEAD_NOT_FOUND")
        status_code: HTTP status code for API responses
        context: Additional context data (lead_id, api_name, etc.)
    
    Example:
        raise SalesAgentException(
            message="Operation failed",
            error_code="OPERATION_ERROR",
            status_code=500,
            context={"operation": "qualify_lead", "lead_id": 123}
        )
    """
    
    def __init__(
        self,
        message: str,
        error_code: str = "SALES_AGENT_ERROR",
        status_code: int = 500,
        context: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.context = context or {}
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization"""
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "context": self.context
            }
        }
    
    def __str__(self) -> str:
        """String representation for logging"""
        if self.context:
            return f"{self.error_code}: {self.message} (context: {self.context})"
        return f"{self.error_code}: {self.message}"
    
    def __repr__(self) -> str:
        """Detailed representation for debugging"""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"error_code={self.error_code!r}, "
            f"status_code={self.status_code}, "
            f"context={self.context!r})"
        )


# ============================================================================
# LEAD EXCEPTIONS
# ============================================================================


class LeadException(SalesAgentException):
    """Base exception for lead-related errors"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "LEAD_ERROR",
        status_code: int = 500,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, status_code, context)


class LeadValidationError(LeadException):
    """Lead data validation failed"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="LEAD_VALIDATION_ERROR",
            status_code=400,
            context=context
        )


class LeadNotFoundError(LeadException):
    """Lead not found in database"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="LEAD_NOT_FOUND",
            status_code=404,
            context=context
        )


class LeadQualificationError(LeadException):
    """Lead qualification process failed"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="LEAD_QUALIFICATION_ERROR",
            status_code=500,
            context=context
        )


# ============================================================================
# VOICE EXCEPTIONS
# ============================================================================


class VoiceException(SalesAgentException):
    """Base exception for voice-related errors"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "VOICE_ERROR",
        status_code: int = 500,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, status_code, context)


class CartesiaAPIError(VoiceException):
    """Cartesia API call failed"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="CARTESIA_API_ERROR",
            status_code=502,
            context=context
        )


class VoiceGenerationError(VoiceException):
    """Voice generation process failed"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="VOICE_GENERATION_ERROR",
            status_code=500,
            context=context
        )


class AudioProcessingError(VoiceException):
    """Audio processing failed"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="AUDIO_PROCESSING_ERROR",
            status_code=500,
            context=context
        )


class VoiceSessionNotFoundError(VoiceException):
    """Voice session not found"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="VOICE_SESSION_NOT_FOUND",
            status_code=404,
            context=context
        )


# ============================================================================
# DOCUMENT EXCEPTIONS
# ============================================================================


class DocumentException(SalesAgentException):
    """Base exception for document processing errors"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "DOCUMENT_ERROR",
        status_code: int = 500,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, status_code, context)


class PDFProcessingError(DocumentException):
    """PDF processing failed"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="PDF_PROCESSING_ERROR",
            status_code=500,
            context=context
        )


class DocumentParsingError(DocumentException):
    """Document parsing failed"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="DOCUMENT_PARSING_ERROR",
            status_code=422,
            context=context
        )


class DocumentNotFoundError(DocumentException):
    """Document not found"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="DOCUMENT_NOT_FOUND",
            status_code=404,
            context=context
        )


class UnsupportedDocumentTypeError(DocumentException):
    """Unsupported document type"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="UNSUPPORTED_DOCUMENT_TYPE",
            status_code=400,
            context=context
        )


class DocumentTooLargeError(DocumentException):
    """Document exceeds size limit"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="DOCUMENT_TOO_LARGE",
            status_code=413,
            context=context
        )


# ============================================================================
# EXTERNAL API EXCEPTIONS
# ============================================================================


class ExternalAPIException(SalesAgentException):
    """Base exception for external API errors"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "EXTERNAL_API_ERROR",
        status_code: int = 502,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, status_code, context)


class APIConnectionError(ExternalAPIException):
    """Failed to connect to external API"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="API_CONNECTION_ERROR",
            status_code=502,
            context=context
        )


class APIRateLimitError(ExternalAPIException):
    """External API rate limit exceeded"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None
    ):
        super().__init__(
            message=message,
            error_code="API_RATE_LIMIT_ERROR",
            status_code=429,
            context=context
        )
        self.retry_after = retry_after  # Seconds until rate limit resets


class APIAuthenticationError(ExternalAPIException):
    """External API authentication failed"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="API_AUTHENTICATION_ERROR",
            status_code=401,
            context=context
        )


class APITimeoutError(ExternalAPIException):
    """External API request timed out"""

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="API_TIMEOUT_ERROR",
            status_code=504,
            context=context
        )


class CerebrasAPIError(ExternalAPIException):
    """Cerebras Cloud API error"""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="CEREBRAS_API_ERROR",
            status_code=502,
            context=details
        )


class CerebrasTimeoutError(ExternalAPIException):
    """Cerebras API request timeout"""

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="CEREBRAS_TIMEOUT",
            status_code=504,
            context=context
        )


# ============================================================================
# CONFIGURATION EXCEPTIONS
# ============================================================================


class ConfigurationError(SalesAgentException):
    """Application configuration error"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            status_code=500,
            context=context
        )


class MissingAPIKeyError(ConfigurationError):
    """Required API key not found in environment"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            context=context
        )
        self.error_code = "MISSING_API_KEY"


# ============================================================================
# VALIDATION EXCEPTIONS
# ============================================================================


class ValidationError(SalesAgentException):
    """Data validation error"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            context=context
        )


class InvalidInputError(ValidationError):
    """Invalid input data provided"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            context=context
        )
        self.error_code = "INVALID_INPUT"


# ============================================================================
# RESOURCE EXCEPTIONS
# ============================================================================


class ResourceNotFoundError(SalesAgentException):
    """Generic resource not found error"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="RESOURCE_NOT_FOUND",
            status_code=404,
            context=context
        )


class ResourceConflictError(SalesAgentException):
    """Resource conflict (duplicate, version mismatch)"""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="RESOURCE_CONFLICT",
            status_code=409,
            context=context
        )


# ============================================================================
# EXCEPTION CATALOG
# ============================================================================

# Mapping of error codes to exception classes for reverse lookup
ERROR_CODE_MAPPING = {
    "SALES_AGENT_ERROR": SalesAgentException,
    "LEAD_ERROR": LeadException,
    "LEAD_VALIDATION_ERROR": LeadValidationError,
    "LEAD_NOT_FOUND": LeadNotFoundError,
    "LEAD_QUALIFICATION_ERROR": LeadQualificationError,
    "VOICE_ERROR": VoiceException,
    "CARTESIA_API_ERROR": CartesiaAPIError,
    "VOICE_GENERATION_ERROR": VoiceGenerationError,
    "AUDIO_PROCESSING_ERROR": AudioProcessingError,
    "VOICE_SESSION_NOT_FOUND": VoiceSessionNotFoundError,
    "DOCUMENT_ERROR": DocumentException,
    "PDF_PROCESSING_ERROR": PDFProcessingError,
    "DOCUMENT_PARSING_ERROR": DocumentParsingError,
    "DOCUMENT_NOT_FOUND": DocumentNotFoundError,
    "UNSUPPORTED_DOCUMENT_TYPE": UnsupportedDocumentTypeError,
    "DOCUMENT_TOO_LARGE": DocumentTooLargeError,
    "EXTERNAL_API_ERROR": ExternalAPIException,
    "API_CONNECTION_ERROR": APIConnectionError,
    "API_RATE_LIMIT_ERROR": APIRateLimitError,
    "API_AUTHENTICATION_ERROR": APIAuthenticationError,
    "API_TIMEOUT_ERROR": APITimeoutError,
    "CEREBRAS_API_ERROR": CerebrasAPIError,
    "CEREBRAS_TIMEOUT": CerebrasTimeoutError,
    "CONFIGURATION_ERROR": ConfigurationError,
    "MISSING_API_KEY": MissingAPIKeyError,
    "VALIDATION_ERROR": ValidationError,
    "INVALID_INPUT": InvalidInputError,
    "RESOURCE_NOT_FOUND": ResourceNotFoundError,
    "RESOURCE_CONFLICT": ResourceConflictError,
}
