"""
Tests for custom exception hierarchy

Verifies exception behavior, error codes, status codes, and serialization.
"""

import pytest
from app.core.exceptions import (
    SalesAgentException,
    LeadException,
    LeadValidationError,
    LeadNotFoundError,
    LeadQualificationError,
    VoiceException,
    CartesiaAPIError,
    VoiceGenerationError,
    AudioProcessingError,
    VoiceSessionNotFoundError,
    DocumentException,
    PDFProcessingError,
    DocumentParsingError,
    DocumentNotFoundError,
    UnsupportedDocumentTypeError,
    DocumentTooLargeError,
    ExternalAPIException,
    APIConnectionError,
    APIRateLimitError,
    APIAuthenticationError,
    APITimeoutError,
    ConfigurationError,
    MissingAPIKeyError,
    ValidationError,
    InvalidInputError,
    ResourceNotFoundError,
    ResourceConflictError,
    ERROR_CODE_MAPPING,
)


class TestBaseException:
    """Test SalesAgentException base class"""
    
    def test_basic_exception(self):
        """Test basic exception creation"""
        exc = SalesAgentException(
            message="Test error",
            error_code="TEST_ERROR",
            status_code=500,
            context={"key": "value"}
        )
        
        assert exc.message == "Test error"
        assert exc.error_code == "TEST_ERROR"
        assert exc.status_code == 500
        assert exc.context == {"key": "value"}
    
    def test_exception_defaults(self):
        """Test exception with default values"""
        exc = SalesAgentException("Test error")
        
        assert exc.message == "Test error"
        assert exc.error_code == "SALES_AGENT_ERROR"
        assert exc.status_code == 500
        assert exc.context == {}
    
    def test_to_dict(self):
        """Test to_dict serialization"""
        exc = SalesAgentException(
            message="Test error",
            error_code="TEST_ERROR",
            status_code=400,
            context={"lead_id": 123}
        )
        
        result = exc.to_dict()
        
        assert result == {
            "error": {
                "code": "TEST_ERROR",
                "message": "Test error",
                "context": {"lead_id": 123}
            }
        }
    
    def test_str_representation(self):
        """Test string representation"""
        exc = SalesAgentException(
            message="Test error",
            error_code="TEST_ERROR",
            context={"key": "value"}
        )
        
        assert str(exc) == "TEST_ERROR: Test error (context: {'key': 'value'})"
    
    def test_str_without_context(self):
        """Test string representation without context"""
        exc = SalesAgentException(
            message="Test error",
            error_code="TEST_ERROR"
        )
        
        assert str(exc) == "TEST_ERROR: Test error"
    
    def test_repr_representation(self):
        """Test repr representation"""
        exc = SalesAgentException(
            message="Test error",
            error_code="TEST_ERROR",
            status_code=400,
            context={"key": "value"}
        )
        
        repr_str = repr(exc)
        assert "SalesAgentException" in repr_str
        assert "message='Test error'" in repr_str
        assert "error_code='TEST_ERROR'" in repr_str
        assert "status_code=400" in repr_str


class TestLeadExceptions:
    """Test lead-related exceptions"""
    
    def test_lead_validation_error(self):
        """Test LeadValidationError"""
        exc = LeadValidationError(
            "Invalid email format",
            context={"email": "invalid"}
        )
        
        assert exc.error_code == "LEAD_VALIDATION_ERROR"
        assert exc.status_code == 400
        assert exc.message == "Invalid email format"
        assert exc.context == {"email": "invalid"}
    
    def test_lead_not_found_error(self):
        """Test LeadNotFoundError"""
        exc = LeadNotFoundError(
            "Lead 123 not found",
            context={"lead_id": 123}
        )
        
        assert exc.error_code == "LEAD_NOT_FOUND"
        assert exc.status_code == 404
        assert exc.context == {"lead_id": 123}
    
    def test_lead_qualification_error(self):
        """Test LeadQualificationError"""
        exc = LeadQualificationError(
            "Qualification failed",
            context={"lead_id": 123, "reason": "API timeout"}
        )
        
        assert exc.error_code == "LEAD_QUALIFICATION_ERROR"
        assert exc.status_code == 500


class TestVoiceExceptions:
    """Test voice-related exceptions"""
    
    def test_cartesia_api_error(self):
        """Test CartesiaAPIError"""
        exc = CartesiaAPIError(
            "Voice generation failed",
            context={"voice_id": "abc123"}
        )
        
        assert exc.error_code == "CARTESIA_API_ERROR"
        assert exc.status_code == 502
    
    def test_voice_generation_error(self):
        """Test VoiceGenerationError"""
        exc = VoiceGenerationError(
            "Failed to generate voice",
            context={"text": "Hello"}
        )
        
        assert exc.error_code == "VOICE_GENERATION_ERROR"
        assert exc.status_code == 500
    
    def test_audio_processing_error(self):
        """Test AudioProcessingError"""
        exc = AudioProcessingError(
            "Audio processing failed",
            context={"format": "wav"}
        )
        
        assert exc.error_code == "AUDIO_PROCESSING_ERROR"
        assert exc.status_code == 500
    
    def test_voice_session_not_found(self):
        """Test VoiceSessionNotFoundError"""
        exc = VoiceSessionNotFoundError(
            "Session not found",
            context={"session_id": "xyz"}
        )
        
        assert exc.error_code == "VOICE_SESSION_NOT_FOUND"
        assert exc.status_code == 404


class TestDocumentExceptions:
    """Test document-related exceptions"""
    
    def test_pdf_processing_error(self):
        """Test PDFProcessingError"""
        exc = PDFProcessingError(
            "Failed to extract text",
            context={"filename": "test.pdf"}
        )
        
        assert exc.error_code == "PDF_PROCESSING_ERROR"
        assert exc.status_code == 500
    
    def test_document_parsing_error(self):
        """Test DocumentParsingError"""
        exc = DocumentParsingError(
            "Invalid document structure",
            context={"filename": "test.docx"}
        )
        
        assert exc.error_code == "DOCUMENT_PARSING_ERROR"
        assert exc.status_code == 422
    
    def test_document_not_found_error(self):
        """Test DocumentNotFoundError"""
        exc = DocumentNotFoundError(
            "Document not found",
            context={"document_id": 456}
        )
        
        assert exc.error_code == "DOCUMENT_NOT_FOUND"
        assert exc.status_code == 404
    
    def test_unsupported_document_type(self):
        """Test UnsupportedDocumentTypeError"""
        exc = UnsupportedDocumentTypeError(
            "Unsupported file type: .exe",
            context={"file_extension": "exe"}
        )
        
        assert exc.error_code == "UNSUPPORTED_DOCUMENT_TYPE"
        assert exc.status_code == 400
    
    def test_document_too_large(self):
        """Test DocumentTooLargeError"""
        exc = DocumentTooLargeError(
            "File exceeds 10MB limit",
            context={"file_size_mb": 15.5, "max_size_mb": 10}
        )
        
        assert exc.error_code == "DOCUMENT_TOO_LARGE"
        assert exc.status_code == 413


class TestExternalAPIExceptions:
    """Test external API exceptions"""
    
    def test_api_connection_error(self):
        """Test APIConnectionError"""
        exc = APIConnectionError(
            "Failed to connect to API",
            context={"api": "HubSpot", "url": "https://api.hubspot.com"}
        )
        
        assert exc.error_code == "API_CONNECTION_ERROR"
        assert exc.status_code == 502
    
    def test_api_rate_limit_error(self):
        """Test APIRateLimitError with retry_after"""
        exc = APIRateLimitError(
            "Rate limit exceeded",
            context={"api": "OpenAI"},
            retry_after=60
        )
        
        assert exc.error_code == "API_RATE_LIMIT_ERROR"
        assert exc.status_code == 429
        assert exc.retry_after == 60
    
    def test_api_authentication_error(self):
        """Test APIAuthenticationError"""
        exc = APIAuthenticationError(
            "Invalid API key",
            context={"api": "Stripe"}
        )
        
        assert exc.error_code == "API_AUTHENTICATION_ERROR"
        assert exc.status_code == 401
    
    def test_api_timeout_error(self):
        """Test APITimeoutError"""
        exc = APITimeoutError(
            "Request timed out",
            context={"api": "Cerebras", "timeout_ms": 30000}
        )
        
        assert exc.error_code == "API_TIMEOUT_ERROR"
        assert exc.status_code == 504


class TestConfigurationExceptions:
    """Test configuration exceptions"""
    
    def test_configuration_error(self):
        """Test ConfigurationError"""
        exc = ConfigurationError(
            "Invalid configuration",
            context={"setting": "DATABASE_URL"}
        )
        
        assert exc.error_code == "CONFIGURATION_ERROR"
        assert exc.status_code == 500
    
    def test_missing_api_key_error(self):
        """Test MissingAPIKeyError"""
        exc = MissingAPIKeyError(
            "CEREBRAS_API_KEY not set",
            context={"api_key": "CEREBRAS_API_KEY"}
        )
        
        assert exc.error_code == "MISSING_API_KEY"
        assert exc.status_code == 500


class TestValidationExceptions:
    """Test validation exceptions"""
    
    def test_validation_error(self):
        """Test ValidationError"""
        exc = ValidationError(
            "Invalid input",
            context={"field": "email"}
        )
        
        assert exc.error_code == "VALIDATION_ERROR"
        assert exc.status_code == 400
    
    def test_invalid_input_error(self):
        """Test InvalidInputError"""
        exc = InvalidInputError(
            "Invalid email format",
            context={"email": "invalid"}
        )
        
        assert exc.error_code == "INVALID_INPUT"
        assert exc.status_code == 400


class TestResourceExceptions:
    """Test resource exceptions"""
    
    def test_resource_not_found_error(self):
        """Test ResourceNotFoundError"""
        exc = ResourceNotFoundError(
            "Resource not found",
            context={"resource_type": "User", "id": 123}
        )
        
        assert exc.error_code == "RESOURCE_NOT_FOUND"
        assert exc.status_code == 404
    
    def test_resource_conflict_error(self):
        """Test ResourceConflictError"""
        exc = ResourceConflictError(
            "Resource already exists",
            context={"email": "test@example.com"}
        )
        
        assert exc.error_code == "RESOURCE_CONFLICT"
        assert exc.status_code == 409


class TestExceptionInheritance:
    """Test exception inheritance hierarchy"""
    
    def test_lead_exception_inheritance(self):
        """Test LeadException inherits from SalesAgentException"""
        exc = LeadValidationError("test")
        
        assert isinstance(exc, LeadException)
        assert isinstance(exc, SalesAgentException)
        assert isinstance(exc, Exception)
    
    def test_voice_exception_inheritance(self):
        """Test VoiceException inherits from SalesAgentException"""
        exc = CartesiaAPIError("test")
        
        assert isinstance(exc, VoiceException)
        assert isinstance(exc, SalesAgentException)
        assert isinstance(exc, Exception)
    
    def test_document_exception_inheritance(self):
        """Test DocumentException inherits from SalesAgentException"""
        exc = PDFProcessingError("test")
        
        assert isinstance(exc, DocumentException)
        assert isinstance(exc, SalesAgentException)
        assert isinstance(exc, Exception)
    
    def test_external_api_exception_inheritance(self):
        """Test ExternalAPIException inherits from SalesAgentException"""
        exc = APIConnectionError("test")
        
        assert isinstance(exc, ExternalAPIException)
        assert isinstance(exc, SalesAgentException)
        assert isinstance(exc, Exception)


class TestErrorCodeMapping:
    """Test error code mapping catalog"""
    
    def test_error_code_mapping_exists(self):
        """Test ERROR_CODE_MAPPING dictionary exists"""
        assert isinstance(ERROR_CODE_MAPPING, dict)
        assert len(ERROR_CODE_MAPPING) > 0
    
    def test_all_error_codes_mapped(self):
        """Test all exception classes are in mapping"""
        expected_codes = [
            "SALES_AGENT_ERROR",
            "LEAD_ERROR",
            "LEAD_VALIDATION_ERROR",
            "LEAD_NOT_FOUND",
            "LEAD_QUALIFICATION_ERROR",
            "VOICE_ERROR",
            "CARTESIA_API_ERROR",
            "VOICE_GENERATION_ERROR",
            "AUDIO_PROCESSING_ERROR",
            "VOICE_SESSION_NOT_FOUND",
            "DOCUMENT_ERROR",
            "PDF_PROCESSING_ERROR",
            "DOCUMENT_PARSING_ERROR",
            "DOCUMENT_NOT_FOUND",
            "UNSUPPORTED_DOCUMENT_TYPE",
            "DOCUMENT_TOO_LARGE",
            "EXTERNAL_API_ERROR",
            "API_CONNECTION_ERROR",
            "API_RATE_LIMIT_ERROR",
            "API_AUTHENTICATION_ERROR",
            "API_TIMEOUT_ERROR",
            "CONFIGURATION_ERROR",
            "MISSING_API_KEY",
            "VALIDATION_ERROR",
            "INVALID_INPUT",
            "RESOURCE_NOT_FOUND",
            "RESOURCE_CONFLICT",
        ]
        
        for code in expected_codes:
            assert code in ERROR_CODE_MAPPING, f"Error code {code} not in mapping"
    
    def test_mapping_values_are_classes(self):
        """Test all mapping values are exception classes"""
        for code, exc_class in ERROR_CODE_MAPPING.items():
            assert isinstance(exc_class, type)
            assert issubclass(exc_class, SalesAgentException)


class TestExceptionRaising:
    """Test exception raising and catching"""
    
    def test_raise_and_catch_lead_exception(self):
        """Test raising and catching LeadNotFoundError"""
        with pytest.raises(LeadNotFoundError) as exc_info:
            raise LeadNotFoundError("Lead not found", context={"lead_id": 123})
        
        exc = exc_info.value
        assert exc.message == "Lead not found"
        assert exc.context == {"lead_id": 123}
    
    def test_catch_as_base_exception(self):
        """Test catching specific exception as base SalesAgentException"""
        with pytest.raises(SalesAgentException) as exc_info:
            raise LeadNotFoundError("Lead not found")
        
        exc = exc_info.value
        assert isinstance(exc, LeadNotFoundError)
        assert isinstance(exc, SalesAgentException)
    
    def test_exception_message_accessibility(self):
        """Test exception message is accessible via str()"""
        exc = LeadValidationError("Invalid email", context={"email": "test"})
        
        message = str(exc)
        assert "LEAD_VALIDATION_ERROR" in message
        assert "Invalid email" in message
